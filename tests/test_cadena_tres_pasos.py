"""Pruebas de la chain de tres pasos con un modelo falso: no llaman a la API."""
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from cadena_tres_pasos import DATOS_CAMPANA, SIN_RESPUESTA, construir_cadena


def modelo_falso(*respuestas):
    """Simula el modelo: devuelve una respuesta distinta en cada llamada, en orden."""
    modelo = MagicMock()
    modelo.side_effect = [AIMessage(content=texto) for texto in respuestas]
    return modelo


def texto_del_prompt(llamada):
    """El texto que recibió el modelo en una llamada (un prompt ya armado por la plantilla)."""
    return llamada.args[0].to_string()


def test_cadena_conecta_los_tres_pasos():
    modelo = modelo_falso("pregunta_producto", "El K7 cuesta 59.990 CLP", "El K7 cuesta 59.990 CLP 🛒")
    resultado = construir_cadena(modelo).invoke({"mensaje": "cuánto cuesta?"})
    assert modelo.call_count == 3
    assert resultado == "El K7 cuesta 59.990 CLP 🛒"


def test_el_redactor_recibe_la_categoria_y_el_mensaje():
    modelo = modelo_falso("  Interes_Compra \n", "borrador", "final")
    construir_cadena(modelo).invoke({"mensaje": "lo quiero!!"})
    prompt_redactar = texto_del_prompt(modelo.call_args_list[1])
    assert "clasificó como: interes_compra" in prompt_redactar  # la categoría llega limpia
    assert "lo quiero!!" in prompt_redactar                       # y el mensaje original no se pierde


def test_el_revisor_recibe_el_borrador_y_los_datos_de_la_campana():
    modelo = modelo_falso("pregunta_producto", "Hay un 20% de descuento", "No hay descuentos")
    construir_cadena(modelo).invoke({"mensaje": "tiene descuento?"})
    prompt_revisar = texto_del_prompt(modelo.call_args_list[2])
    assert "Borrador: Hay un 20% de descuento" in prompt_revisar
    assert DATOS_CAMPANA in prompt_revisar


def test_la_salida_final_es_la_del_revisor_no_la_del_borrador():
    modelo = modelo_falso("pregunta_producto", "Cuesta 49.990 CLP", "Cuesta 59.990 CLP")
    assert construir_cadena(modelo).invoke({"mensaje": "precio?"}) == "Cuesta 59.990 CLP"


def test_spam_termina_sin_respuesta():
    modelo = modelo_falso("spam", SIN_RESPUESTA, SIN_RESPUESTA)
    assert construir_cadena(modelo).invoke({"mensaje": "SIGAN MI CANAL"}) == SIN_RESPUESTA


def test_sin_mensaje_falla_antes_de_llamar_al_modelo():
    modelo = modelo_falso("no debería usarse")
    with pytest.raises(KeyError):
        construir_cadena(modelo).invoke({"texto": "clave equivocada"})
    assert modelo.call_count == 0
