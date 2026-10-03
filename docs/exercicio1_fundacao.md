# AT — Exercício 1: Fundação da API de agendamento

## Ambiente isolado

Ambiente virtual próprio em `venv/`, criado com o Python 3.12 (`python3.12 -m venv venv`), fora do versionamento pelo [.gitignore](../.gitignore). As dependências estão fixadas em [requirements.txt](../requirements.txt) com `pip freeze`. O servidor sobe com `uvicorn app.main:app`, e a resposta das rotas foi capturada com `curl` em [evidencias/exercicio1_fundacao.txt](evidencias/exercicio1_fundacao.txt).

## Estrutura modular

| Módulo | Responsabilidade |
|---|---|
| [app/main.py](../app/main.py) | Monta o `FastAPI()`, expõe `GET /` e registra os routers com `include_router` |
| [app/routes/consultas.py](../app/routes/consultas.py) | `APIRouter` do recurso consultas |
| [app/models/consulta.py](../app/models/consulta.py) | Schemas de entrada (`ConsultaCreate`, `ConsultaUpdate`) e de saída (`ConsultaResponse`) |
| [app/database/consultas_db.py](../app/database/consultas_db.py) | Acesso a dados; nenhuma rota lê o armazenamento diretamente |

Um router por recurso limita o raio de impacto de cada mudança: um recurso novo entra como um arquivo em `routes/`, sem tocar no código dos demais.

## Recurso RESTful `consultas`

| Método | Rota | Sucesso | Erros |
|---|---|---|---|
| GET | `/consultas` | `200` lista | — |
| POST | `/consultas` | `201` | `422` |
| GET | `/consultas/{id}` | `200` | `404` / `422` |
| PUT | `/consultas/{id}` | `200` | `404` / `422` |
| DELETE | `/consultas/{id}` | `204` | `404` |

A validação de entrada já está nos schemas desde a primeira versão: limite de tamanho nos campos de texto, `data_hora` obrigatoriamente no futuro e `extra="forbid"` (campo não declarado responde `422`). O status inicial é definido pelo servidor (`agendada`), não pelo cliente.

## Teste automatizado

[tests/test_consultas.py](../tests/test_consultas.py) usa o `TestClient` do FastAPI; a fixture `client` limpa o estado antes e depois de cada teste. O enunciado pedia pelo menos um caminho de sucesso — o arquivo cobre os cinco verbos do recurso, o health check e os casos de validação. É o arquivo que será expandido ao longo do Assessment.

```bash
./venv/bin/pytest -v
```

## Evidência

[evidencias/exercicio1_fundacao.txt](evidencias/exercicio1_fundacao.txt): o Python do venv isolado, o health check, o CRUD completo via `curl`, as validações (`422`) e a execução do `pytest`.
