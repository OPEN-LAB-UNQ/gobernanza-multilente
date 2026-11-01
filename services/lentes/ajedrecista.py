"""Ajedrecista: reconocimiento configuracional.

Busca estados imposibles o estructuralmente fuera de lugar: relaciones de
orden presupuestario, totales que no cierran y series acumuladas que
retroceden. Luego prioriza filas que conviene revisar primero.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from services import ambito, perfilado, plural

from .util import (
    ID_LIKE,
    NEGATIVO_SOSPECHOSO,
    columna_etiqueta_fila,
    columnas_numericas,
    etiqueta_fila,
    etiquetas_filas,
    valor_numero,
)

TOLERANCIA = 0.001

ADMITE_NEGATIVOS = re.compile(
    r"(variaci[oó]n|var\.?|porcentaje|%|tasa|saldo|balance|resultado|diferencia|"
    r"desv[ií]o|margen|ganancia|p[eé]rdida|excedente|quebranto|super[aá]vit|d[eé]ficit|"
    r"financiamiento|fuentes|aplicaciones)",
    re.I,
)
# Filas que, por lo que declaran, admiten un negativo aunque estén en una columna «Total»: el resultado
# (déficit), el financiamiento y sus fuentes y aplicaciones financieras, los saldos, las variaciones.
# No una tasa o un porcentaje (una tasa de desocupación negativa es imposible), ni «Ganancias» (un
# impuesto), ni «Fuentes de agua».
FILA_ADMITE_NEGATIVOS = re.compile(
    r"(variaci[oó]n|\bvar\b|\bsaldo|\bbalance\b|\bresultado|\bdiferencia|quebranto|super[aá]vit|d[eé]ficit|"
    r"financiamiento|(?:fuentes|aplicaciones)\s+(?:de\s+)?financ|existencias|objetos valiosos|discrepancia|"
    r"\bnet[oa]s?\b)",
    re.I,
)
# El rótulo «Total» de una columna («2009 Total», «TOTAL_8», «a precios constantes Total_2»).
TOTAL_EN_ROTULO = re.compile(r"\btotal(?:es)?\b(?:[\s_]*\d+)?", re.I)
# Una columna con negativos en una de cada cinco filas (o más) tiene signo por naturaleza (una variación,
# un saldo neto): no es una magnitud no negativa con una celda mal cargada.
PROPORCION_NEGATIVOS_NATURAL = 0.2
# Rótulo repetido con sufijo («a precios corrientes Total_2» junto a «a precios corrientes Total»): el nivel
# del encabezado que distingue a esa columna («Variación porcentual respecto de igual mes del año anterior»)
# no quedó en el nombre, así que el nombre no alcanza para afirmar que es una magnitud no negativa.
SUFIJO_REPETIDO = re.compile(r"^(?P<base>.+?)_\d+$")


def _rotulo_repetido(col, columnas) -> bool:
    m = SUFIJO_REPETIDO.match(str(col or ""))
    return bool(m) and m.group("base") in columnas


def _rotulo_periodo(col) -> bool:
    """El rótulo de la columna es un período («2019 4º trimestre», «Año 2020», «2009 Total»)."""
    from services.controles_excel.periodos import leer
    texto = str(col or "").strip()
    if leer(texto):
        return True
    sin_total = TOTAL_EN_ROTULO.sub(" ", texto).strip(" _-")
    return bool(sin_total) and sin_total != texto and bool(leer(sin_total))


# Filas que, en un estado de resultados o un presupuesto vs real, se cargan con
# signo negativo por convención contable.
FILA_EGRESO_RE = re.compile(
    r"costo|gasto|egreso|sueldo|salario|jornal|cargas? social|honorario|amortizaci|depreciaci|"
    r"impuesto|inter[eé]s(?:es)? pagad|comisi[oó]n|alquiler|compra|p[eé]rdida|devoluci|"
    r"descuento|bonificaci|previsi[oó]n|aguinaldo|\bsac\b|remuneraci|mantenimiento|reparaci|seguro",
    re.I,
)
FILA_INGRESO_RE = re.compile(
    r"ingreso|venta|cuota|recaudaci|cobranza|facturaci|donaci|aporte|subsidio|subvenci|"
    r"inter[eé]s(?:es)? (?:ganad|cobrad)|rendimiento|arancel|matr[ií]cula|abono",
    re.I,
)


def _columna_admite_negativos(col: str) -> bool:
    return bool(ADMITE_NEGATIVOS.search(perfilado.normalizar_texto(col)))


def _total_verificado(datos: list[dict[str, Any]], numericas: list[str]) -> tuple[str | None, list[str]]:
    if len(numericas) < 3:
        return None, []
    for candidata in numericas:
        if not re.search(r"total|suma|general", perfilado.normalizar_texto(candidata)):
            continue
        # «% del total», tasas o promedios no son componentes de la suma.
        partes = [c for c in numericas if c != candidata and not COLUMNA_NO_SUMABLE_RE.search(str(c))]
        if len(partes) < 2:
            continue
        comparables = 0
        coinciden = 0
        for fila in datos:
            total = valor_numero(fila.get(candidata))
            if total is None or total == 0:
                continue
            calculado = sum(valor_numero(fila.get(c)) or 0 for c in partes)
            comparables += 1
            if abs(total - calculado) / abs(total) <= TOLERANCIA:
                coinciden += 1
        if comparables >= 3 and coinciden / comparables >= 0.7:
            return candidata, partes
    return None, []


def _cierre_consultas(datos: list[dict[str, Any]], numericas: list[str]) -> dict | None:
    """Valida el cierre operativo solo cuando las tres columnas son inequívocas.

    No intenta inferir cualquier total genérico: la igualdad se aplica únicamente
    al trío consultas/resueltas/pendientes para evitar falsos positivos en tablas
    donde una columna parecida representa stock, flujo o universo diferente.
    """
    por_nombre = {perfilado.normalizar_texto(col): col for col in numericas}

    def buscar(*alias: str) -> str | None:
        return next((por_nombre[nombre] for nombre in alias if nombre in por_nombre), None)

    col_consultas = buscar("consultas", "consultas_totales", "total_consultas")
    col_resueltas = buscar("resueltas", "consultas_resueltas")
    col_pendientes = buscar("pendientes", "consultas_pendientes")
    if not all((col_consultas, col_resueltas, col_pendientes)):
        return None
    assert col_consultas is not None and col_resueltas is not None and col_pendientes is not None

    comparables = 0
    violaciones = []
    for i, fila in enumerate(datos):
        consultas = valor_numero(fila.get(col_consultas))
        resueltas = valor_numero(fila.get(col_resueltas))
        pendientes = valor_numero(fila.get(col_pendientes))
        if consultas is None or resueltas is None or pendientes is None:
            continue
        comparables += 1
        calculado = resueltas + pendientes
        escala = max(abs(consultas), 1.0)
        if abs(consultas - calculado) / escala > TOLERANCIA:
            violaciones.append((i, consultas, resueltas, pendientes, calculado))
    if comparables < 3 or not violaciones:
        return None

    i, declarado, resueltas, pendientes, calculado = violaciones[0]
    diferencia = calculado - declarado
    diferencia_pct = diferencia / abs(declarado) * 100 if declarado else None
    periodo = next(
        (str(valor) for clave, valor in datos[i].items() if "period" in perfilado.normalizar_texto(clave)),
        f"el {etiqueta_fila(datos, i)}",
    )
    return {
        "modo": "imposibilidad",
        "descripcion": (
            f"El cierre operativo no coincide en {plural.contar(len(violaciones), 'fila')}: "
            f"{col_resueltas} + {col_pendientes} debería ser igual a {col_consultas}. "
            f"Muestra de referencia: {etiqueta_fila(datos, i)} declara {declarado:g} consultas; "
            f"{resueltas:g} resueltas + {pendientes:g} pendientes = {calculado:g}, "
            f"una diferencia de {diferencia:g} ({diferencia_pct:.2f}% de las consultas)."
        ),
        "severidad": "alta",
        "pregunta_institucional": (
            f"Verificar por qué en {periodo} se registraron {resueltas:g} consultas resueltas y "
            f"{pendientes:g} pendientes frente a {declarado:g} consultas totales, generando una diferencia de {diferencia:g}."
        ),
        "evidencia": {
            "regla": "resueltas_mas_pendientes_no_cierran_consultas",
            "columnas": [col_consultas, col_resueltas, col_pendientes],
            "columna_total": col_consultas,
            "columnas_componentes": [col_resueltas, col_pendientes],
            "filas_en_violacion": len(violaciones),
            "filas": [fila for fila, *_ in violaciones[:20]],
            "filas_detalle": etiquetas_filas(datos, [fila for fila, *_ in violaciones], 20),
            "muestra": {
                "fila": i,
                "registro": i + 1,
                "fila_fuente_con_encabezado": i + 2,
                "fila_detalle": etiqueta_fila(datos, i),
                "declarado": declarado,
                "resueltas": resueltas,
                "pendientes": pendientes,
                "calculado": calculado,
                "diferencia_absoluta": diferencia,
                "diferencia_pct_consultas": round(diferencia_pct, 2) if diferencia_pct is not None else None,
            },
        },
    }


def _gasto_en_negativo_por_convencion(datos: list[dict[str, Any]], col: str, negativas: list[int]) -> bool:
    """Organizaciones: una columna de gasto cargada entera en negativo sigue la convención contable."""
    if not re.search(r"gasto", perfilado.normalizar_texto(col)):
        return False
    con_valor = [i for i, f in enumerate(datos) if valor_numero(f.get(col)) not in (None, 0)]
    return len(con_valor) >= 2 and len(negativas) == len(con_valor)


def _sin_egresos_por_convencion(datos: list[dict[str, Any]], col: str, negativas: list[int]) -> list[int]:
    """Descarta negativos de egreso cuando el archivo usa esa convención contable.

    La convención se da por establecida sólo si hay al menos dos filas de egreso
    con valor y todas están en negativo: un signo invertido en una sola celda
    (el error que esta regla existe para detectar) no alcanza para establecerla.
    """
    # Sólo en organizaciones: en el presupuesto público un importe negativo sigue siendo
    # una señal, aunque varias filas de gasto lo compartan.
    if not negativas or not ambito.es_organizacion():
        return negativas
    etiqueta = columna_etiqueta_fila(datos)
    if not etiqueta:
        return negativas
    egresos = [
        i for i, fila in enumerate(datos)
        if FILA_EGRESO_RE.search(str(fila.get(etiqueta) or "")) and valor_numero(fila.get(col)) not in (None, 0)
    ]
    if len(egresos) < 2 or any((valor_numero(datos[i].get(col)) or 0) > 0 for i in egresos):
        return negativas
    # Con la convención establecida, un negativo sólo es imposible donde se esperan
    # ingresos: el resto de las filas puede ser un egreso con otro rótulo.
    def es_ingreso(i: int) -> bool:
        rotulo = str(datos[i].get(etiqueta) or "")
        return bool(FILA_INGRESO_RE.search(rotulo)) and not FILA_EGRESO_RE.search(rotulo)

    return [i for i in negativas if es_ingreso(i)]


FILA_TOTAL_RE = re.compile(r"^\s*(?:sub)?total|resultado", re.I)
PRESUPUESTO_ORG_RE = re.compile(r"presupuest|budget|\bplan\b|proyectad|previst", re.I)
# «real» y «actual» como palabra: corta también en «_» («Real_2023», «gasto_real»),
# pero no dentro de «Actualización» o «realizado».
REAL_ORG_RE = re.compile(r"(?<![a-záéíóúñ])(?:real|actual)(?![a-záéíóúñ])|ejecutad|incurrid", re.I)
# Columnas que comparan o miden avance: no son el presupuesto ni el real.
COMPARACION_ORG_RE = re.compile(
    r"\bvs\.?\b|\bcontra\b|cumplimiento|avance|%|porcentaje|variaci|diferencia|desv|ratio|tasa|[ií]ndice|actualizaci",
    re.I,
)
ANIO_RE = re.compile(r"(?:19|20)\d{2}")
# Columnas que se llaman explícitamente presupuesto y ejecutado/real: ahí cualquier rubro
# («Salud», «Obras») es un gasto comparable, aunque su rótulo no diga «gasto».
PRESUPUESTO_EXPLICITO_RE = re.compile(r"presupuest", re.I)
EJECUTADO_EXPLICITO_RE = re.compile(r"ejecutad|(?<![a-záéíóúñ])real(?![a-záéíóúñ])", re.I)
SOBREEJECUCION_FUERTE = 0.10


def _candidatas_org(perfiles: list[dict[str, Any]], patron: re.Pattern, excluir: re.Pattern | None = None) -> list[str]:
    return [
        p["name"] for p in perfiles
        if p.get("dtype") == "numero" and patron.search(str(p["name"]))
        and not (excluir and excluir.search(str(p["name"])))
        and not COMPARACION_ORG_RE.search(str(p["name"]))
        and not ADMITE_NEGATIVOS.search(perfilado.normalizar_texto(p["name"]))
    ]


def _preferir_vigente(columnas: list[str]) -> str:
    # Si hay presupuesto original y vigente, se compara contra el vigente.
    vigentes = [c for c in columnas if re.search(r"vigente|actualizad|modificad|final", c, re.I)]
    return (vigentes or columnas)[0]


def _columnas_presupuesto_real(perfiles: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Par presupuesto/real comparable. Con años en los rótulos, sólo del mismo año."""
    presupuestos = _candidatas_org(perfiles, PRESUPUESTO_ORG_RE)
    reales = _candidatas_org(perfiles, REAL_ORG_RE, excluir=PRESUPUESTO_ORG_RE)
    if not presupuestos or not reales:
        return None, None
    anios_p = {c: ANIO_RE.search(c).group(0) for c in presupuestos if ANIO_RE.search(c)}
    anios_r = {c: ANIO_RE.search(c).group(0) for c in reales if ANIO_RE.search(c)}
    if anios_p or anios_r:
        comunes = sorted(set(anios_p.values()) & set(anios_r.values()))
        if not comunes:
            return None, None
        anio = comunes[-1]
        return (_preferir_vigente([c for c, a in anios_p.items() if a == anio]),
                [c for c, a in anios_r.items() if a == anio][0])
    if len(reales) > 1:
        return None, None  # Ambiguo: no se elige al azar cuál es el real.
    return _preferir_vigente(presupuestos), reales[0]


FILA_ES_TOTAL_RE = re.compile(r"^\s*(?:sub)?total(?:es)?\b", re.I)
COLUMNA_NO_SUMABLE_RE = re.compile(
    r"%|porcentaje|tasa|promedio|media(?:na)?\b|[ií]ndice|ratio|variaci|\bvar\.|crecim|participaci|desv[ií]o|diferencia|precio|"
    r"unitari|per\s*c[aá]pita|por\s+(?:niñ|habitante|persona)|[uú]nic|distint|sin\s+duplicar",
    re.I,
)
COLUMNA_PERIODO_RE = re.compile(
    r"(?:19|20)\d{2}|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre",
    re.I,
)
TOL_TOTAL_ABS = 0.05
TOL_TOTAL_REL = 0.002  # por debajo del 0,2 % es redondeo de la fuente


def _decimales(valor: float) -> int:
    texto = repr(float(valor))
    if "e" in texto or "." not in texto:
        return 0
    return min(4, len(texto.split(".")[1].rstrip("0")))


def _cierra(declarado: float, calculado: float, partes: list[float] | None = None) -> bool:
    tolerancia = TOL_TOTAL_ABS + TOL_TOTAL_REL * max(abs(declarado), abs(calculado))
    if partes:
        # Cada componente redondeado aporta hasta media unidad de su último decimal.
        decimales = max(_decimales(v) for v in [declarado, *partes])
        tolerancia = max(tolerancia, 0.5 * 10 ** -decimales * len(partes))
    return abs(declarado - calculado) <= tolerancia


def _no_es_suma(declarado: float, partes: list[float]) -> bool:
    """Un «total» entre el menor y el mayor de componentes positivos es un promedio o una tasa."""
    return len(partes) >= 2 and min(partes) >= 0 and min(partes) <= declarado <= max(partes)


def _etiqueta_con_totales(datos: list[dict[str, Any]]) -> str | None:
    """Columna de texto donde están los rótulos «Total…»/«Subtotal…».

    `columna_etiqueta_fila` prefiere una columna temporal; si esa columna es constante
    («Ejercicio» = 2024) no hay ningún «Total» en ella. Para esta regla se busca la
    columna que efectivamente contiene la fila de total, sin usar rótulos de persona.
    """
    from .util import FILA_LABEL_EVITAR

    preferida = columna_etiqueta_fila(datos)
    columnas = [preferida] if preferida else []
    columnas += [c for c in (datos[0].keys() if datos else []) if c not in columnas]
    for col in columnas:
        if FILA_LABEL_EVITAR.search(str(col)):
            continue
        if any(isinstance(f.get(col), str) and FILA_ES_TOTAL_RE.search(f.get(col)) for f in datos):
            return col
    return None


def _totales_de_filas(datos: list[dict[str, Any]], numericas: list[str]) -> list[dict]:
    """Fila «Total…» que no cierra con la suma de las filas de su grupo, en tablas de un período.

    Es el caso de un presupuesto contra real o un cuadro de un solo corte: la conciliación
    por series exige cuatro períodos y ahí no llega. Para no confundir una estructura que
    no es suma (jerarquías, promedios, totales parciales) con un error, la relación sólo se
    afirma si en la misma fila OTRA columna sí cierra, y se descartan los grupos que
    contienen subtotales y las columnas de porcentajes, tasas o promedios. Las tablas anchas
    de años (cuatro o más columnas de período) quedan para la conciliación por series.
    """
    etiqueta = _etiqueta_con_totales(datos)
    if not etiqueta:
        return []
    columnas = [c for c in numericas if not COLUMNA_NO_SUMABLE_RE.search(str(c))]
    if len(columnas) < 2 or sum(1 for c in numericas if COLUMNA_PERIODO_RE.search(str(c))) >= 4:
        return []
    hallazgos: list[dict] = []
    inicio = 0
    for i, fila in enumerate(datos):
        if not FILA_ES_TOTAL_RE.search(str(fila.get(etiqueta) or "")):
            continue
        grupo = list(range(inicio, i))
        inicio = i + 1
        if len(grupo) < 2:
            continue
        if any(FILA_ES_TOTAL_RE.search(str(datos[j].get(etiqueta) or "")) for j in grupo):
            continue
        cierran, no_cierran = [], []
        for col in columnas:
            declarado = valor_numero(fila.get(col))
            partes = [valor_numero(datos[j].get(col)) for j in grupo]
            if declarado is None or sum(v is not None for v in partes) < 2:
                continue
            presentes = [v for v in partes if v is not None]
            calculado = sum(presentes)
            if _cierra(declarado, calculado, presentes):
                cierran.append((col, declarado, calculado))
            elif not _no_es_suma(declarado, presentes):
                no_cierran.append((col, declarado, calculado))
        if not cierran or not no_cierran:
            continue
        for col, declarado, calculado in no_cierran:
            diferencia = declarado - calculado
            pct = abs(diferencia) / max(abs(declarado), abs(calculado)) * 100
            rotulo = str(fila.get(etiqueta) or "").strip()
            hallazgos.append({
                "modo": "imposibilidad",
                "descripcion": (
                    f"«{rotulo}» en '{col}' declara {declarado:,.2f} y las {len(grupo)} filas de su grupo suman "
                    f"{calculado:,.2f} (diferencia {diferencia:,.2f}; {pct:.1f} %). En la misma fila, "
                    f"{', '.join(repr(c) for c, _, _ in cierran)} sí cierra con la suma, así que la estructura es "
                    "una suma. Revisar el total y sus componentes: la diferencia no dice cuál de ellos es el incorrecto."
                ),
                # Con la estructura de suma corroborada por otra columna, una diferencia material es alta.
                "severidad": "alta" if pct >= 0.5 else "media",
                "pregunta_institucional": (
                    f"¿Por qué «{rotulo}» no coincide con la suma de sus filas en '{col}' si en "
                    f"{cierran[0][0]!r} sí coincide?"
                ),
                "evidencia": {
                    "regla": "total_de_filas_no_cierra",
                    "columna": col,
                    "filas": [i],
                    "fila_detalle": etiqueta_fila(datos, i),
                    "filas_componentes": grupo[:30],
                    "declarado": round(declarado, 4),
                    "calculado": round(calculado, 4),
                    "diferencia": round(diferencia, 4),
                    "columnas_que_cierran": [c for c, _, _ in cierran],
                },
            })
    return hallazgos[:10]


def _rotulo_fila(datos: list[dict[str, Any]], i: int) -> str:
    """Rótulo de la fila sin adivinar su número en la hoja (el cuadro puede no empezar en la fila 1)."""
    col = columna_etiqueta_fila(datos)
    valor = datos[i].get(col) if col and 0 <= i < len(datos) else None
    return f"{col}: {str(valor).strip()[:90]}" if valor is not None and str(valor).strip() else ""


def _cifra(valor: float) -> str:
    """Magnitud del gasto, sin signo, con separador de miles."""
    valor = abs(valor)
    return f"{valor:,.0f}" if valor >= 1000 or float(valor).is_integer() else f"{valor:.2f}".rstrip("0").rstrip(".")


def _columnas_explicitas(col_presupuesto: str | None, col_real: str | None) -> bool:
    return bool(
        col_presupuesto and col_real
        and PRESUPUESTO_EXPLICITO_RE.search(perfilado.normalizar_texto(col_presupuesto))
        and EJECUTADO_EXPLICITO_RE.search(perfilado.normalizar_texto(col_real))
    )


def _par_cubierto_por_etapas(perfiles: list[dict[str, Any]], col_presupuesto: str, col_real: str) -> bool:
    """Público: si el par ya entra en devengado/pagado contra vigente, esa regla lo señala."""
    etapas = perfilado.columnas_etapas_presupuesto(perfiles)
    return bool(etapas.get("credito_vigente")) and col_real in {etapas.get("devengado"), etapas.get("pagado")}


def _gasto_real_supera_presupuesto(
    datos: list[dict[str, Any]], perfiles: list[dict[str, Any]], solo_fuerte: bool = False
) -> dict | None:
    """El gasto real que supera lo presupuestado. En ingresos no se señala.

    Filas de egreso: cualquier exceso (sólo en organizaciones). Con columnas que se llaman
    presupuesto/presupuestado y ejecutado/real, además, toda fila que no sea total ni ingreso
    («Salud», «Obras») con una sobreejecución fuerte (más de 10 %). `solo_fuerte` aplica
    únicamente esta segunda parte (ámbito público).
    """
    etiqueta = columna_etiqueta_fila(datos)
    col_presupuesto, col_real = _columnas_presupuesto_real(perfiles)
    if not etiqueta or not col_presupuesto or not col_real:
        return None
    explicitas = _columnas_explicitas(col_presupuesto, col_real)
    if solo_fuerte and not explicitas:
        return None
    muestras = []
    for i, fila in enumerate(datos):
        rotulo = str(fila.get(etiqueta) or "")
        if not rotulo.strip() or FILA_TOTAL_RE.search(rotulo):
            continue
        egreso = bool(FILA_EGRESO_RE.search(rotulo))
        if not egreso and (not explicitas or FILA_INGRESO_RE.search(rotulo)):
            continue
        umbral = TOLERANCIA if egreso and not solo_fuerte else SOBREEJECUCION_FUERTE
        presupuesto, real = valor_numero(fila.get(col_presupuesto)), valor_numero(fila.get(col_real))
        if presupuesto in (None, 0) or real is None:
            continue
        # Los egresos pueden venir en negativo: se compara la magnitud del gasto.
        exceso = abs(real) - abs(presupuesto)
        if exceso / abs(presupuesto) > umbral:
            muestras.append({
                "egreso": egreso,
                "registro": i + 1,
                "rubro": rotulo.strip(),
                "ubicacion": etiqueta_fila(datos, i),
                "presupuesto": round(presupuesto, 2),
                "real": round(real, 2),
                "exceso_pct": round(exceso / abs(presupuesto) * 100, 2),
            })
    if not muestras:
        return None
    muestras.sort(key=lambda m: m["exceso_pct"], reverse=True)
    principal = muestras[0]
    todas_egreso = all([m.pop("egreso") for m in muestras])
    filas_txt = plural.contar(len(muestras), 'fila') + (" de egreso" if todas_egreso else "")
    criterio = "" if todas_egreso else (
        "En rubros que no se rotulan como gasto sólo se señala una sobreejecución mayor al 10 %. "
    )
    return {
        "modo": "restriccion_formal_a_validar",
        "descripcion": (
            f"En {filas_txt}, '{col_real}' supera a '{col_presupuesto}': "
            f"se gastó más de lo presupuestado. {criterio}La mayor diferencia está en «{principal['rubro']}»: "
            f"{_cifra(principal['real'])} contra {_cifra(principal['presupuesto'])} presupuestados ({principal['exceso_pct']:.1f}% más). "
            "En ingresos no se señala: superar lo presupuestado es favorable. Una diferencia no es un error: "
            "requiere saber si lo explica el precio, el volumen, un cambio de criterio o una imputación."
        ),
        "severidad": "alta" if principal["exceso_pct"] >= 10 else "media",
        "pregunta_institucional": (
            f"¿Qué explica que el gasto real supere lo presupuestado en «{principal['rubro']}»"
            + (f" y en {plural.contar(len(muestras) - 1, 'fila')} más" if len(muestras) > 1 else "")
            + "? ¿Está aprobada o documentada esa diferencia?"
        ),
        "evidencia": {
            "regla": "gasto_real_supera_presupuesto",
            "fuente_regla": "heuristica_por_encabezados_presupuesto_vs_real",
            "requiere_regla_explicita": True,
            "columna_presupuesto": col_presupuesto,
            "columna_real": col_real,
            "filas": [m["registro"] - 1 for m in muestras[:20]],
            "filas_en_violacion": len(muestras),
            "muestras": muestras[:5],
        },
    }


def imposibilidad(datos: list[dict[str, Any]], *, presupuestario: bool = True, importes_estadisticos=()) -> list[dict]:
    hallazgos: list[dict] = []
    if not datos:
        return hallazgos

    perfiles = perfilado.perfilar(datos)
    numericas = columnas_numericas(datos)
    rotulo_fila = columna_etiqueta_fila(datos)

    def fila_admite_negativo(i: int) -> bool:
        # «Resultado financiero», «Fuentes financieras», «Saldo»: en una columna «Total» pueden ser negativos.
        return bool(rotulo_fila) and bool(
            FILA_ADMITE_NEGATIVOS.search(perfilado.normalizar_texto(datos[i].get(rotulo_fila))))

    # Cuadro con períodos en columnas («2019 1º trimestre» … «2019 Total»): cada columna es un período de muchas
    # variables distintas (existencias, discrepancia, exportaciones netas), no una magnitud no negativa.
    periodos_en_columnas = sum(1 for col in numericas if _rotulo_periodo(col)) >= 3
    for col in numericas:
        # Un importe estadístico puede representar flujos netos. El nombre «Total»
        # no prueba que su dominio sea no negativo. Los controles de signos aislados,
        # relaciones aritméticas y restricciones explícitas siguen activos.
        if col in importes_estadisticos:
            continue
        if not NEGATIVO_SOSPECHOSO.search(col) or _columna_admite_negativos(col):
            continue
        if periodos_en_columnas and (_rotulo_periodo(col) or TOTAL_EN_ROTULO.search(col)):
            continue
        negativas = [i for i, f in enumerate(datos) if (valor_numero(f.get(col)) or 0) < 0
                     and not fila_admite_negativo(i)]
        if ambito.es_organizacion() and _gasto_en_negativo_por_convencion(datos, col, negativas):
            continue
        negativas = _sin_egresos_por_convencion(datos, col, negativas)
        distintos_de_cero = sum(1 for f in datos if valor_numero(f.get(col)))
        signo_natural = len(negativas) >= 3 and len(negativas) >= PROPORCION_NEGATIVOS_NATURAL * distintos_de_cero
        repetido = _rotulo_repetido(col, datos[0].keys())
        if negativas:
            filas_ref = etiquetas_filas(datos, negativas, 3)
            hallazgos.append({
                "modo": "imposibilidad",
                "descripcion": (
                    f"La columna '{col}' registra valores negativos en {plural.contar(len(negativas), 'fila')}, "
                    "algo que no debería ocurrir dado lo que esa columna representa. "
                    f"Filas de referencia: {', '.join(filas_ref)}."
                    + (" Son muchas filas: la columna puede tener signo por naturaleza (una variación o un saldo "
                       "neto); conviene confirmar qué representa antes de tomarlo como error." if signo_natural else "")
                    + (" El rótulo repite el de otra columna del cuadro (con un sufijo numérico): el nivel del encabezado "
                       "que la distingue, por ejemplo una variación porcentual, no quedó en el nombre; conviene confirmar "
                       "qué representa antes de tomarlo como error." if repetido and not signo_natural else "")
                ),
                "severidad": "media" if signo_natural or repetido else "alta",
                "evidencia": {
                    "regla": "valor_negativo_en_magnitud_no_negativa",
                    "columna": col,
                    "filas": negativas[:20],
                    "filas_detalle": etiquetas_filas(datos, negativas, 20),
                },
            })

    total_filas = _totales_de_filas(datos, numericas)
    if total_filas:
        hallazgos.extend(total_filas)

    total_col, partes = _total_verificado(datos, numericas)
    if total_col:
        violaciones = []
        for i, fila in enumerate(datos):
            declarado = valor_numero(fila.get(total_col))
            if declarado is None or declarado == 0:
                continue
            calculado = sum(valor_numero(fila.get(c)) or 0 for c in partes)
            if abs(declarado - calculado) / abs(declarado) > TOLERANCIA:
                violaciones.append((i, declarado, calculado))
        if violaciones:
            i, declarado, calculado = violaciones[0]
            rotulo = _rotulo_fila(datos, i)
            hallazgos.append({
                "modo": "imposibilidad",
                "descripcion": (
                    f"'{total_col}' se comporta como un total verificado, pero no coincide con "
                    f"sus componentes en {plural.contar(len(violaciones), 'fila')}. Muestra de referencia"
                    + (f" ({rotulo})" if rotulo else "")
                    + f": declara {declarado:g} y las partes suman {calculado:g}; la celda se indica en la ubicación del hallazgo."
                ),
                "severidad": "alta",
                "evidencia": {
                    "regla": "partes_no_suman_total",
                    # Filas y columna del cuadro: la presentación las traduce a coordenadas de Excel.
                    "filas": [v[0] for v in violaciones[:20]],
                    "columnas": [total_col],
                    "columna_total": total_col,
                    "columnas_componentes": partes[:10],
                    "filas_en_violacion": len(violaciones),
                    "muestra": {"fila": i, "fila_detalle": etiqueta_fila(datos, i), "declarado": declarado, "calculado": calculado},
                },
            })

    cierre_consultas = _cierre_consultas(datos, numericas)
    if cierre_consultas:
        hallazgos.append(cierre_consultas)

    if not presupuestario:
        desvio = None
    elif ambito.es_organizacion():
        desvio = _gasto_real_supera_presupuesto(datos, perfiles)
    else:
        # En público sólo la sobreejecución fuerte con columnas presupuesto/ejecutado explícitas,
        # y nunca si devengado/pagado contra vigente ya mira ese mismo par.
        par = _columnas_presupuesto_real(perfiles)
        desvio = (
            _gasto_real_supera_presupuesto(datos, perfiles, solo_fuerte=True)
            if par[0] and par[1] and not _par_cubierto_por_etapas(perfiles, *par) else None
        )
    if desvio:
        hallazgos.append(desvio)
    etapas = {} if ambito.es_organizacion() or not presupuestario else perfilado.columnas_etapas_presupuesto(perfiles)
    reglas = [
        ("devengado_supera_vigente", "devengado", "credito_vigente", "Bajo una lectura presupuestaria ordinaria, el devengado no debería superar el crédito vigente salvo ampliación, compensación o criterio documentado."),
        ("pagado_supera_devengado", "pagado", "devengado", "Bajo una lectura presupuestaria ordinaria, el pagado no debería superar el devengado salvo diferencia de corte, imputación o criterio documentado."),
        ("pagado_supera_vigente", "pagado", "credito_vigente", "Bajo una lectura presupuestaria ordinaria, el pagado no debería superar el crédito vigente salvo modificación, imputación o criterio documentado."),
        ("devengado_supera_comprometido", "devengado", "compromiso", "Bajo una lectura presupuestaria ordinaria, el devengado no debería superar el comprometido salvo diferencia de corte, regularización o criterio documentado."),
        ("comprometido_supera_vigente", "compromiso", "credito_vigente", "Bajo una lectura presupuestaria ordinaria, el comprometido no debería superar el crédito vigente salvo ampliación, compensación o criterio documentado."),
    ]
    for regla, mayor, menor, lectura in reglas:
        col_mayor, col_menor = etapas.get(mayor), etapas.get(menor)
        if not col_mayor or not col_menor:
            continue
        filas = []
        muestras = []
        comparables = 0
        total_mayor = total_menor = 0.0
        for i, fila in enumerate(datos):
            vmayor = valor_numero(fila.get(col_mayor))
            vmenor = valor_numero(fila.get(col_menor))
            if vmayor is None or vmenor is None or vmenor == 0:
                continue
            comparables += 1
            total_mayor += vmayor
            total_menor += vmenor
            if (vmayor - vmenor) / abs(vmenor) > TOLERANCIA:
                filas.append(i)
                diferencia = vmayor - vmenor
                muestras.append({
                    "registro": i + 1,
                    "fila_fuente_con_encabezado": i + 2,
                    "ubicacion": etiqueta_fila(datos, i),
                    "valor_mayor": round(vmayor, 2),
                    "valor_menor": round(vmenor, 2),
                    "diferencia_absoluta": round(diferencia, 2),
                    "exceso_sobre_menor_pct": round(diferencia / abs(vmenor) * 100, 2),
                })
        agregado_viola = total_menor > 0 and (total_mayor - total_menor) / abs(total_menor) > TOLERANCIA
        if filas or agregado_viola:
            filas_ref = etiquetas_filas(datos, filas, 3) if filas else []
            detalle = f" Filas de referencia: {', '.join(filas_ref)}." if filas_ref else ""
            muestra = muestras[0] if muestras else None
            evidencia_numerica = ""
            if muestra:
                evidencia_numerica = (
                    f" Evidencia: {muestra['valor_mayor']:g} > {muestra['valor_menor']:g}; "
                    f"diferencia {muestra['diferencia_absoluta']:g}, equivalente a "
                    f"{muestra['exceso_sobre_menor_pct']:.1f}% sobre {col_menor}."
                )
            pregunta = (
                f"Verificar por qué {col_mayor} supera a {col_menor} en "
                + "; ".join(
                    f"{item['ubicacion']} ({item['valor_mayor']:g} > {item['valor_menor']:g}; diferencia {item['diferencia_absoluta']:g})"
                    for item in muestras[:3]
                )
                + ", y documentar el corte, la regla y el criterio de carga aplicables."
            )
            hallazgos.append({
                "modo": "restriccion_formal_a_validar",
                "descripcion": (
                    f"{col_mayor} supera a {col_menor}. {lectura} "
                    "Esto no se comunica como incumplimiento automático: requiere validar regla aplicable, corte temporal y criterio de carga."
                    + evidencia_numerica + detalle
                ),
                # Una violación aislada (pocas filas entre muchas que cumplen) apunta a una celda puntual.
                "severidad": "alta" if any(item["exceso_sobre_menor_pct"] >= 10 for item in muestras)
                or (filas and len(filas) <= 2 and comparables >= 5 and len(filas) <= 0.2 * comparables) else "media",
                "pregunta_institucional": pregunta,
                "evidencia": {
                    "regla": regla,
                    "fuente_regla": "heuristica_por_encabezados_presupuestarios",
                    "requiere_regla_explicita": True,
                    "columna_mayor": col_mayor,
                    "columna_menor": col_menor,
                    "filas_en_violacion": len(filas),
                    "filas": filas[:20],
                    "filas_detalle": etiquetas_filas(datos, filas, 20),
                    "muestras_violacion": muestras[:20],
                    "total_mayor": round(total_mayor, 2),
                    "total_menor": round(total_menor, 2),
                    "el_agregado_tambien_viola": agregado_viola,
                },
            })

    identidad = _credito_inicial_mas_modificaciones(datos, etapas)
    if identidad:
        hallazgos.append(identidad)

    # Acumulados sobre el eje temporal elegido por contenido (no por un rótulo que diga «año»).
    # Todas las columnas: un rótulo como «Acumulado del año» no debe quedar fuera por parecer temporal.
    hallazgos.extend(_acumulados(datos, list(dict.fromkeys(c for fila in datos for c in fila))))
    temporales: list[str] = []
    if temporales:
        tcol = temporales[0]
        for col in numericas:
            if not re.search(r"acumulad|acum\b|al periodo|a la fecha", perfilado.normalizar_texto(col)):
                continue
            serie = []
            for fila in datos:
                f = perfilado.fecha(fila.get(tcol))
                v = valor_numero(fila.get(col))
                if f is not None and v is not None:
                    serie.append((f, v))
            if len(serie) < 4:
                continue
            por_periodo: defaultdict[tuple[int, int], float] = defaultdict(float)
            for f, v in serie:
                por_periodo[(f.year, f.month)] += v
            periodos_ordenados = sorted(por_periodo)
            ordenada = [por_periodo[p] for p in periodos_ordenados]
            retrocesos = [i for i in range(1, len(ordenada)) if ordenada[i] < ordenada[i - 1]]
            if retrocesos:
                muestras = []
                filas = []
                for i in retrocesos:
                    previo, actual = periodos_ordenados[i - 1], periodos_ordenados[i]
                    delta = ordenada[i] - ordenada[i - 1]
                    indices = [j for j, fila in enumerate(datos)
                               if (perfilado.fecha(fila.get(tcol)) is not None
                                   and (perfilado.fecha(fila.get(tcol)).year,
                                        perfilado.fecha(fila.get(tcol)).month) == actual)]
                    filas.extend(indices)
                    muestras.append({"periodo_previo": "%04d-%02d" % previo,
                                     "periodo": "%04d-%02d" % actual,
                                     "valor_previo": ordenada[i - 1], "valor_actual": ordenada[i],
                                     "diferencia": delta,
                                     "variacion_pct": round(delta / abs(ordenada[i - 1]) * 100, 2) if ordenada[i - 1] else None})
                detalle = "; ".join(f"{m['periodo_previo']} a {m['periodo']}: {m['valor_previo']:g} → {m['valor_actual']:g} (diferencia {m['diferencia']:g})" for m in muestras)
                hallazgos.append({
                    "modo": "imposibilidad",
                    "descripcion": (
                        f"La serie acumulada '{col}' retrocede en {plural.contar(len(retrocesos), 'paso')}. "
                        f"{detalle}. Requiere explicar ajustes, reversas, corte de serie o cambios de criterio; no demuestra por sí solo un error."
                    ),
                    "severidad": "alta",
                    "evidencia": {"regla": "serie_acumulada_retrocede", "columna": col, "retrocesos": len(retrocesos),
                                  "filas": filas, "filas_detalle": etiquetas_filas(datos, filas, 20),
                                  "retrocesos_detalle": muestras},
                })

    return hallazgos


def _credito_inicial_mas_modificaciones(datos: list[dict[str, Any]], etapas: dict[str, str]) -> dict | None:
    """Crédito inicial + modificaciones = crédito vigente, fila por fila (con tolerancia de redondeo)."""
    col_ini, col_mod, col_vig = (etapas.get(k) for k in ("credito_original", "modificaciones", "credito_vigente"))
    if not (col_ini and col_mod and col_vig):
        return None
    filas, muestras, comparables = [], [], 0
    for i, fila in enumerate(datos):
        ini, mod, vig = (valor_numero(fila.get(c)) for c in (col_ini, col_mod, col_vig))
        if ini is None or mod is None or vig is None:
            continue
        comparables += 1
        esperado = ini + mod
        if not _cierra(vig, esperado, [ini, mod]):
            filas.append(i)
            muestras.append({"registro": i + 1, "fila_fuente_con_encabezado": i + 2,
                             "ubicacion": etiqueta_fila(datos, i), "inicial": round(ini, 2),
                             "modificaciones": round(mod, 2), "vigente_declarado": round(vig, 2),
                             "vigente_calculado": round(esperado, 2), "diferencia": round(vig - esperado, 2)})
    if not filas:
        return None
    m = muestras[0]
    aislado = len(filas) <= 2 and comparables >= 5
    return {
        "modo": "restriccion_formal_a_validar",
        "descripcion": (
            f"{col_vig} no coincide con {col_ini} más {col_mod} en {plural.contar(len(filas), 'fila')}. "
            f"Por ejemplo, {m['ubicacion']}: {m['inicial']:g} + {m['modificaciones']:g} = {m['vigente_calculado']:g}, "
            f"pero se informa {m['vigente_declarado']:g} (diferencia {m['diferencia']:g}). "
            "Puede deberse a modificaciones no incluidas en la columna, a otro corte o a un error de carga."
        ),
        "severidad": "alta" if aislado or any(abs(x["diferencia"]) >= 0.01 * max(abs(x["vigente_declarado"]), 1) for x in muestras) else "media",
        "pregunta_institucional": (
            f"Verificar por qué {col_vig} difiere de {col_ini} más {col_mod} en "
            + "; ".join(f"{x['ubicacion']} (diferencia {x['diferencia']:g})" for x in muestras[:3])
            + ", y documentar las modificaciones presupuestarias y el corte aplicados."
        ),
        "evidencia": {
            "regla": "credito_vigente_no_cierra_con_modificaciones",
            "fuente_regla": "heuristica_por_encabezados_presupuestarios",
            "requiere_regla_explicita": True,
            "columnas": [col_ini, col_mod, col_vig],
            "filas_en_violacion": len(filas),
            "filas": filas[:20],
            "filas_detalle": etiquetas_filas(datos, filas, 20),
            "muestras_violacion": muestras[:20],
        },
    }


def _acumulados(datos: list[dict[str, Any]], numericas: list[str]) -> list[dict]:
    hallazgos = []
    for i, col, previo, actual, p_previo, p_actual in retrocesos_acumulados(datos, numericas):
        hallazgos.append({
            "modo": "imposibilidad",
            "descripcion": (
                f"La serie acumulada '{col}' retrocede de {previo:g} ({p_previo}) a {actual:g} ({p_actual}) dentro del mismo "
                "año. Un acumulado no puede bajar salvo ajuste o reversa documentada: posible error de carga en la celda."
            ),
            "severidad": "alta",
            "evidencia": {"regla": "serie_acumulada_retrocede", "columna": col, "columnas": [col], "filas": [i],
                          "valor_previo": previo, "valor_actual": actual, "periodo_previo": p_previo, "periodo": p_actual},
        })
    for i, col, previo, actual, p_previo, p_siguiente in estancamientos_acumulados(datos, numericas):
        hallazgos.append({
            "modo": "imposibilidad",
            "descripcion": (
                f"El acumulado de '{col}' repite el de '{p_previo}' ({previo:g}) y luego salta a {actual:g} "
                f"en '{p_siguiente}', mientras las demás filas avanzan en todos los períodos: posible valor copiado del período anterior."
            ),
            "severidad": "alta",
            "evidencia": {"regla": "acumulado_sin_avance", "columna": col, "columnas": [col], "filas": [i],
                          "valor_repetido": previo, "valor_siguiente": actual},
        })
    return hallazgos


def _columnas_comparables(datos: list[dict[str, Any]]) -> set[str]:
    omitidas = {
               "extraccion_pdf",
        "pagina_pdf",
        "pagina_pdf_impresa",
        "tabla_pdf",
        "fila_tabla_pdf",
        "paginas_documento",
        "paginas_pdf_analizadas",
        "limite_paginas_pdf",
        "pdf_truncado_por_paginas",
    }
    return {str(c) for fila in datos for c in fila.keys() if str(c) not in omitidas}


def _historial_comparable(datos: list[dict[str, Any]], datos_periodo_anterior: list[dict[str, Any]], col_clave: str) -> bool:
    columnas_actual = _columnas_comparables(datos)
    columnas_anterior = _columnas_comparables(datos_periodo_anterior)
    if columnas_actual != columnas_anterior:
        return False
    claves_actual = {str(f.get(col_clave)).strip() for f in datos if f.get(col_clave) is not None and str(f.get(col_clave)).strip()}
    claves_anterior = {str(f.get(col_clave)).strip() for f in datos_periodo_anterior if f.get(col_clave) is not None and str(f.get(col_clave)).strip()}
    if len(claves_actual) < 3 or len(claves_anterior) < 3:
        return False
    inter = claves_actual & claves_anterior
    return len(inter) / max(len(claves_actual), 1) >= 0.8 and len(inter) / max(len(claves_anterior), 1) >= 0.8


def priorizacion(
    datos: list[dict[str, Any]],
    datos_periodo_anterior: list[dict[str, Any]] | None,
    top_n: int = 3,
) -> list[dict]:
    if not datos or not datos_periodo_anterior:
        return []

    numericas = columnas_numericas(datos)
    comunes = [c for c in numericas if c in columnas_numericas(datos_periodo_anterior) and not ID_LIKE.search(str(c))]
    if not comunes:
        return []

    col_clave = next((c for c in datos[0].keys() if ID_LIKE.search(c)), None) or columna_etiqueta_fila(datos)
    if not col_clave or col_clave not in datos_periodo_anterior[0]:
        return []
    if not _historial_comparable(datos, datos_periodo_anterior, col_clave):
        return []
    prev_por_clave = {
        str(f.get(col_clave)).strip(): f
        for f in datos_periodo_anterior
        if f.get(col_clave) is not None and str(f.get(col_clave)).strip()
    }
    if not prev_por_clave:
        return []
    puntajes = []
    for i, fila in enumerate(datos):
        clave = str(fila.get(col_clave)).strip() if fila.get(col_clave) is not None else ""
        anterior = prev_por_clave.get(clave)
        if not anterior:
            continue
        z_total = 0.0
        detalle = {}
        for c in comunes:
            actual = valor_numero(fila.get(c))
            base = valor_numero(anterior.get(c))
            if actual is None or base is None or base == 0:
                continue
            variacion_pct = (actual - base) / abs(base) * 100
            if abs(variacion_pct) < 1:
                continue
            detalle[c] = round(variacion_pct, 1)
            z_total += abs(variacion_pct) / 100
        if detalle:
            puntajes.append((z_total, i, detalle))

    hallazgos = []
    for z_total, i, detalle in sorted(puntajes, reverse=True)[:top_n]:
        if z_total < 2:
            continue
        hallazgos.append({
            "modo": "priorizacion",
            "descripcion": (
                f"{etiqueta_fila(datos, i)} es una de las primeras que conviene revisar: se aparta del "
                f"comportamiento previo en {', '.join(detalle) or 'varias columnas'}."
            ),
            "severidad": "media" if z_total < 3 else "alta",
            "evidencia": {"fila": i, "fila_detalle": etiqueta_fila(datos, i), "variacion_pct_por_columna": detalle, "score": round(z_total, 2)},
        })
    return hallazgos


def analizar(
    datos: list[dict[str, Any]],
    datos_periodo_anterior: list[dict[str, Any]] | None = None,
) -> list[dict]:
    # El parámetro histórico se conserva por compatibilidad. La comparación
    # con preinformes pertenece a Radiólogo y el orquestador la comunica allí.
    return imposibilidad(datos)


# Una variación, un porcentaje o una tasa acumulados («Variación porcentual acumulada del año respecto a igual
# acumulado del año anterior») pueden bajar: la regla de los acumulados es sólo para niveles (importes, cantidades).
ACUMULADO_NO_NIVEL = re.compile(r"variaci|\bvar\b|porcent|%|\btasa|indice|respecto|interanual|\bratio|promedio")


def _acumulado_de_nivel(col) -> bool:
    texto = perfilado.normalizar_texto(col)
    return bool(re.search(r"acumulad|acum\b|a la fecha", texto)) and not ACUMULADO_NO_NIVEL.search(texto)


def retrocesos_acumulados(datos, columnas):
    """Retrocesos de series acumuladas sobre su eje temporal real.

    Con una columna de períodos (elegida por contenido) la serie corre por filas y se reinicia al
    cambiar de año. Si los períodos están en los rótulos de varias columnas acumuladas («Ejec. acum.
    T1…T4») la serie corre por cada fila a lo largo de esas columnas. Sin eje temporal no se compara
    (filas de metas distintas no son períodos). Devuelve [(fila, columna, previo, actual, periodo_previo, periodo)].
    """
    from services.controles_excel.periodos import leer
    from services.lentes.cronista import columna_tiempo
    salida = []
    tcol = columna_tiempo(datos)
    acumuladas = [c for c in columnas if _acumulado_de_nivel(c)]
    if tcol:
        orden = []
        for i, fila in enumerate(datos):
            f = perfilado.fecha(fila.get(tcol))
            if f is not None:
                orden.append(((f.year, f.month), i))
        orden.sort()
        for col in acumuladas:
            previo = None
            for (anio_mes, i) in orden:
                v = valor_numero(datos[i].get(col))
                if v is None:
                    continue
                if previo is not None and previo[0][0] == anio_mes[0] and v + 0.001 < previo[1]:
                    salida.append((i, col, previo[1], v, str(datos[previo[2]].get(tcol)), str(datos[i].get(tcol))))
                previo = (anio_mes, v, i)
        return salida
    con_periodo = []
    for c in acumuladas:
        p = leer(str(c))
        if p and p["frecuencia"] != "anual":
            con_periodo.append((p["sub"], c))
    if len(con_periodo) < 2 or len({s for s, _ in con_periodo}) != len(con_periodo):
        return salida
    con_periodo.sort()
    for i, fila in enumerate(datos):
        previo = None
        for _, c in con_periodo:
            v = valor_numero(fila.get(c))
            if v is None:
                continue
            if previo is not None and v + 0.001 < previo[1]:
                salida.append((i, c, previo[1], v, previo[0], c))
            previo = (c, v)
    return salida


def estancamientos_acumulados(datos, columnas):
    """Acumulado que no avanza en un período y salta en el siguiente, cuando el resto avanza siempre."""
    from services.controles_excel.periodos import leer
    con_periodo = []
    for c in columnas:
        p = leer(str(c))
        if p and p["frecuencia"] != "anual" and _acumulado_de_nivel(c):
            con_periodo.append((p["sub"], c))
    con_periodo.sort()
    if len(con_periodo) < 3 or len({s for s, _ in con_periodo}) != len(con_periodo):
        return []
    cols = [c for _, c in con_periodo]
    series = []
    for i, fila in enumerate(datos):
        vs = [valor_numero(fila.get(c)) for c in cols]
        if all(v is not None for v in vs):
            series.append((i, vs))
    if len(series) < 4:
        return []
    salida = []
    for i, vs in series:
        pasos = [b - a for a, b in zip(vs, vs[1:])]
        for k in range(len(pasos) - 1):
            if pasos[k] == 0 and vs[k] != 0 and pasos[k + 1] > 0:
                otros = [p for kk, p in enumerate(pasos) if kk not in (k, k + 1)]
                tipico = sorted(otros)[len(otros) // 2] if otros else None
                sanas = sum(1 for j, ws in series if j != i and all(b > a for a, b in zip(ws, ws[1:])))
                if tipico and pasos[k + 1] >= 1.6 * tipico and sanas >= 0.8 * (len(series) - 1):
                    salida.append((i, cols[k + 1], vs[k], vs[k + 2], cols[k], cols[k + 2]))
    return salida
