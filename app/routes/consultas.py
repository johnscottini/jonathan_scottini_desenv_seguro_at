from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from sqlmodel import Session

from app.database import consultas_db, resultados_db, usuarios_db
from app.database.session import get_session
from app.models.consulta import ConsultaCreate, ConsultaResponse, ConsultaUpdate
from app.models.laboratorio import ResultadoExameResponse
from app.models.usuario import PapelUsuario
from app.security import autorizar_dono, eh_admin, get_current_user

router = APIRouter(prefix="/consultas")


def carregar_consulta(session: Session, consulta_id: int, usuario: dict, escrita: bool):
    """Ownership da consulta via helper central (Exercício 9). Leitura: paciente ou
    profissional. Escrita: só o profissional que a criou. Administrador passa nos dois."""
    consulta = consultas_db.obter_consulta(session, consulta_id)
    campos = ["profissional_id"] if escrita else ["profissional_id", "paciente_id"]
    return autorizar_dono(consulta, usuario, campos)


def consultas_visiveis(session: Session, usuario: dict) -> list:
    """Listagem filtrada pelo dono: ninguém além do administrador vê a agenda inteira."""
    if eh_admin(usuario):
        return consultas_db.listar_consultas(session)
    if usuario["papel"] == PapelUsuario.profissional.value:
        return consultas_db.listar_por_profissional(session, usuario["id"])
    return consultas_db.listar_por_paciente(session, usuario["id"])


@router.get("", response_model=list[ConsultaResponse])
def listar_consultas(
    usuario: dict = Security(get_current_user, scopes=["consultas:read"]),
    session: Session = Depends(get_session),
):
    return consultas_visiveis(session, usuario)


@router.post("", response_model=ConsultaResponse, status_code=201)
def criar_consulta(
    dados: ConsultaCreate,
    request: Request,
    usuario: dict = Security(get_current_user, scopes=["consultas:write"]),
    session: Session = Depends(get_session),
):
    paciente = usuarios_db.obter_por_username(session, dados.paciente)
    if paciente is None or paciente.papel != PapelUsuario.paciente.value:
        raise HTTPException(status_code=422, detail="Paciente não encontrado")
    profissional = usuarios_db.obter_por_id(session, usuario["id"])
    origem_ip = request.client.host if request.client else "desconhecido"
    return consultas_db.criar_consulta(session, dados, paciente, profissional, origem_ip)


@router.get("/{consulta_id}", response_model=ConsultaResponse)
def obter_consulta(
    consulta_id: int,
    usuario: dict = Security(get_current_user, scopes=["consultas:read"]),
    session: Session = Depends(get_session),
):
    return carregar_consulta(session, consulta_id, usuario, escrita=False)


@router.put("/{consulta_id}", response_model=ConsultaResponse)
def atualizar_consulta(
    consulta_id: int,
    dados: ConsultaUpdate,
    usuario: dict = Security(get_current_user, scopes=["consultas:write"]),
    session: Session = Depends(get_session),
):
    consulta = carregar_consulta(session, consulta_id, usuario, escrita=True)
    return consultas_db.atualizar_consulta(session, consulta, dados)


@router.delete("/{consulta_id}", status_code=204)
def cancelar_consulta(
    consulta_id: int,
    usuario: dict = Security(get_current_user, scopes=["consultas:write"]),
    session: Session = Depends(get_session),
):
    consulta = carregar_consulta(session, consulta_id, usuario, escrita=True)
    consultas_db.cancelar_consulta(session, consulta)
    return Response(status_code=204)


@router.get("/{consulta_id}/resultados", response_model=list[ResultadoExameResponse])
def listar_resultados(
    consulta_id: int,
    usuario: dict = Security(get_current_user, scopes=["consultas:read"]),
    session: Session = Depends(get_session),
):
    consulta = carregar_consulta(session, consulta_id, usuario, escrita=False)
    return resultados_db.listar_da_consulta(session, consulta.id)
