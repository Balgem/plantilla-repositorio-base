# Comparación de modelos para el bot de chat (2026-10-20)

Generado con `src/comparar_modelos.py`: 4 repeticiones del mismo mensaje para la latencia y 8 mensajes de chat para la calidad, con reintentos de espera creciente (2, 4, 8 s) ante errores 429, 5xx o de conexión. Precios de https://ai.google.dev/gemini-api/docs/pricing consultados el 2026-10-20.

| Criterio | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3-flash-preview` | `gemini-3.6-flash` | `gemini-3.8-flash` | `gemini-3.7-flash` | `gemini-2.5-flash-lite` | `gemma-4-26b-a4b-it` | `gemma-4-31b-it` |
|---|---|---|---|---|---|---|---|---|---|
| Entrada (USD / 1M tokens) | 0.25 | 0.30 | 0.50 | 0.75 | 0.75 | sin precio publicado | sin precio publicado | sin precio publicado | sin precio publicado |
| Salida (USD / 1M tokens) | 1.50 | 2.50 | 3.00 | 3.75 | 3.75 | sin precio publicado | sin precio publicado | sin precio publicado | sin precio publicado |
| Respondidas | 11 de 11 | 11 de 11 | 11 de 11 | 11 de 11 | 10 de 11 | 4 de 11 | 0 de 1 | 11 de 11 | 7 de 11 |
| Respondidas al primer intento | 11 de 11 | 11 de 11 | 11 de 11 | 7 de 11 | 7 de 11 | 2 de 11 | 0 de 1 | 11 de 11 | 3 de 11 |
| Errores | ninguno | ninguno | ninguno | ninguno | 503×1 | 429×7 | 404×1 | ninguno | conexión×4 |
| Latencia promedio (mismo mensaje ×4) | 4.64 s | 2.94 s | 3.82 s | 8.10 s | 10.93 s | 9.48 s | sin datos | 10.71 s | 24.73 s |
| Latencia mediana (todas) | 6.31 s | 1.95 s | 3.63 s | 4.98 s | 10.45 s | 9.79 s | sin datos | 11.63 s | 27.99 s |
| Latencia mín – máx | 1.25 – 10.18 s | 1.07 – 6.55 s | 2.81 – 4.72 s | 4.38 – 17.94 s | 5.89 – 28.74 s | 8.84 – 25.42 s | sin datos | 9.29 – 28.57 s | 22.54 – 29.83 s |
| Costo promedio por mensaje (USD) | 0.000084 | 0.000132 | 0.001265 | 0.002494 | 0.002420 | sin precio | sin precio | sin precio | sin precio |
| Costo por 10.000 mensajes (USD) | 0.84 | 1.32 | 12.65 | 24.94 | 24.20 | sin precio | sin precio | sin precio | sin precio |
| Tokens de razonamiento promedio | 0 | 0 | 368 | 605 | 587 | 548 | sin datos | 566 | 364 |
| Clasificación correcta | 8 de 8 | 8 de 8 | 8 de 8 | 8 de 8 | 8 de 8 | 2 de 2 | 0 de 0 | 0 de 8 | 0 de 5 |
| Respuestas con datos inventados | 0 de 8 | 0 de 8 | 0 de 8 | 0 de 8 | 0 de 8 | 0 de 2 | 0 de 0 | 3 de 8 | 2 de 5 |
| Publicidad a spam u off-topic | 2 de 3 | 3 de 3 | 3 de 3 | 3 de 3 | 2 de 3 | 0 de 0 | 0 de 0 | 3 de 3 | 2 de 2 |
| Cumple los criterios mínimos | sí | sí | sí | sí | sí | no | no | no | no |

## Ranking

Criterios mínimos: precio publicado, al menos 90 % de peticiones respondidas, a lo sumo un error de clasificación y ninguna respuesta con datos inventados. Entre los que cumplen, se ordena por costo por mensaje y luego por latencia mediana.

1. `gemini-3.1-flash-lite`: 0.000084 USD por mensaje, mediana 6.31 s, 8 de 8 correctas
2. `gemini-3.5-flash-lite`: 0.000132 USD por mensaje, mediana 1.95 s, 8 de 8 correctas
3. `gemini-3-flash-preview`: 0.001265 USD por mensaje, mediana 3.63 s, 8 de 8 correctas
4. `gemini-3.8-flash`: 0.002420 USD por mensaje, mediana 10.45 s, 8 de 8 correctas
5. `gemini-3.6-flash`: 0.002494 USD por mensaje, mediana 4.98 s, 8 de 8 correctas

## Modelos sin nivel gratuito (no probados, solo referencia de precio)

| Modelo | Entrada (USD / 1M) | Salida (USD / 1M) |
|---|---|---|
| `gemini-3.1-pro-preview` | 2.00 | 12.00 |
| `gemini-4-argon` | 2.00 | 10.00 |
| `gemini-omni-1.1-flash` | 1.50 | 9.00 |

## Respuestas de cada modelo

### `gemini-3.1-flash-lite`
- **cuánto cuesta el teclado que estás usando?? 👀** → pregunta_producto | El teclado K7 tiene un precio de 59.990 CLP, puedes revisar los detalles en este link: https://ejemplo.cl/r/k7
- **lo quiero!! dónde lo compro** → interes_compra | ¡Genial! Puedes comprar tu teclado mecánico K7 por 59.990 CLP en este enlace: https://ejemplo.cl/r/k7
- **SIGAN MI CANAL, seguidores gratis en bit.ly/regalo** → spam | Por favor, evita publicar enlaces externos en el chat.
- **jajaja qué buena jugada** → otro | ¡Gracias por ver el stream! Si quieres mejorar tu setup, chequéalo en https://ejemplo.cl/r/k7 📢 publicidad indebida
- **hacen envíos a regiones?** → pregunta_producto | Sí, puedes revisar todos los detalles de envío directamente en https://ejemplo.cl/r/k7
- **how much is the keyboard?** → pregunta_producto | El teclado mecánico K7 tiene un precio de 59.990 CLP, puedes ver más detalles en https://ejemplo.cl/r/k7
- **compro 2 si me hacen descuento** → interes_compra | Lo siento, el precio es fijo a 59.990 CLP, puedes revisar más detalles en https://ejemplo.cl/r/k7
- **a qué hora termina el stream?** → otro | No tengo información sobre el horario del stream, por favor revisa el link del producto para más detalles: https://ejemplo.cl/r/k7 📢 publicidad indebida

### `gemini-3.5-flash-lite`
- **cuánto cuesta el teclado que estás usando?? 👀** → pregunta_producto | El teclado K7 cuesta 59.990 CLP, revísalo aquí: https://ejemplo.cl/r/k7
- **lo quiero!! dónde lo compro** → interes_compra | ¡Hola! Cómpralo aquí: https://ejemplo.cl/r/k7 por 59.990 CLP.
- **SIGAN MI CANAL, seguidores gratis en bit.ly/regalo** → spam | ¡No caigas en estafas, chat! Para lo único que estamos hoy es para el teclado mecánico K7 a 59.990 CLP en https://ejemplo.cl/r/k7 ⌨️🔥 📢 publicidad indebida
- **jajaja qué buena jugada** → otro | ¡Jajaja estuvo buenísima! Por cierto, ¿viste nuestro teclado mecánico K7 a solo 59.990 CLP? Revisa el link para comprarlo: https://ejemplo.cl/r/k7 📢 publicidad indebida
- **hacen envíos a regiones?** → pregunta_producto | No tengo esa información, por favor revisa el link: https://ejemplo.cl/r/k7
- **how much is the keyboard?** → pregunta_producto | Cuesta 59.990 CLP, puedes revisar todos los detalles y comprarlo en https://ejemplo.cl/r/k7
- **compro 2 si me hacen descuento** → interes_compra | ¡Hola! No tenemos descuentos disponibles, pero puedes revisar toda la info y comprar en https://ejemplo.cl/r/k7
- **a qué hora termina el stream?** → otro | No sé esa información, pero puedes revisar el link https://ejemplo.cl/r/k7 para conocer más del teclado K7 por 59.990 CLP. 📢 publicidad indebida

### `gemini-3-flash-preview`
- **cuánto cuesta el teclado que estás usando?? 👀** → pregunta_producto | El teclado K7 cuesta 59.990 CLP. Puedes verlo aquí: https://ejemplo.cl/r/k7
- **lo quiero!! dónde lo compro** → interes_compra | ¡Buenísima! Adquiérelo por 59.990 CLP en este link: https://ejemplo.cl/r/k7
- **SIGAN MI CANAL, seguidores gratis en bit.ly/regalo** → spam | Revisa toda la información del teclado K7 en el link: https://ejemplo.cl/r/k7 📢 publicidad indebida
- **jajaja qué buena jugada** → otro | ¡Qué buena! Si quieres mejorar tus jugadas con el teclado K7, revísalo aquí: https://ejemplo.cl/r/k7 📢 publicidad indebida
- **hacen envíos a regiones?** → pregunta_producto | Puedes revisar los detalles de envío en el link de compra: https://ejemplo.cl/r/k7
- **how much is the keyboard?** → pregunta_producto | El teclado K7 cuesta 59.990 CLP, encuéntralo en https://ejemplo.cl/r/k7
- **compro 2 si me hacen descuento** → interes_compra | No hay descuentos disponibles, el precio es 59.990 CLP en https://ejemplo.cl/r/k7
- **a qué hora termina el stream?** → otro | No tengo esa información, te invito a revisar los detalles en https://ejemplo.cl/r/k7 📢 publicidad indebida

### `gemini-3.6-flash`
- **cuánto cuesta el teclado que estás usando?? 👀** → pregunta_producto | El teclado mecánico K7 cuesta 59.990 CLP y puedes comprarlo en https://ejemplo.cl/r/k7
- **lo quiero!! dónde lo compro** → interes_compra | ¡Puedes comprar el teclado mecánico K7 a 59.990 CLP en este link: https://ejemplo.cl/r/k7!
- **SIGAN MI CANAL, seguidores gratis en bit.ly/regalo** → spam | Por favor no hagas spam en el chat. Si te interesa el teclado mecánico K7, revisa https://ejemplo.cl/r/k7 📢 publicidad indebida
- **jajaja qué buena jugada** → otro | ¡Destaca en tus jugadas con el teclado mecánico K7 a 59.990 CLP! Encuéntralo en https://ejemplo.cl/r/k7 📢 publicidad indebida
- **hacen envíos a regiones?** → pregunta_producto | Puedes revisar la información sobre envíos directamente en el link: https://ejemplo.cl/r/k7
- **how much is the keyboard?** → pregunta_producto | El teclado mecánico K7 cuesta 59.990 CLP y lo puedes encontrar en https://ejemplo.cl/r/k7
- **compro 2 si me hacen descuento** → interes_compra | No hay descuentos disponibles, el precio es 59.990 CLP cada uno y puedes comprar en https://ejemplo.cl/r/k7
- **a qué hora termina el stream?** → otro | No tengo esa información, te invito a revisar más detalles en https://ejemplo.cl/r/k7 📢 publicidad indebida

### `gemini-3.8-flash`
- **cuánto cuesta el teclado que estás usando?? 👀** → pregunta_producto | El teclado mecánico K7 cuesta 59.990 CLP y lo encuentras en https://ejemplo.cl/r/k7
- **lo quiero!! dónde lo compro** → interes_compra | ¡Genial! Puedes comprar tu teclado mecánico K7 por 59.990 CLP aquí: https://ejemplo.cl/r/k7
- **SIGAN MI CANAL, seguidores gratis en bit.ly/regalo** → spam | Por favor, no hagas spam en el chat.
- **jajaja qué buena jugada** → otro | ¡Totalmente! Para jugar con la mejor precisión, revisa el teclado mecánico K7 a 59.990 CLP en https://ejemplo.cl/r/k7 📢 publicidad indebida
- **hacen envíos a regiones?** → pregunta_producto | Puedes revisar la información sobre envíos directamente en https://ejemplo.cl/r/k7
- **how much is the keyboard?** → pregunta_producto | El teclado mecánico K7 cuesta 59.990 CLP. Puedes comprarlo aquí: https://ejemplo.cl/r/k7
- **compro 2 si me hacen descuento** → interes_compra | No hay descuentos disponibles, el precio del teclado K7 es 59.990 CLP. Puedes comprarlo aquí: https://ejemplo.cl/r/k7
- **a qué hora termina el stream?** → otro | No tengo esa información, ¡pero puedes revisar el teclado K7 en https://ejemplo.cl/r/k7! 📢 publicidad indebida

### `gemini-3.7-flash`
- **cuánto cuesta el teclado que estás usando?? 👀** → pregunta_producto | El teclado mecánico K7 cuesta 59.990 CLP y puedes encontrarlo en https://ejemplo.cl/r/k7
- **compro 2 si me hacen descuento** → interes_compra | No hay descuentos disponibles, el teclado mecánico K7 cuesta 59.990 CLP y lo puedes comprar en https://ejemplo.cl/r/k7

### `gemini-2.5-flash-lite`

### `gemma-4-26b-a4b-it`
- **cuánto cuesta el teclado que estás usando?? 👀** → *   Role: Twitch stream chat bot.
*   Ad Campaign Details:
    *   Product: Teclado mecánico K7.
    *   Price: 59.990 CLP.
    *   Link: https://ejemplo.cl/r/k7.
    *   Restrictions: No discounts, no chat commands. Use *only* provided data. If unknown, refer to the link.
*   Classification Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
*   Output Format: One line, `category | brief chat response`.
*   User Message: "cuánto cuesta el teclado que estás usando?? 👀"

    *   Content: "cuánto cuesta el teclado que estás usando?? 👀" (How much does the keyboard you are using cost??)
    *   Intent: Asking for the price of the product.

    *   The user is asking about the product (price).
    *   Category: `pregunta_producto`.

    *   Price: 59.990 CLP.
    *   Product name: Teclado mecánico K7.
    *   Brief response: "El teclado mecánico K7 cuesta 59.990 CLP." or "Cuesta 59.990 CLP. Link: https://ejemplo.cl/r/k7".

    *   Format: `pregunta_producto | [response]`
    *   Response: "El teclado mecánico K7 cuesta 59.990 CLP. Compra aquí: https://ejemplo.cl/r/k7"

    *   Only use provided data? Yes.
    *   One line? Yes.
    *   Format correct? Yes.
    *   Classification correct? Yes. ❌ categoría
- **lo quiero!! dónde lo compro** → *   Role: Twitch stream chatbot.
*   Campaign Details:
    *   Product: Teclado mecánico K7.
    *   Price: 59.990 CLP.
    *   Link: https://ejemplo.cl/r/k7.
    *   Constraint: No discounts, no chat commands. Use *only* provided data. If unknown, refer to the link.
*   Output Format: A single line in the format `category | brief response for chat`.
*   Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
*   Input Message: "lo quiero!! dónde lo compro"

    *   "lo quiero!! dónde lo compro" (I want it!! where do I buy it)
    *   Intent: Buying/Purchasing.
    *   Classification: `interes_compra`.

    *   The user wants to know where to buy.
    *   Data available: Link (https://ejemplo.cl/r/k7).
    *   Draft response: "Puedes comprarlo aquí: https://ejemplo.cl/r/k7"

    *   Format: `categoria | respuesta breve para el chat`
    *   Category: `interes_compra`
    *   Response: `Puedes comprarlo aquí: https://ejemplo.cl/r/k7`

    *   `interes_compra | ¡Genial! Puedes comprarlo aquí: https://ejemplo.cl/r/k7` (Keeping it brief and chat-friendly). ❌ categoría
- **SIGAN MI CANAL, seguidores gratis en bit.ly/regalo** → *   Role: Twitch stream chatbot.
*   Product: K7 mechanical keyboard.
*   Price: 59.990 CLP.
*   Link: https://ejemplo.cl/r/k7.
*   Constraint 1: No discounts, no chat commands.
*   Constraint 2: Use *only* provided data. If unsure, refer to the link.
*   Constraint 3: Classify message into one category: `pregunta_producto`, `interes_compra`, `spam`, or `otro`.
*   Constraint 4: Response format: `category | brief response for chat` (one line).
*   Input message: "SIGAN MI CANAL, seguidores gratis en bit.ly/regalo"

    *   "SIGAN MI CANAL, seguidores gratis en bit.ly/regalo"
    *   Analysis: This is typical promotional spam or self-promotion by a viewer. It is not related to the keyboard.

    *   Classification: `spam`.
    *   Response: Needs to be a brief chat response. Since it's spam and I'm a bot for a specific product campaign, I shouldn't engage with the spam content other than following the format.

    *   Format: `categoria | respuesta breve para el chat`
    *   Category: `spam`
    *   Response: Since I'm a bot for the K7 keyboard and the message is spam, a brief response could be ignoring the content or just a generic "No estamos promocionando eso" or similar, but per instructions, I should only use the provided data if relevant. However, since it's spam, the response is usually a warning or a redirect if it were a real bot. Given the strict constraints, I will just provide the classification and a very brief, standard bot-like reaction to spam (or simply acknowledge the category).
    *   *Self-Correction:* The prompt says "si no sabes algo, invita a revisar el link". But this isn't a question about the product. It's just spam.
    *   Standard bot behavior for spam in this context: `spam | No se permite el spam en el chat.` (Wait, is that in the data? No. The data is only about the K7).
    *   Let's look at the rules again: "Usa solo esos datos: si no sabes algo, invita a revisar el link."
    *   Does "usar solo esos datos" apply to the *response* content or the *knowledge base*? Usually, it means don't invent features/prices.
    *   Message is clearly `spam`.

    *   `spam | No se permite el spam.` (A bit risky if I'm strictly following "use only those data").
    *   Actually, if the message is spam, the classification is the most important part.
    *   Let's try to keep the response extremely minimal or neutral.

    *   Input: "SIGAN MI CANAL, seguidores gratis en bit.ly/regalo"
    *   Category: `spam`
    *   Response: `spam | No hagas spam.` (Or simply don't engage).

    Wait, let's re-read: "Usa solo esos datos: si no sabes algo, invita a revisar el link."
    The message isn't a question. It's spam.
    
    Let's refine:
    Category: `spam`
    Response: `spam | No hagas spam.` (Standard chatbot behavior).

    Wait, let's look at the "Usa solo esos datos" constraint. If I can't use anything else, can I even say "No hagas spam"?
    If the prompt implies I should only talk about the K7:
    If a user asks "Is it red?", I'd say "Revisa el link: https://ejemplo.cl/r/k7".
    If a user says "Buy my stuff", it's `spam`.

    Let's go with:
    `spam | No hagas spam.`

    Actually, a more professional bot approach:
    `spam | Evita el spam en el chat.`

    Let's check if there's a simpler way.
    The instruction is "Responde en una línea con el formato 'categoria | respuesta breve para el chat'".

    Category: `spam`
    Response: `spam | No hagas spam.`

    (Note: In a real scenario, a bot wouldn't answer spam with product info, but the classification is the priority).

    *Final Polish:*
    `spam | No se permite el spam.` (Common sense for a bot).

    Let's try to be even more compliant with "Usa solo esos datos".
    If the user asks something else, I use the link. Since this isn't a question, I'll just label it.

    `spam | No hagas spam.`

    Let's check if `otro` is better. No, `spam` fits perfectly.

    `spam | No hagas spam. ❌ categoría ⚠️ inventa datos 📢 publicidad indebida
- **jajaja qué buena jugada** → *   Role: Twitch stream chatbot.
*   Campaign Info:
    *   Product: Teclado mecánico K7.
    *   Price: 59.990 CLP.
    *   Link: https://ejemplo.cl/r/k7.
    *   Rules: No discounts, no chat commands. Use only provided data. If unknown, refer to the link.
*   Task: Classify the viewer's message and respond.
*   Output Format: `category | brief response for chat` (one line).
*   Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
*   User Message: "jajaja qué buena jugada" (hahaha what a good play).

    *   Content: "jajaja qué buena jugada" (expressing reaction to gameplay).
    *   Intent: Not about the product, not expressing interest in buying, not spam (it's a valid reaction to a stream), but not a product question either.
    *   Classification: `otro`.

    *   Since it's `otro` and not about the product, the bot should ideally react normally or stay out of the way, but according to the instructions: "Si no sabes algo, invita a revisar el link." However, the instruction "Si no sabes algo" usually applies to product-related queries. Since this is a casual reaction, a standard chat response is better. But wait, the instructions say: "Usa solo esos datos".
    *   Actually, the instruction "Usa solo esos datos" applies to the *campaign*.
    *   If I classify it as `otro`, the response should be brief and fit the chat vibe.
    *   Let's look at the categories again.
    *   `pregunta_producto`: asks about K7.
    *   `interes_compra`: wants to buy K7.
    *   `spam`: nonsense/repeated stuff.
    *   `otro`: everything else.
    *   Message: "jajaja qué buena jugada" $\rightarrow$ `otro`.

    *   Response: "¡Totalmente! ¡Esa fue épica! 🎮" (Too long/not following the "brief" rule strictly?)
    *   Constraint check: "Responde en una línea con el formato 'categoria | respuesta breve para el chat'".
    *   If the user says something unrelated, the bot doesn't *have* to talk about the product unless it's a product question.
    *   Wait, the prompt says: "Usa solo esos datos: si no sabes algo, invita a revisar el link."
    *   Does "no sabes algo" apply to a laugh? Not really.
    *   Let's try to keep it extremely professional/bot-like.
    *   `otro | ¡Fue increíble! 🙌`

    *Refining based on the "Use only those data" rule:*
    If I follow "Usa solo esos datos" extremely strictly, I might not be able to respond to a laugh. But that would make for a bad chatbot.
    However, in these prompt engineering tasks, "Usa solo esos datos" usually means "Don't hallucinate product features/prices".
    The message "jajaja qué buena jugada" is a reaction to the stream.

    Let's re-evaluate the category.
    `otro | ¡Fue una jugada épica! 🔥`

    Wait, if I'm a *bot for the campaign*, maybe I shouldn't engage in gameplay talk if I am strictly a campaign bot? But usually, Twitch bots do both.
    If I follow the prompt's logic:
    1. Classify: `otro`
    2. Response: `¡Fue épica! 🔥`

    *Self-Correction:* The prompt says "Usa solo esos datos" in the context of the campaign. If the user says something not related to the K7, the bot can't use the data to answer.
    Category: `otro`.
    Response: `¡Fue una jugada increíble! 🎮`

    Let's check if there's a better way.
    Is it `spam`? No, it's a normal reaction.
    Is it `pregunta_producto`? No.
    Is it `interes_compra`? No.
    So `otro`.

    `otro | ¡Fue una jugada épica! 🔥`

    Wait, if the instruction "Usa solo esos datos" is meant to be absolute for *every* response (even non-product ones), the bot would be useless. But usually, these prompts imply "When talking about the product, use only these data".
    Since the user is just laughing, I'll just acknowledge it briefly.

    Actually, looking at the prompt again: "Usa solo esos datos: si no sabes algo, invita a revisar el link."
    If the user says "jajaja qué buena jugada", I "don't know" what that refers to in the context of the campaign. But it's a reaction to the stream.
    If I treat "no sabes algo" as "if the message is not about the product", I would link the product. But that's bad UX for a bot.
    I will categorize as `otro` and give a short reaction.

    *Final Plan:*
    Category: `otro`
    Response: `¡Fue una jugada increíble! 🔥`

    Let's try to be even more concise.
    `otro | ¡Fue épica! 🔥`

    One more thought: If the instruction "Usa solo esos datos" means I *cannot* say anything else, then I would be stuck. But "Responde en una línea con el formato..." allows for a response.

    `otro | ¡Fue una jugada épica! 🔥 ❌ categoría ⚠️ inventa datos 📢 publicidad indebida
- **hacen envíos a regiones?** → *   Role: Twitch stream chatbot.
*   Ad Campaign:
    *   Product: Teclado mecánico K7.
    *   Price: 59.990 CLP.
    *   Purchase Link: https://ejemplo.cl/r/k7.
    *   Constraints: No discounts, no chat commands. Use *only* provided data. If unknown, invite to check the link.
*   Format: Single line: `categoria | respuesta breve para el chat`.
*   Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
*   User Message: "hacen envíos a regiones?" (Do you ship to regions?)

    *   The message asks about shipping.
    *   The provided data *does not* mention shipping policies.
    *   According to instructions: "si no sabes algo, invita a revisar el link." (if you don't know something, invite to check the link).
    *   Category: Since it's a question about the product/service, it fits `pregunta_producto`.

    *   Category: `pregunta_producto`
    *   Response: "No tengo esa info, revisa el link para más detalles: https://ejemplo.cl/r/k7" (Simplified/Short for chat).

    *   `pregunta_producto | No tengo esa info, revisa el link para más detalles: https://ejemplo.cl/r/k7`

    *   One line? Yes.
    *   Format `categoria | respuesta`? Yes.
    *   Used only provided data? Yes.
    *   Handled unknown info correctly? Yes. ❌ categoría
- **how much is the keyboard?** → *   Role: Twitch stream chat bot.
*   Campaign Details:
    *   Product: Teclado mecánico K7.
    *   Price: 59.990 CLP.
    *   Link: https://ejemplo.cl/r/k7.
    *   Constraint 1: No discounts.
    *   Constraint 2: No chat commands.
    *   Constraint 3: Use *only* provided data. If unknown, refer to the link.
*   Task: Classify the viewer's message and respond.
*   Classification Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
*   Output Format: Single line, `category | brief chat response`.
*   Viewer Message: "how much is the keyboard?"

    *   The user is asking for the price.
    *   This falls under `pregunta_producto` (product question).

    *   The price is 59.990 CLP.
    *   The response should be brief and suitable for a Twitch chat.

    *   Format: `categoria | respuesta breve para el chat`
    *   Result: `pregunta_producto | Cuesta 59.990 CLP. Puedes verlo aquí: https://ejemplo.cl/r/k7` (Wait, the prompt says "respuesta breve para el chat").

    *   *Self-Correction/Refinement:*
        *   Category: `pregunta_producto`
        *   Brief response: "El teclado K7 cuesta 59.990 CLP. Compra aquí: https://ejemplo.cl/r/k7"

    *   Category: `pregunta_producto`
    *   Message: `pregunta_producto | El K7 cuesta 59.990 CLP. Link: https://ejemplo.cl/r/k7`

    *   Product: K7? Yes.
    *   Price: 59.990 CLP? Yes.
    *   Link: https://ejemplo.cl/r/k7? Yes.
    *   One line? Yes.
    *   Format `categoria | respuesta`? Yes. ❌ categoría
- **compro 2 si me hacen descuento** → *   Role: Twitch stream chatbot.
*   Campaign Details:
    *   Product: Teclado mecánico K7.
    *   Price: 59.990 CLP.
    *   Link: https://ejemplo.cl/r/k7.
    *   Constraint: No discounts, no chat commands. Use *only* these details. If unknown, invite to check the link.
*   Classification Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
*   Output Format: Single line, `category | brief response for chat`.
*   User Message: "compro 2 si me hacen descuento" (I'll buy 2 if you give me a discount).

    *   The user is expressing a conditional intent to purchase based on a discount.
    *   Since it involves buying, it fits `interes_compra`.

    *   User wants a discount.
    *   Policy says: "No hay descuentos" (No discounts).
    *   Instruction: "Si no sabes algo, invita a revisar el link" (If you don't know something/can't provide it, invite them to check the link).
    *   Draft 1: No hay descuentos. Mira el link: https://ejemplo.cl/r/k7
    *   Draft 2: No contamos con descuentos, revisa todos los detalles aquí: https://ejemplo.cl/r/k7

    *   Format: `categoria | respuesta breve para el chat`
    *   Result: `interes_compra | No hay descuentos disponibles, revisa el link para más info: https://ejemplo.cl/r/k7`

    *   Category: `interes_compra` (Correct).
    *   Response: Short, contains only provided info, mentions no discounts, points to link.
    *   Format: One line. ❌ categoría ⚠️ inventa datos
- **a qué hora termina el stream?** → *   Role: Twitch stream chatbot.
*   Ad Campaign Data:
    *   Product: K7 mechanical keyboard.
    *   Price: 59.990 CLP.
    *   Link: https://ejemplo.cl/r/k7.
    *   Constraints: No discounts, no chat commands, use *only* these data. If unknown, invite to check the link.
*   Output Format: One line with `category | brief response for chat`.
*   Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
*   User Message: "a qué hora termina el stream?" (what time does the stream end?)

    *   Message: "a qué hora termina el stream?"
    *   Content: Asking about stream timing.
    *   Relation to product: None.
    *   Relation to campaign: None.
    *   Category determination:
        *   `pregunta_producto`? No (not about the keyboard).
        *   `interes_compra`? No.
        *   `spam`? No (it's a normal question, just irrelevant to the ad).
        *   `otro`? Yes.

    *   The information needed (stream end time) is not in the provided data.
    *   Rule: "si no sabes algo, invita a revisar el link." (if you don't know something, invite them to check the link).
    *   *Note: Usually, a bot wouldn't link a product for a stream time question, but the prompt strictly says "Usa solo esos datos: si no sabes algo, invita a revisar el link."*

    *   `otro | No tengo esa info, revisa el link: https://ejemplo.cl/r/k7`

    *   Single line? Yes.
    *   Format `category | response`? Yes.
    *   Only used provided data? Yes.
    *   Handled unknown info via link? Yes.

    *Self-Correction/Refinement:* While logically it's weird to point to a keyboard link for stream time, the prompt instructions are absolute: "Usa solo esos datos: si no sabes algo, invita a revisar el link." I must follow the system prompt's logic.

    Category: `otro`
    Response: `No sé la hora, revisa aquí: https://ejemplo.cl/r/k7`

    *Wait, looking at the category again:* Is asking for stream time "spam"? Not really. It's "otro".

    Let's try to be even briefer to fit "respuesta breve para el chat".

    `otro | No lo sé, revisa el link: https://ejemplo.cl/r/k7 ❌ categoría 📢 publicidad indebida

### `gemma-4-31b-it`
- **cuánto cuesta el teclado que estás usando?? 👀** → Twitch stream chat bot.
Mechanical keyboard K7.
59.990 CLP.
https://ejemplo.cl/r/k7.
No discounts, no chat commands.
Use only provided data; if unknown, refer to the link.

        *   Classify message into: `pregunta_producto`, `interes_compra`, `spam`, or `otro`.
        *   Format: `categoria | respuesta breve para el chat` (one line).
"cuánto cuesta el teclado que estás usando?? 👀"

    *   The viewer is asking for the price.
    *   This fits best under `pregunta_producto` (product question).

    *   Price: 59.990 CLP.
    *   Product: Teclado mecánico K7.
    *   Link: https://ejemplo.cl/r/k7.
    *   Draft: "El teclado mecánico K7 cuesta 59.990 CLP. Cómpralo aquí: https://ejemplo.cl/r/k7"

    *   `pregunta_producto | El teclado mecánico K7 cuesta 59.990 CLP. Encuéntralo aquí: https://ejemplo.cl/r/k7 ❌ categoría
- **SIGAN MI CANAL, seguidores gratis en bit.ly/regalo** → Twitch stream chat bot.
Mechanical keyboard K7.
59.990 CLP.
https://ejemplo.cl/r/k7.
No discounts, no chat commands.
Use only provided data; refer to the link for unknowns.
Classify viewer message into one of: `pregunta_producto`, `interes_compra`, `spam`, or `otro`.
Single line: `categoria | respuesta breve para el chat`.
"SIGAN MI CANAL, seguidores gratis en bit.ly/regalo"

    *   Message: "SIGAN MI CANAL, seguidores gratis en bit.ly/regalo"
    *   Intent: Self-promotion, promising free followers (typical bot/spam behavior).
    *   Classification: `spam`.

    *   Since the message is spam, the bot shouldn't encourage it or provide product info (unless specifically told to handle spam by promoting the product, but usually, a chat bot ignores or warns about spam). However, given the constraints "Use only those data", if it's spam, the response should be a brief rejection or simple redirection to the stream context. Actually, usually, for spam, the bot doesn't need to sell the keyboard, but it needs to follow the format.
    *   Response for spam: "Por favor, no hagas spam en el chat." or similar.

    *   Category: `spam`
    *   Response: `Por favor, evita el spam en el chat.` (Keep it brief for Twitch chat).

    *   Format: `categoria | respuesta breve para el chat`
    *   Draft: `spam | Por favor, no hagas spam en el chat. ❌ categoría ⚠️ inventa datos 📢 publicidad indebida
- **hacen envíos a regiones?** → Twitch stream chat bot.
Mechanical Keyboard K7.
59.990 CLP.
https://ejemplo.cl/r/k7.
No discounts, no chat commands.
Use only provided data. If unknown, refer to the link.
Classify viewer message into: `pregunta_producto`, `interes_compra`, `spam`, or `otro`.
Single line: `categoria | brief response for chat`.
"hacen envíos a regiones?" (Do you ship to regions/provinces?)

    *   The provided data contains: Product name, Price, Link.
    *   It does *not* contain information about shipping/delivery.
    *   Constraint: "si no sabes algo, invita a revisar el link" (if you don't know something, invite them to check the link).

    *   The user is asking about shipping. This is related to the purchase process/product logistics.
    *   Categories: `pregunta_producto` (product question), `interes_compra` (purchase interest), `spam`, `otro`.
    *   Asking about shipping usually falls under `pregunta_producto` or `interes_compra`. In this context, since they are asking about a specific logistical detail of the product/sale, `pregunta_producto` is a good fit, but `interes_compra` is also applicable. However, usually, "do you ship" is a product/service query. Let's go with `pregunta_producto`.

    *   Since I don't have shipping info: "Revisa el link para más info: https://ejemplo.cl/r/k7" or similar.

    *   Format: `categoria | respuesta`
    *   Result: `pregunta_producto | Revisa toda la información en el link: https://ejemplo.cl/r/k7 ❌ categoría
- **compro 2 si me hacen descuento** → *   Role: Twitch stream chat bot.
    *   Product: Mechanical keyboard K7.
    *   Price: 59,990 CLP.
    *   Purchase Link: https://ejemplo.cl/r/k7.
    *   Constraints: No discounts, no chat commands. Use *only* provided data. If unknown, refer to the link.
    *   Required Format: `categoria | respuesta breve para el chat` (One single line).
    *   Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
    *   Input Message: "compro 2 si me hacen descuento" (I'll buy 2 if you give me a discount).

    *   The user is expressing intent to buy ("compro 2") but conditioning it on a discount ("si me hacen descuento").
    *   This falls under `interes_compra` (intent to buy) or `pregunta_producto` (asking about price/discount). Since they are talking about purchasing, `interes_compra` is a strong candidate, but they are specifically asking for a discount. However, the prompt asks to classify. "Interes compra" fits best as they are stating they will buy.

    *   The product is the K7.
    *   The price is 59,990 CLP.
    *   Constraint: "No hay descuentos" (No discounts).
    *   Constraint: Use only provided data.
    *   Draft response: "No hay descuentos disponibles. El precio es 59.990 CLP. Cómpralo aquí: https://ejemplo.cl/r/k7"

    *   Format: `categoria | respuesta`
    *   Category: `interes_compra`
    *   Response: "No hay descuentos disponibles. Precio: 59.990 CLP. Link: https://ejemplo.cl/r/k7"

    *   `interes_compra | No hay descuentos disponibles. Precio: 59.990 CLP. Compra aquí: https://ejemplo.cl/r/k7 ❌ categoría ⚠️ inventa datos
- **a qué hora termina el stream?** → *   Role: Twitch stream chat bot.
    *   Campaign details:
        *   Product: Mechanical Keyboard K7.
        *   Price: 59.990 CLP.
        *   Purchase link: https://ejemplo.cl/r/k7.
        *   Constraints: No discounts, no chat commands.
        *   Rule: Use only provided data; if unknown, refer to the link.
    *   Task: Classify the viewer's message and provide a brief response.
    *   Categories: `pregunta_producto`, `interes_compra`, `spam`, `otro`.
    *   Output format: `categoria | respuesta breve para el chat` (single line).
    *   Input message: "a qué hora termina el stream?" (At what time does the stream end?).

    *   Message: "a qué hora termina el stream?"
    *   Does it ask about the keyboard? No.
    *   Does it show interest in buying? No.
    *   Is it spam? No.
    *   Does it fit "otro"? Yes.

    *   The bot only knows about the K7 keyboard, price, and link.
    *   The bot does *not* know the stream schedule.
    *   According to the rule: "si no sabes algo, invita a revisar el link" (if you don't know something, invite them to check the link).

    *   Category: `otro`
    *   Response: "No lo sé, ¡revisa el link para más info! https://ejemplo.cl/r/k7" (or similar brief response).

    *   Format: `categoria | respuesta breve para el chat`
    *   Draft: `otro | No tengo esa información, revisa el link: https://ejemplo.cl/r/k7 ❌ categoría 📢 publicidad indebida
