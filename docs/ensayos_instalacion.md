# Registro de los ensayos de instalación limpia

Cada ensayo clona el repositorio en una carpeta nueva y sigue solo el README, para comprobar que otra persona puede instalarlo y ejecutarlo sin ayuda.

## Ensayo 2 · macOS (2026-10-25)

- **Entorno:** MacBook con chip Apple, macOS 14, zsh. Clon nuevo en una carpeta aparte, siguiendo solo el README.
- **Encontrado:** en macOS, `python3` a secas es el Python 3.9 del sistema. El entorno se creó con 3.9 y `pip install -r requirements.txt` falló (`Could not find a version that satisfies the requirement annotated-types==0.8.0`), así que después faltaba `requests`.
- **Corregido:** el README ahora exige Python 3.12, crea el entorno con `python3.12 -m venv venv`, explica cómo instalarlo con Homebrew y agrega el error a la tabla de problemas frecuentes.
- **Resultado:** Python 3.12, las 26 dependencias instaladas sin errores, `git status` del clon limpio (el `.env` no aparece) y una corrida real con la API sin ningún traceback.

## Ensayo 1 · Nube (2026-10-22)

- **Entorno:** contenedor Linux en la nube, sin nada instalado previamente; Python 3.13.
- **Pasos:** clonar desde GitHub, crear un entorno virtual nuevo, `pip install -r requirements.txt`, `cp .env.example .env` y ejecutar `src/consumir_gemini.py`.
- **Encontrado:** `.env.example` traía `GEMINI_MODEL=gemini-3.6-flash`, el modelo que la decisión de arquitectura descartó. Quien siguiera las instrucciones habría usado un modelo unas 19 veces más caro y más lento.
- **Corregido:** `.env.example` ahora trae `gemini-3.5-flash-lite`, y el README explica cada variable.
- **Resultado:** la instalación termina sin errores, `git status` del clon no muestra el `.env`, y el programa corre de principio a fin sin ningún traceback. Sin una llave válida, cada petición muestra un mensaje controlado en vez de cortar el programa.
