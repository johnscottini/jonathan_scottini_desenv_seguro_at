import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

_MFA_EXPIRE_MINUTES = 5
_MAX_TENTATIVAS = 3
_desafios: dict[str, dict] = {}


def gerar_desafio(usuario_id: str) -> tuple[str, str]:
    """Cria um desafio de segundo fator e devolve (mfa_token, codigo).

    O desafio é identificado por um token aleatório, não pelo username: quem confirma
    o código precisa ter passado pela etapa da senha, que é a única que recebe o token.
    """
    mfa_token = secrets.token_urlsafe(32)
    codigo = f"{secrets.randbelow(900000) + 100000}"
    _desafios[mfa_token] = {
        "usuario_id": usuario_id,
        "codigo": codigo,
        "expira": datetime.now(timezone.utc) + timedelta(minutes=_MFA_EXPIRE_MINUTES),
        "tentativas": 0,
    }
    return mfa_token, codigo


def verificar_desafio(mfa_token: str, codigo: str) -> Optional[str]:
    """Devolve o id do usuário se o código confere. Uso único, expira e tem limite de erros."""
    desafio = _desafios.get(mfa_token)
    if desafio is None:
        return None
    if datetime.now(timezone.utc) > desafio["expira"]:
        del _desafios[mfa_token]
        return None
    if not secrets.compare_digest(desafio["codigo"], codigo):
        desafio["tentativas"] += 1
        if desafio["tentativas"] >= _MAX_TENTATIVAS:
            del _desafios[mfa_token]
        return None
    del _desafios[mfa_token]
    return desafio["usuario_id"]


def limpar() -> None:
    _desafios.clear()
