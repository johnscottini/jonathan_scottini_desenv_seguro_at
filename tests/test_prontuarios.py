"""Prontuário clínico: caminhos de sucesso (a parte de segurança está em test_vulnerabilidades.py)."""

import pytest

PRONTUARIO = {
    "diagnostico": "Angina estável",
    "anotacoes": "Dor torácica aos esforços há 2 meses.\nECG sem alterações agudas.",
    "prescricao": "AAS 100 mg/dia",
}


@pytest.fixture
def consulta_da_maria(client, cenario, consulta_payload):
    return client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).json()


@pytest.fixture
def prontuario_da_maria(client, cenario, consulta_da_maria):
    resposta = client.post(f"/consultas/{consulta_da_maria['id']}/prontuario", json=PRONTUARIO, headers=cenario["dra_ana"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_profissional_registra_prontuario_da_propria_consulta(prontuario_da_maria):
    assert prontuario_da_maria["paciente"] == "Maria Souza"
    assert prontuario_da_maria["profissional"] == "Dra. Ana Costa"
    assert prontuario_da_maria["diagnostico"] == "Angina estável"


def test_prontuario_unico_por_consulta(client, cenario, consulta_da_maria, prontuario_da_maria):
    url = f"/consultas/{consulta_da_maria['id']}/prontuario"
    assert client.post(url, json=PRONTUARIO, headers=cenario["dra_ana"]).status_code == 409


def test_outro_profissional_nao_registra_prontuario(client, cenario, consulta_da_maria):
    url = f"/consultas/{consulta_da_maria['id']}/prontuario"
    assert client.post(url, json=PRONTUARIO, headers=cenario["dr_paulo"]).status_code == 404


def test_paciente_le_o_proprio_prontuario(client, cenario, prontuario_da_maria):
    resposta = client.get(f"/prontuarios/{prontuario_da_maria['id']}", headers=cenario["maria"])
    assert resposta.status_code == 200
    assert resposta.json()["diagnostico"] == "Angina estável"


def test_profissional_atualiza_o_proprio_prontuario(client, cenario, prontuario_da_maria):
    resposta = client.put(
        f"/prontuarios/{prontuario_da_maria['id']}", json={"prescricao": "AAS 100 mg/dia + estatina"}, headers=cenario["dra_ana"]
    )
    assert resposta.status_code == 200
    assert resposta.json()["prescricao"] == "AAS 100 mg/dia + estatina"
    assert resposta.json()["atualizado_em"] is not None


def test_busca_por_diagnostico(client, cenario, prontuario_da_maria):
    resposta = client.get("/prontuarios/busca", params={"termo": "Angina"}, headers=cenario["maria"])
    assert resposta.status_code == 200
    assert [p["id"] for p in resposta.json()] == [prontuario_da_maria["id"]]
    assert client.get("/prontuarios/busca", params={"termo": "Angina"}, headers=cenario["joao"]).json() == []


def test_pagina_do_prontuario(client, cenario, prontuario_da_maria):
    client.post("/pagina/login", data={"username": "maria", "password": "senha-forte-123"})
    resposta = client.get(f"/pagina/prontuarios/{prontuario_da_maria['id']}")
    assert resposta.status_code == 200
    assert "Angina estável" in resposta.text
