# AT — Exercício 9: Correção das vulnerabilidades de entrada e saída

Cada falha do [Exercício 8](exercicio8_vulnerabilidades.md) foi corrigida, e o mesmo ataque que a identificou deixou de funcionar. As evidências ficam lado a lado: [antes](evidencias/exercicio8_vulnerabilidades_antes.txt) e [depois](evidencias/exercicio9_correcoes_depois.txt).

| # | Falha | Correção | Ataque: antes → depois |
|---|---|---|---|
| V1 | BOLA | Ownership centralizado (`autorizar_dono`) | `GET /prontuarios/2` por Maria: `200` → `404` |
| V2 | SQL Injection | Query parametrizada + whitelist regex | `%' OR 1=1 --`: vazava tudo → `422` |
| V3 | XSS armazenado | Remoção do `\|safe` (auto-escape) | `<script>` executava → sai como texto |
| V4 | Mass assignment | `extra="forbid"` | retrodatava o registro → `422` |

## V1 — BOLA: ownership centralizado

A checagem foi centralizada num helper único em [security.py](../app/security.py), reusado por consultas e prontuários:

```python
def autorizar_dono(recurso, usuario, campos_dono):
    if recurso is None:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    if eh_admin(usuario):
        return recurso
    if usuario["id"] not in {getattr(recurso, campo) for campo in campos_dono}:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    return recurso
```

O enunciado cita "middleware JWT com dependency injection"; a implementação é uma dependency/helper, não um `app.add_middleware`, porque um middleware ASGI roda antes da resolução de rota e não teria acesso ao recurso tipado, e o campo do dono varia por rota (consulta e prontuário diferem). A rota passa a ser:

```python
prontuario = prontuarios_db.obter_prontuario(session, prontuario_id)
return autorizar_dono(prontuario, usuario, ["paciente_id", "profissional_id"])
```

Decisões: `404` (não `403`) para "não é seu", igual a "não existe", para não confirmar a existência do id; `administrador` tem passe livre. Resultado: Maria em `GET /prontuarios/2` passou de `200` para `404`, idêntico a um id inexistente.

## V2 — SQL Injection: parametrização + whitelist

Duas camadas:

1. **Whitelist por regex** na assinatura da rota ([prontuarios.py](../app/routes/prontuarios.py)): `pattern=r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9 \-]+$"`. Aspas, `%`, parênteses e `--` recebem `422` antes da rota executar.
2. **Query parametrizada** ([prontuarios_db.py](../app/database/prontuarios_db.py)): o termo e o id do dono passam como valores vinculados, nunca concatenados. A coluna do dono é escolhida por allowlist (atributo fixo do modelo).

A parametrização sozinha já torna a injeção impossível; a whitelist é defesa em profundidade. Resultado: `%' OR 1=1 --` e `O'Brien` passam a receber `422`, e `termo=Angina` continua devolvendo o prontuário certo com o filtro de dono valendo.

## V3 — XSS armazenado: output encoding

Removido o `|safe`, voltando ao auto-escape ([prontuario_detalhe.html](../app/templates/prontuario_detalhe.html)):

```jinja
<div class="anotacoes" style="white-space:pre-line">{{ prontuario.anotacoes }}</div>
```

O escape acontece na saída: o texto continua salvo como foi enviado, e a renderização o neutraliza. O `white-space:pre-line` preserva as quebras de linha (o motivo pelo qual o `|safe` tinha sido posto). Resultado: o payload sai como `&lt;script&gt;...`, o título da aba não muda e não há `<script>` no DOM.

## V4 — Mass assignment: `extra="forbid"`

`ProntuarioUpdate` passou de `extra="allow"` para `extra="forbid"` ([prontuario.py](../app/models/prontuario.py)). Resultado: a tentativa de enviar `criado_em` e `profissional` recebe `422 extra_forbidden`, e a data e a autoria ficam intactas. A atualização legítima (só `prescricao`) continua com `200`.

## Endpoint não citado no Exercício 8 com o mesmo padrão

O **`PUT /prontuarios/{id}`** busca o objeto por id e decide a autorização na rota — mesmo padrão do BOLA da V1, que era sobre o `GET`. No Exercício 8 ele tinha uma checagem ad hoc; na correção passou a usar o mesmo helper `autorizar_dono` (com `["profissional_id"]`, porque paciente não escreve prontuário). Um `PUT` de prontuário alheio pelo Dr. Paulo recebe `404`.

## Testes e evidência

[test_vulnerabilidades.py](../tests/test_vulnerabilidades.py) reexecuta cada ataque e afirma a nova resposta, mais os testes de uso legítimo. Evidência em [evidencias/exercicio9_correcoes_depois.txt](evidencias/exercicio9_correcoes_depois.txt), com a verificação do XSS no navegador (título intacto, zero scripts).
