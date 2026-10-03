from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.bcrypt_rounds)

# Hash de uma senha qualquer, usado para gastar o mesmo tempo de verificação quando o
# usuário não existe. Sem isso, a resposta rápida denunciaria quais usernames existem.
HASH_FICTICIO = pwd_context.hash("senha-ficticia-para-tempo-constante")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    return pwd_context.verify(senha, hash_armazenado)
