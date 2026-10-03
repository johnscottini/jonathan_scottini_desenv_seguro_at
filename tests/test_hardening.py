"""Exercício 10: CORS com allowlist, cabeçalhos de segurança e rate limiting no login."""

import pytest


# Cabeçalhos de segurança em toda resposta


@pytest.mark.parametrize("rota", ["/", "/pagina/login"])
def test_cabecalhos_de_seguranca_presentes(client, rota):
    h = client.get(rota).headers
    assert h["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert h["x-frame-options"] == "DENY"
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert h["cross-origin-resource-policy"] == "same-origin"
    assert h["cache-control"] == "no-store"


# CORS com allowlist explícita


def test_cors_origem_autorizada_recebe_o_header(client):
    resposta = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert resposta.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_origem_nao_autorizada_nao_recebe_o_header(client):
    resposta = client.get("/", headers={"Origin": "https://site-malicioso.com"})
    # Requisição simples é processada (200), mas sem o header o navegador nega a leitura.
    assert "access-control-allow-origin" not in resposta.headers


def test_cors_preflight_de_origem_nao_autorizada_e_bloqueado(client):
    resposta = client.options(
        "/consultas",
        headers={
            "Origin": "https://site-malicioso.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resposta.status_code == 400
    assert "access-control-allow-origin" not in resposta.headers


# Rate limiting diferenciado no login


def test_login_bloqueia_apos_cinco_tentativas(client, limite_login_baixo):
    for _ in range(5):
        assert client.post("/token", data={"username": "maria", "password": "errada"}).status_code == 401
    resposta = client.post("/token", data={"username": "maria", "password": "errada"})
    assert resposta.status_code == 429
    assert "retry-after" in resposta.headers


def test_bloqueio_e_por_ip_independe_do_resultado(client, criar_usuario, limite_login_baixo):
    criar_usuario("maria", "paciente", "Maria Souza")
    for _ in range(5):
        client.post("/token", data={"username": "maria", "password": "errada"})
    # Mesmo com a senha correta, o IP já estourou o limite.
    resposta = client.post("/token", data={"username": "maria", "password": "senha-forte-123"})
    assert resposta.status_code == 429


def test_formulario_html_compartilha_o_mesmo_limite(client, limite_login_baixo):
    for _ in range(5):
        client.post("/token", data={"username": "maria", "password": "errada"})
    # O contador é o mesmo do /token: o /pagina/login já entra bloqueado.
    resposta = client.post(
        "/pagina/login", data={"username": "maria", "password": "errada"}, follow_redirects=False
    )
    assert resposta.status_code == 429


def test_listagem_de_consultas_nao_e_afetada_pelo_limite_do_login(client, cenario):
    # A listagem tem volume legítimo alto; não pode herdar o limite baixo do login.
    for _ in range(15):
        assert client.get("/consultas", headers=cenario["maria"]).status_code == 200
