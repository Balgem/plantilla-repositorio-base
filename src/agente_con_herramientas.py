"""Agente del bot con sus herramientas propias (Bloques 21 a 23).

A diferencia de la chain con enrutamiento (Bloque 19), aquí el modelo decide en cada consulta
qué herramienta usar, en qué orden, o si no necesita ninguna:

- consultar_campana: datos de la campaña. Desde el Gate 2 responde con el RAG (logging_rag.responder) y
  devuelve la respuesta con su fuente; si el RAG no está configurado, usa los datos fijos, también con su fuente.
- consultar_viewers: cuántas personas están viendo el stream.
- registrar_interes_compra: guarda en el CRM a un viewer que quiere comprar.
- marcar_comentario_negativo (Bloque 23): deja con flag un comentario negativo sobre el producto o la marca.
  No lo manda a nadie: queda pendiente para la revisión humana del reporte post-stream (src/reporte_marca.py).

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
from pydantic import BaseModel, Field

from cadena_tres_pasos import SIN_RESPUESTA, crear_modelo
from privacidad import huella
from enrutamiento import MODELO_SECUNDARIO

logger = logging.getLogger(__name__)

LINK_OFICIAL = "https://ejemplo.cl/r/k7"

DATOS_CAMPANA = {
    "precio": "El teclado mecánico K7 cuesta 59.990 CLP.",
    "link": f"El link de compra es {LINK_OFICIAL}",
    "descuento": "No hay descuentos ni códigos de descuento.",
    "mecánico": "Sí, el K7 es un teclado mecánico.",
}
# De qué documento del corpus sale cada dato fijo (criterio 2 del Gate 2: toda respuesta cita su fuente).
FUENTE_DATO = {"precio": "02_precio_y_compra.md", "link": "02_precio_y_compra.md",
               "descuento": "02_precio_y_compra.md", "mecánico": "01_ficha_tecnica.md"}

ETIQUETA_FUENTE = re.compile(r"\(Fuentes?: ([^)]+)\)")


def etiqueta_fuentes(fuentes: list[str]) -> str:
    """'(Fuente: 03_despacho.md)' o '(Fuentes: a.md, b.md)': la cita que ve el viewer en el chat."""
    return f"(Fuente{'s' if len(fuentes) > 1 else ''}: {', '.join(fuentes)})" if fuentes else ""


def fuentes_de(texto: str) -> list[str]:
    """Las fuentes citadas en un texto con etiqueta_fuentes."""
    return [f.strip() for m in ETIQUETA_FUENTE.finditer(texto or "") for f in m.group(1).split(",")]


# El RAG se conecta al arrancar el servicio (main.py / servicio_rag.py): configurar_rag(lambda pregunta: ...).
# Recibe la pregunta y devuelve {"respuesta": texto ya filtrado y con fuente, "fuentes": [...]}.
_responder_rag = None


def configurar_rag(responder) -> None:
    """responder(pregunta) -> {"respuesta", "fuentes"}. None vuelve a los datos fijos."""
    global _responder_rag
    _responder_rag = responder

# Simulación: en el Gate 2 esto se reemplaza por la API de Twitch y el CRM real.
CANAL = "canal_demo"  # el canal lo define la configuración del bot, no el viewer ni el modelo
VIEWERS_SIMULADOS = {"canal_demo": 1200}
REGISTRO_CRM: list[dict] = []


@tool
def consultar_campana(dato: str) -> str:
    """Devuelve un dato oficial de la campaña del teclado K7: precio, link de compra, descuentos o si es mecánico.
    Usar siempre que el viewer pregunte por el producto, cuánto cuesta, dónde comprarlo o si hay descuentos,
    antes de responder, para no inventar datos."""
    if _responder_rag is not None:
        resultado = _responder_rag(dato)
        if resultado["fuentes"]:
            return resultado["respuesta"]  # ya trae "(Fuente: ...)"
        return ("Ese dato no está en la información de la campaña: di que no tienes ese dato del K7, "
                "sin inventarlo.")
    texto = dato.lower()
    for clave, valor in DATOS_CAMPANA.items():
        if clave in texto:
            return f"{valor} {etiqueta_fuentes([FUENTE_DATO[clave]])}"
    if "comprar" in texto or "compro" in texto:
        return f"{DATOS_CAMPANA['link']} {etiqueta_fuentes([FUENTE_DATO['link']])}"
    return "Ese dato no está en la campaña: hay que decir que no se tiene esa información e invitar a revisar el link."


@tool
def consultar_viewers() -> str:
    """Devuelve cuántas personas están viendo el stream en este momento. No necesita argumentos.
    Usar solo cuando el viewer pregunta cuánta gente está mirando o cuántos espectadores hay."""
    try:
        return f"{VIEWERS_SIMULADOS[CANAL]} personas están viendo el stream."
    except KeyError:
        return "No se pudo obtener la cantidad de viewers en este momento."


class ArgumentosInteresCompra(BaseModel):
    """Argumentos de registrar_interes_compra (Bloque 22): cada uno con su propia descripción para el modelo."""

    usuario: str = Field(description="Nombre del viewer tal como aparece entre corchetes al inicio del mensaje, "
                                     "por ejemplo 'juli_k'. No inventarlo.")
    mensaje: str = Field(description="El mensaje original del viewer, sin cambios.")
    cantidad: int = Field(default=1, ge=1, description="Cuántas unidades quiere comprar; 1 si no lo dice.")


@tool("registrar_interes_compra", args_schema=ArgumentosInteresCompra)
def registrar_interes_compra(usuario: str, mensaje: str, cantidad: int = 1) -> str:
    """Registra en el CRM a un viewer que muestra intención clara de comprar el producto
    (por ejemplo, 'lo quiero', 'cómo lo compro', 'me lo compro', 'compro 2'). No usar para preguntas generales,
    saludos ni spam. Si el viewer ya estaba registrado, actualiza la cantidad en vez de duplicarlo."""
    try:
        for registro in REGISTRO_CRM:
            if registro["usuario"] == usuario:
                registro.update({"mensaje": mensaje, "cantidad": cantidad, "fecha": datetime.now().isoformat()})
                return f"{usuario} ya estaba registrado en el CRM; se actualizó a {cantidad} unidad/es."
        REGISTRO_CRM.append({"usuario": usuario, "mensaje": mensaje, "cantidad": cantidad,
                             "fecha": datetime.now().isoformat()})
        return f"Interés de compra de {usuario} registrado en el CRM ({cantidad} unidad/es)."
    except Exception as error:  # en el CRM real puede fallar la conexión
        return f"No se pudo registrar el interés de compra: {error}"


class ArgumentosComentarioNegativo(BaseModel):
    """Argumentos de marcar_comentario_negativo (Bloque 23)."""

    usuario: str = Field(description="Nombre del viewer tal como aparece entre corchetes al inicio del mensaje. "
                                     "No inventarlo.")
    mensaje: str = Field(description="El mensaje original del viewer, sin cambios ni resumen.")
    motivo: str = Field(max_length=150, description="En pocas palabras, qué critica: calidad, precio, la marca, "
                                                    "una falla, etc.")


COMENTARIOS_MARCADOS: list[dict] = []  # en memoria del proceso; el reporte post-stream los lee desde la traza


@tool("marcar_comentario_negativo", args_schema=ArgumentosComentarioNegativo)
def marcar_comentario_negativo(usuario: str, mensaje: str, motivo: str) -> str:
    """Deja con flag un comentario negativo sobre el teclado K7 o la marca (crítica, queja, burla, una falla).
    Usar solo cuando el mensaje habla mal del producto o de la marca, no por cualquier mensaje con tono fuerte.
    No envía nada a nadie: el comentario queda pendiente de que una persona decida si va al reporte de la marca."""
    for comentario in COMENTARIOS_MARCADOS:
        if comentario["usuario"] == usuario and comentario["mensaje"] == mensaje:
            return "Ese comentario ya estaba marcado."
    COMENTARIOS_MARCADOS.append({"usuario": usuario, "mensaje": mensaje, "motivo": motivo,
                                 "estado": "pendiente de revisión", "fecha": datetime.now().isoformat()})
    return "Comentario marcado para revisión humana. No respondas discutiendo ni defendiendo el producto."


HERRAMIENTAS = [consultar_campana, consultar_viewers, registrar_interes_compra, marcar_comentario_negativo]

# Clasificación de riesgo del agente en vivo (Bloque 23), la misma de docs/limites_autonomia_agente.md.
# Ninguna es de riesgo alto: lo que sale hacia la marca pasa por src/reporte_marca.py, con aprobación humana.
# tests/test_supervision_y_trazas.py comprueba que toda herramienta "alto" llame a esperar_aprobacion.
NIVEL_DE_RIESGO = {
    "consultar_campana": "bajo",             # solo lee datos fijos de la campaña
    "consultar_viewers": "bajo",             # solo lee un número
    "registrar_interes_compra": "medio",     # escribe en el CRM, pero se puede corregir y no duplica
    "marcar_comentario_negativo": "medio",   # escribe un flag interno; no sale hasta que una persona lo apruebe
}

INSTRUCCIONES_BOT = (
        "Eres el bot de chat de una campaña publicitaria del teclado mecánico K7 en un stream de Twitch. "
        "Responde en español, en una o dos frases. Para cualquier dato del producto usa consultar_campana: "
        "nunca inventes precios, descuentos ni características, y no agregues frases promocionales que no "
        "vengan de las herramientas (stock, unidades limitadas, ofertas por tiempo limitado, envío gratis). Si el viewer quiere comprar, regístralo con "
        "registrar_interes_compra y dale el link que entrega consultar_campana (nunca escribas otro link). "
        "Si consultar_campana trae '(Fuente: ...)', copia esa fuente tal cual al final de tu respuesta. Si te preguntan algo que no tiene que ver con la campaña ni "
        "con el stream, responde breve y amable, sin usar herramientas. Si alguien habla mal del producto o de la marca, "
        "márcalo con marcar_comentario_negativo y responde breve y neutral, sin discutir ni defender el producto."
)

prompt_agente = ChatPromptTemplate.from_messages([
    ("system", INSTRUCCIONES_BOT),
    ("human", "{entrada}"),
    MessagesPlaceholder("agent_scratchpad"),
])


class AvisarFallosDelModelo(BaseCallbackHandler):
    """Registra cada vez que una llamada al modelo falla (por ejemplo, un 503), aunque el respaldo la cubra."""

    def on_llm_error(self, error, **kwargs):
        logger.warning("Falló una llamada al modelo (%s); se usa el modelo de respaldo si está configurado.", error)


def construir_agente(modelo, verbose: bool = False, modelo_secundario=None, prompt=None) -> AgentExecutor:
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
    agente = create_tool_calling_agent(modelo, HERRAMIENTAS, prompt or prompt_agente)
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
    r"env[ií]o gratis|gratis|2x1|precio especial|"
    # Descuentos con cifra ("50% de descuento", "descuento del 20 %"). "descuento" a secas no se puede prohibir:
    # borraría la respuesta correcta "No hay descuentos". Hueco encontrado en el Bloque 31 (inyección de prompt).
    r"\d+\s*%\s*(?:de\s+)?(?:dcto|descuento)|descuento\s+(?:del?\s+)?\d+\s*%",
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
        # Solo la palabra prohibida que calzó y cuántas frases: nunca la frase completa, que puede traer un
        # correo o un nombre que el modelo repitió del mensaje del viewer (criterio 3 del Gate 2).
        claves = sorted({m.group(0).lower() for f in frases for m in PROMESAS_PROHIBIDAS.finditer(f)})
        logger.warning("Se quitaron %d frase(s) con promesas que la campaña no hace: %s",
                       len(frases) - len(permitidas), claves)
    return " ".join(permitidas) if permitidas else SIN_RESPUESTA


URL = re.compile(r"https?://[^\s)\]]+")


def corregir_links(texto: str) -> str:
    """Reemplaza cualquier link que no sea el oficial por el oficial (chequeo determinista).

    En la prueba con memoria el modelo escribió un link inventado (teclado-k7-campana.com) en vez del real:
    un viewer que lo abre podría terminar en un sitio que no es de la marca.
    """
    def reemplazar(coincidencia: re.Match) -> str:
        link = coincidencia.group(0).rstrip(".,;:!?")
        sobrante = coincidencia.group(0)[len(link):]
        if link == LINK_OFICIAL:
            return coincidencia.group(0)
        logger.warning("Se reemplazó un link inventado (dominio %s)", re.sub(r"^https?://([^/]+).*", r"\1", link))
        return LINK_OFICIAL + sobrante

    return URL.sub(reemplazar, texto)


def filtrar_salida(salida) -> str:
    """Todos los chequeos deterministas sobre la respuesta: texto plano, link oficial y sin promesas inventadas."""
    return quitar_promesas_inventadas(corregir_links(texto_de_salida(salida)))


def asegurar_fuente(texto: str, pasos) -> str:
    """Si el agente usó consultar_campana y su respuesta final no copió la fuente, se la agrega (criterio 2).

    No se confía en que el modelo la copie: es la misma idea de corregir_links, un chequeo determinista.
    """
    if texto == SIN_RESPUESTA or fuentes_de(texto):
        return texto
    fuentes = []
    for accion, observacion in pasos or []:
        if getattr(accion, "tool", None) == "consultar_campana":
            fuentes += [f for f in fuentes_de(str(observacion)) if f not in fuentes]
    return f"{texto} {etiqueta_fuentes(fuentes)}" if fuentes else texto


def procesar_mensaje_agente(ejecutor: AgentExecutor, entrada: str) -> dict:
    """Invoca al agente sin que una falla tumbe el programa (Bloque 20) y devuelve la respuesta como texto.

    Si el agente falla aun con el respaldo, registra el error y el bot no responde.
    """
    try:
        resultado = ejecutor.invoke({"entrada": entrada})
        salida = asegurar_fuente(filtrar_salida(resultado["output"]), resultado.get("intermediate_steps"))
        return {**resultado, "output": salida}
    except Exception:
        logger.exception("El agente no pudo procesar un mensaje (largo %d, huella %s)", len(entrada or ""),
                         huella(entrada))
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
