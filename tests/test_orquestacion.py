"""Verificación de extremo a extremo del flujo orquestado (checklist del Bloque 20).

El camino exitoso de cada ruta, la ruta por defecto y la normalización están en tests/test_enrutamiento.py.
Aquí se prueban los fallos: cada uno debe terminar en una respuesta razonable, nunca en una excepción.
"""
import logging
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from cadena_tres_pasos import SIN_RESPUESTA
from enrutamiento import (
    LINK,
    RESPALDO_COMPRA,
    RESPALDO_PREGUNTA,
    construir_cadena,
    construir_cadena_con_enrutamiento,
    construir_ruta_segura,
    procesar_mensaje_seguro,
)


def fallar_a_proposito(_):
    raise ConnectionError("Error de red simulado")


ruta_rota = RunnableLambda(fallar_a_proposito)


# --- Fallbacks por ruta ---


def test_ruta_compra_usa_fallback_ante_fallo_del_modelo():
    resultado = construir_ruta_segura(ruta_rota, RESPALDO_COMPRA).invoke({"mensaje": "lo quiero"})
    assert resultado == RESPALDO_COMPRA
    assert "59.990" in resultado and LINK in resultado  # respuesta útil y verdadera, no un "error"


def test_ruta_pregunta_usa_fallback_ante_fallo_del_modelo():
    resultado = construir_ruta_segura(ruta_rota, RESPALDO_PREGUNTA).invoke({"mensaje": "es inalámbrico?"})
    assert resultado == RESPALDO_PREGUNTA and LINK in resultado


def test_fallback_prueba_el_modelo_secundario_antes_del_texto_fijo():
    ruta_secundaria = RunnableLambda(lambda _: "respuesta del modelo secundario")
    resultado = construir_ruta_segura(ruta_rota, RESPALDO_COMPRA, ruta_secundaria).invoke({"mensaje": "lo quiero"})
    assert resultado == "respuesta del modelo secundario"


def test_si_fallan_los_dos_modelos_queda_el_texto_fijo():
    resultado = construir_ruta_segura(ruta_rota, RESPALDO_COMPRA, RunnableLambda(fallar_a_proposito)).invoke(
        {"mensaje": "lo quiero"}
    )
    assert resultado == RESPALDO_COMPRA


def test_si_falla_el_revisor_no_se_publica_el_borrador():
    modelo = MagicMock(side_effect=[
        AIMessage(content="pregunta_producto"),            # clasificar
        AIMessage(content="Hay un 20% de descuento"),      # redactar: borrador con un dato inventado
        ConnectionError("el revisor no responde"),         # revisar: falla
    ])
    resultado = construir_cadena(modelo).invoke({"mensaje": "tiene descuento?"})
    assert resultado == RESPALDO_PREGUNTA
    assert "descuento" not in resultado


def test_flujo_completo_pasa_al_modelo_secundario_si_el_principal_falla():
    principal = MagicMock(side_effect=ConnectionError("modelo principal caído"))
    secundario = MagicMock(side_effect=[
        AIMessage(content="interes_compra"), AIMessage(content="borrador"), AIMessage(content="Cómpralo aquí"),
    ])
    resultado = construir_cadena(principal, modelo_secundario=secundario).invoke({"mensaje": "lo quiero"})
    assert resultado == "Cómpralo aquí"
    assert secundario.call_count == 3


# --- try/except general ---


def test_procesar_mensaje_seguro_no_propaga_excepciones():
    clasificacion_rota = MagicMock(side_effect=ConnectionError("simulado"))
    cadena = construir_cadena_con_enrutamiento(paso_clasificacion=clasificacion_rota)
    assert procesar_mensaje_seguro(cadena, "mensaje de prueba") == SIN_RESPUESTA


def test_procesar_mensaje_seguro_registra_el_error(caplog):
    clasificacion_rota = MagicMock(side_effect=ConnectionError("Error de red simulado"))
    cadena = construir_cadena_con_enrutamiento(paso_clasificacion=clasificacion_rota)
    with caplog.at_level(logging.ERROR):
        procesar_mensaje_seguro(cadena, "mensaje de prueba")
    assert "Error procesando el mensaje" in caplog.text
    assert "Error de red simulado" in caplog.text  # el error no se oculta: queda registrado con su causa


def test_procesar_mensaje_seguro_devuelve_la_respuesta_normal_si_nada_falla():
    cadena = construir_cadena_con_enrutamiento(
        MagicMock(return_value="interes_compra"), ruta_compra=RunnableLambda(lambda _: "Cómpralo aquí")
    )
    assert procesar_mensaje_seguro(cadena, "lo quiero") == "Cómpralo aquí"


def test_mensaje_vacio_no_llama_al_modelo():
    modelo = MagicMock()
    for mensaje in ["", "   ", None]:
        assert procesar_mensaje_seguro(construir_cadena(modelo), mensaje) == SIN_RESPUESTA
    modelo.assert_not_called()


# --- Los respaldos no ocultan el problema ---


def test_usar_un_respaldo_queda_registrado(caplog):
    with caplog.at_level(logging.WARNING):
        construir_ruta_segura(ruta_rota, RESPALDO_COMPRA).invoke({"mensaje": "lo quiero"})
    assert "se usa el respaldo: respuesta fija" in caplog.text


def test_el_camino_normal_no_registra_avisos(caplog):
    ruta_sana = RunnableLambda(lambda _: "Cómpralo aquí")
    with caplog.at_level(logging.WARNING):
        construir_ruta_segura(ruta_sana, RESPALDO_COMPRA).invoke({"mensaje": "lo quiero"})
    assert caplog.text == ""
