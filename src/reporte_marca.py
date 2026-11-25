"""Reporte post-stream para la marca, con aprobación humana antes de enviarlo.

El grafo arma el reporte desde las trazas y se detiene hasta que alguien elige qué comentarios
incluir y aprueba o rechaza el envío. El reporte no incluye nombres de viewers.

Uso:
    python3 src/reporte_marca.py
    python3 src/reporte_marca.py --pendientes
    python3 src/reporte_marca.py --aprobar THREAD_ID --comentarios c1,c3
    python3 src/reporte_marca.py --rechazar THREAD_ID
    python3 src/reporte_marca.py --interactivo     el flujo por consola del Bloque 23
"""
import argparse
import getpass
import logging
import sqlite3
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

import supervision
import trazas
from indexar_corpus import RAIZ

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
    intentos: list[dict] = []
    for registro in registros:
        if registro.get("inyeccion"):  # Gate 2: el viewer queda marcado (por su huella) para la revisión humana
            intentos.append({"viewer": registro.get("viewer", "?"), "patrones": registro["inyeccion"],
                             "momento": registro.get("timestamp", "")})
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
        "intentos_inyeccion": intentos,
    }


def revisar_comentarios(comentarios: list[dict]) -> list[dict]:
    """Pide aprobación humana para cada comentario marcado. Devuelve solo los aprobados."""
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
        f"- Mensajes bloqueados por intentar manipular al bot: {len(datos.get('intentos_inyeccion', []))} "
        f"(de {len({i['viewer'] for i in datos.get('intentos_inyeccion', [])})} viewer/s; no se respondieron)",
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


# --- Aprobación como grafo de LangGraph (se detiene hasta que alguien decide) ---

ARCHIVO_CHECKPOINTS = RAIZ / "checkpoints" / "reporte.db"
MOTIVO = "aprobar el envío del reporte post-stream a la marca"


class EstadoReporte(TypedDict, total=False):
    datos: dict
    comentarios: list[dict]
    aprobado: bool
    comentarios_aprobados: list[str]
    decidido_por: str
    reporte: str
    resultado: str


def construir_grafo(checkpointer, archivo_trazas=None, archivo_reporte=None):
    """preparar -> revisar (interrupt) -> enviar. Los archivos se pueden cambiar (las pruebas usan temporales)."""

    def preparar(estado: EstadoReporte):
        datos = datos_del_stream(trazas.leer_trazas(archivo_trazas))
        comentarios = [{"id": f"c{n}", "mensaje": c["mensaje"], "motivo": c["motivo"]}  # sin el viewer
                       for n, c in enumerate(datos.pop("comentarios_marcados"), start=1)]
        return {"datos": datos, "comentarios": comentarios}

    def revisar(estado: EstadoReporte):
        """Solo pregunta (al reanudar se vuelve a ejecutar desde aquí): nada que no se pueda repetir."""
        decision = interrupt({
            "motivo": MOTIVO,
            "resumen": armar_reporte({**estado["datos"], "comentarios_marcados": estado["comentarios"]}, []),
            "comentarios": estado["comentarios"],
            # Para quien revisa, no para la marca: la huella del viewer permite identificarlo y moderarlo
            # (privacidad.huella("nombre") da la misma huella), sin que el nombre quede escrito en ningún archivo.
            "intentos_inyeccion": estado["datos"].get("intentos_inyeccion", []),
        })
        if not isinstance(decision, dict):
            decision = {"aprobado": decision}
        ids = {c["id"] for c in estado["comentarios"]}
        aprobado = decision.get("aprobado") is True  # "no", "si", 1: nada que no sea True envía
        return {"aprobado": aprobado, "decidido_por": decision.get("por", "desconocido"),
                "comentarios_aprobados": [i for i in decision.get("comentarios", []) if i in ids] if aprobado else []}

    def enviar(estado: EstadoReporte):
        incluidos = [c for c in estado["comentarios"] if c["id"] in estado["comentarios_aprobados"]]
        for comentario in estado["comentarios"]:
            supervision.registrar_aprobacion("incluir_comentario_en_reporte", comentario,
                                             comentario in incluidos)
        reporte = armar_reporte({**estado["datos"], "comentarios_marcados": estado["comentarios"]}, incluidos)
        supervision.registrar_aprobacion("enviar_reporte_a_marca", {"reporte": reporte}, estado["aprobado"])
        if not estado["aprobado"]:
            return {"resultado": "reporte NO enviado"}
        REPORTES_ENVIADOS.append(reporte)
        Path(archivo_reporte or ARCHIVO_REPORTE).write_text(reporte, encoding="utf-8")  # simulación del envío
        return {"reporte": reporte, "resultado": f"reporte enviado con {len(incluidos)} comentario(s)"}

    grafo = StateGraph(EstadoReporte)
    grafo.add_node("preparar", preparar)
    grafo.add_node("revisar", revisar)
    grafo.add_node("enviar", enviar)
    grafo.add_edge(START, "preparar")
    grafo.add_edge("preparar", "revisar")
    grafo.add_edge("revisar", "enviar")
    grafo.add_edge("enviar", END)
    return grafo.compile(checkpointer=checkpointer)


def app_durable(archivo=ARCHIVO_CHECKPOINTS, archivo_trazas=None, archivo_reporte=None):
    from langgraph.checkpoint.sqlite import SqliteSaver

    Path(archivo).parent.mkdir(parents=True, exist_ok=True)
    return construir_grafo(SqliteSaver(sqlite3.connect(archivo, check_same_thread=False)),
                           archivo_trazas, archivo_reporte)


def config_de(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def preparar_reporte(app) -> tuple[str, dict]:
    """Corre hasta el interrupt con un thread_id nuevo. Devuelve (thread_id, lo que la persona revisa)."""
    thread_id = f"reporte-{uuid.uuid4().hex[:8]}"
    resultado = app.invoke({}, config=config_de(thread_id))
    return thread_id, resultado["__interrupt__"][0].value


def pendientes(app) -> list[tuple[str, dict]]:
    hilos = {c.config["configurable"]["thread_id"] for c in app.checkpointer.list(None)}
    return [(h, app.get_state(config_de(h)).interrupts[0].value) for h in sorted(hilos)
            if app.get_state(config_de(h)).next and app.get_state(config_de(h)).interrupts]


def resolver(app, thread_id: str, aprobar: bool, comentarios: list[str], por: str) -> dict:
    """Reanuda solo si ese hilo espera una decisión y los comentarios elegidos existen."""
    if not isinstance(aprobar, bool):
        raise TypeError(f"la decisión tiene que ser True o False, no {aprobar!r}")
    snapshot = app.get_state(config_de(thread_id))
    if not snapshot.next:
        raise ValueError(f"{thread_id} no tiene ningún reporte pendiente (no existe o ya se decidió)")
    desconocidos = set(comentarios) - {c["id"] for c in snapshot.values.get("comentarios", [])}
    if desconocidos:
        raise ValueError(f"comentarios que no están en el reporte: {sorted(desconocidos)}")
    return app.invoke(Command(resume={"aprobado": aprobar, "comentarios": comentarios, "por": por}),
                      config=config_de(thread_id))


def mostrar_pendiente(thread_id: str, valor: dict) -> None:
    print(f"\n{thread_id} · {valor['motivo']}\n")
    print(valor["resumen"])
    if valor.get("intentos_inyeccion"):
        print("Viewers que intentaron manipular al bot (solo para tu revisión; a la marca le llega el número):")
        for i in valor["intentos_inyeccion"]:
            print(f"  viewer {i['viewer']} · {i['momento'][:19]} · {', '.join(i['patrones'])}")
    print("Comentarios marcados por el bot (redactados; elige cuáles van):")
    for c in valor["comentarios"] or [{"id": "-", "mensaje": "ninguno", "motivo": ""}]:
        print(f"  {c['id']}: «{c['mensaje']}» ({c['motivo']})")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Reporte post-stream con aprobación humana.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--pendientes", action="store_true")
    grupo.add_argument("--aprobar", metavar="THREAD_ID")
    grupo.add_argument("--rechazar", metavar="THREAD_ID")
    grupo.add_argument("--interactivo", action="store_true", help="el flujo por consola del Bloque 23")
    parser.add_argument("--comentarios", default="", help="ids a incluir, separados por coma (ej.: c1,c3)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

    if args.interactivo:
        registros = trazas.leer_trazas()
        if registros:
            datos = datos_del_stream(registros)
            aprobados = revisar_comentarios(datos["comentarios_marcados"])
            enviado = enviar_reporte_a_marca(armar_reporte(datos, aprobados))
            print("✅ Reporte enviado" if enviado else "⛔ Reporte NO enviado")
        return

    app = app_durable()
    if args.pendientes:
        lista = pendientes(app)
        print(f"{len(lista)} reporte(s) esperando una decisión")
        for thread_id, valor in lista:
            mostrar_pendiente(thread_id, valor)
    elif args.aprobar or args.rechazar:
        ids = [c.strip() for c in args.comentarios.split(",") if c.strip()]
        final = resolver(app, args.aprobar or args.rechazar, bool(args.aprobar), ids, por=getpass.getuser())
        print(f"{final['resultado']} (decidido por {final['decidido_por']})")
        if final.get("reporte"):
            print(f"\n{final['reporte']}\nGuardado en {ARCHIVO_REPORTE} (simula el envío).")
    else:
        thread_id, valor = preparar_reporte(app)
        mostrar_pendiente(thread_id, valor)
        print(f"\n⏸  Pendiente de aprobación. Nada se envía hasta que decidas:\n"
              f"  python3 src/reporte_marca.py --aprobar {thread_id} --comentarios c1,c2\n"
              f"  python3 src/reporte_marca.py --rechazar {thread_id}")


if __name__ == "__main__":
    try:
        _cli()
    except (ValueError, TypeError) as error:
        sys.exit(f"No se pudo: {error}")
