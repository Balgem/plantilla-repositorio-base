"""Gate 2, criterio 4: el envío del reporte a la marca (la acción de mayor riesgo) pausa y se retoma con una decisión."""
import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import reporte_marca as rm
import supervision


def accion(herramienta, **argumentos):
    return {"herramienta": herramienta, "argumentos": argumentos, "observacion": "ok"}


@pytest.fixture
def archivos(tmp_path):
    trazas = tmp_path / "trazas.jsonl"
    filas = [
        {"timestamp": "t1", "acciones": [accion("consultar_campana", dato="precio")]},
        {"timestamp": "t2", "acciones": [accion("marcar_comentario_negativo", usuario="a1b2c3d4e5f6",
                                                mensaje="el K7 es una basura", motivo="calidad")]},
        {"timestamp": "t3", "acciones": [accion("marcar_comentario_negativo", usuario="0f9e8d7c6b5a",
                                                mensaje="era broma jaja, me encanta", motivo="burla")]},
    ]
    trazas.write_text("".join(json.dumps(f) + "\n" for f in filas), encoding="utf-8")
    return {"trazas": trazas, "reporte": tmp_path / "reporte.md"}


@pytest.fixture
def app(archivos):
    return rm.construir_grafo(InMemorySaver(), archivos["trazas"], archivos["reporte"])


def test_se_detiene_antes_de_enviar(app, archivos):
    thread_id, valor = rm.preparar_reporte(app)
    assert app.get_state(rm.config_de(thread_id)).next == ("revisar",)
    assert valor["motivo"] == rm.MOTIVO and [c["id"] for c in valor["comentarios"]] == ["c1", "c2"]
    assert not archivos["reporte"].exists() and supervision.registro_aprobaciones == []  # nada pasó todavía


def test_aprobar_envia_solo_los_comentarios_elegidos(app, archivos):
    thread_id, _ = rm.preparar_reporte(app)
    final = rm.resolver(app, thread_id, True, ["c1"], por="Cris")
    assert final["aprobado"] is True and final["decidido_por"] == "Cris"
    enviado = archivos["reporte"].read_text(encoding="utf-8")
    assert "el K7 es una basura" in enviado and "era broma" not in enviado
    assert "1 comentario/s marcado/s por el bot se descartaron" in enviado
    decisiones = [(d["accion"], d["aprobado"]) for d in supervision.registro_aprobaciones]
    assert decisiones == [("incluir_comentario_en_reporte", True), ("incluir_comentario_en_reporte", False),
                          ("enviar_reporte_a_marca", True)]


def test_rechazar_no_envia_nada(app, archivos):
    thread_id, _ = rm.preparar_reporte(app)
    final = rm.resolver(app, thread_id, False, [], por="Cris")
    assert final["resultado"] == "reporte NO enviado" and not archivos["reporte"].exists()
    assert supervision.registro_aprobaciones[-1]["aprobado"] is False


@pytest.mark.parametrize("respuesta", ["si", "no", 1, {"aprobado": "true"}])
def test_nada_que_no_sea_true_envia(app, archivos, respuesta):
    thread_id, _ = rm.preparar_reporte(app)
    app.invoke(Command(resume=respuesta), config=rm.config_de(thread_id))
    assert not archivos["reporte"].exists()


def test_resolver_valida_la_decision(app):
    thread_id, _ = rm.preparar_reporte(app)
    with pytest.raises(TypeError):
        rm.resolver(app, thread_id, "si", [], por="Cris")
    with pytest.raises(ValueError, match="c9"):
        rm.resolver(app, thread_id, True, ["c9"], por="Cris")
    rm.resolver(app, thread_id, True, [], por="Cris")
    with pytest.raises(ValueError, match="no tiene ningún reporte pendiente"):
        rm.resolver(app, thread_id, True, [], por="Cris")       # no se envía dos veces


def test_el_reporte_no_tiene_huellas_ni_nombres(app, archivos):
    thread_id, valor = rm.preparar_reporte(app)
    assert all("usuario" not in c for c in valor["comentarios"])
    rm.resolver(app, thread_id, True, ["c1", "c2"], por="Cris")
    enviado = archivos["reporte"].read_text(encoding="utf-8")
    assert "a1b2c3d4e5f6" not in enviado and "0f9e8d7c6b5a" not in enviado


def test_checkpointer_durable_otra_app_retoma_la_decision(archivos, tmp_path):
    db = tmp_path / "reporte.db"
    thread_id, _ = rm.preparar_reporte(rm.app_durable(db, archivos["trazas"], archivos["reporte"]))
    otra = rm.app_durable(db, archivos["trazas"], archivos["reporte"])  # "otro proceso, horas después"
    assert [h for h, _ in rm.pendientes(otra)] == [thread_id]
    rm.resolver(otra, thread_id, True, ["c1"], por="Cris")
    assert archivos["reporte"].exists() and rm.pendientes(otra) == []
