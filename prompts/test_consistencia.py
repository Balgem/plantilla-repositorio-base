"""Prueba la consistencia del banco de prompts contra la API real.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 prompts/test_consistencia.py

Guarda el resultado en prompts/registro_resultados.json.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
sys.path.insert(0, str(CARPETA))
sys.path.insert(0, str(CARPETA.parent / "src"))

from banco import BANCO_DE_PROMPTS  # noqa: E402
from consumir_gemini import (  # noqa: E402
    armar_peticion,
    con_reintentos,
    enviar_peticion,
    extraer_texto,
    parsear_respuesta_json,
)

INTENTOS = 3
PAUSA_SEGUNDOS = 2


def pedir_con_reintentos(prompt):
    """Devuelve el texto del modelo; reintenta solo si la API falla por saturación o conexión."""
    url, headers, body = armar_peticion(
        prompt["ejemplo_usuario"],
        prompt["system_instruction"],
        prompt.get("response_schema"),
    )
    respuesta_json, _ = con_reintentos(lambda: enviar_peticion(url, headers, body))
    return extraer_texto(respuesta_json)


registro = {"fecha": date.today().isoformat(), "intentos_por_prompt": INTENTOS, "prompts": {}}

for prompt in BANCO_DE_PROMPTS:
    exitos = 0
    fallos = []
    for intento in range(INTENTOS):
        try:
            texto = pedir_con_reintentos(prompt)
            datos = parsear_respuesta_json(texto, prompt["claves_esperadas"])
            exitos += 1
            print(f"  intento {intento + 1}: {json.dumps(datos, ensure_ascii=False)}")
        except (ValueError, RuntimeError) as error:
            fallos.append(f"intento {intento + 1}: {error}")
            print(f"  intento {intento + 1} falló: {error}")
        time.sleep(PAUSA_SEGUNDOS)
    print(f"{prompt['nombre']}: {exitos}/{INTENTOS} respuestas válidas\n")
    registro["prompts"][prompt["nombre"]] = {"exitos": exitos, "intentos": INTENTOS, "fallos": fallos}

with open(CARPETA / "registro_resultados.json", "w", encoding="utf-8") as archivo:
    json.dump(registro, archivo, indent=2, ensure_ascii=False)
print("Registro guardado en prompts/registro_resultados.json")
