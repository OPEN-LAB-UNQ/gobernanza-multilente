"""Movimientos compensados: un monto que pasa de un rubro a otro sin cambiar el total.

La suma sigue cerrando, así que la conciliación no lo ve. La huella queda en la serie de
cada rubro: en el mismo período uno sube y otro baja casi el mismo importe respecto de su
propia tendencia, mientras el total sigue su curso. Se compara contra la interpolación
geométrica de los vecinos (tolera inflación) y se exige que el desvío sea grande frente a
la variación habitual de cada serie.
"""

import math
from collections import defaultdict
from statistics import median

from .comun import hallazgo, normalizar, numero, referencia

RELATIVO_MINIMO = 0.3  # al menos uno de los dos rubros se aparta 30 % de su tendencia
VECES_RUIDO = 3  # y el otro, 3 veces su desvío habitual
CALCE = 0.2  # los dos desvíos se compensan con un margen de 20 %
TOTAL_QUIETO = 0.25  # el total se aparta menos que un cuarto del monto movido
MINIMO_CAMBIOS_PARTICIPACION = 3  # cuadros cortos: cambios de participación para estimar el ruido


def _es_total(s):
    return normalizar(s["etiqueta"]).split(" ")[0] in ("total", "subtotal")


def _desvios(vs):
    """Desvío de cada período interior respecto de la interpolación geométrica de sus vecinos."""
    out = [None] * len(vs)
    for i in range(1, len(vs) - 1):
        a, v, p = vs[i - 1], vs[i], vs[i + 1]
        if a and v is not None and p and a > 0 and p > 0 and v >= 0:
            base = math.sqrt(a * p)
            out[i] = (v - base, base)
    return out


def _ruido(vs, excluir):
    """Variación habitual del crecimiento, sin los dos pasos que tocan el período evaluado."""
    pasos = [
        math.log(vs[k + 1] / vs[k])
        for k in range(len(vs) - 1)
        if excluir not in (k, k + 1) and vs[k] and vs[k + 1] and vs[k] > 0 and vs[k + 1] > 0
    ]
    if len(pasos) < 2:
        return None
    centro = median(pasos)
    return max(median(abs(p - centro) for p in pasos), 0.02)


def _ruido_participacion(info, vt, excluir):
    """Cuadros cortos (cuatro períodos): la serie propia no tiene dos pasos lejos del período.

    Se estima la variación habitual con los cambios de participación en el total de todos los
    rubros del cuadro, en los pasos que no tocan el período evaluado. La participación ya
    descuenta la inflación y el crecimiento común, que mueven al total.
    """
    cambios = []
    for _, vs, _ in info:
        for k in range(len(vs) - 1):
            if excluir in (k, k + 1):
                continue
            a, b, ta, tb = vs[k], vs[k + 1], vt[k], vt[k + 1]
            if a and b and ta and tb and min(a, b, ta, tb) > 0:
                cambios.append(abs(math.log((b / tb) / (a / ta))))
    if len(cambios) < MINIMO_CAMBIOS_PARTICIPACION:
        return None
    return max(median(cambios), 0.02)


DESVIOS_ALTA = 3.0  # desvíos de la volatilidad propia del cuadro (series.anotar_volatilidad_cuadro)


def _desvio_log(d, base):
    valor = base + d
    return abs(math.log(valor / base)) if valor > 0 and base > 0 else float("inf")


def analizar(series):
    grupos = defaultdict(list)
    for s in series:
        grupos[(s["archivo"], s["hoja"], s["cuadro"])].append(s)
    out = []
    for filas in grupos.values():
        totales = [s for s in filas if _es_total(s)]
        rubros = [s for s in filas if not _es_total(s)]
        if not totales or len(rubros) < 2:
            continue
        total = totales[0]
        periodos = total["periodos"]
        vt = [numero(v) for v in total["valores"]]
        dt = _desvios(vt)
        info = []
        for s in rubros:
            if s["periodos"] != periodos:
                continue
            vs = [numero(v) for v in s["valores"]]
            info.append((s, vs, _desvios(vs)))
        for i in range(1, len(periodos) - 1):
            if not dt[i]:
                continue
            candidatos = []
            ruido_cuadro = None
            for s, vs, ds in info:
                if not ds[i]:
                    continue
                d, base = ds[i]
                ruido = _ruido(vs, i)
                if ruido is None:
                    ruido_cuadro = ruido_cuadro or _ruido_participacion(info, vt, i)
                    ruido = ruido_cuadro
                if ruido is None or base <= 0:
                    continue
                candidatos.append((s, d, base, abs(d) / base, ruido))
            usados = set()
            pares = sorted(
                ((a, b) for a in candidatos for b in candidatos if a[1] > 0 and b[1] < 0),
                key=lambda x: abs(x[0][1] + x[1][1]) / max(abs(x[0][1]), abs(x[1][1])),
            )
            # Cada rubro participa de un solo par (el que mejor compensa): evita repetir el mismo
            # movimiento con el rubro padre y su subrubro.
            for (s1, d1, b1, r1, n1), (s2, d2, b2, r2, n2) in pares:
                if id(s1) in usados or id(s2) in usados or s1.get("nivel", 0) != s2.get("nivel", 0):
                    continue  # sólo rubros del mismo nivel: un subrubro no compensa a otro rubro
                monto = max(abs(d1), abs(d2))
                if abs(d1 + d2) > CALCE * monto:
                    continue
                if max(r1, r2) < RELATIVO_MINIMO or min(r1 / max(n1, 1e-9), r2 / max(n2, 1e-9)) < VECES_RUIDO:
                    continue
                if abs(dt[i][0]) > TOTAL_QUIETO * monto:
                    continue
                usados.update((id(s1), id(s2)))
                # Calibración por volatilidad del cuadro: si los rubros suelen moverse así, el par
                # compensado puede ser azar; queda como señal media, no alta.
                ruido_cuadro_log = s1.get("volatilidad_cuadro")
                desvios = min(_desvio_log(d1, b1), _desvio_log(d2, b2)) / max(ruido_cuadro_log or 0, 0.05)
                puntos = 100 if ruido_cuadro_log is None or desvios >= DESVIOS_ALTA else 60
                # Se señala el rubro que más se aparta en proporción: allí el error es más visible.
                s, otro = (s1, s2) if r1 >= r2 else (s2, s1)
                out.append(
                    hallazgo(
                        s,
                        i,
                        "movimiento_compensado",
                        f"En {periodos[i]} «{s1['etiqueta']}» sube {abs(d1):,.1f} y «{s2['etiqueta']}» baja {abs(d2):,.1f} "
                        "respecto de su tendencia, mientras el total sigue su curso. Puede ser una reclasificación "
                        "o un importe imputado al rubro equivocado; la suma sigue cerrando.",
                        100,
                        calculo=dict(
                            desvio_sube=d1,
                            desvio_baja=d2,
                            desvio_total=dt[i][0],
                            celda_compensada=referencia(otro, i),
                        ),
                        participantes=[referencia(s1, i), referencia(s2, i), referencia(total, i)],
                        accion="Confirmar con el área la imputación de ambos rubros en el período; si hubo una reclasificación, documentarla.",
                        lente="conciliador",
                    )
                )
                if puntos < 100:
                    ev = out[-1]["evidencia"]
                    ev.update(puntaje_prioridad=puntos, calibrado_por_volatilidad=True,
                              volatilidad_tipica_log=ruido_cuadro_log, salto_en_desvios=desvios)
                    ev["factores_prioridad"].append({"criterio": "cuadro_volatil", "puntos": puntos - 100})
                    out[-1]["severidad"] = "media"
    return out
