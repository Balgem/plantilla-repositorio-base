"""Punto de entrada único del proyecto: reúne en un solo archivo todos los flujos para ejecutar.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 main.py demo                     demo del bot: validación, conexión y dos mensajes del chat
    python3 main.py consistencia             prueba cada prompt del banco 3 veces contra la API
    python3 main.py comparar --confirmar     compara 9 modelos (unos 15 minutos y unas 100 peticiones)
    python3 main.py                          muestra esta ayuda
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

if sys.version_info < (3, 12):
    sys.exit(f"Este proyecto necesita Python 3.12 o superior y estás usando {sys.version.split()[0]}.\n"
             "Activa el entorno primero: source venv/bin/activate")

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "prompts"))

SCRIPTS = {
    "demo": RAIZ / "src" / "consumir_gemini.py",
    "consistencia": RAIZ / "prompts" / "test_consistencia.py",
    "comparar": RAIZ / "src" / "comparar_modelos.py",
}


def crear_parser() -> argparse.ArgumentParser:
    """Define los comandos disponibles y su ayuda."""
    parser = argparse.ArgumentParser(
        prog="python3 main.py",
        description="Bot de chat con IA para campañas en Twitch: todos los flujos desde un solo archivo.",
    )
    comandos = parser.add_subparsers(dest="comando", title="comandos")
    comandos.add_parser("demo", help="demo del bot: validación, conexión y dos mensajes del chat")
    comandos.add_parser("consistencia", help="prueba cada prompt del banco 3 veces (guarda prompts/registro_resultados.json)")
    comparar = comandos.add_parser(
        "comparar", help="compara 9 modelos por costo, latencia y calidad (unos 15 minutos)"
    )
    comparar.add_argument(
        "--confirmar", action="store_true",
        help="necesario para ejecutarlo: hace unas 100 peticiones y reemplaza docs/comparacion_modelos.*",
    )
    return parser


def main(argumentos: list[str] | None = None) -> None:
    """Ejecuta el flujo elegido como si se corriera su archivo directamente."""
    parser = crear_parser()
    args = parser.parse_args(argumentos)
    if args.comando is None:
        parser.print_help()
        return
    if args.comando == "comparar" and not args.confirmar:
        print("La comparación hace unas 100 peticiones, tarda unos 15 minutos y reemplaza los resultados\n"
              "del 2026-10-20 que usa docs/decision-arquitectura.md. Para ejecutarla de todas formas:\n"
              "    python3 main.py comparar --confirmar")
        return
    runpy.run_path(str(SCRIPTS[args.comando]), run_name="__main__")


if __name__ == "__main__":
    main()
