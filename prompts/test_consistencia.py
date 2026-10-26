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
from cliente import consultar_modelo  # noqa: E402
from consumir_gemini import parsear_respuesta_json  # noqa: E402

INTENTOS = 3
PAUSA_SEGUNDOS = 2


registro = {"fecha": date.today().isoformat(), "intentos_por_prompt": INTENTOS, "prompts": {}}

for prompt in BANCO_DE_PROMPTS:
    exitos = 0
    fallos = []
    for intento in range(INTENTOS):
        try:
            texto = consultar_modelo(
                prompt["ejemplo_usuario"],
                prompt["system_instruction"],
                prompt.get("response_schema"),
            )
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
