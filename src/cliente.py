"""Cliente modular para consultar a Gemini.

consultar_modelo es el único punto de entrada: arma la petición, la envía con
reintentos y devuelve el texto. Quien lo usa solo tiene que distinguir dos errores:

- ValueError: problema de configuración (mensaje vacío, falta la llave o la llave es inválida).
  Hay que corregirlo; reintentar no sirve.
- RuntimeError: el servicio no respondió tras varios intentos, o respondió algo inesperado.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/cliente.py
"""
import sys

from consumir_gemini import (
    INSTRUCCION_BOT,
    armar_peticion,
    con_reintentos,
    enviar_peticion,
    extraer_texto,
)


def consultar_modelo(
    pregunta: str,
    system_instruction: str | None = None,
    response_schema: dict | None = None,
) -> str:
    """Consulta al modelo y devuelve el texto de la respuesta.

    Reintenta automáticamente ante límite de uso o saturación. Si se agotan los
    reintentos, lanza RuntimeError con un mensaje pensado para quien usa el cliente.
    Un ValueError (credencial inválida o entrada vacía) se propaga tal cual.
    """
    url, headers, body = armar_peticion(pregunta, system_instruction, response_schema)
    try:
        respuesta_json, _ = con_reintentos(lambda: enviar_peticion(url, headers, body))
    except TimeoutError as error:
        raise RuntimeError("El servicio no respondió tras varios intentos. Intenta más tarde.") from error
    return extraer_texto(respuesta_json)


def probar(pregunta: str, system_instruction: str | None = None) -> None:
    """Muestra la respuesta del cliente, o el error tal como lo vería quien lo usa."""
    try:
        print(consultar_modelo(pregunta, system_instruction))
    except ValueError as error:
        print(f"Error de configuración: {error}")
    except RuntimeError as error:
        print(f"Error del servicio: {error}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rafaga":
        # Varias consultas seguidas y rápidas, para intentar provocar un límite de uso real.
        cantidad = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        for numero in range(1, cantidad + 1):
            print(f"--- Consulta {numero} de {cantidad} ---")
            probar("cuánto cuesta el teclado??", INSTRUCCION_BOT)
    else:
        print("--- Entrada vacía ---")
        probar("")
        print("--- Consulta normal ---")
        probar("¿Cuál es la capital de Chile? Responde en una frase.")
        print("--- Mensajes del chat, con la instrucción del bot ---")
        for mensaje in ["cuánto cuesta el teclado??", "hacen envíos a regiones?"]:
            print(f"> {mensaje}")
            probar(mensaje, INSTRUCCION_BOT)
