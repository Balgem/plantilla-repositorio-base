"""Bloque 32, paso 2: punto de supervisión humana para desplegar un prompt (sin API, sobre una copia del registro)."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import grafo_supervision as gs
import registro_prompts as rp
from registro_prompts import PROMPT_RAG, RegistroDePrompts


@pytest.fixture
def copia(tmp_path):
    archivo = tmp_path / "registro.json"
    registro = RegistroDePrompts(archivo)
    rp.cargar_historial(registro)
    registro.guardar()
    return archivo


@pytest.fixture
def app(copia):
    return gs.construir_grafo(InMemorySaver(), copia)


V2 = rp.huella_prompt(rp.V2_ANTI_INYECCION)
V3 = rp.huella_prompt(rp.V3_NO_SE_PARA_EL_VIEWER)


def activa(archivo):
    return RegistroDePrompts(archivo).activa(PROMPT_RAG)["huella"]


def test_prueba_2_sin_reanudar_trae_interrupt_y_no_despliega(app, copia):
    resultado = app.invoke({"nombre": PROMPT_RAG, "huella_nueva": V3}, config=gs.config_de("t1"))
    valor = resultado["__interrupt__"][0].value
    assert valor["motivo"] == gs.MOTIVO and valor["huella_propuesta"] == V3 and valor["huella_activa"] == V2
    assert "-dilo" in valor["diff"]                                  # la persona aprueba mirando el diff
    assert app.get_state(gs.config_de("t1")).next == ("supervisar",)
    assert activa(copia) == V2 and "resultado" not in resultado      # "aplicar" no corrió


def test_prueba_3_aprobar_activa_la_version(app, copia):
    thread_id, _ = gs.proponer_despliegue(app, V3)
    final = gs.resolver(app, thread_id, True, V3, por="Cris")
    assert final["aprobado"] is True and "__interrupt__" not in final
    assert activa(copia) == V3
    assert RegistroDePrompts(copia).activa(PROMPT_RAG)["decidido_por"] == "Cris"


def test_prueba_4_rechazar_en_otro_hilo_mantiene_la_anterior(app, copia):
    thread_id, _ = gs.proponer_despliegue(app, V3)
    final = gs.resolver(app, thread_id, False, V3, por="Cris")
    assert final["aprobado"] is False and "rechazada" in final["resultado"]
    assert activa(copia) == V2
    assert RegistroDePrompts(copia).buscar(PROMPT_RAG, V3)["estado"] == "rechazada"


@pytest.mark.parametrize("respuesta", ["no", "false", 1, "si"])
def test_resume_que_no_es_true_nunca_activa(app, copia, respuesta):
    thread_id, _ = gs.proponer_despliegue(app, V3)
    app.invoke(Command(resume=respuesta), config=gs.config_de(thread_id))
    assert activa(copia) == V2


def test_resolver_exige_bool_y_la_huella_revisada(app):
    thread_id, _ = gs.proponer_despliegue(app, V3)
    with pytest.raises(TypeError):
        gs.resolver(app, thread_id, "si", V3, por="Cris")
    with pytest.raises(ValueError, match="espera decidir"):
        gs.resolver(app, thread_id, True, V2, por="Cris")


def test_no_se_aprueba_dos_veces_ni_un_hilo_inexistente(app):
    thread_id, _ = gs.proponer_despliegue(app, V3)
    gs.resolver(app, thread_id, True, V3, por="Cris")
    for hilo in (thread_id, "despliegue-noexiste"):
        with pytest.raises(ValueError, match="no tiene ninguna aprobación pendiente"):
            gs.resolver(app, hilo, True, V3, por="Cris")


def test_thread_id_unico_y_sin_propuestas_duplicadas(app):
    thread_id, _ = gs.proponer_despliegue(app, V3)
    assert thread_id.startswith("despliegue-") and len(thread_id) == len("despliegue-") + 8
    with pytest.raises(ValueError, match="ya espera una decisión"):
        gs.proponer_despliegue(app, V3)
    assert [h for h, _ in gs.pendientes(app)] == [thread_id]


def test_solo_se_propone_una_version_propuesta(app):
    with pytest.raises(ValueError, match="activa"):
        gs.proponer_despliegue(app, V2)


def test_el_nodo_supervisar_no_tiene_efectos_aunque_se_ejecute_dos_veces(app, copia):
    """Al reanudar, LangGraph vuelve a ejecutar 'supervisar' desde su primera línea: el registro solo cambia en 'aplicar'."""
    antes = copia.read_text(encoding="utf-8")
    thread_id, _ = gs.proponer_despliegue(app, V3)
    assert copia.read_text(encoding="utf-8") == antes
    gs.resolver(app, thread_id, True, V3, por="Cris")
    assert copia.read_text(encoding="utf-8") != antes


def test_checkpointer_durable_sobrevive_a_otro_proceso(copia, tmp_path):
    """Una app propone y 'se cierra'; otra, con el mismo archivo, encuentra lo pendiente y lo aprueba."""
    db = tmp_path / "supervision.db"
    thread_id, _ = gs.proponer_despliegue(gs.app_durable(db, copia), V3)
    otra = gs.app_durable(db, copia)
    assert [h for h, _ in gs.pendientes(otra)] == [thread_id]
    gs.resolver(otra, thread_id, True, V3, por="Cris")
    assert activa(copia) == V3 and gs.pendientes(otra) == []


def test_la_demo_no_toca_el_registro_real(capsys):
    antes = rp.ARCHIVO_REGISTRO.read_text(encoding="utf-8")
    gs.demo()
    assert rp.ARCHIVO_REGISTRO.read_text(encoding="utf-8") == antes
    assert "activada" in capsys.readouterr().out


def test_el_grafo_deduce_que_la_propuesta_es_del_agente(app, copia):
    v4 = rp.huella_prompt(rp.V4_AGENTE)
    thread_id, valor = gs.proponer_despliegue(app, v4)
    assert valor["nombre"] == rp.PROMPT_AGENTE and valor["huella_activa"] == rp.huella_prompt(rp.V3_AGENTE)
    gs.resolver(app, thread_id, True, v4, por="Cris")
    registro = RegistroDePrompts(copia)
    assert registro.activa(rp.PROMPT_AGENTE)["huella"] == v4 and registro.activa(PROMPT_RAG)["huella"] == V2
