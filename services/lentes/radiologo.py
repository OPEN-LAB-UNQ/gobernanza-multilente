"""Radiólogo: semejanza de casos.

Alcance inicial: dominio presupuestario. Compara el caso nuevo exclusivamente
contra un banco histórico de informes previos comparables. La evolución dentro
del archivo pertenece a Matemático y Cronista, no se usa como sustituto del
banco de preinformes.
"""
from __future__ import annotations

import re
from typing import Any

from .util import columnas_numericas, suma_por_columna, zscore

DOMINIO_SOPORTADO = "presupuestario"
# Con pocos casos casi iguales, un +3 % daba «alta» a cinco sigmas. Se exige un cambio
# relativo mínimo frente a la media, un piso de dispersión y casos suficientes para «alta».
CAMBIO_RELATIVO_MIN = 0.10
PISO_DISPERSION_REL = 0.02
CASOS_MIN_ALTA = 5
MES_RE = re.compile(r"(\d{4})-(\d{2})")


def _mismo_mes(periodo_a: str, periodo_b: str) -> bool:
    ma, mb = MES_RE.match(periodo_a or ""), MES_RE.match(periodo_b or "")
    return bool(ma and mb and ma.group(2) == mb.group(2))


def _tendencia_sostenida(serie: list[float], umbral_proporcion: float = 0.8) -> dict | None:
    """Si la serie historica sube (o baja) de forma casi monotona, el ultimo
    punto de una serie asi va a estar cerca del extremo del rango casi por
    construccion -- no hace falta que haya un quiebre real para que el
    z-score contra el nivel bruto lo marque. En vez de intentar destendenciar
    el calculo (probado aparte: con 6-7 puntos una regresion es inestable y
    puede empeorar el falso positivo en vez de corregirlo), esta funcion solo
    detecta la tendencia para que quede como contexto explicito en el
    hallazgo -- el criterio de si eso alcanza para explicar la senal queda en
    quien lee el informe, no en el sistema."""
    if len(serie) < 3:
        return None
    transiciones = list(zip(serie, serie[1:]))
    subidas = sum(1 for a, b in transiciones if b >= a)
    bajadas = len(transiciones) - subidas
    proporcion = max(subidas, bajadas) / len(transiciones)
    if proporcion < umbral_proporcion:
        return None
    variaciones = [
        (b - a) / a for a, b in transiciones if a not in (0, None)
    ]
    if not variaciones:
        return None
    variacion_promedio = sum(variaciones) / len(variaciones)
    return {
        "direccion": "creciente" if subidas >= bajadas else "decreciente",
        "proporcion_consistente": round(proporcion, 2),
        "variacion_promedio_por_periodo_pct": round(variacion_promedio * 100, 1),
    }


def _hallazgos_vs_casos(
    periodo: str,
    actual: dict[str, float],
    casos: list[dict[str, Any]],
    fuente: str,
    umbral: float,
) -> list[dict]:
    hallazgos = []
    for col, valor_actual in actual.items():
        casos_col = [c for c in casos if col in c["sumas"]]
        serie = [c["sumas"][col] for c in casos_col]
        if len(serie) < 3:
            continue
        media = sum(serie) / len(serie)
        if media and abs(valor_actual - media) / abs(media) < CAMBIO_RELATIVO_MIN:
            continue
        desvio = (sum((x - media) ** 2 for x in serie) / len(serie)) ** 0.5
        piso = PISO_DISPERSION_REL * abs(media)
        z = (valor_actual - media) / piso if desvio < piso and piso > 0 else zscore(valor_actual, serie)
        if abs(z) < umbral:
            continue

        precedente_estacional = any(
            _mismo_mes(periodo, c["periodo"]) and abs(zscore(c["sumas"][col], serie)) >= 2.0
            for c in casos_col
        )
        if fuente == "banco_historico" and precedente_estacional:
            continue

        periodos_de_referencia = sorted({c["periodo"] for c in casos_col})
        serie_cronologica = [c["sumas"][col] for c in sorted(casos_col, key=lambda c: c["periodo"])]
        tendencia = _tendencia_sostenida(serie_cronologica)
        nota_tendencia = ""
        if tendencia:
            nota_tendencia = (
                f" Aviso: la serie previa venía en tendencia {tendencia['direccion']} sostenida "
                f"({tendencia['proporcion_consistente']*100:.0f}% de los períodos, "
                f"~{tendencia['variacion_promedio_por_periodo_pct']}% promedio por período); "
                "el desvío puede corresponder a esa tendencia y no a un quiebre puntual -- conviene revisarlo antes de escalarlo."
            )

        hallazgos.append({
            "modo": "semejanza",
            "descripcion": (
                f"En el período {periodo}, '{col}' se ubica muy por fuera del rango comparable "
                f"(desvío de {z:.1f} sigma respecto a {len(serie)} casos previos). "
                f"La comparación usa {('un banco histórico de informes' if fuente == 'banco_historico' else 'los períodos anteriores del propio archivo')}."
                f"{nota_tendencia}"
            ),
            "severidad": "media" if tendencia or len(serie) < CASOS_MIN_ALTA else ("alta" if abs(z) > 3.5 else "media"),
            "evidencia": {
                "columna": col,
                "valor_actual": round(valor_actual, 2),
                "zscore_vs_historico": round(z, 2),
                "n_casos_comparados": len(serie),
                "fuente_comparacion": fuente,
                "periodo_comparado": periodo,
                "periodos_de_referencia": periodos_de_referencia,
                "tendencia_previa": tendencia,
            },
        })
    return hallazgos


def analizar(
    dominio: str,
    periodo: str,
    datos: list[dict[str, Any]],
    banco_historico: list[dict[str, Any]],
) -> list[dict]:
    if dominio != DOMINIO_SOPORTADO or not datos:
        return []

    numericas = columnas_numericas(datos)
    if not numericas:
        return []

    if len(banco_historico) < 3:
        return []
    actual = suma_por_columna(datos, numericas)
    casos = []
    for caso in banco_historico:
        cols_caso = [c for c in numericas if c in columnas_numericas(caso["datos"])]
        if not cols_caso:
            continue
        sumas = suma_por_columna(caso["datos"], cols_caso)
        casos.append({"periodo": caso["periodo"], "sumas": sumas})
    return _hallazgos_vs_casos(periodo, actual, casos, "banco_historico", 2.5)
