"""Capa de enrutamiento institucional.

Una vez que la persona responsable decide escalar un hallazgo, esta capa
vincula la señal con la unidad competente y produce un documento de contexto.
El sistema no interviene sobre unidades ni acusa: formula una pregunta trazable
para que la unidad explique, corrija o documente el criterio utilizado.
No evalúa orientaciones políticas, partidos ni decisiones de oportunidad institucional.
"""
from __future__ import annotations

import datetime

import models


def _pregunta_sugerida(h: models.Hallazgo) -> str:
    if h.pregunta_institucional:
        return h.pregunta_institucional
    preguntas = {
        "conciliador": "¿La señal se explica por carga, acumulación, reclasificación, corte de período o criterio de publicación?",
        "ajedrecista": "¿Qué regla interna, fórmula, total o restricción formal explica la señal marcada?",
        "cronista": "¿Qué ocurrió en el período bisagra señalado y cómo debe documentarse?",
        "orquesta": "¿Por qué las variables involucradas dejaron de moverse de manera coherente?",
        "radiologo": "¿La semejanza con antecedentes comparables es esperable o requiere revisión específica?",
        "rizoma": "¿La asociación detectada tiene explicación institucional o queda como hipótesis en seguimiento?",
        "matematico": "¿El método de cálculo corresponde al tipo de informe o requiere ponderadores/denominadores alternativos?",
    }
    return preguntas.get(h.lente, "¿Qué contexto documentado explica la señal marcada?")


def _cuerpo(informe: models.Informe, area_origen: models.Area, area_destino: models.Area,
            hallazgos: list[models.Hallazgo], comentario: str | None, decidido_por: str | None) -> str:
    fecha = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
    lineas = [
        f"INFORME DE CONTEXTO — {fecha}",
        f"Unidad que produjo el insumo: {area_origen.nombre} ({area_origen.codigo})",
        f"Unidad destinataria: {area_destino.nombre} ({area_destino.codigo})",
        f"Período analizado: {informe.periodo} — dominio: {informe.dominio}",
        "",
        "Este documento no es un señalamiento de auditoría, no atribuye "
        "responsabilidades y no evalúa ideologías, partidos ni "
        "decisiones de oportunidad institucional. Surge de un barrido asistido por IA sobre "
        "información agregada, revisado y escalado por la persona responsable "
        "de decisión, con el pedido de que la unidad destinataria revise, "
        "amplíe o explique lo señalado.",
        "",
        "Señales escaladas y pregunta sugerida:",
    ]
    for h in hallazgos:
        lineas.append(f"- [{h.lente}/{h.modo or '-'}] {h.descripcion} (severidad: {h.severidad})")
        lineas.append(f"  Pregunta para revisar: {_pregunta_sugerida(h)}")

    if comentario:
        lineas += ["", f"Comentario de quien decidió escalar: {comentario}"]
    if decidido_por:
        lineas += ["", f"Decisión tomada por: {decidido_por}"]

    lineas += [
        "",
        "Esta devolución no exige una intervención predeterminada: se pide "
        "revisión y, si corresponde, una explicación trazable.",
    ]
    return "\n".join(lineas)


def generar_documentos(
    informe: models.Informe,
    hallazgos: list[models.Hallazgo],
    areas_destino: list[models.Area],
    comentario: str | None,
    decidido_por: str | None,
) -> list[dict]:
    """Devuelve, sin persistir, un documento por cada unidad destino."""
    destinos = areas_destino or [informe.area]
    return [
        {
            "area_destino_id": area.id,
            "contenido": _cuerpo(informe, informe.area, area, hallazgos, comentario, decidido_por),
        }
        for area in destinos
    ]
