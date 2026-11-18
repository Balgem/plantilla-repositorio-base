"""Decisión fundamentada de personalización para el clasificador del chat (Bloque 30).

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/decision.py            # mide la evidencia (40 llamadas a Gemini), puntúa y arma el esqueleto
    python3 src/decision.py --sin-api  # puntúa con la última evidencia guardada, sin llamar a la API

Paso 0 (evidencia): el criterio de "problema_de_formato_o_tono" pide revisar 20 respuestas reales y contar
cuántas no cumplen el formato. Se usan los 20 mensajes etiquetados del dataset del Bloque 29 que tienen una
categoría de la chain actual (5 por categoría) y se pasan por el clasificador que el bot usa hoy (el primer
paso de cadena_tres_pasos.py). Para comparar, los mismos 20 se pasan con salida estructurada (with_structured_output
+ categorías cerradas), una alternativa que no necesita entrenar nada.

Paso 1: las 5 respuestas del método, cada una con la evidencia que la sustenta.
Paso 2: el esqueleto de docs/decision_personalizacion.md. Si el documento ya existe (completado a mano), NO se
pisa: el esqueleto nuevo se escribe en docs/decision_personalizacion_esqueleto.md.
"""
import argparse
import json
from datetime import date
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from dataset_tuning import EJEMPLOS_RAW, REGLA_RESPONDER
from indexar_corpus import RAIZ

CATEGORIAS_CHAIN = ("pregunta_producto", "interes_compra", "spam", "otro")  # las del prompt actual (Bloque 18)
UMBRAL_FORMATO = 3            # 3 de 20 (15 %) incumplen -> hay problema de formato (criterio de la actividad)
UMBRAL_DATASET = 200          # ejemplos etiquetados para considerar el dataset "grande"
ARCHIVO_EVIDENCIA = RAIZ / "docs" / "evidencia_clasificador.json"
ARCHIVO_DECISION = RAIZ / "docs" / "decision_personalizacion.md"

MUESTRA = [(texto, s["categoria"]) for texto, s in EJEMPLOS_RAW if s["categoria"] in CATEGORIAS_CHAIN]


class Clasificacion(BaseModel):
    """Salida estructurada: la API solo puede devolver una de las categorías de la chain."""

    categoria: Literal["pregunta_producto", "interes_compra", "spam", "otro"] = Field(
        description="Tipo de mensaje del chat de Twitch con una campaña publicitaria.")


# --- Paso 0: evidencia ---


def revisar_salida(cruda: str, esperada: str) -> dict:
    """Formato estricto: la salida tiene que ser EXACTAMENTE una de las categorías (sin mayúsculas, punto ni texto
    extra). La chain hoy compensa con .strip().lower(), así que también se mide si ESO alcanza (categoria_normalizada)."""
    normalizada = cruda.strip().lower()
    return {
        "cruda": cruda,
        "formato_ok": cruda.strip() in CATEGORIAS_CHAIN,
        "categoria_normalizada": normalizada if normalizada in CATEGORIAS_CHAIN else None,
        "correcta": normalizada == esperada,
    }


def medir(clasificar, muestra=MUESTRA) -> dict:
    """Pasa la muestra por una función clasificar(texto) -> str y resume formato y aciertos."""
    filas = []
    for texto, esperada in muestra:
        try:
            cruda = clasificar(texto)
        except Exception as error:  # una salida que ni siquiera se pudo leer también es un incumplimiento
            cruda = f"<error: {type(error).__name__}>"
        filas.append({"mensaje": texto, "esperada": esperada, **revisar_salida(cruda, esperada)})
    return {
        "muestra": len(filas),
        "formato_incumplido": sum(not f["formato_ok"] for f in filas),
        "fuera_de_lista_aun_normalizando": sum(f["categoria_normalizada"] is None for f in filas),
        "aciertos": sum(f["correcta"] for f in filas),
        "filas": filas,
    }


def clasificador_actual(modelo):
    """El primer paso de la chain del Bloque 18, tal cual lo usa el bot (sin el .strip().lower() de después)."""
    from langchain_core.output_parsers import StrOutputParser

    from cadena_tres_pasos import plantilla_clasificar

    cadena = plantilla_clasificar | modelo | StrOutputParser()
    return lambda texto: cadena.invoke({"mensaje": texto})


def clasificador_estructurado(modelo):
    """El mismo prompt, pero con salida estructurada: la API obliga a una de las 4 categorías."""
    from cadena_tres_pasos import plantilla_clasificar

    cadena = plantilla_clasificar | modelo.with_structured_output(Clasificacion)
    return lambda texto: cadena.invoke({"mensaje": texto}).categoria


def medir_evidencia() -> dict:
    from cadena_tres_pasos import crear_modelo

    load_dotenv()
    modelo = crear_modelo()
    evidencia = {
        "fecha": str(date.today()),
        "prompt_actual": medir(clasificador_actual(modelo)),
        "salida_estructurada": medir(clasificador_estructurado(modelo)),
        "ejemplos_etiquetados": len(EJEMPLOS_RAW),
    }
    ARCHIVO_EVIDENCIA.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO_EVIDENCIA.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidencia


# --- Paso 1: el método ---


def recomendar_estrategia(respuestas: dict[str, bool]) -> tuple[dict[str, int], list[str]]:
    """El método de la lección 2, con los empates reportados. Exige bool: un "no" sería verdadero en silencio."""
    for clave, valor in respuestas.items():
        if not isinstance(valor, bool):
            raise TypeError(f"{clave} tiene que ser True o False, no {valor!r}")
    puntos = {"RAG": 0, "Fine-tuning completo": 0, "PEFT": 0}
    if respuestas["informacion_cambia_seguido"]:
        puntos["RAG"] += 3
    if respuestas["problema_de_formato_o_tono"]:
        puntos["PEFT"] += 2
        puntos["Fine-tuning completo"] += 1
    if respuestas["dataset_grande_y_de_calidad"]:
        puntos["Fine-tuning completo"] += 2
        puntos["PEFT"] += 1
    if respuestas["presupuesto_limitado_o_iterar_rapido"]:
        puntos["RAG"] += 2
        puntos["PEFT"] += 1
    if respuestas["necesita_multiples_variantes"]:
        puntos["PEFT"] += 2
    maximo = max(puntos.values())
    return puntos, [t for t, p in puntos.items() if p == maximo]


def responder_preguntas(evidencia: dict) -> dict[str, tuple[bool, str]]:
    """Cada respuesta con el hecho que la sustenta. Las dos medibles salen de la evidencia, no de una impresión."""
    actual = evidencia["prompt_actual"]
    n = evidencia["ejemplos_etiquetados"]
    return {
        "informacion_cambia_seguido": (
            False, "las categorías del clasificador son las mismas desde el Bloque 18 (más comentario_negativo en el 23); "
                   "lo que cambia por campaña son los datos del producto, y eso ya lo resuelve el RAG"),
        "problema_de_formato_o_tono": (
            actual["formato_incumplido"] >= UMBRAL_FORMATO,
            f"de {actual['muestra']} respuestas reales del prompt actual, {actual['formato_incumplido']} no cumplen el "
            f"formato exacto (umbral: {UMBRAL_FORMATO})"),
        "dataset_grande_y_de_calidad": (
            n >= UMBRAL_DATASET, f"hay {n} ejemplos etiquetados y validados (umbral: {UMBRAL_DATASET})"),
        "presupuesto_limitado_o_iterar_rapido": (
            True, "proyecto de curso con llave del nivel gratuito; quiero ver el efecto de un cambio en el mismo día"),
        "necesita_multiples_variantes": (
            False, "un solo clasificador: las categorías son las mismas para cualquier marca o campaña"),
    }


def sensibilidad(respuestas: dict[str, bool]) -> list[tuple[str, bool, list[str], bool]]:
    """Cambia una respuesta a la vez: (clave, nuevo valor, ganadoras, si cambió el resultado)."""
    _, base = recomendar_estrategia(respuestas)
    filas = []
    for clave in respuestas:
        variante = dict(respuestas)
        variante[clave] = not variante[clave]
        _, ganadoras = recomendar_estrategia(variante)
        filas.append((clave, variante[clave], ganadoras, set(ganadoras) != set(base)))
    return filas


# --- Paso 2: el esqueleto ---


def generar_esqueleto_decision(problema: str, puntos: dict[str, int], ganadoras: list[str]) -> str:
    empate = len(ganadoras) > 1
    lineas = ["# Decision de personalizacion", "", "## 1. El problema", problema, "",
              "## 2. Resultado del metodo de decision"]
    lineas += [f"- {tecnica}: {p} puntos" for tecnica, p in sorted(puntos.items(), key=lambda x: -x[1])]
    if empate:
        lineas += ["", f"**Empate entre: {', '.join(ganadoras)}**"]
    lineas += ["", "## 3. Tecnica elegida y por que"]
    lineas.append("[COMPLETAR: el puntaje no resolvio el empate solo -- justifica aqui con criterio propio]" if empate
                  else f"[COMPLETAR: por que {ganadoras[0]} responde mejor a este caso]")
    lineas += ["", "## 4. Que necesitarias para ejecutarla",
               "[COMPLETAR: corpus faltante, o cantidad de ejemplos etiquetados que faltan]"]
    return "\n".join(lineas) + "\n"


def guardar_esqueleto(texto: str, archivo=None):
    """No pisa el documento completado a mano: si ya existe, el esqueleto va a un archivo aparte."""
    ruta = archivo or ARCHIVO_DECISION
    if ruta.exists():
        ruta = ruta.with_name(ruta.stem + "_esqueleto.md")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def titulo(texto: str) -> None:
    print(f"\n{'=' * 66}\n{texto}\n{'=' * 66}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decisión de personalización del clasificador del chat.")
    parser.add_argument("--sin-api", action="store_true", help="usar la última evidencia guardada")
    sin_api = parser.parse_args().sin_api

    titulo("PASO 0: evidencia (20 mensajes etiquetados, 5 por categoría de la chain)")
    evidencia = json.loads(ARCHIVO_EVIDENCIA.read_text(encoding="utf-8")) if sin_api else medir_evidencia()
    for nombre in ("prompt_actual", "salida_estructurada"):
        m = evidencia[nombre]
        print(f"{nombre:20} formato incumplido: {m['formato_incumplido']:>2}/{m['muestra']} · "
              f"fuera de la lista aun normalizando: {m['fuera_de_lista_aun_normalizando']:>2} · "
              f"aciertos: {m['aciertos']:>2}/{m['muestra']}")
    for f in evidencia["prompt_actual"]["filas"]:
        if not f["formato_ok"] or not f["correcta"]:
            print(f"   prompt actual -> {f['cruda']!r:28} esperada {f['esperada']:18} «{f['mensaje']}»")

    titulo("PASO 1: el método sobre mi caso")
    preguntas = responder_preguntas(evidencia)
    respuestas = {clave: valor for clave, (valor, _) in preguntas.items()}
    for clave, (valor, porque) in preguntas.items():
        print(f"{clave:38} {str(valor):5}  ({porque})")
    puntos, ganadoras = recomendar_estrategia(respuestas)
    print(f"\n{puntos}\ncandidatas: {ganadoras}")

    titulo("Sensibilidad: una respuesta distinta a la vez")
    for clave, valor, g, cambia in sensibilidad(respuestas):
        print(f"{clave} -> {valor}: {g}  [{'CAMBIA' if cambia else 'igual'}]")

    titulo("PASO 2: esqueleto del documento")
    problema = ("El primer paso del bot clasifica cada mensaje del chat (pregunta de producto, interés de compra, spam u "
                "otro) con un prompt, y necesito que la salida sea siempre exactamente una de esas categorías y la correcta.")
    ruta = guardar_esqueleto(generar_esqueleto_decision(problema, puntos, ganadoras))
    print(f"Guardado en {ruta.relative_to(RAIZ)}")
    assert set(REGLA_RESPONDER) >= set(CATEGORIAS_CHAIN)
