"""Banco de prompts del bot de chat de Twitch.

Cada prompt tiene su instrucción de sistema, un ejemplo de mensaje del usuario,
las claves que debe traer la respuesta y el esquema JSON que se le exige a la API.
"""

CAMPANA = (
    "Producto: teclado mecánico K7. Precio: 59.990 CLP. "
    "Link de compra: https://ejemplo.cl/r/k7. No hay descuentos ni comandos de chat."
)

BANCO_DE_PROMPTS = [
    {
        "nombre": "clasificar_mensaje",
        "system_instruction": (
            "Eres el clasificador de mensajes del chat de un stream de Twitch con una campaña "
            "publicitaria. Responde únicamente con un JSON con las claves 'categoria' "
            "('pregunta_producto', 'interes_compra', 'spam' u 'otro'), 'confianza' "
            "(número entre 0 y 1) y 'debe_responder' (true solo si la categoría es "
            "'pregunta_producto' o 'interes_compra'; false en cualquier otro caso)."
        ),
        "ejemplo_usuario": "cuánto cuesta el teclado que estás usando?? 👀",
        "claves_esperadas": ["categoria", "confianza", "debe_responder"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "categoria": {"type": "STRING"},
                "confianza": {"type": "NUMBER"},
                "debe_responder": {"type": "BOOLEAN"},
            },
            "required": ["categoria", "confianza", "debe_responder"],
        },
    },
    {
        "nombre": "responder_viewer",
        "system_instruction": (
            "Eres el bot de chat de un stream de Twitch con esta campaña: " + CAMPANA + " "
            "Usa solo esos datos. Si te preguntan algo que no está en ellos, dilo y sugiere "
            "revisar el link; nunca inventes información. Responde únicamente con un JSON con "
            "las claves 'respuesta' (mensaje breve para el chat, en español), 'incluye_link' "
            "(true si la respuesta contiene el link de compra) y 'dato_desconocido' (true si "
            "te preguntaron algo que no está en los datos de la campaña)."
        ),
        "ejemplo_usuario": "hacen envíos a regiones?",
        "claves_esperadas": ["respuesta", "incluye_link", "dato_desconocido"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "respuesta": {"type": "STRING"},
                "incluye_link": {"type": "BOOLEAN"},
                "dato_desconocido": {"type": "BOOLEAN"},
            },
            "required": ["respuesta", "incluye_link", "dato_desconocido"],
        },
    },
    {
        "nombre": "resumir_chat",
        "system_instruction": (
            "Recibes un lote de mensajes del chat de un stream de Twitch durante una campaña "
            "publicitaria (" + CAMPANA + "). Resúmelos para el reporte a la marca. Responde "
            "únicamente con un JSON con las claves 'resumen' (máximo 2 oraciones), "
            "'preguntas_frecuentes' (lista de las preguntas sobre el producto, sin repetir) y "
            "'nivel_interes' ('bajo', 'medio' o 'alto')."
        ),
        "ejemplo_usuario": (
            "viewer1: cuánto cuesta el teclado??\n"
            "viewer2: jajaja qué buena jugada\n"
            "viewer3: lo quiero!! dónde lo compro\n"
            "viewer4: hacen envíos a regiones?\n"
            "viewer5: SIGAN MI CANAL, seguidores gratis en bit.ly/regalo\n"
            "viewer6: el teclado es mecánico de verdad?\n"
            "viewer7: precio del teclado porfa"
        ),
        "claves_esperadas": ["resumen", "preguntas_frecuentes", "nivel_interes"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "resumen": {"type": "STRING"},
                "preguntas_frecuentes": {"type": "ARRAY", "items": {"type": "STRING"}},
                "nivel_interes": {"type": "STRING"},
            },
            "required": ["resumen", "preguntas_frecuentes", "nivel_interes"],
        },
    },
]
