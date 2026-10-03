from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


# Exercício 11: registro clínico persistido em banco relacional (guarda obrigatória).
class Prontuario(SQLModel, table=True):
    __tablename__ = "prontuarios"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    consulta_id: int = SQLField(foreign_key="consultas.id", unique=True)
    paciente_id: str = SQLField(index=True)
    profissional_id: str = SQLField(index=True)
    paciente: str
    profissional: str
    diagnostico: str
    anotacoes: str
    prescricao: Optional[str] = None
    criado_em: datetime
    atualizado_em: Optional[datetime] = None


class ProntuarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostico: str = Field(..., min_length=1, max_length=200)
    anotacoes: str = Field(..., min_length=1, max_length=5000)
    prescricao: Optional[str] = Field(default=None, max_length=2000)


class ProntuarioUpdate(BaseModel):
    # Exercício 9: campo não declarado é rejeitado com 422. Antes, extra="allow" deixava
    # o cliente injetar colunas internas (criado_em, profissional) direto no UPDATE.
    model_config = ConfigDict(extra="forbid")

    diagnostico: Optional[str] = Field(default=None, min_length=1, max_length=200)
    anotacoes: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    prescricao: Optional[str] = Field(default=None, max_length=2000)


class ProntuarioResponse(BaseModel):
    id: int
    consulta_id: int
    paciente: str
    profissional: str
    diagnostico: str
    anotacoes: str
    prescricao: Optional[str]
    criado_em: datetime
    atualizado_em: Optional[datetime]
