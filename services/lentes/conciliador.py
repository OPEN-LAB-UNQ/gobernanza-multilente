"""Conciliador: capa transversal de contextualizacion tecnica.

No es una lente sustantiva mas: corre despues de las seis lentes sustantivas
y revisa si sus hallazgos pueden explicarse por como fue cargado, acumulado,
recortado, clasificado o publicado el dato (aperturas con credito cero, series
acumuladas reexpresadas, reversas mensuales o mezcla de niveles de agregacion).

Cuando encuentra ese solapamiento, no produce una alarma nueva y paralela:
adjunta el contexto tecnico al hallazgo existente y le baja la severidad un
escalon (queda registrado en limites.contexto_tecnico, nunca se descarta en
silencio). Solo cuando detecta artefactos sin poder emparejarlos con un
hallazgo puntual, cae a una advertencia propia -- exactamente igual que antes.
Sin artefacto técnico no modula nada: una imposibilidad presupuestaria sin pistas
conserva su severidad, y en el ámbito «organizacion» no se usa el vocabulario del
presupuesto público para emparejar.
"""
from __future__ import annotations

import re
from typing import Any

from services import ambito, perfilado, plural, sanitizacion

from .util import columnas_numericas, etiquetas_filas, valor_numero

PERIODO_RE = re.compile(r"periodo|mes|fecha|anio|año|trimestre", re.I)
COBERTURA_RE = re.compile(r"relevamiento\s+desde|a\s+partir\s+de|cambio\s+de\s+(?:cobertura|serie|criterio)|inicio\s+de\s+serie|cobertura|corte\s+(?:temporal|de\s+carga|de\s+informaci[oó]n)|cierre\s+(?:parcial|provisorio)|dato\s+preliminar|carga\s+parcial|actualizaci[oó]n\s+posterior|desde\s+(?:ene|enero|feb|febrero|mar|marzo|abr|abril|may|mayo|jun|junio|jul|julio|ago|agosto|sep|septiembre|oct|octubre|nov|noviembre|dic|diciembre|(?:19|20)\d{2})", re.I)
REVERSA_OPERATIVA_RE = re.compile(r"\bmes\b|mensual|movimiento|comprometido|devengado|pagado", re.I)
# Columnas de notas, observaciones o comentarios: texto libre escrito a mano, donde suelen
# quedar nombres, teléfonos o correos. De ahí no se copia el texto, sólo dónde está la nota.
COLUMNA_NOTAS_RE = re.compile(
    r"(?<![a-z])(?:observ\w*|obs|notas?|comentarios?|aclaraci\w*|detalles?|motivos?|justificaci\w*)(?![a-z])"
)
VARIACION_PERIODICA_RE = re.compile(r"variacion.*(?:\bmes\b|mensual|intermensual|periodo|periodic)|(?:\bmes\b|mensual|intermensual|periodo|periodic).*variacion", re.I)


def _periodo_col(datos: list[dict[str, Any]]) -> str | None:
    if not datos:
        return None
    columnas = list(datos[0].keys())
    preferidas = ["periodo", "fecha", "mes", "anio", "año"]
    for preferida in preferidas:
        for col in columnas:
            if perfilado.normalizar_texto(col) == preferida:
                return col
    for col in columnas:
        if PERIODO_RE.search(col):
            return col
    perfiles = perfilado.perfilar(datos)
    temporales = perfilado.columnas_temporales(perfiles)
    return temporales[0] if temporales else None


def _serie(datos: list[dict[str, Any]], col: str) -> list[float]:
    return [valor_numero(f.get(col)) or 0.0 for f in datos]


def _nombre_columnas_presupuesto(datos: list[dict[str, Any]]) -> dict[str, str]:
    # Crédito cero, reversas y ratios ejecución/crédito son del presupuesto público.
    if ambito.es_organizacion():
        return {}
    perfiles = perfilado.perfilar(datos)
    return perfilado.columnas_etapas_presupuesto(perfiles)

def _pistas_cobertura(datos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    columnas = sorted({c for fila in datos for c in fila.keys()})
    pistas: list[dict[str, Any]] = []
    for col in columnas:
        if COBERTURA_RE.search(perfilado.normalizar_texto(col)):
            pistas.append({"tipo": "columna", "detalle": col})
    for idx, fila in enumerate(datos[:40]):
        for col, valor in fila.items():
            if valor is None:
                continue
            texto = str(valor).strip()
            if len(texto) < 8 or len(texto) > 240:
                continue
            if COBERTURA_RE.search(perfilado.normalizar_texto(texto)):
                pistas.append({"tipo": "valor", "columna": col, "fila": idx, "fila_detalle": etiquetas_filas(datos, [idx], 1)[0], "detalle": _detalle_nota(col, texto, idx)})
    return pistas[:8]


def _columna_de_notas_o_persona(col: str) -> bool:
    nombre = perfilado.normalizar_texto(col)
    return bool(
        COLUMNA_NOTAS_RE.search(nombre)
        or sanitizacion.COLUMNA_PERSONA_RE.search(str(col))
        or sanitizacion.columna_sensible(str(col))
    )


def _detalle_nota(col: str, texto: str, idx: int) -> str:
    """Lo que viaja a la evidencia (y de ahí al prompt de los modelos) de una nota de cobertura.

    De una columna de notas, observaciones o personas no se copia el texto: sólo dónde está.
    En cualquier otra columna se copia saneado (DNI, CUIT, correos, teléfonos, expedientes).
    """
    if _columna_de_notas_o_persona(col):
        return f"nota de cobertura en la fila {idx + 1}"
    return sanitizacion.redactar_texto_libre(texto)[:180]


def _filas_credito_cero_con_ejecucion(datos: list[dict[str, Any]], etapas: dict[str, str]) -> list[int]:
    vigente = etapas.get("credito_vigente")
    dev = etapas.get("devengado")
    pag = etapas.get("pagado")
    if not vigente or not (dev or pag):
        return []
    filas = []
    for i, fila in enumerate(datos):
        v = valor_numero(fila.get(vigente))
        d = valor_numero(fila.get(dev)) if dev else None
        p = valor_numero(fila.get(pag)) if pag else None
        if v is not None and abs(v) <= 0.001 and ((d or 0) > 0 or (p or 0) > 0):
            filas.append(i)
    return filas


def _es_columna_reversa_operativa(nombre_normalizado: str) -> bool:
    if REVERSA_OPERATIVA_RE.search(nombre_normalizado):
        return True
    return bool(VARIACION_PERIODICA_RE.search(nombre_normalizado))


def _columnas_con_reversas(datos: list[dict[str, Any]], numericas: list[str]) -> list[dict]:
    reversas = []
    for col in numericas:
        n = perfilado.normalizar_texto(col)
        if not _es_columna_reversa_operativa(n):
            continue
        vals = _serie(datos, col)
        filas = [i for i, v in enumerate(vals) if v < -0.001]
        if filas:
            reversas.append({"columna": col, "filas": filas[:12], "filas_detalle": etiquetas_filas(datos, filas, 12), "cantidad": len(filas)})
    return reversas[:6]


def _acumulados_que_retroceden(datos: list[dict[str, Any]], numericas: list[str]) -> list[dict]:
    """Retrocesos sobre el eje temporal real; filas de metas distintas no se comparan como períodos."""
    from services.lentes.ajedrecista import retrocesos_acumulados
    por_columna: dict[str, list[int]] = {}
    columnas = list(dict.fromkeys(c for fila in datos for c in fila))
    for i, col, *_ in retrocesos_acumulados(datos, columnas):
        por_columna.setdefault(col, []).append(i)
    return [{"columna": col, "filas": filas[:12], "filas_detalle": etiquetas_filas(datos, filas, 12), "cantidad": len(filas)}
            for col, filas in list(por_columna.items())[:6]]


def _ratios_extremos(datos: list[dict[str, Any]], etapas: dict[str, str]) -> list[dict]:
    vigente = etapas.get("credito_vigente")
    dev = etapas.get("devengado")
    pag = etapas.get("pagado")
    extremos = []
    if vigente and dev:
        filas = []
        for i, fila in enumerate(datos):
            v = valor_numero(fila.get(vigente))
            d = valor_numero(fila.get(dev))
            if v and d is not None and d / abs(v) > 1.25:
                filas.append(i)
        if filas:
            extremos.append({"relacion": f"{dev} / {vigente}", "filas": filas[:12], "filas_detalle": etiquetas_filas(datos, filas, 12), "cantidad": len(filas)})
    if dev and pag:
        filas = []
        for i, fila in enumerate(datos):
            d = valor_numero(fila.get(dev))
            p = valor_numero(fila.get(pag))
            if d and p is not None and p / abs(d) > 1.25:
                filas.append(i)
        if filas:
            extremos.append({"relacion": f"{pag} / {dev}", "filas": filas[:12], "filas_detalle": etiquetas_filas(datos, filas, 12), "cantidad": len(filas)})
    return extremos


_BAJAR_SEVERIDAD = {"alta": "media", "media": "baja", "baja": "baja"}


def _filas_con_artefacto(filas_cero, reversas, retrocesos, ratios) -> set[int]:
    filas: set[int] = set(filas_cero)
    for grupo in (reversas, retrocesos, ratios):
        for item in grupo:
            filas.update(item.get("filas") or [])
    return filas


def _es_hallazgo_presupuestario(h: dict) -> bool:
    return bool(re.search(r"devengado|pagado|credito|crédito|vigente", h.get("descripcion", ""), re.I))


def analizar(datos: list[dict[str, Any]], hallazgos_previos: list[dict] | None = None, *, interpretacion=None) -> dict:
    """Devuelve {"modulaciones": [...], "hallazgo_general": dict | None}.

    Cada modulacion es {"filas": set[int], "hallazgo_presupuestario": bool,
    "contexto_tecnico": str} y se usa para anotar/bajar severidad de un
    hallazgo ya producido por una lente sustantiva, sin duplicarlo.
    """
    vacio: dict = {"modulaciones": [], "hallazgo_general": None}
    if not datos:
        return vacio

    etapas = _nombre_columnas_presupuesto(datos)
    numericas = columnas_numericas(datos)
    # Los flujos estadísticos con signo no prueban una reversa operativa ni una
    # ejecución presupuestaria. La confirmación del cuadro gobierna esta lente también.
    estadistico = (interpretacion or {}).get("tipo") == "estadistica"
    if estadistico:
        etapas = {}
    importes_estadisticos = {c for c, r in (interpretacion or {}).get("roles", {}).items()
                            if estadistico and r == "importe"}
    cobertura = _pistas_cobertura(datos)
    retrocesos = _acumulados_que_retroceden(datos, numericas)
    if not etapas and len(numericas) < 3 and not cobertura and not retrocesos:
        return vacio

    filas_cero = _filas_credito_cero_con_ejecucion(datos, etapas)
    reversas = _columnas_con_reversas(datos, [c for c in numericas if c not in importes_estadisticos])
    if (interpretacion or {}).get("eje") in {"ninguno", "operaciones"}:
        reversas = []
    # Los acumulados también pueden tener períodos en columnas: su detector
    # verifica ese eje por separado y conserva el contexto de esas señales.
    ratios = _ratios_extremos(datos, etapas)

    pistas = []
    if filas_cero:
        pistas.append(f"{plural.contar(len(filas_cero), 'fila')} con crédito vigente cero o nulo y ejecución informada")
    if reversas:
        pistas.append(f"reversas o movimientos negativos en {plural.contar(len(reversas), 'columna mensual', 'columnas mensuales')}")
    if retrocesos:
        pistas.append(f"retrocesos en {plural.contar(len(retrocesos), 'serie acumulada', 'series acumuladas')}")
    if ratios:
        pistas.append(f"relaciones ejecución/crédito por encima de 125% en {len(ratios)} relación(es)")
    if cobertura:
        pistas.append(f"notas explícitas de cobertura, metodología, controles, inicio de serie o relevamiento en {plural.contar(len(cobertura), 'columna')}")

    # Una imposibilidad que menciona devengado o crédito sólo se modula si el archivo
    # tiene un artefacto técnico real que la explique (las pistas de arriba). Sin pistas
    # la señal queda con su severidad. En una organización no hay vocabulario de
    # presupuesto público: no se modula por palabras de ese vocabulario.
    hallazgos_presupuestarios = [
        h for h in (hallazgos_previos or [])
        if h.get("modo") == "imposibilidad" and _es_hallazgo_presupuestario(h)
    ] if pistas and not ambito.es_organizacion() else []

    if not pistas:
        return vacio

    filas_con_artefacto = _filas_con_artefacto(filas_cero, reversas, retrocesos, ratios)
    contexto_tecnico = (
        "Antes de escalar la señal, conviene conciliar el criterio de publicación: "
        + "; ".join(pistas)
        + ". Puede indicar cambio de cobertura, inicio de serie, reclasificación, carga parcial, "
        "corte temporal, una actualización posterior del presupuesto, una ampliación o compensación no reflejada todavía "
        "o mezcla de niveles de agregación; no es una conclusión sustantiva por sí sola."
    )

    modulaciones = []
    if pistas:
        modulaciones.append({"filas": filas_con_artefacto, "hallazgo_presupuestario": False, "contexto_tecnico": contexto_tecnico})
    if hallazgos_presupuestarios:
        modulaciones.append({"filas": set(), "hallazgo_presupuestario": True, "contexto_tecnico": contexto_tecnico})

    evidencia_general = {
        "regla": "conciliacion_tecnica_previa",
        "columna_periodo": _periodo_col(datos),
        "filas_credito_cero_con_ejecucion": filas_cero[:20],
        "filas_credito_cero_con_ejecucion_detalle": etiquetas_filas(datos, filas_cero, 20),
        "reversas_mensuales": reversas,
        "acumulados_que_retroceden": retrocesos,
        "ratios_extremos": ratios,
        "notas_cobertura": cobertura,
    }
    hallazgo_general = {
        "modo": "conciliacion",
        "descripcion": contexto_tecnico,
        "severidad": "media" if hallazgos_presupuestarios else "baja",
        "evidencia": evidencia_general,
    }

    return {"modulaciones": modulaciones, "hallazgo_general": hallazgo_general}

