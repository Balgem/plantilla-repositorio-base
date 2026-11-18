"""Configuración del entorno en un solo lugar (Gate 2).

La clave de Gemini se acepta con los dos nombres:
- GEMINI_API_KEY: el nombre que usa el curso para el Gate 2 (y el que pondrá quien evalúe en un entorno limpio).
- API_KEY: el nombre que usa este proyecto desde el Gate 1.
"""
import os

NOMBRES_CLAVE = ("GEMINI_API_KEY", "API_KEY")
MENSAJE_SIN_CLAVE = 'Falta la clave de Gemini: define GEMINI_API_KEY (o API_KEY) en tu archivo ".env".'


def clave_api() -> str | None:
    """La clave de Gemini, o None si no está definida con ninguno de los dos nombres. Nunca se imprime.

    No llama a load_dotenv: eso lo hace cada script al arrancar (y las pruebas pueden borrar la variable).
    """
    for nombre in NOMBRES_CLAVE:
        valor = os.getenv(nombre)
        if valor:
            return valor
    return None


def nombre_modelo() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
