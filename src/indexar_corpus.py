"""Indexa el corpus de la campaña y persiste los embeddings en Chroma (Bloque 24).

Indexación (una vez por campaña, o cuando cambian los documentos):
    python3 src/indexar_corpus.py              # chunking + embeddings + guardar en vectorstore/
Comprobar que quedó en disco, en un proceso nuevo y SIN recalcular embeddings:
    python3 src/indexar_corpus.py --verificar

- Corpus: corpus/campana_k7/*.md, un tema por archivo (ficha técnica, precio, despacho, garantía...).
- Chunking: RecursiveCharacterTextSplitter, documento por documento, para que un chunk nunca mezcle
  dos archivos (dos temas). Ver CHUNK_SIZE más abajo para el porqué del tamaño.
- Embeddings: gemini-embedding-001 (una llamada por chunk, gasta tokens reales).
- Persistencia: vectorstore/ en la raíz del repo (en .gitignore: se regenera con este script).
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from consumir_gemini import con_reintentos

RAIZ = Path(__file__).resolve().parent.parent  # rutas fijas: funciona aunque se corra desde otra carpeta
CARPETA_CORPUS = RAIZ / "corpus" / "campana_k7"
CARPETA_VECTORSTORE = RAIZ / "vectorstore"
COLECCION = "campana_k7"
MODELO_EMBEDDINGS = "models/gemini-embedding-001"

# Los párrafos del corpus miden entre 60 y 182 caracteres y cada uno es una idea completa.
# - 250 deja entrar el párrafo más largo entero (no se corta ninguna oración) y como mucho junta
#   2 o 3 párrafos cortos del MISMO archivo, que hablan del mismo tema: 6 documentos -> 15 chunks.
# - Con 150 se partían párrafos y quedaban chunks como "cuesta 3.990 CLP" sin decir de qué (lección 2).
# - Con 400 o más, una pregunta frecuente quedaba mezclada con otras 2 o 3 (ruido + ñ + hot-swap).
# El overlap (~15 %) solo actúa si algún párrafo supera 250 caracteres.
CHUNK_SIZE = 250
CHUNK_OVERLAP = 40


def cargar_corpus(carpeta: Path = CARPETA_CORPUS) -> list[Document]:
    """Un Document por archivo .md, con el nombre del archivo en metadata['fuente']."""
    archivos = sorted(carpeta.glob("*.md"))
    if not archivos:
        raise SystemExit(f"No hay documentos .md en {carpeta}.")
    return [Document(page_content=a.read_text(encoding="utf-8").strip(), metadata={"fuente": a.name})
            for a in archivos]


def partir_en_chunks(documentos: list[Document], chunk_size: int = CHUNK_SIZE,
                     chunk_overlap: int = CHUNK_OVERLAP) -> list[Document]:
    """Parte cada documento por separado. Cada chunk conserva su 'fuente' y suma su posición ('chunk')."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = []
    for documento in documentos:
        for numero, texto in enumerate(splitter.split_text(documento.page_content)):
            chunks.append(Document(page_content=texto, metadata={**documento.metadata, "chunk": numero}))
    return chunks


def crear_embeddings():
    """Modelo de embeddings de Gemini con la misma llave del proyecto (API_KEY)."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    load_dotenv()
    if not os.getenv("API_KEY"):
        raise SystemExit('Falta API_KEY. Defínela en tu archivo ".env" y vuelve a ejecutar.')
    return GoogleGenerativeAIEmbeddings(model=MODELO_EMBEDDINGS, google_api_key=os.getenv("API_KEY"))


def clasificar_error(error: Exception) -> Exception:
    """Traduce el error de la API a los tipos del proyecto: TimeoutError se reintenta, ValueError no."""
    mensaje = str(error)
    if "429" in mensaje or "RESOURCE_EXHAUSTED" in mensaje or "503" in mensaje or "UNAVAILABLE" in mensaje:
        return TimeoutError(f"Límite de peticiones o servicio no disponible: {mensaje[:200]}")
    if "API key" in mensaje or "API_KEY_INVALID" in mensaje or "401" in mensaje or "403" in mensaje:
        return ValueError('La API rechazó la llave. Revisa API_KEY en tu ".env".')
    return error


def indexar(chunks: list[Document], embeddings, carpeta: Path = CARPETA_VECTORSTORE) -> Chroma:
    """Borra la colección anterior (si existe) y la vuelve a crear con estos chunks.

    Se borra antes porque correr from_documents dos veces sobre la misma carpeta AGREGA los chunks de nuevo
    (quedarían duplicados), y un documento eliminado del corpus seguiría apareciendo en las búsquedas.
    Los ids son estables (archivo#posición) para poder rastrear cada chunk hasta su fuente.
    """
    Chroma(collection_name=COLECCION, embedding_function=embeddings,
           persist_directory=str(carpeta)).delete_collection()
    try:
        return Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            ids=[f"{c.metadata['fuente']}#{c.metadata['chunk']}" for c in chunks],
            collection_name=COLECCION,
            persist_directory=str(carpeta),
        )
    except Exception as error:  # solo la llamada externa; se traduce para decidir si se reintenta
        clasificado = clasificar_error(error)
        if clasificado is error:
            raise
        raise clasificado from error


def conectar_indice(embeddings, carpeta: Path = CARPETA_VECTORSTORE) -> Chroma:
    """Se reconecta al índice ya guardado. No calcula ningún embedding del corpus."""
    return Chroma(collection_name=COLECCION, embedding_function=embeddings, persist_directory=str(carpeta))


def titulo(texto: str) -> None:
    print(f"\n{'=' * 60}\n{texto}\n{'=' * 60}")


def mostrar_carpeta(carpeta: Path = CARPETA_VECTORSTORE) -> None:
    elementos = sorted(carpeta.iterdir()) if carpeta.exists() else []
    print(f"Contenido real de {carpeta.name}/ ({len(elementos)} elementos):")
    for elemento in elementos:
        print(f"  {elemento.name}/" if elemento.is_dir() else f"  {elemento.name}  ({elemento.stat().st_size} bytes)")


def verificar(embeddings) -> int:
    titulo("PASO 3: reconectando al índice ya persistido (sin recalcular embeddings)")
    total = conectar_indice(embeddings)._collection.count()
    print(f"Chunks recuperados al reconectar: {total}")
    if total == 0:
        print("0 chunks: corre primero 'python3 src/indexar_corpus.py' (o revisa la carpeta del índice).")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indexa el corpus de la campaña en Chroma.")
    parser.add_argument("--verificar", action="store_true", help="solo reconectar y contar, sin indexar")
    argumentos = parser.parse_args()

    embeddings = crear_embeddings()
    if argumentos.verificar:
        sys.exit(0 if verificar(embeddings) else 1)

    titulo("PASO 1: chunking + embeddings + indexación")
    documentos = cargar_corpus()
    chunks = partir_en_chunks(documentos)
    print(f"Corpus original: {len(documentos)} documentos")
    print(f"Después de chunking: {len(chunks)} chunks (chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP})\n")
    for chunk in chunks:
        texto = chunk.page_content.replace("\n", " ")
        print(f"  {chunk.metadata['fuente']}#{chunk.metadata['chunk']} ({len(chunk.page_content)}): {texto[:80]}...")
    print(f"\nCalculando {len(chunks)} embeddings e indexando en Chroma (esto llama a la API)...")
    try:
        _, intentos = con_reintentos(lambda: indexar(chunks, embeddings))
    except (TimeoutError, ValueError) as error:
        print(f"No se pudo indexar: {error}")
        raise SystemExit(1)
    print(f"Indexados {len(chunks)} chunks en {CARPETA_VECTORSTORE.name}/ (intentos: {intentos})")

    titulo("PASO 2: confirmando que quedó en disco, no solo en memoria")
    mostrar_carpeta()

    verificar(embeddings)

    titulo("PASO 4: búsqueda por significado (1 embedding: el de la pregunta)")
    indice = conectar_indice(embeddings)
    for pregunta in ["¿qué valor tiene el teclado?", "¿me sirve si uso Mac?", "¿cuánto se demora en llegar a Concepción?"]:
        [(chunk, distancia)] = indice.similarity_search_with_score(pregunta, k=1)
        print(f"\n> {pregunta}\n  {chunk.metadata['fuente']} (distancia {distancia:.3f}): "
              f"{chunk.page_content.replace(chr(10), ' ')[:110]}...")
