"""Bloque 26: recuperación, prompt dinámico y revisión de citas, con embeddings y modelo falsos (sin API)."""
import re

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import indexar_corpus as ic
import recuperacion as rc


@pytest.fixture
def indice(tmp_path):
    """El corpus real de la campaña, indexado con embeddings falsos en una carpeta temporal."""
    chunks = ic.partir_en_chunks(ic.cargar_corpus())
    return ic.indexar(chunks, DeterministicFakeEmbedding(size=32), carpeta=tmp_path)


# --- Lo que la actividad pide que se cumpla siempre ---


def test_citas_tiene_k_entradas_con_claves_1_a_k(indice):
    _, citas, _ = rc.construir_prompt("¿qué valor tiene el teclado?", indice=indice, k=3)
    assert list(citas) == [1, 2, 3]


def test_ninguna_cita_es_desconocida(indice):
    _, citas, _ = rc.construir_prompt("¿cuánto pesa?", indice=indice, k=5)
    archivos = {d.metadata["fuente"] for d in ic.cargar_corpus()}
    assert set(citas.values()) <= archivos


def test_el_prompt_tiene_la_pregunta_exacta(indice):
    pregunta = "¿lo puedo usar con la PlayStation?  (pregunta con espacios raros)"
    prompt, _, _ = rc.construir_prompt(pregunta, indice=indice)
    assert f"Pregunta: {pregunta}\n" in prompt


def test_los_bloques_estan_numerados_desde_1_sin_saltos(indice):
    prompt, _, chunks = rc.construir_prompt("¿qué trae la caja?", indice=indice, k=4)
    numeros = [int(n) for n in re.findall(r"^\[(\d+)\] ", prompt, flags=re.MULTILINE)]
    assert numeros == list(range(1, len(chunks) + 1)) == [1, 2, 3, 4]


def test_el_prompt_pide_citar_y_admitir_que_no_sabe(indice):
    prompt, _, _ = rc.construir_prompt("hola", indice=indice)
    assert "Cita la fuente" in prompt and "dilo" in prompt and "en vez de inventar" in prompt


def test_preguntas_distintas_traen_contextos_distintos(indice):
    _, _, uno = rc.construir_prompt("¿qué valor tiene el teclado?", indice=indice)
    _, _, otro = rc.construir_prompt("¿cuánto se demora el despacho?", indice=indice)
    assert [c.page_content for c in uno] != [c.page_content for c in otro]


# --- Errores frecuentes de la actividad ---


def test_construir_prompt_no_reindexa(tmp_path):
    ic.indexar(ic.partir_en_chunks(ic.cargar_corpus()), DeterministicFakeEmbedding(size=32), carpeta=tmp_path)

    class SoloPreguntas(DeterministicFakeEmbedding):
        def embed_documents(self, texts):
            raise AssertionError("construir_prompt no debería calcular embeddings del corpus")

    indice = ic.conectar_indice(SoloPreguntas(size=32), carpeta=tmp_path)
    rc.construir_prompt("¿qué valor tiene?", indice=indice)  # solo embed_query de la pregunta


def test_k_mayor_que_el_indice_devuelve_lo_que_hay(indice):
    _, citas, _ = rc.construir_prompt("x", indice=indice, k=50)
    assert len(citas) == indice._collection.count()


def test_indice_vacio_no_inventa_contexto(tmp_path):
    vacio = ic.conectar_indice(DeterministicFakeEmbedding(size=32), carpeta=tmp_path / "vacio")
    prompt, citas, _ = rc.construir_prompt("¿qué valor tiene?", indice=vacio)
    assert citas == {} and rc.SIN_CONTEXTO in prompt


def test_pregunta_vacia():
    with pytest.raises(ValueError):
        rc.construir_prompt("   ", indice=object())


def test_metadata_faltante_se_ve_como_desconocida():
    from langchain_core.documents import Document

    _, citas = rc.formatear_contexto([Document(page_content="x", metadata={})])
    assert citas == {1: "desconocida"}


# --- Revisión de citas ---


def test_revisar_citas():
    citas = {1: "02_precio_y_compra.md", 2: "03_despacho.md"}
    respuesta = "El K7 cuesta 59.990 CLP [1]. El despacho son 3.990 CLP [2]. Llega mañana [5]. Tiene 2 años de garantía."
    revision = rc.revisar_citas(respuesta, citas)
    assert revision["fuentes"] == ["02_precio_y_compra.md", "03_despacho.md"]
    assert revision["inventadas"] == [5]
    assert revision["sin_cita"] == ["Tiene 2 años de garantía."]


def test_respuesta_bien_citada_no_marca_nada():
    revision = rc.revisar_citas("Cuesta 59.990 CLP [1] y se compra en el link oficial [1][2].", {1: "a", 2: "b"})
    assert revision == {"fuentes": ["a", "b"], "inventadas": [], "sin_cita": []}


def test_responder_llama_al_modelo_con_el_prompt_y_revisa_las_citas(indice):
    modelo = FakeListChatModel(responses=["El K7 cuesta 59.990 CLP [1]. Además es resistente al agua [9]."])
    resultado = rc.responder("¿qué valor tiene el teclado?", modelo, indice=indice)
    assert resultado["respuesta"].startswith("El K7 cuesta")
    assert resultado["revision"]["inventadas"] == [9]
    assert resultado["citas"][1] in {d.metadata["fuente"] for d in ic.cargar_corpus()}


def test_cada_chunk_queda_en_una_sola_linea_del_contexto(indice):
    contexto, citas = rc.formatear_contexto(ic.partir_en_chunks(ic.cargar_corpus())[:3])
    assert len(contexto.split("\n\n")) == len(citas) == 3
