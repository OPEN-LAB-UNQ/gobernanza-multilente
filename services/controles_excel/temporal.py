"""Encabezados y columnas de período: validación compartida para ambas orientaciones."""

import threading
from collections import Counter
from functools import lru_cache

from .comun import hallazgo, numero

SUBPERIODOS = {"mensual", "trimestral", "semestral"}


def formato_oficial(periodos):
    """Formatos oficiales de una columna de períodos que no son errores; None si no es ninguno.

    - «anios_con_subperiodos»: años con sus meses (o trimestres, semestres) debajo, en la misma columna
      («2010», «Enero» … «Diciembre», «2011», …). Antes cada mes era un «año no entero».
    - «anio_punto_mes»: año.mes como número (2021.04; 2021.1 es octubre; 2021.11). Antes, «año no entero».
    - «bloques_por_frecuencia»: bloques seguidos de una sola frecuencia cada uno («2016» … «2025», «I.16» …
      «IV.25», «2016-01» …), como en las planillas de un ministerio. Antes cada trimestre y cada mes era un «año no entero».
    """
    from . import periodos as P

    nums = [numero(y) for y in periodos]
    anios = [i for i, n in enumerate(nums) if n is not None and n.is_integer() and 1800 <= n <= 2200]
    subs = []
    for i, y in enumerate(periodos):
        p = P.leer(y) if isinstance(y, str) else None
        if p and p.get("anio") is None and p.get("frecuencia") in SUBPERIODOS:
            subs.append(i)
    if anios and len(subs) >= 2 and min(anios) < min(subs) and len(anios) + len(subs) >= len(nums) - 2:
        return "anios_con_subperiodos", None
    if bloques_de_frecuencia(periodos):
        return "bloques_por_frecuencia", None
    fracc = [n for n in nums if n is not None and not n.is_integer()]
    if len(fracc) >= 3 and all(1800 <= n < 2201 and 1 <= round((n - int(n)) * 100) <= 12 for n in fracc):
        return "anio_punto_mes", [int(n) * 12 + round((n - int(n)) * 100) if n is not None else None for n in nums]
    # Una sola frecuencia que no es anual, con su año («I.16» … «IV.18», «2016-01» …): se valida por su ordinal.
    leidos = [None if _vacio(y) else P.leer(y) for y in periodos]
    presentes = [p for p in leidos if p is not None]
    if (len(presentes) >= 2 and len(presentes) == sum(not _vacio(y) for y in periodos)
            and all(p.get("anio") is not None for p in presentes)
            and len({p["frecuencia"] for p in presentes}) == 1 and presentes[0]["frecuencia"] != "anual"):
        return "subperiodos_con_anio", [P.ordinal(p) if p else None for p in leidos]
    return None, None


def _vacio(y):
    return y is None or (isinstance(y, str) and not y.strip())


def bloques_de_frecuencia(periodos):
    """Tramos (desde, hasta) de dos o más bloques seguidos, cada uno de una sola frecuencia y con año, con al menos
    dos períodos cada uno y todos los rótulos leídos como períodos; None si la columna no tiene esa forma. Un rótulo
    vacío queda en el bloque en el que está."""
    from . import periodos as P

    bloques = []  # [frecuencia, desde, hasta, cantidad]
    for i, y in enumerate(periodos):
        if _vacio(y):
            if bloques:
                bloques[-1][2] = i + 1
            continue
        p = P.leer(y)
        if not p or p.get("anio") is None:
            return None
        if bloques and bloques[-1][0] == p["frecuencia"]:
            bloques[-1][2:] = [i + 1, bloques[-1][3] + 1]
        else:
            bloques.append([p["frecuencia"], bloques[-1][2] if bloques else 0, i + 1, 1])
    frecuencias = [b[0] for b in bloques]
    if len(bloques) < 2 or len(set(frecuencias)) != len(frecuencias) or any(b[3] < 2 for b in bloques):
        return None
    return [(b[1], b[2]) for b in bloques]


def _validar_mensual(s, ordinales, aclaracion=" (año.mes)", periodicidad="mensual (año.mes)"):
    """Año.mes como número (o subperíodos con su año): duplicados y retrocesos se miden sobre el ordinal del
    período, no sobre el año."""
    out, vistos = [], set()
    conocidos = [o for o in ordinales if o is not None]
    descendente = len(conocidos) > 1 and conocidos[-1] < conocidos[0]
    previo = None
    for i, o in enumerate(ordinales):
        if o is None:
            continue
        regla = None
        if o in vistos:
            regla = "periodo_duplicado"
        elif previo is not None and ((o < previo) != descendente):
            regla = "periodo_fuera_de_secuencia"
        vistos.add(o)
        previo = o
        if regla:
            out.append(hallazgo(s, i, regla, f"Período {s['periodos'][i]}{aclaracion}; secuencia observada {s['periodos']}.",
                                120, {"periodicidad_inferida": periodicidad},
                                accion="Corregir o justificar el período antes de interpretar el tramo afectado."))
    return out, not out


def validar(s):
    periodos = s["periodos"]
    formato, ordinales = formato_oficial(periodos)
    if formato == "anios_con_subperiodos":
        # Totales anuales y meses en la misma columna: no es un error, pero tampoco una serie única que se
        # pueda comparar punto a punto. No se marca nada y la columna no entra en los controles temporales.
        return [], False
    if formato == "bloques_por_frecuencia":
        # Bloques de distinta frecuencia: cada uno se valida con su propio ordinal (un año repetido al comienzo del
        # bloque trimestral es un duplicado del anual); la columna entera no es una serie única.
        from . import periodos as P

        out = []
        for desde, hasta in bloques_de_frecuencia(periodos):
            ordinales = [P.ordinal(P.leer(y)) if desde <= i < hasta and not _vacio(y) else None
                         for i, y in enumerate(periodos)]
            out += _validar_mensual(s, ordinales, "", "bloques por frecuencia")[0]
        return out, False
    if formato == "anio_punto_mes":
        return _validar_mensual(s, ordinales)
    if formato == "subperiodos_con_anio":
        return _validar_mensual(s, ordinales, "", "subperíodos con su año")
    out = []
    nums = [numero(y) for y in periodos]
    diferencias = [b - a for a, b in zip(nums, nums[1:]) if a is not None and b is not None]
    # Una secuencia decreciente es una presentación válida. Los duplicados
    # se siguen evaluando aparte; no inferir descenso de un orden mezclado.
    descendente = bool(diferencias) and any(x < 0 for x in diferencias) and all(x <= 0 for x in diferencias)
    paso = -1 if descendente else 1
    anual = sum(x == paso for x in diferencias) >= max(2, len(periodos) - 3)
    for i, y in enumerate(periodos):
        n = nums[i]
        prev = nums[i - 1] if i else None
        regla = None
        if y is None or (isinstance(y, str) and not y.strip()):
            # Celda vacía del encabezado (un año combinado sobre dos columnas): no es un período.
            continue
        if n is None or not n.is_integer():
            regla = "anio_no_entero"
        elif n in nums[:i]:
            regla = "anio_duplicado"
        elif prev is not None and n < prev and not descendente:
            regla = "anios_no_crecientes"
        elif prev is not None and anual and n - prev != paso:
            regla = "discontinuidad_anual"
        if regla:
            out.append(
                hallazgo(
                    s,
                    i,
                    regla,
                    f"Período {y}; secuencia observada {periodos}.",
                    120,
                    {"periodicidad_inferida": "anual" if anual else "no establecida"},
                    accion="Corregir o justificar el período antes de interpretar el tramo afectado.",
                )
            )
    return out, not out


def _tabla_calculada(ordinales, periodos):
    if ordinales:
        claves = list(ordinales)
    else:
        nums = [numero(y) for y in periodos]
        # Sólo años enteros; el duplicado se mide sobre el valor numérico (2019 y 2019.0 son el mismo año).
        claves = [int(n) if n is not None and n.is_integer() else None for n in nums]
        cuenta_num = Counter(n for n in nums if n is not None)
        claves = [k if k is not None and cuenta_num[float(k)] == 1 else None for k in claves]
    cuenta = Counter(k for k in claves if k is not None)
    mapa = {k: i for i, k in enumerate(claves) if k is not None and cuenta[k] == 1}
    return mapa, {i: k for k, i in mapa.items()}


@lru_cache(maxsize=64)
def _tabla_en_cache(ordinales, periodos):
    return _tabla_calculada(ordinales, periodos)


_ultima = threading.local()


def _tabla(s):
    """(período inequívoco → posición, posición → período). Una serie larga llama a esto una vez por punto:
    se calcula una sola vez por secuencia de períodos (antes era cuadrático y un libro grande tardaba horas).
    Los puntos de una misma serie se consultan seguidos: se reconoce la serie por identidad, sin volver a
    armar la clave con todos sus períodos en cada consulta."""
    ordinales = s.get("ordinales") or None
    previa = getattr(_ultima, "valor", None)
    if previa and previa[0] is ordinales and previa[1] is s["periodos"]:
        return previa[2]
    try:
        tabla = _tabla_en_cache(tuple(ordinales) if ordinales else None, None if ordinales else tuple(s["periodos"]))
    except TypeError:  # algún período no hashable: se calcula sin caché
        tabla = _tabla_calculada(ordinales, s["periodos"])
    _ultima.valor = (ordinales, s["periodos"], tabla)
    return tabla


def mapa_periodos(s):
    """Período inequívoco → posición. Se excluyen ambas apariciones de un duplicado.

    Con años, la clave es el año. Con meses o trimestres (series del modelo común) la clave es el
    ordinal del período, de modo que meses consecutivos también son vecinos.
    """
    return dict(_tabla(s)[0])


def ventana_valida(s, indices):
    inverso = _tabla(s)[1]
    indices = list(indices)
    if any(i < 0 or i >= len(s["periodos"]) or i not in inverso for i in indices):
        return False
    anos = [inverso[i] for i in indices]
    # Vecindad anual consecutiva en cualquiera de los dos órdenes válidos.
    # No aceptar saltos, duplicados ni cambios de dirección dentro de la ventana.
    pasos = [b - a for a, b in zip(anos, anos[1:])]
    return all(paso == 1 for paso in pasos) or all(paso == -1 for paso in pasos)


def periodos_ambiguos(s):
    validas = set(_tabla(s)[1])
    return list(dict.fromkeys(str(y) for i, y in enumerate(s["periodos"]) if i not in validas))
