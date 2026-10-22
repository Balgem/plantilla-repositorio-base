# Bot de chat con IA para campañas en Twitch

Miniaplicación en Python que usa la API de Google Gemini para el bot de chat de un stream de Twitch con una campaña publicitaria. El bot lee cada mensaje del chat, lo clasifica (`pregunta_producto`, `interes_compra`, `spam` u `otro`) y responde usando solo los datos de la campaña y su link medible.

Este repositorio corresponde al **Gate 1** del programa: el módulo que consume la API, procesa la respuesta, maneja los errores y fuerza una salida JSON estructurada. El agente que se conecta al chat en vivo se construye en el Gate 2.

## Qué hace

- **Consume la API de Gemini** por REST, con la llave en el header `x-goog-api-key`, nunca en la URL ni en el código.
- **Separa la instrucción del bot del mensaje del usuario**, usando `systemInstruction`.
- **Fuerza respuestas en JSON** con `responseSchema` y las valida antes de usarlas.
- **Maneja los errores** de conexión, de la API (4xx/5xx), de formato y de datos faltantes, siempre con un mensaje claro y sin cortar el programa.
- **Calcula el costo de cada petición**, incluyendo los tokens de razonamiento.

## Estructura

```
├── src/
│   ├── consumir_gemini.py      # módulo principal
│   └── comparar_modelos.py     # comparación de modelos por costo, latencia y calidad
├── prompts/
│   ├── banco.py                # banco de prompts del bot
│   ├── test_consistencia.py    # prueba de consistencia del banco
│   └── registro_resultados.json
├── docs/                       # diagramas, decisión de arquitectura y evidencias
├── tests/
├── .env.example                # plantilla de variables de entorno (sin valores reales)
└── requirements.txt
```

## Requisitos

- Python 3.12 o superior.
- Git.
- Una API key de Gemini. Es gratuita y no pide tarjeta: se crea en [Google AI Studio](https://aistudio.google.com/apikey).

## Instalación

**macOS / Linux / WSL**

```bash
git clone https://github.com/Balgem/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/Balgem/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Si PowerShell no permite activar el entorno, ejecuta una vez `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`.

## Configuración

Abre el archivo `.env` que acabas de crear y completa tu llave:

```
API_KEY=tu_llave_de_gemini
GEMINI_MODEL=gemini-3.5-flash-lite
```

| Variable | Obligatoria | Descripción |
|---|---|---|
| `API_KEY` | Sí | Tu API key de Gemini. Sin comillas ni espacios alrededor del `=`. |
| `GEMINI_MODEL` | No | Modelo a usar. Por defecto, `gemini-3.5-flash-lite`. La razón de esta elección está en [`docs/decision-arquitectura.md`](docs/decision-arquitectura.md). |

El archivo `.env` está excluido en `.gitignore`: nunca se sube al repositorio.

## Ejecución

Con el entorno activo y desde la raíz del repositorio (en Windows, usa `python` en vez de `python3`):

```bash
python3 src/consumir_gemini.py
```

Salida esperada (el texto del modelo varía en cada ejecución):

```
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

El primer mensaje de error es intencional: demuestra la validación de una entrada vacía.

### Otros scripts

```bash
python3 prompts/test_consistencia.py   # prueba cada prompt del banco 3 veces (~1 minuto)
python3 src/comparar_modelos.py        # compara 9 modelos (~15 minutos, unas 100 peticiones)
```

## Si algo falla

| Mensaje | Causa probable |
|---|---|
| `No se encontró la variable API_KEY en el archivo .env.` | No creaste el `.env` o la variable tiene otro nombre. |
| `El servicio respondió con un error (código 400)` o `(código 401)` | La llave está incompleta o no es válida. Vuelve a copiarla desde AI Studio. |
| `El servicio respondió con un error (código 429)` | Superaste el límite de uso gratuito. Espera un minuto. |
| `El servicio respondió con un error (código 503)` | El modelo está saturado. Reintenta, o cambia `GEMINI_MODEL` en el `.env`. |
| `ModuleNotFoundError` | El entorno virtual no está activo, o falta `pip install -r requirements.txt`. |

## Documentación

- [Diagrama del módulo](docs/diagrama.png) y [diagrama del proyecto completo](docs/diagrama_proyecto_banner.drawio) (se abre en [app.diagrams.net](https://app.diagrams.net)).
- [Decisión de arquitectura: elección de modelo](docs/decision-arquitectura.md), con la [comparación de 9 modelos](docs/comparacion_modelos.md).
- [Evidencia de la primera petición autenticada](docs/evidencia_peticion_autenticada.md).
- [Registro de consistencia del banco de prompts](prompts/registro_resultados.json).

## Registro del ensayo de instalación limpia

- **Fecha:** 2026-10-22.
- **Entorno:** contenedor Linux en la nube, sin nada instalado previamente; Python 3.13.
- **Pasos:** clonar desde GitHub, crear un entorno virtual nuevo, `pip install -r requirements.txt`, `cp .env.example .env` y ejecutar `src/consumir_gemini.py`.
- **Encontrado:** `.env.example` traía `GEMINI_MODEL=gemini-3.6-flash`, el modelo que la decisión de arquitectura descartó. Quien siguiera las instrucciones habría usado un modelo unas 19 veces más caro y más lento.
- **Corregido:** `.env.example` ahora trae `gemini-3.5-flash-lite`, y el README explica cada variable.
- **Resultado:** la instalación termina sin errores, `git status` del clon no muestra el `.env`, y el programa corre de principio a fin sin ningún traceback. Sin una llave válida, cada petición muestra un mensaje controlado en vez de cortar el programa.
