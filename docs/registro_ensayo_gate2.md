# Registro del ensayo del Gate 2

Lo que encontré al correr todas las piezas juntas y qué corregí (18 de noviembre de 2026).

## Revisión de los criterios no compensables

| Encontrado | Criterio | Corrección |
|---|---|---|
| Las respuestas se publicaban sin fuente: borraba los `[n]` para que el chat se viera limpio | 2 | Cada `[n]` válido se cambia por `(Fuente: archivo.md)`; una frase sin cita no se publica |
| Si el modelo repetía un correo en una frase que el filtro quitaba, el aviso guardaba la frase entera | 3 | El aviso guarda solo la palabra prohibida que calzó |
| Las trazas del agente guardaban el nombre del viewer y su mensaje | 3 | Huella HMAC del viewer; del mensaje, solo largo y huella |
| Los errores del agente registraban el mensaje completo | 3 | Largo y huella |
| La huella de la pregunta era SHA-256 sin clave | 3 | HMAC con una clave propia |
| El `interrupt()` cubría el cambio de prompt, no la acción de mayor riesgo | 4 | El envío del reporte a la marca pasó a un grafo con `interrupt()` |
| Mi código leía solo `API_KEY` y el curso usa `GEMINI_API_KEY` | 1 | Se aceptan los dos nombres |
| La prueba 3 de la lección usa `caplog`, que no ve mis logs | 3 | `test_gate2.py` lee también el archivo de log |

## Piezas reales conectadas (con embeddings y modelo simulados)

| Probado | Resultado |
|---|---|
| Interfaz `Document` entre indexación, recuperación, filtro y log | Coinciden |
| Todos los chunks descartados por inyección | Se llamaba igual al modelo y respondía sin respaldo. Corregido: responde que no tiene información verificada, sin llamar al modelo |
| Falla del retriever | Salía una excepción sin capturar. Corregido: se registra y el bot no responde |
| `trace_id` entre consultas | Aislado |
| Reindexar | No duplica, y ahora solo recalcula lo que cambió |

También apareció un bug: después de aprobar la v3 del prompt, la demo de `grafo_supervision.py` no tenía ninguna propuesta que mostrar. Ahora crea una variante de prueba en su copia temporal del registro.

## Instalación en un entorno limpio

Copia del repo sin `venv`, `.env`, `vectorstore/` ni `logs/`, con `pip install -r requirements.txt` desde cero.

- Con Python 3.11 falla: numpy 2.5.4 necesita 3.12. El mínimo del proyecto es 3.12.
- Con Python 3.12 instala en unos 3 minutos y pasan todas las pruebas, `gate2` y el servicio simulado.
- Sin `.env`, `verificar` y `servicio` terminan con un mensaje claro, sin Traceback.

## Corrida real con Gemini (en mi Mac, Python 3.13)

| Pregunta | Respuesta | Tokens (entrada/salida) | Costo |
|---|---|---|---|
| ¿cuánto cobran por el envío? | El despacho del K7 cuesta 3.990 CLP y se paga aparte del precio del teclado. (Fuente: 03_despacho.md) | 325 / 24 | 0,00016 USD |
| ¿cuánto pesa el teclado? | No tengo ese dato del K7. | 336 / 8 | 0,00012 USD |

El índice se recalculó entero esa vez (15 embeddings, 1,4 s) porque el anterior no tenía la huella de contenido que usa la actualización incremental.

## Después de la entrega

- El clasificador de la chain usa salida estructurada (lo que sugería la decisión del Bloque 30).
- Los mensajes con intentos de inyección no llegan al agente y aparecen en la revisión del reporte; a la marca solo le llega el número.
- El prompt del agente quedó en el registro de versiones con sus 4 versiones. La del Gate 2 se aprobó con el grafo.

Resultado final: 376 pruebas y `test_gate2.py` 4 de 4.
