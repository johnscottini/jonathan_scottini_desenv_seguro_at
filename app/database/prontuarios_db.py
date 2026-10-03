from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, col, select

from app.models.consulta import Consulta
from app.models.prontuario import Prontuario, ProntuarioCreate


def criar_prontuario(session: Session, consulta: Consulta, dados: ProntuarioCreate) -> Prontuario:
    prontuario = Prontuario(
        consulta_id=consulta.id,
        paciente_id=consulta.paciente_id,
        profissional_id=consulta.profissional_id,
        paciente=consulta.paciente,
        profissional=consulta.profissional,
        diagnostico=dados.diagnostico,
        anotacoes=dados.anotacoes,
        prescricao=dados.prescricao,
        criado_em=datetime.now(timezone.utc),
    )
    session.add(prontuario)
    session.commit()
    session.refresh(prontuario)
    return prontuario


def obter_prontuario(session: Session, prontuario_id: int) -> Optional[Prontuario]:
    return session.get(Prontuario, prontuario_id)


def obter_por_consulta(session: Session, consulta_id: int) -> Optional[Prontuario]:
    return session.exec(select(Prontuario).where(Prontuario.consulta_id == consulta_id)).first()


def buscar_por_diagnostico(session: Session, termo: str, usuario: dict) -> list[Prontuario]:
    # Exercício 11: a busca do Exercício 9 continua parametrizada, agora pelo próprio
    # SQLModel — não existe mais SQL montada como string. A coluna do dono é escolhida
    # por allowlist (atributo fixo do modelo), nunca vinda do request.
    coluna_dono = Prontuario.profissional_id if usuario["papel"] == "profissional" else Prontuario.paciente_id
    consulta = select(Prontuario).where(coluna_dono == usuario["id"], col(Prontuario.diagnostico).contains(termo))
    return list(session.exec(consulta).all())


def atualizar_prontuario(session: Session, prontuario: Prontuario, dados: dict) -> Prontuario:
    for campo, valor in dados.items():
        setattr(prontuario, campo, valor)
    prontuario.atualizado_em = datetime.now(timezone.utc)
    session.add(prontuario)
    session.commit()
    session.refresh(prontuario)
    return prontuario
