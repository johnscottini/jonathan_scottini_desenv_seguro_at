# AT — Exercício 8: Identificação de vulnerabilidades (OWASP Top 10)

Análise do código por leitura, sem ferramenta automatizada. As falhas foram introduzidas na funcionalidade de **prontuário clínico** ([models/prontuario.py](../app/models/prontuario.py), [database/prontuarios_db.py](../app/database/prontuarios_db.py), [routes/prontuarios.py](../app/routes/prontuarios.py)) e sobrevivem *depois* da autenticação do [Exercício 6](exercicio6_autenticacao.md), são falhas de autorização e tratamento de dado que dependem do contexto de negócio.

Cenário das evidências: prontuário 1 = Maria (Dra. Ana, "Angina estável"); prontuário 2 = João (Dr. Paulo, "Transtorno depressivo moderado").

| # | Vulnerabilidade | Categoria OWASP | CWE | Endpoint |
|---|---|---|---|---|
| V1 | **BOLA** (prontuário alheio por id) | A01 (API1:2023 BOLA) | CWE-639 | `GET /prontuarios/{id}` |
| V2 | **SQL Injection** na busca | A03 Injection | CWE-89 | `GET /prontuarios/busca` |
| V3 | **XSS armazenado** nas anotações | A03 Injection | CWE-79 | `GET /pagina/prontuarios/{id}` |
| V4 | **Mass assignment** na edição | A08 (API3:2023 BOPLA) | CWE-915 | `PUT /prontuarios/{id}` |

As três categorias distintas pedidas (A01, A03, A08) estão cobertas, e a instância de BOLA é a V1, o incidente do enunciado: um paciente lê o prontuário de outro trocando o id na URL.

## V1 — BOLA em `GET /prontuarios/{id}`

A rota resolve o objeto só pelo id:

```python
prontuario = prontuarios_db.obter_prontuario(prontuario_id)
if prontuario is None:
    raise HTTPException(status_code=404, ...)
return prontuario
```

O `usuario` é autenticado, mas nunca comparado com o dono. Na evidência, Maria chama `GET /prontuarios/2` e recebe `200` com o diagnóstico do João. A consulta correspondente (`GET /consultas/2`) já responde `404` porque foi protegida no Exercício 6, o prontuário nasceu sem essa checagem.

## V2 — SQL Injection em `GET /prontuarios/busca`

A query é montada por concatenação:

```python
sql = (f"SELECT * FROM prontuarios WHERE {coluna_dono} = '{usuario['id']}' "
       f"AND diagnostico LIKE '%{termo}%'")
```

O `max_length=100` limita o tamanho, mas não impede a injeção. O termo `%' OR 1=1 --` fecha a aspa e comenta o resto: o `AND` do filtro de dono é anulado e Maria recebe também o prontuário do João. O termo controla a lógica da query, não só o valor filtrado.

## V3 — XSS armazenado em `GET /pagina/prontuarios/{id}`

O template usa `|safe`:

```jinja
<div class="anotacoes">{{ prontuario.anotacoes|safe }}</div>
```

As anotações são texto livre do profissional, exibidas ao paciente e a outros profissionais. Na evidência, uma anotação com `<script>document.title="XSS-EXECUTADO"</script>` executa ao abrir a página (o título da aba muda, verificado no navegador). É XSS armazenado: reexecuta a cada carregamento.

## V4 — Mass assignment em `PUT /prontuarios/{id}`

O schema de edição aceita campos extras:

```python
class ProntuarioUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
```

Na evidência, a Dra. Ana envia `criado_em` e `profissional` (campos internos, fora do schema): o registro é retrodatado para 2024 e a autoria atribuída a outro profissional. Adulterar data e autoria de um registro clínico compromete seu valor probatório.

## Evidência

[evidencias/exercicio8_vulnerabilidades_antes.txt](evidencias/exercicio8_vulnerabilidades_antes.txt): a exploração de cada falha no servidor (código antes da correção), com a verificação do XSS no navegador. É o "antes" comparado no [Exercício 9](exercicio9_correcoes.md).
