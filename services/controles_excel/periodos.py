"""Rótulos de período reconocidos por su contenido, no por el nombre de la columna.

Un período es un año («2024», «2024 (p)», «2023*», «Ejercicio 2025», «30/06/2025»), un mes
(«Ene», «enero 2025», «2025-01», «01/2025», una fecha), un trimestre («T1», «1T 2025»,
«2025-T1», «Ejec. acum. T2»), o un semestre. Cada rótulo se traduce a un ordinal entero que
permite comparar vecindad y orden sin importar la frecuencia. Las marcas («p», «e», «*»,
«provisorio», «estimado») se conservan como metadato: no vuelven inválido el año.
"""

import datetime as _dt
import re

from .comun import normalizar, numero

MESES = {
    "ene": 1, "enero": 1, "jan": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3, "abr": 4, "abril": 4, "apr": 4,
    "may": 5, "mayo": 5, "jun": 6, "junio": 6, "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "aug": 8,
    "sep": 9, "sept": 9, "set": 9, "septiembre": 9, "setiembre": 9, "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12, "dec": 12,
}
FRECUENCIA = {"anual": 1, "semestral": 2, "trimestral": 4, "bimestral": 6, "mensual": 12}
ROMANOS = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
# Bimestre: dos meses consecutivos, el primero impar («Ene-feb 24», «mar/abr 2025»).
BIM = re.compile(r"^(?P<m1>[a-z]{3,10})\.?\s*[-/]\s*(?P<m2>[a-z]{3,10})\.?(?:\s*[-/ ]?\s*(?P<y>(?:19|20)?\d{2}))?$", re.I)
# Prefijo que R agrega a los nombres de columna que empiezan con un número («X2017»).
PREFIJO_R = re.compile(r"^X(?=\d)")

# Marca de provisorio o estimado: «2025 (p)», «2025p», «2025*», «2025 prov.», «2025 (e)», «2025 est.»;
# también una llamada de nota «2025 (1)» o «2025¹», que tampoco cambia el período.
_MARCA = r"(?P<marca>\(\s*\d\s*\)|[¹²³⁴⁵]|\(?\s*(?:p|e|r|\*+|prov\.?|provisori[oa]s?|est\.?|estim\.?|estimad[oa]s?|prel\.?|prelim\.?|preliminar(?:es)?|proy\.?|proyectad[oa]s?)\s*\)?\.?)"
ANIO_MARCA = re.compile(rf"^(?:ejercicio|año|ano|anio|periodo)?\s*(?P<y>(?:18|19|20|21)\d{{2}})\s*{_MARCA}?\s*$", re.I)
MES_ANIO = re.compile(r"^(?P<m>[a-z]{3,10})\.?(?:\s*[-/ ]\s*(?P<y>(?:19|20)?\d{2}))?$", re.I)
# También el código SDMX «2025M01».
ISO_MES = re.compile(r"^(?P<y>(?:19|20)\d{2})(?:\s*[-/.]\s*|m)(?P<m>0?[1-9]|1[0-2])$", re.I)
MES_ISO = re.compile(r"^(?P<m>0?[1-9]|1[0-2])\s*[-/.]\s*(?P<y>(?:19|20)\d{2})$")
FECHA = re.compile(r"^(?P<d>[0-3]?\d)\s*[-/.]\s*(?P<m>[01]?\d)\s*[-/.]\s*(?P<y>(?:19|20)\d{2})$")
TRIM = re.compile(
    r"^(?:(?P<y1>(?:19|20)\d{2})\s*[-/ ]?\s*)?"
    r"(?:(?:t|q|trim(?:estre)?\.?)\s*(?P<q1>[1-4])|(?P<q2>[1-4])\s*(?:°|º|o|er|do|ro|to)?\.?\s*(?:t|q|trim(?:estre)?\.?)|(?P<q3>i{1,3}|iv)\s*(?:trim(?:estre)?\.?|t))"
    r"(?:\s*[-/ ]?\s*(?P<y2>(?:19|20)\d{2}))?$",
    re.I,
)
# Trimestre de las planillas de un ministerio y un instituto de estadística: romano y año de dos o cuatro dígitos («I-94», «III 01», «IV  99»,
# «I93», «II-2000»), o «1T93» / «4T-01». Con dos dígitos el año va del 50 al 49 (1950–2049): las series empiezan
# en los ochenta y cruzan el 2000 sin cortar el orden.
TRIM_ROMANO = re.compile(r"^(?:(?P<r>i{1,3}|iv)|(?P<n>[1-4])\s*t)\s*[-/. ]?\s*(?P<y>\d{2}|(?:19|20)\d{2})$", re.I)
# Una fecha guardada como texto («2020-08-01», «2020-08-01 00:00:00»): el mes de esa fecha, como una fecha de Excel.
FECHA_ISO = re.compile(r"^(?P<y>(?:19|20)\d{2})-(?P<m>0[1-9]|1[0-2])-(?P<d>[0-3]\d)(?:[ t]00:00(?::00)?)?$")
SEM = re.compile(
    r"^(?:(?P<y1>(?:19|20)\d{2})\s*[-/ ]?\s*)?(?:(?:s|sem(?:estre)?\.?)\s*(?P<s1>[12])|(?P<s2>[12])\s*(?:°|º|o|er|do)?\.?\s*(?:s|sem(?:estre)?\.?))"
    r"(?:\s*[-/ ]?\s*(?P<y2>(?:19|20)\d{2}))?$",
    re.I,
)
# Marca de provisorio o llamada de nota dentro de un rótulo de subperíodo: «2024T4*», «2023 (1) 4º trimestre».
MARCA_INTERNA = re.compile(r"\s*(?:\(\s*\d\s*\)|\*+|[¹²³⁴⁵]|\(\s*(?:p|e|r)\s*\))\s*")
# Anotación final entre paréntesis o corchetes con letras (no una marca de provisorio).
ANOTACION = re.compile(r"^(?P<base>[^()\[\]]*?\S)\s*[\(\[](?P<nota>[^()\[\]]*[a-z%$][^()\[\]]*)[\)\]]\s*\.?$")
_MARCA_SOLA = re.compile(r"\s*(?:\d|p|e|r|\*+|prov\.?|provisori[oa]s?|est\.?|estim\.?|estimad[oa]s?|prel\.?|prelim\.?|preliminar(?:es)?|proy\.?|proyectad[oa]s?)\s*\.?", re.I)
# Prefijos descriptivos que acompañan al período en el rótulo de una columna.
PREFIJO = re.compile(r"^(?:ejec(?:ucion|utado)?\.?|acum(?:ulad[oa])?\.?|al|a|hasta|cierre|saldo|total|real|programad[oa]|ejercicio|periodo|año|ano|anio|mes)\s+", re.I)
ACUMULADO = re.compile(r"acum|a la fecha|al cierre|hasta", re.I)
# Columnas que acompañan a los períodos sin ser períodos: «CV (%)», «Error estándar», «Var. %», «IC 95 %».
AUXILIAR = re.compile(
    r"^(?:c\.?\s*v\.?|coef\.?(?:iciente)?\s*(?:de\s*)?var\.?(?:iacion)?|error\s*(?:estandar|tipico|muestral)"
    r"|e\.\s*e\.?|desv(?:\.|io|iacion)?(?:\s*(?:estandar|tipica))?|intervalo(?:\s*de\s*confianza)?"
    r"|i\.?\s*c\.?(?:\s*\d{2}\s*%)?|lim\.?(?:ite)?\s*(?:inf|sup)\.?(?:erior)?"
    r"|var\.?(?:iacion)?(?:\s*(?:%|porcentual|interanual|i\.?\s*a\.?))?|%|part\.?(?:icipacion)?\s*%?)"
    r"(?:\s*(?:\(\s*%\s*\)|%|(?:19|20)\d{2}))*$"
)


# Llamada de nota sola en el encabezado («(1)», «(a)», «(*)», «²»): marca una columna de notas entre los
# períodos, no un período; sin esto «(2)» se leía como el número −2 (paréntesis contables).
LLAMADA_SOLA = re.compile(r"^(?:\(\s*(?:\d{1,2}|[a-z]|\*+)\s*\)|\*+|[¹²³⁴⁵⁶⁷⁸⁹])$", re.I)


def es_llamada(valor):
    return isinstance(valor, str) and bool(LLAMADA_SOLA.match(valor.strip()))


def es_auxiliar(valor):
    """Rótulo de una columna auxiliar intercalada entre los períodos: no es un período ni un componente."""
    return isinstance(valor, str) and bool(AUXILIAR.match(normalizar(valor)))


def _anio(y):
    y = int(y)
    return y + 2000 if y < 100 else y


def leer(valor):
    """Devuelve dict(anio, sub, frecuencia, marca, acumulado, texto) o None si no es un período."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (_dt.datetime, _dt.date)):
        return dict(anio=valor.year, sub=valor.month, frecuencia="mensual", marca=None, acumulado=False,
                    texto=str(valor)[:10], dia=valor.day)
    n = numero(valor) if not isinstance(valor, str) else None
    if n is not None:
        if n.is_integer() and 1800 <= n <= 2200:
            return dict(anio=int(n), sub=1, frecuencia="anual", marca=None, acumulado=False, texto=str(int(n)))
        return None
    texto = str(valor).strip()
    if not texto or len(texto) > 80:
        return None
    t = normalizar(texto)
    # «2024 (miles de asistentes)», «2023 (en millones)»: la anotación entre paréntesis es la
    # unidad de la columna, un metadato; el período es lo que queda antes.
    m = ANOTACION.match(t)
    if m and not _MARCA_SOLA.fullmatch(m.group("nota").strip()):
        p = leer(texto[: len(m.group("base"))] if len(texto) == len(t) else m.group("base"))
        if p:
            p.update(texto=texto, unidad=m.group("nota").strip())
            return p
        return None
    if len(texto) > 40:
        return None
    acumulado = bool(ACUMULADO.search(t))
    base = t
    for _ in range(3):
        nuevo = PREFIJO.sub("", base)
        if nuevo == base:
            break
        base = nuevo
    base = base.strip(" .:")
    base = re.sub(r"^([a-z]{3,10})\.?\s+del?\s+((?:19|20)\d{2})$", r"\1 \2", base)
    m = ANIO_MARCA.match(base)
    if m:
        marca = (m.group("marca") or "").strip("() .") or None
        return dict(anio=int(m.group("y")), sub=1, frecuencia="anual", marca=marca, acumulado=acumulado, texto=texto)
    m = ISO_MES.match(base) or MES_ISO.match(base)
    if m:
        return dict(anio=int(m.group("y")), sub=int(m.group("m")), frecuencia="mensual", marca=None,
                    acumulado=acumulado, texto=texto)
    m = FECHA_ISO.match(base)
    if m:
        return dict(anio=int(m.group("y")), sub=int(m.group("m")), frecuencia="mensual", marca=None,
                    acumulado=acumulado, texto=texto, dia=int(m.group("d")))
    m = FECHA.match(base)
    if m and 1 <= int(m.group("m")) <= 12:
        return dict(anio=int(m.group("y")), sub=int(m.group("m")), frecuencia="mensual", marca=None,
                    acumulado=acumulado, texto=texto, dia=int(m.group("d")))
    # La marca de provisorio o la llamada de nota no cambian el subperíodo: se conservan como metadato.
    sin_marca = MARCA_INTERNA.sub(" ", base).strip()
    marca = (MARCA_INTERNA.search(base).group(0).strip("() ") or None) if sin_marca != base else None
    m = TRIM.match(base) or TRIM.match(sin_marca)
    if m:
        q = m.group("q1") or m.group("q2")
        q = int(q) if q else ROMANOS[m.group("q3").lower()]
        y = m.group("y1") or m.group("y2")
        return dict(anio=_anio(y) if y else None, sub=q, frecuencia="trimestral", marca=marca, acumulado=acumulado,
                    texto=texto)
    m = TRIM_ROMANO.match(base) or TRIM_ROMANO.match(sin_marca)
    if m:
        y = int(m.group("y"))
        anio = y if y >= 100 else (1900 + y if y >= 50 else 2000 + y)
        q = int(m.group("n")) if m.group("n") else ROMANOS[m.group("r").lower()]
        return dict(anio=anio, sub=q, frecuencia="trimestral", marca=marca, acumulado=acumulado, texto=texto)
    m = SEM.match(base) or SEM.match(sin_marca)
    if m:
        s = int(m.group("s1") or m.group("s2"))
        y = m.group("y1") or m.group("y2")
        return dict(anio=_anio(y) if y else None, sub=s, frecuencia="semestral", marca=marca, acumulado=acumulado,
                    texto=texto)
    m = BIM.match(base)
    if m:
        m1, m2 = MESES.get(m.group("m1").lower()), MESES.get(m.group("m2").lower())
        if m1 and m2 and m2 == m1 + 1 and m1 % 2 == 1:
            y = m.group("y")
            return dict(anio=_anio(y) if y else None, sub=(m1 + 1) // 2, frecuencia="bimestral", marca=None,
                        acumulado=acumulado, texto=texto)
    # En cuadros oficiales «Junio2» y «Diciembre2» remiten a una nota al pie.
    # La cifra no es el año ni un período nuevo.
    nota_mes = re.fullmatch(r"([a-z]{3,10})([1-9])", base)
    if nota_mes and nota_mes.group(1) in MESES:
        base = nota_mes.group(1)
        marca = nota_mes.group(2)
    m = MES_ANIO.match(base) or MES_ANIO.match(sin_marca)  # «Octubre*»: el mes provisorio sigue siendo octubre
    if m and m.group("m").lower() in MESES:
        y = m.group("y")
        return dict(anio=_anio(y) if y else None, sub=MESES[m.group("m").lower()], frecuencia="mensual", marca=marca,
                    acumulado=acumulado, texto=texto)
    return None


def ordinal(p):
    """Entero comparable: años consecutivos o meses consecutivos difieren en 1."""
    f = FRECUENCIA[p["frecuencia"]]
    return (p["anio"] or 0) * f + (p["sub"] - 1)


def leer_eje(valores, minimo=3):
    """Interpreta una secuencia de rótulos como eje temporal homogéneo.

    Devuelve None si no hay al menos `minimo` períodos de una misma frecuencia que dominen
    la secuencia. Las fechas que comparten día y mes en todos los rótulos son un eje anual
    (cierres de ejercicio), no mensual. Los rótulos no interpretables quedan como None.
    """
    leidos = [leer(v) for v in valores]
    rotulos = [str(v).strip() for v in valores if v is not None and str(v).strip()]
    if rotulos and all(PREFIJO_R.match(r) for r in rotulos):
        # Encabezados exportados desde R («X2017», «X2018»…): sólo si todos traen la X se lee el
        # período sin ella; el rótulo original se conserva como texto.
        leidos = []
        for v in valores:
            p = leer(PREFIJO_R.sub("", str(v).strip())) if v is not None and str(v).strip() else None
            if p:
                p["texto"] = str(v).strip()
            leidos.append(p)
    validos = [p for p in leidos if p]
    if len(validos) < minimo or len(validos) < 0.6 * len([v for v in valores if v is not None and str(v).strip()]):
        return None
    fechas = [p for p in validos if p.get("dia")]
    if fechas and len(fechas) == len(validos) and len({(p["dia"], p["sub"]) for p in fechas}) == 1:
        for p in validos:
            p.update(frecuencia="anual", sub=1)
    frecuencias = {p["frecuencia"] for p in validos}
    if len(frecuencias) != 1:
        # «enero de 2025 … diciembre de 2025, Total 2025»: el total del año al pie de un eje
        # mensual no es un período más; sin él, el eje es homogéneo y el total queda como fila.
        totales = [i for i, v in enumerate(valores) if leidos[i] and normalizar(str(v)).startswith("total")]
        resto = {p["frecuencia"] for i, p in enumerate(leidos) if p and i not in totales}
        if not totales or len(resto) != 1:
            return None
        for i in totales:
            leidos[i] = None
        validos = [p for p in leidos if p]
        if len(validos) < minimo:
            return None
        frecuencias = resto
    frecuencia = frecuencias.pop()
    # Meses sin año: sólo si el año se infiere sin ambigüedad (un único ciclo creciente).
    if frecuencia != "anual" and any(p["anio"] is None for p in validos):
        if any(p["anio"] is not None for p in validos):
            return None
        # Más rótulos que un ciclo completo: el año avanza cada vez que el ciclo recomienza.
        ciclos = len(validos) > FRECUENCIA[frecuencia]
        anio, previo = 0, None
        for p in validos:
            if ciclos and previo is not None and p["sub"] < previo:
                anio += 1
            previo = p["sub"]
            p["anio"] = anio
            p["anio_inferido"] = True
    for p in leidos:
        if p:
            p["ordinal"] = ordinal(p)
    return dict(frecuencia=frecuencia, periodos=leidos)


def etiqueta(p):
    if not p:
        return None
    if p["frecuencia"] == "anual":
        return str(p["anio"])
    if p["frecuencia"] == "mensual":
        return f"{p['anio']}-{p['sub']:02d}" if not p.get("anio_inferido") else p["texto"]
    if p["frecuencia"] == "trimestral":
        return f"{p['anio']}-T{p['sub']}" if not p.get("anio_inferido") else p["texto"]
    if p["frecuencia"] == "bimestral":
        return f"{p['anio']}-B{p['sub']}" if not p.get("anio_inferido") else p["texto"]
    return f"{p['anio']}-S{p['sub']}" if not p.get("anio_inferido") else p["texto"]
