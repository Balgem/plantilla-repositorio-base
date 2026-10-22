# Decisión de arquitectura: elección de modelo

- **Fecha de la decisión:** 2026-10-21
- **Contexto:** bot de chat para Twitch que acompaña un banner rotativo de campañas publicitarias. El bot lee cada mensaje del chat, lo clasifica (`pregunta_producto`, `interes_compra`, `spam` u `otro`) y responde con los datos de la campaña y su link medible.

## Modelo elegido

**`gemini-3.5-flash-lite`**, para clasificar y responder los mensajes del chat.

Se configura en el archivo `.env` con la variable `GEMINI_MODEL=gemini-3.5-flash-lite`. El código no cambia: `src/consumir_gemini.py` lee el modelo desde esa variable.

## Diagrama de arquitectura

Diagrama: [`diagrama_proyecto_banner.drawio`](./diagrama_proyecto_banner.drawio) (se abre en [app.diagrams.net](https://app.diagrams.net)).

El modelo elegido se usa en el bloque `consumir_gemini.py` del diagrama (Gate 1). Su flujo interno es:

1. `armar_peticion(pregunta)`: valida la pregunta, lee `API_KEY` y `GEMINI_MODEL` desde `.env` y arma la URL, el header `x-goog-api-key` y el cuerpo.
2. `enviar_peticion(url, headers, body)`: envía el `POST` a la API de Gemini y maneja los errores de conexión, los códigos 4xx/5xx y la respuesta que no es JSON.
3. `extraer_texto(respuesta_json)`: devuelve el texto generado, o un error claro si la respuesta no lo trae.
4. `calcular_costo(respuesta_json, precio_entrada, precio_salida)`: calcula el costo con `usageMetadata`, incluyendo los tokens de razonamiento.

Este documento elige el modelo que usa ese bloque. El agente del Gate 2 lo llamará por cada mensaje del chat.

## Comparación de candidatos

**Método.** Se probaron 9 modelos con [`src/comparar_modelos.py`](../src/comparar_modelos.py) el 2026-10-20: 4 repeticiones del mismo mensaje para medir la latencia y 8 mensajes de chat representativos para medir la calidad, incluidos casos difíciles (una pregunta sin respuesta en los datos de la campaña, un mensaje en inglés y un pedido de un descuento que no existe). Ante errores 429, 5xx o de conexión, el script reintenta hasta 3 veces con espera creciente (2, 4 y 8 s). Precios de la [página oficial de precios de Gemini](https://ai.google.dev/gemini-api/docs/pricing), consultados el mismo día; la salida incluye los tokens de razonamiento.

Resultados completos, con todas las respuestas de cada modelo: [`comparacion_modelos.md`](./comparacion_modelos.md). Datos crudos de cada petición: [`comparacion_modelos.json`](./comparacion_modelos.json).

### Modelos probados

| Modelo | Respondidas | Latencia mediana | Latencia p90 | Costo / 10.000 mensajes | Razonamiento | Clasificación | Datos inventados |
|---|---|---|---|---|---|---|---|
| **`gemini-3.5-flash-lite`** | 11 de 11 | **1,95 s** | **4,98 s** | 1,32 USD | 0 | 8 de 8 | 0 |
| `gemini-3.1-flash-lite` | 11 de 11 | 6,31 s | 8,29 s | **0,84 USD** | 0 | 8 de 8 | 0 (1 respuesta engañosa, ver abajo) |
| `gemini-3-flash-preview` | 11 de 11 | 3,63 s | 4,55 s | 12,65 USD | 368 | 8 de 8 | 0 |
| `gemini-3.6-flash` | 11 de 11 (4 con reintento) | 4,98 s | 6,40 s | 24,94 USD | 605 | 8 de 8 | 0 |
| `gemini-3.8-flash` | 10 de 11 (4 con reintento) | 10,45 s | 21,32 s | 24,20 USD | 587 | 8 de 8 | 0 |
| `gemini-3.7-flash` | 4 de 11 (7 errores 429) | 9,79 s | — | sin precio publicado | 548 | 2 de 2 | 0 |
| `gemma-4-26b-a4b-it` | 11 de 11 | 11,63 s | 24,97 s | sin precio publicado | 566 | no evaluable* | no evaluable* |
| `gemma-4-31b-it` | 7 de 11 (4 fallas de conexión) | 27,99 s | 29,10 s | sin precio publicado | 364 | no evaluable* | no evaluable* |
| `gemini-2.5-flash-lite` | 0 de 1 (404) | — | — | — | — | — | — |

\* Los modelos Gemma devuelven su razonamiento como texto dentro de la respuesta, antes de la línea final. El script lee el primer fragmento, así que sus puntajes de calidad no son válidos. Revisando sus respuestas a mano, la clasificación final suele ser correcta, pero el formato obligaría a un procesamiento extra y su latencia (de 10 a 30 s) ya los descarta para un chat en vivo.

### Modelos sin nivel gratuito (no probados, solo referencia de precio)

| Modelo | Entrada (USD / 1M tokens) | Salida (USD / 1M tokens) | Salida comparada con `3.5-flash-lite` |
|---|---|---|---|
| `gemini-3.1-pro-preview` | 2,00 | 12,00 | 4,8 veces más cara |
| `gemini-4-argon` | 2,00 (4,00 desde el 2026-12-01) | 10,00 (20,00 desde el 2026-12-01) | 4 veces más cara (8 veces desde diciembre) |
| `gemini-omni-1.1-flash` | 1,50 | 9,00 | 3,6 veces más cara |

## Justificación

El script ordena automáticamente a los modelos que cumplen los criterios mínimos por **costo** primero, y así puso en primer lugar a `gemini-3.1-flash-lite`. La decisión final es `gemini-3.5-flash-lite` porque, para un bot de chat en vivo, la **latencia** pesa más que una diferencia mínima de costo:

- **La diferencia de costo es insignificante.** Entre los dos `flash-lite` hay 0,48 USD por cada 10.000 mensajes.
- **La diferencia de latencia es grande.** `gemini-3.5-flash-lite` tuvo una mediana de 1,95 s frente a 6,31 s: es más de 3 veces más rápido. En un chat en vivo, una respuesta que llega 6 segundos tarde queda enterrada bajo los mensajes nuevos.
- **Fue el más rápido de los 9 en la mediana**, y el único con mediana menor a 2 segundos. Las mediciones anteriores del mismo día lo confirman: fue el más rápido en todas.
- **Respondió el 100 % de las peticiones al primer intento**, sin necesitar reintentos.
- **Su calidad fue la más segura.** A la pregunta "¿hacen envíos a regiones?", que la campaña no responde, contestó "No tengo esa información, por favor revisa el link". `gemini-3.1-flash-lite` respondió "**Sí**, puedes revisar todos los detalles de envío…", afirmando algo que nadie le dijo. El detector automático no lo marcó, pero en un bot de marca una afirmación así puede generar reclamos.
- **No razona** (0 tokens de razonamiento): para clasificar un mensaje y responder con datos que ya entrega la campaña, el razonamiento no mejoró el resultado de ningún modelo.

## Alternativas descartadas y por qué

| Modelo | Razón concreta |
|---|---|
| `gemini-3.1-flash-lite` | Algo más barato (0,84 frente a 1,32 USD por 10.000 mensajes), pero más de 3 veces más lento (mediana de 6,31 s) y afirmó un dato que no tenía ("Sí" a los envíos). |
| `gemini-3-flash-preview` | La latencia más estable (2,81 a 4,72 s), pero 10 veces más caro por sus 368 tokens de razonamiento, y es `preview`: puede cambiar o desaparecer sin aviso. |
| `gemini-3.6-flash` | 19 veces más caro por sus 605 tokens de razonamiento, más lento, y 4 de 11 peticiones necesitaron reintento. Su precio se duplica desde el 2027-01-01. |
| `gemini-3.8-flash` | Igual de caro que el 3.6, la mediana más lenta de los modelos con precio (10,45 s, con picos de 28 s) y una petición que falló aun con reintentos. |
| `gemini-3.7-flash` | Sin precio publicado y con 7 de 11 peticiones rechazadas por límite de uso (429). |
| `gemini-2.5-flash-lite` | No está disponible para cuentas nuevas (404). |
| `gemma-4-26b-a4b-it`, `gemma-4-31b-it` | Sin precio publicado, de 10 a 30 s de latencia y devuelven el razonamiento mezclado con la respuesta. El 31b además falló 4 veces por conexión. |
| `gemini-3.1-pro-preview`, `gemini-4-argon`, `gemini-omni-1.1-flash` | Sin nivel gratuito y con una salida de 3,6 a 8 veces más cara. Clasificar mensajes de chat no necesita un modelo de esa capacidad: todos los modelos baratos que se pudieron evaluar clasificaron 8 de 8. |

## Hallazgos para el diseño del agente

1. **Sin los datos de la campaña, el modelo inventa.** En una prueba sin contexto, los modelos inventaron un precio, un descuento y comandos de chat inexistentes. Al entregarles los datos reales de la campaña en el prompt, ninguno inventó precios ni descuentos. El agente siempre debe recibir los datos de la campaña activa.
2. **Hay que pedir explícitamente que diga "no sé".** Aun con los datos, `gemini-3.1-flash-lite` respondió "Sí" a una pregunta sobre envíos. La instrucción debe exigir que el bot reconozca lo que no sabe, y conviene revisar manualmente una muestra de respuestas.
3. **El bot no debería responder a todo.** Todos los modelos le hicieron publicidad a mensajes de spam o sin relación con el producto (de 2 a 3 de cada 3 casos). El agente solo debería responder a `pregunta_producto` e `interes_compra`, lo que además reduce peticiones y costo.
4. **La saturación del servicio es real.** Hubo errores 503, 429 y de conexión durante la prueba. Los reintentos con espera creciente recuperaron la mayoría y deben formar parte del bot.

## Cuándo revisar esta decisión

- Si cambian los precios o la disponibilidad de los modelos. Para repetir la comparación, basta con correr `python3 src/comparar_modelos.py`.
- Si el bot necesita respuestas más elaboradas que una clasificación y un mensaje corto.
- Si aumenta mucho el volumen de mensajes: con 1 millón de mensajes al mes, la diferencia entre los dos `flash-lite` sería de unos 48 USD, y habría que volver a pesar costo contra latencia.
