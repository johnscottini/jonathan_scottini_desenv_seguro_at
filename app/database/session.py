from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False é exigência do SQLite com o pool de conexões do FastAPI.
# Para outros bancos o connect_args fica vazio.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)


def criar_tabelas() -> None:
    # importa os módulos de modelo para registrar as tabelas no metadata antes de criar
    from app.models import cliente_m2m, consulta, prontuario, resultado, usuario  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Sessão por requisição, injetada com Depends(get_session) (Exercício 11)."""
    with Session(engine) as session:
        yield session
