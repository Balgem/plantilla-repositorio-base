"""Pruebas unitarias de las métricas. No necesitan mocks: no tocan la red."""
import json

import pytest

import metricas
from metricas import (
    calcular_metricas,
    calcular_precision_cobertura_f1,
    contar_coincidencias,
    peores_casos,
    resumir_metricas,
)


def test_contar_coincidencias_no_cuenta_repeticiones_de_mas():
    # "el gato el gato" contra "el gato": como máximo un "el" y un "gato".
    assert contar_coincidencias(["el", "gato"], ["el", "gato", "el", "gato"]) == 2


def test_contar_coincidencias_toma_el_minimo_de_cada_palabra():
    referencia = ["el", "gato", "duerme", "en", "el", "sofá"]
    respuesta = ["el", "gato", "duerme", "en", "el", "sillón", "todo", "el", "día"]
    assert contar_coincidencias(referencia, respuesta) == 5


def test_ejemplo_calculado_a_mano():
    resultado = calcular_metricas("El gato duerme en el sofá.", "El gato duerme en el sillón todo el día.")
    assert resultado["precision"] == pytest.approx(5 / 9)
    assert resultado["cobertura"] == pytest.approx(5 / 6)
    assert resultado["f1"] == pytest.approx(2 / 3)


def test_textos_iguales_dan_todo_uno():
    assert calcular_metricas("No hay descuentos.", "no hay descuentos") == {"precision": 1.0, "cobertura": 1.0, "f1": 1.0}


def test_sin_palabras_en_comun_da_cero():
    assert calcular_metricas("hola mundo", "chao planeta")["f1"] == 0.0


@pytest.mark.parametrize("referencia, respuesta", [([], ["hola"]), (["hola"], []), ([], [])])
def test_lista_vacia_no_divide_por_cero(referencia, respuesta):
    assert calcular_precision_cobertura_f1(referencia, respuesta) == {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}


def test_precision_castiga_lo_que_sobra():
    resultado = calcular_metricas("No hay descuentos", "No hay descuentos, revisa el link para más detalles")
    assert resultado["cobertura"] == 1.0
    assert resultado["precision"] < 1.0


# Límites conocidos de la métrica (Bloque 16): estas pruebas documentan que existen.


def test_limite_sinonimo_baja_el_puntaje():
    assert calcular_metricas("El auto es veloz.", "El vehículo es rápido.")["f1"] == pytest.approx(0.5)


def test_limite_precio_equivocado_puntua_alto():
    resultado = calcular_metricas("El K7 cuesta 59.990 CLP", "El K7 cuesta 49.990 CLP")
    assert resultado["f1"] == pytest.approx(0.8)


def test_limite_negacion_ausente_puntua_casi_perfecto():
    resultado = calcular_metricas("Python no es un lenguaje compilado.", "Python es un lenguaje compilado.")
    assert resultado["precision"] == 1.0
    assert resultado["f1"] == pytest.approx(10 / 11)


def test_resumir_metricas_promedia():
    resultados = [{"precision": 0.8, "cobertura": 0.6, "f1": 0.7}, {"precision": 0.4, "cobertura": 0.2, "f1": 0.3}]
    resumen = resumir_metricas(resultados)
    assert resumen["precision_promedio"] == pytest.approx(0.6)
    assert resumen["cobertura_promedio"] == pytest.approx(0.4)
    assert resumen["f1_promedio"] == pytest.approx(0.5)


def test_resumir_metricas_sin_resultados():
    assert resumir_metricas([]) == {"precision_promedio": 0.0, "cobertura_promedio": 0.0, "f1_promedio": 0.0}


def test_peores_casos_ordena_por_f1():
    resultados = [{"consulta": "a", "f1": 0.77}, {"consulta": "b", "f1": 0.44}, {"consulta": "c", "f1": 0.62}]
    assert [r["consulta"] for r in peores_casos(resultados, 2)] == ["b", "c"]


def test_guardar_escribe_json_con_tildes(tmp_path, monkeypatch):
    archivo = tmp_path / "resultados.json"
    monkeypatch.setattr(metricas, "ARCHIVO_RESULTADOS", archivo)
    metricas.guardar([{"consulta": "¿envíos?", "precision": 1.0, "cobertura": 1.0, "f1": 1.0}])
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    assert datos["casos"][0]["consulta"] == "¿envíos?"
    assert datos["resumen"]["f1_promedio"] == 1.0
