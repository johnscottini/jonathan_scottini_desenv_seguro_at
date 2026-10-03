# AT — Exercício 11: Persistência segura com SQLModel

A aplicação deixou de guardar dados em dicionários de módulo (e num SQLite cru, no caso dos prontuários) e passou a usar um banco relacional único via SQLModel.

## O que mudou

As cinco entidades viraram tabelas SQLModel, cada uma ao lado dos schemas Pydantic de entrada/saída que já existiam:

| Entidade | Tabela | Antes |
|---|---|---|
| Usuário | `Usuario` ([models/usuario.py](../app/models/usuario.py)) | dict em memória |
| Consulta | `Consulta` ([models/consulta.py](../app/models/consulta.py)) | dict em memória |
| Prontuário | `Prontuario` ([models/prontuario.py](../app/models/prontuario.py)) | SQLite cru |
| Resultado | `ResultadoExame` ([models/resultado.py](../app/models/resultado.py)) | dict em memória |
| Cliente M2M | `ClienteM2M` ([models/cliente_m2m.py](../app/models/cliente_m2m.py)) | dict em memória |

Manter a tabela separada dos schemas é o que impede o acoplamento entre banco e resposta: `ConsultaResponse` continua sem `prontuario_paciente`, `paciente_id`, `profissional_id` e os `audit_*`, que existem na tabela. `exames_solicitados` e `escopos` (listas) são colunas `JSON`.

## Queries parametrizadas

Toda função de `app/database/` recebe uma `Session` e usa `session.get`, `session.add` e `select(...)`. Não existe mais SQL montada como string. A busca de prontuário, origem da SQLi do Exercício 8, agora é ([prontuarios_db.py](../app/database/prontuarios_db.py)):

```python
coluna_dono = Prontuario.profissional_id if usuario["papel"] == "profissional" else Prontuario.paciente_id
consulta = select(Prontuario).where(coluna_dono == usuario["id"], col(Prontuario.diagnostico).contains(termo))
```

O termo e o id do dono são valores vinculados; a coluna do dono é escolhida por allowlist. A whitelist por regex na rota permanece como defesa em profundidade. Um `grep` por SQL em f-string, `.format()` e `execute(` em `app/database/` não retorna ocorrência.

## Sessão por injeção de dependência

[session.py](../app/database/session.py) define o `engine`, `criar_tabelas()` e o gerador `get_session()`:

```python
def get_session():
    with Session(engine) as session:
        yield session
```

As rotas recebem a sessão com `Depends(get_session)` (os seis routers usam). O `lifespan` em [main.py](../app/main.py) cria as tabelas e semeia o admin e o laboratório, de forma idempotente.

## Credenciais via BaseSettings e `.env`

`Settings(BaseSettings)` ([config.py](../app/config.py)) lê `DATABASE_URL` do `.env`, junto com `SECRET_KEY`, `ADMIN_PASSWORD` e `LAB_CLIENT_SECRET`. O único literal de URL no código é o default de dev, sobrescrito pelo `.env`. Nenhuma credencial de banco aparece no código. Trocar para Postgres é mudar `DATABASE_URL`: o `connect_args` do SQLite só é aplicado quando a URL começa com `sqlite`.

## Resultado

A suíte inteira roda sobre SQLModel, num SQLite em memória recriado a cada teste. O ganho concreto: o dado sobrevive ao reinício do processo (a lacuna AM-12 do threat model).

## Evidência

[evidencias/exercicio11_sqlmodel.txt](evidencias/exercicio11_sqlmodel.txt): a URL vindo do `.env`, a ausência de SQL concatenada e de credencial no código, os seis routers com `Depends(get_session)`, o dado sobrevivendo ao reinício do servidor e o conteúdo real do arquivo SQLite.
