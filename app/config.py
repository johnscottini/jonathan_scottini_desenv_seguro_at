from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Segredos e parâmetros de segurança vêm do .env, nunca do código-fonte."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Exercício 11: URL do banco vem do .env, nunca hardcoded. Default só para dev local.
    database_url: str = "sqlite:///./agendamento.db"

    secret_key: str
    algorithm: str = "HS256"
    jwt_issuer: str = "agendamento-api"
    jwt_audience: str = "agendamento-api"
    access_token_expire_minutes: int = 30
    m2m_token_expire_minutes: int = 15

    # Exercício 10: tentativas de login por minuto e por IP.
    login_rate_limit: int = 5

    # Conta administrativa inicial: o cadastro público só cria pacientes, então
    # alguém precisa existir para criar profissionais e outros administradores.
    admin_username: str
    admin_password: str

    # Laboratório parceiro (Exercício 7), semeado na inicialização.
    lab_client_id: str = "laboratorio-parceiro"
    lab_client_secret: str

    # Custo do bcrypt (2^rounds iterações). 12 é o padrão do passlib; a suíte de testes
    # reduz para rodar rápido, sem mudar o algoritmo.
    bcrypt_rounds: int = 12

    # Em produção a aplicação roda atrás de HTTPS e o cookie só trafega cifrado.
    cookie_secure: bool = True


settings = Settings()
