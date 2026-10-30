"""Pruebas unitarias del pipeline de texto. No necesitan mocks: no tocan la red."""
from collections import Counter

import pytest

from pipeline_texto import (
    comparar_antes_y_despues,
    coincidencia,
    limpiar_texto,
    procesar_texto,
    quitar_categoria,
    vectorizar,
)


def test_procesar_texto_normaliza_mayusculas_y_puntuacion():
    assert procesar_texto("El Cielo, es AZUL!") == ["el", "cielo", "es", "azul"]


def test_procesar_texto_solo_puntuacion_devuelve_lista_vacia():
    assert procesar_texto("¡¡¡...!!!") == []


def test_limpiar_texto_colapsa_espacios():
    assert limpiar_texto("  hola     mundo \n ") == "hola mundo"


def test_limpiar_texto_conserva_tildes_y_enie():
    assert limpiar_texto("¿Hacen envíos a Ñuñoa?") == "hacen envíos a ñuñoa"


def test_limpiar_texto_elimina_emojis():
    assert limpiar_texto("Cómpralo aquí 🛒⌨️🔥") == "cómpralo aquí"


def test_limpiar_texto_conserva_numeros_sin_puntos():
    # El punto de miles es puntuación: el precio queda como un solo número.
    assert limpiar_texto("Cuesta 59.990 CLP") == "cuesta 59990 clp"


def test_limpiar_texto_rechaza_lo_que_no_es_texto():
    with pytest.raises(TypeError, match="espera str"):
        limpiar_texto(None)


def test_vectorizar_cuenta_repeticiones():
    assert vectorizar(["el", "gato", "y", "el", "perro"]) == Counter({"el": 2, "gato": 1, "y": 1, "perro": 1})


def test_coincidencia_textos_iguales_es_total():
    assert coincidencia(["el", "cielo"], ["el", "cielo"]) == 1.0


def test_coincidencia_referencia_vacia_no_divide_por_cero():
    assert coincidencia([], ["hola"]) == 0.0


def test_coincidencia_no_distingue_el_orden():
    # Límite conocido de la métrica: mismas palabras, sentido opuesto.
    referencia = procesar_texto("El perro persiguió al gato.")
    respuesta = procesar_texto("El gato persiguió al perro.")
    assert coincidencia(referencia, respuesta) == 1.0


def test_pipeline_cambia_el_resultado_frente_al_texto_crudo():
    crudo, procesado = comparar_antes_y_despues("El cielo es azul.", "el cielo es azul")
    assert crudo == 0.5
    assert procesado == 1.0


def test_quitar_categoria_deja_solo_la_respuesta():
    assert quitar_categoria("pregunta_producto | Cuesta 59.990 CLP") == "Cuesta 59.990 CLP"
