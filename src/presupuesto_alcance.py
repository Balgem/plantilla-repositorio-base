"""Revisa si el alcance de la ficha cabe en las horas disponibles (Bloque 33).

Las horas son las que faltan (lo del Módulo 2 ya está hecho). Lo nuevo para mí (FastAPI, Docker) cuenta 1,5 veces.
Del total se reserva 30 % para pruebas y documentación y 20 % para imprevistos.

Uso:
    python3 src/presupuesto_alcance.py             con 30 horas disponibles
    python3 src/presupuesto_alcance.py --horas 20
"""
import argparse

FACTOR_NOVEDAD = 1.5
HORAS_DISPONIBLES = 30
RESERVA_PRUEBAS_DOCS = 0.30
MARGEN_IMPREVISTOS = 0.20
CAPAS_OBLIGATORIAS = {"api", "rag", "contenedor"}


def F(id_, horas, capa, nombre, tipo, novedad, sistema_real):
    return {"id": id_, "horas": horas, "capa": capa, "nombre": nombre, "tipo": tipo,
            "novedad": novedad, "sistema_real": sistema_real}


FUNCIONALIDADES = [
    F("RF-01", 3, "api", "Endpoint de consulta (JSON con respuesta, fuentes y trace_id)", "imprescindible", True, False),
    F("RF-02", 0.5, "rag", "Respuesta con fuente (ya existe: conectarla al endpoint)", "imprescindible", False, False),
    F("RF-03", 1, "otra", "Registro de interesados por la API (la herramienta ya existe)", "imprescindible", False, False),
    F("RF-05", 0.5, "otra", "Reporte con aprobación humana (ya existe: integrarlo)", "imprescindible", False, False),
    F("RF-10", 3, "api", "Links medibles: código por viewer + endpoint que registra y redirige", "imprescindible", False, False),
    F("RNF-03", 3, "contenedor", "Contenedor que levanta el servicio desde cero", "imprescindible", True, False),
    F("RF-04", 0.5, "otra", "Comentarios negativos (ya existe)", "deseable", False, False),
    F("RF-06", 0.5, "otra", "Bloqueo de intentos de inyección (ya existe)", "deseable", False, False),
    F("RF-07", 2, "otra", "Procesar un archivo de chat simulado de un stream", "deseable", False, False),
    F("RF-11", 4, "rag", "Varias campañas, cada una con sus documentos", "deseable", False, False),
    F("RF-08", 8, "otra", "Chat real de Twitch", "deseable", True, True),
    F("RF-09", 12, "otra", "Panel web en vivo", "deseable", True, False),
]


def horas_reales(f):
    return f["horas"] * (FACTOR_NOVEDAD if f["novedad"] else 1)


def presupuesto(horas=None):
    horas = HORAS_DISPONIBLES if horas is None else horas
    return round(horas * (1 - RESERVA_PRUEBAS_DOCS - MARGEN_IMPREVISTOS), 2)


def recortar(lista, horas=None):
    """Mete primero los imprescindibles, del más corto al más largo, y después los deseables.

    A diferencia de la versión de la lección, si un imprescindible no cabe no entra ningún deseable:
    las horas que sobran no se gastan en algo opcional mientras falte algo del MVP.
    """
    limite, usado = presupuesto(horas), 0.0
    dentro, fuera = [], []
    falta_imprescindible = False
    for f in sorted(lista, key=lambda f: (f["tipo"] != "imprescindible", horas_reales(f))):
        h = horas_reales(f)
        if f["sistema_real"]:
            fuera.append((f, "requiere datos o sistemas reales"))
        elif f["tipo"] == "deseable" and falta_imprescindible:
            fuera.append((f, "espera: falta cubrir un imprescindible"))
        elif usado + h <= limite:
            dentro.append(f)
            usado += h
        else:
            fuera.append((f, "no cabe en el presupuesto"))
            falta_imprescindible |= f["tipo"] == "imprescindible"
    return dentro, fuera, usado


def informe(lista, horas=None):
    pedido = sum(horas_reales(f) for f in lista)
    dentro, fuera, usado = recortar(lista, horas)
    neto = presupuesto(horas)
    print(f"Pedido: {pedido:.1f} h | Presupuesto: {neto:.1f} h netas de {horas or HORAS_DISPONIBLES} "
          f"({pedido / neto:.1f} veces lo disponible)")
    print(f"\nDENTRO DEL MVP ({usado:.1f} h):")
    for f in dentro:
        print(f"  {f['id']} {f['nombre']} [{f['capa']}, {horas_reales(f):.1f} h]")
    print("\nFUERA:")
    for f, motivo in fuera:
        print(f"  {f['id']} {f['nombre']} -> {motivo}")
    faltan = CAPAS_OBLIGATORIAS - {f["capa"] for f in dentro}
    if faltan:
        print("\nATENCION: capas obligatorias sin cubrir:", ", ".join(sorted(faltan)))
    else:
        print("\nLas tres capas obligatorias están cubiertas.")
    return dentro, fuera, usado


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horas", type=float, default=HORAS_DISPONIBLES, help="horas disponibles en el módulo")
    informe(FUNCIONALIDADES, parser.parse_args().horas)
