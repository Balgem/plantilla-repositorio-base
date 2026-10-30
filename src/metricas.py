"""Métricas de evaluación de texto: precisión, cobertura y F1 por coincidencia de palabras.

Comparan una respuesta generada contra una referencia, contando repeticiones (Counter).
Miden qué tan parecida es la elección de palabras, no si la respuesta es correcta:
no reconocen sinónimos, no detectan un dato equivocado (un precio distinto cuenta como
"una palabra más") y casi no cambian si falta una negación.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/metricas.py
Evalúa respuestas reales del bot y guarda el resultado en docs/resultados_metricas.json.
"""
import json
import os
import time
from collections import Counter
from datetime import date
from pathlib import Path

from cliente import consultar_modelo
from consumir_gemini import INSTRUCCION_BOT
from pipeline_texto import procesar_texto, quitar_categoria

ARCHIVO_RESULTADOS = Path(__file__).resolve().parent.parent / "docs" / "resultados_metricas.json"


def contar_coincidencias(tokens_referencia: list[str], tokens_respuesta: list[str]) -> int:
    """Cuenta las palabras en común, tomando para cada una el mínimo de veces que aparece en cada lado."""
    interseccion = Counter(tokens_referencia) & Counter(tokens_respuesta)
    return sum(interseccion.values())


def calcular_precision_cobertura_f1(tokens_referencia: list[str], tokens_respuesta: list[str]) -> dict[str, float]:
    """Precisión (cuánto de la respuesta está en la referencia), cobertura (cuánto de la referencia
    dijo la respuesta) y F1 (las dos combinadas). Si alguna lista está vacía, devuelve todo en 0.0.
    """
    if not tokens_referencia or not tokens_respuesta:
        return {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}
    coincidencias = contar_coincidencias(tokens_referencia, tokens_respuesta)
    precision = coincidencias / len(tokens_respuesta)
    cobertura = coincidencias / len(tokens_referencia)
    f1 = 0.0 if precision + cobertura == 0 else 2 * precision * cobertura / (precision + cobertura)
    return {"precision": precision, "cobertura": cobertura, "f1": f1}


def calcular_metricas(texto_referencia: str, texto_respuesta: str) -> dict[str, float]:
    """Procesa los dos textos y calcula las métricas, para no olvidar procesar uno de los lados."""
    return calcular_precision_cobertura_f1(procesar_texto(texto_referencia), procesar_texto(texto_respuesta))


def resumir_metricas(resultados: list[dict]) -> dict[str, float]:
    """Promedio de precisión, cobertura y F1. Esconde los casos individuales: es solo una primera lectura."""
    if not resultados:
        return {"precision_promedio": 0.0, "cobertura_promedio": 0.0, "f1_promedio": 0.0}
    n = len(resultados)
    return {
        "precision_promedio": sum(r["precision"] for r in resultados) / n,
        "cobertura_promedio": sum(r["cobertura"] for r in resultados) / n,
        "f1_promedio": sum(r["f1"] for r in resultados) / n,
    }


def peores_casos(resultados: list[dict], cantidad: int = 3) -> list[dict]:
    """Los casos con F1 más bajo primero: por ahí conviene empezar a leer."""
    return sorted(resultados, key=lambda r: r["f1"])[:cantidad]


# Mensajes del chat y la respuesta de referencia que escribí con los datos de la campaña.
# Incluyen preguntas con respuesta en la campaña, preguntas sin respuesta (el bot debe decir que no sabe)
# y casos difíciles: descuentos, otra moneda, otro idioma y pedidos de datos que la campaña no tiene.
LINK = "https://ejemplo.cl/r/k7"
NO_SE = f"No tengo esa información, revisa el link {LINK}"
CASOS = [
    ("cuánto cuesta el teclado??", f"El teclado mecánico K7 cuesta 59.990 CLP. Cómpralo en {LINK}"),
    ("precio?", f"El K7 cuesta 59.990 CLP. Cómpralo en {LINK}"),
    ("dónde lo compro", f"Cómpralo en {LINK}"),
    ("lo quiero!! pásame el link", f"Cómpralo en {LINK}"),
    ("me lo compro altiro, cómo hago?", f"Cómpralo en {LINK}"),
    ("el teclado es mecánico de verdad?", f"Sí, el K7 es un teclado mecánico. Revisa el link {LINK}"),
    ("qué teclado estás usando?", f"Es el teclado mecánico K7, cuesta 59.990 CLP. Revisa el link {LINK}"),
    ("tiene descuento?", f"No hay descuentos, revisa el link {LINK}"),
    ("compro 2 si me hacen descuento", f"No hay descuentos, revisa el link {LINK}"),
    ("hay algún código de descuento para el chat?", f"No hay descuentos ni códigos, revisa el link {LINK}"),
    ("cuánto sale en dólares?", f"El K7 cuesta 59.990 CLP. Revisa el link {LINK}"),
    ("how much is the keyboard?", f"El teclado mecánico K7 cuesta 59.990 CLP. Revisa el link {LINK}"),
    ("hacen envíos a regiones?", NO_SE),
    ("cuánto demora el envío?", NO_SE),
    ("tiene garantía?", NO_SE),
    ("qué switches trae?", NO_SE),
    ("es inalámbrico?", NO_SE),
    ("sirve para mac?", NO_SE),
    ("viene en color blanco?", NO_SE),
    ("se puede pagar en cuotas?", NO_SE),
]
PAUSA_SEGUNDOS = 2  # entre consultas, para no topar el límite de uso con 20 seguidas


def guardar(resultados: list[dict]) -> None:
    """Guarda los resultados con su resumen. Se llama en cada vuelta para no perder lo avanzado si algo falla."""
    datos = {
        "fecha": date.today().isoformat(),
        "modelo": os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "resumen": {clave: round(valor, 3) for clave, valor in resumir_metricas(resultados).items()},
        "casos": resultados,
    }
    with open(ARCHIVO_RESULTADOS, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    resultados = []
    for mensaje, referencia in CASOS:
        try:
            respuesta = quitar_categoria(consultar_modelo(mensaje, INSTRUCCION_BOT))
        except RuntimeError as error:
            print(f"{mensaje}: sin respuesta ({error})")
            continue
        metricas = calcular_metricas(referencia, respuesta)
        resultados.append({
            "consulta": mensaje,
            "referencia": referencia,
            "respuesta": respuesta,
            **{clave: round(valor, 3) for clave, valor in metricas.items()},
        })
        guardar(resultados)
        time.sleep(PAUSA_SEGUNDOS)

    print(f"\n{'Consulta':<36}{'Precisión':>10}{'Cobertura':>11}{'F1':>7}")
    for r in resultados:
        print(f"{r['consulta']:<36}{r['precision']:>10.2f}{r['cobertura']:>11.2f}{r['f1']:>7.2f}")

    resumen = resumir_metricas(resultados)
    print(f"\nPromedio: precisión {resumen['precision_promedio']:.2f} · "
          f"cobertura {resumen['cobertura_promedio']:.2f} · F1 {resumen['f1_promedio']:.2f}")

    # Muestra para la revisión manual: los 5 peores y los 5 mejores (sin repetir si hay pocos resultados).
    ordenados = peores_casos(resultados, len(resultados))
    muestra = ordenados[:5] + [r for r in ordenados[-5:] if r not in ordenados[:5]]
    print(f"\nMuestra para revisar a mano ({len(muestra)} casos: los 5 peores y los 5 mejores):")
    for r in muestra:
        print(f"\n  F1 {r['f1']:.2f} · P {r['precision']:.2f} · C {r['cobertura']:.2f} · {r['consulta']}"
              f"\n    Referencia: {r['referencia']}\n    Respuesta:  {r['respuesta']}")

    print(f"\nResultados guardados en docs/{ARCHIVO_RESULTADOS.name}")
