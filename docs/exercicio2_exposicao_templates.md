# AT — Exercício 2: Controle de exposição de dados e templates seguros

## `response_model` controlando os campos expostos

Cada consulta é guardada com campos públicos e campos internos ([consultas_db.py](../app/database/consultas_db.py)): `prontuario_paciente` (identificador do paciente no sistema clínico) e `audit_token`, `audit_origem_ip`, `audit_criado_em` (auditoria). O `ConsultaResponse` ([models/consulta.py](../app/models/consulta.py)) é declarado como `response_model` nas rotas: o FastAPI serializa só os campos do schema, mesmo que o dicionário interno tenha mais chaves.

Entrada e saída usam schemas diferentes, e nenhum é o registro interno: `ConsultaCreate` não tem `status` nem campos de auditoria, `ConsultaResponse` não tem os campos internos.

## Risco quando `response_model` não é definido

A comparação foi feita em um app descartável, [evidencias/comparar_response_model.py](evidencias/comparar_response_model.py), que registra a mesma função `criar_consulta` com e sem `response_model`:

```
COM response_model:  {"id":1,"paciente":"Maria Souza",...,"status":"agendada"}
SEM response_model:  {... "prontuario_paciente":279169, "audit_token":"bed94b1a15ff74f3",
                      "audit_origem_ip":"testclient", "audit_criado_em":"..."}
```

Sem o filtro, a resposta vaza o identificador interno do paciente (permite correlacionar consultas da mesma pessoa e cruzar com outras bases) e a trilha de auditoria (o `audit_token` reaproveitado permitiria forjar ou contestar registros). São dados de saúde e de auditoria que não deveriam sair da aplicação.

## Página HTML com herança e auto-escape

As páginas ficam sob `/pagina` ([routes/paginas.py](../app/routes/paginas.py)) e chamam as mesmas funções de dados da API JSON. [base.html](../app/templates/base.html) define cabeçalho/rodapé comuns; `consultas_lista.html` e `consulta_detalhe.html` usam `{% extends "base.html" %}`.

O campo de risco é o `motivo`, texto livre exibido na página de detalhe. O `Jinja2Templates` liga o auto-escape para arquivos `.html`, então `{{ consulta.motivo }}` sai com `<`, `>`, `&`, `"` e `'` convertidos em entidades. Nenhum template usa `|safe`.

O payload `<script>document.title="XSS-EXECUTADO"</script>` foi testado no navegador nas duas versões:

| Versão | HTML gerado | Navegador |
|---|---|---|
| Com `{{ motivo\|safe }}` | `<p><script>...</script></p>` | A aba muda para "XSS-EXECUTADO" |
| Com auto-escape (entregue) | `<p>&lt;script&gt;...&lt;/script&gt;</p>` | Título intacto, sem `<script>` no DOM |

A API JSON devolve o texto como foi salvo: não é XSS porque a resposta é `application/json`, não interpretada como HTML. O escape fica na fronteira em que o dado vira HTML.

## Evidência

[evidencias/exercicio2_exposicao_templates.txt](evidencias/exercicio2_exposicao_templates.txt): a comparação com/sem `response_model`, o cadastro do payload XSS, o HTML escapado das páginas e a verificação no navegador antes e depois.
