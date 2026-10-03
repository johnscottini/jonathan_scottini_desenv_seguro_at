from typing import List

from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


# Exercício 11: cliente de integração M2M (laboratório parceiro).
class ClienteM2M(SQLModel, table=True):
    __tablename__ = "clientes_m2m"

    client_id: str = SQLField(primary_key=True)
    hashed_secret: str
    nome: str
    escopos: List[str] = SQLField(sa_column=Column(JSON))
    ativo: bool = True
