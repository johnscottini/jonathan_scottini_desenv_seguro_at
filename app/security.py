from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from app.config import settings
from app.database import usuarios_db
from app.hashing import HASH_FICTICIO, verificar_senha
from app.models.usuario import PapelUsuario

ESCOPOS = {
    "consultas:read": "Ler consultas (as próprias, ou as dos próprios pacientes)",
    "consultas:write": "Criar e gerenciar consultas dos próprios pacientes",
    "admin": "Operações administrativas",
    "exames:read": "Laboratório: ler pedidos de exame",
    "exames:write": "Laboratório: enviar resultados de exame",
}

# RBAC: o papel determina o conjunto de escopos do token. A decisão sobre *qual*
# consulta cada um enxerga é a checagem de dono, feita por recurso nas rotas.
ESCOPOS_POR_PAPEL = {
    PapelUsuario.paciente.value: ["consultas:read"],
    PapelUsuario.profissional.value: ["consultas:read", "consultas:write"],
    PapelUsuario.administrador.value: ["consultas:read", "consultas:write", "admin"],
}

# Escopos que o laboratório parceiro pode receber. Nenhum papel humano os tem, e o
# laboratório não tem nenhum escopo de consultas:* (Exercício 7).
ESCOPOS_LABORATORIO = ["exames:read", "exames:write"]

COOKIE_SESSAO = "sessao"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scopes=ESCOPOS)


def autenticar_usuario(session: Session, username: str, senha: str):
    usuario = usuarios_db.obter_por_username(session, username)
    if usuario is None:
        # Verifica contra um hash fictício mesmo sem usuário, para não vazar por tempo
        # de resposta quais usernames existem (CWE-204).
        verificar_senha(senha, HASH_FICTICIO)
        return None
    if not verificar_senha(senha, usuario.hashed_password):
        return None
    return usuario


def criar_access_token(claims: dict, expira_em: timedelta) -> str:
    agora = datetime.now(timezone.utc)
    dados = {
        **claims,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": agora,
        "exp": agora + expira_em,
    }
    return jwt.encode(dados, settings.secret_key, algorithm=settings.algorithm)


def token_de_usuario(usuario: dict) -> str:
    return criar_access_token(
        {
            "sub": usuario.id,
            "tipo_cliente": "usuario",
            "papel": usuario.papel,
            "escopos": ESCOPOS_POR_PAPEL[usuario.papel],
        },
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def token_de_cliente_m2m(cliente: dict, escopos: list[str]) -> str:
    # Sem "papel": um cliente M2M não é uma pessoa e não herda nenhum papel humano.
    return criar_access_token(
        {"sub": cliente.client_id, "tipo_cliente": "m2m", "escopos": escopos},
        timedelta(minutes=settings.m2m_token_expire_minutes),
    )


def decodificar_token(token: str) -> Optional[dict]:
    """Valida assinatura, algoritmo, expiração, emissor e audiência. None se qualquer um falhar."""
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            # Lista explícita: um token com "alg": "none" ou outro algoritmo é recusado.
            algorithms=[settings.algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError:
        return None


def _identidade(payload: dict) -> dict:
    return {
        "id": payload["sub"],
        "tipo_cliente": payload.get("tipo_cliente", "usuario"),
        "papel": payload.get("papel"),
        "escopos": payload.get("escopos", []),
    }


def get_current_user(security_scopes: SecurityScopes, token: str = Depends(oauth2_scheme)) -> dict:
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"' if security_scopes.scopes else "Bearer"
    )
    payload = decodificar_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar as credenciais",
            headers={"WWW-Authenticate": authenticate_value},
        )

    identidade = _identidade(payload)
    for escopo in security_scopes.scopes:
        if escopo not in identidade["escopos"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Escopo insuficiente para esta operação",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return identidade


def get_cliente_m2m(security_scopes: SecurityScopes, token: str = Depends(oauth2_scheme)) -> dict:
    """Rotas do laboratório: além do escopo, exige que o token seja de um cliente M2M.

    Os escopos já bastariam hoje, porque nenhum papel humano recebe exames:*. A checagem
    de tipo impede que uma mudança futura em ESCOPOS_POR_PAPEL abra estas rotas a pessoas.
    """
    cliente = get_current_user(security_scopes, token)
    if cliente["tipo_cliente"] != "m2m":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rota exclusiva de integrações M2M")
    return cliente


class RedirecionarParaLogin(Exception):
    """Levantada pelas páginas HTML sem sessão válida; main.py a converte em redirect."""


def get_usuario_da_sessao(request: Request) -> dict:
    """Mesma validação do JWT da API, mas lendo o token do cookie de sessão das páginas."""
    token = request.cookies.get(COOKIE_SESSAO)
    payload = decodificar_token(token) if token else None
    if payload is None or payload.get("tipo_cliente") != "usuario":
        raise RedirecionarParaLogin()
    identidade = _identidade(payload)
    if "consultas:read" not in identidade["escopos"]:
        raise RedirecionarParaLogin()
    return identidade


def eh_admin(usuario: dict) -> bool:
    return usuario["papel"] == PapelUsuario.administrador.value


def autorizar_dono(recurso: Optional[dict], usuario: dict, campos_dono: list[str]) -> dict:
    """Exercício 9: checagem de ownership centralizada, reusada por consultas e prontuários.

    Um recurso inexistente e um recurso de outra pessoa devolvem o MESMO 404, para não
    confirmar a existência do objeto (evita enumeração de dados de saúde). Administrador
    tem passe livre, como já era desde o Exercício 6.
    """
    if recurso is None:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    if eh_admin(usuario):
        return recurso
    if usuario["id"] not in {getattr(recurso, campo) for campo in campos_dono}:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    return recurso
