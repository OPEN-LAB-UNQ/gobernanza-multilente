"""El mismo rubro en las demás hojas del archivo.

Los informes provinciales repiten la misma estructura hoja por hoja: veinticuatro versiones del
mismo cuadro. Eso da un punto de referencia que no existe dentro de una sola hoja. Un rubro
cargado en otra unidad, o dos rubros que quedaron intercambiados, dejan la hoja internamente
coherente —los totales siguen cerrando— pero rompen la proporción que ese rubro tiene en todas
las demás jurisdicciones. Solo se afirma algo cuando esa proporción es pareja en el resto.
"""

from collections import defaultdict
from statistics import median

from .comun import es_numero, es_porcentaje, hallazgo, normalizar, numero, referencia

MINIMO_HOJAS = 8  # con pocas hojas no hay patrón contra el cual comparar
MINIMO_PERIODOS = 3
DESVIO = 20  # veces que la proporción se aparta del extremo del resto, no de su mediana
DISPERSION_MAXIMA = 10  # entre el percentil 90 y el 10 del resto; más que eso no es un patrón
CALCE_INTERCAMBIO = 1.5  # cada rubro toma la proporción típica del otro
REFERENCIA_FUERA = 0.6  # proporción de rubros desviados que apunta a la fila de referencia


def _percentil(vs, q):
    vs = sorted(vs)
    return vs[min(len(vs) - 1, max(0, int(round(q * (len(vs) - 1)))))]


def _disperso(resto):
    bajo = _percentil(resto, 0.1)
    return not bajo or _percentil(resto, 0.9) / bajo > DISPERSION_MAXIMA


def _comparable_en_nivel(unidad):
    """Unidades que se comparan en su propio valor: por persona y porcentajes.

    Los millones dependen del tamaño de la jurisdicción y sólo se comparan como proporción; un
    valor por habitante o un porcentaje, en cambio, es del mismo orden en todas las hojas.
    """
    u = normalizar(unidad)
    return u.startswith("en %") or "porcentaje" in u or " por " in u


def _nivel(s):
    vs = [x for x in map(numero, s["valores"]) if x is not None and x > 0]
    return median(vs) if len(vs) >= MINIMO_PERIODOS else None


def _peso(s, pivote):
    """Proporción típica entre el rubro y el rubro de referencia de su hoja."""
    mapa = {p: i for i, p in enumerate(pivote["periodos"]) if isinstance(p, int)}
    razones = []
    for i, p in enumerate(s["periodos"]):
        j = mapa.get(p)
        if j is None:
            continue
        a, b = numero(s["valores"][i]), numero(pivote["valores"][j])
        if a is not None and b is not None and a > 0 and b > 0:
            razones.append(a / b)
    return median(razones) if len(razones) >= MINIMO_PERIODOS else None


def _por_hoja(series_archivo):
    """hoja -> etiqueta normalizada -> serie. Se descartan las etiquetas repetidas en una hoja."""
    out = defaultdict(dict)
    repetidas = defaultdict(set)
    for s in series_archivo:
        clave = normalizar(s["etiqueta"])
        if not clave or sum(numero(v) is not None for v in s["valores"]) < MINIMO_PERIODOS:
            continue
        if clave in out[s["hoja"]]:
            repetidas[s["hoja"]].add(clave)
        out[s["hoja"]][clave] = s
    for hoja, claves in repetidas.items():
        for c in claves:
            out[hoja].pop(c, None)
    return out


def _magnitud(hojas, clave):
    vs = [
        median([x for x in map(numero, hojas[h][clave]["valores"]) if x is not None and x > 0] or [0])
        for h in hojas
        if clave in hojas[h]
    ]
    return median(vs) if vs else 0


def _primera(s):
    return next(i for i, v in enumerate(s["valores"]) if numero(v) is not None)


def _celdas(s):
    return [referencia(s, i) for i, v in enumerate(s["valores"]) if numero(v) is not None]


def _calza(a, b):
    return bool(b) and max(a / b, b / a) <= CALCE_INTERCAMBIO


def _texto(valor, pivote, nombrar=True):
    """Con referencia se expresa como proporción; sin ella, en el valor propio de la serie.

    La fila de referencia se nombra una sola vez por frase: repetirla en cada cifra no agrega
    nada y hace ilegible el hallazgo.
    """
    if not pivote:
        return es_numero(valor)
    return f"{es_porcentaje(valor)} de «{pivote['etiqueta']}»" if nombrar else es_porcentaje(valor)


def _hallazgos_de_hoja(etiquetas, pivote, desvios):
    out, usados = [], set()
    for i, a in enumerate(desvios):
        for b in desvios[i + 1 :]:
            if a["clave"] in usados or b["clave"] in usados:
                continue
            if not (_calza(a["peso"], b["tipico"]) and _calza(b["peso"], a["tipico"])):
                continue
            # Cada uno tiene la proporción del otro: la lectura más simple es que están intercambiados.
            sa, sb = etiquetas[a["clave"]], etiquetas[b["clave"]]
            usados |= {a["clave"], b["clave"]}
            out.append(
                hallazgo(
                    sa,
                    _primera(sa),
                    "rubros_intercambiados",
                    f"«{sa['etiqueta']}» y «{sb['etiqueta']}» tienen acá el valor que el otro tiene en las "
                    f"otras {a['comparadas']} hojas: {_texto(a['peso'], pivote)} y {_texto(b['peso'], pivote, False)}, "
                    f"contra {_texto(a['tipico'], pivote, False)} y {_texto(b['tipico'], pivote, False)}. Las dos series "
                    "parecen intercambiadas.",
                    85,
                    {
                        "serie_intercambiada": sb["etiqueta"],
                        "proporcion_hoja": a["peso"],
                        "proporcion_resto": a["tipico"],
                        "proporcion_hoja_intercambiada": b["peso"],
                        "proporcion_resto_intercambiada": b["tipico"],
                        "hojas_comparadas": a["comparadas"],
                        "serie_referencia": pivote["etiqueta"] if pivote else None,
                    },
                    participantes=_celdas(sa) + _celdas(sb),
                    accion="Verificar si las dos filas quedaron intercambiadas al cargar la hoja.",
                    lente="orquesta",
                )
            )
    for d in desvios:
        if d["clave"] in usados:
            continue
        s = etiquetas[d["clave"]]
        out.append(
            hallazgo(
                s,
                _primera(s),
                "escala_entre_hojas",
                f"«{s['etiqueta']}» vale {_texto(d['peso'], pivote)} en esta hoja y "
                f"{_texto(d['tipico'], pivote, False)} en las otras {d['comparadas']}; se aparta {es_numero(d['factor'], 0)} veces. "
                "Toda la serie está afectada, no un período: puede ser un error de unidad.",
                70,
                {
                    "proporcion_hoja": d["peso"],
                    "proporcion_resto": d["tipico"],
                    "factor_desvio": d["factor"],
                    "hojas_comparadas": d["comparadas"],
                    "serie_referencia": pivote["etiqueta"] if pivote else None,
                },
                participantes=_celdas(s),
                accion="Verificar la unidad de la fila contra las demás hojas del archivo.",
                lente="orquesta",
            )
        )
    return out


def analizar(series):
    # La comparación exige una misma unidad: millones con millones, por persona con por persona.
    por_unidad = defaultdict(list)
    for s in series:
        por_unidad[(s["archivo"], s.get("unidad"))].append(s)
    out = []
    for (_, unidad), ss in por_unidad.items():
        if not unidad:
            continue
        out += _por_unidad(ss, unidad)
    return out


def _pesos(hojas, clave, referencia_clave):
    """Magnitud comparable del rubro en cada hoja: su propio nivel o su proporción con la referencia."""
    pesos = {}
    for h, etiquetas in hojas.items():
        if clave not in etiquetas:
            continue
        if referencia_clave is None:
            p = _nivel(etiquetas[clave])
        elif referencia_clave in etiquetas:
            p = _peso(etiquetas[clave], etiquetas[referencia_clave])
        else:
            p = None
        if p:
            pesos[h] = p
    return pesos


def _desvios(pesos, clave):
    out = []
    for hoja, peso in pesos.items():
        resto = [v for h, v in pesos.items() if h != hoja]
        m = median(resto)
        # El resto tiene que ser parejo: si el rubro ya varía mucho entre hojas, no hay patrón.
        if not m or _disperso(resto):
            continue
        # No alcanza con apartarse de la mediana: hay rubros casi nulos en dos o tres
        # jurisdicciones. Se exige quedar lejos también de las hojas más extremas.
        if peso * DESVIO < _percentil(resto, 0.05) or peso > _percentil(resto, 0.95) * DESVIO:
            out.append(
                (
                    hoja,
                    {
                        "clave": clave,
                        "peso": peso,
                        "tipico": m,
                        "factor": max(peso / m, m / peso),
                        "comparadas": len(resto),
                    },
                )
            )
    return out


def _por_unidad(ss, unidad):
    """Una unidad de un archivo: compara cada rubro con el mismo rubro en las demás hojas."""
    hojas = _por_hoja(ss)
    if len(hojas) < MINIMO_HOJAS:
        return []
    presencia = defaultdict(int)
    for etiquetas in hojas.values():
        for clave in etiquetas:
            presencia[clave] += 1
    comunes = [c for c, n in presencia.items() if n >= max(MINIMO_HOJAS, 0.8 * len(hojas))]
    if _comparable_en_nivel(unidad):
        # Un valor por persona o un porcentaje se compara con el de las otras hojas: alcanza con
        # que la fila exista en todas, sin necesidad de una referencia dentro de la hoja.
        pivote = None
        if not comunes:
            return []
    else:
        if len(comunes) < 3:
            return []
        # Referencia: el rubro común de mayor magnitud, normalmente el total de la hoja.
        pivote = max(comunes, key=lambda c: _magnitud(hojas, c))
        if _magnitud(hojas, pivote) <= 0:
            return []
    desvios = defaultdict(list)
    comparables = defaultdict(int)
    for clave in comunes:
        if clave == pivote:
            continue
        pesos = _pesos(hojas, clave, pivote)
        if len(pesos) < MINIMO_HOJAS:
            continue
        for h in pesos:
            comparables[h] += 1
        for hoja, d in _desvios(pesos, clave):
            desvios[hoja].append(d)
    out = []
    for hoja, ds in desvios.items():
        # Si casi todos los rubros de la hoja se apartan, lo que está fuera de lugar es la fila de
        # referencia: se señala esa y no una por rubro.
        if pivote and len(ds) >= max(3, REFERENCIA_FUERA * comparables[hoja]):
            s = hojas[hoja][pivote]
            out.append(
                hallazgo(
                    s,
                    _primera(s),
                    "referencia_entre_hojas",
                    f"{len(ds)} de los {comparables[hoja]} rubros de esta hoja quedan fuera de escala frente a las "
                    f"otras {ds[0]['comparadas']}; la fila que no coincide es «{s['etiqueta']}», con la que se "
                    "comparan todos.",
                    75,
                    {
                        "rubros_afectados": len(ds),
                        "rubros_comparados": comparables[hoja],
                        "hojas_comparadas": ds[0]["comparadas"],
                    },
                    participantes=_celdas(s),
                    accion="Verificar la fila de referencia de esta hoja contra las demás del archivo.",
                    lente="orquesta",
                )
            )
            continue
        out += _hallazgos_de_hoja(hojas[hoja], hojas[hoja].get(pivote) if pivote else None, ds)
    return out
