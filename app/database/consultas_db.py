import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models.consulta import Consulta, ConsultaCreate, ConsultaUpdate, StatusConsulta
from app.models.usuario import Usuario

# Exercício 11: toda leitura e escrita passa por estas funções, agora sobre uma Session
# do SQLModel. Nenhuma query é montada por concatenação de string.


def criar_consulta(session: Session, dados: ConsultaCreate, paciente: Usuario, profissional: Usuario, origem_ip: str) -> Consulta:
    consulta = Consulta(
        paciente_id=paciente.id,
        profissional_id=profissional.id,
        paciente=paciente.nome,
        profissional=profissional.nome,
        especialidade=dados.especialidade,
        data_hora=dados.data_hora,
        motivo=dados.motivo,
        exames_solicitados=list(dados.exames_solicitados),
        status=StatusConsulta.agendada,
        # Campos internos, filtrados por ConsultaResponse.
        prontuario_paciente=secrets.randbelow(900000) + 100000,
        audit_token=secrets.token_hex(8),
        audit_origem_ip=origem_ip,
        audit_criado_em=datetime.now(timezone.utc),
    )
    session.add(consulta)
    session.commit()
    session.refresh(consulta)
    return consulta


def listar_consultas(session: Session) -> list[Consulta]:
    return list(session.exec(select(Consulta)).all())


def listar_por_paciente(session: Session, paciente_id: str) -> list[Consulta]:
    return list(session.exec(select(Consulta).where(Consulta.paciente_id == paciente_id)).all())


def listar_por_profissional(session: Session, profissional_id: str) -> list[Consulta]:
    return list(session.exec(select(Consulta).where(Consulta.profissional_id == profissional_id)).all())


def listar_pedidos_de_exame(session: Session) -> list[Consulta]:
    consulta = select(Consulta).where(Consulta.status != StatusConsulta.cancelada)
    return [c for c in session.exec(consulta).all() if c.exames_solicitados]


def obter_consulta(session: Session, consulta_id: int) -> Optional[Consulta]:
    return session.get(Consulta, consulta_id)


def atualizar_consulta(session: Session, consulta: Consulta, dados: ConsultaUpdate) -> Consulta:
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(consulta, campo, valor)
    session.add(consulta)
    session.commit()
    session.refresh(consulta)
    return consulta


def cancelar_consulta(session: Session, consulta: Consulta) -> Consulta:
    # Cancelamento lógico: o registro de saúde e a sua trilha continuam existindo (AM-11).
    consulta.status = StatusConsulta.cancelada
    session.add(consulta)
    session.commit()
    session.refresh(consulta)
    return consulta
