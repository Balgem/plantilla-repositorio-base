# Evidencia del cliente modular (Bloques 12 y 13)

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

## 4. Registro del ensayo de rate limit (Bloque 13)

Con backoff exponencial con jitter y registro de costo ya integrados (`python3 src/cliente.py --rafaga 30`).

- **Fecha:** 2026-10-26.
- **Modelo:** `gemini-3.5-flash-lite`, con llave gratuita.
- **Peticiones enviadas:** 30 seguidas, sin pausa, rotando 5 mensajes de chat.
- **Primer límite de uso:** en la petición 16 (`Respuesta 15`). Las 15 primeras respondieron al primer intento. El cliente no muestra si fue 429 o 5xx, porque los dos se tratan igual.
- **Esperas observadas:** 2,1 s · 2,2 / 4,3 / 8,6 s · 2,2 / 4,1 / 8,5 s. Crecen al doble y nunca son exactamente iguales (jitter): el backoff funciona.
- **Resultado:** 29 de 30 respondieron. La petición 16 se recuperó con 1 reintento; la 17 agotó sus 4 intentos y terminó en `RuntimeError: El servicio no respondió tras varios intentos.`; la 18 se recuperó al cuarto intento.
- **Costo:** se registró solo en las 29 operaciones exitosas; la que falló no sumó nada. Entre 143 y 176 tokens por operación, unos 0,00012 USD cada una. **Costo total del ensayo: 0,003489 USD** (unos 1,20 USD por 10.000 mensajes, coherente con la medición del 2026-10-20).

```text
Respuesta 14: pregunta_producto | No hay descuentos, revisa el link https:...
Intento 1 de 4 falló. Reintentando en 2.1s...
Operación: 170 tokens, costo estimado: $0.000152 (acumulado: $0.001930)
Respuesta 15: pregunta_producto | ¡Hola! El teclado mecánico K7 cuesta 59....
Intento 1 de 4 falló. Reintentando en 2.2s...
Intento 2 de 4 falló. Reintentando en 4.3s...
Intento 3 de 4 falló. Reintentando en 8.6s...
Respuesta 16 falló definitivamente: El servicio no respondió tras varios intentos. Intenta más tarde.
Intento 1 de 4 falló. Reintentando en 2.2s...
Intento 2 de 4 falló. Reintentando en 4.1s...
Intento 3 de 4 falló. Reintentando en 8.5s...
Operación: 150 tokens, costo estimado: $0.000100 (acumulado: $0.002030)
Respuesta 17: pregunta_producto | No tengo esa información, revisa el link...
...
Costo total del ensayo: $0.003489
```

**Algo que noté:** el mismo mensaje ("dónde lo compro") a veces se clasificó como `interes_compra` y una vez como `pregunta_producto`. No afecta la respuesta, pero conviene tenerlo en cuenta para el reporte a la marca.
