"""Agente del bot con memoria por viewer (Bloque 22).

Junta las tres piezas del bloque:
1. Herramientas (agente_con_herramientas.py), con args_schema en registrar_interes_compra.
2. Agente y ejecutor, con chat_history ANTES del mensaje y agent_scratchpad DESPUÉS.
3. Memoria: un historial por viewer (session_id = nombre de usuario de Twitch).

Lo que agrega respecto del ejemplo de la lección, por ser un chat público con cientos de viewers:
- Cada historial guarda solo los últimos MAX_MENSAJES: la memoria y el costo por turno no crecen sin límite.
- cerrar_sesion() y cerrar_todas() para liberar memoria (por ejemplo, al terminar el stream).
- La sesión sale del nombre entre corchetes del mensaje, así un viewer no puede usar la memoria de otro.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/agente_con_memoria.py
"""
import logging
import re
import warnings

from dotenv import load_dotenv
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory

from agente_con_herramientas import (
    INSTRUCCIONES_BOT,
    REGISTRO_CRM,
    construir_agente,
    filtrar_salida,
    herramientas_usadas,
)
from cadena_tres_pasos import SIN_RESPUESTA, crear_modelo
from enrutamiento import MODELO_SECUNDARIO

logger = logging.getLogger(__name__)

MAX_MENSAJES = 6  # 3 turnos (pregunta + respuesta) por viewer

prompt_con_memoria = ChatPromptTemplate.from_messages([
    ("system", INSTRUCCIONES_BOT),
    MessagesPlaceholder("chat_history"),      # turnos anteriores de este viewer
    ("human", "{entrada}"),
    MessagesPlaceholder("agent_scratchpad"),  # herramientas de este turno
])


class HistorialLimitado(InMemoryChatMessageHistory):
    """Historial en memoria que conserva solo los últimos MAX_MENSAJES mensajes."""

    def add_messages(self, messages) -> None:
        super().add_messages(messages)
        self.messages = self.messages[-MAX_MENSAJES:]


historiales: dict[str, HistorialLimitado] = {}


def obtener_historial(session_id: str) -> HistorialLimitado:
    """Devuelve (o crea) el historial de un viewer. Para persistir en una base de datos, solo se cambia esta función."""
    if session_id not in historiales:
        historiales[session_id] = HistorialLimitado()
    return historiales[session_id]


def cerrar_sesion(session_id: str) -> None:
    """Borra el historial de un viewer. No falla si no existe."""
    historiales.pop(session_id, None)


def cerrar_todas() -> None:
    """Borra todos los historiales (por ejemplo, al terminar el stream)."""
    historiales.clear()


def usuario_de(entrada: str) -> str | None:
    """Saca el nombre de usuario del formato '[usuario] mensaje'. Sin nombre, no hay sesión."""
    coincidencia = re.match(r"\s*\[([^\]]+)\]", entrada or "")
    return coincidencia.group(1).strip().lower() if coincidencia else None


def limpiar_salida(resultado: dict) -> dict:
    """Deja 'output' como texto plano y filtrado ANTES de que la memoria lo guarde.

    Gemini 3.x responde con una lista de bloques ({'type': 'text', 'text': ..., 'extras': {'signature': ...}}).
    Si esa lista se guarda tal cual en el historial, en el turno siguiente LangChain no puede convertirla
    en mensaje y falla (MESSAGE_COERCION_FAILURE). Además, así la memoria no guarda links ni promesas inventadas:
    si los guardara, el modelo los vería en el turno siguiente como si fueran ciertos.
    """
    return {**resultado, "output": filtrar_salida(resultado["output"])}


def construir_agente_con_memoria(modelo, modelo_secundario=None, verbose: bool = False) -> RunnableWithMessageHistory:
    """El agente del Bloque 21, con el prompt que incluye chat_history, envuelto con memoria por sesión."""
    ejecutor = construir_agente(modelo, verbose=verbose, modelo_secundario=modelo_secundario, prompt=prompt_con_memoria)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # aviso de deprecación conocido (Bloque 22, lección 2)
        return RunnableWithMessageHistory(
            ejecutor | RunnableLambda(limpiar_salida),  # se limpia antes de guardar en el historial
            obtener_historial,
            input_messages_key="entrada",
            history_messages_key="chat_history",
            output_messages_key="output",
        )


def procesar_mensaje_con_memoria(agente: RunnableWithMessageHistory, entrada: str) -> dict:
    """Responde un mensaje del chat usando la memoria del viewer que lo escribió.

    Sin nombre de usuario no hay sesión: el bot no responde (no puede saber a qué historial pertenece).
    Ante cualquier error, registra y no responde (Bloque 20). La salida pasa por los mismos filtros del Bloque 21.
    """
    usuario = usuario_de(entrada)
    if usuario is None:
        return {"output": SIN_RESPUESTA, "intermediate_steps": []}
    try:
        resultado = agente.invoke({"entrada": entrada}, {"configurable": {"session_id": usuario}})
        return resultado  # 'output' ya viene limpio (limpiar_salida)
    except Exception:
        logger.exception("El agente con memoria no pudo procesar %r", entrada)
        return {"output": SIN_RESPUESTA, "intermediate_steps": []}


CONVERSACION = [
    "[juli_k] cuánto cuesta el teclado?",
    "[juli_k] y si compro 2?",                   # depende del turno anterior
    "[ana_gamer] de qué teclado me hablaste?",    # otra sesión: no debería saberlo
    "[juli_k] dale, lo quiero!! cómo pago?",      # no debe duplicar el registro en el CRM
]

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    warnings.filterwarnings("ignore", message=".*deprecated.*")
    agente = construir_agente_con_memoria(crear_modelo(), modelo_secundario=crear_modelo(MODELO_SECUNDARIO))
    for entrada in CONVERSACION:
        resultado = procesar_mensaje_con_memoria(agente, entrada)
        usuario = usuario_de(entrada)
        print(f"> {entrada}")
        print(f"  Herramientas: {herramientas_usadas(resultado) or 'ninguna'}")
        print(f"  Respuesta: {resultado['output']}")
        print(f"  Mensajes en el historial de {usuario}: {len(obtener_historial(usuario).messages)}\n")
    print(f"Registros en el CRM simulado: {REGISTRO_CRM}")
