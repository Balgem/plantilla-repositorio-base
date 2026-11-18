"""Gate 2: el punto de entrada único (main.py) y el servicio RAG de punta a punta (simulado, sin API)."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import main  # noqa: E402
import servicio_rag  # noqa: E402


def test_cada_comando_apunta_a_un_archivo_que_existe():
    for nombre, (script, _, _, _) in main.COMANDOS.items():
        assert script is None or (RAIZ / script).exists(), nombre


def test_estan_los_comandos_del_modulo_2():
    pedidos = {"rafaga", "pipeline", "metricas", "revision", "chain", "enrutamiento", "agente", "memoria", "trazas",
               "reporte", "indexar", "recuperar", "evaluar", "registro", "pruebas"}
    assert pedidos <= set(main.COMANDOS)
    assert main.COMANDOS["demo"][0] == "src/cliente.py"


def test_sin_comando_muestra_la_ayuda(capsys):
    assert main.main([]) == 0
    assert "servicio" in capsys.readouterr().out


def test_los_argumentos_pasan_al_script(monkeypatch):
    llamado = {}
    monkeypatch.setattr(main.runpy, "run_path", lambda ruta, run_name: llamado.update(ruta=ruta, argv=list(sys.argv)))
    main.main(["consulta", "¿llega a Arica?"])
    assert llamado["ruta"].endswith("servicio_rag.py") and llamado["argv"][1:] == ["--pregunta", "¿llega a Arica?"]


def test_comparar_pide_confirmacion(monkeypatch, capsys):
    monkeypatch.setattr(main.runpy, "run_path", lambda *a, **k: pytest.fail("no debía correr"))
    assert main.main(["comparar"]) == 0 and "--confirmar" in capsys.readouterr().out


def test_un_systemexit_con_mensaje_devuelve_1(monkeypatch):
    def falla(*a, **k):
        raise SystemExit("Falta la clave")
    monkeypatch.setattr(main.runpy, "run_path", falla)
    assert main.main(["servicio"]) == 1


@pytest.fixture
def servicio(tmp_path):
    return servicio_rag.crear_servicio(simulado=True, carpeta_indice=tmp_path / "indice",
                                       archivo_logs=tmp_path / "rag.jsonl", consola=False)


def test_servicio_simulado_responde_con_fuente_y_auditoria(servicio):
    r = servicio_rag.consultar(servicio, "¿cuánto cuesta el teclado?")
    assert r["fuentes"] and r["respuesta"].endswith(f"(Fuente: {r['fuentes'][0]})")
    assert [e["evento"] for e in r["auditoria"]] == ["consulta_recibida", "documentos_recuperados",
                                                      "contexto_filtrado", "consumo_llm", "respuesta_generada"]
    assert {e["trace_id"] for e in r["auditoria"]} == {r["trace_id"]}


def test_el_indice_persistido_se_reutiliza(tmp_path):
    kwargs = dict(simulado=True, carpeta_indice=tmp_path / "indice", archivo_logs=tmp_path / "rag.jsonl", consola=False)
    assert servicio_rag.crear_servicio(**kwargs).indice["estado"] == "indice_creado"
    segundo = servicio_rag.crear_servicio(**kwargs).indice
    assert segundo["estado"] == "indice_reutilizado" and segundo["embeddings_calculados"] == 0


def test_sin_clave_el_servicio_real_termina_con_un_mensaje(monkeypatch, tmp_path):
    monkeypatch.setattr(servicio_rag, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="--simulado"):
        servicio_rag.crear_servicio(archivo_logs=tmp_path / "rag.jsonl", consola=False)


def test_la_clave_se_acepta_con_los_dos_nombres(monkeypatch):
    from configuracion import clave_api
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "a")
    assert clave_api() == "a"
    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setenv("API_KEY", "b")
    assert clave_api() == "b"


def test_el_agente_usa_el_rag_del_servicio(servicio):
    import agente_con_herramientas as ag
    servicio_rag.conectar_rag_al_agente(servicio)
    try:
        assert "(Fuente: " in ag.consultar_campana.invoke({"dato": "cuánto cuesta el teclado"})
    finally:
        ag.configurar_rag(None)


def test_main_del_servicio_simulado_termina_en_cero(monkeypatch, tmp_path, capsys):
    real = servicio_rag.crear_servicio
    monkeypatch.setattr(servicio_rag, "crear_servicio", lambda simulado: real(
        simulado=simulado, carpeta_indice=tmp_path / "i", archivo_logs=tmp_path / "rag.jsonl", consola=False))
    monkeypatch.setattr(servicio_rag, "estado_supervision", lambda: {"reportes_a_la_marca": [], "prompts_propuestos": []})
    assert servicio_rag.main(["--simulado", "--pregunta", "¿precio?"]) == 0
    assert "Proceso terminado sin errores." in capsys.readouterr().out
