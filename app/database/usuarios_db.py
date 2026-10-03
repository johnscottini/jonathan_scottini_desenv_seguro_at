from typing import Optional

from sqlmodel import Session, select

from app.hashing import hash_senha
from app.models.usuario import Usuario


def criar_usuario(session: Session, username: str, nome: str, senha: str, papel: str) -> Usuario:
    usuario = Usuario(username=username, nome=nome, hashed_password=hash_senha(senha), papel=papel)
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


def obter_por_id(session: Session, usuario_id: str) -> Optional[Usuario]:
    return session.get(Usuario, usuario_id)


def obter_por_username(session: Session, username: str) -> Optional[Usuario]:
    return session.exec(select(Usuario).where(Usuario.username == username)).first()


def listar_usuarios(session: Session) -> list[Usuario]:
    return list(session.exec(select(Usuario)).all())
