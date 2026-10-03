from datetime import datetime
from typing import Optional

from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


# Exercício 11: resultado de exame enviado pelo laboratório, agora persistido.
class ResultadoExame(SQLModel, table=True):
    __tablename__ = "resultados_exame"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    consulta_id: int = SQLField(foreign_key="consultas.id", index=True)
    exame: str
    resultado: str
    laboratorio: str
    recebido_em: datetime
