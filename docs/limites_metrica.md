# Límites de la métrica de evaluación

## Qué mide

Coincidencia de palabras entre la respuesta del bot y una referencia escrita con los datos de la campaña, contando repeticiones, después de limpiar el texto (minúsculas, sin puntuación ni emojis): precisión, cobertura y F1 (`src/metricas.py`). No mide si la respuesta es correcta.

## Modos de falla conocidos

- **Información extra correcta baja el F1.** Si la referencia es corta, todo lo que el bot agrega cuenta como error de precisión, aunque sea verdad. "lo quiero!! pásame el link" → F1 = 0,11 con link y precio correctos.
- **Paráfrasis y conjugaciones puntúan bajo.** "Cómpralo en" contra "Métete a… para llevártelo": F1 = 0,15 para una respuesta correcta. `cómpralo` y `comprar` son palabras distintas para la métrica.
- **No distingue "no inventó" de "le faltó un dato".** "cuánto sale en dólares?" → F1 = 0,36: el bot no inventó una conversión (lo importante), pero tampoco dio el precio en CLP.
- **Un F1 perfecto puede ser solo la plantilla.** Los 5 casos con F1 = 1,0 son la misma frase de "No tengo esa información". El 1,0 confirma que repite la instrucción, no que la respuesta sea mejor que otras.
- **No detecta un dato falso ni una negación ausente** (probado con ejemplos controlados en `tests/test_metricas.py`; no apareció en las respuestas reales): "cuesta 49.990" contra "59.990" da F1 = 0,80, y "¡Hay descuentos!" contra "No hay descuentos" da precisión 1,0. Son justo los errores más graves para una campaña.

## Muestra revisada

- **2026-10-30:** 10 casos (los 5 con F1 más bajo y los 5 con F1 más alto) de 20 respuestas de `gemini-3.5-flash-lite`, con la rúbrica de corrección factual, completitud y contradicción (`docs/revision_manual.json`). Resultado: 0 datos incorrectos y 0 contradicciones; 1 respuesta incompleta (dólares). Los 5 casos con F1 bajo eran respuestas correctas, así que el F1 bajo nunca indicó una respuesta mala.

## Recomendación de uso

Usar F1 solo para comparar en volumen versiones del prompt o del modelo; nunca para decidir si una respuesta del bot es correcta. Toda respuesta con precio, link, descuento o envío se revisa a mano (o con un chequeo exacto de esos datos), sin importar su F1.
