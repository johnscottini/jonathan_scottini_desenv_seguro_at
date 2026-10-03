# AT — Exercício 13: Capstone — auditoria final e relatório de rastreabilidade

Auditoria de segurança do `agendamento-api` antes do primeiro deploy: scan passivo do OWASP ZAP, auditoria da especificação OpenAPI, testes automatizados e rastreabilidade do [threat model do Exercício 4](exercicio4_threat_model_stride.md) até a correção. Termina com o risco residual e a decisão de deploy.

## 1. Aplicação final

Integra, num único serviço FastAPI: autenticação OAuth2 + JWT + MFA + ownership (Ex. 6), integração M2M (Ex. 7), validação e saída seguras (Ex. 9), hardening de rede (Ex. 10), persistência SQLModel (Ex. 11) e pipeline DevSecOps (Ex. 12).

## 2. OWASP ZAP (scan passivo)

O `zap-baseline.py` (só regras passivas) rodou contra a app no ar, via o container oficial `ghcr.io/zaproxy/zaproxy:stable`.

| Execução | FAIL | WARN | PASS | Alertas |
|---|---|---|---|---|
| Antes | 0 | 2 | 65 | CORP header ausente (Low); conteúdo cacheável (Info) |
| **Depois** | **0** | **1** | **66** | Non-Storable Content (Info — confirma o `no-store`) |

O único finding de risco (Low, `Cross-Origin-Resource-Policy` ausente) foi corrigido adicionando `Cross-Origin-Resource-Policy: same-origin` e `Cache-Control: no-store` ao `SecurityHeadersMiddleware`. O alerta restante é informativo e confirma que o `no-store` está ativo. Evidência em [evidencias/exercicio13_zap_scan.txt](evidencias/exercicio13_zap_scan.txt) e no relatório HTML [exercicio13_zap_relatorio.html](evidencias/exercicio13_zap_relatorio.html).

Entre os PASS estão CSP, Cookie sem SameSite, Cross-Domain Misconfiguration, PII Disclosure, Session ID in URL e Anti-CSRF Tokens.

## 3. Auditoria da especificação OpenAPI

Verificada por [test_openapi_audit.py](../tests/test_openapi_audit.py) e registrada em [evidencias/exercicio13_openapi_audit.txt](evidencias/exercicio13_openapi_audit.txt):

- Toda rota de API sensível declara segurança com o escopo correto; as públicas são só as de entrada.
- Nenhum schema `*Response` expõe campo interno (`paciente_id`, `audit_token`, `hashed_password`, etc.).
- O esquema `OAuth2PasswordBearer` está declarado com os escopos.

**Falha de design encontrada:** as páginas autenticadas por cookie de sessão (`/pagina/consultas`, `/pagina/prontuarios/{id}`) não aparecem com `security` no OpenAPI, porque a sessão por cookie não é declarada como `securityScheme`. A proteção existe em runtime (sem cookie, redirecionam para o login — testado), mas a spec não a anuncia. É lacuna de documentação, registrada como risco residual R3.

## 4. Testes automatizados

126 testes, incluindo unitários com mocking ([test_unit_mock.py](../tests/test_unit_mock.py), cobrindo o endpoint inicial do Ex. 1, login, cadastro, validação de entrada e autorização em isolamento) e a auditoria da spec.

## 5. Rastreabilidade: threat model → OWASP → correção → evidência

| Ameaça / Finding | OWASP | Correção (exercício) | Evidência |
|---|---|---|---|
| AM-04 BOLA | A01 / API1 | `autorizar_dono` central (Ex. 9) | ex8/ex9; `test_bola_*` |
| AM-06 BFLA | A01 / API5 | RBAC + `SecurityScopes` (Ex. 6) | ex6; `test_am06_*` |
| AM-01 Spoofing | A01 | paciente da base, profissional do token (Ex. 6) | `test_am01_*` |
| AM-02/AM-11 Tampering | A01 | ownership no PUT; DELETE lógico (Ex. 6/9) | `test_am02_*`, `test_am11_*` |
| SQLi | A03 | whitelist + query parametrizada (Ex. 9/11) | ex8/ex9; `test_sqli_*` |
| XSS armazenado | A03 | auto-escape, sem `\|safe` (Ex. 9) | navegador antes/depois |
| Mass assignment | A08 / API3 | `extra="forbid"` (Ex. 9) | ex9; `test_mass_assignment_*` |
| AM-13/14 Broken Auth | A07 / API2 | bcrypt, resposta idêntica, rate limit (Ex. 6/10) | ex10; `test_login_*` |
| AM-16 JWT inválido | A07 | `alg` explícito, `aud`/`exp`/assinatura (Ex. 6) | `test_am16_*` |
| AM-09 Config | A05 | headers + CORS allowlist (Ex. 10) | ex10; ZAP |
| AM-10 Exposição de campos | A01 / API3 | `response_model` (Ex. 2) | audit OpenAPI |
| SCA PyJWT 2.13.0 | A06 | upgrade 2.14.0 (Ex. 12) | ex12 antes/depois |
| ZAP CORP ausente | A05 | `Cross-Origin-Resource-Policy` (Ex. 13) | ZAP antes/depois |
| AM-12 Perda em memória | — | persistência SQLModel (Ex. 11) | ex11 |

Todas as ameaças Crítica e Alta do threat model foram fechadas e comprovadas.

## 6. Riscos residuais

| Id | Risco | Por que permanece | Sev. | Aceitável? |
|---|---|---|---|---|
| R1 | MFA simulado (código na resposta, não TOTP real) | O enforcement real ficaria num IdP (Keycloak), fora do escopo deste Assessment | Média | Sim em ambiente interno; integrar antes de expor à internet |
| R2 | Rate limit e MFA em memória de processo | Não compartilham estado entre réplicas | Média | Sim em instância única; migrar para Redis ao escalar |
| R3 | Auth por cookie não declarada no OpenAPI | Protegida em runtime, não anunciada na spec | Baixa | Sim; declarar um `APIKeyCookie` scheme numa iteração |
| R4 | Sem CSP | XSS já neutralizado por output encoding; CSP seria reforço | Baixa | Sim |
| R5 | Sem audit log central (SIEM) | Há `audit_*` por consulta, mas não trilha de leitura exportável | Média | Sim; próxima evolução |
| R6 | TLS terminado fora da app | HSTS é enviado, mas o TLS é do proxy de produção | — | Sim; premissa de infraestrutura |

## 7. Recomendação de deploy

**Liberar para ambiente interno/piloto, condicionado a premissas de infraestrutura, e bloquear a exposição pública à internet até fechar R1.**

- Todas as vulnerabilidades Crítica e Alta estão corrigidas e comprovadas. O ZAP não retorna finding de risco, a auditoria OpenAPI está limpa, SCA/SAST passam e 126 testes cobrem os vetores do threat model.
- Os residuais são de severidade Média ou Baixa e nenhum reabre uma falha crítica. R2/R5/R6 são escala e infraestrutura; R3/R4 são reforços.
- O único que condiciona a exposição pública é o **R1 (MFA simulado)**: para um serviço de saúde aberto à internet, o segundo fator real é requisito. Num piloto interno atrás de VPN, o risco é aceitável.
- Premissas que a infra deve garantir: TLS/HTTPS no proxy (R6), `.env` de produção com segredos fortes, e instância única enquanto R2 não for resolvido.

O risco residual é aceitável para deploy interno controlado, e não para exposição pública direta enquanto o MFA real não estiver integrado. A liberação é condicional.
