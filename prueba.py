import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("API_KEY"))
respuesta = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="Di hola en una frase corta",
)
print(respuesta.text)