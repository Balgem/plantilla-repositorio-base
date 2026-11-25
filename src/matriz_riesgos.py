"""Matriz de riesgos del bot (Bloque 32). Genera docs/matriz_riesgos.md.

Los puntajes son del riesgo residual (con las mitigaciones actuales); también se muestra el inherente.

Uso:
    python3 src/matriz_riesgos.py
"""
from indexar_corpus import RAIZ

ARCHIVO_MATRIZ = RAIZ / "docs" / "matriz_riesgos.md"
ORDEN = ("BAJO", "MEDIO", "ALTO", "CRITICO")
CLAVES = ("riesgo", "probabilidad", "impacto", "mitigacion", "supervision", "estado_supervision", "inherente",
          "evidencia")


def puntaje_riesgo(probabilidad, impacto):
    return probabilidad * impacto


def categoria_riesgo(puntaje):
    if puntaje >= 15:
        return "CRITICO"
    if puntaje >= 9:
        return "ALTO"
    if puntaje >= 4:
        return "MEDIO"
    return "BAJO"


def _vecinos(p, i):
    return [(a, b) for a, b in [(p + 1, i), (p - 1, i), (p, i + 1), (p, i - 1)] if 1 <= a <= 5 and 1 <= b <= 5]


def esta_en_el_limite(probabilidad, impacto):
    """La de la lección: ¿un punto de diferencia en P o en I cambia la categoría?"""
    actual = categoria_riesgo(puntaje_riesgo(probabilidad, impacto))
    return any(categoria_riesgo(puntaje_riesgo(a, b)) != actual for a, b in _vecinos(probabilidad, impacto))


def rango_categoria(probabilidad, impacto) -> tuple[str, str]:
    """(categoría más baja, más alta) posibles si P o I se equivocan en un punto."""
    cats = {categoria_riesgo(puntaje_riesgo(a, b)) for a, b in [(probabilidad, impacto), *_vecinos(probabilidad, impacto)]}
    return min(cats, key=ORDEN.index), max(cats, key=ORDEN.index)


def le_faltaria_supervision(riesgo: dict) -> bool:
    """Con un punto de error en P o I, ¿quedaría ALTO o CRITICO sin ningún punto de supervisión?"""
    return ORDEN.index(rango_categoria(riesgo["probabilidad"], riesgo["impacto"])[1]) >= ORDEN.index("ALTO") \
        and not riesgo.get("supervision")


# P e I con el sistema actual; "inherente" es (P, I) sin las mitigaciones.
MIS_RIESGOS = [
    {"riesgo": 'El bot publica un dato inventado del K7 que el filtro no cubre',
     "probabilidad": 2, "impacto": 4, "inherente": (5, 4),
     "evidencia": 'Sin filtros, 3 de 3 corridas inventaron el link (Bloque 22)',
     "mitigacion": 'Cita obligatoria por frase (Bloque 26) y filtros de link y promesas (Bloques 22 y 31)',
     "supervision": 'Revisión posterior de lo que el filtro corrigió (logging_rag.py --revisar)', "estado_supervision": 'existe'},
    {"riesgo": 'Un viewer escribe instrucciones en el chat y el bot responde fuera del guion',
     "probabilidad": 3, "impacto": 4, "inherente": (4, 4),
     "evidencia": 'El detector se esquiva con sinónimos (probado en el Bloque 31)',
     "mitigacion": 'Detector de inyección antes del RAG y del agente, roles separados, filtros de salida y cita obligatoria (Bloque 31)',
     "supervision": 'Los intentos quedan marcados y se ven en la revisión del reporte antes de enviarlo', "estado_supervision": 'existe'},
    {"riesgo": 'Datos personales de viewers quedan en texto plano en logs o trazas',
     "probabilidad": 1, "impacto": 3, "inherente": (4, 3),
     "evidencia": 'Antes del Gate 2 las trazas guardaban nombres y mensajes',
     "mitigacion": 'Huellas HMAC y redacción en logs y trazas (privacidad.py); test_gate2.py lo comprueba',
     "supervision": 'Nada llega a la marca sin aprobación humana', "estado_supervision": 'existe'},
    {"riesgo": 'El agente marca como negativo a un viewer que no lo era y eso llega a la marca',
     "probabilidad": 3, "impacto": 3, "inherente": (3, 4),
     "evidencia": 'La diferencia entre criticar el producto y criticar el juego es ambigua (dataset del Bloque 29)',
     "mitigacion": 'Marcar no publica nada en el chat (Bloque 23)',
     "supervision": 'Una persona elige qué comentarios van al reporte antes de enviarlo', "estado_supervision": 'existe'},
    {"riesgo": 'Un cambio de prompt llega a producción sin registro ni revisión',
     "probabilidad": 2, "impacto": 4, "inherente": (3, 4),
     "evidencia": 'El cambio del prompt del agente en el Gate 2 entró sin aprobación y hubo que regularizarlo',
     "mitigacion": 'Registro de versiones de los dos prompts; el bot usa la versión activa (Bloque 32)',
     "supervision": 'Aprobación con grafo_supervision.py, mirando el diff', "estado_supervision": 'existe'},
    {"riesgo": 'La respuesta llega tarde (unos 9 s) y el chat ya cambió de tema',
     "probabilidad": 4, "impacto": 2, "inherente": (4, 2),
     "evidencia": 'Corridas reales del Bloque 31 y del Gate 2',
     "mitigacion": 'Latencia medida por etapa (Bloque 28); todavía no está optimizada',
     "supervision": '', "estado_supervision": 'no aplica'},
    {"riesgo": 'El precio o las condiciones cambian y el índice queda desactualizado',
     "probabilidad": 2, "impacto": 4, "inherente": (3, 4),
     "evidencia": 'El corpus son archivos .md que se editan a mano',
     "mitigacion": 'Actualización incremental del índice (Bloque 25) y evaluación de la recuperación (Bloque 27)',
     "supervision": '', "estado_supervision": 'no aplica'},
    {"riesgo": "El bot dice 'el contexto no menciona…' y el viewer no entiende",
     "probabilidad": 1, "impacto": 1, "inherente": (5, 1),
     "evidencia": 'Corrida real del Bloque 31',
     "mitigacion": 'Prompt v3 aprobado y activo (Bloque 32)',
     "supervision": '', "estado_supervision": 'no aplica'},
    {"riesgo": 'La API key se sube al repositorio público',
     "probabilidad": 1, "impacto": 5, "inherente": (3, 5),
     "evidencia": 'El repositorio es público',
     "mitigacion": '.env en .gitignore y revisión de git status antes de cada commit (Bloque 4)',
     "supervision": '', "estado_supervision": 'no aplica'},
    {"riesgo": 'Un documento del corpus trae instrucciones escondidas',
     "probabilidad": 1, "impacto": 4, "inherente": (1, 4),
     "evidencia": 'Hoy el corpus lo escribe solo la marca',
     "mitigacion": 'Filtro de chunks sospechosos y contexto delimitado (Bloque 31)',
     "supervision": '', "estado_supervision": 'no aplica'},
    {"riesgo": 'Se descartan todos los chunks y el modelo responde sin respaldo',
     "probabilidad": 1, "impacto": 4, "inherente": (2, 4),
     "evidencia": 'Pasó en el ensayo del Gate 2 antes de corregirlo',
     "mitigacion": 'Sin chunks limpios no se llama al modelo (ensayo del Gate 2)',
     "supervision": '', "estado_supervision": 'no aplica'},
    {"riesgo": 'Un pico de mensajes dispara el gasto en la API',
     "probabilidad": 2, "impacto": 1, "inherente": (2, 1),
     "evidencia": 'Unos 0,13 USD por 1.000 respuestas (Bloque 28)',
     "mitigacion": 'Costo medido por consulta (Bloque 28) y reintentos con backoff (Bloques 12 y 13)',
     "supervision": '', "estado_supervision": 'no aplica'},
]


def completar(riesgos: list[dict]) -> list[dict]:
    for r in riesgos:
        r["puntaje"] = puntaje_riesgo(r["probabilidad"], r["impacto"])
        r["categoria"] = categoria_riesgo(r["puntaje"])
        r["al_limite"] = esta_en_el_limite(r["probabilidad"], r["impacto"])
        r["rango"] = rango_categoria(r["probabilidad"], r["impacto"])
        r["revisar"] = le_faltaria_supervision(r)
        if r.get("inherente"):
            r["categoria_inherente"] = categoria_riesgo(puntaje_riesgo(*r["inherente"]))
    return riesgos


def validar_matriz(riesgos: list[dict]) -> list[str]:
    """Lo que la actividad exige que se cumpla siempre, más los errores de tipo de la lección."""
    problemas = []
    for n, r in enumerate(riesgos):
        faltan = [c for c in ("riesgo", "probabilidad", "impacto", "mitigacion") if c not in r]
        if faltan:
            problemas.append(f"fila {n}: faltan las claves {faltan}")
            continue
        for campo in ("probabilidad", "impacto"):
            if not isinstance(r[campo], int) or isinstance(r[campo], bool) or not 1 <= r[campo] <= 5:
                problemas.append(f"fila {n}: {campo} tiene que ser un entero de 1 a 5, no {r[campo]!r}")
        if len(r["riesgo"].split()) < 5:
            problemas.append(f"fila {n}: riesgo demasiado genérico: {r['riesgo']!r}")
    if problemas:
        return problemas
    completar(riesgos)
    if len(riesgos) < 5:
        problemas.append(f"hay {len(riesgos)} riesgos, se piden al menos 5")
    for r in riesgos:
        if r["categoria"] in ("ALTO", "CRITICO") and not r.get("supervision"):
            problemas.append(f"{r['categoria']} sin punto de supervisión: {r['riesgo']}")
    if sum("Bloque" in r["mitigacion"] for r in riesgos) < 2:
        problemas.append("menos de 2 mitigaciones apuntan a algo construido (con su número de bloque)")
    if not any(r["categoria"] in ("ALTO", "CRITICO") for r in riesgos):
        problemas.append("ningún riesgo ALTO o CRITICO: revisa si estás subestimando P o I")
    if len({r["categoria"] for r in riesgos}) == 1:
        problemas.append("todos los riesgos en la misma categoría: puntúa cada fila por separado")
    return problemas


def ordenados(riesgos):
    return sorted(riesgos, key=lambda r: (-r["puntaje"], -r["impacto"]))  # a igual puntaje, primero el más grave


def a_markdown(riesgos: list[dict]) -> str:
    lineas = [
        "# Matriz de riesgos del bot",
        "",
        "Generada con `python3 src/matriz_riesgos.py`. Puntaje = probabilidad × impacto (1 a 5). "
        "CRÍTICO ≥ 15, ALTO ≥ 9, MEDIO ≥ 4, BAJO < 4. P e I son del riesgo actual, con las mitigaciones ya "
        "construidas; la columna Inherente es la categoría sin ellas. Rango es la categoría si P o I cambian en un "
        "punto (⚠️: quedaría ALTO sin supervisión).",
        "",
        "| # | Riesgo | P | I | Puntaje | Categoría | Inherente | Rango | Mitigación | Supervisión |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(ordenados(riesgos), start=1):
        rango = r["rango"][0] if r["rango"][0] == r["rango"][1] else f"{r['rango'][0]}..{r['rango'][1]}"
        lineas.append(f"| {n} | {r['riesgo']} | {r['probabilidad']} | {r['impacto']} | {r['puntaje']} | "
                      f"{r['categoria']} | {r.get('categoria_inherente', '—')} | "
                      f"{rango}{' ⚠️' if r['revisar'] else ''} | {r['mitigacion']} | {r['supervision'] or '—'} |")
    lineas += ["", "## Evidencia", ""]
    lineas += [f"{n}. {r['evidencia']}." for n, r in enumerate(ordenados(riesgos), start=1)]
    lineas += ["", "## Para revisar con otra persona", ""]
    lineas += [f"- {r['riesgo']}" for r in ordenados(riesgos) if r["revisar"]]
    return "\n".join(lineas) + "\n"


if __name__ == "__main__":
    riesgos = completar(MIS_RIESGOS)
    print("Mi matriz de riesgos (residual, ordenada por puntaje)\n")
    for r in ordenados(riesgos):
        marca = " [AL LIMITE]" if r["al_limite"] else ""
        print(f"{r['categoria']:8} ({r['puntaje']:2}) - {r['riesgo'][:85]}{marca}")

    print("\nRevisar con otra persona (con un punto de error quedarían ALTO sin supervisión):")
    for r in ordenados(riesgos):
        if r["revisar"]:
            print(f"  {r['rango'][0]}..{r['rango'][1]:8} {r['riesgo'][:85]}")
    print(f"\n(esta_en_el_limite marca {sum(r['al_limite'] for r in riesgos)} de {len(riesgos)} filas: casi todo, "
          "por eso el criterio de arriba es más útil)")

    problemas = validar_matriz(riesgos)
    print("\nValidación:", "OK" if not problemas else "")
    for p in problemas:
        print(" -", p)
    ARCHIVO_MATRIZ.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO_MATRIZ.write_text(a_markdown(riesgos), encoding="utf-8")
    print(f"Matriz escrita en {ARCHIVO_MATRIZ.relative_to(RAIZ)}")
    raise SystemExit(1 if problemas else 0)
