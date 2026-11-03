"""Enrutamiento condicional del bot: cada tipo de mensaje sigue su propio camino.

    mensaje → clasificar ─┬─ pregunta_producto → responder con los datos → revisar
                          ├─ interes_compra    → invitar a comprar       → revisar
                          └─ cualquier otra    → (sin respuesta), sin llamar al modelo

La ruta por defecto es NO responder: si el clasificador devuelve spam, otro o algo inesperado,
el bot se queda callado. Para un bot de marca es más seguro callar que responder spam.
Además ahorra llamadas: un spam cuesta 1 llamada (la clasificación) en vez de 3.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/enrutamiento.py
"""
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough

from cadena_tres_pasos import DATOS_CAMPANA, SIN_RESPUESTA, crear_modelo, plantilla_clasificar, plantilla_revisar

# Ruta 1 · Responder una pregunta sobre el producto, solo con los datos de la campaña.
plantilla_pregunta = PromptTemplate.from_template(
    "Eres el bot de chat de una campaña publicitaria en Twitch. Datos de la campaña: {campana}\n"
    "Un viewer hizo esta pregunta sobre el producto. Respóndela en una o dos frases, en español, usando solo "
    "los datos de la campaña. Si no está en los datos, di que no tienes esa información e invita a revisar el link.\n\n"
    "Pregunta: {mensaje}"
)

# Ruta 2 · Aprovechar el interés de compra: precio y link, con una invitación directa a comprar.
plantilla_compra = PromptTemplate.from_template(
    "Eres el bot de chat de una campaña publicitaria en Twitch. Datos de la campaña: {campana}\n"
    "Un viewer quiere comprar. Responde en una frase entusiasta, en español, con el precio y el link de compra. "
    "No ofrezcas descuentos ni beneficios que no estén en los datos.\n\n"
    "Mensaje: {mensaje}"
)


def construir_paso_clasificacion(modelo):
    """Clasifica el mensaje y normaliza la respuesta (minúsculas, sin espacios) antes de comparar."""
    return plantilla_clasificar | modelo | StrOutputParser() | (lambda texto: texto.strip().lower())


def construir_ruta(plantilla, modelo):
    """Una ruta de respuesta: redacta con su propia plantilla y después pasa por el revisor."""
    redactar = plantilla | modelo | StrOutputParser()
    revisar = plantilla_revisar | modelo | StrOutputParser()
    return RunnablePassthrough.assign(borrador=redactar) | revisar


def construir_cadena_con_enrutamiento(paso_clasificacion, ruta_pregunta=None, ruta_compra=None):
    """Arma la bifurcación. Recibe las piezas como parámetros para poder reemplazarlas por mocks."""
    ruta_pregunta = ruta_pregunta or RunnablePassthrough()
    ruta_compra = ruta_compra or RunnablePassthrough()
    bifurcacion = RunnableBranch(
        (lambda x: x["categoria"] == "pregunta_producto", ruta_pregunta),
        (lambda x: x["categoria"] == "interes_compra", ruta_compra),
        RunnableLambda(lambda x: SIN_RESPUESTA),  # por defecto: spam, otro o una categoría inesperada
    )
    return (
        RunnablePassthrough.assign(campana=lambda _: DATOS_CAMPANA)
        | RunnablePassthrough.assign(categoria=paso_clasificacion)
        | bifurcacion
    )


def construir_cadena(modelo):
    """La chain completa con el modelo real (o un modelo falso en las pruebas)."""
    return construir_cadena_con_enrutamiento(
        construir_paso_clasificacion(modelo),
        ruta_pregunta=construir_ruta(plantilla_pregunta, modelo),
        ruta_compra=construir_ruta(plantilla_compra, modelo),
    )


MENSAJES_DE_PRUEBA = [
    "el teclado es inalámbrico?",          # pregunta_producto
    "lo quiero!! cómo lo compro?",         # interes_compra
    "SIGAN MI CANAL, seguidores gratis",   # spam
    "jajaja qué buena jugada",             # otro
]

if __name__ == "__main__":
    load_dotenv()
    modelo = crear_modelo()
    paso_clasificacion = construir_paso_clasificacion(modelo)
    cadena = construir_cadena(modelo)
    for mensaje in MENSAJES_DE_PRUEBA:
        categoria = paso_clasificacion.invoke({"mensaje": mensaje})
        print(f"> {mensaje}\n  [{categoria}] {cadena.invoke({'mensaje': mensaje})}\n")
