"""Compara modelos de Gemini por costo, latencia, calidad y disponibilidad para el bot de chat.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 src/comparar_modelos.py

Guarda los resultados en docs/comparacion_modelos.md y docs/comparacion_modelos.json.
"""
import json
import os
import re
import statistics
import time
from datetime import date
from pathlib import Path

from consumir_gemini import (
    armar_peticion,
    calcular_costo,
    con_reintentos,
    enviar_peticion,
    extraer_texto,
)

# Precios en USD por millón de tokens, de https://ai.google.dev/gemini-api/docs/pricing
# (consultados el 2026-10-20; la salida incluye los tokens de razonamiento).
# None = la página oficial no publica precio para ese modelo.
MODELOS = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.7-flash": None,
    "gemini-2.5-flash-lite": None,
    "gemma-4-26b-a4b-it": None,
    "gemma-4-31b-it": None,
}

# Sin nivel gratuito: no se pueden probar con una llave gratuita. Solo referencia de precio.
SOLO_PAGO = {
    "gemini-3.1-pro-preview": (2.00, 12.00),
    "gemini-4-argon": (2.00, 10.00),
    "gemini-omni-1.1-flash": (1.50, 9.00),
}

CAMPANA = (
    "Producto: teclado mecánico K7. Precio: 59.990 CLP. "
    "Link de compra: https://ejemplo.cl/r/k7. No hay descuentos ni comandos de chat."
)

INSTRUCCION = (
    "Eres el bot de chat de un stream de Twitch con esta campaña publicitaria: "
    + CAMPANA
    + " Usa solo esos datos: si no sabes algo, invita a revisar el link. "
    "Clasifica el mensaje del viewer en una sola categoría: pregunta_producto, "
    "interes_compra, spam u otro. Responde en una línea con el formato "
    "'categoria | respuesta breve para el chat'. Mensaje: "
)

# (mensaje, categoría esperada). El primero se repite para medir la latencia.
MENSAJES = [
    ("cuánto cuesta el teclado que estás usando?? 👀", "pregunta_producto"),
    ("lo quiero!! dónde lo compro", "interes_compra"),
    ("SIGAN MI CANAL, seguidores gratis en bit.ly/regalo", "spam"),
    ("jajaja qué buena jugada", "otro"),
    ("hacen envíos a regiones?", "pregunta_producto"),
    ("how much is the keyboard?", "pregunta_producto"),
    ("compro 2 si me hacen descuento", "interes_compra"),
    ("a qué hora termina el stream?", "otro"),
]

REPETICIONES = 4
PAUSA_SEGUNDOS = 4
CARPETA_DOCS = Path(__file__).resolve().parent.parent / "docs"

CODIGO = re.compile(r"código (\d{3})")
# Datos que la campaña no entrega: otros precios, descuentos, comandos, envíos o plazos.
DATO_INVENTADO = re.compile(
    r"\$|usd|descuento|\d+\s?%|(?<!\w)!\w+|gratis|\b\d+\s?(días|horas|hrs)\b", re.IGNORECASE
)
NEGACIONES = re.compile(
    r"no (hay|tenemos|contamos con|existen?|incluye|ofrecemos) (ningún |ning[uú]n )?descuentos?|sin descuentos?",
    re.IGNORECASE,
)


def inventa_datos(texto):
    limpio = re.sub(r"\$\s?59\.990|59\.990", "", texto)
    limpio = NEGACIONES.sub("", limpio)
    return bool(DATO_INVENTADO.search(limpio))


def promociona(texto):
    return "ejemplo.cl" in texto or "59.990" in texto


def medir_con_reintentos(modelo, mensaje, precios):
    """Envía un mensaje al modelo (con reintentos) y registra latencia, costo y respuesta."""
    os.environ["GEMINI_MODEL"] = modelo

    def peticion_medida():
        inicio = time.perf_counter()
        respuesta = enviar_peticion(url, headers, body)
        return respuesta, time.perf_counter() - inicio

    try:
        url, headers, body = armar_peticion(INSTRUCCION + mensaje)
        (respuesta_json, latencia), intentos = con_reintentos(peticion_medida)
        texto = extraer_texto(respuesta_json).strip()
    except (ValueError, RuntimeError, TimeoutError) as error:
        codigo = CODIGO.search(str(error))
        return {
            "ok": False,
            "intentos": getattr(error, "intentos", 1),
            "error": codigo.group(1) if codigo else "conexión",
        }
    uso = respuesta_json.get("usageMetadata", {})
    costo = calcular_costo(respuesta_json, precios[0] / 1e6, precios[1] / 1e6) if precios else None
    return {
        "ok": True,
        "intentos": intentos,
        "latencia": latencia,
        "costo": costo,
        "texto": texto,
        "razonamiento": uso.get("thoughtsTokenCount", 0),
    }


def evaluar_modelo(modelo, precios):
    print(f"\n=== {modelo} ===")
    pruebas = [MENSAJES[0]] * (REPETICIONES - 1) + MENSAJES
    registros = []
    for numero, (mensaje, esperada) in enumerate(pruebas, start=1):
        r = medir_con_reintentos(modelo, mensaje, precios)
        r.update({"mensaje": mensaje, "esperada": esperada, "repeticion": numero <= REPETICIONES})
        if r["ok"]:
            categoria = r["texto"].split("|")[0].strip().lower()
            r["correcta"] = categoria == esperada
            r["inventa"] = inventa_datos(r["texto"])
            r["promo_indebida"] = esperada in ("spam", "otro") and promociona(r["texto"])
            print(f"Prueba {numero}: {r['latencia']:.2f} s ({r['intentos']} intento/s)")
        else:
            print(f"Prueba {numero}: falló con error {r['error']} tras {r['intentos']} intento/s")
        registros.append(r)
        time.sleep(PAUSA_SEGUNDOS)
        if numero == 1 and not r["ok"] and r["error"] in ("400", "403", "404"):
            print("El modelo no está disponible con esta llave: se omite el resto.")
            break
    return resumir(registros, precios)


def resumir(registros, precios):
    ok = [r for r in registros if r["ok"]]
    calidad, vistos = [], set()  # una respuesta por mensaje distinto
    for r in ok:
        if r["mensaje"] not in vistos:
            vistos.add(r["mensaje"])
            calidad.append(r)
    lat_rep = [r["latencia"] for r in ok if r["repeticion"]]
    lat_todas = [r["latencia"] for r in ok]
    costos = [r["costo"] for r in ok if r["costo"] is not None]
    errores = {}
    for r in registros:
        if not r["ok"]:
            errores[r["error"]] = errores.get(r["error"], 0) + 1
    promo_base = [r for r in calidad if r["esperada"] in ("spam", "otro")]
    return {
        "precios": precios,
        "peticiones": len(registros),
        "respondidas": len(ok),
        "primer_intento": sum(1 for r in ok if r["intentos"] == 1),
        "errores": errores,
        "latencia_promedio": statistics.mean(lat_rep) if lat_rep else None,
        "latencia_mediana": statistics.median(lat_todas) if lat_todas else None,
        "latencia_min": min(lat_todas) if lat_todas else None,
        "latencia_max": max(lat_todas) if lat_todas else None,
        "costo": statistics.mean(costos) if costos else None,
        "razonamiento": statistics.mean(r["razonamiento"] for r in ok) if ok else None,
        "evaluadas": len(calidad),
        "correctas": sum(r["correcta"] for r in calidad),
        "inventa": sum(r["inventa"] for r in calidad),
        "promo_indebida": sum(r["promo_indebida"] for r in promo_base),
        "promo_base": len(promo_base),
        "registros": registros,
    }


def apto(res):
    """Criterios mínimos para usarlo en el bot (explícitos para poder discutirlos)."""
    return (
        res["precios"] is not None
        and res["peticiones"] > 0
        and res["respondidas"] / res["peticiones"] >= 0.9
        and res["evaluadas"] >= len(MENSAJES) - 1
        and res["correctas"] >= res["evaluadas"] - 1
        and res["inventa"] == 0
    )


def f(valor, plantilla, vacio="sin datos"):
    return vacio if valor is None else plantilla.format(valor)


def generar_markdown(resultados, fecha):
    nombres = list(resultados)
    lineas = [f"# Comparación de modelos para el bot de chat ({fecha})", ""]
    lineas += [
        f"Generado con `src/comparar_modelos.py`: {REPETICIONES} repeticiones del mismo mensaje "
        f"para la latencia y {len(MENSAJES)} mensajes de chat para la calidad, con reintentos "
        f"de espera creciente (2, 4 y 8 s) ante errores 429, 5xx o de conexión. "
        "Precios de https://ai.google.dev/gemini-api/docs/pricing consultados el 2026-10-20.",
        "",
    ]
    filas = [
        ("Entrada (USD / 1M tokens)", lambda r: f(r["precios"] and r["precios"][0], "{:.2f}", "sin precio publicado")),
        ("Salida (USD / 1M tokens)", lambda r: f(r["precios"] and r["precios"][1], "{:.2f}", "sin precio publicado")),
        ("Respondidas", lambda r: f"{r['respondidas']} de {r['peticiones']}"),
        ("Respondidas al primer intento", lambda r: f"{r['primer_intento']} de {r['peticiones']}"),
        ("Errores", lambda r: ", ".join(f"{k}×{v}" for k, v in r["errores"].items()) or "ninguno"),
        (f"Latencia promedio (mismo mensaje ×{REPETICIONES})", lambda r: f(r["latencia_promedio"], "{:.2f} s")),
        ("Latencia mediana (todas)", lambda r: f(r["latencia_mediana"], "{:.2f} s")),
        ("Latencia mín – máx", lambda r: "sin datos" if r["latencia_min"] is None else f"{r['latencia_min']:.2f} – {r['latencia_max']:.2f} s"),
        ("Costo promedio por mensaje (USD)", lambda r: f(r["costo"], "{:.6f}", "sin precio")),
        ("Costo por 10.000 mensajes (USD)", lambda r: f(r["costo"] and r["costo"] * 10_000, "{:.2f}", "sin precio")),
        ("Tokens de razonamiento promedio", lambda r: f(r["razonamiento"], "{:.0f}")),
        ("Clasificación correcta", lambda r: f"{r['correctas']} de {r['evaluadas']}"),
        ("Respuestas con datos inventados", lambda r: f"{r['inventa']} de {r['evaluadas']}"),
        ("Publicidad a spam u off-topic", lambda r: f"{r['promo_indebida']} de {r['promo_base']}"),
        ("Cumple los criterios mínimos", lambda r: "sí" if apto(r) else "no"),
    ]
    lineas += ["| Criterio | " + " | ".join(f"`{n}`" for n in nombres) + " |", "|---|" + "---|" * len(nombres)]
    for criterio, valor in filas:
        lineas.append(f"| {criterio} | " + " | ".join(valor(resultados[n]) for n in nombres) + " |")

    aptos = sorted((n for n in nombres if apto(resultados[n])), key=lambda n: (resultados[n]["costo"], resultados[n]["latencia_mediana"]))
    lineas += ["", "## Ranking", "",
               "Criterios mínimos: precio publicado, al menos 90 % de peticiones respondidas, a lo sumo un error "
               "de clasificación y ninguna respuesta con datos inventados. Entre los que cumplen, se ordena por "
               "costo por mensaje y luego por latencia mediana.", ""]
    if aptos:
        for i, n in enumerate(aptos, start=1):
            r = resultados[n]
            lineas.append(f"{i}. `{n}`: {r['costo']:.6f} USD por mensaje, mediana {r['latencia_mediana']:.2f} s, "
                          f"{r['correctas']} de {r['evaluadas']} correctas")
    else:
        lineas.append("Ningún modelo cumplió todos los criterios en esta corrida.")
    lineas += ["", "## Modelos sin nivel gratuito (no probados, solo referencia de precio)", "",
               "| Modelo | Entrada (USD / 1M) | Salida (USD / 1M) |", "|---|---|---|"]
    for n, (e, s) in SOLO_PAGO.items():
        lineas.append(f"| `{n}` | {e:.2f} | {s:.2f} |")
    lineas += ["", "## Respuestas de cada modelo", ""]
    for n in nombres:
        lineas.append(f"### `{n}`")
        vistos = set()
        for r in resultados[n]["registros"]:
            if not r["ok"] or r["mensaje"] in vistos:
                continue
            vistos.add(r["mensaje"])
            marcas = ("" if r["correcta"] else " ❌ categoría") + (" ⚠️ inventa datos" if r["inventa"] else "") \
                + (" 📢 publicidad indebida" if r["promo_indebida"] else "")
            lineas.append(f"- **{r['mensaje']}** → {r['texto']}{marcas}")
        lineas.append("")
    return "\n".join(lineas)


def main():
    fecha = date.today().isoformat()
    resultados = {m: evaluar_modelo(m, p) for m, p in MODELOS.items()}
    markdown = generar_markdown(resultados, fecha)
    CARPETA_DOCS.mkdir(exist_ok=True)
    (CARPETA_DOCS / "comparacion_modelos.md").write_text(markdown, encoding="utf-8")
    (CARPETA_DOCS / "comparacion_modelos.json").write_text(
        json.dumps({"fecha": fecha, "resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n" + markdown)
    print("\nResultados guardados en docs/comparacion_modelos.md y docs/comparacion_modelos.json")


if __name__ == "__main__":
    main()
