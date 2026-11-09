# Límites de autonomía: bot de chat de la campaña K7

El bot trabaja en dos momentos y cada uno tiene su propio nivel de autonomía:

- **En vivo** (`src/agente_con_memoria.py`): el agente responde preguntas en el chat de Twitch y decide solo qué herramienta usar. Todo lo que hace ahí es leer o escribir registros internos.
- **Post-stream** (`src/reporte_marca.py`): cuando termina la transmisión se arma el reporte para la marca desde la traza. Esto es lo único que sale hacia afuera, así que nada se envía sin que una persona lo apruebe.

## Herramientas y nivel de riesgo

| Herramienta / acción | Momento | Riesgo | Por qué |
|---|---|---|---|
| `consultar_campana` | En vivo | 🟢 Bajo | Solo lee datos fijos de la campaña (precio, link, descuentos). Si la usa de más, el peor caso es una respuesta repetida. |
| `consultar_viewers` | En vivo | 🟢 Bajo | Solo lee un número. No cambia nada. |
| `registrar_interes_compra` | En vivo | 🟡 Medio | Escribe en el CRM. Un registro equivocado se corrige o se borra después, y no se duplica: si el viewer insiste, se actualiza su registro. |
| `marcar_comentario_negativo` | En vivo | 🟡 Medio | Deja un flag interno en un comentario. No se lo manda a nadie; queda pendiente de revisión. Un flag equivocado solo cuesta el tiempo de descartarlo. |
| Incluir un comentario en el reporte | Post-stream | 🔴 Alto | Una vez que llega a la marca no se puede retirar. Un comentario mal marcado (una broma, alguien que hablaba de otro producto) termina como crítica oficial. |
| Enviar el reporte a la marca | Post-stream | 🔴 Alto | Sale de nuestro control y la marca toma decisiones con él. |

La clasificación está también en el código (`NIVEL_DE_RIESGO` en `src/agente_con_herramientas.py` y `ACCIONES_DE_RIESGO_ALTO` en `src/reporte_marca.py`).

Además, publicar la respuesta en el chat es público y no se puede borrar del stream, pero no tiene aprobación humana porque en un chat en vivo la respuesta pierde sentido en segundos. Lo cubren chequeos deterministas que corren antes de publicar (`filtrar_salida`): el link siempre es el oficial y se quitan las promesas que la campaña no hace (stock, ofertas, envío gratis).

## Herramientas que requieren aprobación humana

- **Incluir cada comentario marcado en el reporte:** se aprueba uno por uno, no todos juntos, porque el error típico es un falso positivo puntual. Sin respuesta en 300 s, el comentario queda fuera.
- **Enviar el reporte a la marca:** se muestra completo antes de aprobar. Sin respuesta en 300 s, no se envía.

Las cuatro herramientas en vivo **no** piden aprobación: son de riesgo bajo o medio, y pedirla en pleno chat obligaría a alguien a aprobar cada mensaje, hasta aprobar por costumbre. Se revisan después en la traza.

Implementación (`esperar_aprobacion` en `src/supervision.py`):
- Límite de tiempo con `select`. Sin respuesta, sin consola o con cualquier duda, devuelve **no aprobado**.
- Cada decisión, sí o no, queda en `aprobaciones.jsonl` con la acción, los datos, quién decidió y cuándo.
- El reporte no lleva nombres de viewers: la marca recibe lo que se dijo, no quién lo dijo.

Verificado contra el código (2026-11-09):

```
$ grep -n "esperar_aprobacion(" src/reporte_marca.py
72:        aprobado = supervision.esperar_aprobacion(       # revisar_comentarios
105:    aprobado = supervision.esperar_aprobacion(...)        # enviar_reporte_a_marca
$ grep -n "esperar_aprobacion(" src/agente_con_herramientas.py src/agente_con_memoria.py
(sin resultados: el agente en vivo no tiene acciones de riesgo alto)
```

El mismo chequeo está automatizado en `tests/test_reporte_marca.py` y `tests/test_supervision_y_trazas.py`. Si alguien saca la aprobación de una acción de riesgo alto, o agrega una herramienta en vivo sin clasificar, las pruebas fallan.

## Revisión de trazas

Cada turno del chat queda como una línea en `trazas_agente.jsonl` (`src/trazas.py`) con:
- la entrada;
- las herramientas, con sus argumentos y lo que devolvieron;
- lo que respondió el modelo **y** lo que se publicó después de los filtros;
- el error, si hubo.

Ese archivo, `aprobaciones.jsonl` y `reporte_marca.md` tienen mensajes de viewers, por eso están en `.gitignore` y no se suben.

- **Frecuencia:**
  - Antes de cada reporte, todos los comentarios marcados: es el paso de aprobación.
  - Después de cada stream, la primera pasada automática (`python3 src/trazas.py`) y la lectura de todo lo que marque.
  - Una vez por semana, una muestra de 10 turnos sin marcas.
- **Qué se busca** (`python3 src/trazas.py` lo marca; la decisión es mía):
  - 🧩 **Un filtro cambió la respuesta.** El modelo escribió algo que ninguna herramienta le dio, por ejemplo un link inventado. Es el patrón más frecuente hasta ahora.
  - 🔄 **La misma herramienta dos veces seguidas.** El agente no avanza o una observación lo confundió.
  - 🔴 **Una herramienta de riesgo alto o sin clasificar en el agente en vivo.** Hoy no debería aparecer nunca: si aparece, alguien agregó una herramienta sin pasar por esta clasificación.
  - 🚩 **Comentarios marcados.** Además de aprobarlos uno por uno, reviso si el bot marca bromas o deja pasar críticas reales.
  - ⚠️ **Errores.** Turnos en que el agente falló y el bot no respondió.

### Traza real (2026-11-09, `gemini-3.5-flash-lite`)

```
$ wc -l trazas_agente.jsonl                                              → 7
$ grep -c '"herramienta": "marcar_comentario_negativo"' trazas_agente.jsonl → 2
$ grep -c '"herramienta": "registrar_interes_compra"' trazas_agente.jsonl   → 2
```

7 turnos de 5 viewers, con herramientas de los dos niveles del agente en vivo: `consultar_campana` (bajo) 3 veces, `registrar_interes_compra` (medio) 2 y `marcar_comentario_negativo` (medio) 2.

- **🧩 1 caso de filtro.** En "y si compro 2?" el modelo escribió `https://k7keyboard.example.com` aunque había consultado la campaña. `corregir_links` publicó el link oficial. En las pruebas anteriores había inventado `teclado-k7-campana.com` y `k7keyboard.com`: pasó en 3 de 3 corridas.
- **🚩 2 comentarios marcados, los dos correctos.** troll99 se quejó de la calidad y maria_fps del precio. La broma de tomas ("jajaja qué buena jugada") no se marcó.
- **🔄 0 repeticiones, 🔴 0 herramientas de riesgo alto en vivo, ⚠️ 0 errores.**
- **Post-stream:** rechacé el comentario de troll99 (dice que le pasó a su primo y no se puede verificar) y aprobé el de maria_fps (crítica de precio, útil para la marca). Aprobé el envío. `aprobaciones.jsonl` quedó con 3 decisiones (1 rechazada, 2 aprobadas) y el reporte salió sin nombres de viewers.

Cosas que la traza mostró y los filtros **no** atrapan (quedan para revisión manual):
- **"Podés revisar … el link de compra en la descripción del canal"** (ana_gamer). No es un link, así que `corregir_links` no lo ve, pero ninguna herramienta dijo que el link esté en la descripción.
- **"y si compro 2?"** registró interés de compra con una pregunta hipotética y no dio el total (119.980 CLP), cosa que sí hizo en corridas anteriores.
- **El bot le respondió a troll99 "Comentario registrado".** Le cuenta al viewer que quedó marcado, y no hace falta que lo sepa.

## Qué hacer ante un comportamiento inesperado

1. **Cortar el efecto.** Si una herramienta se usa mal varias veces en un stream (por ejemplo, marca muchas bromas o registra compras que nadie pidió), la saco de `HERRAMIENTAS` en `src/agente_con_herramientas.py`. El bot sigue respondiendo con las demás. Si el problema es la respuesta publicada, dejo el bot en modo sin respuesta (`SIN_RESPUESTA`) hasta revisar.
2. **No enviar nada a la marca** con datos de ese stream hasta terminar la revisión. Si el reporte no se aprueba, no sale.
3. **Encontrar los turnos** con `python3 src/trazas.py` y `grep '"session_id": "<viewer>"' trazas_agente.jsonl`. Comparar `respuesta_modelo` con `respuesta_final` y las observaciones de las herramientas.
4. **Corregir en el lugar que corresponde:**
   - Si eligió mal la herramienta, ajusto el docstring ("Usar solo cuando…").
   - Si los argumentos vinieron mal, ajusto las descripciones del `args_schema`.
   - Si inventó un dato, primero agrego un chequeo determinista (como con el link y las promesas) y después el prompt, porque el prompt solo no alcanzó ni una vez.
5. **Agregar una prueba con el caso real** en `tests/`, con un modelo falso que devuelva exactamente lo que devolvió Gemini (así se encontró el error de los bloques con `signature`).
6. **Volver a correr** `pytest -q` y la conversación de ejemplo antes de reactivar la herramienta, y dejar anotado el caso en este documento.

## Pendiente (lo que todavía no está implementado)

- La aprobación es por consola. En el bot real tiene que venir de otra interfaz (un panel o un mensaje al encargado de la campaña), con el mismo valor por defecto: sin respuesta, no se envía.
- `select()` sobre la consola no funciona en Windows. Hoy corre en macOS.
- El reporte se arma con **toda** la traza. En el bot real cada stream tiene que tener su propio archivo o un filtro por fecha.
- El CRM y el envío a la marca son simulados (`REGISTRO_CRM` y `reporte_marca.md`).
- Falta que el bot no le diga al viewer que su comentario quedó marcado y que no registre compras ante preguntas hipotéticas.
