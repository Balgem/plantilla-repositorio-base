"""Servicio RAG del bot de la campaña K7, de punta a punta (Gate 2).

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 servicio_rag.py                                  # corrida real: índice persistido + Gemini
    python3 servicio_rag.py --pregunta "¿llega a Arica?"     # una pregunta propia
    python3 servicio_rag.py --simulado                       # sin clave ni costo: embeddings y modelo simulados
(También: python3 main.py servicio / python3 main.py consulta "pregunta".)

Qué hace, en orden:
1. Índice: abre vectorstore/ y lo actualiza de forma INCREMENTAL (Bloque 25): si el corpus no cambió, no
   recalcula ningún embedding; si el índice no existe (entorno limpio), lo crea y mide cuánto tardó.
2. Consultas: logging_rag.responder -> filtro de inyección (pregunta y chunks), prompt versionado y aprobado
   (Bloque 32), modelo, citas, filtros de salida, logs JSON con trace_id y consumo (Bloque 31).
   Cada respuesta se imprime con su fuente, su trace_id y su traza de auditoría (los eventos de ESA consulta).
3. Supervisión humana: muestra qué está esperando una decisión (reporte a la marca y prompts propuestos).
   Las decisiones se toman con sus propios comandos; este servicio nunca aprueba nada por su cuenta.

Termina con código 0 si todo corrió; 1 si falta algo para correr (clave, dependencia), con el motivo.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from dotenv import load_dotenv  # noqa: E402

PREGUNTAS = ["¿cuánto cobran por el envío?", "¿cuánto pesa el teclado?"]


@dataclass
class Servicio:
    buscar: object            # pregunta -> chunks
    modelo: object            # chat model (Gemini o simulado)
    nombre_modelo: str
    archivo_logs: Path
    indice: dict              # resumen de la actualización del índice
    simulado: bool


def _modelo_simulado():
    """Responde con el primer fragmento del contexto y lo cita como [1]: la cita la convierte el CÓDIGO en la
    fuente real (metadata del chunk), no viene escrita en el texto del modelo (lección del ensayo del Gate 2)."""
    import re

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class ModeloSimulado(FakeMessagesListChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            humano = messages[-1].content
            fragmento = re.search(r"\[1\] (.+)", humano)
            if fragmento:
                cuerpo = re.sub(r"^#+ .*?\bK7\s+", "", fragmento.group(1))  # sin el título "# ... del K7"
                texto = f"{cuerpo.split('. ')[0].rstrip('.')} [1]."
            else:
                texto = "No tengo ese dato del K7."
            mensaje = AIMessage(content=texto, usage_metadata={"input_tokens": len(humano) // 4,
                                                               "output_tokens": len(texto) // 4,
                                                               "total_tokens": (len(humano) + len(texto)) // 4})
            return ChatResult(generations=[ChatGeneration(message=mensaje)])

    return ModeloSimulado(responses=[AIMessage(content="")])


def crear_servicio(simulado: bool = False, carpeta_indice: Path | None = None,
                   archivo_logs: Path | None = None, consola: bool = True) -> Servicio:
    """Arma el servicio. Con simulado=True usa un índice TEMPORAL (nunca mezcla embeddings falsos con vectorstore/)."""
    import indexar_corpus as ic
    import logging_rag as lr
    from configuracion import MENSAJE_SIN_CLAVE, clave_api, nombre_modelo
    from recuperacion import K

    archivo_logs = archivo_logs or lr.ARCHIVO_LOGS
    lr.configurar_logging(archivo_logs, consola=consola)
    chunks = ic.partir_en_chunks(ic.cargar_corpus())
    if simulado:
        from langchain_core.embeddings import DeterministicFakeEmbedding

        embeddings, modelo, nombre = DeterministicFakeEmbedding(size=768), _modelo_simulado(), "simulado"
        carpeta = carpeta_indice or Path(tempfile.mkdtemp(prefix="indice_simulado_"))
    else:
        load_dotenv()
        if not clave_api():
            raise SystemExit(f"{MENSAJE_SIN_CLAVE}\nSin clave puedes probar todo con: python3 servicio_rag.py --simulado")
        from cadena_tres_pasos import crear_modelo

        embeddings, modelo, nombre = ic.crear_embeddings(), crear_modelo(), nombre_modelo()
        carpeta = carpeta_indice or ic.CARPETA_VECTORSTORE

    inicio = time.perf_counter()
    indice, resumen = ic.actualizar_indice(chunks, embeddings, carpeta=carpeta)
    resumen["segundos"] = round(time.perf_counter() - inicio, 2)
    resumen["estado"] = ("indice_creado" if resumen["nuevos"] == resumen["total"]
                         else "indice_actualizado" if resumen["embeddings_calculados"] or resumen["borrados"]
                         else "indice_reutilizado")
    lr.evento(resumen["estado"], **resumen)  # fuera de una consulta: trace_id null, y está bien
    retriever = indice.as_retriever(search_kwargs={"k": K})
    return Servicio(buscar=retriever.invoke, modelo=modelo, nombre_modelo=nombre, archivo_logs=archivo_logs,
                    indice=resumen, simulado=simulado)


def consultar(servicio: Servicio, pregunta: str) -> dict:
    """Una consulta completa. Devuelve trace_id, respuesta (con su fuente), fuentes y la auditoría de esa consulta."""
    import logging_rag as lr

    resultado = lr.responder(pregunta, servicio.buscar, servicio.modelo, servicio.nombre_modelo)
    eventos = []
    if servicio.archivo_logs.exists():
        for linea in servicio.archivo_logs.read_text(encoding="utf-8").splitlines():
            evento = json.loads(linea)
            if evento.get("trace_id") == resultado["trace_id"]:
                eventos.append({k: v for k, v in evento.items() if k not in ("ts", "msg")})
    return {**resultado, "auditoria": eventos}


def conectar_rag_al_agente(servicio: Servicio) -> None:
    """consultar_campana del agente pasa a responder con este mismo RAG (y con su fuente)."""
    import agente_con_herramientas as ag
    import logging_rag as lr

    ag.configurar_rag(lambda pregunta: lr.responder(pregunta, servicio.buscar, servicio.modelo, servicio.nombre_modelo))


def estado_supervision() -> dict:
    """Qué espera una decisión humana, leído de los checkpointers durables (sin crear nada nuevo)."""
    import grafo_supervision as gs
    import reporte_marca as rm

    estado = {}
    for nombre, modulo, archivo in [("reportes_a_la_marca", rm, rm.ARCHIVO_CHECKPOINTS),
                                    ("prompts_propuestos", gs, gs.ARCHIVO_CHECKPOINTS)]:
        estado[nombre] = [h for h, _ in modulo.pendientes(modulo.app_durable(archivo))] if archivo.exists() else []
    return estado


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servicio RAG del bot de la campaña K7.")
    parser.add_argument("--simulado", action="store_true", help="sin clave ni costo (embeddings y modelo simulados)")
    parser.add_argument("--pregunta", action="append", help="pregunta a responder (se puede repetir)")
    args = parser.parse_args(argumentos)

    try:
        servicio = crear_servicio(simulado=args.simulado)
    except ModuleNotFoundError as error:
        print(f"Falta una dependencia ({error.name}). Instala con: pip install -r requirements.txt")
        return 1
    i = servicio.indice
    print(f"\n{'[SIMULADO] ' if servicio.simulado else ''}Índice: {i['estado']} · {i['total']} chunks · "
          f"embeddings calculados ahora: {i['embeddings_calculados']} · {i['segundos']} s")

    for pregunta in args.pregunta or PREGUNTAS:
        print(f"\n--- respuesta completa del servicio{' (SIMULADA)' if servicio.simulado else ''} ---")
        print(json.dumps(consultar(servicio, pregunta), ensure_ascii=False, indent=2))

    print("\n--- punto de supervisión humana ---")
    pendientes = estado_supervision()
    print(f"Reportes a la marca esperando aprobación: {len(pendientes['reportes_a_la_marca'])} "
          f"(python3 src/reporte_marca.py --pendientes)")
    print(f"Versiones de prompt esperando aprobación: {len(pendientes['prompts_propuestos'])} "
          f"(python3 src/grafo_supervision.py --pendientes)")
    print("\nProceso terminado sin errores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
