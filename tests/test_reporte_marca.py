"""Bloque 23 (post-stream): el reporte para la marca y sus dos aprobaciones humanas. Sin llamar a la API."""
import inspect

import reporte_marca as rm
import supervision


def accion(herramienta, **argumentos):
    return {"herramienta": herramienta, "argumentos": argumentos, "observacion": "ok"}


TRAZA = [
    {"timestamp": "t1", "acciones": [accion("consultar_campana", dato="precio")]},
    {"timestamp": "t2", "acciones": [accion("registrar_interes_compra", usuario="juli_k", mensaje="compro 2", cantidad=2)]},
    {"timestamp": "t3", "acciones": [accion("registrar_interes_compra", usuario="juli_k", mensaje="lo quiero", cantidad=2)]},
    {"timestamp": "t4", "acciones": [accion("marcar_comentario_negativo", usuario="troll99",
                                            mensaje="el K7 es una basura", motivo="calidad")]},
    {"timestamp": "t5", "acciones": [accion("marcar_comentario_negativo", usuario="maria_fps",
                                            mensaje="carísimo", motivo="precio")]},
    {"timestamp": "t6", "acciones": [accion("marcar_comentario_negativo", usuario="troll99",
                                            mensaje="el K7 es una basura", motivo="calidad")]},  # repetido
    {"timestamp": "t7", "acciones": [], "error": "TimeoutError()"},
]


def respuestas(monkeypatch, *decisiones):
    """El supervisor humano responde en orden con las decisiones dadas; anota cada pregunta."""
    preguntas, pendientes = [], list(decisiones)
    monkeypatch.setattr(supervision, "esperar_aprobacion", lambda mensaje, *a, **k: preguntas.append(mensaje) or pendientes.pop(0))
    return preguntas


def test_cada_accion_de_riesgo_alto_pide_aprobacion():
    """El mismo chequeo que el grep de la actividad, automático: si alguien lo saca, la prueba falla."""
    for funcion in rm.ACCIONES_DE_RIESGO_ALTO.values():
        assert "esperar_aprobacion(" in inspect.getsource(getattr(rm, funcion))


def test_datos_del_stream():
    datos = rm.datos_del_stream(TRAZA)
    assert datos["turnos"] == 7 and datos["con_error"] == 1
    assert datos["interesados"] == 1 and datos["unidades"] == 2  # juli_k no se cuenta dos veces
    assert [c["usuario"] for c in datos["comentarios_marcados"]] == ["troll99", "maria_fps"]  # sin duplicados


def test_solo_entran_al_reporte_los_comentarios_aprobados(monkeypatch):
    preguntas = respuestas(monkeypatch, True, False)
    comentarios = rm.datos_del_stream(TRAZA)["comentarios_marcados"]
    aprobados = rm.revisar_comentarios(comentarios)
    assert [c["usuario"] for c in aprobados] == ["troll99"]
    assert len(preguntas) == 2  # uno por uno, no todos de una vez
    assert [d["aprobado"] for d in supervision.registro_aprobaciones] == [True, False]  # el rechazo también queda


def test_el_reporte_no_tiene_nombres_de_viewers(monkeypatch):
    datos = rm.datos_del_stream(TRAZA)
    reporte = rm.armar_reporte(datos, datos["comentarios_marcados"][:1])
    assert "el K7 es una basura" in reporte and "carísimo" not in reporte
    assert "troll99" not in reporte and "juli_k" not in reporte and "maria_fps" not in reporte
    assert "1 comentario/s marcado/s por el bot se descartaron" in reporte
    assert "2 unidades" in reporte


def test_reporte_aprobado_se_envia(monkeypatch):
    respuestas(monkeypatch, True)
    assert rm.enviar_reporte_a_marca("reporte") is True
    assert rm.REPORTES_ENVIADOS == ["reporte"]
    assert rm.ARCHIVO_REPORTE.read_text(encoding="utf-8") == "reporte"


def test_reporte_rechazado_o_sin_respuesta_no_se_envia(monkeypatch):
    respuestas(monkeypatch, False)
    assert rm.enviar_reporte_a_marca("reporte") is False
    assert rm.REPORTES_ENVIADOS == [] and not rm.ARCHIVO_REPORTE.exists()
    assert supervision.registro_aprobaciones[0]["accion"] == "enviar_reporte_a_marca"
    assert supervision.registro_aprobaciones[0]["aprobado"] is False


def test_sin_consola_no_se_envia_nada():
    # flujo completo sin supervisor (por ejemplo, si alguien lo programa en un proceso desatendido)
    datos = rm.datos_del_stream(TRAZA)
    aprobados = rm.revisar_comentarios(datos["comentarios_marcados"])
    assert aprobados == []
    assert rm.enviar_reporte_a_marca(rm.armar_reporte(datos, aprobados)) is False
    assert rm.REPORTES_ENVIADOS == []
