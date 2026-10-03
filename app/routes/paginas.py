from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import prontuarios_db
from app.database.session import get_session
from app.models.token import DesafioMFA
from app.routes.auth import concluir_mfa, iniciar_login, limite_login
from app.routes.consultas import carregar_consulta, consultas_visiveis
from app.security import COOKIE_SESSAO, get_usuario_da_sessao

router = APIRouter(prefix="/pagina")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
# Jinja2Templates liga o auto-escape para arquivos .html: todo {{ }} sai com
# <, >, &, " e ' convertidos em entidades HTML (Exercício 2).
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _abrir_sessao(access_token: str) -> RedirectResponse:
    """Exercício 6: sessão das páginas em cookie, com o mesmo JWT emitido pela API."""
    resposta = RedirectResponse("/pagina/consultas", status_code=303)
    resposta.set_cookie(
        COOKIE_SESSAO,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        path="/pagina",
        httponly=True,  # inacessível a document.cookie: um XSS não consegue ler a sessão
        secure=settings.cookie_secure,  # só trafega em HTTPS
        samesite="strict",  # não é enviado em requisições vindas de outro site (CSRF)
    )
    return resposta


@router.get("/login")
def pagina_login(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login", dependencies=[Depends(limite_login)])
def enviar_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        resultado = iniciar_login(session, username, password)
    except HTTPException:
        return templates.TemplateResponse(
            request, "login.html", {"erro": "Usuário ou senha incorretos"}, status_code=401
        )
    if isinstance(resultado, DesafioMFA):
        return templates.TemplateResponse(request, "login_mfa.html", {"desafio": resultado})
    # Um token novo a cada login: não existe sessão anterior para ser "promovida"
    # (session fixation).
    return _abrir_sessao(resultado.access_token)


@router.post("/login/mfa")
def enviar_mfa(
    request: Request,
    mfa_token: str = Form(...),
    codigo: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        token = concluir_mfa(session, mfa_token, codigo)
    except HTTPException:
        return templates.TemplateResponse(
            request, "login.html", {"erro": "Código MFA inválido ou expirado"}, status_code=401
        )
    return _abrir_sessao(token.access_token)


@router.post("/logout")
def sair():
    resposta = RedirectResponse("/pagina/login", status_code=303)
    resposta.delete_cookie(COOKIE_SESSAO, path="/pagina")
    return resposta


# As páginas usam as mesmas funções de dados e de ownership da API JSON; só muda a apresentação.
@router.get("/consultas")
def pagina_lista_consultas(
    request: Request,
    usuario: dict = Depends(get_usuario_da_sessao),
    session: Session = Depends(get_session),
):
    return templates.TemplateResponse(
        request, "consultas_lista.html", {"consultas": consultas_visiveis(session, usuario), "usuario": usuario}
    )


@router.get("/consultas/{consulta_id}")
def pagina_detalhe_consulta(
    request: Request,
    consulta_id: int,
    usuario: dict = Depends(get_usuario_da_sessao),
    session: Session = Depends(get_session),
):
    consulta = carregar_consulta(session, consulta_id, usuario, escrita=False)
    return templates.TemplateResponse(
        request,
        "consulta_detalhe.html",
        {"consulta": consulta, "usuario": usuario, "prontuario": prontuarios_db.obter_por_consulta(session, consulta_id)},
    )


@router.get("/prontuarios/{prontuario_id}")
def pagina_prontuario(
    request: Request,
    prontuario_id: int,
    usuario: dict = Depends(get_usuario_da_sessao),
    session: Session = Depends(get_session),
):
    from app.security import autorizar_dono

    prontuario = prontuarios_db.obter_prontuario(session, prontuario_id)
    # Mesma checagem de dono da API: uma página não pode vazar prontuário alheio.
    prontuario = autorizar_dono(prontuario, usuario, ["paciente_id", "profissional_id"])
    return templates.TemplateResponse(
        request, "prontuario_detalhe.html", {"prontuario": prontuario, "usuario": usuario}
    )
