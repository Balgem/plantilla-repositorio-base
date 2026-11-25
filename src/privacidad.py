"""Huellas y redacción de datos personales para logs y trazas.

huella() usa HMAC con una clave propia (CLAVE_HUELLAS en .env, o logs/.clave_huellas, que se crea sola).
redactar() reemplaza correos, RUT, teléfonos y links ajenos a la campaña por una etiqueta.
"""
import hashlib
import hmac
import os
import re
import secrets
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_CLAVE = RAIZ / "logs" / ".clave_huellas"
LINK_OFICIAL = "https://ejemplo.cl/r/k7"

PATRONES_PII = {
    "correo": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "rut": re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b"),
    # Celulares chilenos (+56 9 1234 5678) y cualquier número de 8 o más dígitos seguidos.
    # Los precios ("59.990", "3.990") llevan punto de miles y no calzan.
    "telefono": re.compile(r"(?<![\w.])(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?![\w.])|(?<![\w.])\d{8,}(?![\w.])"),
    "link": re.compile(r"(?:https?://|www\.)[^\s)\]]+|\b[\w-]+\.(?:com|cl|ly|net|org|gg|tv|io)(?:/[^\s)\]]*)?",
                       re.IGNORECASE),
}


@lru_cache(maxsize=1)
def _clave() -> bytes:
    desde_env = os.getenv("CLAVE_HUELLAS")
    if desde_env:
        return desde_env.encode("utf-8")
    try:
        if ARCHIVO_CLAVE.exists():
            return ARCHIVO_CLAVE.read_text(encoding="utf-8").strip().encode("utf-8")
        ARCHIVO_CLAVE.parent.mkdir(parents=True, exist_ok=True)
        clave = secrets.token_hex(32)
        ARCHIVO_CLAVE.write_text(clave, encoding="utf-8")
        ARCHIVO_CLAVE.chmod(0o600)
        return clave.encode("utf-8")
    except OSError:  # sin disco escribible: una clave solo para este proceso (las huellas no se comparan entre corridas)
        return secrets.token_bytes(32)


def huella(texto: str) -> str:
    """12 caracteres hex. Mismo texto -> misma huella en esta instalación; sin la clave, no se puede revertir."""
    return hmac.new(_clave(), (texto or "").encode("utf-8"), hashlib.sha256).hexdigest()[:12]


def contiene_pii(texto: str) -> list[str]:
    """Qué tipos de dato personal aparecen (el link oficial de la campaña no cuenta)."""
    encontrados, resto = [], texto or ""
    for nombre, patron in PATRONES_PII.items():  # en orden: el dominio de un correo no cuenta además como link
        coincidencias = [m.group(0) for m in patron.finditer(resto)]
        resto = patron.sub(" ", resto)
        if nombre == "link":
            coincidencias = [c for c in coincidencias if not c.startswith(LINK_OFICIAL) and "ejemplo.cl" not in c]
        if coincidencias:
            encontrados.append(nombre)
    return encontrados


DATOS_PERSONALES = ("correo", "rut", "telefono")


def redactar(texto: str, tipos=tuple(PATRONES_PII)) -> str:
    """Reemplaza cada dato personal por [correo], [rut], [telefono] o [link]. El link oficial se deja."""
    if not texto:
        return texto
    resultado = texto
    for nombre, patron in PATRONES_PII.items():
        if nombre not in tipos:
            continue
        def etiqueta(m, nombre=nombre):
            if nombre == "link" and (m.group(0).startswith(LINK_OFICIAL) or "ejemplo.cl" in m.group(0)):
                return m.group(0)
            return f"[{nombre}]"
        resultado = patron.sub(etiqueta, resultado)
    return resultado


def resumen_texto(texto: str) -> dict:
    """Lo que se puede registrar de un texto de un viewer: su largo, su huella y qué tipos de PII traía."""
    return {"largo": len(texto or ""), "huella": huella(texto), "pii": contiene_pii(texto)}
