"""Supervisión humana (Bloque 23): pedir aprobación con límite de tiempo y registrar cada decisión.

Se usa en el reporte post-stream (src/reporte_marca.py), que es donde están las acciones de riesgo alto:
lo que se manda a la marca ya no se puede retirar. El agente en vivo no tiene acciones de riesgo alto.

El archivo aprobaciones.jsonl queda en .gitignore: tiene comentarios de viewers.
"""
import getpass
import json
import logging
import select
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

TIEMPO_LIMITE_APROBACION = 300  # segundos; post-stream no hay apuro, pero tampoco se espera para siempre
ARCHIVO_APROBACIONES = Path("aprobaciones.jsonl")
registro_aprobaciones: list[dict] = []


def esperar_aprobacion(mensaje: str, tiempo_limite_segundos: float = TIEMPO_LIMITE_APROBACION) -> bool:
    """Pide una confirmación por consola (s/n) con límite de tiempo. Ante cualquier duda, devuelve False.

    - Sin respuesta a tiempo: False (para una acción de riesgo alto, lo seguro es NO ejecutarla).
    - Sin una consola interactiva (dentro de pytest, o en un proceso sin terminal): False.
    select() sobre stdin funciona en Linux y macOS; en Windows haría falta un hilo con threading.Event.
    """
    print(mensaje, end="", flush=True)
    try:
        listo, _, _ = select.select([sys.stdin], [], [], tiempo_limite_segundos)
    except (OSError, ValueError, AttributeError) as error:  # sin stdin real (io.UnsupportedOperation es OSError)
        print()
        logger.warning("No hay una consola para pedir aprobación (%s): se toma como NO aprobado.", error)
        return False
    if not listo:
        print()
        logger.warning("Nadie respondió en %s s: se toma como NO aprobado.", tiempo_limite_segundos)
        return False
    return sys.stdin.readline().strip().lower() == "s"


def registrar_aprobacion(accion: str, argumentos: dict, aprobado: bool, archivo=None) -> None:
    """Guarda cada decisión, sea sí o no: qué acción, con qué datos, quién decidió y cuándo.

    Queda en memoria (registro_aprobaciones) y en aprobaciones.jsonl, para poder responder después
    "¿quién aprobó que este comentario fuera a la marca?". Si el archivo falla, se registra el error.
    """
    registro = {
        "accion": accion,
        "argumentos": argumentos,
        "aprobado": aprobado,
        "aprobado_por": getpass.getuser(),
        "momento": datetime.now(timezone.utc).isoformat(),
    }
    registro_aprobaciones.append(registro)
    try:
        with open(archivo or ARCHIVO_APROBACIONES, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    except OSError:
        logger.exception("No se pudo guardar la aprobación de %s", accion)
