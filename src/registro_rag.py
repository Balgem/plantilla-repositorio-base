"""Latencia y costo del flujo RAG por etapa: embedding, búsqueda y generación (Bloque 28).

Cada corrida se agrega a docs/registros_latencia_costo.jsonl.

Uso:
    python3 src/registro_rag.py
    python3 src/registro_rag.py --leer
"""
import argparse
import json
import logging
import os
import statistics
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

from agente_con_herramientas import texto_de_salida
from cliente import PRECIOS_POR_MILLON
from evaluacion_recuperacion import CASOS_EVALUACION
from indexar_corpus import CHUNK_SIZE, RAIZ, conectar_indice, crear_embeddings
from recuperacion import PROMPT_TEMPLATE, K, formatear_contexto, revisar_citas

logger = logging.getLogger(__name__)

ARCHIVO_REGISTROS = RAIZ / "docs" / "registros_latencia_costo.jsonl"

# Preguntas del conjunto de evaluación del Bloque 27, de distinto largo y de distintas zonas del corpus
PREGUNTAS = [
    "¿es inalámbrico?",
    "¿cuánto cobran por el envío?",
    "si le cae café encima, ¿lo cubre la garantía?",
    "¿cuánto pesa el teclado?",  # sin respuesta: ¿cuesta distinto cuando el bot admite que no sabe?
]
PREGUNTA_COMPARAR_K = "¿cuánto cobran por el envío?"
K_MAYOR = 6

assert all(p in {c["pregunta"] for c in CASOS_EVALUACION} for p in PREGUNTAS)


@contextmanager
def medir(tiempos: dict, etapa: str):
    """Guarda en tiempos[etapa] los segundos que tardó el bloque with (perf_counter, no time.time)."""
    inicio = time.perf_counter()
    try:
        yield
    finally:
        tiempos[etapa] = time.perf_counter() - inicio


def costo_usd(tokens: dict | None, modelo: str) -> float | None:
    """Costo real de la llamada: entrada y salida con su propio precio. La salida ya incluye el razonamiento."""
    precios = PRECIOS_POR_MILLON.get(modelo)
    if not tokens or precios is None:
        return None
    return (tokens["input_tokens"] * precios[0] + tokens["output_tokens"] * precios[1]) / 1_000_000


def registrar_consulta(pregunta: str, indice, embeddings, modelo, nombre_modelo: str, k: int = K) -> dict:
    """Corre una consulta RAG real midiendo cada etapa y devuelve el registro (no lo guarda)."""
    tiempos = {}
    with medir(tiempos, "embed_query"):
        vector = embeddings.embed_query(pregunta)
    with medir(tiempos, "busqueda_vectorial"):
        chunks = indice.similarity_search_by_vector(vector, k=k)
    contexto, citas = formatear_contexto(chunks)
    prompt = PROMPT_TEMPLATE.format(contexto=contexto, pregunta=pregunta)
    with medir(tiempos, "generacion"):
        respuesta = modelo.invoke(prompt)

    tokens = dict(respuesta.usage_metadata) if respuesta.usage_metadata else None
    texto = texto_de_salida(respuesta.content).strip()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pregunta": pregunta,
        "k": k,
        "chunk_size": CHUNK_SIZE,
        "modelo": nombre_modelo,
        "ids_recuperados": [c.id for c in chunks],
        "caracteres_prompt": len(prompt),
        "tiempos_ms": {etapa: round(s * 1000, 2) for etapa, s in tiempos.items()},
        "tiempo_total_ms": round(sum(tiempos.values()) * 1000, 2),
        "tokens": tokens,
        "costo_usd": costo_usd(tokens, nombre_modelo),
        "respuesta": texto,
        "fuentes_citadas": revisar_citas(texto, citas)["fuentes"],
    }


def guardar(registro: dict, archivo=None) -> None:
    """Agrega el registro como una línea JSON (JSON Lines: no hay que leer todo el archivo para agregar)."""
    ruta = archivo or ARCHIVO_REGISTROS
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_registros(archivo=None) -> list[dict]:
    ruta = archivo or ARCHIVO_REGISTROS
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def razonamiento(registro: dict) -> int:
    return ((registro.get("tokens") or {}).get("output_token_details") or {}).get("reasoning", 0)


def linea(r: dict) -> str:
    t, tok = r["tiempos_ms"], r.get("tokens") or {}
    costo = "   n/a   " if r.get("costo_usd") is None else f"${r['costo_usd']:.6f}"
    return (f"k={r['k']}  embed {t.get('embed_query', 0):>6.0f} ms  búsqueda {t.get('busqueda_vectorial', 0):>4.0f} ms  "
            f"generación {t.get('generacion', 0):>6.0f} ms  |  entrada {tok.get('input_tokens', '?'):>4}  "
            f"salida {tok.get('output_tokens', '?'):>4} (razonamiento {razonamiento(r):>4})  {costo}  {r['pregunta']}")


def resumen(registros: list[dict]) -> str:
    """Promedios por etapa, qué parte del tiempo es generación, y costo típico (no el de una sola consulta)."""
    if not registros:
        return "No hay registros."
    def prom(f):
        return statistics.mean(f(r) for r in registros)
    total = prom(lambda r: r["tiempo_total_ms"])
    gen = prom(lambda r: r["tiempos_ms"].get("generacion", 0))
    costos = [r["costo_usd"] for r in registros if r.get("costo_usd") is not None]
    salidas = [r["tokens"]["output_tokens"] for r in registros if r.get("tokens")]
    lineas = [
        f"Consultas registradas: {len(registros)}",
        f"Promedio por etapa: embed {prom(lambda r: r['tiempos_ms'].get('embed_query', 0)):.0f} ms · "
        f"búsqueda {prom(lambda r: r['tiempos_ms'].get('busqueda_vectorial', 0)):.0f} ms · generación {gen:.0f} ms "
        f"(total {total:.0f} ms; la generación es el {100 * gen / total:.0f} %)",
    ]
    if salidas:
        lineas.append(f"Tokens de salida: promedio {statistics.mean(salidas):.0f}, de los cuales razonamiento "
                      f"{statistics.mean(razonamiento(r) for r in registros if r.get('tokens')):.0f}")
    if costos:
        lineas.append(f"Costo por consulta: promedio ${statistics.mean(costos):.6f} (mín ${min(costos):.6f}, "
                      f"máx ${max(costos):.6f}) -> 1.000 respuestas ≈ ${1000 * statistics.mean(costos):.2f}")
    return "\n".join(lineas)


if __name__ == "__main__":
    from cadena_tres_pasos import crear_modelo

    parser = argparse.ArgumentParser(description="Registra la latencia y el costo real del flujo RAG.")
    parser.add_argument("--leer", action="store_true", help="solo mostrar lo ya registrado")
    if parser.parse_args().leer:
        registros = leer_registros()
        for r in registros:
            print(linea(r))
        print("\n" + resumen(registros))
        raise SystemExit(0)

    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    nombre_modelo = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    embeddings = crear_embeddings()
    indice = conectar_indice(embeddings)  # una vez, fuera de las mediciones
    modelo = crear_modelo()
    print(f"Modelo: {nombre_modelo} · índice: {indice._collection.count()} chunks · chunk_size={CHUNK_SIZE}\n")

    corridas = [(p, K) for p in PREGUNTAS] + [(PREGUNTA_COMPARAR_K, K_MAYOR)]
    nuevos = []
    for pregunta, k in corridas:
        try:
            registro = registrar_consulta(pregunta, indice, embeddings, modelo, nombre_modelo, k=k)
        except Exception as error:  # una consulta fallida no se guarda: el archivo solo tiene corridas reales completas
            logger.warning("No se registró %r (k=%s): %s", pregunta, k, error)
            continue
        guardar(registro)
        nuevos.append(registro)
        print(linea(registro))
        print(f"      respuesta: {registro['respuesta']}")

    print(f"\n{len(nuevos)} líneas nuevas en {ARCHIVO_REGISTROS.relative_to(RAIZ)}\n")
    print(resumen(nuevos))
    comparar = {r["k"]: r for r in nuevos if r["pregunta"] == PREGUNTA_COMPARAR_K}
    if K in comparar and K_MAYOR in comparar:
        a, b = comparar[K]["tokens"]["input_tokens"], comparar[K_MAYOR]["tokens"]["input_tokens"]
        print(f"\nMisma pregunta, k={K} -> k={K_MAYOR}: input_tokens {a} -> {b} (creció: {b > a})")
