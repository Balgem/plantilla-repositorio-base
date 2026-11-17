"""Bloque 29: dataset para PEFT del clasificador del chat (sin API)."""
import json

import pytest
from google.genai import types

import dataset_tuning as dt


def ej(texto, salida):
    return types.TuningExample(text_input=texto, output=salida if isinstance(salida, str) else json.dumps(salida))


# --- Lo que la actividad exige ---


def test_al_menos_10_ejemplos_y_mas_de_una_categoria():
    assert len(dt.EJEMPLOS_RAW) >= 10
    assert len(dt.chequear_balance(dt.EJEMPLOS_RAW)) > 1


def test_el_dataset_real_valida_sin_problemas():
    assert dt.validar_dataset(dt.construir_examples(dt.EJEMPLOS_RAW + dt.EJEMPLOS_PRUEBA)) == []


def test_balanceado_y_cubre_todas_las_categorias():
    balance = dt.chequear_balance(dt.EJEMPLOS_RAW)
    assert set(balance) == set(dt.CATEGORIAS)
    assert dt.razon_desbalance(balance) <= 1.5


def test_la_prueba_no_repite_el_entrenamiento():
    entrenamiento = {dt.normalizar(t) for t, _ in dt.EJEMPLOS_RAW}
    assert not any(dt.normalizar(t) in entrenamiento for t, _ in dt.EJEMPLOS_PRUEBA)


def test_los_outputs_son_json_con_comillas_dobles():
    for ejemplo in dt.construir_examples(dt.EJEMPLOS_RAW):
        assert isinstance(json.loads(ejemplo.output), dict)
        assert '"categoria"' in ejemplo.output  # json.dumps: comillas dobles, nunca el dict de Python con simples


def test_las_categorias_coinciden_con_la_chain():
    """Las 4 de la chain del Bloque 18 (+ el flag del Bloque 23): si la chain cambia, el dataset tiene que cambiar."""
    from cadena_tres_pasos import plantilla_clasificar
    for categoria in ("pregunta_producto", "interes_compra", "spam", "otro"):
        assert categoria in dt.CATEGORIAS and categoria in plantilla_clasificar.template


# --- El validador encuentra lo que dice encontrar ---


@pytest.mark.parametrize("ejemplo, problema", [
    (ej("", dt.salida("otro")), "text_input vacio"),
    (ej("hola", ""), "output vacio"),
    (ej("hola", "{'categoria': 'otro', 'responder': False}"), "no es JSON valido"),
    (ej("hola", '"categoria responder"'), "no es un objeto JSON"),
    (ej("hola", '["categoria", "responder"]'), "no es un objeto JSON"),
    (ej("hola", {"categoria": "otro"}), 'no tiene la clave "responder"'),
    (ej("hola", {"categoria": "otro", "responder": False, "motivo": "x"}), 'clave de más "motivo"'),
    (ej("hola", {"categoria": "interés_compra", "responder": True}), "categoria desconocida"),
    (ej("hola", {"categoria": "otro", "responder": "no"}), "debe ser true o false"),
    (ej("hola", {"categoria": "spam", "responder": True}), "no sigue la regla"),
])
def test_el_validador_detecta(ejemplo, problema):
    problemas = dt.validar_dataset([ejemplo])
    assert any(problema in p for p in problemas), problemas


def test_duplicado_y_contradiccion_aunque_cambien_mayusculas():
    problemas = dt.validar_dataset([
        ej("Lo quiero", dt.salida("interes_compra")),
        ej("lo   QUIERO", dt.salida("interes_compra")),
        ej("LO QUIERO", dt.salida("otro")),
    ])
    assert "duplicado" in problemas[0] and "contradicción" in problemas[1]


def test_reporta_todos_los_problemas_de_un_ejemplo():
    assert len(dt.validar_dataset([ej("", '{"categoria": "x"}')])) == 3  # vacío + falta responder + categoría
