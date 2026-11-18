"""Punto de supervisión humana para desplegar una versión nueva del prompt (Bloque 32, paso 2).

Uso, desde la raíz del repositorio y con el entorno activo (no llama a la API):
    python3 src/grafo_supervision.py                              # demo: pruebas 2, 3 y 4 sobre una COPIA del registro
    python3 src/grafo_supervision.py --proponer 959478c666ac      # pide la aprobación de verdad y se detiene
    python3 src/grafo_supervision.py --pendientes                 # qué está esperando una decisión
    python3 src/grafo_supervision.py --aprobar <thread_id> --huella 959478c666ac
    python3 src/grafo_supervision.py --rechazar <thread_id> --huella 959478c666ac

Lo que cambia respecto del grafo de la lección:
- "aplicar" ACTIVA o RECHAZA de verdad la versión en prompts/registro_versiones.json, y logging_rag.py lee de
  ahí el prompt activo: aprobar es desplegar.
- El interrupt muestra el DIFF contra la versión activa (lección 1: se aprueba mirando el cambio, no releyendo
  el prompt entero).
- Solo True aprueba: resume="no", "false" o 1 se tratan como rechazo (con resume="no" el grafo de la lección
  activaba la versión).
- El nodo "supervisar" solo pregunta: al reanudar, LangGraph lo vuelve a ejecutar desde su primera línea, así
  que cualquier efecto ahí se repetiría. Los efectos van en "aplicar".
- Para la aprobación real usa SqliteSaver (checkpoints/supervision.db): la propuesta queda pendiente aunque se
  cierre la terminal, y otra persona (u otro proceso, horas después) la puede resolver.
- resolver() comprueba antes de reanudar que el hilo tenga algo pendiente y que la huella sea la que la persona
  revisó (el caso "se aprobó otra versión" de la tabla de errores de la lección).
"""
import argparse
import getpass
import shutil
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from indexar_corpus import RAIZ
from registro_prompts import ARCHIVO_REGISTRO, PROMPT_RAG, RegistroDePrompts, diff_prompts

ARCHIVO_CHECKPOINTS = RAIZ / "checkpoints" / "supervision.db"
MOTIVO = "aprobar nueva version de prompt en produccion"


class EstadoDespliegue(TypedDict, total=False):
    nombre: str
    huella_nueva: str
    huella_activa: str
    diff: list[str]
    aprobado: bool
    decidido_por: str
    resultado: str


def construir_grafo(checkpointer, archivo_registro: Path = ARCHIVO_REGISTRO):
    """El grafo de la lección con el registro real. archivo_registro se puede cambiar (las pruebas usan una copia)."""

    def proponer(estado: EstadoDespliegue):
        """Valida la propuesta ANTES de pedir aprobación: que exista, que esté propuesta, y arma el diff."""
        registro = RegistroDePrompts(archivo_registro)
        nombre = estado.get("nombre", PROMPT_RAG)
        nueva = registro.buscar(nombre, estado["huella_nueva"])
        if nueva is None or nueva["estado"] != "propuesta":
            raise ValueError(f"{estado['huella_nueva']} no es una versión propuesta de {nombre} "
                             f"({'no existe' if nueva is None else nueva['estado']})")
        activa = registro.activa(nombre)
        return {"nombre": nombre, "huella_activa": activa["huella"] if activa else None,
                "diff": diff_prompts(activa["texto"] if activa else "", nueva["texto"])}

    def supervisar(estado: EstadoDespliegue):
        """Solo pregunta. Se vuelve a ejecutar al reanudar: aquí no va nada que no se pueda repetir."""
        decision = interrupt({
            "motivo": MOTIVO,
            "huella_propuesta": estado["huella_nueva"],
            "huella_activa": estado["huella_activa"],
            "diff": estado["diff"],
        })
        if isinstance(decision, dict):  # {"aprobado": True, "por": "Cris"}
            return {"aprobado": decision.get("aprobado") is True, "decidido_por": decision.get("por", "desconocido")}
        return {"aprobado": decision is True, "decidido_por": "desconocido"}

    def aplicar(estado: EstadoDespliegue):
        registro = RegistroDePrompts(archivo_registro)
        if estado["aprobado"] is True:
            registro.activar(estado["nombre"], estado["huella_nueva"], estado["decidido_por"])
            resultado = f"version {estado['huella_nueva']} activada"
        else:
            registro.rechazar(estado["nombre"], estado["huella_nueva"], estado["decidido_por"])
            resultado = f"version {estado['huella_nueva']} rechazada, se mantiene {estado['huella_activa']}"
        registro.guardar()
        print(resultado)
        return {"resultado": resultado}

    grafo = StateGraph(EstadoDespliegue)
    grafo.add_node("proponer", proponer)
    grafo.add_node("supervisar", supervisar)
    grafo.add_node("aplicar", aplicar)
    grafo.add_edge(START, "proponer")
    grafo.add_edge("proponer", "supervisar")
    grafo.add_edge("supervisar", "aplicar")
    grafo.add_edge("aplicar", END)
    return grafo.compile(checkpointer=checkpointer)


def nuevo_thread_id() -> str:
    return f"despliegue-{uuid.uuid4().hex[:8]}"


def config_de(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def proponer_despliegue(app, huella: str, nombre: str = PROMPT_RAG) -> tuple[str, dict]:
    """Corre hasta el interrupt con un thread_id NUEVO. Devuelve (thread_id, lo que la persona tiene que revisar).

    Si esa versión ya espera una decisión en otro hilo, no abre un segundo: dos aprobaciones pendientes para lo
    mismo terminan en que la segunda falla (la versión ya no está "propuesta").
    """
    for otro, valor in pendientes(app):
        if valor["huella_propuesta"] == huella:
            raise ValueError(f"{huella} ya espera una decisión en {otro}")
    thread_id = nuevo_thread_id()
    resultado = app.invoke({"nombre": nombre, "huella_nueva": huella}, config=config_de(thread_id))
    return thread_id, resultado["__interrupt__"][0].value


def resolver(app, thread_id: str, aprobar: bool, huella_revisada: str, por: str):
    """Reanuda solo si hay algo pendiente en ese hilo Y es la versión que la persona revisó."""
    if not isinstance(aprobar, bool):
        raise TypeError(f"la decisión tiene que ser True o False, no {aprobar!r}")
    config = config_de(thread_id)
    snapshot = app.get_state(config)
    if not snapshot.next:
        raise ValueError(f"{thread_id} no tiene ninguna aprobación pendiente (no existe o ya se resolvió)")
    pendiente = snapshot.values.get("huella_nueva")
    if pendiente != huella_revisada:
        raise ValueError(f"{thread_id} espera decidir {pendiente}, no {huella_revisada}: revisa el diff de nuevo")
    return app.invoke(Command(resume={"aprobado": aprobar, "por": por}), config=config)


def pendientes(app) -> list[tuple[str, dict]]:
    """Hilos con un interrupt sin resolver, leídos del checkpointer (no hace falta haber guardado el invoke)."""
    hilos = {c.config["configurable"]["thread_id"] for c in app.checkpointer.list(None)}
    resultado = []
    for thread_id in sorted(hilos):
        snapshot = app.get_state(config_de(thread_id))
        if snapshot.next and snapshot.interrupts:
            resultado.append((thread_id, snapshot.interrupts[0].value))
    return resultado


def app_durable(archivo: Path = ARCHIVO_CHECKPOINTS, archivo_registro: Path = ARCHIVO_REGISTRO):
    from langgraph.checkpoint.sqlite import SqliteSaver

    archivo.parent.mkdir(parents=True, exist_ok=True)
    return construir_grafo(SqliteSaver(sqlite3.connect(archivo, check_same_thread=False)), archivo_registro)


def mostrar(valor: dict) -> None:
    print(f"motivo: {valor['motivo']}")
    print(f"activa {valor['huella_activa']}  ->  propuesta {valor['huella_propuesta']}")
    print("\n".join("   " + linea for linea in valor["diff"]))


def titulo(texto: str) -> None:
    print(f"\n{'=' * 64}\n{texto}\n{'=' * 64}")


def demo() -> None:
    """Pruebas 2, 3 y 4 de la actividad sobre una copia temporal del registro: no cambia el prompt real."""
    with tempfile.TemporaryDirectory() as carpeta:
        copia = Path(carpeta) / "registro.json"
        shutil.copy(ARCHIVO_REGISTRO, copia)
        registro = RegistroDePrompts(copia)
        propuesta = registro.ultima(PROMPT_RAG)
        if propuesta["estado"] != "propuesta":
            sys.exit("No hay ninguna versión propuesta: corre primero python3 src/registro_prompts.py")
        huella = propuesta["huella"]
        app = construir_grafo(InMemorySaver(), copia)

        titulo("Prueba 2: sin reanudar, el despliegue NO pasó")
        thread_1, valor = proponer_despliegue(app, huella)
        estado = app.get_state(config_de(thread_1))
        print(f"thread_id: {thread_1}  ·  siguiente nodo: {estado.next}  ·  '__interrupt__' presente: {bool(estado.interrupts)}")
        mostrar(valor)
        print("activa en el registro:", RegistroDePrompts(copia).activa(PROMPT_RAG)["huella"], "(sigue la anterior)")

        titulo("Prueba 3: una persona aprueba")
        final = resolver(app, thread_1, True, huella, por="Cris")
        print(resumen(final), "· activa en el registro:", RegistroDePrompts(copia).activa(PROMPT_RAG)["huella"])

        titulo("Prueba 4: rechazo, en un hilo NUEVO (otra copia, con la propuesta pendiente)")
        shutil.copy(ARCHIVO_REGISTRO, copia)
        thread_2, _ = proponer_despliegue(app, huella)
        final = resolver(app, thread_2, False, huella, por="Cris")
        print(resumen(final), "· activa en el registro:", RegistroDePrompts(copia).activa(PROMPT_RAG)["huella"])

        titulo("Lo que la lección no prueba")
        shutil.copy(ARCHIVO_REGISTRO, copia)
        thread_3, _ = proponer_despliegue(app, huella)
        for intento, args in [("aprobar una huella distinta de la revisada", (thread_3, True, "000000000000")),
                              ("aprobar con 'si' en vez de True", (thread_3, "si", huella))]:
            try:
                resolver(app, *args, por="Cris")
            except (ValueError, TypeError) as error:
                print(f"  {intento} -> {type(error).__name__}: {error}")
        print("  reanudar directo con resume='no' (sin pasar por resolver) ->", end=" ")
        app.invoke(Command(resume="no"), config=config_de(thread_3))
        print("  aprobado:", app.get_state(config_de(thread_3)).values["aprobado"], "(un texto no es True: no activó nada)")
        try:
            resolver(app, thread_1, True, huella, por="Cris")
        except ValueError as error:
            print(f"  aprobar otra vez un hilo ya resuelto -> ValueError: {error}")


def resumen(estado: dict) -> str:
    return f"aprobado={estado['aprobado']} por {estado['decidido_por']}: {estado['resultado']}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aprobación humana para desplegar un prompt.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--proponer", metavar="HUELLA", help="pedir la aprobación de esa versión propuesta")
    grupo.add_argument("--pendientes", action="store_true", help="listar lo que espera una decisión")
    grupo.add_argument("--aprobar", metavar="THREAD_ID")
    grupo.add_argument("--rechazar", metavar="THREAD_ID")
    parser.add_argument("--huella", help="la huella que revisaste (obligatoria para aprobar o rechazar)")
    args = parser.parse_args()

    if not (args.proponer or args.pendientes or args.aprobar or args.rechazar):
        demo()
        sys.exit(0)

    app = app_durable()
    if args.proponer:
        thread_id, valor = proponer_despliegue(app, args.proponer)
        mostrar(valor)
        print(f"\nPendiente de aprobación. thread_id: {thread_id}\n"
              f"  aprobar:  python3 src/grafo_supervision.py --aprobar {thread_id} --huella {args.proponer}\n"
              f"  rechazar: python3 src/grafo_supervision.py --rechazar {thread_id} --huella {args.proponer}")
    elif args.pendientes:
        lista = pendientes(app)
        print(f"{len(lista)} pendiente(s)")
        for thread_id, valor in lista:
            print(f"\n{thread_id}")
            mostrar(valor)
    else:
        if not args.huella:
            parser.error("--huella es obligatoria: es la versión que revisaste")
        thread_id = args.aprobar or args.rechazar
        estado = resolver(app, thread_id, bool(args.aprobar), args.huella, por=getpass.getuser())
        print("estado final:", {k: estado[k] for k in ("huella_nueva", "aprobado", "decidido_por")})
