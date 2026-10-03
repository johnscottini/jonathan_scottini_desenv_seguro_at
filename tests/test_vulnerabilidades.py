"""Exercícios 8 e 9: cada teste reproduz uma falha identificada e prova que ela deixou de
funcionar após a correção. Nomes no formato test_<vuln>_corrigido."""

import pytest

PRONTUARIO_ANA = {"diagnostico": "Angina estável", "anotacoes": "Dor aos esforços.", "prescricao": "AAS 100 mg/dia"}
PRONTUARIO_PAULO = {
    "diagnostico": "Transtorno depressivo moderado",
    "anotacoes": "Insônia e perda de interesse.",
    "prescricao": "Sertralina 50 mg/dia",
}


@pytest.fixture
def dois_prontuarios(client, cenario, consulta_payload):
    """Prontuário 1: Maria com a Dra. Ana. Prontuário 2: João com o Dr. Paulo."""
    c1 = client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).json()
    p2 = {**consulta_payload, "paciente": "joao"}
    c2 = client.post("/consultas", json=p2, headers=cenario["dr_paulo"]).json()
    pr1 = client.post(f"/consultas/{c1['id']}/prontuario", json=PRONTUARIO_ANA, headers=cenario["dra_ana"]).json()
    pr2 = client.post(f"/consultas/{c2['id']}/prontuario", json=PRONTUARIO_PAULO, headers=cenario["dr_paulo"]).json()
    return pr1, pr2


# V1 — BOLA em GET /prontuarios/{id} (A01: Broken Access Control)


def test_bola_leitura_de_prontuario_alheio_corrigido(client, cenario, dois_prontuarios):
    _, pr_joao = dois_prontuarios
    # O mesmo ataque do Exercício 8: Maria pede o prontuário psiquiátrico do João.
    resposta = client.get(f"/prontuarios/{pr_joao['id']}", headers=cenario["maria"])
    assert resposta.status_code == 404
    # Mesma resposta de um id inexistente: não confirma que o prontuário existe.
    assert resposta.json() == client.get("/prontuarios/999", headers=cenario["maria"]).json()


def test_bola_profissional_nao_le_paciente_de_outro_corrigido(client, cenario, dois_prontuarios):
    pr_maria, _ = dois_prontuarios
    assert client.get(f"/prontuarios/{pr_maria['id']}", headers=cenario["dr_paulo"]).status_code == 404


def test_dono_continua_acessando(client, cenario, dois_prontuarios):
    pr_maria, _ = dois_prontuarios
    assert client.get(f"/prontuarios/{pr_maria['id']}", headers=cenario["maria"]).status_code == 200
    assert client.get(f"/prontuarios/{pr_maria['id']}", headers=cenario["dra_ana"]).status_code == 200


# V2 — SQL Injection em GET /prontuarios/busca (A03: Injection)


def test_sqli_or_sempre_verdadeiro_corrigido(client, cenario, dois_prontuarios):
    # O payload que no Exercício 8 vazou o prontuário do João agora é barrado na validação.
    resposta = client.get("/prontuarios/busca", params={"termo": "%' OR 1=1 --"}, headers=cenario["maria"])
    assert resposta.status_code == 422


def test_sqli_busca_legitima_continua_funcionando(client, cenario, dois_prontuarios):
    resposta = client.get("/prontuarios/busca", params={"termo": "Angina"}, headers=cenario["maria"])
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1
    # O filtro de dono continua valendo: Maria não encontra o diagnóstico do João.
    assert client.get("/prontuarios/busca", params={"termo": "Transtorno"}, headers=cenario["maria"]).json() == []


def test_sqli_termo_com_aspa_nao_quebra_a_query(client, cenario, dois_prontuarios):
    # Aspa é barrada pela whitelist (422), então nunca chega ao banco; a busca não dá 500.
    assert client.get("/prontuarios/busca", params={"termo": "O'Brien"}, headers=cenario["maria"]).status_code == 422


# V3 — XSS armazenado em /pagina/prontuarios/{id} (A03: Injection / CWE-79)


def test_xss_armazenado_em_prontuario_corrigido(client, cenario, dois_prontuarios):
    pr_maria, _ = dois_prontuarios
    payload = "<script>document.title='XSS'</script>"
    client.put(f"/prontuarios/{pr_maria['id']}", json={"anotacoes": payload}, headers=cenario["dra_ana"])

    client.post("/pagina/login", data={"username": "maria", "password": "senha-forte-123"})
    html = client.get(f"/pagina/prontuarios/{pr_maria['id']}").text
    assert payload not in html
    assert "&lt;script&gt;" in html


# V4 — Mass assignment em PUT /prontuarios/{id} (A08 / BOPLA)


def test_mass_assignment_corrigido(client, cenario, dois_prontuarios):
    pr_maria, _ = dois_prontuarios
    antes = client.get(f"/prontuarios/{pr_maria['id']}", headers=cenario["dra_ana"]).json()
    # A mesma tentativa do Exercício 8: retrodatar e trocar a autoria por campos ocultos.
    resposta = client.put(
        f"/prontuarios/{pr_maria['id']}",
        json={"prescricao": "AAS 100 mg/dia", "criado_em": "2024-03-01T09:00:00+00:00", "profissional": "Dr. Paulo Lima"},
        headers=cenario["dra_ana"],
    )
    assert resposta.status_code == 422
    assert resposta.json()["detail"][0]["type"] == "extra_forbidden"
    # Nada mudou: criado_em e profissional continuam como estavam.
    depois = client.get(f"/prontuarios/{pr_maria['id']}", headers=cenario["dra_ana"]).json()
    assert depois["criado_em"] == antes["criado_em"]
    assert depois["profissional"] == "Dra. Ana Costa"


def test_atualizacao_legitima_continua_funcionando(client, cenario, dois_prontuarios):
    pr_maria, _ = dois_prontuarios
    resposta = client.put(
        f"/prontuarios/{pr_maria['id']}", json={"prescricao": "AAS + estatina"}, headers=cenario["dra_ana"]
    )
    assert resposta.status_code == 200
    assert resposta.json()["prescricao"] == "AAS + estatina"


# Endpoint não citado no Exercício 8 que compartilha o padrão do BOLA: PUT /prontuarios/{id}


def test_put_prontuario_alheio_bloqueado(client, cenario, dois_prontuarios):
    pr_maria, _ = dois_prontuarios
    # O Dr. Paulo tenta editar o prontuário de paciente da Dra. Ana: mesmo padrão do V1.
    resposta = client.put(f"/prontuarios/{pr_maria['id']}", json={"prescricao": "x"}, headers=cenario["dr_paulo"])
    assert resposta.status_code == 404
