# Evidencia del pipeline de texto (Bloque 15)

Registro del antes y el después de `python3 src/pipeline_texto.py`, con 3 respuestas reales del bot (`gemini-3.5-flash-lite`, 2026-10-30), comparadas contra referencias que escribí con los datos de la campaña. La métrica es la proporción de palabras distintas de la referencia que aparecen en la respuesta. Antes de comparar se quita el prefijo `categoria |` de la salida del bot.

| Caso | Mensaje del chat | Texto crudo | Texto procesado |
| --- | --- | --- | --- |
| 1 | cuánto cuesta el teclado?? | 80,0 % | 80,0 % |
| 2 | hacen envíos a regiones? | 87,5 % | **100,0 %** |
| 3 | tiene descuento? | 100,0 % | 100,0 % |

Las 3 consultas costaron 0,000361 USD en total.

## Caso 2: el pipeline cambia el resultado

```text
Referencia: No tengo esa información, revisa el link https://ejemplo.cl/r/k7
Respuesta:  No tengo esa información, revisa el link: https://ejemplo.cl/r/k7
Coincidencia texto crudo:     87.5%
Coincidencia texto procesado: 100.0%
```

La respuesta es idéntica a la referencia salvo por los dos puntos después de "link". Sin el pipeline, `link:` y `link` cuentan como palabras distintas y la métrica baja a 87,5 % por una diferencia de formato.

## Lo que observé

- **Caso 1, el pipeline no infla el resultado.** El 80 % se mantiene porque la diferencia es real: la referencia dice "Cómpralo en" y el bot dijo "Pásate por". El pipeline corrige el formato (los emojis 🎮✨ y el signo `¡`), no las diferencias de redacción.
- **Caso 3, la métrica no castiga lo que sobra.** El bot agregó "para más detalles" y aun así dio 100 %, porque solo mide cuántas palabras de la referencia aparecen en la respuesta, no cuántas palabras extra tiene. Una respuesta con datos inventados al final también daría 100 %.
- **La negación pasa casi inadvertida.** "¡Hay descuentos! Revisa el link…" contra la referencia "No hay descuentos, revisa el link…" da 85,7 %, aunque inventa una promoción. Para el bot, esta métrica sirve para ver si la respuesta trae los datos esperados, pero no para detectar información inventada.
- **Efectos del pipeline en los datos de la campaña:** el precio `59.990` queda como `59990` y el link como un solo token (`httpsejemploclrk7`). Como la referencia pasa por la misma limpieza, la comparación sigue siendo justa.
