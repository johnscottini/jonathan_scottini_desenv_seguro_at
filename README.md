# agendamento-api

API REST em FastAPI para agendamento de consultas médicas, construída no AT (Assessment) de Desenvolvimento Seguro de Aplicações Web. O sistema trata dados de saúde de pacientes, que são dado pessoal sensível pela LGPD, e por isso cada decisão de exposição e de acesso está documentada em [docs/](docs/). A base de conhecimento da disciplina, consolidada dos TP1 a TP3, está em [docs/base_conhecimento.md](docs/base_conhecimento.md).

## Estrutura do projeto

- `app/main.py`: cria a aplicação `FastAPI()`, registra os middlewares (cabeçalhos de segurança e CORS), semeia o administrador e o laboratório parceiro no `lifespan` e registra os routers.
- `app/config.py`: `Settings(BaseSettings)` com segredos e parâmetros lidos do `.env`.
- `app/security.py`: autenticação e autorização — `OAuth2PasswordBearer` com escopos, emissão/validação de JWT, o helper central de ownership (`autorizar_dono`), a sessão das páginas e a dependency M2M.
- `app/hashing.py`: hashing de senha com bcrypt via passlib. `app/mfa.py`: segundo fator simulado.
- `app/rate_limit.py`: limitador por IP em janela deslizante. `app/middleware.py`: allowlist do CORS e cabeçalhos de segurança.
- `app/routes/`: `auth.py` (cadastro, login, MFA, M2M), `consultas.py`, `prontuarios.py`, `laboratorio.py` (rotas M2M), `admin.py` e `paginas.py` (HTML com sessão).
- `app/models/`: schemas Pydantic de entrada (com `extra="forbid"`) e de saída, separados do formato interno de armazenamento.
- `app/database/`: camada de acesso a dados em **SQLModel**, com `session.py` (engine, criação de tabelas, `get_session`) e um módulo por entidade, todos com queries parametrizadas.
- `app/templates/`: templates Jinja2 com herança (`base.html`) e auto-escape.
- `tests/`: suíte `pytest`.
- `docs/`: um documento por exercício, com evidências reais em `docs/evidencias/`.

## Como rodar

Requer Python 3.10 ou superior (desenvolvido no 3.12).

No macOS e no Linux:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # e preencher SECRET_KEY, ADMIN_PASSWORD, LAB_CLIENT_SECRET (DATABASE_URL tem default de dev)

uvicorn app.main:app --reload
```

No Windows (PowerShell), muda o caminho dos executáveis do venv — `Scripts\` no lugar de `bin/`:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env   # e preencher os mesmos segredos

uvicorn app.main:app --reload
```

O `uvloop` do `requirements.txt` tem marcador `sys_platform != "win32"`: ele não compila no Windows e é só um event loop alternativo, então o pip simplesmente o ignora lá e o uvicorn usa o asyncio padrão.

A API sobe em `http://127.0.0.1:8000` e cria o banco relacional (SQLite, `agendamento.db`) na primeira execução. Swagger em `/docs` (botão **Authorize** para colar o token de `/token`), páginas HTML em `/pagina/consultas` (exigem login em `/pagina/login`).

O `.env` guarda os segredos e não é versionado; o `.env.example` documenta as variáveis. O administrador inicial é criado a partir de `ADMIN_USERNAME`/`ADMIN_PASSWORD`, e o laboratório parceiro a partir de `LAB_CLIENT_ID`/`LAB_CLIENT_SECRET`.

## Testes

```bash
pytest -v
```

## Apresentação

[docs/roteiro_apresentacao.md](docs/roteiro_apresentacao.md) traz um roteiro de 5 minutos pelos endpoints principais, com a collection do Postman em [docs/apresentacao/](docs/apresentacao/) — as pastas estão na ordem da demo e cada login guarda o próprio token em variável, sem copiar e colar JWT. O environment versionado é o `.example`, sem segredos: duplicar e preencher a partir do `.env`.

Para a demonstração completa de segurança (CORS, cabeçalhos, SQLi, rate limiting), o `demo.sh` roda os 10 cenários em bash.

## Autenticação e papéis

- **Cadastro público** (`POST /usuarios`) sempre cria `paciente`. Profissionais e administradores só são criados por um administrador (`POST /admin/usuarios`).
- **Login humano** (`POST /token`): devolve o JWT, ou, para `administrador`, exige confirmar o MFA em `POST /token/mfa`. Limitado a 5 tentativas/minuto por IP.
- **Login M2M** (`POST /token/m2m`): fluxo Client Credentials, para o laboratório parceiro.
- **Modelo de autorização**: RBAC (escopos por papel) + ownership por recurso. O escopo é necessário mas não suficiente: em rotas com dono, `autorizar_dono` compara a identidade do token com o dono do recurso e responde `404` para quem não é dono.

| Papel | Escopos |
|---|---|
| `paciente` | `consultas:read` |
| `profissional` | `consultas:read`, `consultas:write` |
| `administrador` | `consultas:read`, `consultas:write`, `admin` (exige MFA) |
| Laboratório (M2M) | `exames:read`, `exames:write` (sem papel humano) |

## Endpoints principais

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| GET | `/` | — | Health check |
| POST | `/usuarios` | — | Cadastra paciente (senha em bcrypt) |
| POST | `/token` | — | Login; JWT ou desafio MFA. 5/min por IP |
| POST | `/token/mfa` | — | Confirma o MFA e devolve o JWT |
| POST | `/token/m2m` | — | Login do parceiro (client credentials) |
| GET/POST | `/admin/usuarios` | `admin` | Lista e cadastra usuários de qualquer papel |
| GET | `/consultas` | `consultas:read` | Lista as consultas do usuário (filtrada pelo dono) |
| POST | `/consultas` | `consultas:write` | Agenda consulta; o profissional vem do token |
| GET/PUT/DELETE | `/consultas/{id}` | `consultas:read`/`write` + ownership | Obtém, atualiza ou cancela (lógico) |
| POST | `/consultas/{id}/prontuario` | `consultas:write` + ownership | Registra o prontuário |
| GET/PUT | `/prontuarios/{id}` | `consultas:read`/`write` + ownership | Lê ou atualiza o prontuário |
| GET | `/prontuarios/busca?termo=` | `consultas:read` | Busca por diagnóstico (whitelist + query parametrizada) |
| GET | `/consultas/{id}/resultados` | `consultas:read` + ownership | Resultados de exame da consulta |
| GET | `/laboratorio/pedidos` | `exames:read` (M2M) | Pedidos de exame, sem dado clínico |
| POST | `/laboratorio/pedidos/{id}/resultados` | `exames:write` (M2M) | Envia resultado de exame |
| GET/POST | `/pagina/...` | Cookie de sessão | Páginas HTML (login, consultas, prontuário) |

## Pipeline de segurança (CI)

O workflow [.github/workflows/security.yml](.github/workflows/security.yml) roda em push/PR para `main`: SCA (`pip-audit`), SAST (`bandit`), a suíte `pytest` e DAST (OWASP ZAP baseline), com um security gate por severidade. Detalhes e a justificativa das fases do SDLC em [docs/exercicio12_devsecops.md](docs/exercicio12_devsecops.md).

## Exercícios

| # | Tema | Documento |
|---|---|---|
| 1 | Fundação: venv, módulos, APIRouter, pytest | [docs/exercicio1_fundacao.md](docs/exercicio1_fundacao.md) |
| 2 | `response_model` e templates seguros contra XSS | [docs/exercicio2_exposicao_templates.md](docs/exercicio2_exposicao_templates.md) |
| 3 | Tríade CIA, frameworks de referência e DFD | [docs/exercicio3_cia_dfd.md](docs/exercicio3_cia_dfd.md) |
| 4 | Misuse cases, STRIDE e threat model | [docs/exercicio4_threat_model_stride.md](docs/exercicio4_threat_model_stride.md) |
| 5 | Partições, fronteiras e vetores nos três eixos | [docs/exercicio5_arquitetura_vetores.md](docs/exercicio5_arquitetura_vetores.md) |
| 6 | Autenticação, MFA, JWT e ownership | [docs/exercicio6_autenticacao.md](docs/exercicio6_autenticacao.md) |
| 7 | Escopos e integração M2M com o laboratório | [docs/exercicio7_m2m_laboratorio.md](docs/exercicio7_m2m_laboratorio.md) |
| 8 | Identificação de vulnerabilidades OWASP (BOLA, SQLi, XSS, mass assignment) | [docs/exercicio8_vulnerabilidades.md](docs/exercicio8_vulnerabilidades.md) |
| 9 | Correção centralizada, com evidência antes/depois | [docs/exercicio9_correcoes.md](docs/exercicio9_correcoes.md) |
| 10 | CORS, cabeçalhos de segurança e rate limiting | [docs/exercicio10_hardening.md](docs/exercicio10_hardening.md) |
| 11 | Persistência segura com SQLModel | [docs/exercicio11_persistencia.md](docs/exercicio11_persistencia.md) |
| 12 | Pipeline DevSecOps e auditoria automatizada | [docs/exercicio12_devsecops.md](docs/exercicio12_devsecops.md) |
| 13 | Capstone: auditoria final e rastreabilidade | [docs/exercicio13_capstone.md](docs/exercicio13_capstone.md) |
