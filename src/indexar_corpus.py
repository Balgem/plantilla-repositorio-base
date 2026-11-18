"""Indexa el corpus de la campaña y persiste los embeddings en Chroma (Bloque 24).

Indexación incremental (Bloque 25): solo calcula embeddings de los chunks nuevos o que cambiaron, y borra
los que ya no están en el corpus. Correrlo sin cambios en el corpus no llama a la API:
    python3 src/indexar_corpus.py
Desde cero (borra la colección y recalcula todo; por ejemplo, si se cambia el modelo de embeddings):
    python3 src/indexar_corpus.py --desde-cero
Comprobar que quedó en disco, en un proceso nuevo y SIN recalcular embeddings:
    python3 src/indexar_corpus.py --verificar

- Corpus: corpus/campana_k7/*.md, un tema por archivo (ficha técnica, precio, despacho, garantía...).
- Chunking: RecursiveCharacterTextSplitter, documento por documento, para que un chunk nunca mezcle
  dos archivos (dos temas). Ver CHUNK_SIZE más abajo para el porqué del tamaño.
- Embeddings: gemini-embedding-001 (una llamada por chunk, gasta tokens reales).
- Persistencia: vectorstore/ en la raíz del repo (en .gitignore: se regenera con este script).
"""
import argparse
import hashlib
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from configuracion import MENSAJE_SIN_CLAVE, clave_api
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
    """Modelo de embeddings de Gemini con la misma clave del proyecto (GEMINI_API_KEY o API_KEY)."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    load_dotenv()
    if not clave_api():
        raise SystemExit(MENSAJE_SIN_CLAVE)
    return GoogleGenerativeAIEmbeddings(model=MODELO_EMBEDDINGS, google_api_key=clave_api())


def clasificar_error(error: Exception) -> Exception:
    """Traduce el error de la API a los tipos del proyecto: TimeoutError se reintenta, ValueError no."""
    mensaje = str(error)
    if "429" in mensaje or "RESOURCE_EXHAUSTED" in mensaje or "503" in mensaje or "UNAVAILABLE" in mensaje:
        return TimeoutError(f"Límite de peticiones o servicio no disponible: {mensaje[:200]}")
    if "API key" in mensaje or "API_KEY_INVALID" in mensaje or "401" in mensaje or "403" in mensaje:
        return ValueError('La API rechazó la llave. Revisa GEMINI_API_KEY (o API_KEY) en tu ".env".')
    return error


def id_de(chunk: Document) -> str:
    """Id estable de un chunk: archivo#posición (sirve para rastrearlo hasta su fuente)."""
    return f"{chunk.metadata['fuente']}#{chunk.metadata['chunk']}"


def huella_contenido(texto: str) -> str:
    """Huella del TEXTO del chunk (no es dato de un viewer): si cambia, el chunk se vuelve a embeber."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def actualizar_indice(chunks: list[Document], embeddings, carpeta: Path = CARPETA_VECTORSTORE,
                      desde_cero: bool = False) -> tuple[Chroma, dict]:
    """Actualización incremental con ids explícitos (Bloque 25). Devuelve (índice, resumen de cambios).

    Compara cada chunk con lo que ya está en el índice por id y por huella del contenido:
    - nuevo (id que no estaba) o cambiado (misma posición, otro texto): se calcula su embedding y se guarda;
    - borrado (id que ya no está en el corpus): se elimina, para que no siga apareciendo en las búsquedas;
    - sin cambios: no se toca y NO se llama a la API.
    Con desde_cero=True se borra la colección completa antes (lo que hacía la versión del Bloque 24).
    """
    if desde_cero:
        Chroma(collection_name=COLECCION, embedding_function=embeddings,
               persist_directory=str(carpeta)).delete_collection()
    indice = Chroma(collection_name=COLECCION, embedding_function=embeddings, persist_directory=str(carpeta))
    guardados = indice.get(include=["metadatas"])
    huellas_guardadas = {id_: (meta or {}).get("huella") for id_, meta in zip(guardados["ids"], guardados["metadatas"])}

    actuales = {}
    for chunk in chunks:
        chunk = Document(page_content=chunk.page_content,
                         metadata={**chunk.metadata, "huella": huella_contenido(chunk.page_content)})
        actuales[id_de(chunk)] = chunk
    nuevos = [i for i in actuales if i not in huellas_guardadas]
    cambiados = [i for i in actuales if i in huellas_guardadas and huellas_guardadas[i] != actuales[i].metadata["huella"]]
    borrados = [i for i in huellas_guardadas if i not in actuales]

    if borrados or cambiados:
        indice.delete(ids=borrados + cambiados)
    por_embeber = nuevos + cambiados
    if por_embeber:
        try:
            indice.add_documents([actuales[i] for i in por_embeber], ids=por_embeber)
        except Exception as error:  # solo la llamada externa; se traduce para decidir si se reintenta
            clasificado = clasificar_error(error)
            if clasificado is error:
                raise
            raise clasificado from error
    resumen = {"nuevos": len(nuevos), "cambiados": len(cambiados), "borrados": len(borrados),
               "sin_cambios": len(actuales) - len(nuevos) - len(cambiados), "total": len(actuales),
               "embeddings_calculados": len(por_embeber)}
    return indice, resumen


def indexar(chunks: list[Document], embeddings, carpeta: Path = CARPETA_VECTORSTORE,
            desde_cero: bool = False) -> Chroma:
    """Igual que actualizar_indice, devolviendo solo el índice (la firma que usan los bloques anteriores)."""
    return actualizar_indice(chunks, embeddings, carpeta, desde_cero)[0]


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
    parser = argparse.ArgumentParser(description="Indexa el corpus de la campaña en Chroma (incremental).")
    parser.add_argument("--verificar", action="store_true", help="solo reconectar y contar, sin indexar")
    parser.add_argument("--desde-cero", action="store_true", help="borrar la colección y recalcular todo")
    argumentos = parser.parse_args()

    load_dotenv()
    embeddings = crear_embeddings()
    if argumentos.verificar:
        sys.exit(0 if verificar(embeddings) else 1)

    titulo("PASO 1: chunking + actualización incremental del índice")
    documentos = cargar_corpus()
    chunks = partir_en_chunks(documentos)
    print(f"Corpus: {len(documentos)} documentos -> {len(chunks)} chunks "
          f"(chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP})")
    try:
        (_, resumen), intentos = con_reintentos(
            lambda: actualizar_indice(chunks, embeddings, desde_cero=argumentos.desde_cero))
    except (TimeoutError, ValueError) as error:
        print(f"No se pudo indexar: {error}")
        raise SystemExit(1)
    print(f"Nuevos: {resumen['nuevos']} · cambiados: {resumen['cambiados']} · borrados: {resumen['borrados']} · "
          f"sin cambios: {resumen['sin_cambios']} · embeddings calculados: {resumen['embeddings_calculados']} "
          f"(intentos: {intentos})")

    titulo("PASO 2: confirmando que quedó en disco, no solo en memoria")
    mostrar_carpeta()
    verificar(embeddings)

    titulo("PASO 3: búsqueda por significado (1 embedding: el de la pregunta)")
    indice = conectar_indice(embeddings)
    for pregunta in ["¿qué valor tiene el teclado?", "¿me sirve si uso Mac?", "¿cuánto se demora en llegar a Concepción?"]:
        [(chunk, distancia)] = indice.similarity_search_with_score(pregunta, k=1)
        print(f"\n> {pregunta}\n  {chunk.metadata['fuente']} (distancia {distancia:.3f}): "
              f"{chunk.page_content.replace(chr(10), ' ')[:110]}...")
