from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenM2M(Token):
    # Campos da resposta de token do OAuth 2.0 (RFC 6749, seção 5.1).
    expires_in: int
    scope: str


class DesafioMFA(BaseModel):
    mfa_requerido: bool = True
    mfa_token: str
    mensagem: str
    # Simulação: em produção o código chegaria por app autenticador (TOTP), nunca na resposta.
    codigo_simulado: str
