"""Bloque 28: latencia por etapa y costo real del flujo RAG, con embeddings y modelo falsos (sin API)."""
import json

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

import indexar_corpus as ic
import registro_rag as rr

USO = {"input_tokens": 280, "output_tokens": 400, "total_tokens": 680,
       "output_token_details": {"reasoning": 370}}


@pytest.fixture
def piezas(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=32)
    indice = ic.indexar(ic.partir_en_chunks(ic.cargar_corpus()), embeddings, carpeta=tmp_path / "indice")
    return indice, embeddings


def modelo(*usos):
    return FakeMessagesListChatModel(responses=[AIMessage(content="Cuesta 3.990 CLP [1].", usage_metadata=u)
                                                for u in usos])


def test_el_registro_tiene_las_claves_de_la_actividad_y_las_tres_etapas(piezas):
    indice, emb = piezas
    r = rr.registrar_consulta("¿cuánto cobran por el envío?", indice, emb, modelo(USO), "gemini-3.5-flash-lite")
    assert {"timestamp", "pregunta", "k", "tiempos_ms", "tiempo_total_ms", "tokens"} <= set(r)
    assert set(r["tiempos_ms"]) == {"embed_query", "busqueda_vectorial", "generacion"}
    assert r["tiempo_total_ms"] == pytest.approx(sum(r["tiempos_ms"].values()), abs=0.05)
    assert len(r["ids_recuperados"]) == 3 and all("#" in i for i in r["ids_recuperados"])


def test_el_costo_usa_los_tokens_reales_y_los_precios_del_proyecto():
    # gemini-3.5-flash-lite: 0,30 entrada y 2,50 salida por millón (src/cliente.py)
    assert rr.costo_usd(USO, "gemini-3.5-flash-lite") == pytest.approx((280 * 0.30 + 400 * 2.50) / 1e6)
    assert rr.costo_usd(USO, "modelo-sin-precio") is None
    assert rr.costo_usd(None, "gemini-3.5-flash-lite") is None


def test_sin_usage_metadata_el_registro_dice_null(piezas):
    indice, emb = piezas
    r = rr.registrar_consulta("¿es inalámbrico?", indice, emb, modelo(None), "gemini-3.5-flash-lite")
    assert r["tokens"] is None and r["costo_usd"] is None


def test_k_mayor_trae_mas_chunks_y_un_prompt_mas_largo(piezas):
    indice, emb = piezas
    m = modelo(USO, USO)
    r3 = rr.registrar_consulta("¿cuánto cobran por el envío?", indice, emb, m, "x", k=3)
    r6 = rr.registrar_consulta("¿cuánto cobran por el envío?", indice, emb, m, "x", k=6)
    assert len(r6["ids_recuperados"]) == 6 and r6["caracteres_prompt"] > r3["caracteres_prompt"]


def test_medir_guarda_el_tiempo_aunque_la_etapa_falle():
    tiempos = {}
    with pytest.raises(RuntimeError):
        with rr.medir(tiempos, "generacion"):
            raise RuntimeError("503")
    assert "generacion" in tiempos


def test_guardar_agrega_una_linea_json_por_corrida(tmp_path):
    archivo = tmp_path / "r.jsonl"
    rr.guardar({"pregunta": "a", "k": 3}, archivo)
    rr.guardar({"pregunta": "b", "k": 6}, archivo)
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["k"] for x in lineas] == [3, 6]
    assert rr.leer_registros(archivo)[1]["pregunta"] == "b"
    assert rr.leer_registros(tmp_path / "no_existe.jsonl") == []


def test_las_preguntas_salen_del_conjunto_de_evaluacion():
    from evaluacion_recuperacion import CASOS_EVALUACION
    assert set(rr.PREGUNTAS) <= {c["pregunta"] for c in CASOS_EVALUACION} and len(rr.PREGUNTAS) >= 3


def test_resumen(piezas):
    indice, emb = piezas
    registros = [rr.registrar_consulta(p, indice, emb, modelo(USO), "gemini-3.5-flash-lite") for p in rr.PREGUNTAS[:2]]
    texto = rr.resumen(registros)
    assert "Consultas registradas: 2" in texto and "razonamiento 370" in texto and "1.000 respuestas" in texto
    assert "k=3" in rr.linea(registros[0])
    assert rr.resumen([]) == "No hay registros."
