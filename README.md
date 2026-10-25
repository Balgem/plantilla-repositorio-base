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
3. **Un bot genérico es un riesgo.** Un modelo sin control inventa precios, descuentos o promociones que la marca no ofrece.

### Propuesta
Un módulo en Python que usa la API de Google Gemini para **clasificar** cada mensaje del chat, **responder** solo con los datos de la campaña (reconociendo lo que no sabe en vez de inventarlo), **resumir** el chat para el reporte a la marca y **medir** el costo en USD de cada interacción.

---

## 🏗️ 2. Arquitectura

![Diagrama de arquitectura del módulo](docs/diagrama.png)

### Componentes principales
* **`src/consumir_gemini.py`**: el módulo principal, con una función por responsabilidad:
  * `armar_peticion(...)`: valida la entrada y arma la petición con `systemInstruction` y `responseSchema`.
  * `enviar_peticion(...)`: hace el `POST` con timeout y convierte cada falla en un mensaje claro.
  * `con_reintentos(...)`: reintenta con espera creciente ante saturación (429, 5xx) o falta de conexión.
  * `extraer_texto(...)`: navega la respuesta de Gemini hasta el texto generado.
  * `parsear_respuesta_json(...)`: limpia el markdown y valida que el JSON traiga las claves esperadas.
  * `calcular_costo(...)`: calcula el costo en USD desde `usageMetadata`, incluidos los tokens de razonamiento.
* **`src/comparar_modelos.py`**: mide modelos de Gemini por costo, latencia, calidad y disponibilidad.
* **`prompts/banco.py`** y **`prompts/test_consistencia.py`**: el banco de prompts del bot y su prueba de consistencia.
* **`docs/decision-arquitectura.md`**: la elección del modelo, con la comparación completa y las alternativas descartadas.

### 📊 Comparación de modelos (medida el 2026-10-20)

| Modelo | Latencia mediana | Costo por 10.000 mensajes | Clasificación correcta |
| :--- | :--- | :--- | :--- |
| **`gemini-3.5-flash-lite`** ✅ | **1,95 s** | **1,32 USD** | 8 de 8 |
| `gemini-3.1-flash-lite` | 6,31 s | 0,84 USD | 8 de 8 |
| `gemini-3-flash-preview` | 3,63 s | 12,65 USD | 8 de 8 |
| `gemini-3.6-flash` | 4,98 s | 24,94 USD | 8 de 8 |
| `gemini-3.8-flash` | 10,45 s | 24,20 USD | 8 de 8 |

**Se eligió `gemini-3.5-flash-lite`**: en un chat en vivo la velocidad pesa más que una diferencia mínima de costo, y fue el más rápido sin inventar datos de la campaña.

---

## ⚡ 3. Instalación

### Requisitos
* **Python 3.12+** y **Git**. En macOS, `python3` suele ser el Python 3.9 del sistema: instala 3.12 con `brew install python@3.12`.
* Una **API key de Gemini**, gratuita en [Google AI Studio](https://aistudio.google.com/apikey).

### Paso 1: Clonar y crear el entorno virtual
```bash
git clone https://github.com/Balgem/plantilla-repositorio-base.git
cd plantilla-repositorio-base

# macOS / Linux:
python3.12 -m venv venv
source venv/bin/activate

# Windows (PowerShell):
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

### Paso 2: Instalar las dependencias
```bash
pip install -r requirements.txt
```

### Paso 3: Configurar las variables de entorno
```bash
cp .env.example .env
```
Edita `.env` y completa tu llave (el archivo está en `.gitignore`, así que nunca se sube):
```ini
API_KEY=tu_llave_de_gemini
GEMINI_MODEL=gemini-3.5-flash-lite
```

---

## 🚀 4. Uso

Con el entorno activo, desde la raíz del repositorio:
```bash
python3 src/consumir_gemini.py
```

### Salida esperada
```text
--- Entrada vacía ---
No se pudo completar la operación: La pregunta no puede estar vacía.
--- Entrada válida, sin instrucción de sistema ---
¡Conexión confirmada y funcionando!
--- Mensajes del chat, con la instrucción del bot como sistema ---
> cuánto cuesta el teclado??
pregunta_producto | ¡Hola! El teclado mecánico K7 cuesta 59.990 CLP. Pídelo acá: https://ejemplo.cl/r/k7
> hacen envíos a regiones?
pregunta_producto | No tengo esa información, revisa el link https://ejemplo.cl/r/k7
```

### Ejemplo de salida JSON (prompt `responder_viewer`)
**Entrada:** `"hacen envíos a regiones?"`
```json
{
  "respuesta": "No tengo información sobre envíos a regiones, te sugiero revisar el link https://ejemplo.cl/r/k7",
  "incluye_link": true,
  "dato_desconocido": true
}
```

### ⚠️ Alcance (Gate 1)
* **Qué SÍ hace:**
  * ✅ Clasifica mensajes del chat y responde solo con los datos de la campaña.
  * ✅ Entrega salidas JSON validadas con `responseSchema`.
  * ✅ Valida la entrada antes de llamar a la API y maneja los errores de red, cuota y formato.
  * ✅ Calcula el costo en USD de cada petición.
* **Qué NO hace todavía:**
  * ❌ No se conecta al chat de Twitch en vivo (Gate 2).
  * ❌ No registra las interacciones en una base de datos ni en un CRM (Gate 2).
  * ❌ No expone una API propia ni corre en un contenedor (Gate 3).

---

## 🛡️ 5. Manejo de errores

| Escenario | Dónde se controla | Respuesta |
| :--- | :--- | :--- |
| **Entrada vacía** o falta `API_KEY` | `armar_peticion` | `ValueError` antes de llamar a la API |
| **Sin conexión o timeout** | `enviar_peticion` | `RuntimeError: No se pudo conectar con el servicio...` |
| **Llave inválida** (400, 401, 403) | `enviar_peticion` | `RuntimeError` con el código, sin reintentar |
| **Cuota o saturación** (429, 5xx) | `con_reintentos` | Reintenta tras 2, 4 y 8 s; si sigue fallando, `RuntimeError` |
| **Respuesta sin texto o JSON inválido** | `extraer_texto`, `parsear_respuesta_json` | `RuntimeError` / `ValueError` con lo que falta |

---

## 🗂️ 6. Banco de prompts y consistencia

1. **`clasificar_mensaje`**: clasifica el mensaje y decide si el bot responde.
2. **`responder_viewer`**: responde con los datos de la campaña y reconoce lo que no sabe.
3. **`resumir_chat`**: resume un lote de mensajes para el reporte a la marca.

```bash
python3 prompts/test_consistencia.py
```
Ejecuta cada prompt 3 veces contra la API real y guarda el resultado en `prompts/registro_resultados.json`, con una **consistencia de 3/3** en los tres prompts.

---

## 🗺️ 7. Hoja de ruta

* **Gate 1 · Habilitación técnica (actual):** módulo de consumo de Gemini, salida JSON validada, banco de prompts y elección del modelo con datos medidos.
* **Gate 2 · Integración y orquestación:** lector del chat de Twitch en tiempo real y un agente con herramientas para consultar los viewers y registrar las interacciones en el CRM.
* **Gate 3 · Capstone:** API propia en un contenedor Docker, con pruebas y un reporte de impacto para la marca.
