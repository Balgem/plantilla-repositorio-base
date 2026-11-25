# Bot de chat con IA para campañas en Twitch

Proyecto de la Especialización en Desarrollo con IA Generativa (Gate 2: servicio IA modular con RAG).

El bot lee el chat de un stream con una campaña publicitaria (un teclado ficticio, el K7) y responde las preguntas sobre el producto usando solo los documentos de la campaña, indicando de cuál sacó cada dato. Al final del stream arma un reporte para la marca, que no se envía hasta que una persona lo aprueba.

Lo hice así porque en mis primeras pruebas el modelo inventaba precios, descuentos y links (3 de 3 corridas inventaron el link de compra).

## Instalación

Necesitas Python 3.12 o superior (algunas versiones fijadas en `requirements.txt`, como numpy 2.5, no se instalan en 3.11) y una clave de Gemini de [Google AI Studio](https://aistudio.google.com/apikey).

```bash
git clone https://github.com/Balgem/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # y pon tu clave en GEMINI_API_KEY (también acepta API_KEY)
```

## Uso

```bash
python3 main.py verificar    # revisa Python, librerías, clave e índice
python3 main.py servicio     # índice + dos preguntas de ejemplo + estado de las aprobaciones
python3 main.py consulta "¿llega a Arica?"
python3 main.py gate2        # pruebas de los 4 criterios no compensables
python3 main.py pruebas      # todas las pruebas (sin API)
```

Sin clave se puede probar todo con embeddings y modelo simulados: `python3 servicio_rag.py --simulado`.

El índice (`vectorstore/`) no está en el repo. El servicio lo crea la primera vez (15 embeddings, un par de segundos) y después solo recalcula los chunks que cambiaron.

Una respuesta se ve así:

```
El despacho del K7 cuesta 3.990 CLP y se paga aparte del precio del teclado. (Fuente: 03_despacho.md)
```

Si el dato no está en los documentos, el bot responde "No tengo ese dato del K7.", sin fuente.

## Cómo funciona una consulta

1. Si la pregunta trae instrucciones para manipular al bot, no se responde.
2. Se recuperan los 3 chunks más cercanos del índice (Chroma).
3. Se descartan los chunks con instrucciones escondidas. Si no queda ninguno, el bot dice que no tiene información verificada, sin llamar al modelo.
4. Gemini responde con el prompt de sistema aprobado y cita cada dato con su número de fragmento.
5. Solo se publican las frases con una cita válida. La fuente sale de los metadatos del chunk, no del texto del modelo.
6. Los filtros de salida corrigen links y quitan promesas que la campaña no hace.

Cada paso queda en `logs/rag.jsonl` con el mismo `trace_id`. La pregunta se guarda solo como largo y huella (HMAC), nunca como texto.

El agente (`src/agente_con_herramientas.py`, `src/agente_con_memoria.py`) registra a quienes quieren comprar y marca comentarios negativos. Su herramienta `consultar_campana` usa el mismo RAG.

## Criterios no compensables

| Criterio | Cómo se cumple | Prueba |
|---|---|---|
| El pipeline corre sin excepciones | Los errores de la API se capturan y quedan en el log | `test_1` |
| Cada respuesta cita su fuente | Fuente desde los metadatos; una frase sin cita no se publica | `test_2` |
| Sin datos personales en los logs | `src/privacidad.py`: huellas HMAC y redacción de correo, RUT, teléfono y links | `test_3` |
| Supervisión humana real | El envío del reporte a la marca se detiene con `interrupt()` hasta que alguien decide | `test_4` |

## Supervisión humana

El reporte a la marca es la acción de mayor riesgo: habla en nombre del canal y no se puede retirar.

```bash
python3 main.py reporte                       # arma el reporte y se detiene
python3 main.py reporte --pendientes
python3 main.py reporte --aprobar THREAD_ID --comentarios c1,c3
python3 main.py reporte --rechazar THREAD_ID
```

Los cambios de prompt (del RAG y del agente) también pasan por aprobación: `python3 main.py supervision --proponer HUELLA`. Las aprobaciones pendientes se guardan en disco, así que se pueden resolver después.

Las respuestas del chat no se aprueban una por una porque llegarían tarde. Lo que el bot bloqueó o corrigió se revisa después con `python3 main.py logs --revisar`.

## Evidencia por dimensión

| Dimensión | Dónde está |
|---|---|
| Pipeline RAG | `servicio_rag.py`, `src/indexar_corpus.py`, `src/logging_rag.py` |
| Recuperación y citas | `src/evaluacion_recuperacion.py`: con k=3, precisión 0,333 y recall 0,962 (`docs/evaluaciones/`) |
| Costo y latencia | `docs/registros_latencia_costo.jsonl`: unos 0,13 USD por 1.000 respuestas; la generación es el 77 % del tiempo |
| Personalización | `docs/decision_personalizacion.md`: no personalizar (20/20 aciertos); el clasificador usa salida estructurada |
| Observabilidad | Logs JSON con `trace_id`, consumo y huella del prompt en cada consulta |
| Seguridad y gobernanza | `docs/matriz_riesgos.md`, `prompts/registro_versiones.json`, `src/privacidad.py`, `docs/limites_autonomia_agente.md` |

También están el registro del ensayo (`docs/registro_ensayo_gate2.md`) y mi autoevaluación (`docs/autoevaluacion_gate2.md`).

## Decisiones

- Modelo `gemini-3.5-flash-lite`: el más rápido de los que clasificaron bien 8 de 8 (`docs/decision-arquitectura.md`).
- Chunks de 250 caracteres: entra el párrafo más largo sin cortarse.
- k = 3: mejor F1 que k = 5 en mis 15 casos de evaluación.
- No personalizar el modelo: el problema de formato que lo justificaría no apareció.
- Prompt del RAG v3: la v2 hacía decir "el contexto no menciona…", y el viewer no sabe qué es el contexto.

## Limitaciones

- No está conectado al chat real de Twitch ni a un CRM.
- El detector de inyección se puede esquivar con sinónimos. Por eso también están la cita obligatoria y los filtros de salida.
- La generación tarda entre 2 y 9 segundos según la corrida.

## Comandos

`python3 main.py` muestra la lista completa. Los principales, además de los de arriba: `indexar`, `recuperar`, `evaluar`, `registro`, `decision`, `logs`, `prompts`, `matriz`, `agente`, `memoria`, `trazas`, `autoevaluacion`, y los del Gate 1 (`demo`, `consistencia`, `comparar --confirmar`).

## Estructura

```
main.py               punto de entrada
servicio_rag.py       el servicio completo
test_gate2.py         criterios no compensables
verificar_entorno.py  chequeo previo
corpus/campana_k7/    documentos de la campaña (ficticios)
prompts/              banco de prompts (Gate 1) y registro de versiones
src/                  código
tests/                pruebas sin API
docs/                 decisiones, evaluaciones y registros
```

## Gate 1

El Gate 1 fue el cliente de Gemini (`src/consumir_gemini.py`, `src/cliente.py`): validación de entrada, errores clasificados, reintentos con backoff y jitter, y costo por petición. Para elegir el modelo comparé 9 modelos con 8 mensajes de chat (20 de octubre de 2026):

| Modelo | Latencia (mediana) | Costo por 10.000 mensajes | Clasificó bien |
| --- | --- | --- | --- |
| gemini-3.5-flash-lite (elegido) | 1,95 s | 1,32 USD | 8 de 8 |
| gemini-3.1-flash-lite | 6,31 s | 0,84 USD | 8 de 8 |
| gemini-3-flash-preview | 3,63 s | 12,65 USD | 8 de 8 |
| gemini-3.6-flash | 4,98 s | 24,94 USD | 8 de 8 |
| gemini-3.8-flash | 10,45 s | 24,20 USD | 8 de 8 |
