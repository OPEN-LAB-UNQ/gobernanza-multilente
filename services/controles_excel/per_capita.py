"""Coherencia entre importe total y valor por persona del mismo cuadro.

Si un cuadro publica "En millones de $" y "En $ por niño/a" (o por habitante), el
cociente importe / valor por persona es la población implícita. La población cambia
poco de un año a otro: un salto aislado indica que uno de los dos valores tiene un
error de escala o de tipeo. La regla sólo se afirma cuando la población implícita es
estable en el resto de la serie.
"""

import math
from collections import defaultdict

from .comun import hallazgo, normalizar, numero, referencia

SALTO = 1.5  # población implícita que cambia más de 50 % respecto de sus vecinos
ESTABLE = 1.15  # el resto de la serie debe variar menos de 15 % por período
MINIMO_PERIODOS = 4


def _es_importe(s):
    return normalizar(s["etiqueta"]).startswith("en millones")


def _es_por_persona(s):
    e = normalizar(s["etiqueta"])
    return " por " in f" {e} " and any(p in e for p in ("nin", "habitante", "persona", "adolescente", "beneficiari"))


def _desvio_local(valores, i):
    vecinos = [valores[j] for j in (i - 1, i + 1) if 0 <= j < len(valores) and valores[j]]
    if not vecinos or not valores[i]:
        return 0.0
    base = math.exp(sum(math.log(v) for v in vecinos) / len(vecinos))
    return abs(math.log(valores[i] / base))


def analizar(series):
    grupos = defaultdict(list)
    for s in series:
        grupos[(s["archivo"], s["hoja"])].append(s)
    pares = []
    for filas in grupos.values():
        # El valor por persona acompaña al importe en las filas siguientes del mismo cuadro;
        # la carga puede separar cada fila en su propio bloque, así que se empareja por cercanía.
        for imp in (s for s in filas if _es_importe(s) and s.get("fila")):
            candidatos = [s for s in filas if _es_por_persona(s) and s.get("fila") and 0 < s["fila"] - imp["fila"] <= 3]
            if candidatos:
                pares.append((imp, min(candidatos, key=lambda s: s["fila"])))
    out = []
    for imp, per in pares:
        comunes = [p for p in imp["periodos"] if p in per["periodos"] and isinstance(p, (int, float))]
        if len(comunes) < MINIMO_PERIODOS:
            continue
        ii = [imp["periodos"].index(p) for p in comunes]
        jj = [per["periodos"].index(p) for p in comunes]
        a = [numero(imp["valores"][i]) for i in ii]
        b = [numero(per["valores"][j]) for j in jj]
        pob = [x * 1e6 / y if x and y and x > 0 and y > 0 else None for x, y in zip(a, b)]
        n = len(pob)
        for k in range(n):
            if pob[k] is None:
                continue
            vecinos = [pob[j] for j in (k - 1, k + 1) if 0 <= j < n and pob[j]]
            if not vecinos:
                continue
            factor = max(abs(math.log(pob[k] / v)) for v in vecinos)
            if all(abs(math.log(pob[k] / v)) < math.log(SALTO) for v in vecinos):
                continue
            # El resto de la serie (sin el período evaluado) debe ser estable.
            resto = [p for j, p in enumerate(pob) if j != k and p]
            pasos = [abs(math.log(resto[j + 1] / resto[j])) for j in range(len(resto) - 1)]
            if len(resto) < MINIMO_PERIODOS - 1 or any(x >= math.log(ESTABLE) for x in pasos):
                continue
            if len(vecinos) == 2 and abs(math.log(pob[k] / vecinos[0]) - math.log(pob[k] / vecinos[1])) > math.log(SALTO):
                continue  # un vecino no acompaña: cambio de nivel, no un valor aislado
            # Culpable probable: el valor que más se aparta de sus propios vecinos.
            sospechosa, idx = (imp, ii[k]) if _desvio_local(a, k) > _desvio_local(b, k) else (per, jj[k])
            otra, idx_otra = (per, jj[k]) if sospechosa is imp else (imp, ii[k])
            veces = math.exp(factor)
            out.append(
                hallazgo(
                    sospechosa,
                    idx,
                    "poblacion_implicita",
                    f"La población implícita ({imp['etiqueta']} / {per['etiqueta']}) es {pob[k]:,.0f}; "
                    f"en los períodos vecinos es {', '.join(f'{v:,.0f}' for v in vecinos)} ({veces:.1f} veces). "
                    "Uno de los dos valores del período no es coherente con el otro.",
                    110 + min(20, round(10 * math.log10(veces))),
                    calculo=dict(
                        poblacion_implicita=pob[k],
                        poblacion_vecinos=vecinos,
                        factor_poblacion=veces,
                        celda_relacionada=referencia(otra, idx_otra),
                    ),
                    participantes=[referencia(sospechosa, idx), referencia(otra, idx_otra)],
                    accion="Verificar el importe y el valor por persona del período con la fuente; uno de los dos tiene otra escala o un error de carga.",
                    lente="conciliador",
                )
            )
    return out
