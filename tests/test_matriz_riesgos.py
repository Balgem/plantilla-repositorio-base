"""Bloque 32, paso 3: matriz de riesgos (solo librería estándar)."""
import copy

import pytest

import matriz_riesgos as mr


@pytest.mark.parametrize("p, i, categoria", [(5, 5, "CRITICO"), (3, 5, "CRITICO"), (4, 4, "CRITICO"),
                                             (3, 3, "ALTO"), (2, 5, "ALTO"), (2, 4, "MEDIO"),
                                             (2, 2, "MEDIO"), (1, 4, "MEDIO"), (1, 3, "BAJO")])
def test_cortes_de_la_leccion(p, i, categoria):
    assert mr.categoria_riesgo(mr.puntaje_riesgo(p, i)) == categoria


def test_al_limite_marca_21_de_25_celdas():
    celdas = [(p, i) for p in range(1, 6) for i in range(1, 6)]
    assert sum(mr.esta_en_el_limite(p, i) for p, i in celdas) == 21
    assert not mr.esta_en_el_limite(1, 1) and not mr.esta_en_el_limite(5, 5)


def test_rango_de_categorias():
    assert mr.rango_categoria(3, 5) == ("ALTO", "CRITICO")    # PII de la lección: nunca baja de ALTO
    assert mr.rango_categoria(3, 2) == ("BAJO", "ALTO")
    assert mr.rango_categoria(1, 1) == ("BAJO", "BAJO")


def mi_matriz():
    return mr.completar(copy.deepcopy(mr.MIS_RIESGOS))


def test_prueba_5_y_las_reglas_de_la_actividad():
    riesgos = mi_matriz()
    assert mr.validar_matriz(riesgos) == []
    assert len(riesgos) >= 5
    assert any(r["categoria"] in ("ALTO", "CRITICO") for r in riesgos)
    assert all(r["supervision"] for r in riesgos if r["categoria"] in ("ALTO", "CRITICO"))
    assert sum("Bloque" in r["mitigacion"] for r in riesgos) >= 2
    assert len({r["categoria"] for r in riesgos}) >= 3          # no todo en la misma categoría


def test_prueba_6_filas_para_revisar_con_otra_persona():
    revisar = [r["riesgo"] for r in mi_matriz() if r["revisar"]]
    assert revisar and all(not r["supervision"] for r in mi_matriz() if r["revisar"])
    assert any("API key" in r for r in revisar)                 # 1×5: con P=2 sería ALTO y no tiene supervisión


def test_las_mitigaciones_reducen_respecto_del_inherente():
    for r in mi_matriz():
        assert mr.puntaje_riesgo(*r["inherente"]) >= r["puntaje"], r["riesgo"]


@pytest.mark.parametrize("cambio, mensaje", [
    (lambda rs: rs[0].update(supervision=""), "sin punto de supervisión"),
    (lambda rs: rs[0].update(probabilidad="4"), "entero de 1 a 5"),
    (lambda rs: rs[0].update(impacto=6), "entero de 1 a 5"),
    (lambda rs: rs[0].update(riesgo="seguridad"), "genérico"),
    (lambda rs: rs[0].pop("impacto"), "faltan las claves"),
    (lambda rs: [r.update(mitigacion="revisaremos") for r in rs], "menos de 2 mitigaciones"),
    (lambda rs: [r.update(probabilidad=1, impacto=1) for r in rs], "ningún riesgo ALTO"),
    (lambda rs: rs.__delitem__(slice(4, None)), "al menos 5"),
])
def test_validar_detecta_cada_problema(cambio, mensaje):
    riesgos = copy.deepcopy(mr.MIS_RIESGOS)
    cambio(riesgos)
    assert any(mensaje in p for p in mr.validar_matriz(riesgos))


def test_markdown_tiene_todas_las_filas_ordenadas():
    md = mr.a_markdown(mi_matriz())
    filas = [l for l in md.splitlines() if l.startswith("| ") and l[2].isdigit()]
    assert len(filas) == len(mr.MIS_RIESGOS)
    puntajes = [int(f.split("|")[5]) for f in filas]
    assert puntajes == sorted(puntajes, reverse=True)
