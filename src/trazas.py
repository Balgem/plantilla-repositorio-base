"""Trazas del agente: una línea JSON por turno en trazas_agente.jsonl (Bloque 23).

El viewer queda como huella y su mensaje como largo + huella. Solo se guarda el texto de los
comentarios marcados como negativos, redactado, porque alguien tiene que revisarlos.

Uso:
    python3 src/trazas.py
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from agente_con_herramientas import NIVEL_DE_RIESGO, texto_de_salida
from privacidad import DATOS_PERSONALES, huella, redactar, resumen_texto

logger = logging.getLogger(__name__)

ARCHIVO_TRAZAS = Path("trazas_agente.jsonl")


def registrar_traza(session_id: str, entrada: str, resultado: dict, respuesta_modelo=None,
                    error: str | None = None, archivo=None, inyeccion: list[str] | None = None) -> None:
    """Agrega una interacción del agente a trazas_agente.jsonl (una línea JSON por turno)."""
    acciones = [
        {"herramienta": accion.tool, "argumentos": sin_pii(accion.tool_input), "observacion": redactar(str(observacion))}
        for accion, observacion in resultado.get("intermediate_steps", [])
    ]
    respuesta_final = texto_de_salida(resultado.get("output", ""))
    respuesta_modelo = respuesta_final if respuesta_modelo is None else texto_de_salida(respuesta_modelo)
    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "viewer": huella(session_id),
        "entrada": resumen_texto(entrada),
        "acciones": acciones,
        "respuesta_modelo": redactar(respuesta_modelo, DATOS_PERSONALES),
        "respuesta_final": redactar(respuesta_final, DATOS_PERSONALES),
        "filtro_actuo": respuesta_modelo != respuesta_final,
    }
    if error:
        registro["error"] = redactar(error)
    if inyeccion:  # Gate 2: el mensaje se bloqueó por intento de inyección (nombres de los patrones, no el texto)
        registro["inyeccion"] = inyeccion
    try:
        with open(archivo or ARCHIVO_TRAZAS, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    except OSError:
        logger.exception("No se pudo guardar la traza del viewer %s", huella(session_id))


def sin_pii(argumentos):
    """Argumentos de una herramienta sin datos personales: 'usuario' -> huella; cualquier texto -> redactado."""
    if not isinstance(argumentos, dict):
        return redactar(str(argumentos))
    return {clave: huella(valor) if clave == "usuario" else redactar(valor) if isinstance(valor, str) else valor
            for clave, valor in argumentos.items()}


def describir_entrada(registro: dict) -> str:
    """Cómo se muestra el mensaje de un turno en la revisión: nunca el texto, solo su largo y su huella."""
    entrada = registro.get("entrada")
    if isinstance(entrada, dict):
        pii = f", traía {'/'.join(entrada['pii'])}" if entrada.get("pii") else ""
        return f"mensaje de {entrada.get('largo')} caracteres (huella {entrada.get('huella')}{pii})"
    return "(traza en formato anterior al Gate 2)"


def leer_trazas(archivo=None) -> list[dict]:
    """Lee el archivo de trazas. Las líneas corruptas (a medio escribir o editadas a mano) se saltan con un aviso."""
    ruta = Path(archivo or ARCHIVO_TRAZAS)
    if not ruta.exists():
        print(f"No se encontró '{ruta}'. Corre el bot al menos una vez antes de revisar trazas.")
        return []
    registros = []
    with open(ruta, encoding="utf-8") as f:
        for numero, linea in enumerate(f, start=1):
            if not linea.strip():
                continue
            try:
                registros.append(json.loads(linea))
            except json.JSONDecodeError as error:
                logger.warning("Línea %s de %s no es JSON válido (%s): se salta.", numero, ruta, error)
    return registros


def revisar_trazas(registros: list[dict]) -> dict[str, list[dict]]:
    """Marca candidatas a revisión con los patrones del Bloque 23. No decide si algo está mal."""
    hallazgos = {"repeticiones": [], "riesgo_alto": [], "filtro_actuo": [], "comentarios_marcados": [],
                 "errores": [], "intentos_inyeccion": []}
    for registro in registros:
        herramientas = [a.get("herramienta") for a in registro.get("acciones", [])]
        if any(actual == anterior for anterior, actual in zip(herramientas, herramientas[1:])):
            hallazgos["repeticiones"].append(registro)
        if any(NIVEL_DE_RIESGO.get(h, "alto") == "alto" for h in herramientas):  # desconocida = alto
            hallazgos["riesgo_alto"].append(registro)
        if registro.get("filtro_actuo"):
            hallazgos["filtro_actuo"].append(registro)
        if "marcar_comentario_negativo" in herramientas:
            hallazgos["comentarios_marcados"].append(registro)
        if registro.get("error"):
            hallazgos["errores"].append(registro)
        if registro.get("inyeccion"):
            hallazgos["intentos_inyeccion"].append(registro)
    return hallazgos


TITULOS = {
    "repeticiones": "🔄 Misma herramienta dos veces seguidas",
    "riesgo_alto": "🔴 Herramienta de riesgo alto o sin clasificar en el agente en vivo",
    "filtro_actuo": "🧩 Un filtro cambió la respuesta del modelo",
    "comentarios_marcados": "🚩 Comentarios negativos marcados (pasan por aprobación en el reporte)",
    "errores": "⚠️ El agente falló y no respondió",
    "intentos_inyeccion": "🛡️ Mensajes bloqueados por intento de inyección (no llegaron al agente)",
}


def imprimir_reporte(registros: list[dict], hallazgos: dict[str, list[dict]]) -> None:
    print(f"Trazas leídas: {len(registros)}")
    conteo = {}
    for registro in registros:
        for accion in registro.get("acciones", []):
            conteo[accion.get("herramienta")] = conteo.get(accion.get("herramienta"), 0) + 1
    for herramienta, veces in sorted(conteo.items()):
        print(f"  {herramienta} ({NIVEL_DE_RIESGO.get(herramienta, 'sin clasificar')}): {veces}")
    for clave, titulo in TITULOS.items():
        print(f"\n{titulo}: {len(hallazgos[clave])}")
        for registro in hallazgos[clave]:
            print(f"  - {registro.get('timestamp', '')[:19]} viewer {registro.get('viewer', '?')}: "
                  f"{describir_entrada(registro)}")
            if clave == "filtro_actuo":
                print(f"      modelo:    {registro.get('respuesta_modelo')}")
                print(f"      publicado: {registro.get('respuesta_final')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    trazas = leer_trazas()
    if trazas:
        imprimir_reporte(trazas, revisar_trazas(trazas))
