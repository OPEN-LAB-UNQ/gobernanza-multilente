"""Comparación con la edición anterior del mismo informe.

Las series oficiales se republican cada año y cada edición repite los años previos. Cuando se
cargan dos ediciones juntas, un valor histórico que cambia mientras el resto de su serie queda
idéntico es una señal fuerte: o es una corrección que debería estar explicada, o es un error de
carga en la edición nueva. El último año de la edición anterior se excluye porque suele ser
provisorio y se revisa por completo.

Antes de comparar dos cuadros se arma una ficha de comparabilidad (concepto, unidad y escala,
período o corte, cobertura y moneda) con lo que cada cuadro declara en su título y su unidad. Si
las fichas no coinciden, el cruce no se hace: se deja UNA nota «no comparable por …» y ninguna
señal de error de carga. Los cuadros y las filas se emparejan por estructura y por rótulos
equivalentes (no sólo por el nombre exacto de la hoja), y cada cruce informa cuántas filas pudo
emparejar.
"""

import re
from collections import Counter, defaultdict

from .comun import es_numero, hallazgo, normalizar, numero, referencia
from .modelo import es_total

CAMBIO = 0.05  # el valor difiere más de 5 % entre ediciones
IGUAL = 0.005  # el resto de la serie coincide con un margen de 0,5 %
MINIMO_IGUALES = 3
MINIMO_PERIODOS = 4
REVISION_COMPLETA = 0.8  # proporción de períodos que cambian para considerar revisada toda la serie
# Cambio de escala: en todos los años la razón nueva/anterior es la misma potencia de 10.
ESCALAS = (1000.0, 100.0, 10.0, 0.1, 0.01, 0.001)
MARGEN_ESCALA = 0.01  # ±1 %
MINIMO_ESCALA = 3  # tres años con la misma potencia de 10 no ocurren por azar
PRIORIDAD_ESCALA = 110
# Un cuadro en el que cambia la mayoría de las filas (y al menos tres) se informa una sola vez.
MINIMO_FILAS_CUADRO = 3
MAYORIA_CUADRO = 0.5
PRIORIDAD_CUADRO_UNIDAD = 70
PRIORIDAD_CUADRO_REVISADO = 60

REGLA_NO_COMPARABLE = "cruce_no_comparable"
REGLA_COBERTURA = "cobertura_cruce_ediciones"
REGLAS_NOTA = {REGLA_NO_COMPARABLE, REGLA_COBERTURA}

_VACIAS = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "a", "al", "por", "para", "con", "otros", "otras"}


def _rel(a, b):
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


def _indice(series_archivo):
    """Clave estable entre ediciones: hoja, etiqueta y orden de aparición en la hoja."""
    out = {}
    contador = defaultdict(int)
    for s in sorted(series_archivo, key=lambda s: (s["hoja"], s.get("fila") or 0)):
        clave = (s["hoja"], normalizar(s["etiqueta"]))
        out[clave + (contador[clave],)] = s
        contador[clave] += 1
    return out


def _ultimo_periodo(series_archivo):
    anios = [p for s in series_archivo for p in s["periodos"] if isinstance(p, int)]
    return max(anios) if anios else None


def _serie_por_anio(s, tope):
    """Valores por año comparable; el último año de la edición anterior se excluye siempre."""
    out = {}
    for i, p in enumerate(s["periodos"]):
        if isinstance(p, int) and p < tope:
            v = numero(s["valores"][i])
            if v is not None and abs(v) > 0.5:
                out[p] = (i, v)
    return out


def _calce(nueva, vieja):
    """Años comunes y cuántos coinciden dentro del margen de igualdad."""
    comunes = [p for p in nueva if p in vieja]
    iguales = [p for p in comunes if _rel(nueva[p][1], vieja[p][1]) < IGUAL]
    return comunes, iguales


def _factor_escala(pares):
    """Potencia de 10 común a la razón nueva/anterior de todos los años comparables, o None."""
    if len(pares) < MINIMO_ESCALA or any(not b for _, _, _, b in pares):
        return None
    razones = [a / b for _, _, a, b in pares]
    for factor in ESCALAS:
        if all(abs(r / factor - 1) <= MARGEN_ESCALA for r in razones):
            return factor
    return None


def _decimales(v):
    texto = f"{abs(v):.6f}".rstrip("0")
    return len(texto.split(".")[1]) if "." in texto else 0


def _igual_redondeado(publicado, esperado):
    """El valor publicado coincide con el esperado salvo 1 % o el redondeo de su último decimal."""
    tolerancia = max(MARGEN_ESCALA * abs(esperado), 0.5 * 10 ** -_decimales(publicado) + 1e-12)
    return abs(publicado - esperado) <= tolerancia


def _texto_factor(factor):
    if factor >= 1:
        return f"{es_numero(factor, 0)} veces"
    return f"la {({0.1: 'décima', 0.01: 'centésima', 0.001: 'milésima'})[factor]} parte de"


# --------------------------------------------------------------------------------------------
# Ficha de comparabilidad
# --------------------------------------------------------------------------------------------

_ETAPAS = (
    (r"credito vigente|\bvigente\b", "crédito vigente"),
    (r"credito inicial|presupuesto inicial|\bsancionad", "crédito inicial"),
    (r"devengad", "devengado"),
    (r"comprometid", "comprometido"),
    (r"\bpagad", "pagado"),
    (r"recaudad|percibid", "recaudado"),
)
_NATURALEZAS = (
    (r"\b(?:recursos|ingresos)\b", "recursos"),
    (r"\b(?:gastos?|erogacion(?:es)?|egresos)\b", "gastos"),
)
_ADMINISTRACION = (
    (r"administracion publica nacional|\bapn\b", "Administración Pública Nacional"),
    (r"sector publico (?:nacional|no financiero)|\bspn\b", "Sector Público Nacional"),
    (r"administracion central", "Administración Central"),
    (r"administracion nacional", "Administración Nacional"),
    (r"organismos descentralizados", "organismos descentralizados"),
)
_PARCIAL = (
    r"acumulad|\bsemestr|\btrimestr|\bal \d{1,2} de [a-z]+|\bal \d{1,2}/\d{1,2}|\benero\s*(?:-|a)\s*[a-z]+"
    r"|\bprimer (?:semestre|trimestre|cuatrimestre)|\bparcial|\bprovisori|\bmensual|\bhasta (?:el )?\d"
)


def _primera(patrones, texto):
    for patron, valor in patrones:
        if re.search(patron, texto):
            return valor
    return None


def _cobertura_geografica(texto):
    m = re.search(r"provincia (?:de |del )?([a-z ]+?)(?:\s*[-(),;:]|$)", texto)
    if m:
        return "provincia de " + m.group(1).strip()
    m = re.search(r"municipio (?:de |del )?([a-z ]+?)(?:\s*[-(),;:]|$)", texto)
    if m:
        return "municipio de " + m.group(1).strip()
    if re.search(r"\bprovincial(?:es)?\b|\bprovincias\b", texto):
        return "provincias"
    if re.search(r"total (?:del )?pais|\bnacion\b|\btotal nacional\b", texto):
        return "total país"
    return None


def _corte(texto):
    """Período o corte declarado: anual, parcial (y si lo parcial afecta sólo a ciertos años)."""
    anios_parciales = set()
    # «(2022: acumulado al 30/06, provisorio)»: sólo esos años son parciales.
    # Una fecha de corte suelta en el título («acumulado al 30/06/2023») afecta a todo el cuadro;
    # sólo una aclaración entre paréntesis que nombra años restringe el corte a esos años.
    for grupo in re.findall(r"\(([^)]*)\)", texto):
        if re.search(_PARCIAL, grupo):
            anios_parciales |= {int(a) for a in re.findall(r"\b((?:19|20)\d{2})\b", grupo)}
    if re.search(_PARCIAL, texto):
        return ("parcial", frozenset(anios_parciales))
    if re.search(r"\banual\b|ejercicio completo|\banuales\b", texto):
        return ("anual", frozenset())
    return (None, frozenset())


def ficha_cuadro(series_cuadro):
    """Lo que el cuadro declara de sí: concepto, unidad, corte, cobertura y moneda."""
    titulos = Counter(
        (s.get("ficha") or {}).get("ambito") or s.get("ambito") for s in series_cuadro
    )
    titulo = next((t for t, _ in titulos.most_common() if t), None)
    unidades = Counter((s.get("ficha") or {}).get("unidad") or s.get("unidad") for s in series_cuadro)
    unidad = next((u for u, _ in unidades.most_common() if u), None)
    t = normalizar(titulo or "")
    u = normalizar(unidad or "")
    escala = None
    if u.startswith("pesos_"):
        # «pesos_miles_de_millones_corrientes» → «miles_de_millones».
        escala = re.sub(r"_(corrientes|constantes)$", "", u[len("pesos_"):])
    elif u:
        escala = u
    moneda = None
    if "dolar" in t or "usd" in t or "u$s" in t or "dolar" in u:
        moneda = "dólares"
    elif "constante" in t or "constante" in u or re.search(r"precios de \d{4}|\breales\b", t):
        base = re.search(r"constantes? de (\d{4})|precios de (\d{4})", t)
        moneda = "pesos constantes" + (f" de {base.group(1) or base.group(2)}" if base else "")
    elif "corriente" in t or (u.startswith("pesos_") and "constante" not in u):
        # La lectura de la unidad rotula «corrientes» por omisión: sólo es dato si hay unidad.
        moneda = "pesos corrientes"
    corte, anios_parciales = _corte(t)
    return dict(
        titulo=titulo,
        unidad=unidad,
        concepto=_primera(_ETAPAS, t),
        naturaleza=_primera(_NATURALEZAS, t),
        escala=escala,
        moneda=moneda,
        corte=corte,
        anios_parciales=sorted(anios_parciales),
        cobertura=_cobertura_geografica(t),
        administracion=_primera(_ADMINISTRACION, t),
    )


_MAGNITUDES = {"unidades", "miles", "millones", "miles_de_millones"}

_DIMENSIONES = (
    ("concepto", "concepto"),
    ("naturaleza", "concepto"),
    ("escala", "unidad y escala"),
    ("moneda", "moneda"),
    ("cobertura", "cobertura"),
    ("administracion", "cobertura"),
)


def comparabilidad(fa, fn):
    """Motivos de no comparabilidad (vacío si ambas fichas son compatibles) y años excluidos.

    Sólo se afirma una diferencia cuando las dos fichas declaran algo distinto: una ficha
    silenciosa no prueba que el cuadro sea otro, pero tampoco se la presenta como verificada.
    """
    motivos = []
    for clave, nombre in _DIMENSIONES:
        a, b = fa.get(clave), fn.get(clave)
        if clave == "escala" and a in _MAGNITUDES and b in _MAGNITUDES:
            # Millones frente a miles de millones es el mismo cuadro en otra escala: se compara y,
            # si el factor coincide, se informa como cambio de unidad (una sola señal), no como otro cuadro.
            continue
        if a and b and a != b:
            motivos.append(dict(dimension=nombre, anterior=a, nueva=b))
    excluidos = set()
    ca, cn = fa.get("corte"), fn.get("corte")
    if ca == "parcial" and fa.get("anios_parciales") and cn != "parcial":
        excluidos |= set(fa["anios_parciales"])
    elif cn == "parcial" and fn.get("anios_parciales") and ca != "parcial":
        excluidos |= set(fn["anios_parciales"])
    elif (ca or cn) and ca != cn:
        motivos.append(dict(dimension="período o corte", anterior=ca or "sin corte parcial declarado",
                            nueva=cn or "sin corte parcial declarado"))
    return motivos, excluidos


# --------------------------------------------------------------------------------------------
# Emparejamiento de cuadros y filas
# --------------------------------------------------------------------------------------------

def _cuadros(series_archivo):
    out = defaultdict(list)
    for s in series_archivo:
        out[(s["hoja"], s.get("cuadro"))].append(s)
    for clave in out:
        out[clave].sort(key=lambda s: s.get("fila") or 0)
    return dict(out)


def _tokens(texto):
    t = re.sub(r"[^a-z0-9 ]", " ", normalizar(texto))
    return {w for w in t.split() if w not in _VACIAS and not re.fullmatch(r"(?:19|20)\d{2}", w)}


def _anios_rotulo(texto):
    """Años que nombra un rótulo («En millones de $ 2018»): una base de precios distinta es otra serie."""
    return frozenset(re.findall(r"\b(?:19|20)\d{2}\b", normalizar(texto)))


def _rotulo(texto):
    return " ".join(sorted(_tokens(texto))) + "|" + " ".join(sorted(_anios_rotulo(texto)))


def _similitud_hoja(a, b):
    if normalizar(a) == normalizar(b):
        return 1.0
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _emparejar_filas(viejas, nuevas, tope):
    """Pares (vieja, nueva) por rótulo exacto, rótulo equivalente y, si no, por valores.

    Devuelve los pares y cuántos se emparejaron por cada vía.
    """
    pares, usadas_v, usadas_n = [], set(), set()
    vias = Counter()

    def emparejar(clave):
        grupos_v, grupos_n = defaultdict(list), defaultdict(list)
        for i, s in enumerate(viejas):
            if i not in usadas_v:
                grupos_v[clave(s)].append(i)
        for j, s in enumerate(nuevas):
            if j not in usadas_n:
                grupos_n[clave(s)].append(j)
        hechos = 0
        for k, iv in grupos_v.items():
            if not k or k not in grupos_n:
                continue
            for i, j in zip(iv, grupos_n[k]):  # mismo rótulo repetido: por orden de aparición
                pares.append((viejas[i], nuevas[j]))
                usadas_v.add(i)
                usadas_n.add(j)
                hechos += 1
        return hechos

    vias["rótulo idéntico"] += emparejar(lambda s: normalizar(s["etiqueta"]))
    vias["rótulo equivalente"] += emparejar(lambda s: _rotulo(s["etiqueta"]))
    # Rótulo contenido en el otro («Salud» y «Servicios de salud»), sólo si es recíproco y único.
    candidatos = defaultdict(list)
    for i, v in enumerate(viejas):
        if i in usadas_v:
            continue
        tv = _tokens(v["etiqueta"])
        for j, n in enumerate(nuevas):
            if j in usadas_n:
                continue
            tn = _tokens(n["etiqueta"])
            if tv and tn and (tv <= tn or tn <= tv) and _anios_rotulo(v["etiqueta"]) == _anios_rotulo(n["etiqueta"]):
                candidatos[i].append(j)
    inversos = defaultdict(list)
    for i, js in candidatos.items():
        for j in js:
            inversos[j].append(i)
    for i, js in candidatos.items():
        if len(js) == 1 and len(inversos[js[0]]) == 1:
            pares.append((viejas[i], nuevas[js[0]]))
            usadas_v.add(i)
            usadas_n.add(js[0])
            vias["rótulo contenido"] += 1
    # Sin rótulo reconocible: la misma serie publicada en los años comunes.
    candidatos = defaultdict(list)
    for i, v in enumerate(viejas):
        if i in usadas_v:
            continue
        sv = _serie_por_anio(v, tope)
        for j, n in enumerate(nuevas):
            if j in usadas_n:
                continue
            comunes, iguales = _calce(_serie_por_anio(n, tope), sv)
            if len(comunes) >= MINIMO_IGUALES and len(iguales) >= max(MINIMO_IGUALES, len(comunes) - 1):
                candidatos[i].append(j)
    inversos = defaultdict(list)
    for i, js in candidatos.items():
        for j in js:
            inversos[j].append(i)
    for i, js in candidatos.items():
        if len(js) == 1 and len(inversos[js[0]]) == 1:
            pares.append((viejas[i], nuevas[js[0]]))
            usadas_v.add(i)
            usadas_n.add(js[0])
            vias["valores coincidentes"] += 1
    return pares, vias


def _acuerdo(pares, tope):
    """Proporción de filas emparejadas que publican la misma serie en los años comunes."""
    con_datos = iguales = 0
    for v, n in pares:
        comunes, coinciden = _calce(_serie_por_anio(n, tope), _serie_por_anio(v, tope))
        if comunes:
            con_datos += 1
            iguales += len(coinciden) == len(comunes)
    return iguales / con_datos if con_datos else 0.0


def _posiciones(cuadros):
    """Lugar de cada cuadro dentro de su hoja (por la fila en que empieza)."""
    por_hoja = defaultdict(list)
    for k, ss in cuadros.items():
        por_hoja[k[0]].append((min((s.get("fila") or 0) for s in ss), str(k[1]), k))
    return {k: i for lista in por_hoja.values() for i, (_, _, k) in enumerate(sorted(lista))}


def _emparejar_cuadros(cuadros_ant, cuadros_nue, tope):
    """Cada cuadro anterior con el cuadro nuevo de mayor afinidad.

    La afinidad suma la proporción de filas emparejadas (sobre el cuadro más grande, para que un
    cuadro de una fila no se quede con uno de doce; por rótulo valen más que sólo por valores),
    cuántas de las emparejadas por rótulo publican la misma serie en los años comunes (desempata
    cuadros con los mismos rótulos, como las aperturas Nación, Provincias y Consolidado de una
    misma hoja), la semejanza del nombre de hoja y el lugar del cuadro dentro de su hoja.
    """
    puntajes = []
    lugar_a, lugar_n = _posiciones(cuadros_ant), _posiciones(cuadros_nue)
    for ka, sa in cuadros_ant.items():
        for kn, sn in cuadros_nue.items():
            hoja = _similitud_hoja(ka[0], kn[0])
            pares, vias = _emparejar_filas(sa, sn, tope)
            if not pares and hoja < 1:
                continue
            # Las filas emparejadas por rótulo pesan más que las emparejadas sólo por valores, y el
            # acuerdo de valores se mide sólo sobre ellas: si dos filas intercambiaron sus series,
            # los valores no deben arrastrar cada cuadro hacia el rótulo equivocado.
            por_valores = vias.get("valores coincidentes", 0)
            por_rotulo = pares[: len(pares) - por_valores]
            total = max(1, len(sa), len(sn))
            filas = (2 * len(por_rotulo) + 0.5 * por_valores) / total
            acuerdo = _acuerdo(por_rotulo, tope)
            lugar = 0.25 if hoja == 1 and lugar_a[ka] == lugar_n[kn] else 0
            puntajes.append((filas + acuerdo + hoja + lugar, ka, kn))
    usados_a, usados_n, out = set(), set(), []
    for puntaje, ka, kn in sorted(puntajes, key=lambda x: (-x[0], str(x[1]), str(x[2]))):
        if ka in usados_a or kn in usados_n:
            continue
        usados_a.add(ka)
        usados_n.add(kn)
        out.append((ka, kn))
    sin_pareja = [ka for ka in cuadros_ant if ka not in usados_a]
    return out, sin_pareja


# --------------------------------------------------------------------------------------------
# Notas y señales de cuadro
# --------------------------------------------------------------------------------------------

def _nota(s, regla, detalle, calculo, participantes=None):
    """Nota de cruce: contexto para el registro de lo revisado, nunca una señal de error."""
    ev = dict(
        archivo_origen=s["archivo"],
        hoja=s["hoja"],
        bloque_excel=s.get("cuadro"),
        celda=s["celdas"][0] if s.get("celdas") else None,
        indicador=None,
        periodo=None,
        regla=regla,
        naturaleza="contexto",
        nota_cruce=True,
        puntaje_prioridad=0,
        factores_prioridad=[{"criterio": regla, "puntos": 0}],
        ubicaciones_excel=[referencia(s, 0)] if s.get("celdas") else [],
        celdas_participantes=participantes or ([referencia(s, 0)] if s.get("celdas") else []),
        accion_revision=calculo.pop("accion", None) or "Sin acción sobre los datos: es una nota sobre el alcance del cruce.",
        **calculo,
    )
    return dict(
        lente="cronista",
        modo="control_tabular",
        severidad="baja",
        descripcion=f"{s['hoja']} · cuadro {s.get('cuadro')}: {detalle}",
        pregunta_institucional=ev["accion_revision"],
        metodo="Cruce entre ediciones: ficha de comparabilidad y emparejamiento de filas documentados en evidencia",
        evidencia=ev,
    )


def _texto_ficha(f):
    return {k: v for k, v in f.items() if v not in (None, [], "")}


def _nota_no_comparable(actual, anterior, nueva, motivos, fa, fn):
    partes = "; ".join(f"{m['dimension']}: «{m['anterior']}» en {anterior} y «{m['nueva']}» en {nueva}" for m in motivos)
    dimensiones = list(dict.fromkeys(m["dimension"] for m in motivos))
    return _nota(
        actual,
        REGLA_NO_COMPARABLE,
        f"No comparable por {' y '.join(dimensiones)} con la edición anterior ({anterior}): {partes}. "
        "No se compararon sus valores y no se emiten señales de cambio entre ediciones para este cuadro.",
        dict(
            archivo_edicion_anterior=anterior,
            motivos_no_comparable=motivos,
            dimensiones_no_comparables=dimensiones,
            ficha_anterior=_texto_ficha(fa),
            ficha_nueva=_texto_ficha(fn),
            accion="Si los cuadros deben compararse, cargar ediciones con el mismo concepto, unidad, corte, cobertura y moneda, o declarar la equivalencia.",
        ),
    )


def _nota_cobertura(actual, anterior, viejas, nuevas, pares, vias, con_diferencias, excluidos, hoja_anterior):
    total = max(len(viejas), len(nuevas))
    detalle_vias = ", ".join(f"{n} por {v}" for v, n in vias.items() if n)
    texto = (
        f"Cruce con la edición anterior ({anterior}, hoja «{hoja_anterior}»): {len(pares)} de {total} filas emparejadas"
        + (f" ({detalle_vias})" if detalle_vias else "")
        + (f"; {con_diferencias} con diferencias en los años comunes." if pares else ".")
    )
    if excluidos:
        texto += f" Excluidos del cruce por corte parcial declarado: {', '.join(map(str, sorted(excluidos)))}."
    sin_pareja = [s["etiqueta"] for s in nuevas if all(s is not n for _, n in pares)]
    if sin_pareja:
        texto += f" Sin pareja en la edición anterior: {', '.join(sin_pareja[:6])}."
    return _nota(
        actual,
        REGLA_COBERTURA,
        texto,
        dict(
            archivo_edicion_anterior=anterior,
            hoja_edicion_anterior=hoja_anterior,
            filas_emparejadas=len(pares),
            filas_totales=total,
            filas_anteriores=len(viejas),
            filas_nuevas=len(nuevas),
            vias_emparejamiento=dict(vias),
            filas_con_diferencias=con_diferencias,
            filas_sin_pareja=sin_pareja,
            anios_excluidos=sorted(excluidos),
        ),
    )


def _senal_cuadro(actual, anterior, cambios, filas_comparadas):
    """Una sola señal para un cuadro que cambió casi entero: revisión global o cambio de unidad."""
    razones = [a / b for _, _, _, a, b in cambios if b]
    razones.sort()
    mediana = razones[len(razones) // 2] if razones else None
    comun = bool(mediana) and all(abs(r / mediana - 1) <= MARGEN_ESCALA for r in razones)
    # Una potencia de 10 explica el cuadro si cada valor nuevo es el anterior por ese factor, salvo el
    # redondeo con que se publicó (4.100 millones → 4,1 miles de millones).
    factor = next(
        (f for f in ESCALAS if razones and all(b and _igual_redondeado(a, b * f) for _, _, _, a, b in cambios)),
        None,
    )
    comun = comun or bool(factor)
    filas = len({id(s) for s, *_ in cambios})
    s0, j0, p0, a0, b0 = cambios[0]
    participantes = list(dict.fromkeys(referencia(s, j) for s, j, *_ in cambios))
    if factor:
        regla, puntos = "cambio_de_unidad_entre_ediciones", PRIORIDAD_CUADRO_UNIDAD
        detalle = (
            f"Cambio de unidad del cuadro: en {filas} de {filas_comparadas} filas cada valor es {_texto_factor(factor)} "
            f"el publicado en la edición anterior ({anterior}); por ejemplo «{s0['etiqueta']}» {p0}: {es_numero(b0)} → {es_numero(a0)}. "
            "El cuadro parece expresado en otra unidad o escala (por ejemplo, miles de millones en lugar de millones)."
        )
        accion = "Confirmar la unidad declarada de cada edición y expresar ambas en la misma escala antes de comparar valores."
    elif comun:
        regla, puntos = "cuadro_reexpresado_entre_ediciones", PRIORIDAD_CUADRO_REVISADO
        detalle = (
            f"Cuadro reexpresado: en {filas} de {filas_comparadas} filas los valores difieren de la edición anterior ({anterior}) "
            f"por un mismo factor ({es_numero(mediana, 4)}); por ejemplo «{s0['etiqueta']}» {p0}: {es_numero(b0)} → {es_numero(a0)}. "
            "Suele indicar un cambio de base, de moneda o de deflactor."
        )
        accion = "Confirmar la base o moneda de cada edición antes de comparar valores."
    else:
        regla, puntos = "cuadro_revisado_entre_ediciones", PRIORIDAD_CUADRO_REVISADO
        detalle = (
            f"Revisión global del cuadro: cambiaron {filas} de {filas_comparadas} filas respecto de la edición anterior "
            f"({anterior}); por ejemplo «{s0['etiqueta']}» {p0}: {es_numero(b0)} → {es_numero(a0)}. Un cambio tan extendido "
            "corresponde a una revisión metodológica, de cobertura o de concepto más que a errores de carga fila por fila."
        )
        accion = "Confirmar si la edición nueva revisó el cuadro completo y con qué criterio documentado."
    h = hallazgo(
        s0,
        j0,
        regla,
        detalle,
        puntos,
        calculo=dict(
            archivo_edicion_anterior=anterior,
            filas_cambiadas=filas,
            filas_comparadas=filas_comparadas,
            factor_comun=mediana if comun else None,
            factor_escala=factor,
            alcance_senal="cuadro",
            valor_edicion_anterior=b0,
        ),
        participantes=participantes,
        accion=accion,
        lente="cronista",
    )
    h["severidad"] = "media"
    return h


def _cambio_de_escala(actual, pares, factor, anterior):
    j, p, a, b = pares[0]
    return hallazgo(
        actual,
        j,
        "cambio_de_escala_entre_ediciones",
        f"Cambio de escala: en los {len(pares)} años comunes con la edición anterior ({anterior}) cada valor de "
        f"«{actual['etiqueta']}» es {_texto_factor(factor)} el publicado antes (por ejemplo {p}: {es_numero(b)} → "
        f"{es_numero(a)}), mientras el resto del cuadro no cambió. Lo más probable es que la fila haya quedado en "
        "otra unidad (unidades, miles o millones) que el resto del cuadro.",
        PRIORIDAD_ESCALA,
        calculo=dict(
            factor_escala=factor,
            periodos_comparables=len(pares),
            archivo_edicion_anterior=anterior,
            valor_edicion_anterior=b,
        ),
        participantes=[referencia(actual, x[0]) for x in pares],
        accion="Confirmar la unidad de la fila y expresarla en la misma escala que el resto del cuadro y que la edición anterior.",
        lente="cronista",
    )


def _movida(actual, vieja_propia, candidatas, tope):
    """La serie nueva reproduce exactamente la que la edición anterior publicaba en otra fila.

    No es una afirmación estadística: que una serie entera coincida con la de otro rubro del año
    pasado, y no con la suya, no ocurre por azar. Por eso alcanzan tres años comunes.
    """
    nueva = _serie_por_anio(actual, tope)
    if len(nueva) < MINIMO_IGUALES or len({v for _, v in nueva.values()}) < 2:
        return None
    # Sin su propia fila en la edición anterior no hay con qué afirmar que la serie se movió.
    if not vieja_propia:
        return None
    comunes, iguales = _calce(nueva, _serie_por_anio(vieja_propia, tope))
    if not comunes or len(iguales) > len(comunes) - MINIMO_IGUALES:
        return None  # la serie sigue siendo la suya
    coincidencias = []
    for otra in candidatas:
        if otra is vieja_propia or normalizar(otra["etiqueta"]) == normalizar(actual["etiqueta"]):
            continue
        # Una fila se confunde con otra del mismo cuadro; un total que coincide con el indicador
        # de la hoja es otra cosa y no se afirma nada sobre él.
        if otra.get("cuadro") != vieja_propia.get("cuadro"):
            continue
        comunes, iguales = _calce(nueva, _serie_por_anio(otra, tope))
        if len(comunes) >= MINIMO_IGUALES and len(iguales) == len(comunes):
            coincidencias.append(otra)
    # Si la serie aparece repetida —dos filas con los mismos valores— la coincidencia no dice de
    # dónde vino: los cuadros repiten aperturas y un rubro puede igualar a su único hijo.
    return coincidencias[0] if len(coincidencias) == 1 else None


def _series_movidas(pares_filas, viejas, tope, anterior):
    """Filas que tomaron la serie de otra fila; si el cambio es mutuo, se informa como intercambio."""
    vieja_de = {id(n): v for v, n in pares_filas}
    nueva_de = {id(v): n for v, n in pares_filas}
    movidas = {}
    for vieja, actual in pares_filas:
        otra = _movida(actual, vieja, viejas, tope)
        if otra:
            movidas[id(actual)] = (actual, otra)
    out, usados = [], set()
    for clave, (actual, otra) in movidas.items():
        if clave in usados:
            continue
        companera_nueva = nueva_de.get(id(otra))
        pareja = None
        if companera_nueva is not None and id(companera_nueva) in movidas:
            if movidas[id(companera_nueva)][1] is vieja_de.get(id(actual)):
                pareja = id(companera_nueva)
        i = next((k for k, v in enumerate(actual["valores"]) if numero(v) is not None), 0)
        celdas = [referencia(actual, k) for k, v in enumerate(actual["valores"]) if numero(v) is not None]
        if pareja:
            usados |= {clave, pareja}
            companera = movidas[pareja][0]
            celdas += [referencia(companera, k) for k, v in enumerate(companera["valores"]) if numero(v) is not None]
            out.append(
                hallazgo(
                    actual,
                    i,
                    "series_intercambiadas_entre_ediciones",
                    f"«{actual['etiqueta']}» repite la serie que la edición anterior ({anterior}) publicaba en "
                    f"«{companera['etiqueta']}», y esa fila repite la de esta. Las dos filas parecen intercambiadas.",
                    90,
                    calculo=dict(
                        archivo_edicion_anterior=anterior,
                        serie_intercambiada=companera["etiqueta"],
                        celda_edicion_anterior=referencia(otra, 0),
                    ),
                    participantes=celdas,
                    accion="Confirmar si las dos filas quedaron intercambiadas al armar esta edición.",
                    lente="cronista",
                )
            )
            continue
        usados.add(clave)
        out.append(
            hallazgo(
                actual,
                i,
                "serie_de_otro_rubro_entre_ediciones",
                f"«{actual['etiqueta']}» repite exactamente la serie que la edición anterior ({anterior}) publicaba "
                f"en «{otra['etiqueta']}», y ya no la suya.",
                85,
                calculo=dict(
                    archivo_edicion_anterior=anterior,
                    serie_de_origen=otra["etiqueta"],
                    celda_edicion_anterior=referencia(otra, 0),
                ),
                participantes=celdas,
                accion="Confirmar de qué fila corresponde cada serie en esta edición.",
                lente="cronista",
            )
        )
    return out


def _revisada(actual, pares_o_distintos, total, anterior):
    j, p, a, b = pares_o_distintos[0]
    return hallazgo(
        actual,
        j,
        "serie_revisada_entre_ediciones",
        f"«{actual['etiqueta']}» cambió en {len(pares_o_distintos)} de {total} años comunes con la "
        f"edición anterior ({anterior}); por ejemplo {p}: {es_numero(b)} → {es_numero(a)}. Puede ser una revisión "
        "metodológica o una fila reemplazada por otra.",
        75,
        calculo=dict(
            periodos_cambiados=len(pares_o_distintos),
            periodos_comparables=total,
            archivo_edicion_anterior=anterior,
            valor_edicion_anterior=b,
        ),
        participantes=[referencia(actual, x[0]) for x in pares_o_distintos],
        accion="Confirmar si la serie fue revisada con un criterio documentado o si la fila quedó reemplazada.",
        lente="cronista",
    )


def _comparar_cuadro(pares_filas, viejas, tope, excluidos, anterior):
    """Señales del cruce de un cuadro ya emparejado y comparable. Devuelve (señales, filas con diferencias)."""
    out = []
    candidatos = []
    revisadas = []
    cambios_por_columna = defaultdict(int)
    filas_comparadas = 0
    cambiadas = 0
    cambios_cuadro = []  # (serie, j, p, a, b) de filas con cambios propios
    escalas = []
    for viejo, actual in pares_filas:
        pares = []
        for j, p in enumerate(actual["periodos"]):
            if not isinstance(p, int) or p >= tope or p in excluidos or p not in viejo["periodos"]:
                continue
            a = numero(actual["valores"][j])
            b = numero(viejo["valores"][viejo["periodos"].index(p)])
            if a is not None and b is not None and max(abs(a), abs(b)) > 0.5:
                pares.append((j, p, a, b))
        distintos = [x for x in pares if _rel(x[2], x[3]) > 0.01]
        formulas = actual.get("formulas") or [False] * len(actual["valores"])
        if actual.get("formulas_desconocidas"):
            # Sin fórmulas legibles (.xls binario): un «Total» o «Subtotal» se trata como calculado, que
            # cambia por arrastre; no cuenta como cambio propio.
            formulas = [es_total(actual.get("etiqueta"))] * len(actual["valores"])
        if pares:
            filas_comparadas += 1
            # Una celda con fórmula («Resto», «Total») cambia por arrastre: no cuenta como cambio propio.
            propios = [x for x in distintos if not formulas[x[0]]]
            if propios:
                cambiadas += 1
                cambios_cuadro.extend((actual, j, p, a, b) for j, p, a, b in propios)
        factor = _factor_escala(pares)
        if factor:
            escalas.append((actual, pares, factor, len(distintos) >= REVISION_COMPLETA * len(pares)))
            if len(pares) < MINIMO_PERIODOS:
                # Igual que antes: con pocos años, sus cambios cuentan para la revisión del año.
                for j, p, a, b in pares:
                    if _rel(a, b) > CAMBIO and not formulas[j]:
                        cambios_por_columna[p] += 1
            continue
        if len(pares) >= MINIMO_PERIODOS and len(distintos) >= REVISION_COMPLETA * len(pares):
            # Toda la serie cambió: es una revisión o una fila que quedó reemplazada.
            revisadas.append(_revisada(actual, distintos, len(pares), anterior))
            continue
        for j, p, a, b in pares:
            if _rel(a, b) <= CAMBIO:
                continue
            # Las celdas con fórmula cambian por arrastre: no indican una revisión del año.
            if not formulas[j]:
                cambios_por_columna[p] += 1
            iguales = [x for x in pares if x[0] != j and _rel(x[2], x[3]) < IGUAL]
            if len(iguales) < MINIMO_IGUALES or len(iguales) < len(pares) - 2:
                continue  # la serie se revisó en varios años: revisión metodológica, no un valor aislado
            candidatos.append((actual, viejo, j, p, a, b, iguales))
    # Si cambió la mayoría de las filas del cuadro, es UNA señal de cuadro y no una por fila.
    if cambiadas >= MINIMO_FILAS_CUADRO and cambiadas > MAYORIA_CUADRO * filas_comparadas and cambios_cuadro:
        return [_senal_cuadro(cambios_cuadro[0][0], anterior, cambios_cuadro, filas_comparadas)], cambiadas
    out += _series_movidas(pares_filas, viejas, tope, anterior)
    for actual, pares, factor, revisada in escalas:
        if cambiadas == 1 and filas_comparadas >= 2:
            # Sólo esta fila cambió, y en la misma potencia de 10 todos los años: cambio de escala.
            out.append(_cambio_de_escala(actual, pares, factor, anterior))
        elif revisada and len(pares) >= MINIMO_PERIODOS:
            # Todo el cuadro se reexpresó (o cambió con ella): se informa como revisión, igual que antes.
            revisadas.append(_revisada(actual, pares, len(pares), anterior))
    out.extend(revisadas)
    for actual, viejo, j, p, a, b, iguales in candidatos:
        if cambios_por_columna[p] > 2:
            continue  # varios rubros del mismo año cambiaron: revisión del año, no un valor aislado
        k = viejo["periodos"].index(p)
        out.append(
            hallazgo(
                actual,
                j,
                "cambio_entre_ediciones",
                f"En la edición anterior ({anterior}) el valor de {p} era {es_numero(b)}; en esta es {es_numero(a)} "
                f"({es_numero(a / b) if b else 'infinitas'} veces). El resto de la serie no cambió.",
                75,  # prioridad media: muchas revisiones entre ediciones son correcciones legítimas
                calculo=dict(
                    valor_edicion_anterior=b,
                    archivo_edicion_anterior=anterior,
                    celda_edicion_anterior=referencia(viejo, k),
                    periodos_sin_cambio=len(iguales),
                    rotulo_edicion_anterior=viejo["etiqueta"],
                ),
                participantes=[referencia(actual, j), f"{anterior}:{referencia(viejo, k)}"],
                accion="Confirmar si es una corrección documentada del dato publicado o un error de carga en la edición nueva.",
                lente="cronista",
            )
        )
    return out, cambiadas


def analizar(series):
    por_archivo = defaultdict(list)
    for s in series:
        por_archivo[s["archivo"]].append(s)
    if len(por_archivo) < 2:
        return []
    ediciones = sorted(por_archivo, key=lambda a: _ultimo_periodo(por_archivo[a]) or 0)
    nueva = ediciones[-1]
    ultimo_nueva = _ultimo_periodo(por_archivo[nueva])
    cuadros_nue = _cuadros(por_archivo[nueva])
    out = []
    for anterior in ediciones[:-1]:
        ultimo_anterior = _ultimo_periodo(por_archivo[anterior])
        if not ultimo_anterior or ultimo_anterior >= ultimo_nueva:
            continue  # misma edición o sin orden claro
        cuadros_ant = _cuadros(por_archivo[anterior])
        emparejados, sin_pareja = _emparejar_cuadros(cuadros_ant, cuadros_nue, ultimo_anterior)
        for ka, kn in emparejados:
            viejas, nuevas = cuadros_ant[ka], cuadros_nue[kn]
            fa, fn = ficha_cuadro(viejas), ficha_cuadro(nuevas)
            motivos, excluidos = comparabilidad(fa, fn)
            if motivos:
                out.append(_nota_no_comparable(nuevas[0], anterior, nueva, motivos, fa, fn))
                continue
            pares, vias = _emparejar_filas(viejas, nuevas, ultimo_anterior)
            senales, con_diferencias = _comparar_cuadro(pares, viejas, ultimo_anterior, excluidos, anterior)
            out.extend(senales)
            out.append(_nota_cobertura(nuevas[0], anterior, viejas, nuevas, pares, vias, con_diferencias, excluidos, ka[0]))
        for ka in sin_pareja:
            viejas = cuadros_ant[ka]
            out.append(
                _nota(
                    viejas[0],
                    REGLA_COBERTURA,
                    f"Cruce con la edición nueva ({nueva}): 0 de {len(viejas)} filas emparejadas; ningún cuadro de la "
                    "edición nueva tiene hoja, rótulos o valores equivalentes a este.",
                    dict(archivo_edicion_nueva=nueva, filas_emparejadas=0, filas_totales=len(viejas),
                         filas_anteriores=len(viejas), filas_nuevas=0, vias_emparejamiento={}, filas_con_diferencias=0,
                         filas_sin_pareja=[s["etiqueta"] for s in viejas], anios_excluidos=[]),
                )
            )
    return out
