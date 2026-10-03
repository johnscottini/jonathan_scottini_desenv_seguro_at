from typing import Optional

from sqlmodel import Session

from app.hashing import HASH_FICTICIO, hash_senha, verificar_senha
from app.models.cliente_m2m import ClienteM2M


def registrar_cliente(session: Session, client_id: str, client_secret: str, nome: str, escopos: list[str]) -> ClienteM2M:
    """Os escopos ficam gravados no cadastro do cliente: é o contrato, em forma de dado."""
    cliente = ClienteM2M(
        client_id=client_id, hashed_secret=hash_senha(client_secret), nome=nome, escopos=escopos, ativo=True
    )
    session.add(cliente)
    session.commit()
    session.refresh(cliente)
    return cliente


def autenticar(session: Session, client_id: str, client_secret: str) -> Optional[ClienteM2M]:
    cliente = session.get(ClienteM2M, client_id)
    if cliente is None:
        verificar_senha(client_secret, HASH_FICTICIO)
        return None
    if not cliente.ativo or not verificar_senha(client_secret, cliente.hashed_secret):
        return None
    return cliente


def obter(session: Session, client_id: str) -> Optional[ClienteM2M]:
    return session.get(ClienteM2M, client_id)
