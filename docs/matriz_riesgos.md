# Matriz de riesgos del bot de la campaña K7

Generada con `python3 src/matriz_riesgos.py` (Bloque 32). Puntaje = probabilidad × impacto (1 a 5 cada uno); CRÍTICO ≥ 15, ALTO ≥ 9, MEDIO ≥ 4, BAJO < 4. **P e I son del riesgo residual** (con lo ya construido); *inherente* es la categoría sin esas mitigaciones. *Rango* es la categoría posible si P o I se equivocan en un punto: ⚠️ marca las filas que con ese error quedarían ALTO **sin** punto de supervisión.

| # | Riesgo | P | I | Puntaje | Categoría | Inherente | Rango | Mitigación | Punto de supervisión |
|---|---|---|---|---|---|---|---|---|---|
| 1 | El bot publica en el chat un dato inventado del K7 que el filtro de salida no cubre (p. ej. 'tiene bluetooth' o 'llega mañana') | 3 | 4 | 12 | **ALTO** | CRITICO | MEDIO..CRITICO | RAG con citas numeradas y revisar_citas (Bloque 26), el bot admite no saber (Bloque 27), corregir_links + filtrar_salida (Bloques 22 y 31) | Revisión post-stream de lo que el filtro corrigió (logging_rag.py --revisar, Bloque 32) y de las trazas respuesta_modelo vs respuesta_final (revisar_trazas, Bloque 23); todo cambio de prompt pasa por grafo_supervision.py (Bloque 32) |
| 2 | Un viewer escribe instrucciones en el chat público y el bot responde fuera del guion (insulta, habla de otra marca o revela sus instrucciones) | 3 | 4 | 12 | **ALTO** | CRITICO | MEDIO..CRITICO | Detector de inyección sobre la pregunta, que corta antes del retriever y del modelo; roles separados; filtrar_salida sobre lo que el modelo responda (Bloque 31) | **Parcial.** Cada intento detectado queda en el log con su trace_id y se revisa post-stream (logging_rag.py --revisar, Bloque 32). Falta: marcar al viewer en el reporte de la marca (Gate 2) |
| 3 | Los nombres y mensajes de viewers quedan en claro en trazas_agente.jsonl y en el reporte para la marca | 3 | 3 | 9 | **ALTO** | ALTO | MEDIO..ALTO | Archivos con datos de viewers en .gitignore (Bloque 23); el log del RAG guarda huella y largo, nunca el texto (Bloque 31) | Ningún comentario ni nombre llega a la marca sin aprobación humana, uno por uno y del envío (reporte_marca.py, Bloque 23) |
| 4 | El agente marca como comentario negativo a un viewer que no lo era y su nombre llega a la marca | 3 | 3 | 9 | **ALTO** | ALTO | MEDIO..ALTO | marcar_comentario_negativo es riesgo medio y no publica nada en el chat (Bloque 23) | Aprobación humana de cada comentario marcado antes del reporte (supervision.py, Bloque 23) |
| 5 | Un cambio del prompt de sistema llega a producción sin registro ni revisión | 2 | 4 | 8 | **MEDIO** | ALTO | MEDIO..ALTO | Registro de versiones con huella; el bot lee el prompt activo del registro y deja su huella en cada consulta del log (Bloque 32) | grafo_supervision.py: interrupt con el diff, aprobación con thread_id único y checkpointer durable (Bloque 32) |
| 6 | El precio o las condiciones de la campaña cambian y el índice sigue con la versión vieja | 2 | 4 | 8 | **MEDIO** | ALTO | MEDIO..ALTO ⚠️ | indexar_corpus.py borra la colección y reindexa con ids explícitos (Bloques 24 y 25); el conjunto de evaluación detecta recuperaciones rotas (Bloque 27) | — |
| 7 | La respuesta llega unos 9 s después y el chat ya cambió de tema | 4 | 2 | 8 | **MEDIO** | MEDIO | MEDIO..ALTO ⚠️ | Latencia medida por etapa: la generación es el 77 % del tiempo (Bloque 28); trace_id para encontrar las lentas (Bloque 31). Mide, todavía no acelera | — |
| 8 | La API key se sube al repositorio público | 1 | 5 | 5 | **MEDIO** | CRITICO | MEDIO..ALTO ⚠️ | .env en .gitignore desde el Bloque 4 y revisión de git status antes de cada commit | — |
| 9 | El bot dice 'el contexto no menciona…' y el viewer no entiende qué es 'el contexto' | 5 | 1 | 5 | **MEDIO** | MEDIO | MEDIO..ALTO ⚠️ | Versión 3 del prompt propuesta en el registro, pendiente de aprobación (Bloque 32) | — |
| 10 | Un documento del corpus trae instrucciones escondidas (inyección indirecta) | 1 | 4 | 4 | **MEDIO** | MEDIO | BAJO..MEDIO | Filtro de chunks sospechosos, <contexto> declarado como dato y roles separados (Bloque 31) | — |
| 11 | Un pico de mensajes en el chat dispara el gasto en la API | 2 | 1 | 2 | **BAJO** | BAJO | BAJO..MEDIO | Costo medido por consulta (Bloques 28 y 31); reintentos con backoff, no en bucle (Bloques 12 y 13) | — |

## Evidencia de cada riesgo

1. **El bot publica en el chat un dato inventado del K7 que el filtro de salida no cubre (p. ej. 'tiene bluetooth' o 'llega mañana')**: Sin filtros, 3 de 3 corridas inventaron el link (Bloque 22); el filtro solo conoce links y promesas de una lista.
2. **Un viewer escribe instrucciones en el chat público y el bot responde fuera del guion (insulta, habla de otra marca o revela sus instrucciones)**: El detector se esquiva con sinónimos o separando letras (probado en el Bloque 31).
3. **Los nombres y mensajes de viewers quedan en claro en trazas_agente.jsonl y en el reporte para la marca**: trazas.py guarda nombre y mensaje; solo logging_rag.py usa huellas (Bloque 31).
4. **El agente marca como comentario negativo a un viewer que no lo era y su nombre llega a la marca**: La frontera crítica al juego/streamer vs. al producto es ambigua (dataset del Bloque 29).
5. **Un cambio del prompt de sistema llega a producción sin registro ni revisión**: Hasta el Bloque 31 el prompt era un string suelto en el código.
6. **El precio o las condiciones de la campaña cambian y el índice sigue con la versión vieja**: El corpus está en archivos .md que se editan a mano.
7. **La respuesta llega unos 9 s después y el chat ya cambió de tema**: Corrida real del Bloque 31: ~9 s de generación por respuesta.
8. **La API key se sube al repositorio público**: El repositorio es público.
9. **El bot dice 'el contexto no menciona…' y el viewer no entiende qué es 'el contexto'**: Corrida real del Bloque 31 ('¿cuánto pesa el teclado?').
10. **Un documento del corpus trae instrucciones escondidas (inyección indirecta)**: Hoy el corpus lo escribe solo la marca; sube si algún día se indexan comentarios o FAQ de usuarios.
11. **Un pico de mensajes en el chat dispara el gasto en la API**: Costo real ≈ 0,13 USD por 1.000 respuestas (Bloque 28).

## Para revisar con otra persona

- El precio o las condiciones de la campaña cambian y el índice sigue con la versión vieja (MEDIO, rango MEDIO..ALTO)
- La respuesta llega unos 9 s después y el chat ya cambió de tema (MEDIO, rango MEDIO..ALTO)
- La API key se sube al repositorio público (MEDIO, rango MEDIO..ALTO)
- El bot dice 'el contexto no menciona…' y el viewer no entiende qué es 'el contexto' (MEDIO, rango MEDIO..ALTO)

## Lectura

- Ningún riesgo queda CRÍTICO con lo ya construido, pero dos lo eran sin mitigar (datos inventados e inyección desde el chat): por eso siguen en ALTO y con revisión humana.
- Las respuestas en vivo no se aprueban una por una (no escala y llegarían tarde): su supervisión es la revisión post-stream de lo que el filtro frenó o corrigió, y la aprobación de cada cambio de prompt.
- Riesgos con el mismo puntaje no son igual de urgentes: la API key (1×5) es rara y grave; el 'no sé' con jerga (5×1) es frecuente y leve.
