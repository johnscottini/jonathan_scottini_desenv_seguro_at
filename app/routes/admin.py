from fastapi import APIRouter, Depends, HTTPException, Security
from sqlmodel import Session

from app.database import usuarios_db
from app.database.session import get_session
from app.models.usuario import UsuarioAdminCreate, UsuarioResponse
from app.security import get_current_user

# Toda rota deste router exige o escopo "admin", que só o papel administrador recebe,
# e só depois do segundo fator.
router = APIRouter(prefix="/admin")


@router.get("/usuarios", response_model=list[UsuarioResponse])
def listar_usuarios(
    _admin: dict = Security(get_current_user, scopes=["admin"]),
    session: Session = Depends(get_session),
):
    return usuarios_db.listar_usuarios(session)


@router.post("/usuarios", response_model=UsuarioResponse, status_code=201)
def cadastrar_usuario(
    dados: UsuarioAdminCreate,
    _admin: dict = Security(get_current_user, scopes=["admin"]),
    session: Session = Depends(get_session),
):
    if usuarios_db.obter_por_username(session, dados.username) is not None:
        raise HTTPException(status_code=409, detail="Nome de usuário já cadastrado")
    return usuarios_db.criar_usuario(session, dados.username, dados.nome, dados.password, dados.papel.value)
