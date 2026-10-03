# AT — Exercício 12: Pipeline DevSecOps e auditoria automatizada

Pipeline em [.github/workflows/security.yml](../.github/workflows/security.yml).

## 1. Fase do SDLC de cada ferramenta

A ideia é shift-left: falhar o mais cedo e barato possível. As ferramentas vão da mais barata (nem sobe a app) para a mais cara (precisa da app no ar).

| Ferramenta | Tipo | Fase no CI/CD | Por quê | Gate |
|---|---|---|---|---|
| **pip-audit** | SCA (dependências) | Commit/build, primeiro | Não executa a app; compara `requirements.txt` com CVEs. Achado mais comum e barato. Rodar primeiro evita gastar CI num código com dependência furada | Bloqueia em qualquer CVE conhecida com fix (`--strict`) |
| **bandit** | SAST (código) | Commit/build, paralelo | Analisa o código sem executá-lo. Feedback imediato na abertura do PR | Bloqueia em severidade HIGH |
| **pytest** | Testes | Build/test | Os testes de autorização precisam da app instanciada (TestClient), não de deploy | Bloqueia em qualquer teste falhando |
| **OWASP ZAP** | DAST | Staging, app no ar | Exercita HTTP real (headers, cookies, métodos). Roda após os gates baratos passarem (`needs:`) | Bloqueia em risco High do ZAP ([.zap/rules.tsv](../.zap/rules.tsv)) |
| **IAST** | Interativa | Test | Agente dentro do processo correlacionando entrada e execução. **Não implementado** (ferramenta licenciada); ponto de inserção documentado seria o job de testes | — |

SCA e SAST são gates de entrada; os testes validam a autorização que a análise estática não enxerga; o DAST é a última rede na app real. Nenhuma camada substitui a outra.

## 2. Priorização com CVSS e impacto de negócio

| Vuln (exercício) | Vetor CVSS 3.1 | Score | Sev. | Impacto de negócio |
|---|---|---|---|---|
| **SQL Injection** na busca (Ex. 8) | `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:L/A:L` | 7.1 | Alta | Anula o filtro de dono; pode ler/alterar toda a base de prontuários |
| **BOLA** em prontuário (Ex. 8) | `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N` | 6.5 | Média | Vazamento de dado de saúde de terceiro por troca de id |
| **Mass assignment** (Ex. 8) | `AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N` | 6.5 | Média | Retrodatar/reatribuir autoria de registro clínico |
| **Broken Auth** sem rate limit (Ex. 8) | `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:L` | 6.5 | Média | Brute force de credenciais |
| **XSS armazenado** (Ex. 8) | `AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N` | 5.4 | Média | Script na sessão de outro profissional |
| **Security Misconfig** (Ex. 8/10) | `AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:L/A:N` | 3.7 | Baixa | Clickjacking, downgrade HTTP, CORS permissivo |
| **Dependência**: PyJWT 2.13.0 (Ex. 12) | CVE-2026-102274 (fix 2.14.0) | — | — | Falha na lib que valida todos os tokens |

Dado de saúde eleva o impacto de confidencialidade. Todas já estão corrigidas (Ex. 9, 10, 11 e o upgrade do PyJWT).

## 3. Security gate: critério e justificativa

| Camada | Bloqueia quando | Justificativa |
|---|---|---|
| SCA | qualquer CVE com fix | Dependência vulnerável com correção publicada é risco inaceitável e barato de resolver |
| SAST | severidade HIGH | HIGH em código (SQL concatenada, exec, segredo hardcoded) é quase sempre real; MEDIUM/LOW reportam |
| Testes | qualquer falha | Um teste de autorização vermelho é regressão de controle de acesso — zero tolerância |
| DAST | risco High do ZAP | Confirmação dinâmica; Medium/Low viram WARN no `rules.tsv` |

Não bloquear em tudo é proposital: um gate que trava em qualquer LOW seria ignorado em uma semana. Ele bloqueia no que tem alta probabilidade de ser real e alto impacto — e, no histórico do Assessment, o maior dano veio de autorização (testes) e injeção/dependência (SAST/SCA).

## 4. Testes rastreáveis ao threat model

[test_threat_model.py](../tests/test_threat_model.py) expande a suíte de autorização do Exercício 6, referenciando as ameaças do Exercício 4 pelo id:

| Ameaça | STRIDE | Teste |
|---|---|---|
| AM-01 | Spoofing | Profissional vem do token; paciente inexistente e campo `profissional` no corpo rejeitados |
| AM-02 / AM-11 | Tampering | Outro profissional/paciente não altera; `DELETE` é cancelamento lógico |
| AM-04 | Information Disclosure / BOLA | Enumeração dá `404`; listagem não traz consulta alheia; campos internos não saem |
| AM-06 | Elevation of Privilege / BFLA | Paciente, profissional e laboratório não alcançam rota admin |
| AM-16 | Elevation of Privilege | JWT com outra chave é recusado |
| AM-05 | Denial of Service | O login tem rate limit |

São 126 testes no total.

## Evidência

[evidencias/exercicio12_pipeline.txt](evidencias/exercicio12_pipeline.txt): o pip-audit pegando o PyJWT 2.13.0 e limpo após o upgrade, o bandit sem finding HIGH em 980 linhas, os testes passando e a contagem por arquivo. As execuções locais usam os mesmos comandos do workflow.
