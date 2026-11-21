# Registro del ensayo funcional del Gate 2

Lo que encontré al conectar todas las piezas y correrlas juntas (Bloque S1), qué corregí y cómo lo verifiqué.

## Ensayo 1: repaso de la rúbrica contra mi proyecto (2026-11-18)

Revisé los cuatro criterios no compensables corriendo el código, no leyéndolo.

| # | Encontrado | Criterio | Corregido |
|---|---|---|---|
| 1 | Para que el chat se viera limpio, `procesar_consulta` borraba los `[n]` antes de publicar: "El despacho cuesta 3.990 CLP." salía **sin fuente** | 2 ❌ | `armar_publicacion`: cada `[n]` válido se convierte en `(Fuente: archivo.md)` desde la metadata del chunk; una frase sin cita válida no se publica |
| 2 | Probando con el correo de la lección: si el modelo repetía el correo en una frase que el filtro de promesas quitaba, el aviso del filtro registraba **la frase completa** (con el correo) | 3 ❌ | El aviso registra solo cuántas frases y qué palabra prohibida calzó; nunca la frase |
| 3 | `trazas_agente.jsonl` guardaba el nombre del viewer y su mensaje en claro | 3 ❌ | `src/privacidad.py`: viewer como huella HMAC; mensaje como largo + huella + tipos de PII; el comentario marcado se guarda redactado |
| 4 | Los errores del agente y de la chain registraban el mensaje completo (`%r`) | 3 ❌ | Largo + huella |
| 5 | La huella de la pregunta era SHA-256 sin clave: con una lista de correos candidatos se podía saber cuál estaba detrás | 3 ⚠️ | HMAC con una clave propia de la instalación |
| 6 | El punto de supervisión con `interrupt()` cubría el despliegue de prompts (MEDIO en mi matriz), no la acción de mayor riesgo | 4 ⚠️ | El envío del reporte a la marca pasó a un grafo con `interrupt()` y checkpointer SQLite |
| 7 | La lección usa `GEMINI_API_KEY` y mi código leía solo `API_KEY`: en un entorno limpio con el nombre del curso, el servicio no encontraba la clave | 1 ⚠️ | `src/configuracion.py` acepta los dos nombres |
| 8 | Con `caplog`, el `test_3` de la lección pasaba sin revisar mis logs (mis loggers tienen `propagate=False`) | 3 ⚠️ | Mi `test_gate2.py` lee además el archivo de log real |

## Ensayo 2: mis piezas reales conectadas (2026-11-18)

Corpus real → `partir_en_chunks` → Chroma con ids `archivo#n` → retriever → `procesar_consulta`, con embeddings y modelo simulados.

| Probado | Resultado | Corregido |
|---|---|---|
| Interfaz `Document` entre indexación, recuperación, filtro y log | ✅ Coinciden (`page_content`, `metadata["fuente"]`, el `id` de Chroma). No tuve el error `.contenido` de la lección: el filtro del Bloque 31 se probó contra `Document` reales | — |
| Todos los chunks recuperados descartados por inyección | ❌ Se llamaba igual al modelo sin contexto y se publicó "Dato inventado." | Sin chunks limpios: evento `sin_contexto_confiable` y "No tengo información verificada sobre eso.", sin llamar al modelo |
| El retriever falla (embedding de la pregunta caído) | ❌ `ConnectionError` sin capturar | Evento `error_recuperacion` y el bot no responde |
| `trace_id` aislado entre consultas | ✅ | — |
| Reindexar no duplica | ✅ | Además: actualización incremental con huella del contenido (sin cambios, 0 embeddings) |

## Ensayo 3: un bug que apareció al integrar

Después de aprobar la v3 del prompt, la demo del grafo de supervisión (`grafo_supervision.py` sin argumentos) terminaba con "No hay ninguna versión propuesta": funcionaba solo mientras hubiera una propuesta pendiente. Corregido: si no hay propuestas, la demo crea una variante de prueba **solo en su copia temporal** del registro.

## Ensayo 4: instalación en un entorno limpio (2026-11-18)

Copia del repositorio sin `venv`, sin `.env`, sin `vectorstore/` ni `logs/`; entorno virtual nuevo; `pip install -r requirements.txt` desde cero.

| Paso | Resultado |
|---|---|
| Python 3.11 + `pip install -r requirements.txt` | ❌ `No matching distribution found for numpy==2.5.4`: numpy 2.5 exige Python 3.12. El curso pide 3.10+, pero mis dependencias fijadas no. **Decisión:** mínimo 3.12 (como ya exigía `main.py` desde el Gate 1), comprobado en `main.py` y en `verificar_entorno.py`, y explicado en el README |
| Python 3.12 + `pip install -r requirements.txt` | ✅ en unos 3 minutos |
| `python main.py verificar` sin `.env` | Termina en 1 con `Pendiente: definir GEMINI_API_KEY (o API_KEY)` y el aviso de que el índice no existe todavía |
| `python main.py servicio` sin `.env` | Mensaje claro y código 1, sin Traceback, sugiriendo `--simulado` |
| `python main.py pruebas` | ✅ todas pasan |
| `python main.py gate2` | ✅ 4 de 4 |
| `python servicio_rag.py --simulado` | ✅ crea el índice (temporal), responde con fuente, termina en 0 |
| `python main.py autoevaluacion` | ✅ promedio 86,8 y 4 de 4 no compensables |

## Resultado tras las correcciones

- `python3 main.py pruebas`: 364 pruebas, todas pasan, sin API.
- `python3 main.py gate2`: 4 de 4.
- `python3 servicio_rag.py --simulado`: corre de punta a punta y termina en 0.
- **Corrida real con Gemini** (`python3 main.py servicio`, 2026-11-18 12:23, en mi Mac, Python 3.13):

| Pregunta | Respuesta publicada | Fuentes | Tokens (entrada/salida) | Costo | Generación |
|---|---|---|---|---|---|
| ¿cuánto cobran por el envío? | El despacho del K7 cuesta 3.990 CLP y se paga aparte del precio del teclado. (Fuente: 03_despacho.md) | 03_despacho.md | 325 / 24 | 0,0001575 USD | ~8 s |
| ¿cuánto pesa el teclado? | No tengo ese dato del K7. | — (admite no saber) | 336 / 8 | 0,0001208 USD | ~7 s |

  El índice se actualizó con 15 embeddings en 1,43 s: el índice anterior no tenía la huella del contenido que usa la actualización incremental, así que esta vez se recalculó entero, una sola vez. Prompt activo: `959478c666ac` (v3). Sin errores, 0 aprobaciones pendientes.

## Después de la entrega: los dos pendientes que quedaban (2026-11-18)

| Pendiente | Qué se hizo | Pruebas |
|---|---|---|
| Salida estructurada en el paso 1 de la chain (decisión del Bloque 30) | `construir_clasificador`: `with_structured_output(Clasificacion)` con Gemini; camino de texto con modelos que no la soportan | 4 nuevas en `tests/test_cadena_tres_pasos.py` |
| Marcar al viewer que intenta inyectar | El mensaje no llega al agente ni a su memoria; la traza guarda la huella del viewer y los patrones (no el texto); la revisión del reporte los muestra y a la marca le llega solo el número | `tests/test_supervision_y_trazas.py`, `tests/test_grafo_reporte.py` |
| Versionar `INSTRUCCIONES_BOT` del agente | Sus 4 versiones reales (Bloques 21, 22, 23 y Gate 2) en el mismo registro, con la fecha de su commit; el agente lee la activa. El cambio del Gate 2 había entrado **sin aprobación**: quedó como propuesta para decidirla con el grafo | `tests/test_registro_prompts.py`, `tests/test_grafo_supervision.py` |

Total: 376 pruebas, `test_gate2.py` 4 de 4.
