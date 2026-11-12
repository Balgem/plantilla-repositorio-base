"""Recuperación semántica y prompt dinámico con citas sobre el corpus de la campaña (Bloque 26).

Uso, desde la raíz del repositorio y con el entorno activo (el índice ya tiene que existir):
    python3 src/indexar_corpus.py --verificar   # opcional: confirma que hay 15 chunks
    python3 src/recuperacion.py

1. construir_prompt: se reconecta al índice (NO reindexa), recupera los k chunks más cercanos a la pregunta
   y arma un prompt con el contexto numerado [1], [2], [3] y la instrucción de citar o decir que no sabe.
2. responder: le pasa ese prompt al modelo y revisa las citas de la respuesta: números que no existen
   en el contexto (inventados) y frases sin ninguna cita (candidatas a invento).

En el bot, los corchetes no se le muestran al viewer: las citas sirven para verificar y para la traza.
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

# Frases con las que el modelo admite que el contexto no alcanza. No citan nada, y está bien: son la salida
# que el prompt pide en vez de inventar. Sin esto, "El contexto no alcanza para responder..." se marcaba
# como frase sin cita (candidata a invento), al revés de lo que es.
ADMITE_NO_SABER = re.compile(
    r"contexto no (alcanza|menciona|indica|dice|incluye|especifica)|no (tengo|hay|se tiene) (esa )?informaci[oó]n|"
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
    """Recupera los k chunks más relevantes y arma el prompt dinámico.

    Recibe el índice ya conectado para no reconectarse en cada pregunta; si no se pasa, se conecta una vez.
    Nunca llama a from_documents: solo calcula el embedding de la pregunta.
    Devuelve (prompt, citas, chunks_recuperados).
    """
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
    """Revisa las citas de una respuesta del modelo.

    - fuentes: archivos que respaldan la respuesta (solo citas válidas).
    - inventadas: números que no estaban en el contexto (por ejemplo [99]).
    - admite_no_saber: frases sin cita en las que el modelo dice que el contexto no alcanza (lo correcto).
    - sin_cita: el resto de las frases que no citan nada: candidatas a invento.
    """
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
