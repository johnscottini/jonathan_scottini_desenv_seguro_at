import uuid
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class PapelUsuario(str, Enum):
    paciente = "paciente"
    profissional = "profissional"
    administrador = "administrador"


# Exercício 11: tabela do banco, separada dos schemas de entrada/saída.
class Usuario(SQLModel, table=True):
    __tablename__ = "usuarios"

    id: str = SQLField(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    username: str = SQLField(index=True, unique=True)
    nome: str
    hashed_password: str
    papel: str


class UsuarioCreate(BaseModel):
    """Cadastro público: não tem campo de papel, então todo cadastro aberto é paciente."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9._-]+$")
    nome: str = Field(..., min_length=1, max_length=120)
    # bcrypt considera só os primeiros 72 bytes da senha; acima disso, o resto seria ignorado.
    password: str = Field(..., min_length=8, max_length=72)


class UsuarioAdminCreate(UsuarioCreate):
    """Cadastro feito por administrador, único caminho para criar profissional ou admin."""

    papel: PapelUsuario


class UsuarioResponse(BaseModel):
    username: str
    nome: str
    papel: PapelUsuario
