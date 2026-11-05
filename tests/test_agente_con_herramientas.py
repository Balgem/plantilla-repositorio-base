"""Pruebas del agente con un modelo falso (no llaman a la API) y de cada herramienta por separado."""
import logging

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

import agente_con_herramientas as ag
from agente_con_herramientas import (
    construir_agente,
    consultar_campana,
    procesar_mensaje_agente,
    quitar_promesas_inventadas,
    texto_de_salida,
    consultar_viewers,
    herramientas_usadas,
    registrar_interes_compra,
)


class ModeloFalso(FakeMessagesListChatModel):
    """Devuelve respuestas fijas en orden. bind_tools no enlaza nada: las herramientas las ejecuta AgentExecutor.

    La anotación -> Runnable es necesaria para que with_fallbacks también enlace las herramientas al respaldo.
    """

    def bind_tools(self, tools, **kwargs) -> Runnable:
        return self.bind()


class ModeloCaido(ModeloFalso):
    """Simula el 503 de Gemini en cada llamada."""

    def _generate(self, *args, **kwargs):
        raise ConnectionError("503 UNAVAILABLE simulado")

    def _stream(self, *args, **kwargs):
        raise ConnectionError("503 UNAVAILABLE simulado")


def llamada(herramienta, **argumentos):
    return AIMessage(content="", tool_calls=[{"name": herramienta, "args": argumentos, "id": herramienta}])


@pytest.fixture(autouse=True)
def crm_vacio():
    ag.REGISTRO_CRM.clear()
    yield


# --- Herramientas por separado ---


def test_consultar_campana_devuelve_el_precio():
    assert "59.990" in consultar_campana.invoke({"dato": "¿Cuál es el PRECIO?"})


def test_consultar_campana_no_inventa_lo_que_no_esta():
    assert "no está en la campaña" in consultar_campana.invoke({"dato": "es inalámbrico?"})


def test_consultar_viewers_no_pide_argumentos():
    assert consultar_viewers.args == {}  # el modelo no puede inventar un canal
    assert "1200" in consultar_viewers.invoke({})


def test_consultar_viewers_maneja_que_no_haya_datos(monkeypatch):
    monkeypatch.setattr(ag, "VIEWERS_SIMULADOS", {})
    assert "No se pudo" in consultar_viewers.invoke({})


def test_registrar_interes_compra_guarda_en_el_crm():
    respuesta = registrar_interes_compra.invoke({"usuario": "juli_k", "mensaje": "lo quiero"})
    assert "registrado" in respuesta
    assert ag.REGISTRO_CRM[0]["usuario"] == "juli_k"


@pytest.mark.parametrize("herramienta", ag.HERRAMIENTAS)
def test_cada_herramienta_explica_cuando_usarla(herramienta):
    assert "usar" in herramienta.description.lower()  # el docstring dice cuándo usarla, no cómo está hecha


# --- El agente (decisiones simuladas con el modelo falso) ---


def test_agente_usa_consultar_campana_para_el_precio():
    modelo = ModeloFalso(responses=[llamada("consultar_campana", dato="precio"), AIMessage(content="Cuesta 59.990 CLP.")])
    resultado = construir_agente(modelo).invoke({"entrada": "[ana] cuánto cuesta?"})
    assert herramientas_usadas(resultado) == ["consultar_campana"]
    assert "59.990" in resultado["intermediate_steps"][0][1]  # la observación trae el dato oficial


def test_agente_usa_consultar_viewers():
    modelo = ModeloFalso(responses=[llamada("consultar_viewers"), AIMessage(content="Hay 1200 personas.")])
    resultado = construir_agente(modelo).invoke({"entrada": "[pedro] cuánta gente hay?"})
    assert herramientas_usadas(resultado) == ["consultar_viewers"]


def test_agente_encadena_registro_y_link_para_un_interes_de_compra():
    modelo = ModeloFalso(responses=[
        llamada("registrar_interes_compra", usuario="juli_k", mensaje="lo quiero"),
        llamada("consultar_campana", dato="link"),
        AIMessage(content="¡Genial! Cómpralo en https://ejemplo.cl/r/k7"),
    ])
    resultado = construir_agente(modelo).invoke({"entrada": "[juli_k] lo quiero!!"})
    assert herramientas_usadas(resultado) == ["registrar_interes_compra", "consultar_campana"]
    assert len(ag.REGISTRO_CRM) == 1


def test_agente_no_usa_herramientas_para_un_mensaje_general():
    modelo = ModeloFalso(responses=[AIMessage(content="¡Qué buena jugada!")])
    resultado = construir_agente(modelo).invoke({"entrada": "[tomas] jajaja"})
    assert resultado["intermediate_steps"] == []
    assert ag.REGISTRO_CRM == []


def test_agente_se_corta_si_entra_en_un_bucle():
    modelo = ModeloFalso(responses=[llamada("consultar_viewers")] * 10)
    resultado = construir_agente(modelo).invoke({"entrada": "[x] ?"})
    assert len(resultado["intermediate_steps"]) == 5  # max_iterations=5
    assert "max iterations" in resultado["output"].lower()


# --- Manejo de errores (Bloque 20 aplicado al agente) ---


def test_si_el_modelo_principal_falla_responde_el_de_respaldo(caplog):
    respaldo = ModeloFalso(responses=[llamada("consultar_campana", dato="precio"), AIMessage(content="Cuesta 59.990 CLP.")])
    with caplog.at_level(logging.WARNING):
        resultado = construir_agente(ModeloCaido(responses=[]), modelo_secundario=respaldo).invoke({"entrada": "[ana] precio?"})
    assert resultado["output"] == "Cuesta 59.990 CLP."
    assert herramientas_usadas(resultado) == ["consultar_campana"]
    assert "Falló una llamada al modelo" in caplog.text  # el respaldo no oculta la falla


def test_si_fallan_los_dos_modelos_el_bot_no_responde_y_registra_el_error(caplog):
    ejecutor = construir_agente(ModeloCaido(responses=[]), modelo_secundario=ModeloCaido(responses=[]))
    with caplog.at_level(logging.ERROR):
        resultado = procesar_mensaje_agente(ejecutor, "[ana] precio?")
    assert resultado["output"] == ag.SIN_RESPUESTA
    assert "El agente no pudo procesar" in caplog.text


# --- Formato de la respuesta ---


def test_texto_de_salida_junta_los_bloques_de_gemini():
    bloques = [{"type": "text", "text": "Cuesta 59.990 CLP.", "index": 0, "extras": {"signature": "abc"}}]
    assert texto_de_salida(bloques) == "Cuesta 59.990 CLP."
    assert texto_de_salida("ya es texto") == "ya es texto"


def test_procesar_mensaje_agente_devuelve_texto_plano():
    modelo = ModeloFalso(responses=[AIMessage(content=[{"type": "text", "text": "¡Qué jugada!", "extras": {}}])])
    resultado = procesar_mensaje_agente(construir_agente(modelo), "[tomas] jajaja")
    assert resultado["output"] == "¡Qué jugada!"


def test_el_prompt_prohibe_promociones_inventadas():
    instrucciones = ag.prompt_agente.messages[0].prompt.template
    assert "unidades limitadas" in instrucciones


# --- Chequeo determinista de promesas inventadas ---


def test_quita_la_promesa_que_invento_el_modelo_en_la_prueba_manual(caplog):
    with caplog.at_level(logging.WARNING):
        texto = quitar_promesas_inventadas("El teclado mecánico K7 cuesta 59.990 CLP. ¡Unidades limitadas!")
    assert texto == "El teclado mecánico K7 cuesta 59.990 CLP."
    assert "Unidades limitadas" in caplog.text  # queda registrado qué se quitó


@pytest.mark.parametrize("promesa", ["¡Envío gratis!", "Oferta por tiempo limitado.", "Quedan pocas en stock."])
def test_quita_otras_promesas(promesa):
    assert quitar_promesas_inventadas(f"Cuesta 59.990 CLP. {promesa}") == "Cuesta 59.990 CLP."


def test_no_toca_una_respuesta_correcta(caplog):
    texto = "No hay descuentos. Cómpralo en https://ejemplo.cl/r/k7"
    with caplog.at_level(logging.WARNING):
        assert quitar_promesas_inventadas(texto) == texto
    assert caplog.text == ""


def test_si_toda_la_respuesta_es_una_promesa_el_bot_no_responde():
    assert quitar_promesas_inventadas("¡Envío gratis a todo Chile!") == ag.SIN_RESPUESTA


def test_procesar_mensaje_agente_aplica_el_filtro():
    modelo = ModeloFalso(responses=[AIMessage(content="Cuesta 59.990 CLP. ¡Unidades limitadas!")])
    assert procesar_mensaje_agente(construir_agente(modelo), "[ana] precio?")["output"] == "Cuesta 59.990 CLP."
