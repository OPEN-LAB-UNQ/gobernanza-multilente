"""Valores aislados contra la estructura del cuadro (filas × períodos).

Un cuadro de rubros por período tiene un nivel propio de cada rubro y un movimiento común de
cada período (inflación, aguinaldo, estacionalidad compartida). Se ajustan ambos efectos en
escala logarítmica (pulido de medianas) y se buscan celdas cuyo residuo es grande, aislado
(los períodos vecinos del mismo rubro no lo acompañan) y que no se repite en el mismo período
del año anterior (estacionalidad propia del rubro). Eso separa un salto de un período que
revierte —posible error de celda— de un cambio de nivel sostenido, que queda para el contexto.

También detecta el cambio de escala simultáneo: la mayoría de las series de un cuadro cambia
por un factor cercano a una potencia de mil en el mismo período (una fila o columna cargada en
otra unidad, o el tramo final pegado en miles). Es una sola causa y se informa como un caso.
"""

import math
from statistics import median

from .comun import es_numero, hallazgo, numero
from .series import PICO_EN_SERIE_MIXTA, _tau, calibrar, signo_mixto

FACTOR_MIN = 4.0
ESCALA_COMUN = 1.7  # log10: factor de 50 o más en el mismo sentido


def _pulido(m, filas, cols, vueltas=8):
    r = {k: v for k, v in m.items()}
    for _ in range(vueltas):
        for i in filas:
            vs = [r[(i, j)] for j in cols if (i, j) in r]
            if vs:
                med = median(vs)
                for j in cols:
                    if (i, j) in r:
                        r[(i, j)] -= med
        for j in cols:
            vs = [r[(i, j)] for i in filas if (i, j) in r]
            if vs:
                med = median(vs)
                for i in filas:
                    if (i, j) in r:
                        r[(i, j)] -= med
    return r


def _ords(s):
    if s.get("ordinales"):
        return list(s["ordinales"])
    out = []
    for p in s["periodos"]:
        n = numero(p)
        out.append(int(n) if n is not None and float(n).is_integer() else None)
    return out


def _ordenar(series):
    """Series comparables de un cuadro: mismos períodos, sin totales ni acumulados."""
    from .modelo import es_total
    base = [s for s in series if not s.get("total") and not es_total(s.get("etiqueta")) and not s.get("acumulada")]
    if not base:
        return [], []
    ords = _ords(base[0])
    base = [s for s in base if _ords(s) == ords]
    return base, ords


def _sobresale(valores, j):
    """El valor j supera PICO_EN_SERIE_MIXTA veces al mayor valor absoluto del resto de la serie."""
    vs = [numero(v) for v in valores]
    resto = [abs(v) for k, v in enumerate(vs) if k != j and v is not None]
    return vs[j] is not None and bool(resto) and abs(vs[j]) > PICO_EN_SERIE_MIXTA * max(resto)


def analizar(series, ya_senaladas=frozenset()):
    base, ords = _ordenar(series)
    anual = not base or base[0].get("frecuencia") in (None, "anual")
    if len(base) < 3 or len(ords) < 4 or len(set(o for o in ords if o is not None)) != len(ords):
        return [], []
    m = {}
    signos = {}
    # Series de signo mixto (flujos) e intermitentes (pagos con ceros entre los montos): un valor chico no es un
    # valor aislado, y uno grande sólo lo es si sobresale de toda la serie (como en series.analizar).
    mixtas = set()
    for i, s in enumerate(base):
        vs = [numero(v) for v in s["valores"]]
        nz = [v for v in vs if v]
        if len(nz) < 3:
            continue
        signo = 1 if sum(v > 0 for v in nz) >= sum(v < 0 for v in nz) else -1
        signos[i] = signo
        con_monto = [k for k, v in enumerate(vs) if v]
        if signo_mixto(nz) or sum(vs[k] == 0 for k in range(con_monto[0], con_monto[-1] + 1)) >= 2:
            mixtas.add(i)
        for j, v in enumerate(vs):
            if v and v * signo > 0:
                m[(i, j)] = math.log10(abs(v))
    filas = sorted(signos)
    cols = list(range(len(ords)))
    if len(filas) < 3 or len(m) < 0.6 * len(filas) * len(cols):
        return [], []
    escala = _escala_comun(base, filas, cols, ords, m)
    excluidas = {(i, j) for h in escala for (i, j) in h["evidencia"].pop("_celdas_idx")}
    if anual:
        # En series anuales el valor aislado lo controla la regla por serie (pico con vecinos);
        # con inflación alta el ajuste por período común no distingue error de quiebre real.
        return [], escala
    r = _pulido({k: v for k, v in m.items() if k not in excluidas}, filas, cols)
    abs_res = [abs(v) for v in r.values()]
    sigma = max(0.02, 1.4826 * median(abs_res)) if abs_res else 0.02
    paso = 12 if base[0].get("frecuencia") == "mensual" else 4 if base[0].get("frecuencia") == "trimestral" else None
    out = []
    for (i, j), res in sorted(r.items()):
        s = base[i]
        celda = f"{s['hoja']}!{s['celdas'][j]}"
        if (i in mixtas and not _sobresale(s["valores"], j)) or celda in ya_senaladas or abs(res) < max(math.log10(FACTOR_MIN), 6 * sigma):
            continue
        vecinos = [r.get((i, k)) for k in (j - 1, j + 1) if 0 <= k < len(cols)]
        vecinos = [v for v in vecinos if v is not None]
        if not vecinos or any(abs(v) > 0.5 * abs(res) or abs(v) > math.log10(2) for v in vecinos):
            continue  # cambio de nivel o tramo: no es una celda aislada
        if j in (0, len(cols) - 1) and len(vecinos) < 2:
            continue  # un extremo no tiene confirmación de ambos lados
        if res < 0 and len(vecinos) < 2 and any(0 <= k < len(cols) and numero(s["valores"][k]) == 0 for k in (j - 1, j + 1)):
            continue  # más chico de lo esperable junto a un cero (saldo que se cancela, rubro que empieza)
        if paso and j - paso >= 0 and (i, j - paso) in r:
            previo = r[(i, j - paso)]
            if previo * res > 0 and abs(previo) >= 0.5 * abs(res):
                continue  # el mismo período del año anterior se mueve igual: estacionalidad del rubro
        v = numero(s["valores"][j])
        esperado = 10 ** (m[(i, j)] - res) * signos[i]
        factor = 10 ** abs(res)
        potencia = round(math.log10(factor))
        detalle = (
            f"{es_numero(v)} se aparta {factor:.1f} veces de lo esperable para «{s['etiqueta']}» en "
            f"{s['periodos'][j]} ({es_numero(esperado)}), considerando el nivel del rubro y el movimiento común del "
            "período en el resto del cuadro; los períodos vecinos del mismo rubro no acompañan el salto."
        )
        if potencia >= 1 and abs(math.log10(factor) - potencia) < 0.15:
            detalle += f" El desvío es cercano a {10 ** potencia:g} veces: posible error de escala o de unidad."
        h = hallazgo(
            s, j, "valor_aislado_en_cuadro", detalle, 95 + min(20, round(10 * abs(res))),
            {"valor_esperado_por_estructura": esperado, "factor_escala": factor, "residuo_log10": res,
             "dispersion_residuos_log10": sigma, "series_comparadas": len(filas), "periodos_comparados": len(cols),
             "metodo": "pulido de medianas en logaritmos (nivel del rubro + movimiento del período)",
             "estacionalidad_controlada": bool(paso)},
            participantes=[f"{s['hoja']}!{s['celdas'][k]}" for k in (j - 1, j, j + 1) if 0 <= k < len(cols)],
            accion="Contrastar la celda con la fuente: puede ser un error de escala, de tipeo o un valor copiado de otro rubro.",
        )
        # Mismo criterio que el pico por serie: en un cuadro volátil un desvío de este orden es
        # habitual y no alcanza para la severidad alta.
        out.append(calibrar(h, abs(res) * math.log(10), _tau(s, [numero(x) for x in s["valores"]], j)))
    return out, escala


def _escala_comun(base, filas, cols, ords, m):
    """Transiciones donde la mayoría de las series cambia por el mismo factor grande."""
    out = []
    usados = set()
    for j in range(1, len(cols)):
        cambios = {i: m[(i, j)] - m[(i, j - 1)] for i in filas if (i, j) in m and (i, j - 1) in m}
        if len(cambios) < 3:
            continue
        grandes = [i for i, d in cambios.items() if abs(d) >= ESCALA_COMUN]
        if len(grandes) < max(3, 0.6 * len(cambios)):
            continue
        signo = 1 if sum(cambios[i] > 0 for i in grandes) > len(grandes) / 2 else -1
        grandes = [i for i in grandes if cambios[i] * signo > 0]
        if len(grandes) < max(3, 0.6 * len(cambios)) or j in usados:
            continue
        factor = 10 ** median(abs(cambios[i]) for i in grandes)
        # ¿Revierte? Buscar el período en que la mayoría vuelve a su escala.
        fin = None
        for k in range(j + 1, len(cols)):
            vuelta = [i for i in grandes if (i, k) in m and (i, k - 1) in m and (m[(i, k)] - m[(i, k - 1)]) * -signo >= ESCALA_COMUN]
            if len(vuelta) >= 0.6 * len(grandes):
                fin = k
                break
        tramo = list(range(j, fin if fin is not None else len(cols)))
        usados.update(tramo)
        s0 = base[grandes[0]]
        celdas = [f"{base[i]['hoja']}!{base[i]['celdas'][k]}" for k in tramo[:3] for i in grandes]
        aislado = fin is not None
        regla = "periodo_en_otra_escala" if aislado else "cambio_escala_sostenido"
        periodos_txt = (f"{s0['periodos'][tramo[0]]}" if len(tramo) == 1 else f"{s0['periodos'][tramo[0]]} a {s0['periodos'][tramo[-1]]}")
        detalle = (
            f"{len(grandes)} de {len(cambios)} series cambian a la vez por un factor cercano a {factor:,.0f} "
            f"{'hacia arriba' if signo > 0 else 'hacia abajo'} en {periodos_txt}"
            + (f" y recuperan su escala en {s0['periodos'][fin]}." if aislado else " y no recuperan la escala anterior.")
            + " Un movimiento así de todo el cuadro en el mismo período es típico de valores cargados en otra unidad "
            "(miles en lugar de millones, por ejemplo), no de la evolución de los rubros."
        )
        h = hallazgo(
            s0, tramo[0], regla, detalle, 125,
            {"factor_escala": factor, "sentido": signo, "series_afectadas": len(grandes), "series_comparadas": len(cambios),
             "periodos_afectados": [s0["periodos"][k] for k in tramo], "revierte": aislado,
             "_celdas_idx": [(i, k) for i in grandes for k in tramo]},
            participantes=celdas[:60],
            accion="Verificar la unidad de los valores de ese tramo contra la fuente y homogeneizarla antes de comparar períodos.",
        )
        h["evidencia"]["ubicaciones_excel"] = list(dict.fromkeys(celdas[:60]))
        h["evidencia"]["grupo_relacion"] = f"escala:{s0['hoja']}:{s0['cuadro']}:{s0['periodos'][tramo[0]]}"
        out.append(h)
    return out
