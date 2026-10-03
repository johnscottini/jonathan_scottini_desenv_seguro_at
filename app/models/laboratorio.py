from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PedidoExameResponse(BaseModel):
    """O que o laboratório enxerga de uma consulta. Minimização (LGPD, art. 6º, III):
    sem motivo, sem especialidade, sem profissional, sem ids internos."""

    consulta_id: int
    paciente: str
    data_hora: datetime
    exames_solicitados: list[str]


class ResultadoExameCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exame: str = Field(..., min_length=1, max_length=80)
    resultado: str = Field(..., min_length=1, max_length=2000)


class ResultadoExameResponse(BaseModel):
    id: int
    consulta_id: int
    exame: str
    resultado: str
    laboratorio: str
    recebido_em: datetime
