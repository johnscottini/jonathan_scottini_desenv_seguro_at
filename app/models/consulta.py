from datetime import datetime
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class StatusConsulta(str, Enum):
    agendada = "agendada"
    realizada = "realizada"
    cancelada = "cancelada"


def _garantir_data_futura(valor: Optional[datetime]) -> Optional[datetime]:
    if valor is None:
        return valor
    agora = datetime.now(valor.tzinfo) if valor.tzinfo else datetime.now()
    if valor <= agora:
        raise ValueError("a consulta precisa ser agendada para uma data futura")
    return valor


# Nome de um exame solicitado; a lista é o que o laboratório parceiro enxerga (Exercício 7).
NomeExame = Annotated[str, StringConstraints(min_length=1, max_length=80)]


# Exercício 11: tabela do banco. Os campos internos (paciente_id, profissional_id,
# prontuario_paciente, audit_*) vivem aqui, mas ConsultaResponse não os expõe.
class Consulta(SQLModel, table=True):
    __tablename__ = "consultas"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    paciente_id: str = SQLField(foreign_key="usuarios.id", index=True)
    profissional_id: str = SQLField(foreign_key="usuarios.id", index=True)
    paciente: str
    profissional: str
    especialidade: str
    data_hora: datetime
    motivo: str
    # SQLite não tem tipo nativo de lista: a coluna é serializada como JSON.
    exames_solicitados: List[str] = SQLField(default_factory=list, sa_column=Column(JSON))
    status: StatusConsulta = SQLField(default=StatusConsulta.agendada)
    prontuario_paciente: int
    audit_token: str
    audit_origem_ip: str
    audit_criado_em: datetime


class ConsultaCreate(BaseModel):
    # Campo não declarado no corpo é rejeitado com 422, em vez de ignorado em silêncio.
    model_config = ConfigDict(extra="forbid")

    # Username de um usuário com papel paciente. O profissional não vem do corpo:
    # é sempre quem está autenticado (Exercício 6).
    paciente: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9._-]+$")
    especialidade: str = Field(..., min_length=1, max_length=80)
    data_hora: datetime
    motivo: str = Field(..., min_length=1, max_length=500)
    exames_solicitados: List[NomeExame] = Field(default_factory=list, max_length=10)

    _data_futura = field_validator("data_hora")(_garantir_data_futura)


class ConsultaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    especialidade: Optional[str] = Field(default=None, min_length=1, max_length=80)
    data_hora: Optional[datetime] = None
    motivo: Optional[str] = Field(default=None, min_length=1, max_length=500)
    status: Optional[StatusConsulta] = None
    exames_solicitados: Optional[List[NomeExame]] = Field(default=None, max_length=10)

    _data_futura = field_validator("data_hora")(_garantir_data_futura)


# Exercício 2: formato que devolve a API de volta ao cliente. Os campos
# internos guardados em consultas_db (paciente_id, profissional_id,
# prontuario_paciente, audit_*) não existem aqui, então nunca são serializados.
class ConsultaResponse(BaseModel):
    id: int
    paciente: str
    profissional: str
    especialidade: str
    data_hora: datetime
    motivo: str
    status: StatusConsulta
    exames_solicitados: List[str]
