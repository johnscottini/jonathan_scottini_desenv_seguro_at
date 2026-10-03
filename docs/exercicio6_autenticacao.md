# AT — Exercício 6: Autenticação e autorização

Resolve as três ameaças críticas do [threat model](exercicio4_threat_model_stride.md) (AM-01, AM-02, AM-04, AM-06).

## Autenticação

- **Hashing bcrypt**: [hashing.py](../app/hashing.py) usa `passlib.CryptContext(schemes=["bcrypt"])`. Nenhuma senha é gravada ou comparada em texto claro. O `bcrypt` está fixado em `4.0.1` (a versão 5 quebra o `passlib` 1.7.4).
- **OAuth2PasswordBearer**: [security.py](../app/security.py) define o esquema com escopos. O login (`POST /token`) usa `OAuth2PasswordRequestForm` e devolve o JWT.
- **Login sem oráculo de usuário**: usuário inexistente e senha errada retornam o mesmo `401`. Quando o usuário não existe, ainda se verifica contra um hash fictício, para não vazar a existência da conta pelo tempo de resposta.

## JWT com expiração

`criar_access_token` ([security.py](../app/security.py)) monta o token com:

| Claim | Valor |
|---|---|
| `sub` | id opaco (uuid), nunca o username |
| `papel`, `escopos` | do papel (RBAC) |
| `exp` | agora + 30 min |
| `iss`, `aud` | `agendamento-api`, validados na decodificação |

`decodificar_token` valida assinatura, algoritmo explícito (`algorithms=[HS256]`, recusa `alg: none`), expiração, emissor e audiência. Os testes `test_token_*` em [test_autorizacao.py](../tests/test_autorizacao.py) cobrem token expirado, `alg: none`, outra chave e audiência errada. O segredo vem do `.env`, nunca do código.

## MFA simulado para administradores

`POST /token` de uma conta `administrador` não devolve o token direto: gera um desafio ([mfa.py](../app/mfa.py)) e responde com um `mfa_token` e um `codigo_simulado` de 6 dígitos. O token só sai após confirmar o código em `POST /token/mfa`. O código é de uso único, expira em 5 min e invalida o desafio após 3 erros. Em produção o enforcement real de MFA (TOTP) ficaria a cargo de um Identity Provider; aqui o código volta na resposta só para o teste manual.

## Verificação de ownership

O helper `autorizar_dono` ([security.py](../app/security.py)) é usado por `carregar_consulta` em [consultas.py](../app/routes/consultas.py):

- Leitura: paciente ou profissional da consulta. Escrita: só o profissional que a criou. `administrador` passa nos dois casos.
- Quem não é dono recebe `404`, idêntico a um id inexistente, para não confirmar que o objeto existe.
- A listagem é filtrada pelo dono (`consultas_visiveis`): o paciente vê só as suas, o profissional só as suas, o admin vê tudo.

O `paciente` da consulta passou a ser um usuário real e o profissional vem do token (resolve o spoofing AM-01); o `DELETE` virou cancelamento lógico (AM-11).

## Modelo de autorização: RBAC + ownership

| Papel | Escopos |
|---|---|
| `paciente` | `consultas:read` |
| `profissional` | `consultas:read`, `consultas:write` |
| `administrador` | `consultas:read`, `consultas:write`, `admin` (exige MFA) |

A escolha é **RBAC como base + autorização por recurso**, não ABAC. RBAC resolve as decisões de papel (quem escreve, quem é admin), mas é insuficiente para dado de saúde: dois pacientes têm o mesmo papel e nenhum pode ler a consulta do outro, RBAC não enxerga *qual* objeto está sendo acessado, e é aí que entra o ownership.

## Sessão das páginas HTML

`POST /pagina/login` valida a senha e grava o JWT num cookie de sessão com `HttpOnly` (inacessível a `document.cookie`), `Secure` (só HTTPS) e `SameSite=Strict` (mitiga CSRF). Um token novo é emitido a cada login (evita session fixation). Sem cookie válido, a página redireciona para o login.

## Teste de autorização pedido

[test_autorizacao.py](../tests/test_autorizacao.py): o teste pedido é `test_nao_administrador_e_impedido_de_acessar_rota_admin`, parametrizado para paciente e profissional — ambos recebem `403` em `GET /admin/usuarios`. É o primeiro da suíte de autorização.

## Evidência

[evidencias/exercicio6_autenticacao.txt](evidencias/exercicio6_autenticacao.txt): cadastro sempre paciente, login de admin exigindo MFA (código de uso único), payloads dos JWT (sub opaco, exp de 30 min), resposta idêntica para senha errada e usuário inexistente, a rota admin recusando paciente/profissional e aceitando o admin, e o ownership das consultas.
