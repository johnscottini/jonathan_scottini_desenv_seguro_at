from typing import Union

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlmodel import Session
from app.rate_limit import limitar_requisicoes
from fastapi.security import OAuth2PasswordRequestForm

from app.config import settings
from app.database import clientes_m2m_db, usuarios_db
from app.database.session import get_session
from app.mfa import gerar_desafio, verificar_desafio
from app.models.token import DesafioMFA, Token, TokenM2M
from app.models.usuario import PapelUsuario, UsuarioCreate, UsuarioResponse
from app.security import autenticar_usuario, token_de_cliente_m2m, token_de_usuario

router = APIRouter()

# Exercício 10: 5 tentativas de login por minuto e por IP. O mesmo limitador cobre a
# API e o formulário HTML, que atacam a mesma superfície.
limite_login = limitar_requisicoes(limite=lambda: settings.login_rate_limit, janela_segundos=60)

def _credenciais_invalidas() -> HTTPException:
    # Mesma resposta para usuário inexistente e senha errada: não revela quem existe.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuário ou senha incorretos",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/usuarios", response_model=UsuarioResponse, status_code=201)
def cadastrar_paciente(dados: UsuarioCreate, session: Session = Depends(get_session)):
    if usuarios_db.obter_por_username(session, dados.username) is not None:
        raise HTTPException(status_code=409, detail="Nome de usuário já cadastrado")
    return usuarios_db.criar_usuario(session, dados.username, dados.nome, dados.password, PapelUsuario.paciente.value)


def iniciar_login(session: Session, username: str, password: str) -> Union[Token, DesafioMFA]:
    """Etapa da senha, compartilhada entre a API e o formulário HTML."""
    usuario = autenticar_usuario(session, username, password)
    if usuario is None:
        raise _credenciais_invalidas()
    if usuario.papel == PapelUsuario.administrador.value:
        mfa_token, codigo = gerar_desafio(usuario.id)
        return DesafioMFA(
            mfa_token=mfa_token,
            mensagem="Contas administrativas exigem segundo fator. Envie o código em POST /token/mfa.",
            codigo_simulado=codigo,
        )
    return Token(access_token=token_de_usuario(usuario))


def concluir_mfa(session: Session, mfa_token: str, codigo: str) -> Token:
    usuario_id = verificar_desafio(mfa_token, codigo)
    usuario = usuarios_db.obter_por_id(session, usuario_id) if usuario_id else None
    if usuario is None:
        raise HTTPException(status_code=401, detail="Código MFA inválido ou expirado")
    return Token(access_token=token_de_usuario(usuario))


@router.post("/token", response_model=Union[Token, DesafioMFA], dependencies=[Depends(limite_login)])
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    return iniciar_login(session, form_data.username, form_data.password)


@router.post("/token/mfa", response_model=Token)
def confirmar_mfa(
    mfa_token: str = Form(...),
    codigo: str = Form(..., min_length=6, max_length=6),
    session: Session = Depends(get_session),
):
    return concluir_mfa(session, mfa_token, codigo)


@router.post("/token/m2m", response_model=TokenM2M)
def login_m2m(
    grant_type: str = Form(..., pattern="^client_credentials$"),
    client_id: str = Form(..., max_length=100),
    client_secret: str = Form(..., max_length=200),
    scope: str = Form(default=""),
    session: Session = Depends(get_session),
):
    """Exercício 7: OAuth 2.0 Client Credentials Grant, para integração máquina a máquina."""
    cliente = clientes_m2m_db.autenticar(session, client_id, client_secret)
    if cliente is None:
        raise HTTPException(status_code=401, detail="invalid_client")

    # O cliente pode pedir um subconjunto dos escopos contratados, nunca um a mais.
    pedidos = scope.split() or cliente.escopos
    if not set(pedidos) <= set(cliente.escopos):
        raise HTTPException(status_code=400, detail="invalid_scope")

    return TokenM2M(
        access_token=token_de_cliente_m2m(cliente, pedidos),
        expires_in=settings.m2m_token_expire_minutes * 60,
        scope=" ".join(pedidos),
    )
