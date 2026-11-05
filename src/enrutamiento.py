"""Enrutamiento condicional del bot con manejo de errores por paso.

    procesar_mensaje_seguro (try/except general + logging)
    └─ clasificar (con modelo secundario de respaldo)
       ├─ pregunta_producto → responder con los datos → revisar ─┐ fallbacks: modelo secundario
       ├─ interes_compra    → invitar a comprar       → revisar ─┘            → texto fijo verdadero
       └─ cualquier otra    → (sin respuesta), sin llamar al modelo

Decisiones para un bot en un chat en vivo:
- La ruta por defecto es NO responder: ante spam o una categoría inesperada, el bot se queda callado.
- Los fallbacks finales son textos fijos con datos verdaderos de la campaña (precio y link), no una
  promesa como "un miembro del equipo te va a responder", que en un chat de Twitch no se cumpliría.
- Si falla el revisor, no se publica el borrador sin revisar: cae en el texto fijo.
- Si falla todo lo demás, el bot no responde y el error queda registrado con logging.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/enrutamiento.py                   flujo normal
    python3 src/enrutamiento.py --simular-falla   el modelo principal no existe: todo pasa al de respaldo
"""
import logging
import sys

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough

from cadena_tres_pasos import DATOS_CAMPANA, SIN_RESPUESTA, crear_modelo, plantilla_clasificar, plantilla_revisar

logger = logging.getLogger(__name__)

LINK = "https://ejemplo.cl/r/k7"
# Respuestas de respaldo: no necesitan el modelo y siempre son verdaderas.
RESPALDO_PREGUNTA = f"Puedes revisar todos los detalles del teclado mecánico K7 en {LINK}"
RESPALDO_COMPRA = f"El teclado mecánico K7 cuesta 59.990 CLP. Cómpralo en {LINK}"
# Modelo de respaldo: el segundo de la comparación del Bloque 9 (docs/decision-arquitectura.md).
MODELO_SECUNDARIO = "gemini-3.1-flash-lite"

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


def respuesta_fija(texto: str):
    """Un paso que siempre devuelve el mismo texto, sin llamar al modelo."""
    return RunnableLambda(lambda _: texto)


def avisar(descripcion: str):
    """Paso que deja registrado que se está usando un respaldo y deja pasar la entrada sin cambios.

    Un fallback que no avisa oculta el problema: el bot seguiría funcionando con el plan B
    sin que nadie sepa que el modelo principal está caído.
    """
    def registrar(entrada):
        logger.warning("Falló el paso principal; se usa el respaldo: %s", descripcion)
        return entrada

    return RunnableLambda(registrar)


def construir_ruta_segura(ruta, texto_respaldo: str, ruta_secundaria=None):
    """Protege una ruta: si falla, prueba la ruta con el modelo secundario y, si también falla, el texto fijo.

    Cada respaldo que se usa queda registrado como WARNING.
    """
    alternativas = []
    if ruta_secundaria is not None:
        alternativas.append(avisar("ruta con el modelo secundario") | ruta_secundaria)
    alternativas.append(avisar("respuesta fija") | respuesta_fija(texto_respaldo))
    return ruta.with_fallbacks(alternativas)


def construir_cadena_con_enrutamiento(paso_clasificacion, ruta_pregunta=None, ruta_compra=None):
    """Arma la bifurcación. Recibe las piezas como parámetros para poder reemplazarlas por mocks."""
    ruta_pregunta = ruta_pregunta or RunnablePassthrough()
    ruta_compra = ruta_compra or RunnablePassthrough()
    bifurcacion = RunnableBranch(
        (lambda x: x["categoria"] == "pregunta_producto", ruta_pregunta),
        (lambda x: x["categoria"] == "interes_compra", ruta_compra),
        respuesta_fija(SIN_RESPUESTA),  # por defecto: spam, otro o una categoría inesperada
    )
    return (
        RunnablePassthrough.assign(campana=lambda _: DATOS_CAMPANA)
        | RunnablePassthrough.assign(categoria=paso_clasificacion)
        | bifurcacion
    )


def construir_cadena(modelo, modelo_secundario=None):
    """La chain completa, con fallbacks en la clasificación y en cada ruta."""
    clasificacion = construir_paso_clasificacion(modelo)
    ruta_pregunta_2 = ruta_compra_2 = None
    if modelo_secundario is not None:
        clasificacion = clasificacion.with_fallbacks(
            [avisar("clasificación con el modelo secundario") | construir_paso_clasificacion(modelo_secundario)]
        )
        ruta_pregunta_2 = construir_ruta(plantilla_pregunta, modelo_secundario)
        ruta_compra_2 = construir_ruta(plantilla_compra, modelo_secundario)
    return construir_cadena_con_enrutamiento(
        clasificacion,
        ruta_pregunta=construir_ruta_segura(construir_ruta(plantilla_pregunta, modelo), RESPALDO_PREGUNTA, ruta_pregunta_2),
        ruta_compra=construir_ruta_segura(construir_ruta(plantilla_compra, modelo), RESPALDO_COMPRA, ruta_compra_2),
    )


def procesar_mensaje_seguro(cadena, mensaje: str) -> str:
    """Punto de entrada del bot: nunca lanza una excepción.

    Un mensaje vacío no llama al modelo. Si algo falla fuera de los fallbacks (por ejemplo, la
    clasificación con los dos modelos caídos), registra el error con su traceback y el bot no responde.
    """
    if not isinstance(mensaje, str) or not mensaje.strip():
        return SIN_RESPUESTA
    try:
        return cadena.invoke({"mensaje": mensaje})
    except Exception:
        logger.exception("Error procesando el mensaje %r", mensaje)
        return SIN_RESPUESTA


MENSAJES_DE_PRUEBA = [
    "el teclado es inalámbrico?",          # pregunta_producto
    "lo quiero!! cómo lo compro?",         # interes_compra
    "SIGAN MI CANAL, seguidores gratis",   # spam
    "jajaja qué buena jugada",             # otro
]

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    if "--simular-falla" in sys.argv:
        # Un modelo que no existe hace fallar cada llamada (404): todo el flujo pasa al modelo de respaldo.
        print("Simulando que el modelo principal no está disponible...\n")
        modelo = crear_modelo("modelo-que-no-existe")
    else:
        modelo = crear_modelo()
    cadena = construir_cadena(modelo, modelo_secundario=crear_modelo(MODELO_SECUNDARIO))
    for mensaje in MENSAJES_DE_PRUEBA:
        print(f"> {mensaje}\n  {procesar_mensaje_seguro(cadena, mensaje)}\n")
