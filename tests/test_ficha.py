"""Pruebas de la ficha de diseño funcional y del presupuesto de alcance (Bloque 33)."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ), str(RAIZ / "src")]

import crear_ficha  # noqa: E402
import presupuesto_alcance as pa  # noqa: E402
import verificar_ficha  # noqa: E402

FICHA = (RAIZ / "docs" / "ficha_diseno_funcional.md").read_text(encoding="utf-8")


def test_el_esqueleto_no_pasa():
    errores, _ = verificar_ficha.verificar(crear_ficha.ESQUELETO, RAIZ)
    assert len(errores) == 3


def test_la_ficha_del_proyecto_pasa_sin_avisos():
    assert verificar_ficha.verificar(FICHA, RAIZ) == ([], [])


def test_rnf_sin_numero_es_error():
    ficha = FICHA.replace("- RNF-05: Cuesta menos de 0,50 USD por cada 1.000 respuestas.", "- RNF-05: Es barato.")
    errores, _ = verificar_ficha.verificar(ficha, RAIZ)
    assert any("RNF-05" in e for e in errores)


def test_un_rf_en_dos_cajones_es_error():
    ficha = FICHA.replace("Deseable: RF-04,", "Deseable: RF-01, RF-04,")
    errores, _ = verificar_ficha.verificar(ficha, RAIZ)
    assert any("RF-01" in e and "exactamente un cajon" in e for e in errores)


def test_nombrar_la_solucion_en_el_problema_da_aviso():
    ficha = FICHA.replace("no puede medir su impacto", "no tiene un chatbot y no puede medir su impacto")
    _, avisos = verificar_ficha.verificar(ficha, RAIZ)
    assert avisos


def test_diagrama_inexistente_es_error():
    ficha = FICHA.replace("docs/diagrama_arquitectura.png", "docs/no_existe.png")
    errores, _ = verificar_ficha.verificar(ficha, RAIZ)
    assert any("no existe" in e for e in errores)


def test_con_30_horas_entran_las_tres_capas():
    dentro, _, usado = pa.recortar(pa.FUNCIONALIDADES, 30)
    assert pa.CAPAS_OBLIGATORIAS <= {f["capa"] for f in dentro}
    assert usado <= pa.presupuesto(30)


def test_si_falta_un_imprescindible_no_entran_deseables():
    dentro, fuera, _ = pa.recortar(pa.FUNCIONALIDADES, 20)
    assert all(f["tipo"] == "imprescindible" for f in dentro)
    assert ("RNF-03", "no cabe en el presupuesto") in [(f["id"], m) for f, m in fuera]


def test_el_alcance_de_la_ficha_coincide_con_el_presupuesto():
    imprescindibles = {f["id"] for f in pa.FUNCIONALIDADES if f["tipo"] == "imprescindible" and f["id"].startswith("RF")}
    assert "Imprescindible: " + ", ".join(sorted(imprescindibles)) in FICHA
