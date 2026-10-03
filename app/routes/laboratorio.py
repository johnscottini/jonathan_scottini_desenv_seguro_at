from fastapi import APIRouter, Depends, HTTPException, Security
from sqlmodel import Session

from app.database import clientes_m2m_db, consultas_db, resultados_db
from app.database.session import get_session
from app.models.consulta import StatusConsulta
from app.models.laboratorio import PedidoExameResponse, ResultadoExameCreate, ResultadoExameResponse
from app.security import get_cliente_m2m

# Exercício 7: únicas operações que o contrato do laboratório autoriza. Cada rota exige
# um escopo exames:* e um token M2M; o laboratório não alcança nenhuma rota de consultas.
router = APIRouter(prefix="/laboratorio")


@router.get("/pedidos", response_model=list[PedidoExameResponse])
def listar_pedidos(
    _lab: dict = Security(get_cliente_m2m, scopes=["exames:read"]),
    session: Session = Depends(get_session),
):
    return [
        {
            "consulta_id": c.id,
            "paciente": c.paciente,
            "data_hora": c.data_hora,
            "exames_solicitados": c.exames_solicitados,
        }
        for c in consultas_db.listar_pedidos_de_exame(session)
    ]


@router.post("/pedidos/{consulta_id}/resultados", response_model=ResultadoExameResponse, status_code=201)
def enviar_resultado(
    consulta_id: int,
    dados: ResultadoExameCreate,
    lab: dict = Security(get_cliente_m2m, scopes=["exames:write"]),
    session: Session = Depends(get_session),
):
    consulta = consultas_db.obter_consulta(session, consulta_id)
    if consulta is None or consulta.status == StatusConsulta.cancelada:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    # Mesmo com escopo de escrita, o laboratório só grava resultado de exame que foi pedido.
    if dados.exame not in consulta.exames_solicitados:
        raise HTTPException(status_code=422, detail="Exame não solicitado nesta consulta")
    nome = clientes_m2m_db.obter(session, lab["id"]).nome
    return resultados_db.registrar_resultado(session, consulta_id, dados, nome)
