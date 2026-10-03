from starlette.middleware.base import BaseHTTPMiddleware

# Exercício 10: allowlist explícita de origens, nunca "*". Foi exatamente o CORS com
# wildcard que reprovou outro serviço de saúde na checklist de pré-produção. O laboratório
# parceiro (M2M) não entra aqui: CORS é verificação de navegador, e ele chama servidor a
# servidor.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://agendamento.exemplo.com.br",
]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resposta = await call_next(request)
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        # Dado de saúde não deve ser indexado nem pré-carregado por intermediários.
        resposta.headers["Referrer-Policy"] = "no-referrer"
        # Exercício 13 (findings do ZAP): impede que outra origem incorpore o recurso...
        resposta.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # ...e que proxies/navegadores guardem dado sensível em cache.
        resposta.headers["Cache-Control"] = "no-store"
        return resposta
