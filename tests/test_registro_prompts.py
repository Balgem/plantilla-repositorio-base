"""Bloque 32, paso 1: registro de versiones del prompt de sistema (sin API)."""
import json

import pytest

import registro_prompts as rp
from registro_prompts import PROMPT_AGENTE, PROMPT_RAG, RegistroDePrompts, diff_prompts, huella_prompt


def de(registro, nombre=PROMPT_RAG):
    return [v for v in registro.versiones if v["nombre"] == nombre]


@pytest.fixture
def registro(tmp_path):
    r = RegistroDePrompts(tmp_path / "registro.json")
    rp.cargar_historial(r)
    return r


def test_prueba_1_huellas_distintas_y_ultima_es_la_mas_reciente(registro):
    huellas = [v["huella"] for v in de(registro)]
    assert len(huellas) == len(set(huellas)) == 3
    assert registro.ultima(PROMPT_RAG)["texto"] == rp.V3_NO_SE_PARA_EL_VIEWER


def test_ultima_no_es_lo_mismo_que_activa(registro):
    assert registro.ultima(PROMPT_RAG)["estado"] == "propuesta"
    assert registro.activa(PROMPT_RAG)["texto"] == rp.V2_ANTI_INYECCION
    assert [v["estado"] for v in de(registro)] == ["reemplazada", "activa", "propuesta"]


def test_cada_version_guarda_modelo_autor_fecha_y_nota(registro):
    for v in registro.versiones:
        assert v["modelo"] == "gemini-3.5-flash-lite" and v["autor"] and v["fecha"] and v["nota"]
    assert registro.versiones[0]["fecha"] == "2026-11-12"  # la fecha real del commit, no la de hoy


def test_el_mismo_texto_no_crea_otra_version(registro):
    registro.registrar(PROMPT_RAG, rp.V2_ANTI_INYECCION, "otra persona", "sin cambios")
    rp.cargar_historial(registro)  # correr el script dos veces tampoco duplica
    assert len(de(registro)) == 3 and len(de(registro, PROMPT_AGENTE)) == 4


def test_una_sola_letra_cambia_la_huella():
    assert huella_prompt(rp.V2_ANTI_INYECCION) != huella_prompt(rp.V2_ANTI_INYECCION + " ")


def test_diff_v2_v3_muestra_exactamente_el_cambio():
    diff = diff_prompts(rp.V2_ANTI_INYECCION, rp.V3_NO_SE_PARA_EL_VIEWER)
    quitadas = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    agregadas = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    assert quitadas == ["dilo"]
    assert " ".join(agregadas) == "responde que no tienes ese dato del K7, sin nombrar el contexto ni los fragmentos,"


def test_activar_reemplaza_la_anterior_y_registra_quien(registro):
    v3 = registro.ultima(PROMPT_RAG)["huella"]
    registro.activar(PROMPT_RAG, v3, "Cris")
    assert registro.activa(PROMPT_RAG)["huella"] == v3 and registro.activa(PROMPT_RAG)["decidido_por"] == "Cris"
    assert sum(v["estado"] == "activa" for v in de(registro)) == 1


def test_no_se_decide_dos_veces_ni_se_activa_algo_rechazado(registro):
    v3 = registro.ultima(PROMPT_RAG)["huella"]
    registro.rechazar(PROMPT_RAG, v3, "Cris")
    with pytest.raises(ValueError, match="rechazada"):
        registro.activar(PROMPT_RAG, v3, "Cris")
    with pytest.raises(KeyError):
        registro.activar(PROMPT_RAG, "000000000000", "Cris")


def test_guardar_y_volver_a_leer(registro, tmp_path):
    registro.guardar()
    otra = RegistroDePrompts(tmp_path / "registro.json")
    assert otra.versiones == registro.versiones
    assert rp.prompt_activo(archivo=tmp_path / "registro.json")["texto"] == rp.V2_ANTI_INYECCION


def test_sin_version_activa_falla_en_vez_de_inventar(tmp_path):
    with pytest.raises(LookupError):
        rp.prompt_activo(archivo=tmp_path / "vacio.json")


def test_el_registro_real_del_repo_es_consistente():
    """Si alguien edita a mano prompts/registro_versiones.json (el texto o el estado), esta prueba lo detecta."""
    versiones = json.loads(rp.ARCHIVO_REGISTRO.read_text(encoding="utf-8"))
    assert all(v["huella"] == huella_prompt(v["texto"]) for v in versiones)
    for nombre in (PROMPT_RAG, PROMPT_AGENTE):
        assert sum(v["estado"] == "activa" for v in versiones if v["nombre"] == nombre) == 1, nombre
    assert all(v["estado"] in rp.ESTADOS for v in versiones)


# --- Gate 2: el prompt del agente también está versionado ---


def test_historial_del_agente_con_sus_fechas_reales(registro):
    agente = de(registro, PROMPT_AGENTE)
    assert [v["fecha"] for v in agente] == ["2026-11-05", "2026-11-09", "2026-11-09", agente[3]["fecha"]]
    assert [v["estado"] for v in agente] == ["reemplazada", "reemplazada", "activa", "propuesta"]
    assert registro.activa(PROMPT_RAG)["nombre"] == PROMPT_RAG  # activar uno no toca el otro prompt


def test_cada_version_del_agente_agrega_una_regla():
    for anterior, nueva, agregada in [(rp.V1_AGENTE, rp.V2_AGENTE, "nunca escribas otro link"),
                                      (rp.V2_AGENTE, rp.V3_AGENTE, "marcar_comentario_negativo"),
                                      (rp.V3_AGENTE, rp.V4_AGENTE, "copia esa fuente")]:
        assert agregada not in anterior and agregada in nueva


def test_el_agente_usa_la_version_activa_del_registro():
    import agente_con_herramientas as ag
    assert ag.INSTRUCCIONES_BOT == rp.prompt_activo(PROMPT_AGENTE)["texto"]


def test_activar_el_agente_no_cambia_el_rag(registro):
    rag_antes = registro.activa(PROMPT_RAG)["huella"]
    registro.activar(PROMPT_AGENTE, huella_prompt(rp.V4_AGENTE), "Cris")
    assert registro.activa(PROMPT_AGENTE)["texto"] == rp.V4_AGENTE and registro.activa(PROMPT_RAG)["huella"] == rag_antes
