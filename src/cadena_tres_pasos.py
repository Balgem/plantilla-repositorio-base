"""Chain de tres pasos (Bloque 18): clasificar -> redactar -> revisar.

El paso 1 usa salida estructurada (Clasificacion) cuando el modelo la soporta, así solo puede
devolver una de las 4 categorías. El paso 3 corrige datos inventados antes de publicar.

Uso:
    python3 src/cadena_tres_pasos.py
"""
import logging
import os
from typing import Literal

from dotenv import load_dotenv
from configuracion import clave_api
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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

CATEGORIAS_CHAIN = ("pregunta_producto", "interes_compra", "spam", "otro")


class Clasificacion(BaseModel):
    """Salida estructurada del paso 1: la API solo puede devolver una de las categorías de la chain."""

    categoria: Literal["pregunta_producto", "interes_compra", "spam", "otro"] = Field(
        description="Tipo de mensaje del chat de Twitch con una campaña publicitaria.")


def construir_clasificador(modelo):
    """Paso 1: devuelve la categoría. Usa salida estructurada si el modelo la soporta; si no, texto normalizado."""
    if isinstance(modelo, BaseChatModel):
        try:
            estructurado = modelo.with_structured_output(Clasificacion)
        except NotImplementedError:
            estructurado = None
        if estructurado is not None:
            return plantilla_clasificar | estructurado | (lambda resultado: resultado.categoria)
    return plantilla_clasificar | modelo | StrOutputParser() | (lambda texto: texto.strip().lower())


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
    """Arma la chain de tres pasos sin ejecutarla. Recibe el modelo como parámetro para poder usar un mock."""
    paso_clasificar = construir_clasificador(modelo)
    paso_redactar = plantilla_redactar | modelo | StrOutputParser()
    paso_revisar = plantilla_revisar | modelo | StrOutputParser()

    return (
        # Agrega los datos de la campaña y la categoría, sin perder el mensaje original
        RunnablePassthrough.assign(campana=lambda _: DATOS_CAMPANA)
        | RunnablePassthrough.assign(categoria=paso_clasificar)
        # El borrador se agrega al mismo diccionario, para que el revisor tenga también la campaña
        | RunnablePassthrough.assign(borrador=paso_redactar)
        | paso_revisar
    )


def crear_modelo(nombre: str | None = None):
    """Crea un modelo de Gemini con la llave del .env. Por defecto, el modelo de GEMINI_MODEL."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=nombre or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        google_api_key=clave_api(),
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
