# Matriz de riesgos del bot

Generada con `python3 src/matriz_riesgos.py`. Puntaje = probabilidad × impacto (1 a 5). CRÍTICO ≥ 15, ALTO ≥ 9, MEDIO ≥ 4, BAJO < 4. P e I son del riesgo actual, con las mitigaciones ya construidas; la columna Inherente es la categoría sin ellas. Rango es la categoría si P o I cambian en un punto (⚠️: quedaría ALTO sin supervisión).

| # | Riesgo | P | I | Puntaje | Categoría | Inherente | Rango | Mitigación | Supervisión |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Un viewer escribe instrucciones en el chat y el bot responde fuera del guion | 3 | 4 | 12 | ALTO | CRITICO | MEDIO..CRITICO | Detector de inyección antes del RAG y del agente, roles separados, filtros de salida y cita obligatoria (Bloque 31) | Los intentos quedan marcados y se ven en la revisión del reporte antes de enviarlo |
| 2 | El agente marca como negativo a un viewer que no lo era y eso llega a la marca | 3 | 3 | 9 | ALTO | ALTO | MEDIO..ALTO | Marcar no publica nada en el chat (Bloque 23) | Una persona elige qué comentarios van al reporte antes de enviarlo |
| 3 | El bot publica un dato inventado del K7 que el filtro no cubre | 2 | 4 | 8 | MEDIO | CRITICO | MEDIO..ALTO | Cita obligatoria por frase (Bloque 26) y filtros de link y promesas (Bloques 22 y 31) | Revisión posterior de lo que el filtro corrigió (logging_rag.py --revisar) |
| 4 | Un cambio de prompt llega a producción sin registro ni revisión | 2 | 4 | 8 | MEDIO | ALTO | MEDIO..ALTO | Registro de versiones de los dos prompts; el bot usa la versión activa (Bloque 32) | Aprobación con grafo_supervision.py, mirando el diff |
| 5 | El precio o las condiciones cambian y el índice queda desactualizado | 2 | 4 | 8 | MEDIO | ALTO | MEDIO..ALTO ⚠️ | Actualización incremental del índice (Bloque 25) y evaluación de la recuperación (Bloque 27) | — |
| 6 | La respuesta llega tarde (unos 9 s) y el chat ya cambió de tema | 4 | 2 | 8 | MEDIO | MEDIO | MEDIO..ALTO ⚠️ | Latencia medida por etapa (Bloque 28); todavía no está optimizada | — |
| 7 | La API key se sube al repositorio público | 1 | 5 | 5 | MEDIO | CRITICO | MEDIO..ALTO ⚠️ | .env en .gitignore y revisión de git status antes de cada commit (Bloque 4) | — |
| 8 | Un documento del corpus trae instrucciones escondidas | 1 | 4 | 4 | MEDIO | MEDIO | BAJO..MEDIO | Filtro de chunks sospechosos y contexto delimitado (Bloque 31) | — |
| 9 | Se descartan todos los chunks y el modelo responde sin respaldo | 1 | 4 | 4 | MEDIO | MEDIO | BAJO..MEDIO | Sin chunks limpios no se llama al modelo (ensayo del Gate 2) | — |
| 10 | Datos personales de viewers quedan en texto plano en logs o trazas | 1 | 3 | 3 | BAJO | ALTO | BAJO..MEDIO | Huellas HMAC y redacción en logs y trazas (privacidad.py); test_gate2.py lo comprueba | Nada llega a la marca sin aprobación humana |
| 11 | Un pico de mensajes dispara el gasto en la API | 2 | 1 | 2 | BAJO | BAJO | BAJO..MEDIO | Costo medido por consulta (Bloque 28) y reintentos con backoff (Bloques 12 y 13) | — |
| 12 | El bot dice 'el contexto no menciona…' y el viewer no entiende | 1 | 1 | 1 | BAJO | MEDIO | BAJO | Prompt v3 aprobado y activo (Bloque 32) | — |

## Evidencia

1. El detector se esquiva con sinónimos (probado en el Bloque 31).
2. La diferencia entre criticar el producto y criticar el juego es ambigua (dataset del Bloque 29).
3. Sin filtros, 3 de 3 corridas inventaron el link (Bloque 22).
4. El cambio del prompt del agente en el Gate 2 entró sin aprobación y hubo que regularizarlo.
5. El corpus son archivos .md que se editan a mano.
6. Corridas reales del Bloque 31 y del Gate 2.
7. El repositorio es público.
8. Hoy el corpus lo escribe solo la marca.
9. Pasó en el ensayo del Gate 2 antes de corregirlo.
10. Antes del Gate 2 las trazas guardaban nombres y mensajes.
11. Unos 0,13 USD por 1.000 respuestas (Bloque 28).
12. Corrida real del Bloque 31.

## Para revisar con otra persona

- El precio o las condiciones cambian y el índice queda desactualizado
- La respuesta llega tarde (unos 9 s) y el chat ya cambió de tema
- La API key se sube al repositorio público
