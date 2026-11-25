# Decisión de personalización: clasificador de mensajes del chat

## 1. El problema

El primer paso del bot clasifica cada mensaje del chat como `pregunta_producto`, `interes_compra`, `spam` u `otro` usando un prompt (`src/cadena_tres_pasos.py`). Necesito que la salida sea siempre exactamente una de esas categorías y que sea la correcta. Si no lo es, la chain manda el mensaje por la ruta equivocada, por ejemplo deja sin respuesta a alguien que quiere comprar. Antes de decidir nada medí si eso está pasando de verdad.

**Evidencia (2026-11-18, `python3 src/decision.py`, detalle en `docs/evidencia_clasificador.json`):** pasé 20 mensajes etiquetados, 5 por categoría, sacados de mi dataset del Bloque 29, por el clasificador que el bot usa hoy.

| Clasificador | Formato incumplido | Fuera de la lista | Aciertos |
|---|---|---|---|
| Prompt actual | **0 / 20** | 0 | **20 / 20** |
| Mismo prompt con salida estructurada (categorías cerradas) | 0 / 20 | 0 | 20 / 20 |

## 2. Resultado del método de decisión

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿La información cambia seguido? | No | Las categorías son las mismas desde el Bloque 18. Lo que cambia por campaña son los datos del producto, y eso ya lo resuelve el RAG de la Unidad 2.5. |
| ¿Hay un problema de formato o tono? | **No** | 0 de 20 respuestas incumplen el formato (el umbral era 3). |
| ¿Hay un dataset grande y de calidad? | No | 25 ejemplos etiquetados y validados (el umbral era 200). |
| ¿Presupuesto limitado o hay que iterar rápido? | Sí | Es un proyecto de curso con llave del nivel gratuito, y quiero ver el efecto de un cambio el mismo día. |
| ¿Hacen falta varias variantes? | No | Un solo clasificador sirve para cualquier marca, porque las categorías no cambian. |

Puntaje: **RAG 2 · PEFT 1 · Fine-tuning completo 0**, sin empate.

## 3. Técnica elegida y por qué

**No personalizo el clasificador. Mantengo el prompt actual.** El método da RAG, pero ese resultado no tiene sentido para este caso. RAG suma sus 2 puntos solo por "presupuesto limitado", y RAG no clasifica mensajes: le da información al modelo, y aquí no falta información. Si un método suma puntos aunque no haya ningún problema que resolver, siempre va a recomendar algo, y le falta la opción más barata, que es no personalizar.

La evidencia es la que decide. El problema que justificaría PEFT, un formato inconsistente, no apareció: 0 incumplimientos y 20 aciertos de 20. Entrenar un adapter costaría etiquetado, cómputo y horas por intento para arreglar algo que hoy funciona.

**La respuesta en la que más dudo es "¿hay un problema de formato?"** Si cambia a "sí", el resultado pasa a PEFT (PEFT 3 · RAG 2 · fine-tuning 1), porque esa respuesta le suma 2 a PEFT y RAG se queda con los mismos 2 puntos del presupuesto. Dudo porque los 20 mensajes los escribí yo para el dataset: son claros y cortos, y un chat real tiene mensajes más ambiguos.

Por eso, en vez de entrenar, dejo una protección que no cuesta nada: la **salida estructurada** (`with_structured_output` con las categorías cerradas, la idea del `responseSchema` del Módulo 1). Con los mismos 20 mensajes dio el mismo resultado (20/20), y además garantiza el formato desde la API aunque el modelo cambie de comportamiento más adelante.

Descarto el fine-tuning completo porque no tengo los datos (25 de 200) y no hay un problema que justifique el costo.

## 4. Qué necesitaría para ejecutarla

**Para mantener la decisión (sin entrenar):**
- Pasar el clasificador a salida estructurada, cambiando el paso 1 de `cadena_tres_pasos.py` a `with_structured_output(Clasificacion)`. Son 0 ejemplos etiquetados y 0 horas de entrenamiento.
- Repetir la medición con **20 mensajes reales** del chat, tomados de las trazas del Bloque 23 en el primer stream real, en vez de los 20 que escribí yo.

**Cuándo cambiaría a PEFT, y qué faltaría:**
- **Disparador:** 3 o más de 20 mensajes reales con formato incumplido o mal clasificados, o la necesidad de un clasificador distinto por marca.
- **Datos:** tengo 25 ejemplos etiquetados (5 por categoría) y necesito 200 balanceados, 40 por categoría. Me faltan **175**.
- **Costo de etiquetado:** las categorías raras deciden el costo. Si el 2 % del chat es intención de compra, juntar 40 ejemplos reales obliga a leer unos **2.000 mensajes**. A 15 segundos por mensaje son **8,3 horas, unos USD 167** a USD 20/h, más un 10 % de segunda revisión. Las trazas del Bloque 23 lo abaratan, porque permiten filtrar los turnos donde el agente ya registró una compra o marcó un comentario.
- **Cuarta categoría:** `comentario_negativo` (Bloque 23) no está en el prompt del clasificador, porque hoy lo detecta el agente con una herramienta. Esta medición no la evaluó. Si se agrega al clasificador, hay que volver a medir antes de decidir.

## Actualización (Gate 2)

La mejora quedó implementada: el paso 1 de la chain clasifica con `with_structured_output(Clasificacion)` (`src/cadena_tres_pasos.py`), el mismo esquema con que medí 20/20.
