"""Chain de tres pasos con LangChain para el bot de chat: clasificar → redactar → revisar.

1. Clasificar: decide qué tipo de mensaje es (pregunta_producto, interes_compra, spam u otro).
2. Redactar: escribe la respuesta para el chat según esa categoría, usando solo los datos de la campaña.
3. Revisar: compara el borrador con los datos de la campaña y corrige cualquier dato inventado
   (precio, descuento, envío) antes de publicarlo.

Cada paso depende del anterior: el redactor necesita la categoría para decidir si responde,
y el revisor necesita el borrador para corregirlo. El paso 3 existe porque en el Bloque 17
vimos que la métrica no detecta un precio falso ni una negación ausente.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/cadena_tres_pasos.py
"""
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

DATOS_CAMPANA = (
    "Producto: teclado mecánico K7. Precio: 59.990 CLP. Link de compra: https://ejemplo.cl/r/k7. "
    "No hay descuentos ni códigos de descuento. No hay información sobre envíos, garantía ni otras características."
)
SIN_RESPUESTA = "(sin respuesta)"

# Paso 1 · Responsabilidad: decidir de qué tipo es el mensaje, en una sola palabra.
plantilla_clasificar = PromptTemplate.from_template(
    "Clasifica este mensaje del chat de un stream de Twitch con una campaña publicitaria. "
    "Responde solo con una de estas palabras, sin nada más: pregunta_producto, interes_compra, spam u otro.\n\n"
    "Mensaje: {mensaje}"
)

# Paso 2 · Responsabilidad: escribir la respuesta para el chat según la categoría.
plantilla_redactar = PromptTemplate.from_template(
    "Eres el bot de chat de una campaña publicitaria en Twitch. Datos de la campaña: {campana}\n"
    "El mensaje se clasificó como: {categoria}\n"
    "Si la categoría es spam u otro, responde exactamente: " + SIN_RESPUESTA + "\n"
    "Si no, escribe una respuesta breve y amable en español, usando solo los datos de la campaña. "
    "Si te preguntan algo que no está en los datos, di que no tienes esa información e invita a revisar el link.\n\n"
    "Mensaje: {mensaje}"
)

# Paso 3 · Responsabilidad: corregir datos inventados en el borrador antes de publicarlo.
plantilla_revisar = PromptTemplate.from_template(
    "Revisa este borrador de respuesta para el chat contra los datos de la campaña: {campana}\n"
    "Corrige cualquier precio, link, descuento, envío o característica que no coincida con los datos o que no "
    "esté en ellos, y quita cualquier promesa que la campaña no hace. No agregues información que el borrador no tenía "
    "y deja la respuesta en máximo 2 frases, porque es para un chat en vivo. Si el borrador es exactamente "
    + SIN_RESPUESTA + ", devuélvelo igual. Devuelve solo la respuesta final, sin explicaciones.\n\n"
    "Borrador: {borrador}"
)


def construir_cadena(modelo):
    """Arma la chain de tres pasos sin ejecutarla. Recibe el modelo como parámetro para poder usar un mock.

    Entrada: {"mensaje": "..."}. Salida: el texto final para publicar en el chat (str).
    """
    paso_clasificar = plantilla_clasificar | modelo | StrOutputParser()
    paso_redactar = plantilla_redactar | modelo | StrOutputParser()
    paso_revisar = plantilla_revisar | modelo | StrOutputParser()

    return (
        # Agrega los datos de la campaña y la categoría, sin perder el mensaje original
        RunnablePassthrough.assign(campana=lambda _: DATOS_CAMPANA)
        | RunnablePassthrough.assign(categoria=paso_clasificar | (lambda texto: texto.strip().lower()))
        # El borrador se agrega al mismo diccionario, para que el revisor tenga también la campaña
        | RunnablePassthrough.assign(borrador=paso_redactar)
        | paso_revisar
    )


def crear_modelo(nombre: str | None = None):
    """Crea un modelo de Gemini con la llave del .env. Por defecto, el modelo de GEMINI_MODEL.

    - No se pasa temperature: gemini-3.5-flash-lite usa valores de muestreo fijos y la ignora.
    - timeout=30: si Gemini no responde, la demora se convierte en excepción (y salta el fallback).
    - max_retries=2: el conector reintenta 6 veces por defecto; con 2 se llega antes al plan B.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=nombre or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        google_api_key=os.getenv("API_KEY"),
        timeout=30,
        max_retries=2,
    )


MENSAJES_DE_PRUEBA = [
    "cuánto cuesta el teclado que estás usando?? 👀",
    "compro 2 si me hacen un 20% de descuento, dale",
    "SIGAN MI CANAL, seguidores gratis en bit.ly/regalo",
]

if __name__ == "__main__":
    load_dotenv()
    cadena = construir_cadena(crear_modelo())
    for mensaje in MENSAJES_DE_PRUEBA:
        print(f"> {mensaje}")
        print(f"  {cadena.invoke({'mensaje': mensaje})}\n")
