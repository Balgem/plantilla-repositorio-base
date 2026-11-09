"""Bloque 23 (en vivo): clasificación de riesgo, flags de comentarios negativos y traza. Sin llamar a la API."""
import inspect
import json
import os
import sys

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

import agente_con_herramientas as ag
import agente_con_memoria as mem
import supervision
import trazas
from agente_con_herramientas import NIVEL_DE_RIESGO, marcar_comentario_negativo
from supervision import esperar_aprobacion


class ModeloFalso(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs) -> Runnable:
        return self.bind()


def llamada(herramienta, **argumentos):
    return AIMessage(content="", tool_calls=[{"name": herramienta, "args": argumentos, "id": herramienta}])


@pytest.fixture(autouse=True)
def estado_limpio():
    mem.cerrar_todas()
    ag.REGISTRO_CRM.clear()
    yield


# --- La clasificación del documento coincide con el código ---


def test_cada_herramienta_tiene_nivel_de_riesgo():
    assert {h.name for h in ag.HERRAMIENTAS} == set(NIVEL_DE_RIESGO)
    assert set(NIVEL_DE_RIESGO.values()) <= {"bajo", "medio", "alto"}


def test_el_agente_en_vivo_no_tiene_herramientas_de_riesgo_alto():
    """Lo que sale hacia la marca pasa por el reporte post-stream, con aprobación humana."""
    assert "alto" not in NIVEL_DE_RIESGO.values()
    for herramienta in ag.HERRAMIENTAS:  # y ninguna pide aprobación en pleno chat
        assert "esperar_aprobacion(" not in inspect.getsource(herramienta.func)


# --- Flag de comentarios negativos ---


def test_marcar_comentario_no_envia_nada_y_queda_pendiente():
    respuesta = marcar_comentario_negativo.invoke({"usuario": "troll99", "mensaje": "el K7 es una basura",
                                                   "motivo": "calidad"})
    assert "revisión humana" in respuesta
    assert ag.COMENTARIOS_MARCADOS[0]["estado"] == "pendiente de revisión"
    assert supervision.registro_aprobaciones == []  # marcar no es aprobar


def test_marcar_dos_veces_el_mismo_comentario_no_duplica():
    argumentos = {"usuario": "troll99", "mensaje": "el K7 es una basura", "motivo": "calidad"}
    marcar_comentario_negativo.invoke(argumentos)
    assert "ya estaba marcado" in marcar_comentario_negativo.invoke(argumentos)
    assert len(ag.COMENTARIOS_MARCADOS) == 1


def test_el_motivo_largo_se_rechaza():
    with pytest.raises(Exception):
        marcar_comentario_negativo.invoke({"usuario": "x", "mensaje": "y", "motivo": "z" * 151})


# --- esperar_aprobacion (se usa en el reporte post-stream) ---


def test_sin_consola_la_aprobacion_es_no():
    # dentro de pytest no hay stdin interactivo: el valor seguro es False, sin colgarse ni lanzar error
    assert esperar_aprobacion("¿Aprobar? ", tiempo_limite_segundos=1) is False


@pytest.mark.skipif(sys.platform == "win32", reason="select() sobre stdin no funciona en Windows")
def test_aprobacion_por_consola_con_si_no_y_timeout(monkeypatch):
    def con_entrada(texto):
        lectura, escritura = os.pipe()
        if texto is not None:
            os.write(escritura, texto.encode())
        monkeypatch.setattr(sys, "stdin", os.fdopen(lectura))
        return escritura

    con_entrada("s\n")
    assert esperar_aprobacion("? ", tiempo_limite_segundos=1) is True
    con_entrada(" N \n")
    assert esperar_aprobacion("? ", tiempo_limite_segundos=1) is False
    escritura = con_entrada(None)  # nadie escribe
    assert esperar_aprobacion("? ", tiempo_limite_segundos=0.2) is False
    os.close(escritura)


def test_registrar_aprobacion_guarda_quien_y_cuando():
    supervision.registrar_aprobacion("enviar_reporte_a_marca", {"reporte": "..."}, False)
    [linea] = supervision.ARCHIVO_APROBACIONES.read_text(encoding="utf-8").splitlines()
    decision = json.loads(linea)
    assert decision["aprobado"] is False and decision["aprobado_por"] and decision["momento"]


# --- Traza ---


def test_registrar_traza_escribe_una_linea_json(tmp_path):
    archivo = tmp_path / "t.jsonl"
    accion = type("Accion", (), {"tool": "consultar_campana", "tool_input": {"dato": "precio"}})()
    trazas.registrar_traza("juli_k", "[juli_k] precio?", {"output": "Cuesta 59.990 CLP.",
                                                          "intermediate_steps": [(accion, "59.990 CLP")]},
                           archivo=archivo)
    trazas.registrar_traza("pepe", "[pepe] hola", {"output": "¡Hola!"}, archivo=archivo)  # sin pasos
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    primera, segunda = (json.loads(linea) for linea in lineas)
    assert primera["acciones"] == [{"herramienta": "consultar_campana", "argumentos": {"dato": "precio"},
                                    "observacion": "59.990 CLP"}]
    assert primera["filtro_actuo"] is False
    assert segunda["acciones"] == []
    assert "59.990" in lineas[0]  # ensure_ascii=False: legible


def test_una_falla_al_escribir_la_traza_no_tumba_el_bot(tmp_path):
    trazas.registrar_traza("juli_k", "x", {"output": "y"}, archivo=tmp_path / "no_existe" / "t.jsonl")


def registro(entrada, herramientas=(), filtro=False, error=None):
    r = {"timestamp": "2026-11-09T00:00:00", "session_id": "x", "entrada": entrada,
         "acciones": [{"herramienta": h} for h in herramientas], "filtro_actuo": filtro}
    if error:
        r["error"] = error
    return r


def test_revisar_trazas_marca_los_patrones_del_bloque_23():
    registros = [
        registro("normal", ["consultar_campana"]),
        registro("seguidas", ["consultar_campana", "consultar_campana"]),
        registro("no seguidas", ["consultar_campana", "registrar_interes_compra", "consultar_campana"]),
        registro("herramienta nueva sin clasificar", ["banear_viewer"]),
        registro("link inventado", ["consultar_campana"], filtro=True),
        registro("crítica", ["marcar_comentario_negativo"]),
        registro("falló", error="TimeoutError()"),
    ]
    hallazgos = trazas.revisar_trazas(registros)
    entradas = {clave: [r["entrada"] for r in lista] for clave, lista in hallazgos.items()}
    assert entradas["repeticiones"] == ["seguidas"]
    assert entradas["riesgo_alto"] == ["herramienta nueva sin clasificar"]
    assert entradas["filtro_actuo"] == ["link inventado"]
    assert entradas["comentarios_marcados"] == ["crítica"]
    assert entradas["errores"] == ["falló"]


def test_leer_trazas_salta_lineas_corruptas_y_tolera_archivo_inexistente(tmp_path, capsys):
    assert trazas.leer_trazas(tmp_path / "no_hay.jsonl") == []
    assert "No se encontró" in capsys.readouterr().out
    archivo = tmp_path / "t.jsonl"
    archivo.write_text('{"entrada": "ok"}\n{"entrada": "a medio escr\n\n', encoding="utf-8")
    assert trazas.leer_trazas(archivo) == [{"entrada": "ok"}]


# --- Integración: agente con memoria + traza ---


def test_un_comentario_negativo_queda_marcado_en_la_traza():
    modelo = ModeloFalso(responses=[
        llamada("marcar_comentario_negativo", usuario="troll99", mensaje="el K7 es una basura", motivo="calidad"),
        AIMessage(content="Gracias por tu opinión."),
    ])
    agente = mem.construir_agente_con_memoria(modelo)
    resultado = mem.procesar_mensaje_con_memoria(agente, "[troll99] el K7 es una basura")
    assert resultado["output"] == "Gracias por tu opinión."
    [traza] = trazas.leer_trazas()
    assert traza["session_id"] == "troll99"
    assert traza["acciones"][0]["argumentos"]["motivo"] == "calidad"
    assert trazas.revisar_trazas([traza])["comentarios_marcados"] == [traza]


def test_la_traza_guarda_el_link_inventado_y_el_publicado():
    modelo = ModeloFalso(responses=[AIMessage(content="Cómpralo en https://k7keyboard.com/comprar")])
    mem.procesar_mensaje_con_memoria(mem.construir_agente_con_memoria(modelo), "[ana] link?")
    [traza] = trazas.leer_trazas()
    assert traza["respuesta_modelo"] == "Cómpralo en https://k7keyboard.com/comprar"
    assert traza["respuesta_final"] == f"Cómpralo en {ag.LINK_OFICIAL}"
    assert trazas.revisar_trazas([traza])["filtro_actuo"] == [traza]


def test_un_turno_que_falla_tambien_queda_en_la_traza():
    class ModeloQueFalla(ModeloFalso):
        def _generate(self, *args, **kwargs):
            raise TimeoutError("503")

    agente = mem.construir_agente_con_memoria(ModeloQueFalla(responses=[AIMessage(content="x")]))
    resultado = mem.procesar_mensaje_con_memoria(agente, "[juli_k] precio?")
    assert resultado["output"] == ag.SIN_RESPUESTA
    [traza] = trazas.leer_trazas()
    assert "TimeoutError" in traza["error"]
