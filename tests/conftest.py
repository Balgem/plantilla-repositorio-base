"""Preparación común a todas las pruebas."""
import pytest

import agente_con_herramientas as ag
import decision
import logging_rag
import registro_rag
import reporte_marca
import supervision
import trazas


@pytest.fixture(autouse=True)
def sin_efectos_fuera_de_la_prueba(tmp_path, monkeypatch):
    """Trazas, aprobaciones, reportes y registros de latencia van a una carpeta temporal (nunca a los archivos reales del proyecto)."""
    monkeypatch.setattr(trazas, "ARCHIVO_TRAZAS", tmp_path / "trazas_prueba.jsonl")
    monkeypatch.setattr(supervision, "ARCHIVO_APROBACIONES", tmp_path / "aprobaciones_prueba.jsonl")
    monkeypatch.setattr(reporte_marca, "ARCHIVO_REPORTE", tmp_path / "reporte_prueba.md")
    monkeypatch.setattr(registro_rag, "ARCHIVO_REGISTROS", tmp_path / "registros_prueba.jsonl")
    monkeypatch.setattr(decision, "ARCHIVO_EVIDENCIA", tmp_path / "evidencia_prueba.json")
    monkeypatch.setattr(decision, "ARCHIVO_DECISION", tmp_path / "decision_prueba.md")
    monkeypatch.setattr(logging_rag, "ARCHIVO_LOGS", tmp_path / "logs_prueba.jsonl")
    supervision.registro_aprobaciones.clear()
    reporte_marca.REPORTES_ENVIADOS.clear()
    ag.COMENTARIOS_MARCADOS.clear()
    yield
