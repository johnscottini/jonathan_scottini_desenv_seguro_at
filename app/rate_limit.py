import time
from typing import Callable, Union

from fastapi import HTTPException, Request, status


def limitar_requisicoes(limite: Union[int, Callable[[], int]], janela_segundos: int) -> Callable:
    """Exercício 10: limita requisições por IP em janela deslizante.

    Cada chamada da factory cria o próprio histórico, então rotas diferentes têm
    contadores independentes. O estado vive na memória do processo: serve ao escopo do
    AT, mas em produção precisaria de armazenamento compartilhado (ex. Redis) para valer
    entre réplicas.
    """

    historico: dict[str, list[float]] = {}

    def verificar_limite(request: Request) -> None:
        ip = request.client.host if request.client else "desconhecido"
        agora = time.monotonic()
        recentes = [t for t in historico.get(ip, []) if agora - t < janela_segundos]

        limite_atual = limite() if callable(limite) else limite
        if len(recentes) >= limite_atual:
            historico[ip] = recentes
            espera = int(janela_segundos - (agora - recentes[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Tente novamente em instantes.",
                headers={"Retry-After": str(espera)},
            )

        recentes.append(agora)
        historico[ip] = recentes

    def limpar() -> None:
        historico.clear()

    verificar_limite.limpar = limpar
    return verificar_limite
