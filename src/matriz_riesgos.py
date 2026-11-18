"""Matriz de riesgos del bot de la campaña K7 (Bloque 32, paso 3).

Uso, desde la raíz del repositorio (solo librería estándar, no llama a la API):
    python3 src/matriz_riesgos.py      # imprime la matriz y escribe docs/matriz_riesgos.md

Decisiones que la lección deja abiertas:
- Se puntúa el riesgo RESIDUAL (con lo que ya está construido) y se muestra también el INHERENTE (sin esas
  mitigaciones), para que se vea cuánto aporta cada una. Se prioriza por el residual.
- Además de "[AL LIMITE]" (que marca 21 de las 25 celdas posibles, y aquí 11 de 11 filas), cada fila muestra
  el RANGO de categorías si P o I se equivocan en un punto. Para decidir qué revisar con otra persona se usa
  una pregunta más útil: con un punto de error, ¿esta fila quedaría ALTO SIN punto de supervisión? Ahí un
  error de estimación sí cambia lo que hay que construir.
- "supervision" y "estado_supervision" van en la fila (la lección los deja fuera del código): así
  validar_matriz() puede comprobar la regla "todo ALTO o CRITICO tiene un punto de supervisión".
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


# Riesgos que YA aparecieron construyendo este bot (con su evidencia), no ejemplos copiados de la lección.
# P e I se puntúan con el sistema como está HOY; "inherente" es (P, I) sin las mitigaciones listadas.
MIS_RIESGOS = [
    {"riesgo": "El bot publica en el chat un dato inventado del K7 que el filtro de salida no cubre "
               "(p. ej. 'tiene bluetooth' o 'llega mañana')",
     "probabilidad": 3, "impacto": 4, "inherente": (5, 4),
     "evidencia": "Sin filtros, 3 de 3 corridas inventaron el link (Bloque 22); el filtro solo conoce links y promesas de una lista",
     "mitigacion": "RAG con citas numeradas y revisar_citas (Bloque 26), el bot admite no saber (Bloque 27), "
                   "corregir_links + filtrar_salida (Bloques 22 y 31)",
     "supervision": "Revisión post-stream de lo que el filtro corrigió (logging_rag.py --revisar, Bloque 32) y de las "
                    "trazas respuesta_modelo vs respuesta_final (revisar_trazas, Bloque 23); todo cambio de prompt pasa "
                    "por grafo_supervision.py (Bloque 32)",
     "estado_supervision": "existe"},
    {"riesgo": "Un viewer escribe instrucciones en el chat público y el bot responde fuera del guion "
               "(insulta, habla de otra marca o revela sus instrucciones)",
     "probabilidad": 3, "impacto": 4, "inherente": (4, 4),
     "evidencia": "El detector se esquiva con sinónimos o separando letras (probado en el Bloque 31)",
     "mitigacion": "Detector de inyección sobre la pregunta, que corta antes del retriever y del modelo; roles "
                   "separados; filtrar_salida sobre lo que el modelo responda (Bloque 31)",
     "supervision": "Cada intento detectado queda en el log con su trace_id y se revisa post-stream "
                    "(logging_rag.py --revisar, Bloque 32). Falta: marcar al viewer en el reporte de la marca (Gate 2)",
     "estado_supervision": "parcial"},
    {"riesgo": "Los nombres y mensajes de viewers quedan en claro en trazas_agente.jsonl y en el reporte para la marca",
     "probabilidad": 3, "impacto": 3, "inherente": (4, 3),
     "evidencia": "trazas.py guarda nombre y mensaje; solo logging_rag.py usa huellas (Bloque 31)",
     "mitigacion": "Archivos con datos de viewers en .gitignore (Bloque 23); el log del RAG guarda huella y largo, "
                   "nunca el texto (Bloque 31)",
     "supervision": "Ningún comentario ni nombre llega a la marca sin aprobación humana, uno por uno y del envío "
                    "(reporte_marca.py, Bloque 23)",
     "estado_supervision": "existe"},
    {"riesgo": "El agente marca como comentario negativo a un viewer que no lo era y su nombre llega a la marca",
     "probabilidad": 3, "impacto": 3, "inherente": (3, 4),
     "evidencia": "La frontera crítica al juego/streamer vs. al producto es ambigua (dataset del Bloque 29)",
     "mitigacion": "marcar_comentario_negativo es riesgo medio y no publica nada en el chat (Bloque 23)",
     "supervision": "Aprobación humana de cada comentario marcado antes del reporte (supervision.py, Bloque 23)",
     "estado_supervision": "existe"},
    {"riesgo": "Un cambio del prompt de sistema llega a producción sin registro ni revisión",
     "probabilidad": 2, "impacto": 4, "inherente": (3, 4),
     "evidencia": "Hasta el Bloque 31 el prompt era un string suelto en el código",
     "mitigacion": "Registro de versiones con huella; el bot lee el prompt activo del registro y deja su huella en "
                   "cada consulta del log (Bloque 32)",
     "supervision": "grafo_supervision.py: interrupt con el diff, aprobación con thread_id único y checkpointer "
                    "durable (Bloque 32)",
     "estado_supervision": "existe"},
    {"riesgo": "La respuesta llega unos 9 s después y el chat ya cambió de tema",
     "probabilidad": 4, "impacto": 2, "inherente": (4, 2),
     "evidencia": "Corrida real del Bloque 31: ~9 s de generación por respuesta",
     "mitigacion": "Latencia medida por etapa: la generación es el 77 % del tiempo (Bloque 28); trace_id para "
                   "encontrar las lentas (Bloque 31). Mide, todavía no acelera",
     "supervision": "", "estado_supervision": "no aplica"},
    {"riesgo": "El precio o las condiciones de la campaña cambian y el índice sigue con la versión vieja",
     "probabilidad": 2, "impacto": 4, "inherente": (3, 4),
     "evidencia": "El corpus está en archivos .md que se editan a mano",
     "mitigacion": "indexar_corpus.py borra la colección y reindexa con ids explícitos (Bloques 24 y 25); el "
                   "conjunto de evaluación detecta recuperaciones rotas (Bloque 27)",
     "supervision": "", "estado_supervision": "no aplica"},
    {"riesgo": "El bot dice 'el contexto no menciona…' y el viewer no entiende qué es 'el contexto'",
     "probabilidad": 5, "impacto": 1, "inherente": (5, 1),
     "evidencia": "Corrida real del Bloque 31 ('¿cuánto pesa el teclado?')",
     "mitigacion": "Versión 3 del prompt propuesta en el registro, pendiente de aprobación (Bloque 32)",
     "supervision": "", "estado_supervision": "no aplica"},
    {"riesgo": "La API key se sube al repositorio público",
     "probabilidad": 1, "impacto": 5, "inherente": (3, 5),
     "evidencia": "El repositorio es público",
     "mitigacion": ".env en .gitignore desde el Bloque 4 y revisión de git status antes de cada commit",
     "supervision": "", "estado_supervision": "no aplica"},
    {"riesgo": "Un documento del corpus trae instrucciones escondidas (inyección indirecta)",
     "probabilidad": 1, "impacto": 4, "inherente": (1, 4),
     "evidencia": "Hoy el corpus lo escribe solo la marca; sube si algún día se indexan comentarios o FAQ de usuarios",
     "mitigacion": "Filtro de chunks sospechosos, <contexto> declarado como dato y roles separados (Bloque 31)",
     "supervision": "", "estado_supervision": "no aplica"},
    {"riesgo": "Un pico de mensajes en el chat dispara el gasto en la API",
     "probabilidad": 2, "impacto": 1, "inherente": (2, 1),
     "evidencia": "Costo real ≈ 0,13 USD por 1.000 respuestas (Bloque 28)",
     "mitigacion": "Costo medido por consulta (Bloques 28 y 31); reintentos con backoff, no en bucle (Bloques 12 y 13)",
     "supervision": "", "estado_supervision": "no aplica"},
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
        "# Matriz de riesgos del bot de la campaña K7",
        "",
        "Generada con `python3 src/matriz_riesgos.py` (Bloque 32). Puntaje = probabilidad × impacto (1 a 5 cada uno); "
        "CRÍTICO ≥ 15, ALTO ≥ 9, MEDIO ≥ 4, BAJO < 4. **P e I son del riesgo residual** (con lo ya construido); "
        "*inherente* es la categoría sin esas mitigaciones. *Rango* es la categoría posible si P o I se equivocan "
        "en un punto: ⚠️ marca las filas que con ese error quedarían ALTO **sin** punto de supervisión.",
        "",
        "| # | Riesgo | P | I | Puntaje | Categoría | Inherente | Rango | Mitigación | Punto de supervisión |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(ordenados(riesgos), start=1):
        rango = r["rango"][0] if r["rango"][0] == r["rango"][1] else f"{r['rango'][0]}..{r['rango'][1]}"
        supervision = r["supervision"] or "—"
        if r["estado_supervision"] == "parcial":
            supervision = f"**Parcial.** {supervision}"
        lineas.append(f"| {n} | {r['riesgo']} | {r['probabilidad']} | {r['impacto']} | {r['puntaje']} | "
                      f"**{r['categoria']}** | {r.get('categoria_inherente', '—')} | "
                      f"{rango}{' ⚠️' if r['revisar'] else ''} | {r['mitigacion']} | {supervision} |")
    lineas += ["", "## Evidencia de cada riesgo", ""]
    lineas += [f"{n}. **{r['riesgo']}**: {r['evidencia']}." for n, r in enumerate(ordenados(riesgos), start=1)]
    lineas += [
        "",
        "## Para revisar con otra persona",
        "",
        *[f"- {r['riesgo']} ({r['categoria']}, rango {r['rango'][0]}..{r['rango'][1]})"
          for r in ordenados(riesgos) if r["revisar"]],
        "",
        "## Lectura",
        "",
        "- Ningún riesgo queda CRÍTICO con lo ya construido, pero dos lo eran sin mitigar (datos inventados e inyección "
        "desde el chat): por eso siguen en ALTO y con revisión humana.",
        "- Las respuestas en vivo no se aprueban una por una (no escala y llegarían tarde): su supervisión es la "
        "revisión post-stream de lo que el filtro frenó o corrigió, y la aprobación de cada cambio de prompt.",
        "- Riesgos con el mismo puntaje no son igual de urgentes: la API key (1×5) es rara y grave; el 'no sé' con "
        "jerga (5×1) es frecuente y leve.",
    ]
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
