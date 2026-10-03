"""Suíte de testes de autenticação e autorização. Iniciada no Exercício 6, para ser
expandida no Exercício 12."""

from datetime import timedelta

import jwt
import pytest

from app.config import settings
from app.database import usuarios_db
from app.security import criar_access_token
from tests.conftest import SENHA, login

# Exercício 6: rota restrita a administradores


@pytest.mark.parametrize("quem", ["maria", "dra_ana"])
def test_nao_administrador_e_impedido_de_acessar_rota_admin(client, cenario, quem):
    resposta = client.get("/admin/usuarios", headers=cenario[quem])
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Escopo insuficiente para esta operação"


def test_nao_administrador_nao_cria_usuario_privilegiado(client, db, cenario):
    novo = {"username": "intruso", "nome": "Intruso", "password": SENHA, "papel": "administrador"}
    assert client.post("/admin/usuarios", json=novo, headers=cenario["dra_ana"]).status_code == 403
    assert usuarios_db.obter_por_username(db, "intruso") is None


def test_administrador_acessa_rota_admin(client, admin_headers):
    resposta = client.get("/admin/usuarios", headers=admin_headers)
    assert resposta.status_code == 200
    assert {"username": "admin", "nome": "Administrador", "papel": "administrador"} in resposta.json()


def test_rota_protegida_sem_token_retorna_401(client):
    assert client.get("/admin/usuarios").status_code == 401
    assert client.get("/consultas").status_code == 401


# Exercício 6: cadastro público e hashing


def test_cadastro_publico_sempre_cria_paciente(client):
    corpo = {"username": "carla", "nome": "Carla", "password": SENHA}
    assert client.post("/usuarios", json=corpo).json()["papel"] == "paciente"

    corpo_com_papel = {**corpo, "username": "carla2", "papel": "administrador"}
    resposta = client.post("/usuarios", json=corpo_com_papel)
    assert resposta.status_code == 422
    assert resposta.json()["detail"][0]["type"] == "extra_forbidden"


def test_senha_armazenada_so_como_hash_bcrypt(client, db):
    client.post("/usuarios", json={"username": "carla", "nome": "Carla", "password": SENHA})
    armazenado = usuarios_db.obter_por_username(db, "carla")
    assert armazenado.hashed_password != SENHA
    assert armazenado.hashed_password.startswith("$2b$")
    assert "password" not in armazenado.model_dump()


def test_login_nao_revela_se_usuario_existe(client, cenario):
    inexistente = client.post("/token", data={"username": "nao.existe", "password": "x"})
    senha_errada = client.post("/token", data={"username": "maria", "password": "errada"})
    assert inexistente.status_code == senha_errada.status_code == 401
    assert inexistente.json() == senha_errada.json()


# Exercício 6: JWT com expiração


def test_token_tem_sub_opaco_expiracao_e_audiencia(client, db, cenario):
    token = cenario["maria"]["Authorization"].removeprefix("Bearer ")
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["sub"] == usuarios_db.obter_por_username(db, "maria").id
    assert payload["sub"] != "maria"
    assert payload["exp"] - payload["iat"] == settings.access_token_expire_minutes * 60
    assert payload["aud"] == settings.jwt_audience
    assert payload["escopos"] == ["consultas:read"]


def _token_forjado(db, **sobrescrever) -> dict:
    maria = usuarios_db.obter_por_username(db, "maria")
    claims = {"sub": maria.id, "tipo_cliente": "usuario", "papel": "paciente", "escopos": ["consultas:read"]}
    claims.update(sobrescrever)
    return claims


def test_token_expirado_e_recusado(client, db, cenario):
    token = criar_access_token(_token_forjado(db), timedelta(seconds=-1))
    assert client.get("/consultas", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_com_alg_none_e_recusado(client, db, cenario):
    claims = _token_forjado(db, escopos=["consultas:read", "admin"], iss=settings.jwt_issuer, aud=settings.jwt_audience)
    claims.update({"iat": 1, "exp": 9999999999})
    token = jwt.encode(claims, key=None, algorithm="none")
    assert client.get("/admin/usuarios", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_assinado_com_outra_chave_e_recusado(client, db, cenario):
    claims = _token_forjado(db, escopos=["admin"], iss=settings.jwt_issuer, aud=settings.jwt_audience)
    claims.update({"iat": 1, "exp": 9999999999})
    token = jwt.encode(claims, "chave-do-atacante-com-tamanho-suficiente-32b", algorithm="HS256")
    assert client.get("/admin/usuarios", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_de_outra_audiencia_e_recusado(client, db, cenario):
    claims = _token_forjado(db, iss=settings.jwt_issuer, aud="outro-sistema")
    claims.update({"iat": 1, "exp": 9999999999})
    token = jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)
    assert client.get("/consultas", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# Exercício 6: MFA simulado para administradores


def test_admin_nao_recebe_token_sem_segundo_fator(client):
    corpo = client.post("/token", data={"username": "admin", "password": "senha-admin-teste"}).json()
    assert corpo["mfa_requerido"] is True
    assert "access_token" not in corpo


def test_codigo_mfa_e_de_uso_unico(client):
    desafio = client.post("/token", data={"username": "admin", "password": "senha-admin-teste"}).json()
    dados = {"mfa_token": desafio["mfa_token"], "codigo": desafio["codigo_simulado"]}
    assert client.post("/token/mfa", data=dados).status_code == 200
    assert client.post("/token/mfa", data=dados).status_code == 401


def test_desafio_mfa_invalida_apos_tres_erros(client):
    desafio = client.post("/token", data={"username": "admin", "password": "senha-admin-teste"}).json()
    for _ in range(3):
        client.post("/token/mfa", data={"mfa_token": desafio["mfa_token"], "codigo": "000000"})
    certo = {"mfa_token": desafio["mfa_token"], "codigo": desafio["codigo_simulado"]}
    assert client.post("/token/mfa", data=certo).status_code == 401


# Exercício 6: ownership nas consultas


@pytest.fixture
def consulta_da_maria(client, cenario, consulta_payload):
    return client.post("/consultas", json=consulta_payload, headers=cenario["dra_ana"]).json()


def test_paciente_le_a_propria_consulta(client, cenario, consulta_da_maria):
    assert client.get(f"/consultas/{consulta_da_maria['id']}", headers=cenario["maria"]).status_code == 200


def test_outro_paciente_recebe_404(client, cenario, consulta_da_maria):
    resposta = client.get(f"/consultas/{consulta_da_maria['id']}", headers=cenario["joao"])
    assert resposta.status_code == 404
    assert resposta.json() == client.get("/consultas/999", headers=cenario["joao"]).json()


def test_outro_profissional_nao_le_nem_altera(client, cenario, consulta_da_maria):
    url = f"/consultas/{consulta_da_maria['id']}"
    assert client.get(url, headers=cenario["dr_paulo"]).status_code == 404
    assert client.put(url, json={"status": "cancelada"}, headers=cenario["dr_paulo"]).status_code == 404
    assert client.delete(url, headers=cenario["dr_paulo"]).status_code == 404


def test_paciente_nao_cria_nem_altera_consulta(client, cenario, consulta_payload, consulta_da_maria):
    assert client.post("/consultas", json=consulta_payload, headers=cenario["maria"]).status_code == 403
    url = f"/consultas/{consulta_da_maria['id']}"
    assert client.put(url, json={"status": "realizada"}, headers=cenario["maria"]).status_code == 403


def test_listagem_filtrada_pelo_dono(client, cenario, consulta_payload, consulta_da_maria):
    assert len(client.get("/consultas", headers=cenario["maria"]).json()) == 1
    assert client.get("/consultas", headers=cenario["joao"]).json() == []
    assert client.get("/consultas", headers=cenario["dr_paulo"]).json() == []


# Exercício 6: sessão das páginas HTML


def test_pagina_sem_sessao_redireciona_para_login(client):
    resposta = client.get("/pagina/consultas", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/pagina/login"


def test_cookie_de_sessao_tem_flags_de_seguranca(client, cenario):
    resposta = client.post("/pagina/login", data={"username": "maria", "password": SENHA}, follow_redirects=False)
    cookie = resposta.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/pagina" in cookie


def test_pagina_de_consulta_alheia_retorna_404(client, cenario, consulta_da_maria):
    client.post("/pagina/login", data={"username": "joao", "password": SENHA})
    assert client.get(f"/pagina/consultas/{consulta_da_maria['id']}").status_code == 404


def test_token_da_api_nao_vale_como_cookie_sem_login(client, cenario):
    # O Bearer da API não abre as páginas: as páginas só aceitam o cookie de sessão.
    resposta = client.get("/pagina/consultas", headers=cenario["maria"], follow_redirects=False)
    assert resposta.status_code == 303


def test_login_admin_na_pagina_exige_mfa(client):
    resposta = client.post("/pagina/login", data={"username": "admin", "password": "senha-admin-teste"})
    assert resposta.status_code == 200
    assert 'name="mfa_token"' in resposta.text
    assert "set-cookie" not in resposta.headers


def test_login_helper_funciona(client, cenario):
    # Sanidade: o helper do conftest obtém token válido para admin (com MFA) e paciente.
    assert client.get("/consultas", headers=login(client, "maria")).status_code == 200
