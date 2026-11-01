"""Series y validación de períodos para cuadros que no son «años en columnas».

Cubre meses y trimestres en el encabezado, encabezados de dos niveles (variable × período),
períodos en una columna y formato largo. En formato largo la secuencia de períodos se controla
dentro de cada combinación de la clave (las columnas de texto de pocos valores distintos), no
en la columna completa: «2017, 2017, 2018, 2018» es correcto si cada año aparece una vez por
provincia e indicador.
"""

from collections import defaultdict

from services import plural
from services.sanitizacion import sanear

from . import periodos as P
from .comun import hallazgo, numero
from .modelo import es_total

DESORDEN_LISTA = 0.15  # pasos hacia atrás (y hacia adelante) a partir de los cuales una columna larga no es una secuencia
DESORDEN_FUERTE = 0.35  # en una columna corta hace falta mucho más desorden: dos pares invertidos en 10 meses son un error
FILAS_LISTA = 20  # filas desde las que alcanza el desorden moderado para leer la columna como una lista


def _ordinales_validos(ordinales):
    return [o for o in ordinales if o is not None]


def validar_secuencia(s, regla_base="periodo"):
    """Duplicados, retrocesos y huecos en una secuencia de períodos con ordinales."""
    ords = s["ordinales"]
    out = []
    vistos = {}
    validos = _ordinales_validos(ords)
    # Si casi todos los períodos se repiten (cada año en muchas filas: ciudades de 2022, datos
    # diarios con su año), la columna clasifica filas; no es una secuencia que controlar.
    if len(validos) >= 4 and len(set(validos)) * 2 <= len(validos):
        return out
    difs = [b - a for a, b in zip(validos, validos[1:])]
    # Fechas que suben y bajan a lo largo de la columna (fechas de emisión de una lista de títulos, de
    # alta de registros): la columna describe cada fila, no es una secuencia de períodos. En una serie
    # corta, unos pocos períodos fuera de orden son un error que se informa, no una lista.
    suben, bajan = sum(d > 0 for d in difs), sum(d < 0 for d in difs)
    desorden = min(suben, bajan) / len(difs) if difs else 0
    if bajan >= 2 and suben >= 2 and (desorden >= DESORDEN_FUERTE or (len(validos) >= FILAS_LISTA and desorden >= DESORDEN_LISTA)):
        return out
    descendente = bool(difs) and all(d <= 0 for d in difs) and any(d < 0 for d in difs)
    paso = -1 if descendente else 1
    regular = sum(d == paso for d in difs) >= max(2, len(difs) - 2)
    previo = None
    for i, o in enumerate(ords):
        regla = detalle = None
        if o is None:
            pass
        elif o in vistos:
            regla = f"{regla_base}_duplicado"
            detalle = f"repite el período de {s['celdas'][vistos[o]]}"
        elif previo is not None and (o - previo) * paso < 0:
            regla = f"{regla_base}_fuera_de_secuencia"
            detalle = "rompe el orden de la secuencia"
        elif previo is not None and regular and abs(o - previo) > 1:
            regla = f"{regla_base}_faltante"
            detalle = f"falta{'' if abs(o - previo) == 2 else 'n'} {plural.contar(abs(o - previo) - 1, 'período', 'períodos')} antes de este"
        if o is not None:
            vistos.setdefault(o, i)
            previo = o
        if regla:
            h = hallazgo(
                s, i, regla,
                f"Período {s['periodos'][i]}: {detalle}; secuencia observada {s['periodos'][:24]}{' …' if len(s['periodos']) > 24 else ''}.",
                120,
                {"frecuencia": s.get("frecuencia"), "clave_formato_largo": s.get("clave"),
                 "analisis_temporal": "no_evaluable",
                 "motivo_no_evaluable": "Período duplicado, faltante o fuera de secuencia en el eje temporal: "
                                         "las comparaciones entre períodos no son confiables hasta corregirlo."},
                accion="Corregir o justificar el rótulo del período antes de interpretar la serie; mientras tanto la lectura temporal de este cuadro no es evaluable.",
            )
            h["evidencia"]["grupo_relacion"] = f"periodo:{s['hoja']}:{s['celdas'][i]}"
            out.append(h)
    return out


def _base(c, **extra):
    # `extra` puede fijar la frecuencia de un panel (años sueltos junto a trimestres en un mismo cuadro).
    base = dict(archivo=c["archivo"], hoja=c["hoja"], cuadro=c["cuadro"], ambito=None, unidad=c.get("unidad"),
                frecuencia=c.get("frecuencia"), modelo=True)
    base.update(extra)
    return base


def _nivel(c, r):
    """Sangría del rótulo. En los cuadros año + trimestre (que antes leía la lectura anual) también cuentan
    los espacios iniciales, como en esa lectura: «     Variaciones de precio» es hija de «Revalorizaciones»."""
    nivel = c["sangria"].get(r, 0)
    if c.get("subperiodos") and c.get("frecuencia") == "trimestral" and c.get("etiqueta_idx"):
        raw = c["crudos"].get((r, c["etiqueta_idx"]))
        if isinstance(raw, str):
            nivel += len(raw) - len(raw.lstrip())
    return nivel


def _con_numero(c, r, idx):
    return numero(c["valores"].get((r, idx))) is not None or numero(c["crudos"].get((r, idx))) is not None


SERIES_PERIODO_SIN_DATOS = 3  # series del cuadro que hacen falta para decir que un período no tiene datos


def periodos_con_datos(tiene):
    """Por serie y período, si el período tiene datos en el cuadro (`tiene`: por serie, si hay número en cada período).

    Es falso sólo si ninguna otra serie tiene número ahí y al menos otras dos lo abarcan (tienen números antes y
    después): la fuente no lo publicó, como un año sin encuesta. Un período antes de que empiecen las demás series no
    cuenta, así que un faltante de la serie más larga se sigue viendo. Con menos de tres series, siempre verdadero.
    """
    if len(tiene) < SERIES_PERIODO_SIN_DATOS:
        return [[True] * len(t) for t in tiene]
    largo = max(len(t) for t in tiene)
    con_dato, abarcan, tramos = [0] * largo, [0] * largo, []
    for t in tiene:
        usados = [k for k, x in enumerate(t) if x]
        tramo = (usados[0], usados[-1]) if usados else None
        tramos.append(tramo)
        for k in usados:
            con_dato[k] += 1
        for k in range(tramo[0] + 1, tramo[1]) if tramo else ():
            abarcan[k] += 1
    return [[con_dato[k] - bool(t[k]) > 0 or abarcan[k] - bool(tramo and tramo[0] < k < tramo[1]) < 2
             for k in range(len(t))] for t, tramo in zip(tiene, tramos)]


def _sanear_valores(raws):
    saneados, _ = sanear([{"valor": v} for v in raws])
    return [x.get("valor") for x in saneados]


def series(c, acumuladas=frozenset(), totales_columna=frozenset()):
    """Series en el formato de los controles por serie (periodos, celdas, valores, fórmulas)."""
    salida = []
    if c["eje"] == "columnas":
        cols = [x for x in c["columnas"] if x.get("periodo")]
        paneles = defaultdict(list)
        for x in cols:
            paneles[c["paneles"].get(x["idx"])].append(x)
        # Un período que abarcan otras series del cuadro sin número en ninguna no tiene datos (la fuente no lo publicó,
        # como un año sin encuesta): un vacío ahí no es un faltante de la serie.
        con_rotulo = [r for r in c["filas"] if c["etiquetas"].get(r)]
        con_datos = {}
        for panel, xs in paneles.items():
            xs = sorted(xs, key=lambda x: x["idx"])
            marcas = periodos_con_datos([[_con_numero(c, r, x["idx"]) for x in xs] for r in con_rotulo])
            con_datos.update({(panel, r): m for r, m in zip(con_rotulo, marcas)})
        for r in c["filas"]:
            etiqueta = c["etiquetas"].get(r)
            if not etiqueta:
                continue
            for panel, xs in paneles.items():
                xs = sorted(xs, key=lambda x: x["idx"])
                raws = _sanear_valores([c["crudos"][(r, x["idx"])] for x in xs])
                vals = [c["valores"][(r, x["idx"])] if c["formulas"][(r, x["idx"])] and raws[k] is None else raws[k]
                        for k, x in enumerate(xs)]
                salida.append(_base(
                    c, fila=r, encabezado=c["header"], orientacion="horizontal",
                    columna_etiqueta=c["etiqueta_idx"],
                    frecuencia=xs[0]["periodo"]["frecuencia"],
                    etiqueta=f"{etiqueta} · {panel}" if panel else etiqueta,
                    nivel=_nivel(c, r),
                    periodos=[_periodo_visible(x["periodo"]) for x in xs],
                    ordinales=[x["periodo"]["ordinal"] for x in xs],
                    marcas=[x["periodo"].get("marca") for x in xs],
                    periodos_validos=True,
                    celdas=[c.celda(r, x["idx"]) for x in xs],
                    valores=vals,
                    formulas=[c["formulas"][(r, x["idx"])] for x in xs],
                    periodo_con_datos=con_datos.get((panel, r), [True] * len(xs)),
                    acumulada=any(x["periodo"].get("acumulado") for x in xs),
                    total=es_total(etiqueta),
                ))
        return salida
    if c["eje"] in ("filas", "largo"):
        grupos = defaultdict(list)
        for r in c["filas"]:
            if r not in c["periodos_fila"]:
                continue
            clave = tuple(str(c["crudos"][(r, k)]).strip() for k in c["claves"])
            grupos[clave].append(r)
        for clave, filas in grupos.items():
            filas = sorted(filas)
            ps = [c["periodos_fila"][r] for r in filas]
            nombre_clave = " · ".join(_sanear_valores(list(clave))) if clave else ""
            numericas = [x for x in c["columnas"] if x["numerica"] and not x.get("identificador") and not x.get("tiempo")]
            marcas = periodos_con_datos([[_con_numero(c, r, x["idx"]) for r in filas] for x in numericas])
            con_datos = {x["idx"]: m for x, m in zip(numericas, marcas)}
            for x in c["columnas"]:
                if not x["numerica"] or x.get("identificador") or x.get("tiempo"):
                    continue
                raws = _sanear_valores([c["crudos"][(r, x["idx"])] for r in filas])
                vals = [c["valores"][(r, x["idx"])] if c["formulas"][(r, x["idx"])] and raws[k] is None else raws[k]
                        for k, r in enumerate(filas)]
                if sum(numero(v) is not None for v in vals) < 3:
                    continue
                salida.append(_base(
                    c, orientacion="vertical", columna=x["idx"], encabezado=c["header"],
                    # La clave primero: «Total · Monto» se reconoce como total de su grupo.
                    etiqueta=f"{nombre_clave} · {x['nombre']}" if nombre_clave else x["nombre"],
                    clave=nombre_clave or None, nivel=0,
                    periodos=[_periodo_visible(p) for p in ps],
                    ordinales=[p["ordinal"] for p in ps],
                    marcas=[p.get("marca") for p in ps],
                    periodos_validos=True,
                    celdas=[c.celda(r, x["idx"]) for r in filas],
                    celdas_periodo=[c.celda(r, c["col_tiempo"]) for r in filas],
                    filas_excel=filas,
                    valores=vals,
                    formulas=[c["formulas"][(r, x["idx"])] for r in filas],
                    periodo_con_datos=con_datos.get(x["idx"], [True] * len(filas)),
                    acumulada=x["idx"] in acumuladas,
                    total=x["idx"] in totales_columna or es_total(x["nombre"]),
                ))
    return salida


def _periodo_visible(p):
    # Años como enteros, igual que el resto de los controles; meses y trimestres con su rótulo normalizado.
    if p["frecuencia"] == "anual":
        return p["anio"]
    return P.etiqueta(p)


def _filas_son_entidades(c):
    """Hay una columna de texto con un valor distinto en cada fila (país, región, código)."""
    filas = c["filas"]
    if len(filas) < 6:
        return False
    for x in c["columnas"]:
        k = x["idx"]
        if k == c.get("col_tiempo"):
            continue
        textos = [str(c["crudos"].get((r, k)) or "").strip() for r in filas]
        if all(t and numero(t) is None for t in textos) and len(set(textos)) == len(textos):
            return True
    return False


def validar_cuadro(c):
    """Alertas de período del cuadro: encabezado, columna de tiempo o cada clave del formato largo."""
    out = []
    if c["eje"] == "columnas":
        cols = [x for x in c["columnas"] if x.get("periodo")]
        paneles = defaultdict(list)
        for x in cols:
            paneles[c["paneles"].get(x["idx"])].append(x)
        for panel, xs in paneles.items():
            xs = sorted(xs, key=lambda x: x["idx"])
            s = _base(c, etiqueta=f"Encabezado temporal{' · ' + panel if panel else ''}",
                      periodos=[x["encabezado"] if x["encabezado"] is not None else P.etiqueta(x["periodo"]) for x in xs],
                      ordinales=[x["periodo"]["ordinal"] for x in xs],
                      celdas=[c.celda(c["header"], x["idx"]) for x in xs], valores=[x["encabezado"] for x in xs])
            out += validar_secuencia(s)
    elif c["eje"] == "filas" and _filas_son_entidades(c):
        # Cada fila es un país o región distinto: el año es un dato de la fila, no una secuencia.
        out += _unidad_por_fila(c)
    elif c["eje"] in ("filas", "largo"):
        grupos = defaultdict(list)
        for r in c["filas"]:
            clave = tuple(str(c["crudos"][(r, k)]).strip() for k in c["claves"])
            grupos[clave].append(r)
        faltantes = []
        presentes = set()  # períodos que tiene alguna combinación de la clave
        huecos = []  # (alerta, ordinales que faltan antes de esa fila)
        for clave, filas in grupos.items():
            filas = sorted(filas)
            ps = [c["periodos_fila"].get(r) for r in filas]
            nombre = " · ".join(_sanear_valores(list(clave))) if clave else None
            s = _base(c, etiqueta=f"Período{' · ' + nombre if nombre else ''}", clave=nombre,
                      periodos=[str(c["crudos"][(r, c["col_tiempo"])]) for r in filas],
                      ordinales=[p["ordinal"] if p else None for p in ps],
                      celdas=[c.celda(r, c["col_tiempo"]) for r in filas],
                      valores=[c["crudos"][(r, c["col_tiempo"])] for r in filas])
            alertas = validar_secuencia(s)
            if c["eje"] == "largo":
                presentes.update(o for o in s["ordinales"] if o is not None)
                for h in alertas:
                    if h["evidencia"]["regla"].endswith("_faltante"):
                        huecos.append((h, _ordinales_faltantes(s, h)))
                alertas = [h for h in alertas if not h["evidencia"]["regla"].endswith("_faltante")]
            out += alertas
        # Un período que no tiene ninguna combinación de la clave falta en todo el cuadro: eso sí es un hueco
        # de la serie (se informa una vez, con prioridad alta). Los demás huecos son de panel.
        del_cuadro = {}
        for h, faltan in huecos:
            if len(grupos) > 1 and faltan and not (faltan & presentes):
                if frozenset(faltan) not in del_cuadro:
                    h["descripcion"] += (f" Ninguna de las {len(grupos)} combinaciones de la clave tiene ese período: "
                                         "falta en todo el cuadro, no sólo en una entidad.")
                    h["evidencia"]["combinaciones_de_la_clave"] = len(grupos)
                    del_cuadro[frozenset(faltan)] = h
            else:
                faltantes.append(h)
        out += list(del_cuadro.values())
        out += _faltantes_de_panel(faltantes, len(grupos))
        out += _unidad_por_fila(c)
    # Un mismo problema de período repetido en muchas claves es una sola causa: se agrupa.
    return out


def _ordinales_faltantes(s, h):
    """Ordinales que faltan entre la fila de la alerta y el período anterior de su serie."""
    try:
        i = s["celdas"].index(h["evidencia"]["celda"])
    except (KeyError, ValueError):
        return set()
    o = s["ordinales"][i]
    previo = next((x for x in reversed(s["ordinales"][:i]) if x is not None), None)
    if o is None or previo is None:
        return set()
    paso = 1 if o > previo else -1
    return set(range(previo + paso, o, paso))


def _faltantes_de_panel(faltantes, entidades):
    """Datos de panel (provincia × departamento × año): que una entidad no tenga un año es lo habitual
    (no se sembró, no se relevó), no un rótulo mal cargado. Se dice una sola vez por cuadro, como señal
    media, con cuántas combinaciones de la clave tienen huecos."""
    if not faltantes:
        return []
    h = faltantes[0]
    con_huecos = len({x["evidencia"].get("clave_formato_largo") for x in faltantes})
    ev = h["evidencia"]
    ev.update(puntaje_prioridad=60, factores_prioridad=[{"criterio": ev["regla"], "puntos": 60}],
              combinaciones_con_huecos=con_huecos, combinaciones_de_la_clave=entidades, huecos_en_el_cuadro=len(faltantes),
              analisis_temporal="evaluable_por_serie",
              motivo_no_evaluable=None)
    h["severidad"] = "media"
    accion = "Confirmar con la fuente si los huecos se esperan; no impiden leer cada serie por separado."
    ev["accion_revision"] = h["pregunta_institucional"] = accion
    h["descripcion"] = h["descripcion"].split(" Corregir o justificar")[0] + (f" Es un cuadro de panel: {con_huecos} de {entidades} combinaciones de la clave tienen algún período "
                         f"sin fila ({len(faltantes)} huecos en total). Que una entidad no tenga un año suele ser normal "
                         f"(sin dato o sin actividad). {accion}")
    return [h]


def _unidad_por_fila(c):
    """Formato largo: una fila declarada en otra unidad que el resto de su serie."""
    mezcla = c.get("unidad_mezclada") or {}
    if not mezcla.get("filas"):
        return []
    valores = [x for x in c["columnas"] if x["numerica"] and not x.get("identificador") and not x.get("tiempo")]
    out = []
    for r, (unidad, mayoritaria) in sorted(mezcla["filas"].items()):
        clave = " · ".join(_sanear_valores([str(c["crudos"][(r, k)]).strip() for k in c["claves"]]))
        x = valores[0] if valores else None
        idx = x["idx"] if x else mezcla["idx"]
        p = c["periodos_fila"].get(r)
        s = _base(c, etiqueta=clave or mezcla["nombre"], clave=clave or None,
                  periodos=[_periodo_visible(p) if p else None], celdas=[c.celda(r, idx)],
                  valores=[c["crudos"][(r, idx)]])
        h = hallazgo(
            s, 0, "unidad_fila_distinta",
            f"La fila declara «{unidad}» en la columna «{mezcla['nombre']}» ({c.celda(r, mezcla['idx'])}) y el resto de "
            f"su serie, «{mayoritaria}». Es una señal de unidad mezclada en esa fila: su valor no es comparable con los "
            "demás períodos sin convertirlo.",
            100,
            {"unidad_fila": unidad, "unidad_serie": mayoritaria, "clave_formato_largo": clave or None},
            participantes=[c.ref(r, mezcla["idx"]), c.ref(r, idx)],
            accion="Confirmar la unidad de esa fila y expresar toda la serie en la misma unidad antes de compararla.",
        )
        h["evidencia"]["grupo_relacion"] = f"unidad:{c['hoja']}:{r}"
        out.append(h)
    return out
