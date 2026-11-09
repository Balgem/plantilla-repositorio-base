"""Reporte post-stream para la marca (Bloque 23).

Se corre cuando termina la transmisión, no durante el chat:
    python3 src/reporte_marca.py

1. Lee la traza del stream (trazas_agente.jsonl) y cuenta qué pasó: turnos, preguntas, interesados en comprar.
2. Toma los comentarios negativos que el agente marcó en vivo y pide aprobación humana para CADA uno:
   solo los aprobados entran al reporte.
3. Muestra el reporte completo y pide aprobación humana para enviarlo.

Pasos 2 y 3 son las acciones de riesgo alto del sistema: lo que llega a la marca no se puede retirar, y un
comentario mal marcado (una broma, un viewer que hablaba de otro producto) termina como crítica oficial.
Sin respuesta a tiempo, el comentario queda fuera y el reporte no se envía.

El reporte no incluye nombres de viewers: la marca recibe lo que se dijo, no quién lo dijo.
"""
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

import supervision
import trazas

logger = logging.getLogger(__name__)

ARCHIVO_REPORTE = Path("reporte_marca.md")  # simula el envío; en .gitignore
REPORTES_ENVIADOS: list[str] = []

# Acciones de riesgo alto del flujo post-stream. tests/test_reporte_marca.py comprueba que cada una
# llame a esperar_aprobacion (el chequeo del grep de la actividad, automático).
ACCIONES_DE_RIESGO_ALTO = {
    "incluir_comentario_en_reporte": "revisar_comentarios",
    "enviar_reporte_a_marca": "enviar_reporte_a_marca",
}


def datos_del_stream(registros: list[dict]) -> dict:
    """Resume la traza: turnos, herramientas usadas, interesados (la última cantidad de cada viewer) y flags."""
    herramientas = Counter()
    interesados: dict[str, int] = {}
    comentarios: list[dict] = []
    for registro in registros:
        for accion in registro.get("acciones", []):
            nombre, argumentos = accion.get("herramienta"), accion.get("argumentos") or {}
            herramientas[nombre] += 1
            if nombre == "registrar_interes_compra":
                interesados[argumentos.get("usuario", "?")] = int(argumentos.get("cantidad", 1))
            elif nombre == "marcar_comentario_negativo":
                clave = (argumentos.get("usuario"), argumentos.get("mensaje"))
                if clave not in {(c["usuario"], c["mensaje"]) for c in comentarios}:  # sin duplicados
                    comentarios.append({"usuario": clave[0], "mensaje": clave[1],
                                        "motivo": argumentos.get("motivo", ""),
                                        "momento": registro.get("timestamp", "")})
    return {
        "turnos": len(registros),
        "con_error": sum(1 for r in registros if r.get("error")),
        "herramientas": dict(herramientas),
        "interesados": len(interesados),
        "unidades": sum(interesados.values()),
        "comentarios_marcados": comentarios,
    }


def revisar_comentarios(comentarios: list[dict]) -> list[dict]:
    """Pide aprobación humana para cada comentario marcado. Devuelve solo los aprobados.

    Cada decisión queda registrada (sí o no). Sin respuesta a tiempo, el comentario NO entra al reporte.
    """
    aprobados = []
    for numero, comentario in enumerate(comentarios, start=1):
        aprobado = supervision.esperar_aprobacion(
            f"\n🚩 Comentario {numero} de {len(comentarios)} marcado por el bot ({comentario['motivo']}):\n"
            f"   «{comentario['mensaje']}»\n¿Incluirlo en el reporte para la marca? (s/n): "
        )
        supervision.registrar_aprobacion("incluir_comentario_en_reporte", comentario, aprobado)
        if aprobado:
            aprobados.append(comentario)
    return aprobados


def armar_reporte(datos: dict, comentarios_aprobados: list[dict]) -> str:
    """Texto del reporte para la marca. Sin nombres de viewers."""
    lineas = [
        f"# Reporte de campaña K7 · {datetime.now():%Y-%m-%d}",
        "",
        f"- Mensajes atendidos por el bot: {datos['turnos']} (sin respuesta por error: {datos['con_error']})",
        f"- Consultas sobre el producto: {datos['herramientas'].get('consultar_campana', 0)}",
        f"- Viewers con interés de compra: {datos['interesados']} ({datos['unidades']} unidades en total)",
        "",
        "## Comentarios negativos (revisados por una persona)",
    ]
    if comentarios_aprobados:
        lineas += [f"- «{c['mensaje']}» ({c['motivo']})" for c in comentarios_aprobados]
    else:
        lineas.append("- Ninguno aprobado para este reporte.")
    descartados = len(datos["comentarios_marcados"]) - len(comentarios_aprobados)
    if descartados:
        lineas.append(f"- ({descartados} comentario/s marcado/s por el bot se descartaron en la revisión.)")
    return "\n".join(lineas) + "\n"


def enviar_reporte_a_marca(reporte: str, archivo=None) -> bool:
    """Muestra el reporte completo y lo envía solo si una persona lo aprueba. La decisión queda registrada."""
    aprobado = supervision.esperar_aprobacion(f"\n{reporte}\n🔴 ¿Enviar este reporte a la marca? (s/n): ")
    supervision.registrar_aprobacion("enviar_reporte_a_marca", {"reporte": reporte}, aprobado)
    if not aprobado:
        return False
    REPORTES_ENVIADOS.append(reporte)
    try:
        Path(archivo or ARCHIVO_REPORTE).write_text(reporte, encoding="utf-8")  # simulación del envío
    except OSError:
        logger.exception("No se pudo guardar el reporte enviado")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    registros = trazas.leer_trazas()
    if registros:
        datos = datos_del_stream(registros)
        print(f"Turnos en la traza: {datos['turnos']} · comentarios marcados: {len(datos['comentarios_marcados'])}")
        print(f"Para cada uno escribe s o n y Enter (tienes {supervision.TIEMPO_LIMITE_APROBACION} s).")
        aprobados = revisar_comentarios(datos["comentarios_marcados"])
        enviado = enviar_reporte_a_marca(armar_reporte(datos, aprobados))
        print(f"\n{'✅ Reporte enviado (simulado en ' + str(ARCHIVO_REPORTE) + ')' if enviado else '⛔ Reporte NO enviado'}")
        print(f"Decisiones registradas en {supervision.ARCHIVO_APROBACIONES}:")
        for decision in supervision.registro_aprobaciones:
            print(f"  {decision['accion']}: {'aprobado' if decision['aprobado'] else 'rechazado'} "
                  f"por {decision['aprobado_por']}")
