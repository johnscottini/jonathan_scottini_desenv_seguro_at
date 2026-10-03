from datetime import datetime, timedelta

from app.database import consultas_db

CAMPOS_PUBLICOS = {
    "id", "paciente", "profissional", "especialidade", "data_hora", "motivo", "status", "exames_solicitados"
}
CAMPOS_INTERNOS = {
    "paciente_id",
    "profissional_id",
    "prontuario_paciente",
    "audit_token",
    "audit_origem_ip",
    "audit_criado_em",
}


def _criar(client, headers, payload):
    resposta = client.post("/consultas", json=payload, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# Exercício 1: caminhos de sucesso do recurso consultas


def test_health_check(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "servico": "agendamento-api"}


def test_criar_consulta(client, cenario, consulta_payload):
    corpo = _criar(client, cenario["dra_ana"], consulta_payload)
    assert corpo["id"] == 1
    assert corpo["paciente"] == "Maria Souza"
    # O profissional vem do token, não do corpo (Exercício 6).
    assert corpo["profissional"] == "Dra. Ana Costa"
    assert corpo["status"] == "agendada"


def test_listar_consultas(client, cenario, consulta_payload):
    assert client.get("/consultas", headers=cenario["dra_ana"]).json() == []
    _criar(client, cenario["dra_ana"], consulta_payload)
    resposta = client.get("/consultas", headers=cenario["dra_ana"])
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_obter_consulta_por_id(client, cenario, consulta_payload):
    criada = _criar(client, cenario["dra_ana"], consulta_payload)
    resposta = client.get(f"/consultas/{criada['id']}", headers=cenario["dra_ana"])
    assert resposta.status_code == 200
    assert resposta.json() == criada


def test_atualizar_consulta(client, cenario, consulta_payload):
    criada = _criar(client, cenario["dra_ana"], consulta_payload)
    resposta = client.put(f"/consultas/{criada['id']}", json={"status": "realizada"}, headers=cenario["dra_ana"])
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "realizada"
    assert resposta.json()["especialidade"] == consulta_payload["especialidade"]


def test_cancelar_consulta_e_logico(client, cenario, consulta_payload):
    criada = _criar(client, cenario["dra_ana"], consulta_payload)
    assert client.delete(f"/consultas/{criada['id']}", headers=cenario["dra_ana"]).status_code == 204
    # O registro de saúde continua existindo, só muda de status.
    resposta = client.get(f"/consultas/{criada['id']}", headers=cenario["dra_ana"])
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "cancelada"


# Exercício 1: validação de entrada


def test_consulta_inexistente_retorna_404(client, cenario):
    assert client.get("/consultas/999", headers=cenario["dra_ana"]).status_code == 404


def test_rejeita_data_no_passado(client, cenario, consulta_payload):
    consulta_payload["data_hora"] = (datetime.now() - timedelta(days=1)).isoformat()
    assert client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).status_code == 422


def test_rejeita_campo_extra(client, cenario, consulta_payload):
    consulta_payload["audit_token"] = "forjado"
    resposta = client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"])
    assert resposta.status_code == 422
    assert resposta.json()["detail"][0]["type"] == "extra_forbidden"


def test_rejeita_paciente_inexistente(client, cenario, consulta_payload):
    consulta_payload["paciente"] = "nao.existe"
    assert client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).status_code == 422


# Exercício 2: response_model controla exatamente os campos expostos


def test_resposta_expoe_somente_campos_publicos(client, cenario, consulta_payload):
    criada = _criar(client, cenario["dra_ana"], consulta_payload)
    assert set(criada) == CAMPOS_PUBLICOS

    headers = cenario["dra_ana"]
    for resposta in (
        client.get(f"/consultas/{criada['id']}", headers=headers).json(),
        client.get("/consultas", headers=headers).json()[0],
    ):
        assert set(resposta) == CAMPOS_PUBLICOS


def test_campos_internos_existem_no_armazenamento_mas_nao_na_resposta(client, db, cenario, consulta_payload):
    criada = _criar(client, cenario["dra_ana"], consulta_payload)
    armazenada = consultas_db.obter_consulta(db, criada["id"]).model_dump()
    assert CAMPOS_INTERNOS <= set(armazenada)
    assert CAMPOS_INTERNOS.isdisjoint(criada)


# Exercício 2: página HTML com herança de templates e auto-escape


def _entrar_na_pagina(client, username, password="senha-forte-123"):
    resposta = client.post("/pagina/login", data={"username": username, "password": password}, follow_redirects=False)
    assert resposta.status_code == 303
    return resposta


def test_pagina_lista_usa_template_base(client, cenario, consulta_payload):
    _criar(client, cenario["dra_ana"], consulta_payload)
    _entrar_na_pagina(client, "dra.ana")
    resposta = client.get("/pagina/consultas")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    assert "agendamento-api — painel interno da clínica" in resposta.text
    assert "Maria Souza" in resposta.text


def test_pagina_detalhe_escapa_xss_no_motivo(client, cenario, consulta_payload):
    payload_xss = "<script>alert('xss')</script>"
    consulta_payload["motivo"] = payload_xss
    criada = _criar(client, cenario["dra_ana"], consulta_payload)
    _entrar_na_pagina(client, "dra.ana")

    html = client.get(f"/pagina/consultas/{criada['id']}").text
    assert payload_xss not in html
    assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in html


def test_pagina_detalhe_nao_exibe_campos_internos(client, db, cenario, consulta_payload):
    criada = _criar(client, cenario["dra_ana"], consulta_payload)
    armazenada = consultas_db.obter_consulta(db, criada["id"])
    _entrar_na_pagina(client, "dra.ana")

    html = client.get(f"/pagina/consultas/{criada['id']}").text
    assert armazenada.audit_token not in html
    assert str(armazenada.prontuario_paciente) not in html
    assert armazenada.paciente_id not in html
