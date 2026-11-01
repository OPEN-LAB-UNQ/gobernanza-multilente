"""Frase «Qué pasó» de cada observación y fórmulas con funciones en castellano.

Es sólo presentación: no cambia qué se detecta ni con qué severidad. La frase la arma el código
con plantillas (mismas entradas, misma frase), nunca un modelo de IA, y pasa por los resguardos de
lenguaje de `services.guardrails` como el resto del texto institucional.

La traducción de funciones también es sólo de presentación: la evidencia guardada y el comprobante
conservan la fórmula tal como figura en el archivo.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from openpyxl.formula.tokenizer import Token, Tokenizer
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string, range_boundaries

logger = logging.getLogger(__name__)

FUNCIONES_ES = {
    "SUM": "SUMA", "AVERAGE": "PROMEDIO", "SUMPRODUCT": "SUMAPRODUCTO", "COUNT": "CONTAR",
    "COUNTA": "CONTARA", "IF": "SI", "IFERROR": "SI.ERROR", "ROUND": "REDONDEAR", "SUMIF": "SUMAR.SI",
    "SUMIFS": "SUMAR.SI.CONJUNTO", "AVERAGEIF": "PROMEDIO.SI", "VLOOKUP": "BUSCARV", "AND": "Y",
    "OR": "O", "MEDIAN": "MEDIANA", "MAX": "MAX", "MIN": "MIN", "ABS": "ABS",
    "TEXT": "TEXTO", "EDATE": "FECHA.MES",
}
_avisadas: set[str] = set()


def _separador() -> str:
    try:
        from config import settings

        return getattr(settings, "formula_separador_argumentos", ";") or ";"
    except Exception:  # noqa: BLE001 — sin configuración se usa la de Argentina
        return ";"


def traducir_formula(formula: Any, separador: str | None = None) -> str:
    """Devuelve la fórmula con nombres de función en castellano, para mostrar.

    Recorre la fórmula por piezas con el analizador de openpyxl: los textos entre comillas, los
    nombres de hoja y las referencias no se tocan. Separador de argumentos «;» (Argentina) salvo que
    se configure otro; con «;» los decimales pasan de «0.5» a «0,5».
    """
    texto = str(formula or "")
    if not texto.startswith("="):
        return texto
    sep = separador or _separador()
    try:
        piezas = Tokenizer(texto).items
    except Exception:  # noqa: BLE001 — fórmula que el analizador no entiende: se muestra tal cual
        return texto
    salida = []
    en_matriz = 0
    for pieza in piezas:
        valor = pieza.value
        if pieza.type == Token.ARRAY:
            en_matriz += 1 if pieza.subtype == Token.OPEN else -1
        if en_matriz:
            # {1,2;3,4}: separadores de matriz con otra convención regional; se muestran como en el archivo.
            salida.append(valor)
            continue
        if pieza.type == Token.FUNC and pieza.subtype == Token.OPEN:
            nombre = valor[:-1]
            prefijo = "_xlfn." if nombre.upper().startswith("_XLFN.") else ""
            base = nombre[len(prefijo):]
            traducida = FUNCIONES_ES.get(base.upper())
            if traducida is None:
                if base.upper() not in _avisadas:
                    _avisadas.add(base.upper())
                    logger.warning("lenguaje_llano: función sin traducción %s; se muestra en inglés", base.upper())
                traducida = base
            valor = traducida + "("
        elif pieza.type == Token.SEP and pieza.subtype == Token.ARG:
            valor = sep
        elif pieza.type == Token.OPERAND and pieza.subtype == Token.NUMBER and sep == ";":
            valor = valor.replace(".", ",")
        elif pieza.type == Token.OPERAND and pieza.subtype == Token.LOGICAL:
            valor = {"TRUE": "VERDADERO", "FALSE": "FALSO"}.get(valor.upper(), valor)
        salida.append(valor)
    return "=" + "".join(salida)


# --- Método de cálculo de una fórmula -------------------------------------------------------

_SIN_PAREN = r"[^()]*"


def _cuerpo(formula: str) -> str:
    texto = str(formula or "").strip().lstrip("=").replace("$", "").replace(" ", "").upper()
    return texto.replace("_XLFN.", "")


def metodo(formula: Any) -> str | None:
    """Nombre llano del cálculo («un promedio ponderado», «una suma»…) o None si no se reconoce."""
    cuerpo = _cuerpo(str(formula or ""))
    m = re.fullmatch(r"ROUND\((.*),[^,()]+\)", cuerpo)
    if m:
        interno = metodo("=" + m.group(1))
        return f"{interno}, redondeado" if interno else None
    if re.fullmatch(rf"SUMPRODUCT\({_SIN_PAREN}\)/SUM\({_SIN_PAREN}\)", cuerpo):
        return "un promedio ponderado"
    if re.fullmatch(rf"AVERAGE\({_SIN_PAREN}\)", cuerpo) or re.fullmatch(rf"SUM\({_SIN_PAREN}\)/COUNTA?\({_SIN_PAREN}\)", cuerpo):
        return "un promedio simple"
    if re.fullmatch(rf"SUM\({_SIN_PAREN}\)", cuerpo):
        return "una suma"
    if re.fullmatch(rf"MEDIAN\({_SIN_PAREN}\)", cuerpo):
        return "una mediana"
    m = re.fullmatch(r"SUM\(([A-Z]{1,3}\d+:[A-Z]{1,3}\d+)\)/(\d+)", cuerpo)
    if m:
        c1, f1, c2, f2 = range_boundaries(m.group(1))
        if (c2 - c1 + 1) * (f2 - f1 + 1) == int(m.group(2)):
            return "un promedio simple"
    pesos = _pesos_explicitos(cuerpo)
    if pesos:
        if abs(sum(pesos) - 1) < 1e-6:
            return "un promedio simple" if len(set(pesos)) == 1 else "un promedio ponderado"
        return "una suma ponderada"
    return None


def _pesos_explicitos(cuerpo: str) -> list[float] | None:
    """«C4*0.15+D4*0.15+E4*0.2+F4*0.5» → [0.15, 0.15, 0.2, 0.5]: pesos escritos dentro de la fórmula."""
    terminos = cuerpo.split("+")
    pesos = []
    for termino in terminos:
        m = (re.fullmatch(r"[A-Z]{1,3}\d+\*(\d+(?:\.\d+)?)", termino)
             or re.fullmatch(r"(\d+(?:\.\d+)?)\*[A-Z]{1,3}\d+", termino))
        if not m:
            return None
        pesos.append(float(m.group(1)))
    return pesos if len(pesos) >= 2 else None


def _funciones(formula: str) -> list[str]:
    return re.findall(r"([A-Z][A-Z0-9.]*)\(", _cuerpo(formula))


def _rangos(formula: str) -> list[tuple[int, int, int, int]]:
    """Rangos y celdas de la fórmula como (col_min, fila_min, col_max, fila_max)."""
    try:
        piezas = Tokenizer(str(formula)).items
    except Exception:  # noqa: BLE001
        return []
    salida = []
    for pieza in piezas:
        if pieza.type == Token.OPERAND and pieza.subtype == Token.RANGE:
            ref = pieza.value.replace("$", "").split("!")[-1]
            try:
                c1, f1, c2, f2 = range_boundaries(ref)
            except (ValueError, TypeError):
                continue
            if None in (c1, f1, c2, f2):
                continue
            salida.append((c1, f1, c2, f2))
    return salida


def patron_en_celda(patron: str, celda: str) -> str | None:
    """Convierte el patrón relativo guardado (R+0C-4…) en una fórmula A1 ubicada en la celda dada."""
    try:
        letras, fila = coordinate_from_string(celda.replace("$", ""))
        col = column_index_from_string(letras)
    except Exception:  # noqa: BLE001 — celda vacía o rango: sin patrón ubicable
        return None

    def absoluta(m: re.Match[str]) -> str:
        # Con signo, relativa a la celda; sin signo, fija (venía con «$» en el archivo).
        rf, rc = m.group(1), m.group(2)
        f = fila + int(rf) if rf[0] in "+-" else int(rf)
        c = col + int(rc) if rc[0] in "+-" else int(rc)
        if f < 1 or c < 1:
            raise ValueError("referencia fuera de la hoja")
        fija_f, fija_c = rf[0] not in "+-", rc[0] not in "+-"
        return f"{'$' if fija_c else ''}{get_column_letter(c)}{'$' if fija_f else ''}{f}"

    try:
        return re.sub(r"R([+-]?\d+)C([+-]?\d+)", absoluta, str(patron or ""))
    except ValueError:
        return None


def _esqueleto(formula: str) -> str:
    """La fórmula sin sus referencias: dos fórmulas con el mismo esqueleto hacen la misma cuenta."""
    try:
        piezas = Tokenizer(str(formula)).items
    except Exception:  # noqa: BLE001
        return str(formula)
    return "".join("R" if (p.type == Token.OPERAND and p.subtype == Token.RANGE) else p.value
                   for p in piezas).replace(" ", "").upper()


def _visible(formula: str) -> str:
    traducida = traducir_formula(formula)
    return f"la fórmula {traducida}" if traducida.strip("=") and not _VEREDICTO.search(traducida) else "otra fórmula"


def clasificar(formula: str, referencia: str, eje: str) -> tuple[str, dict[str, Any]]:
    """Qué tipo de diferencia hay entre la fórmula de la celda y la de su fila o columna."""
    if not str(formula or "").strip() or not str(referencia or "").strip():
        return "otro", {}
    m_celda, m_ref = metodo(formula), metodo(referencia)
    if (m_celda or m_ref) and m_celda != m_ref:
        return "metodo", {"metodo_celda": m_celda or _visible(formula), "metodo_patron": m_ref or _visible(referencia)}
    if _esqueleto(formula) != _esqueleto(referencia):
        return "otro", {}
    r_celda, r_ref = _rangos(formula), _rangos(referencia)
    distintos = [(c, r) for c, r in zip(r_celda, r_ref) if c != r]
    if not r_celda or len(r_celda) != len(r_ref) or not distintos:
        return "otro", {}

    def contenido(c, r):
        return r[0] <= c[0] and r[1] <= c[1] and c[2] <= r[2] and c[3] <= r[3]

    if all(contenido(c, r) for c, r in distintos):
        c, r = distintos[0]
        if (c[2] - c[0]) != (r[2] - r[0]):
            return "incompleto", {"n": c[2] - c[0] + 1, "m": r[2] - r[0] + 1, "unidad": "columnas"}
        return "incompleto", {"n": c[3] - c[1] + 1, "m": r[3] - r[1] + 1, "unidad": "filas"}
    if all((c[2] - c[0], c[3] - c[1]) == (r[2] - r[0], r[3] - r[1]) for c, r in distintos):
        return "corrido", {}
    return "otro", {}


# --- Rótulos ---------------------------------------------------------------------------------

def _rotulo_fila(texto: Any) -> str:
    """«fila 4 (A: Grupos sintéticos)» → «Grupos sintéticos»; sin rótulo, «fila 4»."""
    texto = " ".join(str(texto or "").split())
    m = re.fullmatch(r"fila (\d+) \([A-Z]{1,3}: (.+)\)", texto)
    return m.group(2) if m else texto


def _rotulo_columna(texto: Any) -> str:
    """«G (2025)» → «2025»; sin rótulo, la letra."""
    texto = " ".join(str(texto or "").split())
    m = re.fullmatch(r"[A-Z]{1,3} \((.+)\)", texto)
    return m.group(1) if m else texto


def _partes_detalle(evidencia: dict[str, Any]) -> tuple[str, str]:
    detalle = str(evidencia.get("fila_detalle") or "")
    fila, _, columna = detalle.partition(" / columna ")
    return _rotulo_fila(fila), _rotulo_columna(columna or evidencia.get("columna_detalle") or "")


def _fila_txt(fila: str) -> str:
    return f"la fila {fila[5:]}" if re.fullmatch(r"fila \d+", fila or "") else f"la fila «{fila}»"


def _columna_txt(columna: str) -> str:
    return f"la columna {columna}" if re.fullmatch(r"[A-Z]{1,3}", columna or "") else f"la columna «{columna}»"


def _celda_con_columna(celda: str, columna: str) -> str:
    letras = re.match(r"[A-Z]+", celda or "")
    if columna and letras and columna != letras.group(0):
        return f"{celda} («{columna}»)"
    return celda or "la celda"


# --- Plantillas por regla ----------------------------------------------------------------------

def _formula_fuera_de_patron(e: dict[str, Any]) -> str:
    eje = "columna" if e.get("eje") == "columna" else "fila"
    fila, columna = _partes_detalle(e)
    celda = str(e.get("celda") or "")
    referencia = e.get("formula_referencia") or patron_en_celda(e.get("patron_esperado"), celda) or ""
    caso, datos = clasificar(str(e.get("formula") or ""), referencia, eje)
    if eje == "fila":
        lugar, resto = f"En {_fila_txt(fila)}", "el resto de la fila"
        celda_txt = _celda_con_columna(celda, columna)
    else:
        lugar, resto = f"En {_columna_txt(columna)}", "el resto de la columna"
        celda_txt = f"la celda {celda} («{fila}»)" if fila and not fila.startswith("fila ") else f"la celda {celda}"
    if not celda_txt.startswith("la celda"):
        celda_txt = f"la celda {celda_txt}"
    if caso == "metodo":
        return f"{lugar}, {celda_txt} calcula {datos['metodo_celda']}, mientras que {resto} usa {datos['metodo_patron']}."
    if caso == "incompleto":
        return f"{lugar}, {celda_txt} toma {datos['n']} de las {datos['m']} {datos['unidad']} que toman las demás."
    if caso == "corrido":
        return f"{lugar}, {celda_txt} toma un rango corrido respecto del {resto[3:]}."
    return f"{lugar}, {celda_txt} se calcula distinto que {resto}."


def _valor_fijo_en_serie(e: dict[str, Any]) -> str:
    eje = "columna" if e.get("eje") == "columna" else "fila"
    fila, columna = _partes_detalle(e)
    celda = str(e.get("celda") or "")
    if eje == "fila":
        return f"En {_fila_txt(fila)}, la celda {_celda_con_columna(celda, columna)} tiene un valor cargado a mano donde las demás tienen fórmula."
    return f"En {_columna_txt(columna)}, la celda {celda} tiene un valor cargado a mano donde las demás tienen fórmula."


def _valor_fijo_distinto(e: dict[str, Any]) -> str:
    celda = str(e.get("celda") or "")
    motivo = str(e.get("motivo_patron") or "")
    eje = "columna" if motivo.startswith("la columna") else "fila"
    lugar = _lugar_indicador(e)
    base = f"{lugar}la celda {celda} tiene un valor cargado a mano"
    fijo, segun = e.get("valor_fijo"), e.get("valor_segun_formula")
    if _es_num(fijo) and _es_num(segun):
        return f"{_mayus(base)} ({_num(fijo)}); la fórmula de su {eje} daría {_num(segun)}."
    return f"{_mayus(base)}, mientras que las demás de su {eje} se calculan con fórmula."


def _promedio_simple(e: dict[str, Any]) -> str:
    celda = str(e.get("celda") or "")
    columna = _rotulo_columna(e.get("columna_detalle"))
    if e.get("agrupado"):
        return f"En {_columna_txt(columna)}, {e.get('cantidad_celdas')} celdas calculan un promedio simple, aunque el archivo trae datos con qué ponderarlo."
    fila = _rotulo_fila(e.get("fila_detalle"))
    return f"En {_fila_txt(fila)}, la celda {_celda_con_columna(celda, columna)} calcula un promedio simple, aunque el archivo trae datos con qué ponderarlo."


def _promedio_informado(e: dict[str, Any]) -> str:
    columna = _rotulo_columna(e.get("columna_resultado") or e.get("columna_detalle") or "")
    muestra = e.get("muestra") or {}
    if isinstance(muestra, dict) and _es_num(muestra.get("actual")) and _es_num(muestra.get("ponderado")):
        return (f"La columna «{columna}» informa promedios simples ({_num(muestra['actual'])} en «{_rotulo_fila(muestra.get('fila_detalle'))}»); "
                f"ponderados daría {_num(muestra['ponderado'])}.")
    return f"La columna «{columna}» informa promedios simples, aunque el archivo trae datos con qué ponderarlos."


def _implicita(e: dict[str, Any]) -> str:
    fila = _rotulo_fila(e.get("fila_detalle"))
    columna = _rotulo_columna(e.get("columna_detalle"))
    actual, esperado = e.get("valor_actual"), e.get("valor_esperado")
    if _es_num(actual) and _es_num(esperado):
        return f"En la fila «{fila}», el valor de «{columna}» ({_num(actual)}) no sigue la relación que cumplen las demás columnas, que daría {_num(esperado)}."
    return f"En la fila «{fila}», el valor de «{columna}» no sigue la relación que cumplen las demás columnas."


def _estado_explicito(e: dict[str, Any]) -> str:
    return f"El propio archivo marca para revisión la fila «{_rotulo_fila(e.get('fila_detalle'))}»."


def _porcentajes_como_cantidades(e: dict[str, Any]) -> str:
    return ("Las columnas confirmadas como porcentajes se comportan como cantidades: "
            "sus partes suman el total de cantidades. La aritmética cierra; hay que confirmar la unidad.")


PLANTILLAS = {
    "formula_fuera_de_patron": _formula_fuera_de_patron,
    "valor_fijo_en_serie_de_formulas": _valor_fijo_en_serie,
    "valor_fijo_distinto_de_formula": _valor_fijo_distinto,
    "promedio_simple_con_posibles_ponderadores": _promedio_simple,
    "promedio_informado_simple_con_ponderadores": _promedio_informado,
    "formula_implicita_rota": _implicita,
    "estado_explicito_revision": _estado_explicito,
    "porcentajes_como_cantidades": _porcentajes_como_cantidades,
}

GENERICA_POR_LENTE = {
    "conciliador": "Esta señal se revisó contra la forma en que se cargaron los datos.",
    "ajedrecista": "Hay una relación entre datos del informe que no se cumple como se esperaría.",
    "cronista": "Una serie del informe cambia de un modo que conviene revisar.",
    "orquesta": "Dos datos del informe que deberían acompañarse no coinciden.",
    "radiologo": "Comparado con datos anteriores, este valor queda fuera de su rango habitual.",
    "rizoma": "Hipótesis para explorar: aparece una asociación entre datos del informe.",
    "matematico": "Un cálculo o método del informe difiere de lo que se usa en el resto del cuadro.",
}

_GENERICAS = {*GENERICA_POR_LENTE.values(), "Hay un dato del informe que conviene revisar."}


def _es_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _num(v: Any) -> str:
    from services.reportes.formato import numero

    return numero(v)


def _mayus(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _lugar_indicador(e: dict[str, Any]) -> str:
    indicador = " ".join(str(e.get("indicador") or e.get("serie") or "").split())
    if indicador:
        return f"en «{indicador}», "
    hoja = " ".join(str(e.get("hoja") or "").split())
    return f"en la hoja «{hoja}», " if hoja else ""


_VEREDICTO = re.compile(r"error|incorrect|falla|irregular", re.I)
_DATO_FALTANTE = re.compile(r"\bNone\b|\bnan\b|«\s*»|\(\s*\)|\ben\s*,|la celda la celda|^\s*[,.]")


def _acortar_rotulos(frase: str, maximo: int = 45) -> str:
    """Un rótulo del archivo muy largo no debe ocupar la frase: se corta con «…»."""
    def corta(m: re.Match[str]) -> str:
        return "«" + m.group(1)[: maximo - 1].rsplit(" ", 1)[0].rstrip(" .,;:") + "…»"

    return re.sub("«([^»]{%d,})»" % (maximo + 1), corta, frase)


def resumen_llano(hallazgo: dict[str, Any]) -> str:
    """Una frase llana de qué pasó. Nunca vacía: sin plantilla, una frase de la lente."""
    evidencia = hallazgo.get("evidencia") or {}
    plantilla = PLANTILLAS.get(str(evidencia.get("regla") or ""))
    if plantilla is None and not evidencia.get("regla"):
        reconoce, candidata = PLANTILLAS_SIN_REGLA.get(str(hallazgo.get("lente") or ""), (None, None))
        if reconoce is not None and reconoce(evidencia):
            plantilla = candidata
    if plantilla is not None:
        try:
            frase = plantilla(evidencia)
        except Exception:  # noqa: BLE001 — la frase no puede impedir mostrar la observación
            logger.exception("lenguaje_llano: no se pudo armar la frase de %s", evidencia.get("regla"))
            frase = ""
        frase = _acortar_rotulos(" ".join(frase.split()))
        if frase and not _VEREDICTO.search(frase) and not _DATO_FALTANTE.search(frase):
            return frase
    return GENERICA_POR_LENTE.get(str(hallazgo.get("lente") or ""), "Hay un dato del informe que conviene revisar.")


# --- Parte C: plantillas de las demás lentes ------------------------------------------------------
# Cada una usa sólo datos de la evidencia; si falta un dato, la frase lo omite en vez de inventarlo.

_NOMBRES_PRESUPUESTO = {
    "credito_vigente": "el crédito vigente", "credito_inicial": "el crédito inicial", "devengado": "lo devengado",
    "pagado": "lo pagado", "comprometido": "lo comprometido", "presupuesto": "lo presupuestado",
}


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _n(v: Any) -> str:
    x = _f(v)
    return _num(x) if x is not None else str(v)


def _entero(v: Any) -> str:
    from services.reportes.formato import numero

    x = _f(v)
    return numero(round(x), 0) if x is not None else str(v)


def _uno(v: Any) -> str:
    from services.reportes.formato import numero

    return numero(round(float(v), 1), 1)


def _dos(v: Any) -> str:
    from services.reportes.formato import numero

    return numero(v, 2)


def _txt(v: Any) -> str:
    return " ".join(str(v or "").split())


def _col(nombre: Any) -> str:
    texto = _txt(nombre)
    return _NOMBRES_PRESUPUESTO.get(texto.lower(), f"«{texto.replace('_', ' ')}»")


def _en(e: dict[str, Any]) -> str:
    """«En «Educación» 2023, » con lo que haya: indicador o serie, período; si no, la hoja."""
    nombre = _txt(e.get("indicador") or e.get("serie"))
    periodo = _txt(e.get("periodo"))
    if nombre and not re.fullmatch(r"fila \d+", nombre):
        return f"En «{nombre}»" + (f" {periodo}" if periodo else "") + ", "
    if _txt(e.get("hoja")):
        return f"En la hoja «{_txt(e.get('hoja'))}»" + (f" ({periodo})" if periodo else "") + ", "
    return f"En {periodo}, " if periodo else ""


def _periodo_de_ubicacion(ubicacion: Any) -> str:
    m = re.search(r"per[ií]odo:\s*([^;)]+)", str(ubicacion or ""), re.I)
    return f" en {m.group(1).strip()}" if m else ""


def _supera(e: dict[str, Any]) -> str:
    muestras = e.get("muestras_violacion") or []
    mayor, menor = _col(e.get("columna_mayor")), _col(e.get("columna_menor"))
    lugar = f"En la hoja «{_txt(e['hoja'])}», " if _txt(e.get("hoja")) else ""
    a_menor = "al " + menor[3:] if menor.startswith("el ") else f"a {menor}"
    n = int(_f(e.get("filas_en_violacion")) or 0)
    if muestras and isinstance(muestras[0], dict):
        m = muestras[0]
        frase = (f"{lugar}{mayor} ({_n(m.get('valor_mayor'))}) supera {a_menor} ({_n(m.get('valor_menor'))})"
                 f"{_periodo_de_ubicacion(m.get('ubicacion'))}")
        return _mayus(frase) + (f"; pasa en {n} filas." if n > 1 else ".")
    mayor_total, menor_total = _f(e.get("total_mayor")), _f(e.get("total_menor"))
    if mayor_total is not None and menor_total is not None and mayor_total > menor_total:
        return _mayus(f"{lugar}en el total, {mayor} ({_n(mayor_total)}) supera {a_menor} ({_n(menor_total)})") + "."
    if n > 1:
        return _mayus(f"{lugar}{mayor} supera {a_menor} en {n} filas") + "."
    detalle = (e.get("filas_detalle") or [""])[0]
    return _mayus(f"{lugar}{mayor} supera {a_menor} en una fila{_periodo_de_ubicacion(detalle)}") + "."


def _vigente_no_cierra(e: dict[str, Any]) -> str:
    muestras = e.get("muestras") or e.get("muestras_violacion") or []
    if muestras and isinstance(muestras[0], dict):
        m = muestras[0]
        return (f"El crédito vigente ({_n(m.get('vigente_declarado'))}) no coincide con el inicial más las modificaciones "
                f"({_n(m.get('vigente_calculado'))}){_periodo_de_ubicacion(m.get('ubicacion'))}.")
    return "El crédito vigente no coincide con el crédito inicial más las modificaciones."


def _gasto_real(e: dict[str, Any]) -> str:
    muestras = e.get("muestras") or []
    if muestras and isinstance(muestras[0], dict):
        m = muestras[0]
        return f"En «{_txt(m.get('rubro'))}», el gasto real ({_n(m.get('real'))}) supera lo presupuestado ({_n(m.get('presupuesto'))})."
    return "El gasto real supera lo presupuestado en al menos una fila de egreso."


def _total_vs_suma(declarado: Any, calculado: Any, total: str = "el total declarado") -> str:
    return f"{total} ({_n(declarado)}) no coincide con la suma de sus componentes ({_n(calculado)})"


def _conciliacion(e: dict[str, Any]) -> str:
    return _en(e) + _total_vs_suma(e.get("total_declarado"), e.get("total_reconstruido")) + "."


def _partes_no_suman(e: dict[str, Any]) -> str:
    m = e.get("muestra") if isinstance(e.get("muestra"), dict) else {}
    total = f"«{_txt(e.get('columna_total'))}»" if _txt(e.get("columna_total")) else "el total"
    componentes = [f"«{_txt(c)}»" for c in (e.get("columnas_componentes") or [])]
    if 1 < len(componentes) <= 3 and m:
        return (f"La suma de {' y '.join(componentes)} ({_n(m.get('calculado'))}) no coincide con {total} "
                f"({_n(m.get('declarado'))}){_periodo_de_ubicacion(m.get('ubicacion'))}.")
    if m:
        return _mayus(_total_vs_suma(m.get("declarado"), m.get("calculado"), total)) + "."
    return f"{_mayus(total)} no coincide con la suma de sus componentes."


def _total_filas(e: dict[str, Any]) -> str:
    fila = _rotulo_fila(e.get("fila_detalle"))
    return (f"En «{fila}», «{_txt(e.get('columna'))}» declara {_n(e.get('declarado'))} y las filas de su grupo "
            f"suman {_n(e.get('calculado'))}.")


def _total_columna(e: dict[str, Any]) -> str:
    columna = f" ({_txt(e.get('columna'))})" if _txt(e.get("columna")) else ""
    nombre = _txt(e.get("indicador"))
    return (f"En «{nombre}»{columna}, el total declarado ({_n(e.get('total_declarado'))}) no coincide con la suma "
            f"de su grupo ({_n(e.get('total_reconstruido'))}).")


def _total_omite_bloques(e: dict[str, Any]) -> str:
    omitidos = [f"«{_txt(b)}»" for b in (e.get("bloques_omitidos") or []) if _txt(b)]
    nombre = _txt(e.get("indicador"))
    if not omitidos:
        return _total_columna(e)
    lista = ", ".join(omitidos[:-1]) + f" y {omitidos[-1]}" if len(omitidos) > 1 else omitidos[0]
    return (f"El total «{nombre}» omite {lista}: suma sólo los demás bloques. Con ellos sería "
            f"{_n(e.get('total_reconstruido'))} en lugar de {_n(e.get('total_declarado'))}.")


def _componente_cruzado(e: dict[str, Any]) -> str:
    columna = f" ({_txt(e.get('columna'))})" if _txt(e.get("columna")) else ""
    return (f"En «{_txt(e.get('indicador'))}»{columna}, el valor {_n(e.get('valor_observado'))} hace que no cierren "
            f"el total de su fila ni el de su columna; con {_n(e.get('valor_que_cierra'))} cerrarían ambos.")


def _declarado_calculado(texto_total: str):
    def plantilla(e: dict[str, Any]) -> str:
        return f"{texto_total} ({_n(e.get('valor_declarado'))}) no coincide con lo que dan sus componentes ({_n(e.get('valor_calculado'))})."
    return plantilla


def _complemento(e: dict[str, Any]) -> str:
    return f"Los porcentajes complementarios suman {_n(e.get('valor_calculado'))}, cuando deberían sumar {_n(e.get('valor_esperado') or 100)}."


def _consolidado_pdf(e: dict[str, Any]) -> str:
    periodo = f" en {_txt(e.get('periodo'))}" if _txt(e.get("periodo")) else ""
    return (f"En el PDF, las partes de «{_txt(e.get('columna'))}»{periodo} suman {_n(e.get('valor_calculado'))} "
            f"y «{_txt(e.get('etiqueta_total'))}» declara {_n(e.get('valor_declarado'))}.")


def _fila_pdf(e: dict[str, Any]) -> str:
    pagina = f" de la página {_txt(e.get('pagina_pdf'))}" if _txt(e.get("pagina_pdf")) else ""
    return (f"En el cuadro{pagina} del PDF, los rubros de la fila suman {_n(e.get('valor_calculado'))} "
            f"y «{_txt(e.get('columna_total'))}» declara {_n(e.get('valor_declarado'))}.")


def _porcentaje_base(e: dict[str, Any]) -> str:
    return (f"El valor declarado ({_n(e.get('valor_declarado'))}) no coincide con el {_n(e.get('porcentaje'))} % "
            f"de {_n(e.get('base'))}, que da {_n(e.get('valor_calculado'))}.")


def _variacion_signo(e: dict[str, Any]) -> str:
    return (f"El texto declara una variación «{_txt(e.get('texto_declarado'))}», pero la serie pasa de "
            f"{_n(e.get('valor_previo'))} a {_n(e.get('valor_actual'))}.")


def _texto_tabla(e: dict[str, Any]) -> str:
    return (f"Para {_txt(e.get('mes'))} {_txt(e.get('anio_actual'))}, el texto destacado del PDF dice "
            f"{_n(e.get('valor_actual_texto'))} y la tabla dice {_n(e.get('valor_actual_tabla'))}.")


def _anio_duplicado(e: dict[str, Any]) -> str:
    hoja = f"En la hoja «{_txt(e.get('hoja'))}», " if _txt(e.get("hoja")) else ""
    columna = f" en la columna «{_txt(e.get('indicador'))}»" if _txt(e.get("indicador")) else ""
    return _mayus(f"{hoja}el período {_txt(e.get('valor_observado') or e.get('periodo'))} aparece repetido{columna}.")


def _cambio_edicion(e: dict[str, Any]) -> str:
    return (f"{_en(e)}el valor es {_n(e.get('valor_observado'))} y en la edición anterior era "
            f"{_n(e.get('valor_edicion_anterior'))}; el resto de la serie no cambió.")


def _serie_revisada(e: dict[str, Any]) -> str:
    nombre = _txt(e.get("indicador"))
    return (f"«{nombre}» cambió en {_txt(e.get('periodos_cambiados'))} de {_txt(e.get('periodos_comparables'))} años "
            f"respecto de la edición anterior; por ejemplo, {_txt(e.get('periodo'))}: "
            f"{_n(e.get('valor_edicion_anterior'))} → {_n(e.get('valor_observado'))}.")


def _cambio_tipo(e: dict[str, Any]) -> str:
    celda = f"la celda {_txt(e.get('celda'))}" if _txt(e.get("celda")) else "una celda"
    return f"{_en(e)}{celda} tiene un texto («{_txt(e.get('valor_observado'))}») donde la serie tiene números."


def _pico(e: dict[str, Any]) -> str:
    return (f"{_en(e)}el valor {_n(e.get('valor_observado'))} sale de la escala de sus vecinos "
            f"({_n(e.get('valor_anterior'))} y {_n(e.get('valor_posterior'))}) por un solo período.")


def _escala_extremo(e: dict[str, Any]) -> str:
    valor, anterior = _f(e.get("valor_observado")), _f(e.get("valor_anterior"))
    if valor and anterior and (valor > 0) == (anterior > 0):
        veces = max(abs(valor), abs(anterior)) / min(abs(valor), abs(anterior))
        return (f"{_en(e)}el valor {_n(valor)} queda en otra escala que el anterior ({_n(anterior)}): "
                f"unas {_entero(veces)} veces de diferencia.")
    return f"{_en(e)}el valor {_n(e.get('valor_observado'))} queda en otra escala que lo que sigue la serie."


def _signo(e: dict[str, Any]) -> str:
    valor = _f(e.get("valor_observado"))
    signo = "el único positivo entre valores negativos" if valor is not None and valor > 0 else "el único negativo entre valores positivos"
    if _f(e.get("valor_anterior")) is None or _f(e.get("valor_posterior")) is None:
        vecino = _f(e.get("valor_anterior")) if _f(e.get("valor_anterior")) is not None else _f(e.get("valor_posterior"))
        borde = "último" if _f(e.get("valor_anterior")) is not None else "primer"
        return f"{_en(e)}el valor {_n(e.get('valor_observado'))} es {signo}, en el {borde} período (junto a {_n(vecino)})."
    return f"{_en(e)}el valor {_n(e.get('valor_observado'))} es {signo} ({_n(e.get('valor_anterior'))} y {_n(e.get('valor_posterior'))})."


def _vacio(e: dict[str, Any]) -> str:
    celda = f"la celda {_txt(e.get('celda'))}" if _txt(e.get("celda")) else "una celda"
    return f"{_en(e)}{celda} está vacía dentro de una serie con datos."


def _repetido(e: dict[str, Any]) -> str:
    return f"{_en(e)}el valor {_n(e.get('valor_observado'))} se repite exacto respecto del período anterior, mientras el resto de la serie cambia."


def _fuera_escala_columna(e: dict[str, Any]) -> str:
    valor, mediana = _f(e.get("valor_observado")), _f(e.get("mediana_columna"))
    if valor and mediana and (valor > 0) == (mediana > 0):
        sentido = "por encima" if abs(valor) > abs(mediana) else "por debajo"
        veces = max(abs(valor), abs(mediana)) / min(abs(valor), abs(mediana))
        return (f"En la columna «{_txt(e.get('columna'))}», el valor {_n(valor)} está {_entero(veces)} veces "
                f"{sentido} de la mediana ({_n(mediana)}).")
    return f"En la columna «{_txt(e.get('columna'))}», el valor {_n(e.get('valor_observado'))} queda fuera de la escala de la columna."


def _negativo(e: dict[str, Any]) -> str:
    filas = e.get("filas") or []
    cuantas = f" en {len(filas)} filas" if len(filas) > 1 else ""
    return f"La columna «{_txt(e.get('columna'))}» tiene valores negativos{cuantas}, aunque representa una magnitud que no es negativa."


def _acumulado_retrocede(e: dict[str, Any]) -> str:
    n = int(_f(e.get("retrocesos")) or 1)
    return f"La serie acumulada «{_txt(e.get('columna'))}» disminuye en {n} {'período' if n == 1 else 'períodos'}, cuando un acumulado sólo sube o se mantiene."


def _acumulado_sin_avance(e: dict[str, Any]) -> str:
    return (f"El acumulado de «{_txt(e.get('columna'))}» repite el valor anterior ({_n(e.get('valor_repetido'))}) "
            f"y después salta a {_n(e.get('valor_siguiente'))}.")


def _poblacion(e: dict[str, Any]) -> str:
    vecinos = [_entero(v) for v in (e.get("poblacion_vecinos") or [])][:2]
    return (f"{_en(e)}el importe y el valor por persona implican {_entero(e.get('poblacion_implicita'))} personas, "
            f"frente a {' y '.join(vecinos) or '—'} en los años vecinos.")


def _identidad(e: dict[str, Any]) -> str:
    return (f"«{_txt(e.get('indicador'))}» y otra apertura del mismo importe coinciden en {_txt(e.get('periodos_coincidentes'))} "
            f"de {_txt(e.get('periodos_comparables'))} períodos, pero en {_txt(e.get('periodo'))} valen "
            f"{_n(e.get('valor_observado'))} y {_n(e.get('valor_otra_apertura'))}.")


def _contexto_periodo(e: dict[str, Any]) -> str:
    hojas = e.get("hojas") or []
    en_hojas = f" en {len(hojas)} hojas" if len(hojas) > 1 else ""
    cantidad = int(_f(e.get("cantidad_senales_originales")) or 0)
    if cantidad <= 1:
        return f"En {_txt(e.get('periodo'))} hay una variación anual que conviene leer con el contexto de ese año."
    return (f"En {_txt(e.get('periodo'))}, {cantidad} variaciones anuales aparecen a la vez"
            f"{en_hojas}: puede haber un cambio de contexto en ese año.")


def _corte(e: dict[str, Any]) -> str:
    ratio = _f(e.get("ratio_vs_movimiento_tipico"))
    previo, actual = _f(e.get("valor_previo")), _f(e.get("valor_actual"))
    cambio = ""
    if previo and actual and previo > 0 and actual > 0:
        cambio = (f": se multiplica por {_uno(actual / previo)}" if actual >= previo
                  else f": se divide por {_uno(previo / actual)}")
    if ratio:
        cambio += ", un salto mucho mayor que los habituales de la serie" if ratio >= 10 else ", más que los saltos habituales de la serie"
    return (f"«{_txt(e.get('serie')).replace('_', ' ')}» pasa de {_n(e.get('valor_previo'))} en {_txt(e.get('periodo_previo'))} a "
            f"{_n(e.get('valor_actual'))} en {_txt(e.get('periodo'))}{cambio}.")


def _salto_escala_final(e: dict[str, Any]) -> str:
    anterior, valor = _f(e.get("valor_anterior")), _f(e.get("valor_observado"))
    if anterior is None or valor is None:
        return ""
    cae = abs(valor) < abs(anterior)
    sigue = f" y sigue en {_n(e.get('valor_posterior'))}" if _f(e.get("valor_posterior")) is not None else ""
    factor = _f(e.get("factor_escala"))
    veces = (f"; desde ese año queda unas {_entero(factor)} veces {'por debajo' if cae else 'por encima'} de lo anterior"
             if factor else "")
    return f"{_en(e)}el valor {'cae' if cae else 'sube'} de {_n(anterior)} a {_n(valor)}{sigue}{veces}."


def _corte_conjunto(e: dict[str, Any]) -> str:
    series = [f"«{_txt(serie).replace('_', ' ')}»" for serie in (e.get("series_compactas") or e.get("series") or [])][:3]
    cuales = f" ({', '.join(series)})" if series else ""
    return (f"En {_txt(e.get('periodo'))}, {_txt(e.get('cantidad_series') or len(series))} series saltan a la vez"
            f"{cuales} respecto de {_txt(e.get('periodo_previo'))}.")


def _fisico_financiero(e: dict[str, Any]) -> str:
    variaciones = e.get("variaciones") or {}
    columnas = list(e.get("columnas") or variaciones)
    unidad = "puntos" if e.get("unidad_variacion") == "puntos_porcentuales" else "%"
    if len(columnas) == 2 and all(_f(variaciones.get(c)) is not None for c in columnas):
        financiera, fisica = columnas  # la regla las guarda en ese orden
        v_fin, v_fis = _f(variaciones[financiera]), _f(variaciones[fisica])
        quien = "el avance físico no acompaña al financiero" if abs(v_fin) > abs(v_fis) else "el avance financiero no acompaña al físico"
        return (f"En {_txt(e.get('periodo'))}, «{_txt(financiera).replace('_', ' ')}» cambia {_uno(v_fin)} {unidad} y "
                f"«{_txt(fisica).replace('_', ' ')}» {_uno(v_fis)} {unidad}: {quien}.")
    return f"En {_txt(e.get('periodo'))}, el avance físico y el financiero no se mueven juntos."


def _operativa_espera(e: dict[str, Any]) -> str:
    v = e.get("variaciones_pct") or {}
    columnas = list(v)
    if len(columnas) >= 3:
        demanda, personal, espera = columnas[:3]
        return (f"En {_txt(e.get('periodo'))}, «{demanda}» sube {_n(v[demanda])} % y «{espera}» baja {_n(abs(v[espera]))} % "
                f"con «{personal}» casi sin cambio.")
    return f"En {_txt(e.get('periodo'))}, la demanda sube y el tiempo de espera baja sin más personal."


def _operativa_satisfaccion(e: dict[str, Any]) -> str:
    v = e.get("variaciones_pct") or {}
    columnas = list(v)
    if len(columnas) >= 3:
        sat, rec, enc = columnas[:3]
        return (f"En {_txt(e.get('periodo'))}, «{sat}» sube {_n(v[sat])} % mientras «{rec}» sube {_n(v[rec])} % "
                f"y «{enc}» baja {_n(abs(v[enc]))} %.")
    return f"En {_txt(e.get('periodo'))}, la satisfacción sube mientras suben los reclamos y bajan las encuestas respondidas."


def _relacion_orquesta(e: dict[str, Any]) -> str:
    columnas = [f"«{_txt(c).replace('_', ' ')}»" for c in (e.get("columnas") or [])][:2]
    desvio = _f(e.get("desvio_relativo_pct"))
    if len(columnas) == 2 and desvio is not None:
        cuando = f"En {_txt(e.get('periodo'))}, la" if _txt(e.get("periodo")) else "En el último período, la"
        return f"{cuando} relación entre {columnas[0]} y {columnas[1]} se aparta {_uno(desvio)} % de su valor habitual."
    return GENERICA_POR_LENTE["orquesta"]


def _correlacion_rota(e: dict[str, Any]) -> str:
    columnas = [f"«{_txt(c).replace('_', ' ')}»" for c in (e.get("columnas") or [])][:2]
    r = _f(e.get("correlacion_historica"))
    if len(columnas) == 2:
        if r is not None and r < 0:
            return (f"{columnas[0]} y {columnas[1]} venían moviéndose en sentido opuesto (correlación {_dos(r)}), "
                    "pero en el último período no.")
        return (f"{columnas[0]} y {columnas[1]} venían moviéndose juntas" + (f" (correlación {_dos(r)})" if r is not None else "")
                + ", pero en el último período se separan.")
    return GENERICA_POR_LENTE["orquesta"]


def _orquesta_sin_regla(e: dict[str, Any]) -> str:
    return _relacion_orquesta(e) if e.get("desvio_relativo_pct") is not None else _correlacion_rota(e)


def _benford(e: dict[str, Any]) -> str:
    cantidad = f" ({_txt(e.get('n'))} valores)" if _txt(e.get("n")) else ""
    return f"Hipótesis para explorar: los primeros dígitos de «{_txt(e.get('columna'))}»{cantidad} no siguen la distribución de Benford."


def _radiologo(e: dict[str, Any]) -> str:
    if e.get("fuente_comparacion") == "banco_historico":
        n = _txt(e.get("n_casos_comparados"))
        contra = f"Comparado con {n} informes anteriores del banco histórico" if n else "Comparado con informes anteriores del banco histórico"
    else:
        contra = "Comparado con los períodos anteriores del mismo archivo"
    return f"{contra}, «{_txt(e.get('columna'))}» en {_txt(e.get('periodo_comparado'))} queda fuera de su rango habitual."


def _rizoma(e: dict[str, Any]) -> str:
    columnas = [f"«{_txt(c)}»" for c in (e.get("columnas") or [])][:2]
    r = _f(e.get("correlacion") or e.get("coeficiente_pearson"))
    if len(columnas) == 2:
        sentido = "en sentido opuesto" if r is not None and r < 0 else "juntas"
        return f"Hipótesis para explorar: {columnas[0]} y {columnas[1]} se mueven {sentido}" + (f" (correlación {_dos(r)})." if r is not None else ".")
    return GENERICA_POR_LENTE["rizoma"]


def _conciliacion_previa(e: dict[str, Any]) -> str:
    hoja = f" de «{_txt(e.get('hoja'))}»" if _txt(e.get("hoja")) else ""
    return f"Antes de leer las señales{hoja}, conviene revisar las notas de cobertura o metodología que trae el archivo."


def _textual_pdf(e: dict[str, Any]) -> str:
    pagina = f"La página {_txt(e.get('pagina_pdf'))} del PDF" if _txt(e.get("pagina_pdf")) else "El PDF"
    termino_txt = _txt(e.get("termino_detectado"))
    termino = f" «{termino_txt}»" if termino_txt and not _VEREDICTO.search(termino_txt) else " un control"
    return f"{pagina} menciona{termino}; conviene leerla en su contexto."


def _rubro_otra_escala(e: dict[str, Any]) -> str:
    f = _f(e.get("factor_que_cierra"))
    if not f:
        return GENERICA_POR_LENTE["ajedrecista"]
    cambio = f"se dividen por {_entero(1 / f)}" if f < 1 else f"se multiplican por {_entero(f)}"
    return (f"«{_txt(e.get('indicador'))}» parece estar en otra escala: «{_txt(e.get('fila_total'))}» cierra en "
            f"{_txt(e.get('periodos_que_cierran'))} de {_txt(e.get('periodos_comparables'))} períodos si sus valores {cambio}.")


def _unidad_columna(e: dict[str, Any]) -> str:
    return f"La columna «{_txt(e.get('indicador'))}» declara en su encabezado una unidad propia ({_txt(e.get('unidad_columna'))}), distinta del resto del cuadro."


PLANTILLAS.update({
    "devengado_supera_vigente": _supera, "pagado_supera_devengado": _supera, "pagado_supera_vigente": _supera,
    "devengado_supera_comprometido": _supera, "comprometido_supera_vigente": _supera,
    "credito_vigente_no_cierra_con_modificaciones": _vigente_no_cierra,
    "gasto_real_supera_presupuesto": _gasto_real,
    "conciliacion_aritmetica": _conciliacion,
    "partes_no_suman_total": _partes_no_suman,
    "resueltas_mas_pendientes_no_cierran_consultas": _partes_no_suman,
    "total_de_filas_no_cierra": _total_filas,
    "total_columna_no_cierra": _total_columna,
    "columna_total_no_cierra": _total_columna,
    "total_sin_rotulo_no_cierra": _total_columna,
    "total_bloques_no_cierra": _total_columna,
    "total_omite_bloques": _total_omite_bloques,
    "saldo_final_no_cierra": _declarado_calculado("El saldo final declarado"),
    "componente_no_cierra_fila_y_columna": _componente_cruzado,
    "componentes_no_cierran_total": _declarado_calculado("El total declarado"),
    "brecha_b_menos_a_no_cierra": _declarado_calculado("La brecha declarada"),
    "complemento_porcentual_no_cierra": _complemento,
    "consolidado_no_cierra_pdf": _consolidado_pdf,
    "total_de_fila_no_cierra_pdf": _fila_pdf,
    "porcentaje_de_base_no_cierra": _porcentaje_base,
    "variacion_declarada_con_signo_inconsistente": _variacion_signo,
    "texto_destacado_no_coincide_con_tabla": _texto_tabla,
    "anio_duplicado": _anio_duplicado,
    "cambio_entre_ediciones": _cambio_edicion,
    "serie_revisada_entre_ediciones": _serie_revisada,
    "cambio_tipo": _cambio_tipo,
    "pico_aislado": _pico,
    "escala_extremo": _escala_extremo,
    "signo_aislado": _signo,
    "vacio_interior": _vacio,
    "valor_repetido": _repetido,
    "valor_fuera_de_escala_columna": _fuera_escala_columna,
    "valor_negativo_en_magnitud_no_negativa": _negativo,
    "serie_acumulada_retrocede": _acumulado_retrocede,
    "acumulado_sin_avance": _acumulado_sin_avance,
    "poblacion_implicita": _poblacion,
    "identidad_entre_cuadros": _identidad,
    "contexto_compartido_periodo": _contexto_periodo,
    "corte_temporal": _corte,
    "corte_temporal_conjunto": _corte_conjunto,
    "coherencia_fisico_financiera_agregada": _fisico_financiero,
    "coherencia_operativa_espera": _operativa_espera,
    "coherencia_operativa_satisfaccion": _operativa_satisfaccion,
    "primer_digito_no_conforme_benford": _benford,
    "conciliacion_tecnica_previa": _conciliacion_previa,
    "control_textual_pdf": _textual_pdf,
    "unidad_columna_distinta": _unidad_columna,
    "rubro_en_otra_escala": _rubro_otra_escala,
    "salto_escala_final": _salto_escala_final,
})

# Hallazgos sin regla propia: se reconocen por la forma de su evidencia.
PLANTILLAS_SIN_REGLA = {
    "orquesta": (lambda e: e.get("desvio_relativo_pct") is not None or e.get("correlacion_historica") is not None,
                 _orquesta_sin_regla),
    "radiologo": (lambda e: e.get("columna") and e.get("periodo_comparado"), _radiologo),
    "rizoma": (lambda e: len(e.get("columnas") or []) >= 2, _rizoma),
}


# --- Presentación de hallazgos ya guardados -----------------------------------------------------

def _campo(h: Any, clave: str) -> Any:
    return h.get(clave) if isinstance(h, dict) else getattr(h, clave, None)


def resumen_de(h: Any) -> str:
    """Frase «Qué pasó» de un hallazgo (dict u objeto de la base); si no la tiene, se arma al mostrarlo."""
    guardada = _campo(h, "resumen_llano")
    # Una frase genérica guardada se vuelve a armar: puede haber ganado plantilla después de la corrida.
    if guardada and str(guardada) not in _GENERICAS:
        return str(guardada)
    from services.guardrails import sanitizar_texto

    return sanitizar_texto(resumen_llano({"lente": _campo(h, "lente"), "evidencia": _campo(h, "evidencia") or {}}))


def _fin_formula(texto: str, inicio: int) -> tuple[int, bool]:
    """Dónde termina la fórmula y si quedó bien cerrada (paréntesis y comillas)."""
    profundidad, comilla, k = 0, None, inicio + 1
    while k < len(texto):
        ch = texto[k]
        if comilla:
            if ch == comilla:
                comilla = None
        elif ch in "\"'":
            comilla = ch
        elif ch == "(":
            profundidad += 1
        elif ch == ")":
            if profundidad == 0:
                break
            profundidad -= 1
        elif profundidad == 0 and (ch.isspace() or ch in ";,"):
            break
        k += 1
    cerrada = profundidad == 0 and comilla is None
    while k > inicio + 1 and texto[k - 1] in ".:":
        k -= 1
    return k, cerrada


def traducir_en_texto(texto: Any, separador: str | None = None) -> str:
    """Traduce las fórmulas de Excel que aparecen dentro de un texto (descripciones, preguntas).

    Sólo toca fragmentos que empiezan con «=» seguido de una función o referencia y que contienen
    una función; el resto del texto queda igual.
    """
    s = str(texto or "")
    salida, i = [], 0
    while True:
        j = s.find("=", i)
        if j < 0:
            break
        siguiente = s[j + 1] if j + 1 < len(s) else ""
        anterior = s[j - 1] if j > 0 else " "
        if (siguiente.isalpha() or siguiente in "$'_") and not (anterior.isalnum() or anterior in "<>!="):
            k, cerrada = _fin_formula(s, j)
            fragmento = s[j:k]
            if cerrada and ("(" in fragmento or re.search(r"\d\.\d", fragmento)):
                salida.append(s[i:j])
                salida.append(traducir_formula(fragmento, separador))
                i = k
                continue
        salida.append(s[i:j + 1])
        i = j + 1
    salida.append(s[i:])
    return "".join(salida)
