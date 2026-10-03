from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.config import settings
from app.database import clientes_m2m_db, usuarios_db
from app.database import session as db_session
from app.database.session import criar_tabelas
from app.middleware import ALLOWED_ORIGINS, SecurityHeadersMiddleware
from app.models.usuario import PapelUsuario
from app.routes import admin, auth, consultas, laboratorio, paginas, prontuarios
from app.security import ESCOPOS_LABORATORIO, RedirecionarParaLogin


def semear(session: Session) -> None:
    """Conta administrativa e laboratório parceiro iniciais, lidos do .env. Só criados
    se ainda não existirem — idempotente entre reinícios (Exercício 11)."""
    if usuarios_db.obter_por_username(session, settings.admin_username) is None:
        usuarios_db.criar_usuario(
            session, settings.admin_username, "Administrador", settings.admin_password, PapelUsuario.administrador.value
        )
    if clientes_m2m_db.obter(session, settings.lab_client_id) is None:
        clientes_m2m_db.registrar_cliente(
            session, settings.lab_client_id, settings.lab_client_secret, "Laboratório Parceiro", ESCOPOS_LABORATORIO
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_tabelas()
    with Session(db_session.engine) as session:
        semear(session)
    yield


app = FastAPI(title="agendamento-api", lifespan=lifespan)

# Exercício 10: SecurityHeadersMiddleware antes do CORS, para o CORS ficar na camada
# mais externa e as respostas que ele gera também receberem os cabeçalhos.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RedirecionarParaLogin)
def redirecionar_para_login(request: Request, exc: RedirecionarParaLogin):
    return RedirectResponse("/pagina/login", status_code=303)


@app.get("/")
def status_servico():
    return {"status": "ok", "servico": "agendamento-api"}


app.include_router(auth.router, tags=["auth"])
app.include_router(consultas.router, tags=["consultas"])
app.include_router(prontuarios.router, tags=["prontuarios"])
app.include_router(admin.router, tags=["admin"])
app.include_router(laboratorio.router, tags=["laboratorio"])
app.include_router(paginas.router, tags=["paginas"])
