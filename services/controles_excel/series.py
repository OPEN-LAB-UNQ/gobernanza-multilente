"""Integridad y anomalías locales; conserva huecos y nunca cruza un período ausente."""

import math
import re
from statistics import median

from services.perfilado import es_no_publicado, es_sin_dato

from .comun import hallazgo, mad, normalizar, numero, referencia
from .temporal import periodos_ambiguos, ventana_valida

# Flujos que admiten cualquier signo: transacciones, revalorizaciones, variaciones, saldos netos
# («D.1 Transacciones financieras», «Préstamo neto»). Un negativo entre positivos es parte del flujo.
FLUJO_CON_SIGNO = re.compile(r"\bnet[ao]s?\b|transacci|revaloriz|flujo|variaci")
# Rótulos de fila que declaran un resultado o una diferencia, que puede tener cualquier signo. No basta
# ADMITE_SIGNO (columnas): «Impuesto a las Ganancias», «Margen bruto», «Ajuste por inflación» o
# «Otros servicios» son importes de signo constante, y un negativo ahí sigue siendo una señal; un saldo
# de deuda es un stock, no un flujo.
FILA_ADMITE_SIGNO = re.compile(
    r"\bsaldo\b(?!s?\s+(?:de\s+(?:la\s+)?)?deuda)|\bresultado|super[aá]vit|d[eé]ficit|\bdiferencia|"
    r"\bbalance\b|errores y omisiones|\bahorro\b|\(\s*[ivx]+\s*[-–]\s*[ivx]+\s*\)",
    re.I,
)


def admite_signo(etiqueta):
    """El rótulo de la fila declara un flujo o un saldo, que puede tener cualquier signo."""
    t = normalizar(str(etiqueta or ""))
    return bool(FILA_ADMITE_SIGNO.search(t) or FLUJO_CON_SIGNO.search(t))


# Veces que un pico de una serie de signo mixto debe superar al mayor valor absoluto del resto.
PICO_EN_SERIE_MIXTA = 5


def signo_mixto(ns):
    """La serie alterna signos de forma habitual (flujos): al menos 2 valores, y el 10 % de los no
    nulos, de cada signo. Ahí un valor chico entre dos grandes es el cruce por cero, no un error."""
    no_nulos = [v for v in ns if v]
    negativos = sum(v < 0 for v in no_nulos)
    positivos = len(no_nulos) - negativos
    return min(negativos, positivos) >= max(2, 0.1 * len(no_nulos))

# Calibración por volatilidad: un salto se mide en desvíos robustos de las variaciones
# logarítmicas habituales de la propia serie y de su cuadro. En una serie estable un ×10 son
# decenas de desvíos; en una serie que salta de 5 a 150 y vuelve todos los meses, un salto de ese
# orden es lo habitual y no alcanza para afirmar un error.
DESVIOS_ALTA = 4.0  # desde acá el salto es raro aun para una serie volátil: se mantiene la severidad
VOLATILIDAD_MINIMA = 0.05


def volatilidad(pasos):
    """Desvío robusto (1,4826 · MAD) de variaciones logarítmicas; None con menos de 4 pasos."""
    if len(pasos) < 4:
        return None
    centro = median(pasos)
    return 1.4826 * median(abs(p - centro) for p in pasos)


def pasos_log(vs, excluir=None):
    return [
        math.log(vs[j + 1] / vs[j])
        for j in range(len(vs) - 1)
        if (excluir is None or excluir not in (j, j + 1))
        and vs[j] is not None and vs[j + 1] is not None and vs[j] > 0 and vs[j + 1] > 0
    ]


def _pasos_por_transicion(vs):
    return [
        math.log(vs[j + 1] / vs[j]) if vs[j] is not None and vs[j + 1] is not None and vs[j] > 0 and vs[j + 1] > 0 else None
        for j in range(len(vs) - 1)
    ]


def anotar_volatilidad_cuadro(series):
    """Volatilidad de cada cuadro, para calibrar los saltos de cada una de sus series.

    Se miden los pasos logarítmicos de los rubros (sin totales, que suavizan) descontados la
    tendencia propia de cada rubro y el movimiento común de cada transición (inflación,
    crecimiento del período): lo que queda es cuánto se mueve habitualmente un rubro por su
    cuenta, como desvío robusto (1,4826 · MAD).
    """
    from .modelo import es_total

    grupos = {}
    for s in series:
        grupos.setdefault((s["archivo"], s["hoja"], s["cuadro"], s.get("orientacion"), s.get("panel")), []).append(s)
    for grupo in grupos.values():
        rubros = [s for s in grupo if not (s.get("total") or es_total(s.get("etiqueta")))] or grupo
        matriz = [_pasos_por_transicion([numero(v) for v in s["valores"]]) for s in rubros]
        largo = {len(f) for f in matriz}
        pasos = []
        if len(rubros) >= 3 and len(largo) == 1:
            # Pulido de medianas de los pasos: tendencia propia de cada rubro y movimiento común de
            # cada transición. Un rubro que crece siempre más que otro no es volátil.
            ancho = largo.pop()
            residuos = [list(f) for f in matriz]
            for _ in range(4):
                for f in residuos:
                    presentes = [p for p in f if p is not None]
                    if presentes:
                        centro = median(presentes)
                        f[:] = [None if p is None else p - centro for p in f]
                for j in range(ancho):
                    columna = [f[j] for f in residuos if f[j] is not None]
                    if columna:
                        centro = median(columna)
                        for f in residuos:
                            if f[j] is not None:
                                f[j] -= centro
            pasos = [p for f in residuos for p in f if p is not None]
            # Al quitar una mediana por rubro y otra por transición, los residuos de un cuadro chico
            # se achican: se corrigen por los grados de libertad usados.
            usados = len(rubros) + ancho - 1
            if len(pasos) > usados + 1:
                correccion = math.sqrt(len(pasos) / (len(pasos) - usados))
                pasos = [p * correccion for p in pasos]
        else:
            pasos = [p for f in matriz for p in f if p is not None]
        tau = volatilidad(pasos) if len(pasos) >= 6 else None
        for s in grupo:
            s["volatilidad_cuadro"] = tau


PASOS_PROPIOS_SUFICIENTES = 8


def _tau(s, vs, i):
    """Volatilidad de referencia: la de la serie si tiene historia suficiente; si no, la del cuadro.

    En una serie corta los pocos pasos que quedan pueden estar contaminados por el mismo error
    (un subtotal que lo arrastra): ahí manda la volatilidad de todas las series del cuadro.
    """
    pasos = pasos_log(vs, i)
    propia = volatilidad(pasos)
    cuadro = s.get("volatilidad_cuadro")
    if len(pasos) >= PASOS_PROPIOS_SUFICIENTES or cuadro is None:
        referencia = max(propia or 0.0, cuadro or 0.0)
    else:
        referencia = cuadro
    return max(referencia, VOLATILIDAD_MINIMA)


SALTOS_PARECIDOS = 2  # otros saltos del mismo orden en la serie: el salto es recurrente (estacional)


def saltos_parecidos(vs, i, salto_log):
    """Cuántos pasos de la serie (sin los que tocan el período) son del mismo orden que el salto."""
    return sum(1 for p in pasos_log(vs, i) if abs(p) >= 0.6 * salto_log)


def calibrar(h, salto_log, tau, parecidos=0):
    """Ajusta la severidad de un salto según cuántos desvíos habituales representa.

    Un salto que la serie repite (aguinaldo en junio y diciembre, una cosecha, saltos de 3 a 5
    veces frecuentes) tampoco es raro aunque el resto de los pasos sea chico: queda en media.
    """
    desvios = salto_log / tau
    ev = h["evidencia"]
    ev.update(volatilidad_tipica_log=tau, salto_en_desvios=desvios, saltos_parecidos_en_la_serie=parecidos)
    if desvios >= DESVIOS_ALTA and parecidos < SALTOS_PARECIDOS:
        return h
    # Salto del orden de los habituales (o recurrente): se conserva como señal media, con su
    # calibración en la evidencia; no alcanza para la severidad alta.
    puntos = min(ev["puntaje_prioridad"], 60)
    ev.update(puntaje_prioridad=puntos, calibrado_por_volatilidad=True)
    ev["factores_prioridad"].append({"criterio": "serie_volatil", "puntos": puntos - sum(x["puntos"] for x in ev["factores_prioridad"])})
    h["severidad"] = "media"
    return h


def analizar(s):
    out = []
    vs = [numero(v) for v in s["valores"]]
    ns = [v for v in vs if v is not None]
    if len(ns) < 3 or len(ns) / max(len(vs), 1) < 0.75:
        return out
    # Con 3 valores numéricos no hay base estadística, pero un vacío, un texto o un signo
    # aislado dentro de una serie numérica siguen siendo observables.
    solo_estructura = len(ns) < 4
    positives = all(v > 0 for v in ns)
    negativos = sum(v < 0 for v in ns)
    positivos_n = sum(v > 0 for v in ns)
    med = median(ns)
    dispersion = mad(ns)
    # Un flujo declarado en el rótulo (transacciones, variaciones, netos) admite cualquier signo.
    flujo = admite_signo(s.get("etiqueta"))
    # Si lo declara la hoja o el título del cuadro («Variaciones_Anual»), el signo distinto se registra igual
    # (puede ser la huella de un error que se propaga desde la hoja base) pero no encabeza como prioridad alta.
    hoja_de_variaciones = bool(FLUJO_CON_SIGNO.search(normalizar(str(s.get("hoja") or ""))))\
        or bool(FLUJO_CON_SIGNO.search(normalizar(str(s.get("ambito") or ""))))
    # Serie de signo mixto: los picos se miden mal cerca del cruce por cero.
    mixta = signo_mixto(ns)
    # Serie intermitente (vencimientos o pagos con ceros entre los montos): un período chico entre dos
    # grandes es habitual; como en la de signo mixto, sólo cuenta un valor que sobresale de toda la serie.
    # Cuentan los ceros entre el primer y el último monto: una serie que empieza o termina en cero no lo es.
    con_monto = [k for k, v in enumerate(vs) if v]
    intermitente = bool(con_monto) and sum(vs[k] == 0 for k in range(con_monto[0], con_monto[-1] + 1)) >= 2
    sin_dato = set(s.get("sin_dato_convencion") or ())
    for i, v in enumerate(vs):
        anterior = vs[i - 1] if i else None
        posterior = vs[i + 1] if i + 1 < len(vs) else None
        interior = 0 < i < len(vs) - 1
        vecinos = interior and anterior is not None and posterior is not None
        evidencia = {
            "valor_anterior": anterior,
            "valor_posterior": posterior,
            "tipo_esperado": "número",
            "mediana_serie": med,
            "mad_serie": dispersion,
        }
        raw = s["valores"][i]
        if v is None:
            if raw is None or str(raw).strip() == "":
                # Fórmula sin caché no equivale a dato eliminado.
                if (
                    vecinos
                    and not s.get("formulas", [False] * len(vs))[i]
                    and s.get("periodo_con_datos", [True] * len(vs))[i]
                ):
                    out.append(
                        hallazgo(
                            s,
                            i,
                            "vacio_interior",
                            ("Celda vacía en una serie numérica, con 0 en el período anterior y en el siguiente."
                             if anterior == posterior == 0 else
                             f"Vacío entre {anterior:g} y {posterior:g} en una serie predominantemente numérica."),
                            50 if anterior == posterior == 0 else 120,
                            {**evidencia, "completitud_a_verificar": anterior == posterior == 0},
                            accion=("Completitud a verificar: confirmar el significado administrativo de vacío y cero; no imputar cero automáticamente."
                                    if anterior == posterior == 0 else None),
                        )
                    )
            elif es_no_publicado(raw) or str(raw).strip().lower() in sin_dato or ("(" in str(raw) and es_sin_dato(raw)):
                # «<5», «<0,1»: dato no publicado (confidencialidad o menor que la unidad), declarado en la lectura.
                # «s/i», «s/d», «///» usados dos o más veces en la hoja: convención del cuadro para el dato no
                # disponible, también declarada en la lectura. Una marca suelta sigue siendo un cambio de tipo.
                pass
            else:
                out.append(
                    hallazgo(
                        s,
                        i,
                        "cambio_tipo",
                        f"Valor {raw!r}; se esperaba un número. Puede ser un código de ausencia que requiere explicación.",
                        120,
                        evidencia,
                    )
                )
            continue
        if not flujo and v > 0 and positivos_n == 1 and negativos >= 4 and vecinos and anterior < 0 and posterior < 0:
            # Convención inversa: una serie de egresos o devoluciones en negativo con un único positivo.
            out.append(
                hallazgo(
                    s,
                    i,
                    "signo_aislado",
                    f"Único positivo ({v:g}) en una serie registrada en negativo, entre {anterior:g} y {posterior:g}.",
                    120,
                    evidencia,
                    accion="Confirmar si el signo es correcto o si corresponde a una reversión documentada.",
                )
            )
            continue
        if not flujo and v < 0 and negativos == 1 and vecinos and anterior > 0 and posterior > 0:
            out.append(
                hallazgo(
                    s,
                    i,
                    "signo_aislado",
                    f"Único negativo ({v:g}) entre valores positivos {anterior:g} y {posterior:g}.",
                    120,
                    evidencia,
                    accion="Confirmar si el signo es correcto o si corresponde a una reversión documentada.",
                )
            )
            continue
        if not flujo and v < 0 and negativos == 1 and positivos_n >= 4 and not vecinos and (anterior or posterior or 0) > 0:
            # En el borde de la serie: un único negativo en el primer o último período, entre positivos.
            vecino = anterior if anterior is not None else posterior
            out.append(
                hallazgo(
                    s,
                    i,
                    "signo_aislado",
                    f"Único negativo ({v:g}) entre valores positivos; está en el {'último' if anterior is not None else 'primer'} período, junto a {vecino:g}.",
                    120,
                    {**evidencia, "valor_anterior": anterior, "valor_posterior": posterior},
                    accion="Confirmar si el signo es correcto o si corresponde a una reversión documentada.",
                )
            )
            continue
        if solo_estructura:
            continue
        if vecinos:
            # No unir años separados ni construir vecinos por sobre datos faltantes.
            anos = s["periodos"]
            if not ventana_valida(s, (i - 1, i, i + 1)):
                continue
            interpolado = (anterior + posterior) / 2
            z = abs(v - med) / (1.4826 * dispersion) if dispersion else None
            ra = v / anterior if anterior else None
            rp = v / posterior if posterior else None
            ev = {
                **evidencia,
                "periodos_ventana": [anos[i - 1], anos[i], anos[i + 1]],
                "periodos_ambiguos_excluidos": periodos_ambiguos(s),
                "razon_anterior": ra,
                "razon_posterior": rp,
                "interpolacion": interpolado,
                "desviacion_interpolacion": v - interpolado,
                "desviacion_relativa_interpolacion": abs(v - interpolado) / abs(interpolado) if interpolado else None,
                "desviacion_robusta_mad": z,
                "diferencia_logaritmica": math.log(v) - 0.5 * (math.log(anterior) + math.log(posterior))
                if positives
                else None,
            }
            # En un flujo de signo mixto los saltos de 10 o 30 veces entre trimestres son habituales
            # (153 → 5.899 → 237): sólo cuenta un pico que además sobresale de toda la serie, como
            # un valor cargado en otra unidad.
            fuera_de_serie = not (mixta or intermitente) or v > PICO_EN_SERIE_MIXTA * max(
                abs(x) for k, x in enumerate(vs) if k != i and x is not None)
            if v > 0 and anterior > 0 and posterior > 0 and fuera_de_serie:
                factor = max(v / interpolado, interpolado / v)
                bilateral = min(max(ra, 1 / ra), max(rp, 1 / rp))
                mismo_lado = v > max(anterior, posterior) or v < min(anterior, posterior)
                vecinos_cercanos = max(anterior, posterior) / min(anterior, posterior) <= 4
                # Con inflación alta los vecinos pueden separarse más de 4 veces en dos años; en ese
                # caso se compara contra la interpolación geométrica y se exige un desvío mayor.
                geometrico = math.sqrt(anterior * posterior)
                factor_geometrico = max(v / geometrico, geometrico / v)
                # El resto de la serie debe ser regular: en series chicas y volátiles un salto
                # así es habitual y no alcanza para señalar un error.
                pasos_resto = [
                    abs(math.log(vs[j + 1] / vs[j]))
                    for j in range(len(vs) - 1)
                    if i not in (j, j + 1) and vs[j] and vs[j + 1] and vs[j] > 0 and vs[j + 1] > 0
                ]
                crecimiento_alto = (
                    not vecinos_cercanos
                    and max(anterior, posterior) / min(anterior, posterior) <= 10
                    and bilateral >= 3.5
                    and factor_geometrico >= 6
                    and max(anterior, posterior) >= 1  # importes ínfimos: variación sin significado
                    and len(pasos_resto) >= 2
                    and all(x < math.log(3) for x in pasos_resto)
                )
                fuerte = mismo_lado and ((vecinos_cercanos and bilateral >= 3 and factor >= 5) or crecimiento_alto)
                moderado = (
                    mismo_lado and vecinos_cercanos and bilateral >= 2 and factor >= 3 and z is not None and z >= 6
                )
                tau = _tau(s, vs, i)
                # En una serie volátil los vecinos pueden estar lejos entre sí: un salto de diez
                # veces o más que además es raro para la propia serie (con historia suficiente para
                # medir su volatilidad) y para su cuadro sigue siendo un pico.
                # Los vecinos no pueden estar a más de diez veces entre sí: si lo están, la serie ya
                # cambia de escala por su cuenta y el período no tiene una referencia clara.
                if (not (fuerte or moderado) and mismo_lado and bilateral >= 10
                        and max(anterior, posterior) / min(anterior, posterior) <= 10
                        and volatilidad(pasos_log(vs, i)) is not None and math.log(bilateral) / tau >= DESVIOS_ALTA):
                    fuerte = True
                if fuerte or moderado:
                    puntos = (85 if fuerte else 55) + min(20, round(10 * math.log10(factor)))
                    ev.update(
                        factor_escala=factor,
                        discrepancia_ambos_vecinos=bilateral,
                        transiciones_consolidadas=[anos[i], anos[i + 1]],
                    )
                    out.append(calibrar(
                        hallazgo(
                            s,
                            i,
                            "pico_aislado",
                            f"{anterior:g} → {v:g} → {posterior:g}; el valor se aparta {factor:.2f} veces de la interpolación entre vecinos y la serie recupera su escala.",
                            puntos,
                            ev,
                            participantes=[referencia(s, k) for k in (i - 1, i, i + 1)],
                            accion="Revisar posible error de escala o decimal y contrastar con cambios de cobertura o metodología.",
                        ),
                        math.log(bilateral),
                        tau,
                        saltos_parecidos(vs, i, math.log(bilateral)),
                    ))
        elif (i == len(vs) - 1 or i == 0) and v > 0 and len(vs) >= 5:
            # En un extremo se declara la falta de segundo vecino; nunca se finge confirmación bilateral.
            indices = range(i - 2, i + 1) if i else range(3)
            if not ventana_valida(s, indices):
                continue
            prev = vs[i - 1 : i] + vs[i - 2 : i - 1] if i else vs[1:3]
            if len(prev) == 2 and all(x is not None and x > 0 for x in prev):
                a, b = prev
                esperado = a * a / b
                ratio = max(v / a, a / v)
                factor = max(v / esperado, esperado / v)
                # Un ×10 en el último año con crecimiento previo queda algo por debajo de 10 veces la
                # extrapolación: basta 7 si el salto contra el año anterior es de 10 veces o más.
                # Un primer período diez veces MAYOR, con la serie en crecimiento, queda algo por debajo
                # de 10 veces su vecino: ahí basta apartarse 9 veces de la extrapolación. Sólo en ese
                # caso: una caída fuerte en el último año (2020 en una serie real) no es un error de escala.
                fuerte = (ratio >= 10 and factor >= 7) or (i == 0 and v > a and ratio >= 8 and factor >= 9)
                candidato = ratio >= 3 and factor >= 5
                if candidato and max(a / b, b / a) <= 4:
                    out.append(calibrar(
                        hallazgo(
                            s,
                            i,
                            "escala_extremo",
                            f"Valor extremo {v:g}, vecino {a:g} y extrapolación local {esperado:g}; diferencia de escala de {factor:.2f} veces. Falta un segundo vecino para confirmación bilateral.",
                            90 + min(15, round(math.log10(factor) * 5)),
                            {
                                **evidencia,
                                "factor_escala": factor,
                                "extrapolacion": esperado,
                                "confirmacion_bilateral": False,
                                "requiere_conciliacion": not fuerte,
                            },
                            accion="Verificar la escala en la fuente; considerar que el último o primer período puede ser parcial.",
                        ),
                        math.log(ratio),
                        _tau(s, vs, i),
                        saltos_parecidos(vs, i, math.log(ratio)),
                    ))
    out += salto_escala_final(s, vs)
    out += repeticion_exacta(s, vs)
    if hoja_de_variaciones:
        for h in out:
            if (h.get("evidencia") or {}).get("regla") == "signo_aislado":
                h["evidencia"]["en_hoja_de_variaciones"] = True
    return out


SALTO_FINAL_MINIMO = 2.5  # log10: un factor de ~300 o más
SALTO_FINAL_CERCA_POTENCIA = 0.35
PASO_ESTABLE = 0.5  # log10: antes y después del salto la serie se mueve menos de ~3 veces por período


def salto_escala_final(s, vs):
    """Salto de escala sostenido al final de la serie: desde un período, todos los valores siguientes
    quedan cerca de una potencia de diez por debajo (o por encima) del resto, con la serie estable antes
    y después. Es el valor cargado en otra unidad desde ahí (0,0584 → 0,000075 → 0,00011 → 0,00022).
    Una cola de un solo período queda para el control del extremo; el cambio de unidad declarado en el
    propio cuadro lo vuelve contexto después."""
    n = len(vs)
    out = []
    for j in range(3, n - 1):
        a, b = vs[j - 1], vs[j]
        if not a or not b or a * b < 0:
            continue
        salto = abs(math.log10(abs(b) / abs(a)))
        if salto < SALTO_FINAL_MINIMO or abs(salto - round(salto)) > SALTO_FINAL_CERCA_POTENCIA:
            continue
        pre = [v for v in vs[:j] if v is not None][-6:]
        cola = [v for v in vs[j:] if v is not None]
        if len(pre) < 3 or len(cola) < 2 or any(not v or v * a <= 0 for v in pre + cola):
            continue
        pasos = [abs(math.log10(abs(y) / abs(x))) for tramo in (pre, cola) for x, y in zip(tramo, tramo[1:])]
        if max(pasos) > PASO_ESTABLE or salto < 4 * max(pasos):
            continue
        if not ventana_valida(s, (j - 1, j)):
            continue
        factor = 10 ** salto
        sentido = 1 if abs(b) > abs(a) else -1
        out.append(hallazgo(
            s, j, "salto_escala_final",
            f"{a:g} → {b:g}: desde {s['periodos'][j]} los {len(cola)} valores de la serie quedan unas {factor:,.0f} veces "
            f"{'por encima' if sentido > 0 else 'por debajo'} del resto, con la serie estable antes y después del salto. "
            "Posible cambio de unidad o de escala desde ese período.",
            110,
            {"valor_anterior": a, "valor_posterior": vs[j + 1], "factor_escala": factor, "sentido": sentido,
             "potencia_de_diez": round(salto), "periodos_en_otra_escala": len(cola),
             "paso_maximo_log10_fuera_del_salto": max(pasos)},
            participantes=[referencia(s, k) for k in range(j, n) if vs[k] is not None],
            accion="Verificar la unidad de los valores desde ese período contra la fuente.",
        ))
        break
    return out


def _resolucion(v):
    # Dígitos significativos del valor: 95,24 tiene 4; 0,065 tiene 2; 1.200 tiene 2.
    return len(re.sub(r"[^0-9]", "", f"{abs(v):.10g}").strip("0")) or 1


def repeticion_exacta(s, vs):
    """Un valor repetido exacto en dos períodos seguidos, con el resto de la serie todo distinto.

    Es la costura que deja una columna corrida un período, y también el síntoma de un valor
    copiado del año anterior. No se afirma cuál de las dos cosas es.
    """
    ns = [v for v in vs if v is not None]
    if len(ns) < 5 or len(set(ns)) != len(ns) - 1:
        return []
    pares = [i for i in range(1, len(vs)) if vs[i] is not None and vs[i - 1] is not None and vs[i] == vs[i - 1]]
    if len(pares) != 1:
        return []
    i = pares[0]
    v = vs[i]
    # Valores redondeados a pocos dígitos coinciden por azar; ahí la repetición no dice nada.
    if not v or _resolucion(v) < 4 or not ventana_valida(s, (i - 1, i)):
        return []
    pasos = [
        abs(math.log(vs[j + 1] / vs[j]))
        for j in range(len(vs) - 1)
        if j != i - 1 and vs[j] and vs[j + 1] and vs[j] > 0 and vs[j + 1] > 0
    ]
    # En una serie que casi no se mueve, dos años iguales son esperables.
    if len(pasos) < 3 or median(pasos) < 0.02:
        return []
    return [
        hallazgo(
            s,
            i,
            "valor_repetido",
            f"{v:g} se repite exacto en {s['periodos'][i - 1]} y {s['periodos'][i]}, mientras el resto de la serie cambia en todos los períodos.",
            80,
            {
                **{
                    "valor_anterior": vs[i - 1],
                    "valor_posterior": vs[i + 1] if i + 1 < len(vs) else None,
                    "digitos_significativos": _resolucion(v),
                    "variacion_tipica_serie": median(pasos),
                    "valores_distintos": len(set(ns)),
                    "valores_numericos": len(ns),
                }
            },
            participantes=[referencia(s, i - 1), referencia(s, i)],
            accion="Verificar si el período repite el valor del anterior o si la serie quedó corrida un período.",
        )
    ]


def contexto_compartido(series, hallazgos):
    # Series del mismo cuadro y año: un movimiento compartido pierde prioridad como error aislado.
    for h in hallazgos:
        ev = h["evidencia"]
        if ev["regla"] != "pico_aislado":
            continue
        candidatas = [
            s
            for s in series
            if s["archivo"] == ev["archivo_origen"] and s["hoja"] == ev["hoja"] and s["cuadro"] == ev["bloque_excel"]
        ]
        grupo = [
            x
            for x in hallazgos
            if x["evidencia"]["regla"] == "pico_aislado"
            and all(x["evidencia"][k] == ev[k] for k in ("archivo_origen", "hoja", "bloque_excel", "periodo"))
        ]
        if len(grupo) >= 3 and len(grupo) >= len(candidatas) * 0.5:
            ev.update(
                naturaleza="contexto",
                requiere_contexto_anual=True,
                series_movimiento_compartido=len(grupo),
                puntaje_prioridad=20,
            )
            ev["factores_prioridad"].append(
                {"criterio": "movimiento_compartido", "puntos": 20 - sum(x["puntos"] for x in ev["factores_prioridad"])}
            )
            h["lente"] = "cronista"
            h["severidad"] = "media"
    return hallazgos
