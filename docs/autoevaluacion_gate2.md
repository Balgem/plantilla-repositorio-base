# Autoevaluación del Gate 2

Hecha con la fórmula de la rúbrica (`python3 main.py autoevaluacion`). Los puntajes son mi estimación; los criterios no compensables se miden corriendo `test_gate2.py`.

## Criterios no compensables

| Criterio | Resultado |
|---|---|
| El pipeline corre de punta a punta | Cumple |
| Cada respuesta cita su fuente | Cumple |
| Logs sin datos personales | Cumple |
| Supervisión humana funcionando | Cumple |

Al empezar la entrega, dos de estos fallaban (las respuestas salían sin fuente y un aviso del filtro podía guardar un correo). El detalle está en `docs/registro_ensayo_gate2.md`.

## Puntaje por dimensión

| Dimensión | Peso | Puntaje | Lo que le falta |
|---|---|---|---|
| Pipeline RAG funcional | 25 % | 90 | No está conectado al chat real de Twitch |
| Recuperación y citación | 15 % | 85 | 15 casos de evaluación es poco |
| Costo, latencia y checklist | 10 % | 80 | La generación tarda entre 2 y 9 s y no la optimicé |
| Personalización justificada | 15 % | 88 | El dataset para PEFT es chico (25 ejemplos), aunque hoy no hace falta |
| Observabilidad y trazabilidad | 15 % | 92 | Los logs son archivos locales, sin tablero |
| Seguridad, versionado y gobernanza | 20 % | 88 | El detector de inyección se esquiva con sinónimos |

Promedio ponderado: 87,8, con los 4 criterios no compensables cumplidos.
