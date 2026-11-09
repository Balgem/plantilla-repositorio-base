"""Checklist de cierre del Bloque 22, con un modelo falso (no llama a la API)."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from pydantic import ValidationError

import agente_con_herramientas as ag
import agente_con_memoria as mem
from agente_con_herramientas import registrar_interes_compra
from agente_con_memoria import (
    construir_agente_con_memoria,
    obtener_historial,
    procesar_mensaje_con_memoria,
    usuario_de,
)


RECIBIDOS: list[list[str]] = []  # lo que le llegó al modelo en cada llamada


class ModeloFalso(FakeMessagesListChatModel):
    """Respuestas fijas en orden; anota en RECIBIDOS los mensajes de cada llamada para revisarlos."""

    def bind_tools(self, tools, **kwargs) -> Runnable:
        return self.bind()

    def _generate(self, messages, *args, **kwargs):
        RECIBIDOS.append([m.content for m in messages])
        return super()._generate(messages, *args, **kwargs)


def llamada(herramienta, **argumentos):
    return AIMessage(content="", tool_calls=[{"name": herramienta, "args": argumentos, "id": herramienta}])


@pytest.fixture(autouse=True)
def estado_limpio():
    mem.cerrar_todas()
    ag.REGISTRO_CRM.clear()
    RECIBIDOS.clear()
    yield


# --- 1. args_schema en la herramienta de compra ---


def test_registrar_tiene_descripcion_por_argumento():
    for argumento in ("usuario", "mensaje", "cantidad"):
        assert registrar_interes_compra.args[argumento].get("description")


def test_registrar_valida_la_cantidad():
    with pytest.raises(ValidationError):
        registrar_interes_compra.invoke({"usuario": "juli_k", "mensaje": "compro dos", "cantidad": "dos"})
    with pytest.raises(ValidationError):
        registrar_interes_compra.invoke({"usuario": "juli_k", "mensaje": "x", "cantidad": 0})


def test_la_cantidad_si_se_usa():
    registrar_interes_compra.invoke({"usuario": "juli_k", "mensaje": "compro 2", "cantidad": 2})
    assert ag.REGISTRO_CRM[0]["cantidad"] == 2  # un argumento validado que la función ignora no sirve


def test_repetir_lo_quiero_no_duplica_el_registro():
    registrar_interes_compra.invoke({"usuario": "juli_k", "mensaje": "lo quiero"})
    respuesta = registrar_interes_compra.invoke({"usuario": "juli_k", "mensaje": "compro 2", "cantidad": 2})
    assert len(ag.REGISTRO_CRM) == 1
    assert ag.REGISTRO_CRM[0]["cantidad"] == 2
    assert "ya estaba registrado" in respuesta


# --- 2. El prompt: chat_history antes del mensaje y agent_scratchpad después ---


def test_orden_de_los_placeholders():
    nombres = [getattr(m, "variable_name", None) or type(m).__name__ for m in mem.prompt_con_memoria.messages]
    assert nombres.index("chat_history") < nombres.index("HumanMessagePromptTemplate") < nombres.index("agent_scratchpad")


# --- 3. Dos turnos con la misma sesión ---


def test_el_segundo_turno_recibe_el_primero():
    modelo = ModeloFalso(responses=[AIMessage(content="Cuesta 59.990 CLP."), AIMessage(content="Dos serían 119.980 CLP.")])
    agente = construir_agente_con_memoria(modelo)
    procesar_mensaje_con_memoria(agente, "[juli_k] cuánto cuesta?")
    resultado = procesar_mensaje_con_memoria(agente, "[juli_k] y si compro 2?")
    assert resultado["output"] == "Dos serían 119.980 CLP."
    segunda_llamada = " ".join(map(str, RECIBIDOS[1]))
    assert "cuánto cuesta?" in segunda_llamada and "59.990" in segunda_llamada  # el historial viajó
    assert len(obtener_historial("juli_k").messages) == 4


# --- 4. Dos sesiones no se mezclan ---


def test_dos_viewers_no_comparten_historial():
    modelo = ModeloFalso(responses=[AIMessage(content="Cuesta 59.990 CLP."), AIMessage(content="No sé de qué teclado.")])
    agente = construir_agente_con_memoria(modelo)
    procesar_mensaje_con_memoria(agente, "[juli_k] cuánto cuesta el K7?")
    procesar_mensaje_con_memoria(agente, "[ana_gamer] de qué teclado me hablaste?")
    llamada_de_ana = " ".join(map(str, RECIBIDOS[1]))
    assert "juli_k" not in llamada_de_ana and "59.990" not in llamada_de_ana  # nada de juli_k le llega a ana
    assert len(obtener_historial("juli_k").messages) == 2
    assert len(obtener_historial("ana_gamer").messages) == 2


# --- Lo que agrega el bot respecto de la lección ---


def test_el_historial_no_crece_sin_limite():
    respuestas = [AIMessage(content=f"respuesta {i}") for i in range(10)]
    agente = construir_agente_con_memoria(ModeloFalso(responses=respuestas))
    for i in range(10):
        procesar_mensaje_con_memoria(agente, f"[juli_k] mensaje {i}")
    historial = obtener_historial("juli_k").messages
    assert len(historial) == mem.MAX_MENSAJES
    assert historial[-1].content == "respuesta 9"  # se conservan los más recientes


def test_la_sesion_sale_del_nombre_entre_corchetes():
    assert usuario_de("[Juli_K] hola") == "juli_k"
    assert usuario_de("hola sin nombre") is None


def test_sin_nombre_de_usuario_no_responde_ni_llama_al_modelo():
    modelo = ModeloFalso(responses=[AIMessage(content="no debería usarse")])
    resultado = procesar_mensaje_con_memoria(construir_agente_con_memoria(modelo), "mensaje sin usuario")
    assert resultado["output"] == ag.SIN_RESPUESTA
    assert RECIBIDOS == []


def test_cerrar_sesion_borra_el_historial():
    obtener_historial("juli_k").add_user_message("hola")
    mem.cerrar_sesion("juli_k")
    mem.cerrar_sesion("juli_k")  # no falla si ya no existe
    assert "juli_k" not in mem.historiales


def test_la_salida_pasa_por_el_filtro_de_promesas():
    modelo = ModeloFalso(responses=[AIMessage(content="Cuesta 59.990 CLP. ¡Unidades limitadas!")])
    resultado = procesar_mensaje_con_memoria(construir_agente_con_memoria(modelo), "[ana] precio?")
    assert resultado["output"] == "Cuesta 59.990 CLP."


def test_una_compra_con_memoria_usa_la_herramienta_con_cantidad():
    modelo = ModeloFalso(responses=[
        AIMessage(content="Cuesta 59.990 CLP."),
        llamada("registrar_interes_compra", usuario="juli_k", mensaje="y si compro 2?", cantidad=2),
        AIMessage(content="Te anoté para 2 unidades."),
    ])
    agente = construir_agente_con_memoria(modelo)
    procesar_mensaje_con_memoria(agente, "[juli_k] cuánto cuesta?")
    resultado = procesar_mensaje_con_memoria(agente, "[juli_k] y si compro 2?")
    assert ag.REGISTRO_CRM[0]["cantidad"] == 2
    assert resultado["intermediate_steps"][0][0].tool == "registrar_interes_compra"


def test_respuesta_en_bloques_de_gemini_se_guarda_como_texto():
    """Gemini 3.x responde con bloques + signature; guardarlos así rompía el segundo turno."""
    bloques = [{"type": "text", "text": "Cuesta 59.990 CLP.", "index": 0, "extras": {"signature": "abc"}}]
    modelo = ModeloFalso(responses=[AIMessage(content=bloques), AIMessage(content="Dos serían 119.980 CLP.")])
    agente = construir_agente_con_memoria(modelo)
    procesar_mensaje_con_memoria(agente, "[juli_k] cuánto cuesta?")
    assert obtener_historial("juli_k").messages[1].content == "Cuesta 59.990 CLP."
    resultado = procesar_mensaje_con_memoria(agente, "[juli_k] y si compro 2?")
    assert resultado["output"] == "Dos serían 119.980 CLP."  # el segundo turno ya no falla
    assert len(obtener_historial("juli_k").messages) == 4


def test_la_memoria_no_guarda_promesas_inventadas():
    modelo = ModeloFalso(responses=[AIMessage(content="Cuesta 59.990 CLP. ¡Unidades limitadas!")])
    procesar_mensaje_con_memoria(construir_agente_con_memoria(modelo), "[ana] precio?")
    assert "limitadas" not in obtener_historial("ana").messages[1].content


def test_el_link_inventado_se_corrige_y_no_queda_en_la_memoria():
    """Caso real de la prueba manual: el modelo inventó teclado-k7-campana.com."""
    modelo = ModeloFalso(responses=[AIMessage(content="Puedes comprarlo aquí: https://teclado-k7-campana.com/comprar")])
    resultado = procesar_mensaje_con_memoria(construir_agente_con_memoria(modelo), "[juli_k] dónde compro?")
    assert resultado["output"] == f"Puedes comprarlo aquí: {ag.LINK_OFICIAL}"
    assert "teclado-k7-campana" not in obtener_historial("juli_k").messages[1].content


def test_el_link_oficial_no_se_toca():
    texto = f"El link es {ag.LINK_OFICIAL}. ¡Saludos!"
    assert ag.corregir_links(texto) == texto


def test_link_inventado_con_punto_final():
    assert ag.corregir_links("Compra en https://otro.cl/k7.") == f"Compra en {ag.LINK_OFICIAL}."
