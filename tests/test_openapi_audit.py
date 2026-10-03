"""Exercício 13: auditoria da especificação OpenAPI da aplicação.

Verifica, direto no schema gerado, que rotas sensíveis exigem autenticação e que nenhum
schema de resposta expõe campo interno de auditoria ou identificação.
"""

import pytest

# Rotas públicas por design (entrada do sistema). Todo o resto deve exigir segurança.
ROTAS_PUBLICAS = {
    ("/", "get"),
    ("/usuarios", "post"),
    ("/token", "post"),
    ("/token/mfa", "post"),
    ("/token/m2m", "post"),
    ("/pagina/login", "get"),
    ("/pagina/login", "post"),
    ("/pagina/login/mfa", "post"),
    ("/pagina/logout", "post"),
}

# Páginas protegidas por SESSÃO (cookie), não por Security(...). A proteção existe em
# runtime (redirecionam para o login sem cookie — verificado nos testes de integração),
# mas a autenticação por cookie não é declarada como securityScheme no OpenAPI. É um
# achado de completude da spec, documentado no relatório do Exercício 13.
PAGINAS_COM_SESSAO = {
    ("/pagina/consultas", "get"),
    ("/pagina/consultas/{consulta_id}", "get"),
    ("/pagina/prontuarios/{prontuario_id}", "get"),
}

# Campos internos que jamais podem aparecer em um schema de resposta.
CAMPOS_INTERNOS = {"paciente_id", "profissional_id", "prontuario_paciente", "audit_token",
                   "audit_origem_ip", "audit_criado_em", "hashed_password", "hashed_secret"}


@pytest.fixture
def openapi(client):
    return client.get("/openapi.json").json()


def test_rotas_sensiveis_exigem_seguranca(openapi):
    desprotegidas = []
    for caminho, metodos in openapi["paths"].items():
        for metodo, op in metodos.items():
            if (caminho, metodo) in ROTAS_PUBLICAS | PAGINAS_COM_SESSAO:
                continue
            if "security" not in op:
                desprotegidas.append(f"{metodo.upper()} {caminho}")
    # Toda rota de API sensível (fora as públicas e as páginas com sessão) declara segurança.
    assert desprotegidas == [], f"rotas de API sem requisito de segurança: {desprotegidas}"


def test_paginas_com_sessao_protegidas_em_runtime(client):
    # A contrapartida do achado acima: sem cookie, as páginas redirecionam para o login.
    for caminho in ("/pagina/consultas", "/pagina/consultas/1", "/pagina/prontuarios/1"):
        resposta = client.get(caminho, follow_redirects=False)
        assert resposta.status_code == 303
        assert resposta.headers["location"] == "/pagina/login"


def test_nenhum_schema_de_resposta_expoe_campo_interno(openapi):
    vazamentos = []
    for nome, schema in openapi["components"]["schemas"].items():
        if not nome.endswith("Response"):
            continue
        for campo in schema.get("properties", {}):
            if campo in CAMPOS_INTERNOS:
                vazamentos.append(f"{nome}.{campo}")
    assert vazamentos == [], f"schemas de resposta expondo campo interno: {vazamentos}"


def test_response_model_de_consulta_tem_apenas_campos_publicos(openapi):
    props = set(openapi["components"]["schemas"]["ConsultaResponse"]["properties"])
    assert props == {"id", "paciente", "profissional", "especialidade", "data_hora", "motivo", "status", "exames_solicitados"}


def test_esquema_de_seguranca_declarado(openapi):
    # O esquema OAuth2 com os escopos precisa existir nos componentes.
    esquemas = openapi["components"]["securitySchemes"]
    assert "OAuth2PasswordBearer" in esquemas
    assert esquemas["OAuth2PasswordBearer"]["type"] == "oauth2"
