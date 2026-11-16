"""Bloque 27: métricas de recuperación y conjunto de evaluación (sin API)."""
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

import evaluacion_recuperacion as ev
import indexar_corpus as ic


class RetrieverFijo:
    """Devuelve ids fijos por pregunta, como si ya hubiera buscado (para probar la lógica sin API)."""

    def __init__(self, respuestas):
        self.respuestas = respuestas

    def invoke(self, pregunta):
        return [Document(page_content="x", id=i) for i in self.respuestas[pregunta]]


# --- El conjunto de evaluación ---


def test_entre_8_y_15_preguntas_y_algunas_sin_respuesta():
    assert 8 <= len(ev.CASOS_EVALUACION) <= 15
    assert any(not c["ids_relevantes"] for c in ev.CASOS_EVALUACION)


def test_cada_etiqueta_existe_en_el_indice():
    """Si cambia el chunking, los ids cambian: esta prueba obliga a volver a etiquetar."""
    ids = {f"{c.metadata['fuente']}#{c.metadata['chunk']}" for c in ic.partir_en_chunks(ic.cargar_corpus())}
    for caso in ev.CASOS_EVALUACION:
        assert caso["ids_relevantes"] <= ids, caso["pregunta"]


def test_las_etiquetas_son_conjuntos_y_las_preguntas_no_se_repiten():
    assert all(isinstance(c["ids_relevantes"], set) for c in ev.CASOS_EVALUACION)  # no "doc0" suelto
    preguntas = [c["pregunta"] for c in ev.CASOS_EVALUACION]
    assert len(preguntas) == len(set(preguntas))


def test_el_conjunto_cubre_todos_los_archivos_del_corpus():
    archivos = {d.metadata["fuente"] for d in ic.cargar_corpus()}
    etiquetados = {i.split("#")[0] for c in ev.CASOS_EVALUACION for i in c["ids_relevantes"]}
    assert etiquetados == archivos


# --- Métricas ---


def test_metricas_casos_borde():
    assert ev.precision_at_k([], {"a"}) == 0.0
    assert ev.recall_at_k(["a"], set()) is None
    assert ev.promediar([None, None]) == 0.0
    assert ev.promediar([1.0, None, 0.0]) == 0.5


def test_ejemplo_de_la_leccion():
    assert ev.precision_at_k(["doc2", "doc0", "doc4"], {"doc0"}) == pytest.approx(1 / 3)
    assert ev.recall_at_k(["doc2", "doc0", "doc4"], {"doc0"}) == 1.0


def test_dos_relevantes_y_solo_uno_recuperado():
    assert ev.recall_at_k(["a", "x", "y"], {"a", "b"}) == 0.5


# --- Evaluación ---

CASOS = [
    {"pregunta": "p1", "ids_relevantes": {"a"}},
    {"pregunta": "p2", "ids_relevantes": {"b"}},
    {"pregunta": "sin", "ids_relevantes": set()},
]
RESPUESTAS = {"p1": ["a", "x", "y"], "p2": ["x", "y", "z"], "sin": ["x", "y", "z"]}


def test_evaluar_promedia_solo_las_preguntas_con_respuesta():
    resultados, p, r = ev.evaluar_recuperacion(RetrieverFijo(RESPUESTAS), CASOS, k=3)
    assert p == pytest.approx((1 / 3 + 0) / 2)  # la pregunta sin respuesta no baja la precisión
    assert r == 0.5
    sin = resultados[2]
    assert sin["sin_respuesta"] and sin["precision"] is None and sin["recall"] is None


def test_evaluar_dice_cual_falla_y_en_que_posicion_acierta():
    resultados, _, _ = ev.evaluar_recuperacion(RetrieverFijo({**RESPUESTAS, "p1": ["x", "a", "y"]}), CASOS, k=3)
    assert resultados[0]["primer_acierto"] == 2
    assert resultados[1]["primer_acierto"] is None and resultados[1]["recall"] == 0.0


def test_evaluar_respeta_k():
    resultados, _, r = ev.evaluar_recuperacion(RetrieverFijo({**RESPUESTAS, "p2": ["x", "y", "b"]}), CASOS, k=2)
    assert resultados[1]["recuperados"] == ["x", "y"] and resultados[1]["recall"] == 0.0


def test_precision_maxima():
    assert ev.precision_maxima(CASOS, k=3) == pytest.approx(1 / 3)
    assert ev.precision_maxima([{"pregunta": "q", "ids_relevantes": {"a", "b"}}], k=3) == pytest.approx(2 / 3)


def test_con_el_indice_real_los_ids_coinciden_con_las_etiquetas(tmp_path):
    """Con embeddings falsos el orden no tiene sentido, pero los ids que devuelve Chroma deben ser los del corpus."""
    indice = ic.indexar(ic.partir_en_chunks(ic.cargar_corpus()), DeterministicFakeEmbedding(size=32), carpeta=tmp_path)
    resultados, p, r = ev.correr(indice, k=15)  # con k = total de chunks, todo lo relevante tiene que llegar
    assert r == 1.0
    assert all(0.0 <= x["precision"] <= 1.0 for x in resultados if x["precision"] is not None)


# --- Reporte ---


def test_formatear_y_guardar(tmp_path):
    resultados, p, r = ev.evaluar_recuperacion(RetrieverFijo(RESPUESTAS), CASOS, k=3)
    texto = ev.formatear(resultados, p, r, k=3, casos=CASOS)
    assert f"chunk_size={ic.CHUNK_SIZE}" in texto and "k=3" in texto
    assert "el relevante no llegó" in texto and "sin respuesta" in texto
    assert texto.strip().splitlines()[-2].startswith("promedio -> precision: 0.167  recall: 0.500")
    ruta = ev.guardar(texto, k=3, carpeta=tmp_path)
    assert ruta.name.endswith(f"_cs{ic.CHUNK_SIZE}_k3.txt") and ruta.read_text(encoding="utf-8") == texto
