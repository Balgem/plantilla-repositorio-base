# Evidencia del cliente modular (Bloque 12)

Pruebas de `consultar_modelo` (`src/cliente.py`) contra la API real de Gemini, el 2026-10-26.

## 1. Consulta normal

```text
$ python3 src/cliente.py
--- Entrada vacía ---
Error de configuración: La pregunta no puede estar vacía.
--- Consulta normal ---
La capital de Chile es Santiago.
--- Mensajes del chat, con la instrucción del bot ---
> cuánto cuesta el teclado??
pregunta_producto | ¡Hola! El teclado mecánico K7 cuesta 59.990 CLP. ⌨️🔥 Puedes revisar más detalles en https://ejemplo.cl/r/k7
> hacen envíos a regiones?
pregunta_producto | No tengo esa información, revisa el link https://ejemplo.cl/r/k7
```

## 2. API key inválida a propósito (`API_KEY=clave_invalida`)

Falla de inmediato y sin reintentar. Gemini responde 400 (`API_KEY_INVALID`), no 401, y el cliente lo trata como error de credencial.

```text
$ python3 src/cliente.py
--- Entrada vacía ---
Error de configuración: La pregunta no puede estar vacía.
--- Consulta normal ---
Error de configuración: Credencial inválida o sin permiso. Revisa tu API_KEY en el archivo .env.
--- Mensajes del chat, con la instrucción del bot ---
> cuánto cuesta el teclado??
Error de configuración: Credencial inválida o sin permiso. Revisa tu API_KEY en el archivo .env.
> hacen envíos a regiones?
Error de configuración: Credencial inválida o sin permiso. Revisa tu API_KEY en el archivo .env.
```

Con la llave inválida también se corrió la ráfaga de 30 consultas: las 30 fallaron por credencial y ninguna se reintentó.

## 3. Ráfaga de 30 consultas seguidas (llave válida)

Se provocó un límite de uso real. Aparecieron los dos resultados posibles:

**Reintentos agotados (consulta 15):**

```text
--- Consulta 15 de 30 ---
Intento 1 de 4 falló por límite de uso o saturación. Reintentando en 2 s...
Intento 2 de 4 falló por límite de uso o saturación. Reintentando en 4 s...
Intento 3 de 4 falló por límite de uso o saturación. Reintentando en 8 s...
Error del servicio: El servicio no respondió tras varios intentos. Intenta más tarde.
```

**Éxito después de reintentar (consulta 16):**

```text
--- Consulta 16 de 30 ---
Intento 1 de 4 falló por límite de uso o saturación. Reintentando en 2 s...
pregunta_producto | ¡Hola! El teclado mecánico K7 cuesta 59.990 CLP. 🎮✨ Puedes revisar todos los detalles y comprarlo aquí: https://ejemplo.cl/r/k7
```

Las otras 28 consultas respondieron al primer intento.
