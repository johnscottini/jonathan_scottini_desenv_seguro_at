from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlmodel import Session

from app.database import prontuarios_db
from app.database.session import get_session
from app.models.prontuario import ProntuarioCreate, ProntuarioResponse, ProntuarioUpdate
from app.routes.consultas import carregar_consulta
from app.security import autorizar_dono, get_current_user

router = APIRouter()


@router.post("/consultas/{consulta_id}/prontuario", response_model=ProntuarioResponse, status_code=201)
def registrar_prontuario(
    consulta_id: int,
    dados: ProntuarioCreate,
    usuario: dict = Security(get_current_user, scopes=["consultas:write"]),
    session: Session = Depends(get_session),
):
    consulta = carregar_consulta(session, consulta_id, usuario, escrita=True)
    if prontuarios_db.obter_por_consulta(session, consulta_id) is not None:
        raise HTTPException(status_code=409, detail="A consulta já tem prontuário")
    return prontuarios_db.criar_prontuario(session, consulta, dados)


@router.get("/prontuarios/busca", response_model=list[ProntuarioResponse])
def buscar_prontuarios(
    # Exercício 9: whitelist por regex (defesa em profundidade sobre a query parametrizada).
    termo: str = Query(..., min_length=1, max_length=100, pattern=r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9 \-]+$"),
    usuario: dict = Security(get_current_user, scopes=["consultas:read"]),
    session: Session = Depends(get_session),
):
    return prontuarios_db.buscar_por_diagnostico(session, termo, usuario)


@router.get("/prontuarios/{prontuario_id}", response_model=ProntuarioResponse)
def obter_prontuario(
    prontuario_id: int,
    usuario: dict = Security(get_current_user, scopes=["consultas:read"]),
    session: Session = Depends(get_session),
):
    # Exercício 9 (correção do BOLA): ownership pelo mesmo helper central das consultas.
    prontuario = prontuarios_db.obter_prontuario(session, prontuario_id)
    return autorizar_dono(prontuario, usuario, ["paciente_id", "profissional_id"])


@router.put("/prontuarios/{prontuario_id}", response_model=ProntuarioResponse)
def atualizar_prontuario(
    prontuario_id: int,
    dados: ProntuarioUpdate,
    usuario: dict = Security(get_current_user, scopes=["consultas:write"]),
    session: Session = Depends(get_session),
):
    # Mesmo padrão de BOLA do GET; só o profissional dono escreve.
    prontuario = autorizar_dono(prontuarios_db.obter_prontuario(session, prontuario_id), usuario, ["profissional_id"])
    return prontuarios_db.atualizar_prontuario(session, prontuario, dados.model_dump(exclude_unset=True))
