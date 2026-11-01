"""Convergencia multilente.

Distinto de la triangulacion entre modelos de IA (services/triangulacion.py):
ahi se contrasta como distintos modelos interpretan el MISMO conjunto de
hallazgos. Aca se contrasta cuando LENTES DISTINTAS -- que formulan preguntas
analiticas distintas -- senalan, cada una por su propia razon, el mismo punto
del reporte (mismo periodo, misma serie o las mismas filas). Es agrupacion
sobre evidencia ya estructurada, no un modelo nuevo: no vota ni promedia,
solo deja constancia de que varias preguntas independientes coincidieron en
el mismo locus, lo cual sube la prioridad de revision sin convertir la
coincidencia en certeza.

Dos salvaguardas contra falsa independencia:

1. Contexto del conciliador: corre sobre hallazgos que ya pasaron por
   aplicar_conciliador() (ver services/lentes/__init__.py), asi que un
   hallazgo del grupo puede ya tener limites.contexto_tecnico (severidad
   bajada, explicado como artefacto de carga). No se excluye del grupo --
   la convergencia en si sigue siendo informacion real -- pero se cuenta
   cuantos miembros del grupo ya fueron explicados tecnicamente, para que
   no se lea como "3 lentes confirman con fuerza total" cuando 1 de esas 3
   ya fue relativizada.
2. Pares con co-disparo esperado: algunas lentes comparten el mismo evento
   subyacente por construccion (p.ej. cronista y orquesta suelen reaccionar
   al mismo quiebre de serie: una lo ve como salto temporal, la otra como
   desacople de coherencia). Cuando el grupo son exactamente esas dos, se
   marca como convergencia "debil" -- se muestra igual, pero no se cuenta
   como evidencia tan independiente como una convergencia entre lentes sin
   relacion de construccion conocida.
"""
from __future__ import annotations

import re
from typing import Any

from services import perfilado

# Lentes cuyo co-disparo sobre el mismo periodo es esperable por construccion
# (mismo quiebre subyacente visto desde dos preguntas relacionadas), no
# evidencia de dos razones verdaderamente independientes.
PARES_CO_DISPARO_ESPERADO = (
    frozenset({"cronista", "orquesta"}),
)


_MESES_ES = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "set": 9,
    "septiembre": 9, "setiembre": 9, "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12,
}
_MES_ANIO_RE = re.compile(r"^([a-z]+)\.?\s+(\d{4})$")


def _normalizar_periodo(valor: Any) -> str:
    """cronista guarda el periodo como 'ago 2026' (services/lentes/cronista.py::_fmt_periodo_label);
    orquesta guarda el valor crudo de la columna temporal sin normalizar
    (services/lentes/orquesta.py::_periodo_texto). Sin esto, ambas formas
    del mismo periodo real no matchean como string y la convergencia nunca
    se detecta entre esas dos lentes, aunque corresponda. perfilado.fecha()
    no entiende "ago 2026" (solo formatos numericos y trimestre), asi que
    ese caso se resuelve aparte con el mismo mapa de meses que usa cronista."""
    texto = str(valor or "").strip()
    fecha = perfilado.fecha(texto)
    if fecha is not None:
        return f"{fecha.year:04d}-{fecha.month:02d}"
    m = _MES_ANIO_RE.match(texto.lower())
    if m:
        mes = _MESES_ES.get(m.group(1))
        if mes:
            return f"{m.group(2)}-{mes:02d}"
    return texto.lower()


def _locus_de(evidencia: dict[str, Any]) -> tuple[str, str] | None:
    filas = evidencia.get("filas")
    if isinstance(filas, list) and filas:
        return ("filas", str(sorted(set(filas))))
    serie = evidencia.get("serie")
    if serie:
        return ("serie", str(serie).strip().lower())
    periodo = evidencia.get("periodo")
    if periodo:
        return ("periodo", _normalizar_periodo(periodo))
    return None


def detectar_convergencia(hallazgos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grupos = {}
    for h in hallazgos:
        ev = h.get("evidencia") or {}
        clave = (ev.get("archivo_origen"), ev.get("hoja"), ev.get("bloque_excel"))
        grupos.setdefault(clave, []).append(h)
    return [c for grupo in grupos.values() for c in _detectar_convergencia_unidad(grupo)]


def _detectar_convergencia_unidad(hallazgos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa hallazgos (dicts con al menos "id", "lente", "descripcion",
    "evidencia", y opcionalmente "limites") por locus compartido. Devuelve
    solo los grupos donde convergen 2 o mas lentes distintas -- una misma
    lente con varios hallazgos sobre el mismo locus no cuenta como
    convergencia multilente."""
    grupos: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for h in hallazgos:
        locus = _locus_de(h.get("evidencia") or {})
        if locus is None:
            continue
        grupos.setdefault(locus, []).append(h)

    convergencias: list[dict[str, Any]] = []
    for (locus_tipo, locus_valor), grupo in grupos.items():
        lentes = sorted({str(h.get("lente")) for h in grupo if h.get("lente")})
        if len(lentes) < 2:
            continue

        con_contexto_tecnico = sum(
            1 for h in grupo if (h.get("limites") or {}).get("contexto_tecnico")
        )
        fuerza = "debil" if frozenset(lentes) in PARES_CO_DISPARO_ESPERADO else "fuerte"

        descripcion = (
            f"{len(lentes)} lentes distintas ({', '.join(lentes)}) señalan, cada una por su "
            f"propia pregunta analítica, el mismo {locus_tipo} ({locus_valor})."
        )
        if fuerza == "debil":
            descripcion += (
                " Estas dos lentes suelen reaccionar al mismo quiebre subyacente por construcción "
                "(coincidencia esperable, no dos razones totalmente independientes)."
            )
        else:
            descripcion += (
                " Son mecanismos distintos que señalan el mismo punto; su independencia requiere revisión. "
                "La coincidencia orienta la prioridad sin demostrar certeza ni causalidad."
            )
        if con_contexto_tecnico:
            descripcion += (
                f" {con_contexto_tecnico} de {len(grupo)} señales de este grupo ya fueron "
                "contextualizadas técnicamente por el conciliador (severidad reducida)."
            )

        convergencias.append({
            "locus_tipo": locus_tipo,
            "locus_valor": locus_valor,
            "lentes": lentes,
            "hallazgo_ids": [h.get("id") for h in grupo if h.get("id") is not None],
            "fuerza": fuerza,
            "tipo_convergencia": "co_disparo_esperado" if fuerza == "debil" else "mecanismos_distintos",
            "independencia_verificada": False,
            "produce_certeza": False,
            "con_contexto_tecnico": con_contexto_tecnico,
            "total_hallazgos": len(grupo),
            "descripcion": descripcion,
        })

    orden_prioridad = {"filas": 0, "serie": 1, "periodo": 2}
    convergencias.sort(key=lambda c: (
        0 if c["fuerza"] == "fuerte" else 1,
        orden_prioridad.get(str(c["locus_tipo"]), 9),
        -len(c["lentes"] if isinstance(c.get("lentes"), list) else []),
    ))
    return convergencias
