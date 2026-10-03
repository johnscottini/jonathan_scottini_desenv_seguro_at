# Roteiro de apresentação — 5 min no Postman + 1 min no terminal

Demonstração do `agendamento-api` pelo Postman. A collection e o environment estão em
[docs/apresentacao/](apresentacao/).

**9 requests no Postman** (5 pastas) e um **bloco final de 1 minuto no terminal**, para os exercícios 12 e 13, que não se demonstram por request. A criação dos usuários é encanamento e roda antes,
na pasta `Setup`, fora do cronômetro.

A linha condutora é uma só: **o escopo diz o que você pode fazer; a checagem de dono diz sobre o
que você pode fazer.** As duas pastas de "NEGA" existem para provar que são camadas independentes.

---

## Pré-voo

**1. Importar no Postman** (*Import*, arrastar os dois arquivos):

- `docs/apresentacao/agendamento-api.postman_collection.json`
- `docs/apresentacao/agendamento-api.postman_environment.example.json`

**2. Preencher os segredos.** Aba *Environments* → `agendamento-api (local)`:

| Variável | Vem de |
|---|---|
| `adminPassword` | `ADMIN_PASSWORD` do `.env` |
| `labClientSecret` | `LAB_CLIENT_SECRET` do `.env` |

Depois **selecionar o environment** no canto superior direito. Se ficar em "No Environment", todo
request falha com `{{baseUrl}}` não resolvido.

**3. Subir a API com o limite de login afrouxado.** O setup faz 4 logins em `POST /token` e o
limite real é 5 por minuto por IP (`app/routes/auth.py:19`). Ensaiar e apresentar no mesmo minuto
dá `429` no palco.

```powershell
cd C:\projetos\estudo\jonathan_scottini_dr2_at\desenv-seguro-app-web-at
Remove-Item agendamento.db -ErrorAction SilentlyContinue   # banco limpo: ids baixos na tela
$env:LOGIN_RATE_LIMIT = "100"
.\venv\Scripts\python.exe -m uvicorn app.main:app
```

A variável de ambiente tem precedência sobre o `.env` e **vive só enquanto a janela estiver
aberta** — fechou o terminal, o limite volta sozinho para 5. Por isso ela é preferível a editar o
`.env`: não há como esquecer ligada e entregar o AT com a proteção afrouxada.

**4. Rodar a pasta `Setup` inteira** (botão `...` na pasta → *Run folder*). Ela loga o admin, cria
dra.ana, maria e joao, e guarda os quatro tokens. Leva ~2 segundos e **não entra nos 5 minutos**.

---

## Os 5 blocos

### 1 — Login do admin exige segundo fator · `0:00` → `1:00`

> "Esta é uma API de agendamento médico. Ela guarda diagnóstico, que a LGPD classifica como dado
> pessoal sensível. Vou começar entrando como administrador."

**Enviar `1.1 POST /token`** — usuário e senha do admin.

**Apontar:** a resposta tem `mfa_requerido: true` e um `mfa_token`, **mas nenhum `access_token`**.
A senha correta sozinha não abre a conta administrativa.

> "O `codigo_simulado` só aparece porque o segundo fator é simulado no trabalho. Em produção ele
> chegaria por aplicativo autenticador e nunca trafegaria na resposta."

**Enviar `1.2 POST /token/mfa`** — o token e o código já foram capturados em variável pelo request
anterior; não copie nada.

**Apontar:** agora veio o `access_token`. O escopo `admin` só existe em token emitido depois do MFA.

---

### 2 — Agendar e ler · `1:00` → `2:00`

**Enviar `2.1 POST /consultas`** (token da dra.ana).

**Apontar duas coisas na resposta:**

1. **Não enviei `profissional` no corpo.** Ele vem do token de quem está autenticado. Um
   profissional não consegue agendar em nome de outro, porque esse campo não é entrada.
2. **A tabela guarda muito mais do que isso.** No banco existem `paciente_id`, `profissional_id`,
   `prontuario_paciente`, `audit_token` e `audit_origem_ip`. A resposta tem exatamente 8 campos:

   ```
   id, paciente, profissional, especialidade, data_hora, motivo, status, exames_solicitados
   ```

> "Nenhum campo interno vaza, e não é por filtro manual: o `ConsultaResponse` simplesmente não
> declara esses campos, então o FastAPI não tem como serializá-los. Esquecer de filtrar deixou de
> ser possível."

**Enviar `2.2 GET /consultas/{id}`** com o token da **maria**. Responde `200`.

> "Guardem esta tela. Daqui a pouco eu vou chamar exatamente esta URL, com exatamente este id, e a
> única coisa diferente vai ser o token."

---

### 3 — NEGA: outro paciente, mesma URL · `2:00` → `3:00`

**Enviar `3.1 GET /consultas/{id}`** com o token do **joao**. Responde **`404`**.

> "Mesma URL do bloco anterior, mesmo id, token diferente. E reparem: o joao *tem* o escopo
> `consultas:read`. O token dele é válido e o escopo é suficiente. Quem barrou foi a checagem de
> dono."

**Enviar `3.2 GET /consultas/999999`** — um id que não existe. Responde **o mesmo `404`, com o
mesmo corpo**.

> "É 404 e não 403 de propósito. Responder 'proibido' já confirmaria que existe uma consulta com
> esse id. Como consulta alheia e consulta inexistente devolvem respostas idênticas, não dá para
> varrer os ids e descobrir quem tem consulta marcada — seria vazamento de dado de saúde sem ler
> nenhum prontuário."

O teste do `3.2` compara o corpo com o do `3.1`. **O check verde na aba Test Results é a prova** —
mostre-o, não só o status.

**Este é o ponto alto da apresentação.** Não corra.

---

### 4 — O laboratório parceiro · `3:00` → `4:15`

**Enviar `4.1 POST /token/m2m`**.

> "Integração máquina a máquina, OAuth 2.0 Client Credentials. Não há usuário, não há senha de
> pessoa, não há MFA — é um sistema se autenticando como sistema."

**Apontar:** o campo `scope` da resposta — `exames:read exames:write`. Nenhum escopo de consultas.

**Enviar `4.2 GET /laboratorio/pedidos`**.

**Apontar os campos que a resposta tem:** `consulta_id`, `paciente`, `data_hora`,
`exames_solicitados`. E principalmente os que **não** tem:

> "Não vai o motivo da consulta — 'dor no peito'. Não vai a especialidade, não vai quem é a
> profissional, não vai o diagnóstico. O laboratório não precisa saber por que o exame foi pedido
> para executá-lo. Isso é minimização de dados, LGPD artigo 6º, inciso III."

---

### 5 — NEGA: o parceiro fora do contrato · `4:15` → `5:00`

**Enviar `5.1 GET /consultas`** com o token do **laboratório**. Responde **`403`**.

**Apontar o contraste com o bloco 3:**

| | Status | Por quê |
|---|---|---|
| Bloco 3 | `404` | O escopo bastava, mas o recurso é de outra pessoa — o status precisa esconder até a existência do dado |
| Bloco 5 | `403` | O escopo não está no token, e não há recurso específico a esconder |

**Fechamento:**

> "Esse token é legítimo: foi assinado por esta API, está dentro da validade, não foi forjado.
> Ainda assim não passa. Se a credencial do laboratório vazar amanhã, o atacante consegue no
> máximo a lista de exames a coletar. Nunca o prontuário, nunca o diagnóstico, nunca a agenda
> clínica. O tamanho do incidente é limitado pelo contrato, não pela confiança no parceiro."

---

### 6 — Pipeline e auditoria · `5:00` → `6:00` · **no terminal, não no Postman**

Cobre os exercícios 12 e 13, que não são comportamento de runtime: não existe request de Postman
que os demonstre. Deixe uma segunda janela de terminal já aberta na raiz do projeto.

**Rodar a suíte:**

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Sai `126 passed` em ~6 segundos.

> "126 testes, e eles não são genéricos: vêm do threat model do exercício 4. O
> `test_threat_model.py` cobre os vetores AM01 a AM06 um a um — agendar em nome de outro, alterar
> consulta alheia, enumerar id, paciente alcançando rota de admin. O `test_unit_mock.py` testa o
> `autorizar_dono` isolado, com mock, incluindo o caso de o recurso não existir."

**Mostrar o pipeline** — abrir `.github/workflows/security.yml` no editor:

> "Quatro jobs a cada push: `pip-audit` para dependências, `bandit` para análise estática, a suíte
> pytest, e o OWASP ZAP em scan passivo contra a app no ar. Cada um tem critério de bloqueio
> próprio: SCA trava em qualquer vulnerabilidade conhecida, SAST só em HIGH, teste em qualquer
> falha, ZAP em risco High."

> "Não bloquear em tudo é proposital. Um gate que trava em qualquer LOW é ignorado em uma semana."

**O caso real** — este é o melhor argumento do bloco:

> "O pipeline pegou uma vulnerabilidade de verdade neste projeto: o PyJWT 2.13.0 tinha a
> CVE-2026-102274. O `pip-audit` bloqueou, subi para a 2.14.0, o gate passou. Está em
> `docs/evidencias/exercicio12_pipeline.txt`, com o antes e o depois."

**ZAP e risco residual** — se sobrar fôlego, abrir
[evidencias/exercicio13_zap_relatorio.html](evidencias/exercicio13_zap_relatorio.html):

> "O ZAP saiu de 2 WARN para 1, e o que sobrou é informativo — confirma o `no-store`. O único
> finding de risco era o `Cross-Origin-Resource-Policy` ausente, corrigido no middleware."

**Fechar pelo risco residual, não pelo verde:**

> "A auditoria não terminou dizendo que está tudo perfeito. Ficaram seis riscos residuais
> documentados. Os dois que importam: o MFA é simulado, o enforcement real ficaria num IdP; e o
> rate limit vive em memória do processo, então não vale entre réplicas. Por isso a liberação é
> **condicional**: aprovada para ambiente interno controlado, bloqueada para exposição pública
> direta enquanto o MFA real não estiver integrado."

---

## Depois da apresentação

Feche a janela do PowerShell onde o uvicorn está rodando. O `LOGIN_RATE_LIMIT=100` sai junto e o
padrão de 5 tentativas/minuto (`app/config.py:27`) volta a valer sozinho.

Se tiver optado por colocar `LOGIN_RATE_LIMIT` no `.env` em vez da variável de ambiente, **apague
a linha agora** — senão o AT é entregue com o rate limiting afrouxado.

---

## Plano B

| Problema no palco | O que fazer |
|---|---|
| `401` em um request no meio | O token expirou (30 min). Rodar a pasta `Setup` de novo. |
| `429` em `POST /token` | O `LOGIN_RATE_LIMIT` não pegou. Ele é lido só na subida do processo — reiniciar o uvicorn com a variável setada. |
| `{{baseUrl}}` aparece literal | O environment não está selecionado no canto superior direito. |
| `422` no bloco 2 | O `dataFutura` não foi gerado. Enviar o `2.1` de novo (o pre-request script recalcula a data). |
| `4.2` devolve `[]` | A consulta foi criada sem `exames_solicitados`. Reenviar o `2.1` com o corpo original. |
| Atraso acumulado | Cortar o `3.2`. Perde-se a prova do 404 idêntico, mas o argumento de ownership fica de pé. |
| `401` ao rodar **uma pasta sozinha** no Runner | Esperado, não é defeito: os tokens vêm do `Setup` e o `consultaId` vem do `2.1`. Pastas isoladas só funcionam depois que a sequência rodou. |

---

## Pasta `Extras` — não entra no roteiro

Três requests guardados para arguição, se a banca puxar:

| Request | Mostra |
|---|---|
| `E1 POST /consultas/{id}/prontuario` | Dado sensível; com `"criado_em"` no corpo vira `422` (mass assignment barrado) |
| `E2 GET /admin/usuarios` como maria | BFLA — paciente não alcança rota administrativa |
| `E3 GET /prontuarios/busca?termo=' OR 1=1 --` | `422`, injeção barrada pela whitelist antes do banco |

O resto está documentado: CORS e cabeçalhos em [exercicio10_hardening.md](exercicio10_hardening.md),
SQLi em [exercicio9_correcoes.md](exercicio9_correcoes.md), pipeline DevSecOps em
[exercicio12_devsecops.md](exercicio12_devsecops.md). O `demo.sh` roda os 10 cenários de segurança
completos no terminal.

---

## Validar a collection sem abrir o Postman

Com Node 16+ (`nvm use 22`):

```powershell
npm install -g newman
newman run docs\apresentacao\agendamento-api.postman_collection.json `
  -e meu-environment-preenchido.json
```

Roda os 20 requests e todas as asserções de uma vez. Útil para conferir que está tudo verde antes
de apresentar, sem clicar em nada.
