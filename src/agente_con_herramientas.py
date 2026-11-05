"""Agente del bot con tres herramientas propias (Bloque 21).

A diferencia de la chain con enrutamiento (Bloque 19), aquí el modelo decide en cada consulta
qué herramienta usar, en qué orden, o si no necesita ninguna:

- consultar_campana: datos de la campaña (precio, link, descuentos, características).
- consultar_viewers: cuántas personas están viendo el stream.
- registrar_interes_compra: guarda en el CRM a un viewer que quiere comprar.

En el bot completo, el filtro de spam sigue siendo la chain del Bloque 19 (barata y predecible);
el agente entra solo con los mensajes que merecen respuesta.

Los datos de viewers y el CRM son simulados en esta etapa: en el Gate 2 se conectan a la API de
Twitch y al CRM real.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/agente_con_herramientas.py
"""
import logging
import re
from datetime import datetime

from dotenv import load_dotenv
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from cadena_tres_pasos import SIN_RESPUESTA, crear_modelo
from enrutamiento import MODELO_SECUNDARIO

logger = logging.getLogger(__name__)

DATOS_CAMPANA = {
    "precio": "El teclado mecánico K7 cuesta 59.990 CLP.",
    "link": "El link de compra es https://ejemplo.cl/r/k7",
    "descuento": "No hay descuentos ni códigos de descuento.",
    "mecánico": "Sí, el K7 es un teclado mecánico.",
}

# Simulación: en el Gate 2 esto se reemplaza por la API de Twitch y el CRM real.
CANAL = "canal_demo"  # el canal lo define la configuración del bot, no el viewer ni el modelo
VIEWERS_SIMULADOS = {"canal_demo": 1200}
REGISTRO_CRM: list[dict] = []


@tool
def consultar_campana(dato: str) -> str:
    """Devuelve un dato oficial de la campaña del teclado K7: precio, link de compra, descuentos o si es mecánico.
    Usar siempre que el viewer pregunte por el producto, cuánto cuesta, dónde comprarlo o si hay descuentos,
    antes de responder, para no inventar datos."""
    texto = dato.lower()
    for clave, valor in DATOS_CAMPANA.items():
        if clave in texto:
            return valor
    if "comprar" in texto or "compro" in texto:
        return DATOS_CAMPANA["link"]
    return "Ese dato no está en la campaña: hay que decir que no se tiene esa información e invitar a revisar el link."


@tool
def consultar_viewers() -> str:
    """Devuelve cuántas personas están viendo el stream en este momento. No necesita argumentos.
    Usar solo cuando el viewer pregunta cuánta gente está mirando o cuántos espectadores hay."""
    try:
        return f"{VIEWERS_SIMULADOS[CANAL]} personas están viendo el stream."
    except KeyError:
        return "No se pudo obtener la cantidad de viewers en este momento."


@tool
def registrar_interes_compra(usuario: str, mensaje: str) -> str:
    """Registra en el CRM a un viewer que muestra intención clara de comprar el producto
    (por ejemplo, 'lo quiero', 'cómo lo compro', 'me lo compro'). No usar para preguntas generales,
    saludos ni spam. Recibe el nombre del viewer y su mensaje."""
    try:
        REGISTRO_CRM.append({"usuario": usuario, "mensaje": mensaje, "fecha": datetime.now().isoformat()})
        return f"Interés de compra de {usuario} registrado en el CRM."
    except Exception as error:  # en el CRM real puede fallar la conexión
        return f"No se pudo registrar el interés de compra: {error}"


HERRAMIENTAS = [consultar_campana, consultar_viewers, registrar_interes_compra]

prompt_agente = ChatPromptTemplate.from_messages([
    (
        "system",
        "Eres el bot de chat de una campaña publicitaria del teclado mecánico K7 en un stream de Twitch. "
        "Responde en español, en una o dos frases. Para cualquier dato del producto usa consultar_campana: "
        "nunca inventes precios, descuentos ni características, y no agregues frases promocionales que no "
        "vengan de las herramientas (stock, unidades limitadas, ofertas por tiempo limitado, envío gratis). Si el viewer quiere comprar, regístralo con "
        "registrar_interes_compra y dale el link. Si te preguntan algo que no tiene que ver con la campaña ni "
        "con el stream, responde breve y amable, sin usar herramientas.",
    ),
    ("human", "{entrada}"),
    MessagesPlaceholder("agent_scratchpad"),
])


class AvisarFallosDelModelo(BaseCallbackHandler):
    """Registra cada vez que una llamada al modelo falla (por ejemplo, un 503), aunque el respaldo la cubra."""

    def on_llm_error(self, error, **kwargs):
        logger.warning("Falló una llamada al modelo (%s); se usa el modelo de respaldo si está configurado.", error)


def construir_agente(modelo, verbose: bool = False, modelo_secundario=None) -> AgentExecutor:
    """Arma el agente. Recibe el modelo como parámetro para poder usar un modelo falso en las pruebas.

    - modelo_secundario: si una llamada al modelo principal falla (503, timeout), esa misma llamada se repite
      con el de respaldo, sin volver a ejecutar las herramientas que ya corrieron (no registra dos veces en el CRM).
    - max_iterations=5: un mensaje del chat no debería necesitar más de 2 o 3 herramientas; si el agente
      se queda dando vueltas, se corta antes que el valor por defecto (15) para no gastar llamadas.
    """
    if modelo_secundario is not None:
        # El aviso va en una copia del modelo principal: cada llamada que falle queda registrada
        # aunque la cubra el respaldo (manejar un error no es ocultarlo).
        principal = modelo.model_copy(update={"callbacks": [AvisarFallosDelModelo()]})
        modelo = principal.with_fallbacks([modelo_secundario])
    agente = create_tool_calling_agent(modelo, HERRAMIENTAS, prompt_agente)
    return AgentExecutor(
        agent=agente,
        tools=HERRAMIENTAS,
        verbose=verbose,
        return_intermediate_steps=True,
        max_iterations=5,
    )


def texto_de_salida(salida) -> str:
    """Deja la respuesta como texto plano para el chat.

    Gemini 3.x a veces devuelve una lista de bloques ([{'type': 'text', 'text': ..., 'extras': {...}}])
    en vez de un string; se juntan solo los bloques de texto.
    """
    if isinstance(salida, str):
        return salida
    if isinstance(salida, list):
        partes = [b.get("text", "") if isinstance(b, dict) else str(b) for b in salida]
        return "".join(partes).strip()
    return str(salida)


# Promesas que la campaña no hace. La instrucción de sistema ya las prohíbe, pero en las pruebas manuales
# el modelo igual escribió "¡Unidades limitadas!": una instrucción no garantiza el comportamiento.
PROMESAS_PROHIBIDAS = re.compile(
    r"unidades limitadas|últimas unidades|ultimas unidades|stock|por tiempo limitado|oferta|"
    r"env[ií]o gratis|gratis|2x1|precio especial",
    re.IGNORECASE,
)


def quitar_promesas_inventadas(texto: str) -> str:
    """Quita de la respuesta las frases con promesas que la campaña no hace (chequeo determinista).

    Trabaja por frase: si una frase menciona stock, ofertas, envío gratis u otra promesa prohibida,
    se elimina completa y queda registrado un WARNING. El resto de la respuesta se publica igual.
    """
    frases = re.split(r"(?<=[.!?])\s+", texto.strip())
    permitidas = [f for f in frases if not PROMESAS_PROHIBIDAS.search(f)]
    if len(permitidas) < len(frases):
        quitadas = [f for f in frases if PROMESAS_PROHIBIDAS.search(f)]
        logger.warning("Se quitaron promesas que la campaña no hace: %s", quitadas)
    return " ".join(permitidas) if permitidas else SIN_RESPUESTA


def procesar_mensaje_agente(ejecutor: AgentExecutor, entrada: str) -> dict:
    """Invoca al agente sin que una falla tumbe el programa (Bloque 20) y devuelve la respuesta como texto.

    Si el agente falla aun con el respaldo, registra el error y el bot no responde.
    """
    try:
        resultado = ejecutor.invoke({"entrada": entrada})
        return {**resultado, "output": quitar_promesas_inventadas(texto_de_salida(resultado["output"]))}
    except Exception:
        logger.exception("El agente no pudo procesar %r", entrada)
        return {"output": SIN_RESPUESTA, "intermediate_steps": []}


def herramientas_usadas(resultado: dict) -> list[str]:
    """Los nombres de las herramientas que usó el agente, en orden (desde intermediate_steps)."""
    return [accion.tool for accion, _ in resultado["intermediate_steps"]]


# Pruebas manuales: cada entrada debería disparar estas herramientas.
CASOS = [
    ("[ana_gamer] cuánto cuesta el teclado??", ["consultar_campana"]),
    ("[pedro99] cuánta gente está viendo ahora?", ["consultar_viewers"]),
    ("[juli_k] lo quiero!! cómo lo compro?", ["registrar_interes_compra", "consultar_campana"]),
    ("[tomas] jajaja qué buena jugada", []),
]

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    ejecutor = construir_agente(crear_modelo(), verbose=True, modelo_secundario=crear_modelo(MODELO_SECUNDARIO))
    for entrada, esperadas in CASOS:
        resultado = procesar_mensaje_agente(ejecutor, entrada)
        usadas = herramientas_usadas(resultado)
        ok = sorted(usadas) == sorted(esperadas)
        print(f"\n{'✅' if ok else '⚠️ '} {entrada}")
        print(f"   Herramientas usadas: {usadas or 'ninguna'} (esperadas: {esperadas or 'ninguna'})")
        print(f"   Respuesta: {resultado['output']}\n")
    print(f"Registros en el CRM simulado: {REGISTRO_CRM}")
