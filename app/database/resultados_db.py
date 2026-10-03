from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.laboratorio import ResultadoExameCreate
from app.models.resultado import ResultadoExame


def registrar_resultado(session: Session, consulta_id: int, dados: ResultadoExameCreate, laboratorio: str) -> ResultadoExame:
    resultado = ResultadoExame(
        consulta_id=consulta_id,
        exame=dados.exame,
        resultado=dados.resultado,
        laboratorio=laboratorio,
        recebido_em=datetime.now(timezone.utc),
    )
    session.add(resultado)
    session.commit()
    session.refresh(resultado)
    return resultado


def listar_da_consulta(session: Session, consulta_id: int) -> list[ResultadoExame]:
    return list(session.exec(select(ResultadoExame).where(ResultadoExame.consulta_id == consulta_id)).all())
