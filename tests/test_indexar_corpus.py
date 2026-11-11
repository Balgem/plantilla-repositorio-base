"""Bloque 24: corpus, chunking y persistencia en Chroma, con embeddings falsos (no llama a la API)."""
import re

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

import indexar_corpus as ic
from agente_con_herramientas import PROMESAS_PROHIBIDAS, URL, LINK_OFICIAL


@pytest.fixture
def embeddings_falsos():
    return DeterministicFakeEmbedding(size=32)  # mismo texto -> mismo vector; no es búsqueda por significado


@pytest.fixture
def chunks():
    return ic.partir_en_chunks(ic.cargar_corpus())


# --- Corpus ---


def test_el_corpus_tiene_al_menos_5_documentos_y_no_incluye_el_readme():
    documentos = ic.cargar_corpus()
    assert len(documentos) >= 5
    assert all(d.metadata["fuente"].endswith(".md") for d in documentos)
    assert "README.md" not in {d.metadata["fuente"] for d in documentos}


def test_el_corpus_coincide_con_los_datos_oficiales_de_la_campana():
    texto = " ".join(d.page_content for d in ic.cargar_corpus())
    assert "59.990 CLP" in texto
    assert {link.rstrip(".") for link in URL.findall(texto)} == {LINK_OFICIAL}  # ningún otro link
    assert "no tiene descuentos" in texto.lower()


def test_ninguna_frase_del_corpus_choca_con_el_filtro_de_promesas():
    """Si el corpus dijera 'stock' u 'oferta', el filtro borraría la respuesta correcta del bot."""
    for documento in ic.cargar_corpus():
        assert not PROMESAS_PROHIBIDAS.search(documento.page_content), documento.metadata["fuente"]


# --- Chunking ---


def test_ningun_chunk_supera_el_tamano(chunks):
    assert all(len(c.page_content) <= ic.CHUNK_SIZE for c in chunks)


def test_hay_mas_chunks_que_documentos(chunks):
    assert len(chunks) > len(ic.cargar_corpus())  # sí se partió: no se indexaron documentos completos


def test_ningun_chunk_corta_una_oracion(chunks):
    assert all(re.search(r"[.?!]$", c.page_content.strip()) for c in chunks)


def test_cada_chunk_sabe_de_que_archivo_viene(chunks):
    fuentes = {d.metadata["fuente"]: d.page_content for d in ic.cargar_corpus()}
    for chunk in chunks:
        assert chunk.page_content in fuentes[chunk.metadata["fuente"]]  # nunca mezcla dos archivos


def test_el_precio_queda_en_el_mismo_chunk_que_la_palabra_precio(chunks):
    """El problema de la lección 2: un monto suelto sin decir de qué es."""
    for chunk in chunks:
        if "59.990" in chunk.page_content:
            assert "precio" in chunk.page_content.lower()
        if "3.990" in chunk.page_content:
            assert "despacho" in chunk.page_content.lower()


# --- Persistencia ---


def test_indexar_persiste_en_disco_y_se_puede_reconectar(tmp_path, chunks, embeddings_falsos):
    ic.indexar(chunks, embeddings_falsos, carpeta=tmp_path)
    assert any(tmp_path.iterdir())  # la carpeta no quedó vacía
    recargado = ic.conectar_indice(embeddings_falsos, carpeta=tmp_path)
    assert recargado._collection.count() == len(chunks)


def test_reindexar_no_duplica(tmp_path, chunks, embeddings_falsos):
    ic.indexar(chunks, embeddings_falsos, carpeta=tmp_path)
    ic.indexar(chunks, embeddings_falsos, carpeta=tmp_path)
    assert ic.conectar_indice(embeddings_falsos, carpeta=tmp_path)._collection.count() == len(chunks)


def test_reindexar_borra_lo_que_ya_no_esta_en_el_corpus(tmp_path, chunks, embeddings_falsos):
    ic.indexar(chunks, embeddings_falsos, carpeta=tmp_path)
    ic.indexar(chunks[:3], embeddings_falsos, carpeta=tmp_path)
    assert ic.conectar_indice(embeddings_falsos, carpeta=tmp_path)._collection.count() == 3


def test_reconectar_no_calcula_embeddings_del_corpus(tmp_path, chunks, embeddings_falsos):
    ic.indexar(chunks, embeddings_falsos, carpeta=tmp_path)

    class EmbeddingsQueNoSeDebenUsar(DeterministicFakeEmbedding):
        def embed_documents(self, texts):
            raise AssertionError("reconectar no debería calcular embeddings del corpus")

    recargado = ic.conectar_indice(EmbeddingsQueNoSeDebenUsar(size=32), carpeta=tmp_path)
    assert recargado._collection.count() == len(chunks)


def test_los_metadatos_se_guardan(tmp_path, chunks, embeddings_falsos):
    indice = ic.indexar(chunks, embeddings_falsos, carpeta=tmp_path)
    [resultado] = indice.similarity_search(chunks[0].page_content, k=1)  # texto idéntico -> mismo vector
    assert resultado.metadata == chunks[0].metadata


def test_reconectar_a_una_carpeta_equivocada_da_cero(tmp_path, embeddings_falsos):
    assert ic.conectar_indice(embeddings_falsos, carpeta=tmp_path / "otra")._collection.count() == 0


# --- Errores ---


@pytest.mark.parametrize("mensaje, tipo", [
    ("429 RESOURCE_EXHAUSTED", TimeoutError),
    ("503 UNAVAILABLE", TimeoutError),
    ("400 API key not valid. Please pass a valid API key.", ValueError),
    ("403 PERMISSION_DENIED", ValueError),
])
def test_clasificar_error(mensaje, tipo):
    assert isinstance(ic.clasificar_error(Exception(mensaje)), tipo)


def test_un_error_desconocido_no_se_disfraza():
    error = RuntimeError("otra cosa")
    assert ic.clasificar_error(error) is error


def test_un_429_al_indexar_se_convierte_en_timeout_para_reintentar(tmp_path, chunks):
    class EmbeddingsConLimite(DeterministicFakeEmbedding):
        def embed_documents(self, texts):
            raise Exception("429 RESOURCE_EXHAUSTED")

    with pytest.raises(TimeoutError):
        ic.indexar(chunks, EmbeddingsConLimite(size=32), carpeta=tmp_path)


def test_sin_api_key_termina_con_mensaje_claro(monkeypatch):
    monkeypatch.setattr(ic, "load_dotenv", lambda: None)
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(SystemExit, match="Falta API_KEY"):
        ic.crear_embeddings()
