"""Exercício 2: a mesma função de dados, com e sem response_model.

A rota sem response_model existe só neste script, num app FastAPI descartável;
ela não é registrada na aplicação real, para não virar superfície de ataque.

Rodar da raiz do projeto: PYTHONPATH=. ./venv/bin/python docs/evidencias/comparar_response_model.py
"""
import json
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.database import consultas_db
from app.models.consulta import ConsultaCreate, ConsultaResponse

demo = FastAPI()


@demo.post("/com-response-model", response_model=ConsultaResponse, status_code=201)
def com(dados: ConsultaCreate, request: Request):
    return consultas_db.criar_consulta(dados, request.client.host)


@demo.post("/sem-response-model", status_code=201)
def sem(dados: ConsultaCreate, request: Request):
    return consultas_db.criar_consulta(dados, request.client.host)


payload = {
    "paciente": "Maria Souza",
    "medico": "Dr. Paulo Lima",
    "especialidade": "Cardiologia",
    "data_hora": (datetime.now() + timedelta(days=7)).replace(hour=9, minute=30, second=0, microsecond=0).isoformat(),
    "motivo": "Retorno para avaliação de exames",
}
c = TestClient(demo)
print("COM response_model=ConsultaResponse:")
print(json.dumps(c.post("/com-response-model", json=payload).json(), ensure_ascii=False))
print()
print("SEM response_model:")
print(json.dumps(c.post("/sem-response-model", json=payload).json(), ensure_ascii=False))
