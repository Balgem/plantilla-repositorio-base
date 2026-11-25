"""Recuperación semántica y prompt con citas numeradas (Bloque 26).

Recupera los k chunks más cercanos, arma el prompt con el contexto numerado y revisa las citas
de la respuesta (inventadas o ausentes).

Uso:
    python3 src/recuperacion.py
"""
import re

from dotenv import load_dotenv

from agente_con_herramientas import texto_de_salida
from indexar_corpus import conectar_indice, crear_embeddings

K = 3  # 3 y no 1: con k=1, "¿cuánto se demora en llegar a Concepción?" traía el chunk de Santiago (Bloque 24)

PROMPT_TEMPLATE = """Eres el bot de una campaña del teclado K7 en un chat de Twitch.
Responde la pregunta usando SOLO el contexto de abajo, en una o dos frases. Cita la fuente de cada \
afirmación con su número entre corchetes, como [1]. Si el contexto no alcanza para responder, dilo \
explícitamente en vez de inventar.

Contexto:
{contexto}

Pregunta: {pregunta}

Respuesta:"""

SIN_CONTEXTO = "(no se recuperó ningún fragmento)"

# Frases con las que el modelo admite que no sabe: no llevan cita y no deben contarse como invento.
ADMITE_NO_SABER = re.compile(
    r"contexto no (alcanza|menciona|indica|dice|incluye|especifica)|no (tengo|hay|se tiene) (esa )?informaci[oó]n|"
    r"no tengo (ese|este|el) dato|"  # la forma que pide la v3 del prompt (Bloque 32)
    r"no se (menciona|indica|especifica)",
    re.IGNORECASE,
)


def formatear_contexto(chunks_recuperados) -> tuple[str, dict[int, str]]:
    """Contexto numerado para el prompt y mapa {número: fuente} para reconstruir cada cita después."""
    lineas = []
    citas = {}
    for i, doc in enumerate(chunks_recuperados, start=1):
        fuente = doc.metadata.get("fuente", "desconocida")
        texto = " ".join(doc.page_content.split())  # un chunk = una línea: sus párrafos no parecen bloques aparte
        lineas.append(f"[{i}] {texto}")
        citas[i] = fuente
    contexto = "\n\n".join(lineas) if lineas else SIN_CONTEXTO
    return contexto, citas


def construir_prompt(pregunta: str, indice=None, k: int = K):
    """Recupera los k chunks más relevantes y arma el prompt dinámico."""
    if not pregunta or not pregunta.strip():
        raise ValueError("La pregunta está vacía.")
    if indice is None:
        indice = conectar_indice(crear_embeddings())
    retriever = indice.as_retriever(search_kwargs={"k": k})
    chunks_recuperados = retriever.invoke(pregunta)
    contexto, citas = formatear_contexto(chunks_recuperados)
    prompt = PROMPT_TEMPLATE.format(contexto=contexto, pregunta=pregunta)
    return prompt, citas, chunks_recuperados


def revisar_citas(respuesta: str, citas: dict[int, str]) -> dict:
    """Revisa las citas de una respuesta del modelo."""
    numeros = [int(n) for n in re.findall(r"\[(\d+)\]", respuesta)]
    frases = [f for f in re.split(r"(?<=[.!?])\s+", respuesta.strip()) if f]
    sin_cita = [f for f in frases if not re.search(r"\[\d+\]", f)]
    return {
        "fuentes": sorted({citas[n] for n in numeros if n in citas}),
        "inventadas": sorted({n for n in numeros if n not in citas}),
        "admite_no_saber": [f for f in sin_cita if ADMITE_NO_SABER.search(f)],
        "sin_cita": [f for f in sin_cita if not ADMITE_NO_SABER.search(f)],
    }


def responder(pregunta: str, modelo, indice=None, k: int = K) -> dict:
    """Recupera, arma el prompt, llama al modelo y revisa las citas."""
    prompt, citas, chunks = construir_prompt(pregunta, indice=indice, k=k)
    respuesta = texto_de_salida(modelo.invoke(prompt).content).strip()
    return {"pregunta": pregunta, "prompt": prompt, "citas": citas, "chunks": chunks,
            "respuesta": respuesta, "revision": revisar_citas(respuesta, citas)}


PREGUNTAS = [
    "¿qué valor tiene el teclado?",
    "¿cuánto se demora en llegar a Concepción?",
    "¿lo puedo usar con la PlayStation?",
    "¿cuánto pesa el K7?",  # el corpus no lo dice: el modelo tiene que admitir que no sabe
]

if __name__ == "__main__":
    from cadena_tres_pasos import crear_modelo

    load_dotenv()
    indice = conectar_indice(crear_embeddings())
    print(f"Índice: {indice._collection.name} · {indice._collection.count()} chunks\n")
    modelo = crear_modelo()
    for numero, pregunta in enumerate(PREGUNTAS, start=1):
        resultado = responder(pregunta, modelo, indice=indice)
        print("=" * 70)
        if numero == 1:  # el prompt completo, una vez, para ver cómo queda
            print(resultado["prompt"])
            print("-" * 70)
        print(f"Pregunta: {pregunta}")
        distancias = indice.similarity_search_with_score(pregunta, k=K)
        for i, (chunk, (_, distancia)) in enumerate(zip(resultado["chunks"], distancias), start=1):
            print(f"  [{i}] {chunk.id} (distancia {distancia:.3f}): {chunk.page_content.replace(chr(10), ' ')[:70]}...")
        print(f"citas: {resultado['citas']}")
        print(f"Respuesta del modelo: {resultado['respuesta']}")
        revision = resultado["revision"]
        print(f"  fuentes citadas: {revision['fuentes'] or 'ninguna'}")
        if revision["inventadas"]:
            print(f"  ⚠️ citas inventadas: {revision['inventadas']}")
        if revision["admite_no_saber"]:
            print(f"  ✅ admite que no sabe: {revision['admite_no_saber']}")
        if revision["sin_cita"]:
            print(f"  ⚠️ frases sin cita: {revision['sin_cita']}")
