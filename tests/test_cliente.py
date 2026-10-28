"""Pruebas unitarias del cliente modular.

Ninguna prueba llama a la API real ni espera de verdad: requests.post y time.sleep
se reemplazan por mocks. Correr desde la raíz del repositorio con:
    pytest -v
"""
from unittest.mock import Mock, patch

import pytest
import requests

import cliente
from cliente import consultar_modelo, registrar_costo
from consumir_gemini import con_reintentos, enviar_peticion

URL = "https://ejemplo.test/modelo:generateContent"
HEADERS = {"x-goog-api-key": "llave_de_prueba"}
BODY = {"contents": [{"parts": [{"text": "hola"}]}]}

RESPUESTA_EXITOSA = {
    "candidates": [{"content": {"parts": [{"text": "El K7 cuesta 59.990 CLP."}]}}],
    "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 1000, "totalTokenCount": 2000},
}
# Con gemini-3.5-flash-lite (0,30 USD por millón de entrada y 2,50 por millón de salida):
# 1000 × 0,30 / 1e6 + 1000 × 2,50 / 1e6 = 0,0028 USD
COSTO_RESPUESTA_EXITOSA = 0.0028


def respuesta_falsa(codigo, json=None, texto="{}"):
    """Simula la respuesta de requests.post con un código de estado dado."""
    respuesta = Mock(status_code=codigo, ok=codigo < 400, text=texto)
    respuesta.json.return_value = json
    return respuesta


@pytest.fixture(autouse=True)
def entorno_de_prueba(monkeypatch):
    """Antes de cada prueba: llave y modelo de prueba, y costo de la sesión en cero."""
    monkeypatch.setenv("API_KEY", "llave_de_prueba")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    cliente.costo_total_sesion = 0.0
    yield


# --- enviar_peticion: clasificación de errores ---


def test_enviar_peticion_exito():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(200, RESPUESTA_EXITOSA)):
        assert enviar_peticion(URL, HEADERS, BODY) == RESPUESTA_EXITOSA


def test_enviar_peticion_credencial_invalida():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(401)):
        with pytest.raises(ValueError, match="Credencial inválida"):
            enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_sin_permiso():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(403)):
        with pytest.raises(ValueError):
            enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_llave_invalida_responde_400():
    # Gemini responde 400 (no 401) cuando la llave no es válida.
    texto = '{"error": {"code": 400, "details": [{"reason": "API_KEY_INVALID"}]}}'
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(400, texto=texto)):
        with pytest.raises(ValueError):
            enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_limite_de_uso():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(429)):
        with pytest.raises(TimeoutError, match="429"):
            enviar_peticion(URL, HEADERS, BODY)


@pytest.mark.parametrize("codigo", [500, 503])
def test_enviar_peticion_error_del_proveedor(codigo):
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(codigo)):
        with pytest.raises(TimeoutError):
            enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_sin_conexion():
    with patch("consumir_gemini.requests.post", side_effect=requests.exceptions.ConnectionError):
        with pytest.raises(TimeoutError, match="No se pudo contactar"):
            enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_otro_error_no_se_reintenta():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(404)):
        with pytest.raises(RuntimeError, match="404"):
            enviar_peticion(URL, HEADERS, BODY)


# --- con_reintentos: backoff y decisión de reintentar ---


def test_con_reintento_reintenta_en_timeout():
    funcion = Mock(side_effect=[TimeoutError("simulado"), "ok"])
    with patch("consumir_gemini.time.sleep") as mock_sleep:
        resultado, intentos = con_reintentos(funcion)
    assert resultado == "ok"
    assert intentos == 2
    mock_sleep.assert_called_once()


def test_con_reintento_no_reintenta_value_error():
    funcion = Mock(side_effect=ValueError("credencial inválida"))
    with patch("consumir_gemini.time.sleep") as mock_sleep:
        with pytest.raises(ValueError):
            con_reintentos(funcion)
    assert funcion.call_count == 1
    mock_sleep.assert_not_called()


def test_con_reintento_agota_intentos():
    error = TimeoutError("simulado")
    funcion = Mock(side_effect=error)
    with patch("consumir_gemini.time.sleep") as mock_sleep:
        with pytest.raises(TimeoutError) as capturado:
            con_reintentos(funcion, intentos=3)
    assert capturado.value is error  # se propaga la excepción original
    assert funcion.call_count == 3
    assert mock_sleep.call_count == 2


def test_con_reintento_respeta_backoff_y_jitter():
    # No se compara la espera exacta (el jitter es aleatorio): solo que crece y que respeta el techo.
    funcion = Mock(side_effect=TimeoutError("simulado"))
    with patch("consumir_gemini.time.sleep") as mock_sleep:
        with pytest.raises(TimeoutError):
            con_reintentos(funcion, intentos=6, espera_base=2, espera_maxima=10)
    esperas = [llamada.args[0] for llamada in mock_sleep.call_args_list]
    for esperada, real in zip([2, 4, 8, 10, 10], esperas):
        assert esperada <= real <= esperada * 1.1


# --- registrar_costo: cálculo y acumulado ---


def test_registrar_costo_calcula_con_precios_reales():
    costo = registrar_costo(RESPUESTA_EXITOSA)
    assert costo == pytest.approx(COSTO_RESPUESTA_EXITOSA)


def test_registrar_costo_acumula():
    registrar_costo(RESPUESTA_EXITOSA)
    registrar_costo(RESPUESTA_EXITOSA)
    assert cliente.costo_total_sesion == pytest.approx(2 * COSTO_RESPUESTA_EXITOSA)


def test_registrar_costo_sin_conteo_de_tokens_no_suma():
    assert registrar_costo({"candidates": []}) == 0.0
    assert cliente.costo_total_sesion == 0.0


# --- consultar_modelo: interfaz pública ---


def test_consultar_modelo_flujo_exitoso():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(200, RESPUESTA_EXITOSA)):
        texto = consultar_modelo("cuánto cuesta el teclado??")
    assert texto == "El K7 cuesta 59.990 CLP."
    assert cliente.costo_total_sesion == pytest.approx(COSTO_RESPUESTA_EXITOSA)


def test_consultar_modelo_integra_reintento_y_costo():
    respuestas = [respuesta_falsa(429), respuesta_falsa(200, RESPUESTA_EXITOSA)]
    with patch("consumir_gemini.requests.post", side_effect=respuestas) as mock_post, \
            patch("consumir_gemini.time.sleep"):
        texto = consultar_modelo("cuánto cuesta el teclado??")
    assert texto == "El K7 cuesta 59.990 CLP."
    assert mock_post.call_count == 2
    assert cliente.costo_total_sesion == pytest.approx(COSTO_RESPUESTA_EXITOSA)  # se cobra una sola vez


def test_consultar_modelo_convierte_error():
    with patch("cliente.con_reintentos", side_effect=TimeoutError("simulado")):
        with pytest.raises(RuntimeError, match="tras varios intentos"):
            consultar_modelo("pregunta de prueba")


def test_consultar_modelo_reintentos_agotados_no_registra_costo():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(429)), \
            patch("consumir_gemini.time.sleep"):
        with pytest.raises(RuntimeError):
            consultar_modelo("pregunta de prueba")
    assert cliente.costo_total_sesion == 0.0


def test_consultar_modelo_propaga_value_error():
    with patch("consumir_gemini.requests.post", return_value=respuesta_falsa(401)) as mock_post:
        with pytest.raises(ValueError, match="Credencial inválida"):
            consultar_modelo("pregunta de prueba")
    assert mock_post.call_count == 1  # no se reintentó


def test_consultar_modelo_entrada_vacia_no_llama_a_la_api():
    with patch("consumir_gemini.requests.post") as mock_post:
        with pytest.raises(ValueError, match="vacía"):
            consultar_modelo("   ")
    mock_post.assert_not_called()
