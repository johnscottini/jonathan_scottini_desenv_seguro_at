import os
from datetime import datetime, timedelta

# Configuração fixa dos testes, definida antes de importar a aplicação: a suíte não
# depende do .env local de quem roda. O banco é um SQLite em memória, recriado a cada teste.
os.environ.update(
    {
        "DATABASE_URL": "sqlite://",
        "SECRET_KEY": "chave-de-teste-apenas-para-a-suite-pytest-nao-usar-em-producao",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "senha-admin-teste",
        "LAB_CLIENT_ID": "laboratorio-parceiro",
        "LAB_CLIENT_SECRET": "segredo-lab-teste",
        "COOKIE_SECURE": "false",
        "BCRYPT_ROUNDS": "4",
        "LOGIN_RATE_LIMIT": "1000",
    }
)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import mfa  # noqa: E402
from app.database import session as db_session  # noqa: E402
from app.routes.auth import limite_login  # noqa: E402

SENHA = "senha-forte-123"


@pytest.fixture
def client():
    # Banco SQLite em memória compartilhado entre as conexões do teste (StaticPool),
    # recriado do zero a cada caso. Substitui o engine da aplicação pelo de teste.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db_session.engine = engine
    mfa.limpar()
    limite_login.limpar()

    from app.main import app  # importado aqui para o lifespan usar o engine de teste

    with TestClient(app) as c:  # o lifespan cria as tabelas e semeia admin + laboratório
        yield c

    SQLModel.metadata.drop_all(engine)
    mfa.limpar()
    limite_login.limpar()


def login(client, username, password=SENHA) -> dict:
    resposta = client.post("/token", data={"username": username, "password": password})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    if corpo.get("mfa_requerido"):
        resposta = client.post(
            "/token/mfa", data={"mfa_token": corpo["mfa_token"], "codigo": corpo["codigo_simulado"]}
        )
        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
    return {"Authorization": f"Bearer {corpo['access_token']}"}


@pytest.fixture
def db(client):
    """Sessão sobre o engine de teste, para os testes que inspecionam o banco direto."""
    from sqlmodel import Session

    with Session(db_session.engine) as session:
        yield session


@pytest.fixture
def admin_headers(client):
    return login(client, "admin", "senha-admin-teste")


@pytest.fixture
def criar_usuario(client, admin_headers):
    def _criar(username, papel, nome=None):
        resposta = client.post(
            "/admin/usuarios",
            json={"username": username, "nome": nome or username, "password": SENHA, "papel": papel},
            headers=admin_headers,
        )
        assert resposta.status_code == 201, resposta.text
        return login(client, username)

    return _criar


@pytest.fixture
def cenario(criar_usuario):
    """Dois profissionais e dois pacientes, com um token para cada um."""
    return {
        "dra_ana": criar_usuario("dra.ana", "profissional", "Dra. Ana Costa"),
        "dr_paulo": criar_usuario("dr.paulo", "profissional", "Dr. Paulo Lima"),
        "maria": criar_usuario("maria", "paciente", "Maria Souza"),
        "joao": criar_usuario("joao", "paciente", "João Pereira"),
    }


@pytest.fixture
def consulta_payload():
    return {
        "paciente": "maria",
        "especialidade": "Cardiologia",
        "data_hora": (datetime.now() + timedelta(days=7)).replace(microsecond=0).isoformat(),
        "motivo": "Retorno para avaliação de exames",
    }


@pytest.fixture
def limite_login_baixo():
    """Restaura o limite real de login (5/min) só para os testes de rate limiting."""
    from app.config import settings

    original = settings.login_rate_limit
    settings.login_rate_limit = 5
    limite_login.limpar()
    yield 5
    settings.login_rate_limit = original
