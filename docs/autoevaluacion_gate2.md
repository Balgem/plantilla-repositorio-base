# Autoevaluación del Gate 2

Con la función de la rúbrica (Bloque S1). Se reproduce con `python3 main.py autoevaluacion`: los puntajes son mi estimación, pero los cuatro criterios no compensables **no**: el script los mide corriendo `test_gate2.py` en ese momento.

## Criterios no compensables (medidos, 2026-11-18)

| Criterio | Resultado | Cómo se cumple |
|---|---|---|
| El pipeline corre de punta a punta | ✅ | Errores del retriever y del modelo capturados y registrados; `servicio_rag.py` termina en 0 |
| Cada respuesta cita su fuente | ✅ | Fuente desde la metadata del chunk; una frase sin cita válida no se publica |
| Logs sin contenido crudo sensible | ✅ | `src/privacidad.py` (HMAC + redacción) en logs, trazas y avisos; la prueba lee el archivo de log real |
| Supervisión humana funcionando | ✅ | Envío del reporte a la marca: `interrupt()` + checkpointer SQLite, se retoma con una decisión |

Antes de las correcciones de hoy, **dos fallaban** (las respuestas se publicaban sin fuente y un aviso del filtro podía registrar un correo) y dos estaban incompletos. El detalle está en `docs/registro_ensayo_gate2.md`.

## Puntaje por dimensión (mi estimación)

| Dimensión | Peso | Puntaje | Por qué | Lo que le falta |
|---|---|---|---|---|
| Pipeline RAG funcional | 25 % | 90 | Índice persistido e incremental, recuperación, generación y errores capturados, con un solo comando | No está conectado al chat real de Twitch |
| Recuperación y citación | 15 % | 85 | P = 0,333 (93 % de la máxima) y R = 0,962 con k = 3 sobre mi corpus; cita obligatoria | 15 casos de evaluación es poco |
| Costo, latencia y checklist | 10 % | 80 | Corrida real documentada por etapa; ≈ 0,13 USD por 1.000 respuestas; consumo en cada log | La generación tarda entre 2 y 9 s y no la optimicé |
| Personalización justificada | 15 % | 88 | Decisión con evidencia propia (20/20) y sensibilidad: no personalizar; la mejora sugerida (salida estructurada) quedó implementada | Dataset de 25 ejemplos para PEFT, aunque hoy no hace falta |
| Observabilidad y trazabilidad | 15 % | 92 | `trace_id` por consulta, consumo, huella del prompt, auditoría por respuesta | Sin tablero: archivos locales |
| Seguridad, versionado y gobernanza | 20 % | 88 | 4 capas contra inyección (RAG y agente), los dos prompts versionados con aprobación, dos supervisiones durables, viewers que inyectan marcados para revisión, matriz de 12 riesgos | El detector se esquiva con sinónimos (lo cubren la cita obligatoria y el filtro de salida) |

**Promedio ponderado: 87,8** · no compensables: 4 de 4 → listo para entregar.

Actualizada después de cerrar los dos pendientes que quedaban (salida estructurada en el clasificador; viewers que inyectan marcados en la revisión del reporte y prompt del agente versionado): +3 en personalización y +3 en seguridad. Donde dudé, dejé el puntaje más bajo: seguridad no llega a 90 porque el riesgo más alto de mi matriz (la inyección directa desde el chat) sigue en ALTO, aunque ya con supervisión.
