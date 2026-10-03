"""Exercício 12: testes de segurança derivados diretamente do threat model do Exercício 4.

Cada teste referencia o id da ameaça (AM-xx) que cobre, expandindo a suíte de autorização
iniciada no Exercício 6 para outros vetores mapeados: spoofing, tampering, information
disclosure, DoS e elevação de privilégio.
"""

from datetime import datetime, timedelta

import pytest


@pytest.fixture
def consulta_da_maria(client, cenario, consulta_payload):
    return client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).json()


# AM-01 (Spoofing): o paciente vem do token/base, não do corpo — não dá para agendar
# em nome de terceiro nem se declarar profissional.


def test_am01_profissional_da_consulta_vem_do_token(client, cenario, consulta_da_maria):
    # Quem criou foi a Dra. Ana (token), independentemente de qualquer campo do corpo.
    assert consulta_da_maria["profissional"] == "Dra. Ana Costa"


def test_am01_nao_se_agenda_para_paciente_inexistente(client, cenario, consulta_payload):
    consulta_payload["paciente"] = "fantasma"
    assert client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).status_code == 422


def test_am01_campo_profissional_no_corpo_e_rejeitado(client, cenario, consulta_payload):
    # Tentar injetar o profissional pelo corpo: extra="forbid" barra.
    consulta_payload["profissional"] = "Dr. Falso"
    assert client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).status_code == 422


# AM-02 (Tampering): não se altera consulta de outro; DELETE é cancelamento lógico.


def test_am02_outro_profissional_nao_altera_consulta(client, cenario, consulta_da_maria):
    url = f"/consultas/{consulta_da_maria['id']}"
    assert client.put(url, json={"status": "realizada"}, headers=cenario["dr_paulo"]).status_code == 404


def test_am02_paciente_nao_altera_a_propria_consulta(client, cenario, consulta_da_maria):
    # Paciente tem consultas:read, não write: não muda o status da própria consulta.
    url = f"/consultas/{consulta_da_maria['id']}"
    assert client.put(url, json={"status": "cancelada"}, headers=cenario["maria"]).status_code == 403


def test_am11_delete_e_cancelamento_logico(client, cenario, consulta_da_maria):
    # AM-11: o registro de saúde não é apagado fisicamente.
    url = f"/consultas/{consulta_da_maria['id']}"
    assert client.delete(url, headers=cenario["dra_ana"]).status_code == 204
    assert client.get(url, headers=cenario["dra_ana"]).json()["status"] == "cancelada"


# AM-04 (Information Disclosure / BOLA): dado de saúde não vaza para quem não é dono,
# nem por enumeração de id, nem pela listagem.


def test_am04_enumeracao_de_consulta_alheia_da_404(client, cenario, consulta_da_maria):
    resposta = client.get(f"/consultas/{consulta_da_maria['id']}", headers=cenario["joao"])
    assert resposta.status_code == 404
    assert resposta.json() == client.get("/consultas/99999", headers=cenario["joao"]).json()


def test_am04_listagem_nunca_traz_consulta_de_outro_paciente(client, cenario, consulta_da_maria):
    assert client.get("/consultas", headers=cenario["joao"]).json() == []


def test_am04_campos_internos_nunca_saem_na_api(client, cenario, consulta_da_maria):
    internos = {"paciente_id", "profissional_id", "prontuario_paciente", "audit_token", "audit_origem_ip"}
    assert internos.isdisjoint(consulta_da_maria)


# AM-06 (Elevation of Privilege / BFLA): papéis não alcançam funções acima deles.


@pytest.mark.parametrize("quem", ["maria", "dra_ana"])
def test_am06_nao_admin_nao_acessa_rota_administrativa(client, cenario, quem):
    assert client.get("/admin/usuarios", headers=cenario[quem]).status_code == 403


def test_am06_paciente_nao_cria_consulta(client, cenario, consulta_payload):
    assert client.post("/consultas", json=consulta_payload, headers=cenario["maria"]).status_code == 403


def test_am06_laboratorio_nao_alcanca_rota_de_consulta(client, cenario, consulta_da_maria):
    lab = client.post(
        "/token/m2m",
        data={"grant_type": "client_credentials", "client_id": "laboratorio-parceiro", "client_secret": "segredo-lab-teste"},
    ).json()
    h = {"Authorization": f"Bearer {lab['access_token']}"}
    assert client.get(f"/consultas/{consulta_da_maria['id']}", headers=h).status_code == 403


# AM-16 (Elevation of Privilege): JWT forjado ou adulterado é recusado.


def test_am16_token_sem_assinatura_valida_e_recusado(client, cenario):
    import jwt

    from app.config import settings

    claims = {"sub": "x", "papel": "administrador", "escopos": ["admin"], "iss": settings.jwt_issuer,
              "aud": settings.jwt_audience, "iat": 1, "exp": 9999999999}
    forjado = jwt.encode(claims, "chave-que-o-atacante-nao-tem-32bytes!", algorithm="HS256")
    assert client.get("/admin/usuarios", headers={"Authorization": f"Bearer {forjado}"}).status_code == 401


# AM-05 (Denial of Service): o login tem rate limit (verificado em detalhe em test_hardening).


def test_am05_login_tem_rate_limit(client, limite_login_baixo):
    codigos = [client.post("/token", data={"username": "x", "password": "y"}).status_code for _ in range(7)]
    assert 429 in codigos
