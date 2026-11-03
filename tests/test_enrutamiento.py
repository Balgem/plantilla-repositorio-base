"""Pruebas del enrutamiento: cada ruta se fuerza con una clasificación falsa. No llaman a la API."""
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from cadena_tres_pasos import SIN_RESPUESTA
from enrutamiento import (
    construir_cadena,
    construir_cadena_con_enrutamiento,
    construir_paso_clasificacion,
    plantilla_compra,
    plantilla_pregunta,
)


def clasificacion_que_devuelve(categoria):
    return MagicMock(return_value=categoria)


def ruta_falsa(respuesta):
    return MagicMock(return_value=respuesta)


def test_pregunta_va_a_la_ruta_de_pregunta():
    ruta_pregunta, ruta_compra = ruta_falsa("respuesta con datos"), ruta_falsa("no debería usarse")
    cadena = construir_cadena_con_enrutamiento(
        clasificacion_que_devuelve("pregunta_producto"), ruta_pregunta=ruta_pregunta, ruta_compra=ruta_compra
    )
    assert cadena.invoke({"mensaje": "es inalámbrico?"}) == "respuesta con datos"
    assert ruta_pregunta.called and not ruta_compra.called


def test_interes_de_compra_va_a_la_ruta_de_compra():
    ruta_pregunta, ruta_compra = ruta_falsa("no debería usarse"), ruta_falsa("precio y link")
    cadena = construir_cadena_con_enrutamiento(
        clasificacion_que_devuelve("interes_compra"), ruta_pregunta=ruta_pregunta, ruta_compra=ruta_compra
    )
    assert cadena.invoke({"mensaje": "lo quiero!!"}) == "precio y link"
    assert ruta_compra.called and not ruta_pregunta.called


def test_spam_no_responde_ni_usa_las_rutas():
    ruta_pregunta, ruta_compra = ruta_falsa("x"), ruta_falsa("x")
    cadena = construir_cadena_con_enrutamiento(
        clasificacion_que_devuelve("spam"), ruta_pregunta=ruta_pregunta, ruta_compra=ruta_compra
    )
    assert cadena.invoke({"mensaje": "SIGAN MI CANAL"}) == SIN_RESPUESTA
    assert not ruta_pregunta.called and not ruta_compra.called


def test_categoria_desconocida_cae_en_la_ruta_por_defecto_sin_responder():
    ruta_pregunta, ruta_compra = ruta_falsa("x"), ruta_falsa("x")
    cadena = construir_cadena_con_enrutamiento(
        clasificacion_que_devuelve("no estoy seguro"), ruta_pregunta=ruta_pregunta, ruta_compra=ruta_compra
    )
    assert cadena.invoke({"mensaje": "mensaje ambiguo"}) == SIN_RESPUESTA
    assert not ruta_pregunta.called and not ruta_compra.called


def test_las_rutas_reciben_el_mensaje_original_y_la_campana():
    ruta_pregunta = ruta_falsa("ok")
    cadena = construir_cadena_con_enrutamiento(clasificacion_que_devuelve("pregunta_producto"), ruta_pregunta=ruta_pregunta)
    cadena.invoke({"mensaje": "es inalámbrico?"})
    entrada = ruta_pregunta.call_args.args[0]
    assert entrada["mensaje"] == "es inalámbrico?"
    assert entrada["categoria"] == "pregunta_producto"
    assert "59.990" in entrada["campana"]


def test_clasificacion_normaliza_antes_de_comparar():
    modelo = MagicMock(return_value=AIMessage(content=" Interes_Compra \n"))
    assert construir_paso_clasificacion(modelo).invoke({"mensaje": "lo quiero"}) == "interes_compra"


def test_spam_completo_llama_al_modelo_una_sola_vez():
    modelo = MagicMock(side_effect=[AIMessage(content="spam")])
    assert construir_cadena(modelo).invoke({"mensaje": "SIGAN MI CANAL"}) == SIN_RESPUESTA
    assert modelo.call_count == 1  # solo la clasificación: ni redactor ni revisor


def test_pregunta_completa_clasifica_redacta_y_revisa():
    modelo = MagicMock(side_effect=[
        AIMessage(content="pregunta_producto"),
        AIMessage(content="borrador"),
        AIMessage(content="No tengo esa información, revisa el link"),
    ])
    assert construir_cadena(modelo).invoke({"mensaje": "es inalámbrico?"}) == "No tengo esa información, revisa el link"
    assert modelo.call_count == 3


def test_cada_ruta_tiene_un_prompt_distinto():
    assert plantilla_pregunta.template != plantilla_compra.template
