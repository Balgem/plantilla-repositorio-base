"""Preparación común a todas las pruebas."""
import pytest

import agente_con_herramientas as ag
import reporte_marca
import supervision
import trazas


@pytest.fixture(autouse=True)
def sin_efectos_fuera_de_la_prueba(tmp_path, monkeypatch):
    """Trazas, aprobaciones y reportes van a una carpeta temporal (nunca a los archivos reales del proyecto)."""
    monkeypatch.setattr(trazas, "ARCHIVO_TRAZAS", tmp_path / "trazas_prueba.jsonl")
    monkeypatch.setattr(supervision, "ARCHIVO_APROBACIONES", tmp_path / "aprobaciones_prueba.jsonl")
    monkeypatch.setattr(reporte_marca, "ARCHIVO_REPORTE", tmp_path / "reporte_prueba.md")
    supervision.registro_aprobaciones.clear()
    reporte_marca.REPORTES_ENVIADOS.clear()
    ag.COMENTARIOS_MARCADOS.clear()
    yield
