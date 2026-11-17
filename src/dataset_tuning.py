"""Dataset para personalizar con PEFT el clasificador de mensajes del chat (Bloque 29).

Uso, desde la raíz del repositorio y con el entorno activo (no llama a la API):
    python3 src/dataset_tuning.py

Por qué es un caso de PEFT y no de RAG: al modelo no le falta información (sabe qué es spam o una queja);
lo que falta es comportamiento consistente. Hoy el primer paso de la chain (cadena_tres_pasos.py) clasifica con
un prompt y la salida es texto libre: a veces "Pregunta_producto", a veces "pregunta_producto." o una frase.
Lo que se quiere enseñar es que SIEMPRE devuelva exactamente este JSON:

    {"categoria": <una de CATEGORIAS>, "responder": <true|false>}

- Categorías: las 4 de la chain del Bloque 18 + comentario_negativo (el flag del Bloque 23).
- "responder" sigue una regla fija (REGLA_RESPONDER): el validador comprueba que cada ejemplo la cumpla,
  para que el dataset no le enseñe al modelo dos respuestas distintas para el mismo caso.
- Los ejemplos están balanceados A PROPÓSITO: en un chat real casi todo es "otro" o "spam", y casi nada es
  interes_compra, justo lo que más le importa a la marca.
- EJEMPLOS_PRUEBA no se usa para entrenar: queda aparte para comparar después el modelo afinado contra el prompt.
"""
import json
import sys
from collections import Counter

from google.genai import types

CLAVES = ("categoria", "responder")
CATEGORIAS = ("pregunta_producto", "interes_compra", "comentario_negativo", "spam", "otro")
REGLA_RESPONDER = {
    "pregunta_producto": True,     # se responde con los datos de la campaña (RAG)
    "interes_compra": True,        # se responde con el link y se registra en el CRM
    "comentario_negativo": True,   # respuesta breve y neutral, y se marca para revisión (Bloque 23)
    "spam": False,                 # no se le da visibilidad
    "otro": False,                 # charla del stream: el bot de la campaña no se mete
}


def salida(categoria: str) -> dict:
    return {"categoria": categoria, "responder": REGLA_RESPONDER[categoria]}


# Mensajes como los escribiría un viewer: con jerga, emojis, errores y casos ambiguos a propósito.
EJEMPLOS_RAW: list[tuple[str, dict]] = [
    # pregunta_producto: cualquier duda sobre el teclado, aunque no diga "K7" ni "precio"
    ("cuánto sale el teclado que usas??", salida("pregunta_producto")),
    ("ese teclado tiene ñ o es gringo", salida("pregunta_producto")),
    ("oye y llega a regiones o solo stgo", salida("pregunta_producto")),
    ("los switches son rojos? se escuchan mucho?", salida("pregunta_producto")),
    ("sirve pa la play o solo pc", salida("pregunta_producto")),
    # interes_compra: quiere comprar, no solo pregunta
    ("lo quiero!! pasa el link", salida("interes_compra")),
    ("ya me convenciste, dónde lo compro", salida("interes_compra")),
    ("me llevo 2, uno pa mi hermano", salida("interes_compra")),
    ("cuando me paguen el viernes me lo compro sí o sí 🔥", salida("interes_compra")),
    ("acabo de pedir uno jajaja", salida("interes_compra")),
    # comentario_negativo: crítica al PRODUCTO o a la marca (no al streamer ni al juego)
    ("ese teclado es una basura, a mi primo se le rompió en una semana", salida("comentario_negativo")),
    ("60 lucas por un teclado?? un robo", salida("comentario_negativo")),
    ("pésima marca, nunca me respondieron un reclamo", salida("comentario_negativo")),
    ("se nota que te pagaron pa decir que es bueno, es malo", salida("comentario_negativo")),
    ("los rojos son lo peor para escribir, no lo recomiendo", salida("comentario_negativo")),
    # spam: autopromoción, links ajenos, estafas
    ("SIGAN MI CANAL, seguidores gratis en bit.ly/regalo", salida("spam")),
    ("gana skins gratis aquí 👉 skins-free.example", salida("spam")),
    ("compro y vendo cuentas, escríbanme al priv", salida("spam")),
    ("follow x follow?? 🙏🙏", salida("spam")),
    ("vendo teclado igual pero más barato, hablame", salida("spam")),
    # otro: charla del stream; las críticas al JUEGO o al streamer no son comentario_negativo
    ("jajaja qué buena jugada", salida("otro")),
    ("hola chat!! llegué tarde", salida("otro")),
    ("qué mala esa partida, juegas pésimo hoy", salida("otro")),
    ("a qué hora termina el stream?", salida("otro")),
    ("GG", salida("otro")),
]

# Aparte, para comparar después el modelo afinado contra el prompt (no se entrena con estos).
EJEMPLOS_PRUEBA: list[tuple[str, dict]] = [
    ("tiene bluetooth?", salida("pregunta_producto")),
    ("listo, comprado 🛒", salida("interes_compra")),
    ("se ve barato el teclado ese, no dura nada", salida("comentario_negativo")),
    ("visiten mi tienda de poleras en instagram", salida("spam")),
    ("ese boss estaba roto jaja", salida("otro")),
]


def construir_examples(ejemplos_raw: list[tuple[str, dict]]) -> list[types.TuningExample]:
    """Pares entrada -> salida exacta. La salida va como texto JSON con comillas dobles (json.dumps)."""
    return [types.TuningExample(text_input=texto, output=json.dumps(s, ensure_ascii=False))
            for texto, s in ejemplos_raw]


def chequear_balance(ejemplos_raw: list[tuple[str, dict]], clave: str = "categoria") -> Counter:
    return Counter(s[clave] for _, s in ejemplos_raw)


def normalizar(texto: str) -> str:
    """Para detectar duplicados aunque cambien mayúsculas o espacios."""
    return " ".join(texto.lower().split())


def validar_dataset(examples: list[types.TuningExample], claves_esperadas: tuple[str, ...] = CLAVES,
                    categorias: tuple[str, ...] = CATEGORIAS) -> list[str]:
    """Todos los problemas del dataset, no solo el primero. Lista vacía = listo para entrenar.

    Además de lo que revisa la lección (vacíos, duplicados, JSON inválido, claves faltantes), revisa lo que
    la lección deja pasar: que el JSON sea un objeto, que no tenga claves de más, que la categoría esté en la
    lista cerrada (una tilde crearía una categoría nueva), que "responder" sea booleano y siga la regla, y
    que la misma entrada no aparezca con dos salidas distintas (una contradicción).
    """
    problemas = []
    vistos: dict[str, tuple[int, dict]] = {}
    for i, ej in enumerate(examples):
        if not ej.text_input or not ej.text_input.strip():
            problemas.append(f"ejemplo {i}: text_input vacio")
        if not ej.output or not ej.output.strip():
            problemas.append(f"ejemplo {i}: output vacio")
            continue
        try:
            s = json.loads(ej.output)
        except json.JSONDecodeError:
            problemas.append(f"ejemplo {i}: output no es JSON valido")
            continue
        if not isinstance(s, dict):
            problemas.append(f"ejemplo {i}: el output no es un objeto JSON ({type(s).__name__})")
            continue
        problemas += [f'ejemplo {i}: output no tiene la clave "{c}"' for c in claves_esperadas if c not in s]
        problemas += [f'ejemplo {i}: output tiene una clave de más "{c}"' for c in s if c not in claves_esperadas]
        categoria = s.get("categoria")
        if "categoria" in s and categoria not in categorias:
            problemas.append(f"ejemplo {i}: categoria desconocida {categoria!r}")
        if "responder" in s and not isinstance(s["responder"], bool):
            problemas.append(f'ejemplo {i}: "responder" debe ser true o false, no {s["responder"]!r}')
        elif categoria in REGLA_RESPONDER and s.get("responder") != REGLA_RESPONDER[categoria]:
            problemas.append(f'ejemplo {i}: "responder" no sigue la regla para {categoria}')
        if ej.text_input:
            clave = normalizar(ej.text_input)
            if clave in vistos:
                j, anterior = vistos[clave]
                tipo = "duplicado" if anterior == s else "con OTRA salida (contradicción)"
                problemas.append(f"ejemplo {i}: misma entrada que el ejemplo {j}, {tipo}")
            else:
                vistos[clave] = (i, s)
    return problemas


def razon_desbalance(balance: Counter) -> float:
    return max(balance.values()) / min(balance.values())


def titulo(texto: str) -> None:
    print(f"\n{'=' * 64}\n{texto}\n{'=' * 64}")


if __name__ == "__main__":
    examples = construir_examples(EJEMPLOS_RAW)

    titulo("PASO 1: el dataset")
    print(f"{len(examples)} ejemplos de entrenamiento + {len(EJEMPLOS_PRUEBA)} de prueba (aparte)")
    print(examples[0])

    titulo("PASO 2: balance entre categorías")
    balance = chequear_balance(EJEMPLOS_RAW)
    for categoria in CATEGORIAS:
        print(f"{categoria}: {balance.get(categoria, 0)}")
    print(f"razón max/min: {razon_desbalance(balance):.1f}x")

    titulo("PASO 3: validación")
    todos = examples + construir_examples(EJEMPLOS_PRUEBA)  # la prueba tampoco puede repetir el entrenamiento
    problemas = validar_dataset(todos)
    print(f"{len(todos)} ejemplos (entrenamiento + prueba), {len(problemas)} problemas encontrados")
    for p in problemas:
        print(" -", p)

    titulo("PASO 4: rompo ejemplos a propósito (el validador tiene que encontrarlos)")
    rotos = examples + [
        types.TuningExample(text_input="ese teclado es una basura, A MI PRIMO se le rompió en una semana",
                            output=json.dumps(salida("otro"), ensure_ascii=False)),             # contradicción
        types.TuningExample(text_input="tiene garantía?", output="{'categoria': 'pregunta_producto', 'responder': True}"),
        types.TuningExample(text_input="lo compro", output='{"categoria": "interés_compra", "responder": true}'),
        types.TuningExample(text_input="GG wp", output='{"categoria": "spam", "responder": true}'),
        types.TuningExample(text_input="", output='"categoria responder"'),
    ]
    encontrados = validar_dataset(rotos)
    print(f"{len(rotos)} ejemplos, {len(encontrados)} problemas encontrados")
    for p in encontrados:
        print(" -", p)

    if problemas:
        sys.exit(1)  # un dataset con problemas no se envía a entrenar, ni para probar
    print("\nDataset listo para entrenar (no se envió ningún trabajo de tuning).")
