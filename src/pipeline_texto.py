"""Pipeline de procesamiento de texto: limpieza, tokenización y coincidencia por palabras.

Sirve para comparar las respuestas del bot contra una referencia sin que el formato
(mayúsculas, puntuación, emojis, espacios) distorsione el resultado.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/pipeline_texto.py
Hace 3 consultas reales al bot y muestra la coincidencia antes y después del pipeline.
"""
import re
from collections import Counter

from cliente import consultar_modelo
from consumir_gemini import INSTRUCCION_BOT


def limpiar_texto(texto: str) -> str:
    """Normaliza el texto: minúsculas, sin puntuación ni símbolos (emojis incluidos) y sin espacios repetidos.

    Las tildes, la ñ y los números se conservan. Lanza TypeError si no recibe un str.
    """
    if not isinstance(texto, str):
        raise TypeError(f"limpiar_texto espera str, no {type(texto).__name__}")
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokenizar(texto_limpio: str) -> list[str]:
    """Convierte texto ya limpio en una lista de palabras."""
    return texto_limpio.split()


def procesar_texto(texto: str) -> list[str]:
    """Limpia y tokeniza en un solo paso, para no olvidar ninguno de los dos antes de medir."""
    return tokenizar(limpiar_texto(texto))


def vectorizar(tokens: list[str]) -> Counter:
    """Cuenta cuántas veces aparece cada palabra (bolsa de palabras)."""
    return Counter(tokens)


def coincidencia(tokens_referencia: list[str], tokens_respuesta: list[str]) -> float:
    """Proporción de palabras distintas de la referencia que también aparecen en la respuesta.

    Devuelve un valor entre 0 y 1. Si la referencia no tiene palabras, devuelve 0 en vez de dividir por cero.
    No considera el orden ni las repeticiones: "el perro persiguió al gato" y
    "el gato persiguió al perro" dan 1.0.
    """
    palabras_referencia = set(tokens_referencia)
    if not palabras_referencia:
        return 0.0
    return len(palabras_referencia & set(tokens_respuesta)) / len(palabras_referencia)


def comparar_antes_y_despues(referencia: str, respuesta: str) -> tuple[float, float]:
    """Calcula la coincidencia sobre texto crudo (solo .split()) y sobre texto procesado."""
    crudo = coincidencia(referencia.split(), respuesta.split())
    procesado = coincidencia(procesar_texto(referencia), procesar_texto(respuesta))
    return crudo, procesado


# Mensajes reales del chat y la respuesta de referencia que escribí para cada uno,
# con los datos de la campaña de ejemplo.
CASOS = [
    ("cuánto cuesta el teclado??",
     "El teclado mecánico K7 cuesta 59.990 CLP. Cómpralo en https://ejemplo.cl/r/k7"),
    ("hacen envíos a regiones?",
     "No tengo esa información, revisa el link https://ejemplo.cl/r/k7"),
    ("tiene descuento?",
     "No hay descuentos, revisa el link https://ejemplo.cl/r/k7"),
]


def quitar_categoria(salida_del_bot: str) -> str:
    """El bot responde 'categoria | respuesta': para comparar se usa solo la respuesta."""
    return salida_del_bot.split("|", 1)[-1].strip()


if __name__ == "__main__":
    for numero, (mensaje, referencia) in enumerate(CASOS, start=1):
        respuesta = quitar_categoria(consultar_modelo(mensaje, INSTRUCCION_BOT))
        crudo, procesado = comparar_antes_y_despues(referencia, respuesta)
        print(f"\n[Caso {numero}] Mensaje del chat: {mensaje}")
        print(f"[Caso {numero}] Referencia: {referencia}")
        print(f"[Caso {numero}] Respuesta:  {respuesta}")
        print(f"[Caso {numero}] Tokens de la respuesta: {procesar_texto(respuesta)}")
        print(f"[Caso {numero}] Coincidencia texto crudo:     {crudo:.1%}")
        print(f"[Caso {numero}] Coincidencia texto procesado: {procesado:.1%}")

    # Límite de la métrica, sin llamar a la API: cambia el sentido pero casi no cambia el número.
    referencia = "No hay descuentos, revisa el link https://ejemplo.cl/r/k7"
    inventada = "¡Hay descuentos! Revisa el link https://ejemplo.cl/r/k7"
    _, procesado = comparar_antes_y_despues(referencia, inventada)
    print(f"\n[Límite] '{inventada}' contra la referencia: {procesado:.1%}, aunque inventa una promoción.")
