import os
import requests
from dotenv import load_dotenv

load_dotenv()


def obtener_dato_de_prueba(pregunta):
    api_key = os.getenv("API_KEY")
    modelo = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body = {
        "contents": [
            {"parts": [{"text": pregunta}]}
        ]
    }
    respuesta = requests.post(url, headers=headers, json=body)
    datos = respuesta.json()
    return datos["candidates"][0]["content"]["parts"][0]["text"]


print(obtener_dato_de_prueba("Confirma en una frase corta que esta conexión funciona"))