import json
import os
import re

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


def armar_peticion(pregunta, system_instruction=None, response_schema=None):
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
    body = {"contents": [{"parts": [{"text": pregunta}]}]}
    if system_instruction is not None:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if response_schema is not None:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        }
    return url, headers, body


def enviar_peticion(url, headers, body):
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


def extraer_texto(respuesta_json):
    try:
        return respuesta_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as error:
        raise RuntimeError("La respuesta no trae el texto generado en el lugar esperado.") from error


def parsear_respuesta_json(texto, claves_esperadas=None):
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


def calcular_costo(respuesta_json, precio_entrada, precio_salida):
    try:
        uso = respuesta_json["usageMetadata"]
        tokens_entrada = uso["promptTokenCount"]
        tokens_salida = uso["candidatesTokenCount"] + uso.get("thoughtsTokenCount", 0)
    except KeyError as error:
        raise RuntimeError("La respuesta no trae el conteo de tokens esperado.") from error
    return (tokens_entrada * precio_entrada) + (tokens_salida * precio_salida)


def preguntar_a_gemini(pregunta, system_instruction=None):
    url, headers, body = armar_peticion(pregunta, system_instruction)
    respuesta_json = enviar_peticion(url, headers, body)
    return extraer_texto(respuesta_json)


def mostrar_respuesta(pregunta, system_instruction=None):
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
