# AT — Exercício 7: Escopos e integração com o laboratório (M2M)

## Escolha do fluxo: Client Credentials

O laboratório parceiro consome a API de forma automatizada: ler pedidos de exame e enviar resultados. Não há humano digitando senha nem navegador para consentimento, o que descarta o Authorization Code (feito para o caso oposto) e o ROPC (legado, exigiria o parceiro guardar uma senha fictícia).

O fluxo escolhido é o **Client Credentials Grant**, em `POST /token/m2m` ([auth.py](../app/routes/auth.py)):

- O parceiro se autentica com `client_id` + `client_secret` (o próprio cliente é o dono do recurso). O secret é guardado em hash bcrypt ([clientes_m2m_db.py](../app/database/clientes_m2m_db.py)) e vem do `.env`.
- `grant_type` é obrigatoriamente `client_credentials`.
- A resposta segue o formato do OAuth 2.0: `access_token`, `token_type`, `expires_in`, `scope`. O token M2M expira em 15 min (mais curto que o de usuário, 30 min).

## Escopos e claims: laboratório vs. profissional

Os escopos ficam gravados no cadastro do cliente (o contrato em forma de dado): o laboratório recebe `["exames:read", "exames:write"]` e nenhum escopo de `consultas:*`. Ao pedir o token, pode solicitar um subconjunto dos escopos contratados, nunca um a mais (`400 invalid_scope`).

| Claim | Profissional (`dra.ana`) | Laboratório |
|---|---|---|
| `sub` | uuid opaco | `laboratorio-parceiro` (client_id) |
| `tipo_cliente` | `"usuario"` | `"m2m"` |
| `papel` | `"profissional"` | **ausente** — cliente M2M não herda papel humano |
| `escopos` | `consultas:read/write` | `exames:read/write` |
| `exp` | +30 min | +15 min |

## O que o laboratório pode e não pode

Rotas em [laboratorio.py](../app/routes/laboratorio.py), cada uma exigindo um escopo `exames:*`:

- `GET /laboratorio/pedidos`: lista as consultas com exames solicitados, num schema minimizado (`PedidoExameResponse`) — só `consulta_id`, `paciente`, `data_hora` e `exames_solicitados`, sem motivo, especialidade ou profissional.
- `POST /laboratorio/pedidos/{id}/resultados`: envia resultado, só de um exame que foi solicitado naquela consulta.

Duas camadas isolam o laboratório: o **escopo** (as rotas de consulta exigem `consultas:*`, que ele não tem) e o **tipo de cliente** (`get_cliente_m2m` exige `tipo_cliente == "m2m"`, então nenhum usuário humano, mesmo admin, acessa as rotas do laboratório). O resultado chega ao profissional dono da consulta via `GET /consultas/{id}/resultados`.

## Evidência

[evidencias/exercicio7_m2m_laboratorio.txt](evidencias/exercicio7_m2m_laboratorio.txt): o handshake Client Credentials, os dois payloads de token lado a lado, os erros `invalid_scope`/`invalid_client`, a leitura de pedidos sem dado clínico, o envio de resultado e a bateria de `403` provando que o token do laboratório não alcança nenhuma rota fora do contrato.
