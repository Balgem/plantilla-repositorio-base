"""Autoevaluación del Gate 2 con la función de la rúbrica (Bloque S1).

Uso, desde la raíz del repositorio y con el entorno activo (no llama a la API):
    python3 src/autoevaluacion_gate2.py          (o python3 main.py autoevaluacion)

- Los puntajes por dimensión son MI estimación, cada uno con su justificación y lo que le falta.
- Los cuatro criterios no compensables NO son una estimación: salen de correr test_gate2.py en este momento.
  Si alguno falla, el resultado es "no estoy listo", sea cual sea el promedio (caso 1 de la lección).
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PESOS = {
    "pipeline_funcional": 0.25, "recuperacion_citacion": 0.15,
    "costo_latencia": 0.10, "personalizacion": 0.15,
    "observabilidad": 0.15, "seguridad_gobernanza": 0.20,
}

# (puntaje 0-100, por qué, qué le falta)
MI_PUNTAJE = {
    "pipeline_funcional": (90, "Indexa (incremental, persistido), recupera y genera de punta a punta; los errores de "
                               "la API se capturan; un solo comando (main.py servicio)",
                           "no está conectado al chat real de Twitch"),
    "recuperacion_citacion": (85, "Precisión y recall medidos sobre mi corpus (P=0,333, 93 % de la máxima; R=0,962 con "
                                  "k=3); cita obligatoria por frase, tomada de la metadata",
                              "15 casos de evaluación es poco; la precisión baja por diseño (k=3 con 1 chunk relevante)"),
    "costo_latencia": (80, "Latencia por etapa y costo real documentados (≈0,13 USD por 1.000 respuestas); consumo en "
                           "cada log",
                       "la generación tarda entre 2 y 9 s y no la optimicé"),
    "personalizacion": (88, "Decisión con evidencia propia (20/20) y análisis de sensibilidad: no personalizar; la "
                            "mejora que sugería (salida estructurada en el clasificador) quedó implementada",
                        "el dataset para PEFT es chico (25 ejemplos), aunque hoy no hace falta"),
    "observabilidad": (92, "Logs JSON con trace_id por consulta, consumo, huella del prompt, auditoría por respuesta "
                           "y revisión de lo marcado (--revisar)",
                       "los logs son archivos locales: no hay un tablero"),
    "seguridad_gobernanza": (88, "Inyección en 4 capas (RAG y agente), los dos prompts versionados con aprobación, dos "
                                 "puntos de supervisión durables, viewers que inyectan marcados para revisión, matriz "
                                 "de 12 riesgos, PII fuera de los logs",
                             "el detector se esquiva con sinónimos (lo cubren la cita obligatoria y el filtro de salida)"),
}

CRITERIOS = {
    "pipeline_corre_de_punta_a_punta": "test_1_pipeline_sin_excepciones",
    "respuestas_citan_fuente": "test_2_respuesta_cita_fuente",
    "logs_sin_contenido_crudo": "test_3_logs_sin_contenido_crudo",
    "supervision_humana_funciona": "test_4_supervision_pausa_y_reanuda",
}


def promedio_ponderado(puntajes: dict, pesos: dict = PESOS) -> float:
    return sum(puntajes[d] * pesos[d] for d in pesos)


def no_compensables() -> dict[str, bool]:
    """Corre test_gate2.py y devuelve, por criterio, si su prueba pasó."""
    salida = subprocess.run([sys.executable, "-m", "pytest", "test_gate2.py", "-v", "-p", "no:cacheprovider"],
                            cwd=RAIZ, capture_output=True, text=True).stdout
    return {criterio: f"{prueba} PASSED" in salida for criterio, prueba in CRITERIOS.items()}


def main() -> int:
    assert abs(sum(PESOS.values()) - 1) < 1e-9
    puntajes = {d: p for d, (p, _, _) in MI_PUNTAJE.items()}
    print(f"{'Dimensión':<24} {'Peso':>5} {'Puntaje':>8}   Le falta")
    for dimension, (puntaje, _, falta) in MI_PUNTAJE.items():
        print(f"{dimension:<24} {PESOS[dimension]:>5.0%} {puntaje:>8}   {falta}")
    promedio = promedio_ponderado(puntajes)
    criterios = no_compensables()
    print()
    for criterio, ok in criterios.items():
        print(f"{'✅' if ok else '❌'} {criterio}")
    listo = promedio >= 80 and all(criterios.values())
    print(f"\npromedio: {promedio:.1f}, no compensables OK? {all(criterios.values())} -> "
          f"{'listo para entregar' if listo else 'NO estoy listo'}")
    return 0 if listo else 1


if __name__ == "__main__":
    sys.exit(main())
