# AT — Exercício 10: Hardening de rede e proteção contra abuso

## CORS com allowlist explícita

`CORSMiddleware` em [main.py](../app/main.py) com as origens de [middleware.py](../app/middleware.py):

```python
ALLOWED_ORIGINS = ["http://localhost:5173", "https://agendamento.exemplo.com.br"]
```

Nada de `allow_origins=["*"]`, o wildcard com `allow_credentials=True` deixaria qualquer site ler respostas autenticadas da vítima. O laboratório parceiro (M2M) não entra na allowlist: CORS é verificação de navegador, e ele chama servidor a servidor.

Três cenários na evidência:
1. Origem autorizada → `200` com `access-control-allow-origin`.
2. Origem não autorizada (GET simples) → `200`, sem o header (o navegador nega a leitura; CORS não responde `403`).
3. Preflight de origem não autorizada → `400`, sem o header (bloqueio do servidor).

## Cabeçalhos de segurança

`SecurityHeadersMiddleware` ([middleware.py](../app/middleware.py)) acrescenta a todas as respostas:

| Cabeçalho | Valor | Para quê |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Obriga HTTPS, evita downgrade |
| `X-Frame-Options` | `DENY` | Clickjacking |
| `X-Content-Type-Options` | `nosniff` | Impede adivinhar o content-type |
| `Referrer-Policy` | `no-referrer` | Não vaza a URL para sites externos |

É registrado antes do `CORSMiddleware`, para o CORS ficar na camada mais externa e suas respostas também receberem os cabeçalhos.

## Rate limiting no login

[rate_limit.py](../app/rate_limit.py) traz `limitar_requisicoes(limite, janela_segundos)`, uma factory que devolve uma dependency com histórico próprio por IP, em janela deslizante. O login tem **5 tentativas / 60s por IP**, no `POST /token` e no `POST /pagina/login` (mesma superfície de brute force, mesmo limitador). Ao estourar, `429` com `Retry-After`.

**Por que diferenciado por rota:** o login tem volume legítimo baixíssimo (autentica uma vez, reusa o token) e é o alvo mais valioso (cada tentativa testa uma credencial) — um limite baixo custa quase nada e inviabiliza o brute force. A listagem de consultas é o oposto: muito chamada e de baixo valor para o atacante; 5/min ali quebraria o uso normal. O limite é calibrado pela razão entre tráfego legítimo e dano por rota.

## Evidência

[evidencias/exercicio10_hardening.txt](evidencias/exercicio10_hardening.txt): os cabeçalhos em duas respostas, os três cenários de CORS, o `429` com `Retry-After` no login, o bloqueio por IP independente do resultado, e `GET /consultas` respondendo `200` doze vezes seguidas (contadores independentes).
