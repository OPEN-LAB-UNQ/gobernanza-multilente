"""Tipos simples y evidencia común; ninguna regla depende de archivos o coordenadas."""

import math
import re
import unicodedata
from statistics import median

from services.perfilado import numero as numero_perfilado


def numero(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        n = numero_perfilado(v)
        return n if n is not None and math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def normalizar(v):
    return (
        re.sub(
            r"\s+", " ", "".join(c for c in unicodedata.normalize("NFKD", str(v or "")) if not unicodedata.combining(c))
        )
        .strip()
        .lower()
    )


def mad(vs):
    m = median(vs)
    return median(abs(v - m) for v in vs)


def es_numero(valor, decimales=2):
    """Números como se escriben acá: punto para los miles y coma para los decimales."""
    return f"{valor:,.{decimales}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def es_porcentaje(valor, decimales=2):
    return es_numero(valor * 100, decimales) + " %"


def referencia(s, i):
    return f"{s['hoja']}!{s['celdas'][i]}"


def hallazgo(s, i, regla, detalle, puntos, calculo=None, participantes=None, accion=None, lente="ajedrecista"):
    accion = accion or "Contrastar la celda con la fuente y documentar la corrección o la explicación."
    ev = dict(
        archivo_origen=s["archivo"],
        hoja=s["hoja"],
        bloque_excel=s["cuadro"],
        celda=s["celdas"][i],
        indicador=s["etiqueta"],
        periodo=s["periodos"][i],
        valor_observado=s["valores"][i],
        regla=regla,
        naturaleza="control",
        puntaje_prioridad=puntos,
        factores_prioridad=[{"criterio": regla, "puntos": puntos}],
        ubicaciones_excel=[referencia(s, i)],
        celdas_participantes=participantes or [referencia(s, i)],
        accion_revision=accion,
        **(calculo or {}),
    )
    return dict(
        lente=lente,
        modo="control_tabular",
        severidad="alta" if puntos >= 80 else "media",
        descripcion=f"{referencia(s, i)} · {s['etiqueta']} · {s['periodos'][i]}: {detalle} {accion}",
        pregunta_institucional=accion,
        metodo="Control tabular reproducible; relación y cálculos documentados en evidencia",
        evidencia=ev,
    )
