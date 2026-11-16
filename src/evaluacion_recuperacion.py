"""Evaluación de la recuperación con precisión@k y recall@k (Bloque 27).

Uso, desde la raíz del repositorio y con el entorno activo (el índice ya tiene que existir):
    python3 src/evaluacion_recuperacion.py            # k=3 (el del bot), dos veces + k=5, y guarda los resultados
    python3 src/evaluacion_recuperacion.py --k 2      # otra configuración para comparar

- CASOS_EVALUACION se etiquetó leyendo corpus/campana_k7/ ANTES de correr el retriever con estas preguntas.
- Las preguntas sin respuesta en el corpus se evalúan aparte: no tienen recall (no hay nada que recuperar) y
  su precisión siempre sería 0 (el retriever igual trae k chunks), así que no entran en los promedios.
- Cada corrida se guarda en docs/evaluaciones/<fecha>_cs<chunk_size>_k<k>.txt, con la configuración leída
  de indexar_corpus.py (no escrita a mano), para comparar la próxima vez que cambie algo.
"""
import argparse
from datetime import date
from pathlib import Path

from indexar_corpus import CHUNK_OVERLAP, CHUNK_SIZE, MODELO_EMBEDDINGS, RAIZ, conectar_indice, crear_embeddings
from recuperacion import K

CARPETA_RESULTADOS = RAIZ / "docs" / "evaluaciones"

# Etiquetado a mano desde el corpus (ids = archivo#posición del chunk, ver python3 src/indexar_corpus.py).
# Si cambia el chunking, los ids cambian y hay que volver a etiquetar: tests/test_evaluacion_recuperacion.py
# falla si alguna etiqueta ya no existe en el índice.
CASOS_EVALUACION = [
    # precio y compra
    {"pregunta": "¿sale muy caro el teclado?", "ids_relevantes": {"02_precio_y_compra.md#0"}},
    {"pregunta": "¿dónde lo puedo comprar?", "ids_relevantes": {"02_precio_y_compra.md#1"}},
    {"pregunta": "¿se puede pagar con débito?", "ids_relevantes": {"02_precio_y_compra.md#1"}},
    # despacho
    {"pregunta": "¿cuánto cobran por el envío?", "ids_relevantes": {"03_despacho.md#0"}},
    {"pregunta": "¿llega a Arica?", "ids_relevantes": {"03_despacho.md#0"}},
    {"pregunta": "si lo pido hoy, ¿cuándo me llega en Santiago?", "ids_relevantes": {"03_despacho.md#1"}},
    # garantía y soporte
    {"pregunta": "si le cae café encima, ¿lo cubre la garantía?", "ids_relevantes": {"04_garantia_y_soporte.md#0"}},
    {"pregunta": "se me rompió una tecla, ¿a quién le escribo?", "ids_relevantes": {"04_garantia_y_soporte.md#1"}},
    # producto
    {"pregunta": "¿es inalámbrico?", "ids_relevantes": {"01_ficha_tecnica.md#1"}},
    {"pregunta": "¿sirve para gaming?",  # dos chunks lo responden: la ficha y la pregunta frecuente
     "ids_relevantes": {"05_preguntas_frecuentes.md#0", "01_ficha_tecnica.md#0"}},
    {"pregunta": "¿hace mucho ruido?", "ids_relevantes": {"05_preguntas_frecuentes.md#1"}},
    {"pregunta": "¿le puedo poner otros switches?", "ids_relevantes": {"05_preguntas_frecuentes.md#2"}},
    {"pregunta": "¿trae keycaps de repuesto?", "ids_relevantes": {"06_contenido_de_la_caja.md#0"}},
    # sin respuesta en el corpus: el bot tiene que decir que no sabe
    {"pregunta": "¿cuánto pesa el teclado?", "ids_relevantes": set()},
    {"pregunta": "¿en qué país se fabrica?", "ids_relevantes": set()},
]


def precision_at_k(ids_recuperados: list[str], ids_relevantes: set[str]) -> float:
    """Fracción de los ids recuperados que son relevantes (0.0 si no se recuperó ninguno)."""
    if not ids_recuperados:
        return 0.0
    acertados = [i for i in ids_recuperados if i in ids_relevantes]
    return len(acertados) / len(ids_recuperados)


def recall_at_k(ids_recuperados: list[str], ids_relevantes: set[str]) -> float | None:
    """Fracción de los ids relevantes que se recuperaron (None si el caso no tiene ninguno)."""
    if not ids_relevantes:
        return None
    acertados = [i for i in ids_recuperados if i in ids_relevantes]
    return len(acertados) / len(ids_relevantes)


def promediar(valores) -> float:
    """Promedio que ignora los None y evita dividir por cero."""
    validos = [v for v in valores if v is not None]
    return sum(validos) / len(validos) if validos else 0.0


def evaluar_recuperacion(retriever, casos, k: int = K) -> tuple[list[dict], float, float]:
    """Corre cada caso contra el retriever y promedia precisión y recall de las preguntas CON respuesta.

    Cada resultado guarda también los ids recuperados y la posición del primer relevante (1 = primero),
    para poder ver qué falla, no solo cuánto.
    """
    resultados = []
    for caso in casos:
        chunks = retriever.invoke(caso["pregunta"])
        ids_recuperados = [c.id for c in chunks][:k]
        relevantes = caso["ids_relevantes"]
        posiciones = [i for i, id_ in enumerate(ids_recuperados, start=1) if id_ in relevantes]
        resultados.append({
            "pregunta": caso["pregunta"],
            "sin_respuesta": not relevantes,
            "precision": None if not relevantes else precision_at_k(ids_recuperados, relevantes),
            "recall": recall_at_k(ids_recuperados, relevantes),
            "primer_acierto": posiciones[0] if posiciones else None,
            "recuperados": ids_recuperados,
        })
    con_respuesta = [r for r in resultados if not r["sin_respuesta"]]
    return (resultados, promediar(r["precision"] for r in con_respuesta),
            promediar(r["recall"] for r in con_respuesta))


def precision_maxima(casos, k: int) -> float:
    """Techo de la precisión promedio: con 1 relevante y k=3, ni un retriever perfecto pasa de 0,33."""
    return promediar(min(len(c["ids_relevantes"]), k) / k for c in casos if c["ids_relevantes"])


def formatear(resultados, precision_promedio, recall_promedio, k: int, casos=CASOS_EVALUACION) -> str:
    """Texto del reporte: configuración, una línea por pregunta y los promedios."""
    lineas = [
        f"Fecha: {date.today()}",
        f"Configuracion: k={k}, chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP}, embeddings={MODELO_EMBEDDINGS}",
        f"Casos: {sum(not r['sin_respuesta'] for r in resultados)} con respuesta, "
        f"{sum(r['sin_respuesta'] for r in resultados)} sin respuesta (no entran en los promedios)",
        "",
        "prec  recall  1er acierto  pregunta",
    ]
    for r in resultados:
        if r["sin_respuesta"]:
            lineas.append(f" n/a    n/a        -      {r['pregunta']}   (sin respuesta: {', '.join(r['recuperados'])})")
            continue
        acierto = "-" if r["primer_acierto"] is None else str(r["primer_acierto"])
        marca = "   <-- el relevante no llegó" if r["recall"] == 0 else ""
        lineas.append(f"{r['precision']:.2f}   {r['recall']:.2f}       {acierto:>2}      {r['pregunta']}{marca}")
    lineas += [
        "",
        f"promedio -> precision: {precision_promedio:.3f}  recall: {recall_promedio:.3f}",
        f"precision maxima posible con k={k}: {precision_maxima(casos, k):.3f}",
    ]
    return "\n".join(lineas) + "\n"


def guardar(texto: str, k: int, carpeta: Path = CARPETA_RESULTADOS) -> Path:
    """Guarda la corrida con fecha y configuración en el nombre (no pisa corridas de otra configuración)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{date.today()}_cs{CHUNK_SIZE}_k{k}.txt"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def correr(indice, k: int) -> tuple[list[dict], float, float]:
    retriever = indice.as_retriever(search_kwargs={"k": k})  # el mismo k en el retriever y en la evaluación
    return evaluar_recuperacion(retriever, CASOS_EVALUACION, k=k)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evalúa la recuperación del índice de la campaña.")
    parser.add_argument("--k", type=int, default=K, help=f"chunks a recuperar (por defecto {K}, el del bot)")
    k = parser.parse_args().k

    indice = conectar_indice(crear_embeddings())  # mismo collection_name y ruta que la indexación
    print(f"Índice: {indice._collection.name} · {indice._collection.count()} chunks · {len(CASOS_EVALUACION)} preguntas\n")

    primera = correr(indice, k)
    texto = formatear(*primera, k=k)
    print(texto)
    print(f"Guardado en {guardar(texto, k).relative_to(RAIZ)}")

    segunda = correr(indice, k)  # chequeo 1: sobre un índice que no cambió, tiene que dar idéntico
    print(f"\nSegunda corrida con k={k} idéntica a la primera: {segunda == primera}")

    k_mayor = k + 2  # chequeo 2: el trade-off (recall igual o mayor, precisión igual o menor)
    mayor = correr(indice, k_mayor)
    print(f"\n--- k={k_mayor} ---")
    print(f"promedio -> precision: {mayor[1]:.3f}  recall: {mayor[2]:.3f}")
    print(f"recall subió o se mantuvo (k={k} -> k={k_mayor}): {mayor[2] >= primera[2]}")
    print(f"precisión bajó o se mantuvo (k={k} -> k={k_mayor}): {mayor[1] <= primera[1]}")
    print(f"Guardado en {guardar(formatear(*mayor, k=k_mayor), k_mayor).relative_to(RAIZ)}")
