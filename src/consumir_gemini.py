import os
import requests
from dotenv import load_dotenv

load_dotenv()


def armar_peticion(pregunta):
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("No se encontró la variable API_KEY en el archivo .env.")
    modelo = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body = {"contents": [{"parts": [{"text": pregunta}]}]}
    return url, headers, body


def enviar_peticion(url, headers, body):
    try:
        respuesta = requests.post(url, headers=headers, json=body, timeout=30)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise RuntimeError("No se pudo conectar con el servicio. Intenta de nuevo en unos segundos.")
    if not respuesta.ok:
        raise RuntimeError(f"El servicio respondió con un error (código {respuesta.status_code}).")
    try:
        return respuesta.json()
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError("La respuesta del servicio no llegó en el formato esperado.")


def extraer_texto(respuesta_json):
    try:
        return respuesta_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError("La respuesta no trae el texto generado en el lugar esperado.")


def preguntar_a_gemini(pregunta):
    url, headers, body = armar_peticion(pregunta)
    respuesta_json = enviar_peticion(url, headers, body)
    return extraer_texto(respuesta_json)


def mostrar_respuesta(pregunta):
    try:
        print(preguntar_a_gemini(pregunta))
    except (ValueError, RuntimeError) as error:
        print("No se pudo completar la operación:", error)


if __name__ == "__main__":
    print("--- Entrada vacía ---")
    mostrar_respuesta("")
    print("--- Entrada válida ---")
    mostrar_respuesta("Confirma en una frase corta que esta conexión funciona")