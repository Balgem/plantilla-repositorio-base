"""Lectura de la configuración. La clave se acepta como GEMINI_API_KEY o API_KEY.
"""
import os

NOMBRES_CLAVE = ("GEMINI_API_KEY", "API_KEY")
MENSAJE_SIN_CLAVE = 'Falta la clave de Gemini: define GEMINI_API_KEY (o API_KEY) en tu archivo ".env".'


def clave_api() -> str | None:
    """La clave de Gemini, o None si no está definida con ninguno de los dos nombres. Nunca se imprime."""
    for nombre in NOMBRES_CLAVE:
        valor = os.getenv(nombre)
        if valor:
            return valor
    return None


def nombre_modelo() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
