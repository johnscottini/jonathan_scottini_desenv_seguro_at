"""Exercício 7: o laboratório parceiro só executa o que o contrato autoriza."""

import jwt
import pytest

from app.config import settings

LAB = {"grant_type": "client_credentials", "client_id": "laboratorio-parceiro", "client_secret": "segredo-lab-teste"}


def _token_lab(client, **extra) -> dict:
    resposta = client.post("/token/m2m", data={**LAB, **extra})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


@pytest.fixture
def lab(client):
    return _token_lab(client)


@pytest.fixture
def consulta_com_exames(client, cenario, consulta_payload):
    consulta_payload["exames_solicitados"] = ["Hemograma", "Troponina"]
    return client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).json()


# Fluxo client credentials


def test_token_m2m_carrega_escopos_do_contrato_e_nenhum_papel(client):
    resposta = client.post("/token/m2m", data=LAB).json()
    assert resposta["token_type"] == "bearer"
    assert resposta["expires_in"] == settings.m2m_token_expire_minutes * 60
    payload = jwt.decode(resposta["access_token"], options={"verify_signature": False})
    assert payload["sub"] == "laboratorio-parceiro"
    assert payload["tipo_cliente"] == "m2m"
    assert payload["escopos"] == ["exames:read", "exames:write"]
    assert "papel" not in payload
    assert payload["exp"] - payload["iat"] == settings.m2m_token_expire_minutes * 60


def test_secret_errado_retorna_invalid_client(client):
    resposta = client.post("/token/m2m", data={**LAB, "client_secret": "errado"})
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "invalid_client"


def test_grant_type_diferente_e_recusado(client):
    assert client.post("/token/m2m", data={**LAB, "grant_type": "password"}).status_code == 422


def test_laboratorio_nao_consegue_pedir_escopo_fora_do_contrato(client):
    resposta = client.post("/token/m2m", data={**LAB, "scope": "exames:read consultas:read"})
    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "invalid_scope"


def test_laboratorio_pode_pedir_subconjunto_dos_escopos(client, consulta_com_exames):
    so_leitura = _token_lab(client, scope="exames:read")
    assert client.get("/laboratorio/pedidos", headers=so_leitura).status_code == 200
    resultado = {"exame": "Hemograma", "resultado": "Normal"}
    url = f"/laboratorio/pedidos/{consulta_com_exames['id']}/resultados"
    assert client.post(url, json=resultado, headers=so_leitura).status_code == 403


# O que o laboratório pode fazer


def test_laboratorio_le_pedidos_sem_dados_clinicos(client, lab, consulta_com_exames, consulta_payload, cenario):
    consulta_payload["exames_solicitados"] = []
    client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"])  # sem exames: não aparece

    pedidos = client.get("/laboratorio/pedidos", headers=lab).json()
    assert len(pedidos) == 1
    assert set(pedidos[0]) == {"consulta_id", "paciente", "data_hora", "exames_solicitados"}
    assert "motivo" not in pedidos[0]


def test_laboratorio_envia_resultado_e_profissional_le(client, lab, cenario, consulta_com_exames):
    url = f"/laboratorio/pedidos/{consulta_com_exames['id']}/resultados"
    resposta = client.post(url, json={"exame": "Troponina", "resultado": "0,01 ng/mL"}, headers=lab)
    assert resposta.status_code == 201
    assert resposta.json()["laboratorio"] == "Laboratório Parceiro"

    lidos = client.get(f"/consultas/{consulta_com_exames['id']}/resultados", headers=cenario["dra_ana"]).json()
    assert [r["exame"] for r in lidos] == ["Troponina"]
    assert client.get(f"/consultas/{consulta_com_exames['id']}/resultados", headers=cenario["joao"]).status_code == 404


def test_laboratorio_so_envia_exame_solicitado(client, lab, consulta_com_exames):
    url = f"/laboratorio/pedidos/{consulta_com_exames['id']}/resultados"
    assert client.post(url, json={"exame": "Glicemia", "resultado": "90"}, headers=lab).status_code == 422


# O que o laboratório não pode fazer, mesmo com um token válido


@pytest.mark.parametrize(
    "metodo,url",
    [
        ("get", "/consultas"),
        ("get", "/consultas/1"),
        ("put", "/consultas/1"),
        ("delete", "/consultas/1"),
        ("get", "/consultas/1/resultados"),
        ("get", "/admin/usuarios"),
    ],
)
def test_token_do_laboratorio_nao_alcanca_rotas_de_consulta_nem_admin(client, lab, consulta_com_exames, metodo, url):
    kwargs = {"json": {"status": "cancelada"}} if metodo == "put" else {}
    assert getattr(client, metodo)(url, headers=lab, **kwargs).status_code == 403


def test_token_do_laboratorio_nao_abre_paginas(client, lab):
    token = lab["Authorization"].removeprefix("Bearer ")
    client.cookies.set("sessao", token, path="/pagina")
    assert client.get("/pagina/consultas", follow_redirects=False).status_code == 303


# O que o profissional não pode fazer nas rotas do laboratório


@pytest.mark.parametrize("quem", ["dra_ana", "maria"])
def test_usuario_humano_nao_acessa_rotas_do_laboratorio(client, cenario, consulta_com_exames, quem):
    assert client.get("/laboratorio/pedidos", headers=cenario[quem]).status_code == 403
    url = f"/laboratorio/pedidos/{consulta_com_exames['id']}/resultados"
    assert client.post(url, json={"exame": "Hemograma", "resultado": "x"}, headers=cenario[quem]).status_code == 403


def test_administrador_tambem_nao_acessa_rotas_do_laboratorio(client, admin_headers):
    assert client.get("/laboratorio/pedidos", headers=admin_headers).status_code == 403
