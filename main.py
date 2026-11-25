"""Punto de entrada del proyecto. Todos los flujos se corren desde aquí.

Uso:
    python3 main.py                      lista de comandos
    python3 main.py servicio             el servicio RAG completo
    python3 main.py consulta "pregunta"  una pregunta al servicio
    python3 main.py gate2                pruebas de los criterios no compensables

Lo que va después del comando se le pasa al script (ej.: python3 main.py indexar --verificar).
"""
from __future__ import annotations

import argparse
import runpy
import subprocess
import sys
from pathlib import Path

VERSION_MINIMA = (3, 12)  # numpy 2.5 (dependencia de chromadb en requirements.txt) exige 3.12
if sys.version_info < VERSION_MINIMA:
    sys.exit(f"Este proyecto necesita Python {'.'.join(map(str, VERSION_MINIMA))} o superior y estás usando "
             f"{sys.version.split()[0]}.\nActiva el entorno primero: source venv/bin/activate")

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "prompts"))

# comando -> (script, argumentos fijos, descripción, grupo)
COMANDOS = {
    # Gate 2
    "servicio": ("servicio_rag.py", [], "servicio RAG de punta a punta: índice, consultas con fuente, supervisión", "Gate 2"),
    "consulta": ("servicio_rag.py", ["--pregunta"], 'una pregunta al servicio: python3 main.py consulta "¿llega a Arica?"', "Gate 2"),
    "verificar": ("verificar_entorno.py", [], "comprueba Python, librerías, clave e índice antes de correr", "Gate 2"),
    "gate2": (None, ["-m", "pytest", "test_gate2.py", "-v"], "las 4 pruebas de los criterios no compensables", "Gate 2"),
    "pruebas": (None, ["-m", "pytest", "-q"], "todas las pruebas del proyecto (sin API)", "Gate 2"),
    "autoevaluacion": ("src/autoevaluacion_gate2.py", [], "promedio ponderado + los 4 no compensables medidos", "Gate 2"),
    # Unidad 2.5: RAG
    "indexar": ("src/indexar_corpus.py", [], "indexa el corpus de forma incremental (--desde-cero, --verificar)", "RAG"),
    "recuperar": ("src/recuperacion.py", [], "recuperación semántica + prompt con citas (Bloque 26)", "RAG"),
    "evaluar": ("src/evaluacion_recuperacion.py", [], "precisión y recall de la recuperación (Bloque 27; --k N)", "RAG"),
    "registro": ("src/registro_rag.py", [], "latencia y costo real por etapa (Bloque 28; --leer)", "RAG"),
    # Unidad 2.6: personalización
    "dataset": ("src/dataset_tuning.py", [], "dataset validado para PEFT del clasificador (Bloque 29)", "Personalización"),
    "decision": ("src/decision.py", [], "decisión de personalización con evidencia (Bloque 30; --sin-api)", "Personalización"),
    # Unidad 2.7: observabilidad, seguridad y gobernanza
    "logs": ("src/logging_rag.py", [], "flujo RAG instrumentado (Bloque 31; --real, --revisar)", "Observabilidad y seguridad"),
    "prompts": ("src/registro_prompts.py", [], "versiones del prompt de sistema y su diff (Bloque 32)", "Observabilidad y seguridad"),
    "supervision": ("src/grafo_supervision.py", [], "aprobación humana de un prompt nuevo (--proponer, --aprobar)", "Observabilidad y seguridad"),
    "matriz": ("src/matriz_riesgos.py", [], "matriz de riesgos del bot (Bloque 32)", "Observabilidad y seguridad"),
    # Unidad 2.4: agentes
    "agente": ("src/agente_con_herramientas.py", [], "agente con herramientas (Bloque 21)", "Agentes"),
    "memoria": ("src/agente_con_memoria.py", [], "agente con memoria por viewer (Bloque 22)", "Agentes"),
    "trazas": ("src/trazas.py", [], "revisión de las trazas del agente (Bloque 23)", "Agentes"),
    "reporte": ("src/reporte_marca.py", [], "reporte a la marca con aprobación humana (--pendientes, --aprobar)", "Agentes"),
    # Unidades 2.1 a 2.3
    "rafaga": ("src/cliente.py", ["--rafaga"], "ensayo de rate limit (Bloque 13): python3 main.py rafaga 30", "Componentes"),
    "pipeline": ("src/pipeline_texto.py", [], "pipeline de texto (Bloque 15)", "Componentes"),
    "metricas": ("src/metricas.py", [], "precisión, cobertura y F1 (Bloque 16)", "Componentes"),
    "revision": ("src/revision_manual.py", [], "revisión cualitativa (Bloque 17)", "Componentes"),
    "chain": ("src/cadena_tres_pasos.py", [], "chain de tres pasos con LangChain (Bloque 18)", "Componentes"),
    "enrutamiento": ("src/enrutamiento.py", [], "enrutamiento condicional y respaldo (Bloques 19-20)", "Componentes"),
    # Gate 1
    "demo": ("src/cliente.py", [], "demo del cliente modular: validación, conexión y mensajes del chat", "Gate 1"),
    "consistencia": ("prompts/test_consistencia.py", [], "prueba cada prompt del banco 3 veces contra la API", "Gate 1"),
    "comparar": ("src/comparar_modelos.py", [], "compara 9 modelos (unos 15 minutos; requiere --confirmar)", "Gate 1"),
}


def crear_parser() -> argparse.ArgumentParser:
    grupos: dict[str, list[str]] = {}
    for nombre, (_, _, descripcion, grupo) in COMANDOS.items():
        grupos.setdefault(grupo, []).append(f"  {nombre:<13} {descripcion}")
    epilogo = "\n\n".join(f"{grupo}:\n" + "\n".join(lineas) for grupo, lineas in grupos.items())
    parser = argparse.ArgumentParser(
        prog="python3 main.py", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Bot de chat con IA para campañas en Twitch: todos los flujos desde un solo archivo.",
        epilog=epilogo,
    )
    parser.add_argument("comando", nargs="?", choices=COMANDOS, metavar="comando")
    parser.add_argument("argumentos", nargs=argparse.REMAINDER, help="se pasan tal cual al script")
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Ejecuta el flujo elegido como si se corriera su archivo directamente. Devuelve el código de salida."""
    parser = crear_parser()
    args = parser.parse_args(argumentos)
    if args.comando is None:
        parser.print_help()
        return 0
    script, fijos, _, _ = COMANDOS[args.comando]
    if args.comando == "comparar" and "--confirmar" not in args.argumentos:
        print("La comparación hace unas 100 peticiones, tarda unos 15 minutos y reemplaza los resultados\n"
              "del 2026-10-20 que usa docs/decision-arquitectura.md. Para ejecutarla de todas formas:\n"
              "    python3 main.py comparar --confirmar")
        return 0
    if script is None:  # pytest, con el Python de este entorno (lección del Gate 2: python -m pytest)
        return subprocess.call([sys.executable, *fijos, *args.argumentos], cwd=RAIZ)
    resto = [a for a in args.argumentos if a != "--confirmar"] if args.comando == "comparar" else args.argumentos
    sys.argv = [str(RAIZ / script), *fijos, *resto]
    try:
        runpy.run_path(str(RAIZ / script), run_name="__main__")
    except SystemExit as salida:
        codigo = salida.code
        if isinstance(codigo, str):
            print(codigo, file=sys.stderr)
            return 1
        return codigo or 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
