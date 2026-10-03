"""Exercício 13: testes unitários com mocking, cobrindo entrada e autorização em isolamento.

Diferente dos testes de integração (que sobem a app com TestClient), aqui cada função é
testada sozinha, com as dependências de banco e de request substituídas por mocks.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app import security
from app.models.consulta import ConsultaCreate, ConsultaUpdate
from app.models.prontuario import ProntuarioUpdate
from app.rate_limit import limitar_requisicoes

# --- Autorização: autorizar_dono, testado sem banco ---------------------------

PACIENTE = {"id": "u-paciente", "papel": "paciente", "escopos": ["consultas:read"]}
PROFISSIONAL = {"id": "u-profissional", "papel": "profissional", "escopos": ["consultas:read", "consultas:write"]}
ADMIN = {"id": "u-admin", "papel": "administrador", "escopos": ["admin"]}


def _recurso(**kwargs):
    return SimpleNamespace(**kwargs)


def test_autorizar_dono_libera_o_dono():
    recurso = _recurso(paciente_id="u-paciente", profissional_id="u-profissional")
    assert security.autorizar_dono(recurso, PACIENTE, ["paciente_id", "profissional_id"]) is recurso


def test_autorizar_dono_bloqueia_quem_nao_e_dono():
    recurso = _recurso(paciente_id="outro", profissional_id="u-profissional")
    with pytest.raises(HTTPException) as exc:
        security.autorizar_dono(recurso, PACIENTE, ["paciente_id", "profissional_id"])
    assert exc.value.status_code == 404


def test_autorizar_dono_recurso_inexistente_e_404_igual():
    with pytest.raises(HTTPException) as exc:
        security.autorizar_dono(None, PACIENTE, ["paciente_id"])
    assert exc.value.status_code == 404


def test_autorizar_dono_admin_tem_passe_livre():
    recurso = _recurso(paciente_id="outro", profissional_id="mais-outro")
    assert security.autorizar_dono(recurso, ADMIN, ["paciente_id", "profissional_id"]) is recurso


def test_autorizar_dono_escrita_exclui_paciente():
    # Na escrita só o profissional é dono; o paciente da consulta não pode escrever.
    recurso = _recurso(paciente_id="u-paciente", profissional_id="u-profissional")
    with pytest.raises(HTTPException):
        security.autorizar_dono(recurso, PACIENTE, ["profissional_id"])


# --- Autenticação: autenticar_usuario com banco e hashing mockados ------------


def test_autenticar_usuario_sucesso():
    usuario = SimpleNamespace(id="u1", hashed_password="hash", papel="paciente")
    session = Mock()
    with patch("app.security.usuarios_db.obter_por_username", return_value=usuario), \
         patch("app.security.verificar_senha", return_value=True) as verif:
        assert security.autenticar_usuario(session, "maria", "senha") is usuario
        verif.assert_called_once_with("senha", "hash")


def test_autenticar_usuario_senha_errada_retorna_none():
    usuario = SimpleNamespace(id="u1", hashed_password="hash", papel="paciente")
    with patch("app.security.usuarios_db.obter_por_username", return_value=usuario), \
         patch("app.security.verificar_senha", return_value=False):
        assert security.autenticar_usuario(Mock(), "maria", "errada") is None


def test_autenticar_usuario_inexistente_gasta_tempo_constante():
    # Sem usuário, ainda assim verifica contra o hash fictício (defesa contra enumeração
    # por tempo de resposta). O retorno é None.
    with patch("app.security.usuarios_db.obter_por_username", return_value=None), \
         patch("app.security.verificar_senha", return_value=False) as verif:
        assert security.autenticar_usuario(Mock(), "fantasma", "x") is None
        verif.assert_called_once_with("x", security.HASH_FICTICIO)


# --- Entrada: validação dos schemas Pydantic (unitário, sem HTTP) -------------


def test_consulta_create_rejeita_campo_extra():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ConsultaCreate(paciente="maria", especialidade="Cardio", data_hora="2099-01-01T10:00:00",
                       motivo="x", campo_oculto="malicioso")


def test_consulta_create_rejeita_data_no_passado():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ConsultaCreate(paciente="maria", especialidade="Cardio", data_hora="2000-01-01T10:00:00", motivo="x")


def test_consulta_create_rejeita_paciente_com_caractere_invalido():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ConsultaCreate(paciente="maria; DROP", especialidade="Cardio",
                       data_hora="2099-01-01T10:00:00", motivo="x")


def test_prontuario_update_proibe_campo_interno():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProntuarioUpdate(prescricao="x", criado_em="2000-01-01T00:00:00", profissional="Outro")


def test_consulta_update_status_fora_do_enum_e_rejeitado():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ConsultaUpdate(status="faturada")


# --- Pontos de entrada da aplicação, testados em unidade -----------------------


def test_status_servico_entrada_do_exercicio_1():
    # O mesmo endpoint do teste inicial do Exercício 1, agora testado como unidade
    # (chamada direta da função, sem subir o servidor).
    from app.main import status_servico

    assert status_servico() == {"status": "ok", "servico": "agendamento-api"}


def test_iniciar_login_admin_dispara_mfa():
    from app.routes.auth import iniciar_login
    from app.models.token import DesafioMFA

    admin = SimpleNamespace(id="a1", papel="administrador", hashed_password="h", nome="Admin")
    with patch("app.routes.auth.autenticar_usuario", return_value=admin):
        resultado = iniciar_login(Mock(), "admin", "senha")
    assert isinstance(resultado, DesafioMFA)
    assert resultado.mfa_requerido is True


def test_iniciar_login_paciente_recebe_token_direto():
    from app.routes.auth import iniciar_login
    from app.models.token import Token

    paciente = SimpleNamespace(id="p1", papel="paciente", hashed_password="h", nome="Maria")
    with patch("app.routes.auth.autenticar_usuario", return_value=paciente):
        resultado = iniciar_login(Mock(), "maria", "senha")
    assert isinstance(resultado, Token)
    assert resultado.access_token


def test_iniciar_login_credencial_invalida_levanta_401():
    from app.routes.auth import iniciar_login

    with patch("app.routes.auth.autenticar_usuario", return_value=None):
        with pytest.raises(HTTPException) as exc:
            iniciar_login(Mock(), "x", "y")
    assert exc.value.status_code == 401


def test_cadastro_com_username_existente_gera_409():
    from app.routes.auth import cadastrar_paciente
    from app.models.usuario import UsuarioCreate

    dados = UsuarioCreate(username="maria", nome="Maria", password="senha-forte-123")
    with patch("app.routes.auth.usuarios_db.obter_por_username", return_value=SimpleNamespace(id="x")):
        with pytest.raises(HTTPException) as exc:
            cadastrar_paciente(dados, Mock())
    assert exc.value.status_code == 409


# --- Rate limiter: janela deslizante, com Request e tempo mockados ------------


def test_rate_limiter_bloqueia_apos_o_limite():
    verificar = limitar_requisicoes(limite=3, janela_segundos=60)
    req = Mock()
    req.client.host = "1.2.3.4"
    with patch("app.rate_limit.time.monotonic", side_effect=[0, 1, 2, 3]):
        for _ in range(3):
            verificar(req)  # 3 primeiras passam
        with pytest.raises(HTTPException) as exc:
            verificar(req)  # 4ª estoura
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


def test_rate_limiter_separa_por_ip():
    verificar = limitar_requisicoes(limite=1, janela_segundos=60)
    a, b = Mock(), Mock()
    a.client.host, b.client.host = "1.1.1.1", "2.2.2.2"
    with patch("app.rate_limit.time.monotonic", side_effect=[0, 0]):
        verificar(a)
        verificar(b)  # IP diferente, contador independente: não bloqueia
