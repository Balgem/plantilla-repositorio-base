"""Revisión manual de la muestra de respuestas del bot (Bloque 17).

Muestra: los 5 casos con F1 más bajo y los 5 con F1 más alto de las 20 respuestas
de docs/resultados_metricas.json (generadas el 2026-10-30 con gemini-3.5-flash-lite).

Rúbrica, por caso:
- correccion_factual: ¿los datos verificables (precio, link) coinciden con la campaña? si / no / parcialmente
- completitud: ¿cubre lo que cubre la referencia? si / no / parcialmente
- contradiccion: ¿afirma lo contrario de algo de la referencia (por ejemplo, un descuento)? si / no

Uso, desde la raíz del repositorio:
    python3 src/revision_manual.py
Guarda la revisión en docs/revision_manual.json.
"""
import json
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent.parent / "docs" / "revision_manual.json"

revision_manual = [
    # --- Los 5 con F1 más bajo ---
    {
        "consulta": "lo quiero!! pásame el link",
        "f1": 0.11,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Respuesta correcta: da el link y además el precio correcto. El F1 es bajo porque la referencia "
                "es muy corta (4 palabras) y la respuesta agrega saludo y precio: la precisión castiga "
                "información extra que es verdadera. Falso negativo.",
    },
    {
        "consulta": "me lo compro altiro, cómo hago?",
        "f1": 0.15,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Correcta: link y precio bien. Paráfrasis ('Métete a… para llevártelo') en vez de 'Cómpralo en', "
                "más información extra correcta. Falso negativo.",
    },
    {
        "consulta": "cuánto sale en dólares?",
        "f1": 0.36,
        "correccion_factual": "si",
        "completitud": "parcialmente",
        "contradiccion": "no",
        "nota": "Lo importante está bien: no inventó una conversión a dólares. Pero pudo dar el precio en CLP, "
                "que sí conoce. La métrica no distingue 'no inventó' (bueno) de 'omitió un dato' (mejorable).",
    },
    {
        "consulta": "compro 2 si me hacen descuento",
        "f1": 0.42,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Mantiene la negación ('No hay descuentos disponibles') y no acepta el trato. Paráfrasis más larga "
                "que la referencia. Falso negativo.",
    },
    {
        "consulta": "el teclado es mecánico de verdad?",
        "f1": 0.48,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Confirma que es mecánico y agrega el precio correcto, que la referencia no pedía. "
                "La precisión baja por información verdadera. Falso negativo.",
    },
    # --- Los 5 con F1 más alto ---
    {
        "consulta": "hacen envíos a regiones?",
        "f1": 1.0,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Dice que no sabe en vez de inventar, como pide la instrucción. F1 perfecto confirmado: no es un falso positivo.",
    },
    {
        "consulta": "tiene garantía?",
        "f1": 1.0,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Igual que el anterior: frase idéntica a la referencia. Correcta.",
    },
    {
        "consulta": "es inalámbrico?",
        "f1": 1.0,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Correcta. Ojo: los 5 casos con F1 = 1 son la misma frase de 'no sé'. El 1.0 refleja que el bot "
                "repite la plantilla de la instrucción, no que la respuesta sea especialmente buena.",
    },
    {
        "consulta": "viene en color blanco?",
        "f1": 1.0,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Correcta, misma plantilla de 'no sé'.",
    },
    {
        "consulta": "se puede pagar en cuotas?",
        "f1": 1.0,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Correcta, misma plantilla de 'no sé'. Ninguno de los 5 mejores es un falso positivo.",
    },
]

if __name__ == "__main__":
    with open(ARCHIVO, "w", encoding="utf-8") as archivo:
        json.dump(revision_manual, archivo, indent=2, ensure_ascii=False)
    incorrectas = [c for c in revision_manual if c["correccion_factual"] == "no" or c["contradiccion"] == "si"]
    print(f"{len(revision_manual)} casos revisados · {len(incorrectas)} con datos incorrectos o contradicciones")
    print(f"Revisión guardada en docs/{ARCHIVO.name}")
