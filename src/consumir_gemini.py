"""Módulo de consumo de la API de Gemini para el bot de chat de Twitch.

Arma la petición, la envía, extrae el texto generado, valida la salida JSON y
calcula el costo. La llave se lee del archivo .env y viaja en el header, nunca en la URL.

Son las piezas internas del cliente: el punto de entrada para el resto del proyecto
es consultar_modelo, en src/cliente.py.
"""
import json
import os
import random
import re
import time
from collections.abc import Callable
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

INSTRUCCION_BOT = (
    "Eres el bot de chat de un stream de Twitch con esta campaña publicitaria: "
    "Producto: teclado mecánico K7. Precio: 59.990 CLP. Link de compra: https://ejemplo.cl/r/k7. "
    "No hay descuentos ni comandos de chat. "
    "Usa solo esos datos: si no sabes algo, dilo y invita a revisar el link. "
    "Clasifica el mensaje del viewer en una sola categoría: pregunta_producto, "
    "interes_compra, spam u otro. Responde en una línea con el formato "
    "'categoria | respuesta breve para el chat'."
)

# Reintentos: 4 intentos en total, con esperas de 2, 4 y 8 s (backoff exponencial),
# nunca más de 30 s, más hasta un 10 % al azar (jitter).
INTENTOS = 4
ESPERA_BASE = 2
ESPERA_MAXIMA = 30


def armar_peticion(
    pregunta: str,
    system_instruction: str | None = None,
    response_schema: dict | None = None,
) -> tuple[str, dict, dict]:
    """Valida la entrada y arma la URL, los headers y el body de la petición.

    Si se entrega response_schema, se le exige al modelo una respuesta JSON con esa forma.
    Lanza ValueError si la pregunta o la instrucción están vacías o si falta API_KEY en el .env.
    """
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    if system_instruction is not None and (not isinstance(system_instruction, str) or not system_instruction.strip()):
        raise ValueError("La instrucción de sistema, si se entrega, no puede estar vacía.")
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("No se encontró la variable API_KEY en el archivo .env.")
    modelo = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body: dict[str, Any] = {"contents": [{"parts": [{"text": pregunta}]}]}
    if system_instruction is not None:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if response_schema is not None:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        }
    return url, headers, body


def enviar_peticion(url: str, headers: dict, body: dict) -> dict:
    """Envía la petición POST (timeout de 30 s) y clasifica los errores según si conviene reintentar.

    - ValueError: credencial inválida o sin permiso (400 por llave inválida, 401, 403). No se reintenta.
    - TimeoutError: límite de uso (429), falla del proveedor (5xx) o sin conexión. Se reintenta.
    - RuntimeError: cualquier otro error de la petición o una respuesta que no es JSON.
    """
    try:
        respuesta = requests.post(url, headers=headers, json=body, timeout=30)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
        raise TimeoutError("No se pudo contactar al proveedor. Puede ser momentáneo.") from error
    codigo = respuesta.status_code
    llave_invalida = codigo == 400 and "API_KEY_INVALID" in respuesta.text
    if codigo in (401, 403) or llave_invalida:
        raise ValueError("Credencial inválida o sin permiso. Revisa tu API_KEY en el archivo .env.")
    if codigo == 429 or codigo >= 500:
        raise TimeoutError(f"El proveedor no pudo procesar la petición (código {codigo}). Hay que esperar y reintentar.")
    if not respuesta.ok:
        raise RuntimeError(f"El servicio respondió con un error (código {codigo}).")
    try:
        return respuesta.json()
    except requests.exceptions.JSONDecodeError as error:
        raise RuntimeError("La respuesta del servicio no llegó en el formato esperado.") from error


def con_reintentos(
    funcion: Callable[[], Any],
    intentos: int = INTENTOS,
    espera_base: float = ESPERA_BASE,
    espera_maxima: float = ESPERA_MAXIMA,
) -> tuple[Any, int]:
    """Ejecuta funcion() y la reintenta solo si lanza TimeoutError, con backoff exponencial y jitter.

    La espera se duplica en cada intento (2, 4, 8 s…), nunca supera espera_maxima y se le suma
    hasta un 10 % al azar, para que varios clientes no reintenten todos al mismo tiempo.
    Un ValueError (credencial inválida) u otro error se propaga de inmediato, sin reintentar.
    Devuelve (resultado, intentos). Si se agotan los intentos, relanza el TimeoutError
    con el atributo `intentos`.
    """
    for intento in range(1, intentos + 1):
        try:
            return funcion(), intento
        except TimeoutError as error:
            if intento == intentos:
                error.intentos = intento
                raise
            espera = min(espera_base * (2 ** (intento - 1)), espera_maxima)
            espera_con_jitter = espera + random.uniform(0, espera * 0.1)
            print(f"Intento {intento} de {intentos} falló. Reintentando en {espera_con_jitter:.1f}s...")
            time.sleep(espera_con_jitter)
    raise AssertionError("inalcanzable")


def extraer_texto(respuesta_json: dict) -> str:
    """Devuelve el texto generado (candidates[0].content.parts[0].text).

    Lanza RuntimeError si la respuesta no trae el texto en ese lugar.
    """
    try:
        return respuesta_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as error:
        raise RuntimeError("La respuesta no trae el texto generado en el lugar esperado.") from error


def parsear_respuesta_json(texto: str, claves_esperadas: list[str] | None = None) -> dict:
    """Convierte el texto del modelo en un diccionario y verifica que traiga las claves esperadas.

    Quita los bloques ```json si el modelo los agrega. Lanza ValueError si el texto no es
    un objeto JSON válido o si le faltan claves.
    """
    texto_limpio = texto.strip()
    texto_limpio = re.sub(r"^```(?:json)?\s*", "", texto_limpio)
    texto_limpio = re.sub(r"\s*```$", "", texto_limpio)
    try:
        datos = json.loads(texto_limpio)
    except json.JSONDecodeError as error:
        raise ValueError("La respuesta del modelo no es JSON válido.") from error
    if not isinstance(datos, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON.")
    faltantes = [clave for clave in (claves_esperadas or []) if clave not in datos]
    if faltantes:
        raise ValueError(f"La respuesta no tiene la estructura esperada: faltan {', '.join(faltantes)}.")
    return datos


def calcular_costo(respuesta_json: dict, precio_entrada: float, precio_salida: float) -> float:
    """Calcula el costo en USD de una petición a partir de usageMetadata.

    Los precios van por token. La salida incluye los tokens de razonamiento (thoughtsTokenCount),
    que se cobran como salida. Lanza RuntimeError si falta el conteo de tokens.
    """
    try:
        uso = respuesta_json["usageMetadata"]
        tokens_entrada = uso["promptTokenCount"]
        tokens_salida = uso["candidatesTokenCount"] + uso.get("thoughtsTokenCount", 0)
    except KeyError as error:
        raise RuntimeError("La respuesta no trae el conteo de tokens esperado.") from error
    return (tokens_entrada * precio_entrada) + (tokens_salida * precio_salida)
