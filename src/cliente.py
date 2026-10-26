"""Cliente modular para consultar a Gemini.

consultar_modelo es el único punto de entrada: arma la petición, la envía con
reintentos (backoff exponencial con jitter), registra el costo y devuelve el texto.
Quien lo usa solo tiene que distinguir dos errores:

- ValueError: problema de configuración (mensaje vacío, falta la llave o la llave es inválida).
  Hay que corregirlo; reintentar no sirve.
- RuntimeError: el servicio no respondió tras varios intentos, o respondió algo inesperado.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/cliente.py              demostración
    python3 src/cliente.py --rafaga 30  ensayo de rate limit: 30 consultas seguidas
"""
import os
import sys

from consumir_gemini import (
    INSTRUCCION_BOT,
    armar_peticion,
    calcular_costo,
    con_reintentos,
    enviar_peticion,
    extraer_texto,
)

# Precios oficiales en USD por millón de tokens (entrada, salida), consultados el 2026-10-20 en
# https://ai.google.dev/gemini-api/docs/pricing. La salida incluye los tokens de razonamiento.
PRECIOS_POR_MILLON = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
}

costo_total_sesion = 0.0


def registrar_costo(respuesta_json: dict) -> float:
    """Calcula el costo de una operación exitosa, lo suma al total de la sesión y lo muestra.

    Usa los tokens reales de usageMetadata y el precio del modelo configurado en GEMINI_MODEL,
    distinguiendo entre entrada y salida. Si el modelo no tiene precio conocido o la respuesta
    no trae el conteo de tokens, registra 0 y lo avisa.
    """
    global costo_total_sesion
    modelo = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    precios = PRECIOS_POR_MILLON.get(modelo)
    uso = respuesta_json.get("usageMetadata", {})
    if precios is None or not uso:
        print(f"Operación sin costo registrado (modelo {modelo} sin precio conocido o sin conteo de tokens).")
        return 0.0
    costo = calcular_costo(respuesta_json, precios[0] / 1_000_000, precios[1] / 1_000_000)
    costo_total_sesion += costo
    print(
        f"Operación: {uso.get('totalTokenCount', 0)} tokens "
        f"(entrada {uso.get('promptTokenCount', 0)}, salida {uso.get('candidatesTokenCount', 0)}, "
        f"razonamiento {uso.get('thoughtsTokenCount', 0)}), "
        f"costo: ${costo:.6f} (acumulado: ${costo_total_sesion:.6f})"
    )
    return costo


def consultar_modelo(
    pregunta: str,
    system_instruction: str | None = None,
    response_schema: dict | None = None,
) -> str:
    """Consulta al modelo y devuelve el texto de la respuesta.

    Reintenta automáticamente ante límite de uso o saturación. Si se agotan los
    reintentos, lanza RuntimeError con un mensaje pensado para quien usa el cliente.
    Un ValueError (credencial inválida o entrada vacía) se propaga tal cual.
    El costo se registra solo cuando la respuesta llega con éxito.
    """
    url, headers, body = armar_peticion(pregunta, system_instruction, response_schema)
    try:
        respuesta_json, _ = con_reintentos(lambda: enviar_peticion(url, headers, body))
    except TimeoutError as error:
        raise RuntimeError("El servicio no respondió tras varios intentos. Intenta más tarde.") from error
    registrar_costo(respuesta_json)
    return extraer_texto(respuesta_json)


def probar(pregunta: str, system_instruction: str | None = None) -> None:
    """Muestra la respuesta del cliente, o el error tal como lo vería quien lo usa."""
    try:
        print(consultar_modelo(pregunta, system_instruction))
    except ValueError as error:
        print(f"Error de configuración: {error}")
    except RuntimeError as error:
        print(f"Error del servicio: {error}")


MENSAJES_DEL_CHAT = [
    "cuánto cuesta el teclado??",
    "dónde lo compro",
    "hacen envíos a regiones?",
    "el teclado es mecánico de verdad?",
    "tiene descuento?",
]


def ensayo_rate_limit(cantidad: int) -> None:
    """Manda muchas consultas seguidas, sin pausa, para provocar un límite de uso real."""
    for numero in range(cantidad):
        mensaje = MENSAJES_DEL_CHAT[numero % len(MENSAJES_DEL_CHAT)]
        try:
            respuesta = consultar_modelo(mensaje, INSTRUCCION_BOT)
            print(f"Respuesta {numero}: {respuesta[:60]}...")
        except RuntimeError as error:
            print(f"Respuesta {numero} falló definitivamente: {error}")
    print(f"Costo total del ensayo: ${costo_total_sesion:.6f}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rafaga":
        ensayo_rate_limit(int(sys.argv[2]) if len(sys.argv) > 2 else 30)
    else:
        print("--- Entrada vacía ---")
        probar("")
        print("--- Consulta normal ---")
        probar("¿Cuál es la capital de Chile? Responde en una frase.")
        print("--- Mensajes del chat, con la instrucción del bot ---")
        for mensaje in ["cuánto cuesta el teclado??", "hacen envíos a regiones?"]:
            print(f"> {mensaje}")
            probar(mensaje, INSTRUCCION_BOT)
        print(f"Costo acumulado de la sesión: ${costo_total_sesion:.6f}")
