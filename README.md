# 🎮 Bot de chat con IA para campañas publicitarias en Twitch

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Modelo](https://img.shields.io/badge/modelo-gemini--3.5--flash--lite-orange.svg)](docs/decision-arquitectura.md)
[![Consistencia de prompts](https://img.shields.io/badge/prompts-3%2F3%20consistentes-success.svg)](prompts/registro_resultados.json)

> **Un bot de chat con IA generativa que convierte la conversación de un stream en interacciones medibles para la marca: clasifica cada mensaje del chat, responde con los datos reales de la campaña y deja registro de lo que preguntó la audiencia.**

---

## 📌 1. Problema de negocio y propuesta de valor

Las marcas que invierten en publicidad dentro de transmisiones en vivo **no tienen métricas precisas** del impacto real de sus campañas. Un banner aparece en el stream, pero nadie mide qué preguntó el chat, quién mostró interés de compra ni qué dudas quedaron sin responder.

### Desafíos detectados
1. **El chat se mueve demasiado rápido.** Las preguntas sobre el producto quedan enterradas entre reacciones, memes y spam.
2. **Responder a mano no escala.** Un moderador no puede contestar cada pregunta con el precio y el link correctos.
3. **Un bot genérico es un riesgo.** Un modelo de lenguaje sin control inventa precios, descuentos o promociones que la marca no ofrece.

### Propuesta
Un módulo en Python que usa la API de Google Gemini para:
- **Clasificar** cada mensaje del chat (`pregunta_producto`, `interes_compra`, `spam` u `otro`) y decidir si el bot debe responder.
- **Responder** solo con los datos de la campaña activa, reconociendo lo que no sabe en vez de inventarlo.
- **Resumir** el chat para el reporte a la marca, con las preguntas frecuentes y el nivel de interés.
- **Medir** el costo en USD de cada interacción.

---

## 🏗️ 2. Arquitectura

![Diagrama de arquitectura del módulo](docs/diagrama.png)

El diagrama del proyecto completo, con el lector de chat, el agente y la API propia de los próximos Gates, está en [`docs/diagrama_proyecto_banner.drawio`](docs/diagrama_proyecto_banner.drawio) (se abre en [app.diagrams.net](https://app.diagrams.net)).

### Componentes

* **`src/consumir_gemini.py`**: el módulo principal, con una función por responsabilidad:
  * `armar_peticion(pregunta, system_instruction, response_schema)`: valida la entrada y arma la petición, con la instrucción de sistema y el esquema JSON separados del mensaje del usuario.
  * `enviar_peticion(url, headers, body)`: hace el `POST` con un tiempo límite de 30 s y convierte cada falla en un mensaje claro.
  * `extraer_texto(respuesta_json)`: navega la respuesta de Gemini hasta el texto generado.
  * `parsear_respuesta_json(texto, claves_esperadas)`: limpia el markdown, interpreta el JSON y valida que traiga las claves esperadas.
  * `calcular_costo(respuesta_json, precio_entrada, precio_salida)`: calcula el costo en USD desde `usageMetadata`, incluyendo los tokens de razonamiento.
* **`src/comparar_modelos.py`**: mide 9 modelos de Gemini por costo, latencia, calidad y disponibilidad.
* **`prompts/banco.py`**: el banco de prompts del bot, cada uno con su instrucción de sistema y su esquema JSON.
* **`prompts/test_consistencia.py`**: prueba cada prompt varias veces contra la API real y registra cuántas respuestas fueron válidas.

### 📊 Elección del modelo, con datos medidos

Se compararon 9 modelos con 8 mensajes de chat reales y 4 repeticiones para la latencia (2026-10-20). Estos son los 5 que respondieron de forma confiable:

| Modelo | Latencia mediana | Costo por 10.000 mensajes | Tokens de razonamiento | Clasificación correcta |
| :--- | :--- | :--- | :--- | :--- |
| **`gemini-3.5-flash-lite`** ✅ | **1,95 s** | **1,32 USD** | 0 | 8 de 8 |
| `gemini-3.1-flash-lite` | 6,31 s | 0,84 USD | 0 | 8 de 8 |
| `gemini-3-flash-preview` | 3,63 s | 12,65 USD | 368 | 8 de 8 |
| `gemini-3.6-flash` | 4,98 s | 24,94 USD | 605 | 8 de 8 |
| `gemini-3.8-flash` | 10,45 s | 24,20 USD | 587 | 8 de 8 |

**Se eligió `gemini-3.5-flash-lite`** porque en un chat en vivo la velocidad pesa más que una diferencia mínima de costo: fue el más rápido de los 9, respondió el 100 % de las peticiones al primer intento y ante una pregunta sin respuesta en los datos de la campaña dijo explícitamente que no tenía esa información. La justificación completa, las alternativas descartadas y los hallazgos están en [`docs/decision-arquitectura.md`](docs/decision-arquitectura.md), y los resultados con todas las respuestas, en [`docs/comparacion_modelos.md`](docs/comparacion_modelos.md).

---

## ⚡ 3. Instalación

### Requisitos
* **Python 3.12+** y **Git**. Las dependencias no se instalan en versiones anteriores.
  * **En macOS, `python3` a secas suele ser el Python 3.9 del sistema.** Por eso los comandos usan `python3.12`. Si no lo tienes, instálalo con `brew install python@3.12` o desde [python.org](https://www.python.org/downloads/).
* Una **API key de Gemini**. Es gratuita y no pide tarjeta: se crea en [Google AI Studio](https://aistudio.google.com/apikey).

### Paso 1: Clonar y crear el entorno virtual

**macOS / Linux / WSL**
```bash
git clone https://github.com/Balgem/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python3.12 -m venv venv
source venv/bin/activate
python3 --version   # debe decir Python 3.12 o superior
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/Balgem/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python -m venv venv
.\venv\Scripts\Activate.ps1
python --version   # debe decir Python 3.12 o superior
```

Si `python --version` muestra una versión menor, borra la carpeta `venv` y créala de nuevo con `py -3.12 -m venv venv`.

Si PowerShell no permite activar el entorno, ejecuta una vez `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`.

### Paso 2: Instalar las dependencias
```bash
pip install -r requirements.txt
```

### Paso 3: Configurar las variables de entorno
Crea tu `.env` a partir de la plantilla (`cp .env.example .env` en macOS/Linux, o `Copy-Item .env.example .env` en Windows) y completa tu llave:

```ini
API_KEY=tu_llave_de_gemini
GEMINI_MODEL=gemini-3.5-flash-lite
```

| Variable | Obligatoria | Descripción |
| :--- | :--- | :--- |
| `API_KEY` | Sí | Tu API key de Gemini, sin comillas ni espacios alrededor del `=`. |
| `GEMINI_MODEL` | No | Modelo a usar. Por defecto, `gemini-3.5-flash-lite`. |

El archivo `.env` está excluido en `.gitignore`: tu llave nunca se sube al repositorio.

---

## 🚀 4. Uso

Con el entorno activo y desde la raíz del repositorio (en Windows, usa `python` en vez de `python3`):

```bash
python3 src/consumir_gemini.py
```

### Salida esperada
El texto del modelo varía en cada ejecución. El primer mensaje de error es intencional: demuestra la validación de una entrada vacía.

```text
--- Entrada vacía ---
No se pudo completar la operación: La pregunta no puede estar vacía.
--- Entrada válida, sin instrucción de sistema ---
¡Conexión establecida y funcionando!
--- Mensajes del chat, con la instrucción del bot como sistema ---
> cuánto cuesta el teclado??
pregunta_producto | El teclado mecánico K7 cuesta 59.990 CLP. Cómpralo aquí: https://ejemplo.cl/r/k7
> hacen envíos a regiones?
pregunta_producto | No tengo esa información, revisa el link https://ejemplo.cl/r/k7
```

### Ejemplo de salida JSON estructurada
Con los prompts del banco, la respuesta llega como un objeto JSON validado. Estas son respuestas reales de la prueba de consistencia:

**Entrada (mensaje del chat):** `"hacen envíos a regiones?"`

```json
{
  "respuesta": "No tengo información sobre envíos a regiones, te sugiero revisar el link https://ejemplo.cl/r/k7",
  "incluye_link": true,
  "dato_desconocido": true
}
```

**Entrada:** `"cuánto cuesta el teclado que estás usando?? 👀"`

```json
{
  "categoria": "pregunta_producto",
  "confianza": 0.98,
  "debe_responder": true
}
```

---

## 🛡️ 5. Manejo de errores

El módulo **nunca se cae con un traceback ni falla en silencio**: cada error previsible se convierte en un mensaje claro.

| Escenario | Dónde se controla | Respuesta |
| :--- | :--- | :--- |
| **Pregunta vacía o que no es texto** | `armar_peticion`, antes de llamar a la API | `ValueError: La pregunta no puede estar vacía.` |
| **Falta la llave en `.env`** | `armar_peticion` | `ValueError: No se encontró la variable API_KEY en el archivo .env.` |
| **Sin conexión o sin respuesta en 30 s** | `enviar_peticion` (`ConnectionError`, `Timeout`) | `RuntimeError: No se pudo conectar con el servicio...` |
| **Llave inválida, cuota excedida o servicio saturado** (400, 401, 429, 503) | `enviar_peticion` | `RuntimeError: El servicio respondió con un error (código ...)` |
| **La respuesta no es JSON** | `enviar_peticion` (`JSONDecodeError`) | `RuntimeError: La respuesta del servicio no llegó en el formato esperado.` |
| **La respuesta no trae el texto** | `extraer_texto` (`KeyError`, `IndexError`) | `RuntimeError: La respuesta no trae el texto generado...` |
| **JSON con markdown, inválido o sin las claves esperadas** | `parsear_respuesta_json` | Limpia el markdown; si igual falla, `ValueError` con las claves que faltan. |

Cada excepción conserva la causa técnica original (`raise ... from error`) para depurar, mientras el usuario ve un mensaje simple.

### Si algo falla al ejecutar

| Mensaje | Qué hacer |
| :--- | :--- |
| `No se encontró la variable API_KEY` | Crea el `.env` (paso 3) y revisa que la variable se llame exactamente `API_KEY`. |
| `código 400` o `código 401` | La llave está incompleta o no es válida: vuelve a copiarla desde AI Studio. |
| `código 429` | Superaste el límite gratuito: espera un minuto. |
| `código 503` | El modelo está saturado: reintenta, o cambia `GEMINI_MODEL` en el `.env`. |
| `Could not find a version that satisfies the requirement ...` al instalar | El entorno se creó con un Python anterior a 3.12. Borra la carpeta `venv` y créala de nuevo con `python3.12 -m venv venv` (en Windows, `py -3.12 -m venv venv`). |
| `ModuleNotFoundError` | El entorno no está activo o la instalación falló: actívalo y vuelve a correr `pip install -r requirements.txt`, revisando que termine sin errores. |

---

## 🗂️ 6. Banco de prompts y consistencia

La carpeta `prompts/` tiene los prompts del bot, cada uno con su instrucción de sistema y un esquema JSON que la API aplica al generar la respuesta (`responseSchema`):

| Prompt | Qué hace | Salida JSON | Consistencia |
| :--- | :--- | :--- | :--- |
| **`clasificar_mensaje`** | Clasifica un mensaje del chat y decide si el bot responde | `categoria`, `confianza`, `debe_responder` | 3/3 ✅ |
| **`responder_viewer`** | Responde con los datos de la campaña y reconoce lo que no sabe | `respuesta`, `incluye_link`, `dato_desconocido` | 3/3 ✅ |
| **`resumir_chat`** | Resume un lote de mensajes para el reporte a la marca | `resumen`, `preguntas_frecuentes`, `nivel_interes` | 3/3 ✅ |

```bash
python3 prompts/test_consistencia.py
```

El script ejecuta cada prompt 3 veces contra la API real y guarda el resultado en [`prompts/registro_resultados.json`](prompts/registro_resultados.json). En dos corridas completas, las **18 respuestas fueron válidas** y con la estructura correcta.

Para repetir la comparación de modelos (unos 15 minutos, unas 100 peticiones):

```bash
python3 src/comparar_modelos.py
```

---

## 🔐 7. Seguridad

- La llave vive solo en `.env`, excluido en `.gitignore`, y viaja en el header `x-goog-api-key`, nunca en la URL ni en el código.
- `.env.example` documenta las variables sin ningún valor real.
- El historial completo del repositorio fue revisado: `.env` nunca se subió y no hay ninguna llave en ningún commit.

---

## 🗺️ 8. Hoja de ruta

* **Gate 1 · Habilitación técnica (actual)**
  * Módulo que consume la API de Gemini, con funciones separadas y manejo de errores.
  * Prompt de sistema, salida JSON validada y banco de prompts con consistencia medida.
  * Elección del modelo con datos medidos y arquitectura documentada.
* **Gate 2 · Integración y orquestación**
  * Lector del chat de Twitch en tiempo real.
  * Agente con herramientas: consultar los viewers en vivo, registrar las interacciones en el CRM y responder solo cuando corresponde.
  * Links medibles conectados con el CRM, y reintentos con espera creciente ante la saturación del servicio.
* **Gate 3 · Capstone**
  * API propia expuesta en un contenedor Docker, con documentación técnica y pruebas.
  * Reporte de impacto de la campaña para la marca.

---

## 📋 9. Registro de los ensayos de instalación limpia

### Ensayo 2 · macOS (2026-10-25)

- **Entorno:** MacBook con chip Apple, macOS 14, zsh. Clon nuevo en una carpeta aparte, siguiendo solo este README.
- **Encontrado:** en macOS, `python3` a secas es el Python 3.9 del sistema. El entorno se creó con 3.9 y `pip install -r requirements.txt` falló (`Could not find a version that satisfies the requirement annotated-types==0.8.0`), así que después faltaba `requests`.
- **Corregido:** el README ahora exige Python 3.12, crea el entorno con `python3.12 -m venv venv`, explica cómo instalarlo con Homebrew y agrega el error a la tabla de problemas frecuentes.
- **Resultado:** Python 3.12, las 26 dependencias instaladas sin errores, `git status` del clon limpio (el `.env` no aparece) y una corrida real con la API sin ningún traceback.

### Ensayo 1 · Nube (2026-10-22)

- **Entorno:** contenedor Linux en la nube, sin nada instalado previamente; Python 3.13.
- **Pasos:** clonar desde GitHub, crear un entorno virtual nuevo, `pip install -r requirements.txt`, `cp .env.example .env` y ejecutar `src/consumir_gemini.py`.
- **Encontrado:** `.env.example` traía `GEMINI_MODEL=gemini-3.6-flash`, el modelo que la decisión de arquitectura descartó. Quien siguiera las instrucciones habría usado un modelo unas 19 veces más caro y más lento.
- **Corregido:** `.env.example` ahora trae `gemini-3.5-flash-lite`, y el README explica cada variable.
- **Resultado:** la instalación termina sin errores, `git status` del clon no muestra el `.env`, y el programa corre de principio a fin sin ningún traceback. Sin una llave válida, cada petición muestra un mensaje controlado en vez de cortar el programa.
