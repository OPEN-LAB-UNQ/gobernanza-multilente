"""Observaciones independientes y eje temporal verificable para asociaciones.

No modifica los datos fuente: los totales permanecen disponibles para conciliación.
"""
import re

from services import perfilado
from services.controles_excel.periodos import FRECUENCIA, leer
from services.lentes.util import columna_etiqueta_fila

TOTAL = re.compile(r"^(?:suma\s+total|total(?:es)?|sub\s*total(?:es)?|suma)(?:\b|_)", re.I)


def sin_agregados(datos):
    etiqueta = columna_etiqueta_fila(datos)
    if not etiqueta:
        return list(datos), 0
    salida = [f for f in datos if not TOTAL.match(str(f.get(etiqueta) or "").strip())]
    return salida, len(datos) - len(salida)


def eje_temporal(datos, interpretacion=None):
    """Sólo series en filas con períodos únicos, completos y de una frecuencia.

    Una confirmación explícita prevalece sobre la inferencia por perfilado.
    Sin períodos consecutivos se conserva la asociación, pero no las diferencias.
    """
    if not datos:
        return None
    if interpretacion is not None and interpretacion.get("eje") not in {"serie_filas", "no_determinado"}:
        return None
    roles = (interpretacion or {}).get("roles", {})
    candidatas = [c for c, r in roles.items() if r == "periodo_serie"]
    if not candidatas and not roles:
        candidatas = [p["name"] for p in perfilado.perfilar(datos) if p.get("role") == "temporal"]
    for columna in candidatas:
        periodos = [leer(f.get(columna)) for f in datos]
        if not all(p and p.get("anio") is not None for p in periodos):
            continue
        if len({p["frecuencia"] for p in periodos}) != 1:
            continue
        claves = [(p["anio"], p["sub"]) for p in periodos]
        if len(set(claves)) != len(claves):
            continue
        orden = sorted(range(len(datos)), key=claves.__getitem__)
        frecuencia = FRECUENCIA.get(periodos[0]["frecuencia"])
        if not frecuencia:
            continue
        ordinales = [periodos[i]["anio"] * frecuencia + periodos[i]["sub"] for i in orden]
        if any(b - a != 1 for a, b in zip(ordinales, ordinales[1:])):
            continue
        return columna, orden
    return None
