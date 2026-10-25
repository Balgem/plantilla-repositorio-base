"""Módulo de consumo de la API de Gemini para el bot de chat de Twitch.

Arma la petición, la envía, extrae el texto generado, valida la salida JSON y
calcula el costo. La llave se lee del archivo .env y viaja en el header, nunca en la URL.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/consumir_gemini.py
"""
import json
import os
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

ESPERAS_REINTENTO = (2, 4, 8)  # segundos entre reintentos (backoff exponencial)


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
    """Envía la petición POST (timeout de 30 s) y devuelve la respuesta como diccionario.

    Lanza RuntimeError si no hay conexión, si el servicio responde con un código 4xx o 5xx,
    o si la respuesta no es JSON.
    """
    try:
        respuesta = requests.post(url, headers=headers, json=body, timeout=30)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
        raise RuntimeError("No se pudo conectar con el servicio. Intenta de nuevo en unos segundos.") from error
    if not respuesta.ok:
        raise RuntimeError(f"El servicio respondió con un error (código {respuesta.status_code}).")
    try:
        return respuesta.json()
    except requests.exceptions.JSONDecodeError as error:
        raise RuntimeError("La respuesta del servicio no llegó en el formato esperado.") from error


def es_error_reintentable(error: Exception) -> bool:
    """Indica si vale la pena reintentar: saturación (429), falla del servicio (5xx) o sin conexión."""
    mensaje = str(error)
    codigo = re.search(r"código (\d{3})", mensaje)
    if codigo:
        return codigo.group(1) == "429" or codigo.group(1).startswith("5")
    return "No se pudo conectar" in mensaje


def con_reintentos(funcion: Callable[[], Any], esperas: tuple[int, ...] = ESPERAS_REINTENTO) -> tuple[Any, int]:
    """Ejecuta funcion() y la reintenta con espera creciente ante errores reintentables.

    Devuelve (resultado, intentos). Si se agotan los reintentos o el error no es reintentable,
    relanza el RuntimeError con el atributo `intentos` para saber cuántas veces se probó.
    """
    for intento, espera in enumerate([*esperas, None], start=1):
        try:
            return funcion(), intento
        except RuntimeError as error:
            if espera is None or not es_error_reintentable(error):
                error.intentos = intento
                raise
            time.sleep(espera)
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


def preguntar_a_gemini(pregunta: str, system_instruction: str | None = None) -> str:
    """Hace el recorrido completo (armar, enviar con reintentos, extraer) y devuelve el texto."""
    url, headers, body = armar_peticion(pregunta, system_instruction)
    respuesta_json, _ = con_reintentos(lambda: enviar_peticion(url, headers, body))
    return extraer_texto(respuesta_json)


def mostrar_respuesta(pregunta: str, system_instruction: str | None = None) -> None:
    """Imprime la respuesta del modelo o un mensaje claro si algo falla, sin cortar el programa."""
    try:
        print(preguntar_a_gemini(pregunta, system_instruction))
    except (ValueError, RuntimeError) as error:
        print("No se pudo completar la operación:", error)


if __name__ == "__main__":
    print("--- Entrada vacía ---")
    mostrar_respuesta("")
    print("--- Entrada válida, sin instrucción de sistema ---")
    mostrar_respuesta("Confirma en una frase corta que esta conexión funciona")
    print("--- Mensajes del chat, con la instrucción del bot como sistema ---")
    for mensaje in ["cuánto cuesta el teclado??", "hacen envíos a regiones?"]:
        print(f"> {mensaje}")
        mostrar_respuesta(mensaje, INSTRUCCION_BOT)
