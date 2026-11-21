# Matriz de riesgos del bot de la campaña K7

Generada con `python3 src/matriz_riesgos.py` (Bloque 32). Puntaje = probabilidad × impacto (1 a 5 cada uno); CRÍTICO ≥ 15, ALTO ≥ 9, MEDIO ≥ 4, BAJO < 4. **P e I son del riesgo residual** (con lo ya construido); *inherente* es la categoría sin esas mitigaciones. *Rango* es la categoría posible si P o I se equivocan en un punto: ⚠️ marca las filas que con ese error quedarían ALTO **sin** punto de supervisión.

| # | Riesgo | P | I | Puntaje | Categoría | Inherente | Rango | Mitigación | Punto de supervisión |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Un viewer escribe instrucciones en el chat público y el bot responde fuera del guion (insulta, habla de otra marca o revela sus instrucciones) | 3 | 4 | 12 | **ALTO** | CRITICO | MEDIO..CRITICO | Detector de inyección sobre la pregunta (RAG) y sobre el mensaje antes del agente (Gate 2), que corta antes del retriever y del modelo; roles separados; filtrar_salida y cita obligatoria sobre lo que el modelo responda (Bloque 31, Gate 2) | Cada intento detectado se bloquea y queda marcado con la huella del viewer: en el agente aparece en la revisión humana del reporte antes del envío (reporte_marca.py, Gate 2) y en el RAG en logging_rag.py --revisar (Bloque 32) |
| 2 | El agente marca como comentario negativo a un viewer que no lo era y su nombre llega a la marca | 3 | 3 | 9 | **ALTO** | ALTO | MEDIO..ALTO | marcar_comentario_negativo es riesgo medio y no publica nada en el chat (Bloque 23) | El envío del reporte es un grafo con interrupt() y checkpointer SQLite: se detiene, una persona elige qué comentarios van y aprueba o rechaza, y recién ahí se envía (reporte_marca.py, Gate 2) |
| 3 | El bot publica en el chat un dato inventado del K7 que el filtro de salida no cubre (p. ej. 'tiene bluetooth' o 'llega mañana') | 2 | 4 | 8 | **MEDIO** | CRITICO | MEDIO..ALTO | Gate 2: una frase sin cita válida no se publica y la fuente sale de la metadata del chunk; RAG con citas (Bloque 26), el bot admite no saber (Bloque 27), corregir_links + filtrar_salida (Bloques 22 y 31) | Revisión post-stream de lo que el filtro corrigió (logging_rag.py --revisar, Bloque 32) y de las trazas respuesta_modelo vs respuesta_final (revisar_trazas, Bloque 23); todo cambio de prompt pasa por grafo_supervision.py (Bloque 32) |
| 4 | Un cambio del prompt de sistema llega a producción sin registro ni revisión | 2 | 4 | 8 | **MEDIO** | ALTO | MEDIO..ALTO | Registro de versiones con huella para los DOS prompts (RAG y agente, con su historial desde el Bloque 21); el bot lee el prompt activo del registro y deja su huella en cada consulta (Bloque 32, Gate 2) | grafo_supervision.py: interrupt con el diff, aprobación con thread_id único y checkpointer durable (Bloque 32) |
| 5 | El precio o las condiciones de la campaña cambian y el índice sigue con la versión vieja | 2 | 4 | 8 | **MEDIO** | ALTO | MEDIO..ALTO ⚠️ | Actualización incremental del índice con ids y huella del contenido: un chunk editado se vuelve a embeber al arrancar el servicio (Bloque 25, Gate 2); el conjunto de evaluación detecta recuperaciones rotas (Bloque 27) | — |
| 6 | La respuesta llega unos 9 s después y el chat ya cambió de tema | 4 | 2 | 8 | **MEDIO** | MEDIO | MEDIO..ALTO ⚠️ | Latencia medida por etapa: la generación es el 77 % del tiempo (Bloque 28); trace_id para encontrar las lentas (Bloque 31). Mide, todavía no acelera | — |
| 7 | La API key se sube al repositorio público | 1 | 5 | 5 | **MEDIO** | CRITICO | MEDIO..ALTO ⚠️ | .env en .gitignore desde el Bloque 4 y revisión de git status antes de cada commit | — |
| 8 | Un documento del corpus trae instrucciones escondidas (inyección indirecta) | 1 | 4 | 4 | **MEDIO** | MEDIO | BAJO..MEDIO | Filtro de chunks sospechosos, <contexto> declarado como dato y roles separados (Bloque 31) | — |
| 9 | Todo el contexto recuperado se descarta por inyección y el modelo responde igual, sin respaldo | 1 | 4 | 4 | **MEDIO** | MEDIO | BAJO..MEDIO | Gate 2: sin chunks limpios no se llama al modelo y se responde 'No tengo información verificada' (evento sin_contexto_confiable); el error del retriever se captura (criterio 1) | — |
| 10 | Los nombres, correos o teléfonos de viewers quedan en texto plano en los logs o las trazas | 1 | 3 | 3 | **BAJO** | ALTO | BAJO..MEDIO | Gate 2: privacidad.py (huella HMAC con clave propia + redacción de correo, RUT, teléfono y links) en trazas, logs y avisos; test_gate2.py lo comprueba sobre el archivo de log real; .gitignore (Bloque 23) | Ningún comentario llega a la marca sin aprobación humana en el grafo del reporte (reporte_marca.py, Gate 2) |
| 11 | Un pico de mensajes en el chat dispara el gasto en la API | 2 | 1 | 2 | **BAJO** | BAJO | BAJO..MEDIO | Costo medido por consulta (Bloques 28 y 31); reintentos con backoff, no en bucle (Bloques 12 y 13) | — |
| 12 | El bot dice 'el contexto no menciona…' y el viewer no entiende qué es 'el contexto' | 1 | 1 | 1 | **BAJO** | MEDIO | BAJO | Versión 3 del prompt (959478c666ac), aprobada con el grafo de supervisión y activa (Bloque 32) | — |

## Evidencia de cada riesgo

1. **Un viewer escribe instrucciones en el chat público y el bot responde fuera del guion (insulta, habla de otra marca o revela sus instrucciones)**: El detector se esquiva con sinónimos o separando letras (probado en el Bloque 31).
2. **El agente marca como comentario negativo a un viewer que no lo era y su nombre llega a la marca**: La frontera crítica al juego/streamer vs. al producto es ambigua (dataset del Bloque 29).
3. **El bot publica en el chat un dato inventado del K7 que el filtro de salida no cubre (p. ej. 'tiene bluetooth' o 'llega mañana')**: Sin filtros, 3 de 3 corridas inventaron el link (Bloque 22). Desde el Gate 2 lo que queda es una frase CON cita que igual tergiversa el fragmento citado.
4. **Un cambio del prompt de sistema llega a producción sin registro ni revisión**: Hasta el Bloque 31 el prompt era un string suelto en el código; en el Gate 2 el del agente cambió sin aprobación y se regularizó como propuesta.
5. **El precio o las condiciones de la campaña cambian y el índice sigue con la versión vieja**: El corpus está en archivos .md que se editan a mano.
6. **La respuesta llega unos 9 s después y el chat ya cambió de tema**: Corrida real del Bloque 31: ~9 s de generación por respuesta.
7. **La API key se sube al repositorio público**: El repositorio es público.
8. **Un documento del corpus trae instrucciones escondidas (inyección indirecta)**: Hoy el corpus lo escribe solo la marca; sube si algún día se indexan comentarios o FAQ de usuarios.
9. **Todo el contexto recuperado se descarta por inyección y el modelo responde igual, sin respaldo**: Ensayo funcional del Gate 2: se publicó 'Dato inventado.' con n_limpios = 0.
10. **Los nombres, correos o teléfonos de viewers quedan en texto plano en los logs o las trazas**: Hasta el Gate 2, trazas.py guardaba nombre y mensaje, y el aviso del filtro de salida registraba la frase completa (con un correo, si el modelo lo repetía).
11. **Un pico de mensajes en el chat dispara el gasto en la API**: Costo real ≈ 0,13 USD por 1.000 respuestas (Bloque 28).
12. **El bot dice 'el contexto no menciona…' y el viewer no entiende qué es 'el contexto'**: Corrida real del Bloque 31 ('¿cuánto pesa el teclado?'); con la v3 respondió 'No tengo ese dato del K7.'.

## Para revisar con otra persona

- El precio o las condiciones de la campaña cambian y el índice sigue con la versión vieja (MEDIO, rango MEDIO..ALTO)
- La respuesta llega unos 9 s después y el chat ya cambió de tema (MEDIO, rango MEDIO..ALTO)
- La API key se sube al repositorio público (MEDIO, rango MEDIO..ALTO)

## Lectura

- Ningún riesgo queda CRÍTICO con lo ya construido, pero dos lo eran sin mitigar (datos inventados e inyección desde el chat). La inyección directa sigue ALTO (el detector se esquiva con sinónimos) y con revisión humana.
- Actualizada para el Gate 2 (2026-11-18): las correcciones de los criterios no compensables bajaron la PII en logs a BAJO y los datos inventados a MEDIO; el 'no sé' con jerga quedó BAJO al aprobarse la v3 del prompt.
- Las respuestas en vivo no se aprueban una por una (no escala y llegarían tarde): su supervisión es la revisión post-stream de lo que el filtro frenó o corrigió, y la aprobación de cada cambio de prompt.
- Riesgos con el mismo puntaje no son igual de urgentes: la API key (1×5) es rara y grave; el 'no sé' con jerga (5×1) es frecuente y leve.
