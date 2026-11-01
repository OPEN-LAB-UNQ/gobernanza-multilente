"""Orden reproducible y agrupación de contexto; el detalle nunca se elimina."""

from collections import defaultdict
from copy import deepcopy

from services import plural
from services.lectura_temporal import anual, campo


def clave(h):
    ev = campo(h, "evidencia", {}) or {}
    contexto = anual(h) or ev.get("naturaleza") == "contexto"
    return (
        contexto,
        -float(ev.get("puntaje_prioridad", {"alta": 80, "media": 50, "baja": 20}.get(campo(h, "severidad"), 0))),
        str(ev.get("hoja", "")),
        str(ev.get("celda", "")),
        str(campo(h, "id", "")),
    )


def consolidar_contexto(hallazgos):
    otros = []
    grupos = defaultdict(list)
    for h in hallazgos:
        if anual(h):
            ev = h.get("evidencia") or {}
            grupos[(ev.get("archivo_origen"), str(ev.get("periodo", "sin período")))].append(h)
        else:
            otros.append(h)
    for (archivo, periodo), hs in sorted(grupos.items(), key=lambda x: str(x[0])):
        hojas = sorted({h["evidencia"].get("hoja", "") for h in hs})
        otros.append(
            dict(
                lente="cronista",
                modo="contexto_agrupado",
                severidad="media",
                descripcion=(f"{periodo}: {plural.contar(len(hs), 'variación anual', 'variaciones anuales')} "
                             f"en {plural.contar(len(hojas), 'hoja')}. Revisar inflación, cobertura y metodología del período; "
                             "no equivalen a errores confirmados. El detalle original queda disponible."),
                evidencia=dict(
                    naturaleza="contexto",
                    regla="contexto_compartido_periodo",
                    requiere_contexto_anual=True,
                    archivo_origen=archivo,
                    periodo=periodo,
                    hojas=hojas,
                    cantidad_senales_originales=len(hs),
                    puntaje_prioridad=0,
                    detalle_contexto=deepcopy(hs),
                    ubicaciones_excel=list(
                        dict.fromkeys(u for h in hs for u in h["evidencia"].get("ubicaciones_excel", []))
                    ),
                ),
            )
        )
    return sorted(otros, key=clave)


def portada(hallazgos):
    controles = [
        h
        for h in sorted(hallazgos, key=clave)
        if not anual(h) and (campo(h, "evidencia", {}) or {}).get("naturaleza") != "contexto"
    ]
    return controles[:20]


def lineas_markdown(hallazgos):
    seleccion = portada(hallazgos)
    if not any((campo(h, "evidencia", {}) or {}).get("puntaje_prioridad") is not None for h in seleccion):
        return []
    lineas = [
        "## Hallazgos de control priorizados",
        "",
        "Hasta 20 resultados, ordenados por reglas, magnitud relativa y corroboración. El puntaje no depende del importe absoluto.",
        "",
    ]
    for i, h in enumerate(seleccion, 1):
        ev = campo(h, "evidencia", {}) or {}
        lineas.append(
            f"{i}. **{campo(h, 'severidad', 'media').upper()} · {ev.get('puntaje_prioridad', '-')} puntos:** {campo(h, 'descripcion', '')}"
        )
    return lineas + ["", "El resto de los controles y el contexto temporal se conservan en el detalle.", ""]
