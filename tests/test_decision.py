"""Bloque 30: evidencia, método de decisión y esqueleto del documento (sin API)."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import decision as d


def test_la_muestra_son_20_mensajes_5_por_categoria_de_la_chain():
    assert len(d.MUESTRA) == 20
    assert {c: sum(1 for _, e in d.MUESTRA if e == c) for c in d.CATEGORIAS_CHAIN} == dict.fromkeys(d.CATEGORIAS_CHAIN, 5)


@pytest.mark.parametrize("cruda, formato_ok, correcta", [
    ("spam", True, True),
    ("spam\n", True, True),            # un salto de línea final no es un problema de formato
    ("Spam", False, True),             # mayúscula: incumple el formato, pero el .lower() de la chain lo salva
    ("spam.", False, False),           # el punto ya no lo salva nada
    ("Categoría: spam", False, False),
    ("otro", True, False),             # formato bien, categoría equivocada
])
def test_revisar_salida(cruda, formato_ok, correcta):
    r = d.revisar_salida(cruda, "spam")
    assert (r["formato_ok"], r["correcta"]) == (formato_ok, correcta)


def test_medir_con_el_clasificador_actual_y_un_modelo_falso():
    salidas = ["pregunta_producto", "Interes_compra", "spam.", "otro"] * 5
    modelo = FakeListChatModel(responses=salidas)
    m = d.medir(d.clasificador_actual(modelo))
    assert m["muestra"] == 20
    assert m["formato_incumplido"] == 10          # "Interes_compra" y "spam." x5
    assert m["fuera_de_lista_aun_normalizando"] == 5  # "spam." x5


def test_una_excepcion_cuenta_como_incumplimiento():
    def falla(_):
        raise TimeoutError("503")
    m = d.medir(falla, muestra=[("hola", "otro")])
    assert m["formato_incumplido"] == 1 and m["filas"][0]["cruda"].startswith("<error")


def evidencia(formato_incumplido, ejemplos=25):
    return {"prompt_actual": {"muestra": 20, "formato_incumplido": formato_incumplido}, "ejemplos_etiquetados": ejemplos}


def test_las_respuestas_medibles_salen_de_la_evidencia():
    assert d.responder_preguntas(evidencia(3))["problema_de_formato_o_tono"][0] is True
    assert d.responder_preguntas(evidencia(2))["problema_de_formato_o_tono"][0] is False
    assert d.responder_preguntas(evidencia(0, 200))["dataset_grande_y_de_calidad"][0] is True
    assert all(isinstance(v, bool) and porque for v, porque in d.responder_preguntas(evidencia(5)).values())


def test_metodo_reporta_empates_y_rechaza_strings():
    caso2 = {"informacion_cambia_seguido": False, "problema_de_formato_o_tono": True, "dataset_grande_y_de_calidad": True,
             "presupuesto_limitado_o_iterar_rapido": False, "necesita_multiples_variantes": False}
    assert d.recomendar_estrategia(caso2) == ({"RAG": 0, "Fine-tuning completo": 3, "PEFT": 3},
                                             ["Fine-tuning completo", "PEFT"])
    with pytest.raises(TypeError):
        d.recomendar_estrategia({**caso2, "necesita_multiples_variantes": "no"})


def test_sensibilidad_del_caso_de_la_leccion():
    caso2 = {"informacion_cambia_seguido": False, "problema_de_formato_o_tono": True, "dataset_grande_y_de_calidad": True,
             "presupuesto_limitado_o_iterar_rapido": False, "necesita_multiples_variantes": False}
    assert all(cambia for *_, cambia in d.sensibilidad(caso2))  # en un empate, las 5 cambian el resultado


def test_esqueleto_con_y_sin_empate():
    con = d.generar_esqueleto_decision("P", {"RAG": 0, "PEFT": 3, "Fine-tuning completo": 3}, ["PEFT", "Fine-tuning completo"])
    sin = d.generar_esqueleto_decision("P", {"RAG": 5, "PEFT": 1, "Fine-tuning completo": 0}, ["RAG"])
    assert "**Empate entre: PEFT, Fine-tuning completo**" in con and "no resolvio el empate" in con
    assert "Empate" not in sin and "por que RAG" in sin
    for texto in (con, sin):
        assert [l for l in texto.splitlines() if l.startswith("## ")] == [
            "## 1. El problema", "## 2. Resultado del metodo de decision",
            "## 3. Tecnica elegida y por que", "## 4. Que necesitarias para ejecutarla"]


def test_el_esqueleto_no_pisa_el_documento_completado(tmp_path):
    doc = tmp_path / "decision.md"
    assert d.guardar_esqueleto("v1", doc) == doc
    doc.write_text("completado a mano", encoding="utf-8")
    otra = d.guardar_esqueleto("v2", doc)
    assert otra.name == "decision_esqueleto.md" and doc.read_text(encoding="utf-8") == "completado a mano"
