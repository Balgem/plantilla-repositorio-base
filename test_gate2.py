"""Los cuatro criterios no compensables del Gate 2, con un solo comando:
    python3 -m pytest test_gate2.py -v          (o python3 main.py gate2)

Por defecto corre el servicio REAL del proyecto (corpus, chunking, índice Chroma, filtros, prompt versionado,
logs, grafo de supervisión) con embeddings y modelo simulados, así que no necesita clave ni gasta.
Con GATE2_REAL=1 usa el índice de vectorstore/ y Gemini (necesita la clave y gasta unas pocas consultas).

Diferencias con la plantilla de la lección, a propósito:
- test_2: la fuente sale de la metadata de lo recuperado. El modelo simulado escribe solo "[1]", nunca el nombre
  del archivo: si la prueba pasa, la cita la puso el código del servicio (en la lección, el modelo falso ya
  traía "manual.pdf" en su texto y la prueba pasaba aunque no se recuperara nada).
- test_3: además de caplog, lee el ARCHIVO de log real: los loggers del servicio no propagan (propagate=False)
  y caplog solo no los vería (el falso positivo que advierte la lección).
- test_4: el punto de supervisión es el envío del reporte a la marca, la acción de mayor riesgo del sistema.
"""
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))

# Dato sensible de prueba que NUNCA debe aparecer en los logs
CORREO = "ana.perez@example.com"
PREGUNTA = "¿Cuánto cuesta el envío? Mi correo es " + CORREO

_CARPETA = Path(tempfile.mkdtemp(prefix="gate2_"))
ARCHIVO_LOGS = _CARPETA / "rag.jsonl"
_servicio = None


# ===== ADAPTADO A MI PROYECTO =====
def ejecutar_servicio(pregunta):
    """Corre el flujo completo (indexar, recuperar y responder). Devuelve (respuesta, fuentes)."""
    global _servicio
    import servicio_rag

    if _servicio is None:
        real = os.getenv("GATE2_REAL") == "1"
        _servicio = servicio_rag.crear_servicio(simulado=not real, carpeta_indice=None if real else _CARPETA / "indice",
                                                archivo_logs=ARCHIVO_LOGS, consola=False)
    resultado = servicio_rag.consultar(_servicio, pregunta)
    return resultado["respuesta"], resultado["fuentes"]


def crear_supervision():
    """(app, entrada): el grafo del reporte a la marca, con checkpointer, sobre una traza de prueba."""
    import reporte_marca
    import supervision
    from langgraph.checkpoint.memory import InMemorySaver

    supervision.ARCHIVO_APROBACIONES = _CARPETA / "aprobaciones.jsonl"  # la prueba no escribe en el repo

    trazas = _CARPETA / "trazas.jsonl"
    accion = {"herramienta": "marcar_comentario_negativo", "observacion": "ok",
              "argumentos": {"usuario": "a1b2c3d4e5f6", "mensaje": "el K7 es una basura", "motivo": "calidad"}}
    trazas.write_text(json.dumps({"timestamp": "t1", "acciones": [accion]}) + "\n", encoding="utf-8")
    app = reporte_marca.construir_grafo(InMemorySaver(), archivo_trazas=trazas,
                                        archivo_reporte=_CARPETA / "reporte_marca.md")
    return app, {}
# ===== FIN DE LA SECCIÓN ADAPTADA =====


def test_1_pipeline_sin_excepciones():
    respuesta, _ = ejecutar_servicio(PREGUNTA)
    assert respuesta.strip(), "el servicio devolvio una respuesta vacia"


def test_2_respuesta_cita_fuente():
    respuesta, fuentes = ejecutar_servicio(PREGUNTA)
    assert fuentes, "el servicio no devolvio ninguna fuente"
    assert any(f in respuesta for f in fuentes), "la respuesta no menciona su fuente"
    corpus = {p.name for p in (RAIZ / "corpus" / "campana_k7").glob("*.md")}
    assert set(fuentes) <= corpus, "una fuente citada no es un documento real del corpus"


def test_3_logs_sin_contenido_crudo(caplog):
    with caplog.at_level(logging.DEBUG):
        ejecutar_servicio(PREGUNTA)
    texto_logs = " ".join(r.getMessage() + " " + str(r.__dict__) for r in caplog.records)
    texto_logs += ARCHIVO_LOGS.read_text(encoding="utf-8")  # el archivo real, no solo lo que ve caplog
    assert CORREO not in texto_logs, "un dato sensible aparece en los logs"
    assert PREGUNTA not in texto_logs, "la consulta completa aparece en los logs"
    assert "ana.perez" not in texto_logs, "una parte del correo aparece en los logs"


def test_4_supervision_pausa_y_reanuda():
    from langgraph.types import Command
    app, entrada = crear_supervision()
    config = {"configurable": {"thread_id": "test-gate2"}}
    pausado = app.invoke(entrada, config=config)
    assert "__interrupt__" in pausado, "el grafo no se detuvo en el punto de supervision"
    assert not (_CARPETA / "reporte_marca.md").exists(), "se envio el reporte antes de la aprobacion"
    final = app.invoke(Command(resume=True), config=config)
    assert "__interrupt__" not in final, "el grafo sigue pausado despues de reanudar"
    assert final["aprobado"] is True, "la decision no quedo registrada"
    assert (_CARPETA / "reporte_marca.md").exists(), "aprobado, pero el reporte no se envio"
