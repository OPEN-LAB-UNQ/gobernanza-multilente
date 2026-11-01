"""Perfilado liviano de datos agregados.

Adaptado de /home/Benford para esta app: detecta roles de columnas
(importe, periodo, dimension, identificador), convierte numeros en formatos
habituales de CSV/Excel y expone helpers compartidos por las lentes. No usa
identificadores sensibles como dimensiones analiticas.
"""
from __future__ import annotations

import contextvars
import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from typing import Any


def normalizar_texto(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


# Marcas habituales de «sin dato» en cuadros públicos: no son un valor ni un cero.
SIN_DATO = frozenset({
    "-", "--", "---", "\u2013", "\u2014", "s/d", "s/d.", "s.d.", "sd", "n/d", "n.d.", "nd", "n/a",
    ".", "...", "..", "\u2026", "s/dato", "sin dato", "sin datos",
    # \u00abs/i\u00bb (sin informaci\u00f3n) y \u00ab///\u00bb (dato no disponible) en cuadros de una oficina de presupuesto y de un instituto de estadística.
    "s/i", "s/i.", "s/inf", "s/inf.", "///",
    # «n.d.» y «s.d.» escritos con comas, como en planillas de un ministerio.
    "n,d,", "n,d", "s,d,", "s,d", "n.d", "s.d",
})


# Dato suprimido por confidencialidad estadística: «<5» (entre 1 y 4 casos; un entero chico, de 2 a
# 10) o «s.e.» (secreto estadístico). No es un número: «<5» no vale 5. «<100» o «<2020» no son
# marcas de confidencialidad; «s/e» suele ser «sin especificar».
SUPRIMIDO_RE = re.compile(r"^\s*(?:[<≤]\s*(?:[2-9]|10)|s\.\s?e\.)\s*$", re.I)
# Valor menor que la unidad mínima publicada («<0,1», «<0.5», «<1»): existe pero no se informa la cifra.
MENOR_UNIDAD_RE = re.compile(r"^\s*[<≤]\s*(?:0[.,]\d+|1)\s*$")


def es_suprimido(valor: Any) -> bool:
    return isinstance(valor, str) and bool(SUPRIMIDO_RE.match(valor))


def es_menor_unidad(valor: Any) -> bool:
    return isinstance(valor, str) and bool(MENOR_UNIDAD_RE.match(valor))


def es_no_publicado(valor: Any) -> bool:
    """Dato que existe y no se publica: suprimido por confidencialidad o menor que la unidad mínima."""
    return es_suprimido(valor) or es_menor_unidad(valor)


def es_sin_dato(valor: Any) -> bool:
    return isinstance(valor, str) and (valor.strip().lower() in SIN_DATO or es_no_publicado(valor)
                                      or bool(re.fullmatch(r"\s*[-–—.]{1,3}\s*\(\s*\d+\s*\)\s*", valor)))


_MONEDA_RE = re.compile(r"(?i)u\$s|us\$|\bars\b|\busd\b|\$|%|[\s\u00a0\u202f]")
_ES_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
_EN_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


LLAMADA_NOTA_RE = re.compile(r"\s*(?:\*{1,3}|[†‡§]|[¹²³⁴⁵⁶⁷⁸⁹⁰]+|\((?:[a-z]|p|e|est|prov)\.?\))$", re.I)


def quitar_llamada_nota(texto: str) -> str:
    """«171.535*» → «171.535»: la llamada a una nota al pie no es parte del número."""
    return LLAMADA_NOTA_RE.sub("", texto) if any(ch.isdigit() for ch in texto) else texto


_FORMULA_TEXTO_RE = re.compile(r'=\s*"(.*)"')
# Unidad pegada a la cifra («147.348 ha», «12,5 km»): no es parte del número.
_UNIDAD_PEGADA_RE = re.compile(r"(?<=\d)\s*(?:ha|has|km²|km2|km|kg|tn|t|m²|m2|m³|m3|lts?|kwh|mwh|gwh|hab\.?|unid\.?)$", re.I)


def sin_formula_texto(texto: str) -> str:
    """«="12345"» → «12345»: así exportan algunos sistemas una cifra para que Excel no la cambie."""
    m = _FORMULA_TEXTO_RE.fullmatch(texto.strip())
    return m.group(1) if m else texto


def es_formula_texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(_FORMULA_TEXTO_RE.fullmatch(valor.strip()))


def unidad_pegada(valor: Any) -> str | None:
    """La unidad pegada a una cifra escrita («ha» en «147.348 ha»), o None."""
    if not isinstance(valor, str):
        return None
    m = _UNIDAD_PEGADA_RE.search(valor.strip())
    return m.group(0).strip().lower() if m else None


def tiene_llamada_nota(valor: Any) -> bool:
    return isinstance(valor, str) and bool(LLAMADA_NOTA_RE.search(valor.strip())) and any(ch.isdigit() for ch in valor)


def partes_numero(valor: Any) -> tuple[bool, str] | None:
    """(negativo, cuerpo) de un texto numérico: «(300.000)», «-1.234,5», «1.234-», «$ 12,5 %»."""
    if valor is None or isinstance(valor, bool):
        return None
    t = _MONEDA_RE.sub("", sin_formula_texto(str(valor).strip()).replace("\u2212", "-"))
    t = quitar_llamada_nota(t)
    t = _UNIDAD_PEGADA_RE.sub("", t)
    negativo = False
    if len(t) > 2 and t[0] == "(" and t[-1] == ")":
        negativo, t = True, t[1:-1]
    if t[:1] == "-":
        negativo, t = True, t[1:]
    elif t[:1] == "+":
        t = t[1:]
    elif len(t) > 1 and t[-1] == "-":
        negativo, t = True, t[:-1]
    t = expandir_cientifica(t) or t
    if not t or not t[0].isdigit() or not t[-1].isdigit() or not re.fullmatch(r"[\d.,]+", t):
        return None
    return negativo, t


_CIENTIFICA_RE = re.compile(r"(\d+(?:[.,]\d+)?)[eE]([+-]?\d{1,3})")


def expandir_cientifica(texto: str) -> str | None:
    """«4.203222e+06» → «4203222»: una cifra en notación científica, escrita sin exponente.

    Así la lee el mismo criterio que el resto de la columna; antes quedaba como texto y la
    columna entera se perdía.
    """
    m = _CIENTIFICA_RE.fullmatch(texto.strip())
    if not m:
        return None
    from decimal import Decimal, InvalidOperation

    try:
        valor = Decimal(m.group(1).replace(",", ".")).scaleb(int(m.group(2)))
    except InvalidOperation:
        return None
    return format(valor.normalize(), "f")


def evidencia_formato(cuerpo: str) -> str:
    """Qué dice un número escrito sobre el formato del archivo.

    «es» (punto de miles, coma decimal), «en» (coma de miles, punto decimal), «entero», o
    «ambiguo_punto» / «ambiguo_coma» cuando un único separador va seguido de exactamente tres
    dígitos («1.738»): ahí sólo el resto de la columna o del archivo puede decidir.
    """
    puntos, comas = cuerpo.count("."), cuerpo.count(",")
    if puntos and comas:
        return "es" if cuerpo.rfind(",") > cuerpo.rfind(".") else "en"
    if puntos > 1:
        return "es"
    if comas > 1:
        return "en"
    if puntos or comas:
        sep = "." if puntos else ","
        entero, decimales = cuerpo.split(sep)
        # «0.125» o «1772343.910» no pueden ser miles: el primer grupo de miles no empieza en
        # cero ni tiene más de tres dígitos.
        if len(decimales) != 3 or entero.startswith("0") or len(entero) > 3:
            return "en" if sep == "." else "es"
        return "ambiguo_punto" if sep == "." else "ambiguo_coma"
    return "entero"


def numero_con_formato(valor: Any, formato: str) -> float | int | None:
    """Convierte con un formato ya decidido («es» o «en»). Un texto que no respeta ese formato
    devuelve None: no se adivina celda por celda."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return valor
    partes = partes_numero(valor)
    if not partes:
        return None
    negativo, cuerpo = partes
    patron = _ES_RE if formato == "es" else _EN_RE
    if not patron.fullmatch(cuerpo):
        return None
    if formato == "es":
        limpio = cuerpo.replace(".", "").replace(",", ".")
    else:
        limpio = cuerpo.replace(",", "")
    try:
        resultado = int(limpio) if "." not in limpio else float(limpio)
    except ValueError:
        return None
    return -resultado if negativo else resultado


def votos_formato(valores) -> dict[str, int]:
    votos = {"es": 0, "en": 0, "ambiguo_punto": 0, "ambiguo_coma": 0, "entero": 0}
    for v in valores:
        if isinstance(v, str):
            partes = partes_numero(v)
            if partes:
                votos[evidencia_formato(partes[1])] += 1
    return votos


def preferencia_formato(valores) -> str | None:
    """Formato que muestra el archivo entero, o None si no hay evidencia que decida."""
    votos = votos_formato(valores)
    if votos["es"] > votos["en"]:
        return "es"
    if votos["en"] > votos["es"]:
        return "en"
    return None


def formato_columna(valores, preferencia: str | None = None) -> tuple[str, str]:
    """(formato, de dónde salió): la columna decide con sus propios valores; si ninguno es
    concluyente, decide el resto del archivo; si tampoco, el formato local (punto de miles)."""
    valores = list(valores)
    votos = votos_formato(valores)
    if votos["es"] != votos["en"]:
        return ("es" if votos["es"] > votos["en"] else "en"), "columna"
    # Una columna de enteros cortos («984») en la que los mayores llevan un solo separador
    # seguido de tres cifras («1,054» o «1.054») usa ese separador como miles: si fuera decimal,
    # serían los únicos valores con decimales, y siempre con tres.
    if votos["entero"] and bool(votos["ambiguo_punto"]) != bool(votos["ambiguo_coma"]):
        cortos = all(
            len(partes[1]) <= 3
            for partes in (partes_numero(v) for v in valores if isinstance(v, str))
            if partes and evidencia_formato(partes[1]) == "entero"
        )
        if cortos:
            return ("es" if votos["ambiguo_punto"] else "en"), "columna"
    if preferencia in {"es", "en"}:
        return preferencia, "archivo"
    if votos["ambiguo_punto"] or votos["ambiguo_coma"]:
        return "es", "predeterminado_ambiguo"
    return "es", "predeterminado"


def interpretar_columna(valores, preferencia: str | None = None, minimo: float = 0.6):
    """Lee una columna completa con un único criterio numérico.

    Devuelve (valores, informe). Si la columna no es numérica (menos de `minimo` de sus celdas
    con dato se leen como número) los valores vuelven sin tocar. En una columna numérica, «-» o
    «s/d» se conservan tal cual pero se cuentan como sin dato (`numero` las lee como None, no
    como cero ni como un valor raro), y las celdas que no se pueden leer conservan su texto y se
    cuentan: nunca se descartan en silencio.
    """
    valores = list(valores)
    formato, origen = formato_columna(valores, preferencia)
    con_dato = [
        (i, v) for i, v in enumerate(valores)
        if v is not None and not (isinstance(v, float) and v != v) and str(v).strip() and not es_sin_dato(v)
    ]
    convertidos = {i: numero_con_formato(v, formato) for i, v in con_dato}
    leidos = sum(1 for x in convertidos.values() if x is not None)
    informe = {
        "numerica": bool(con_dato) and leidos >= minimo * len(con_dato),
        "formato": formato,
        "formato_decidido_por": origen,
        "convertidas": 0,
        "sin_dato": [],
        "suprimidos": [],
        "menores": [],
        "no_interpretables": [],
    }
    if not informe["numerica"]:
        return valores, informe
    nuevos = list(valores)
    for i, v in enumerate(valores):
        if es_sin_dato(v):
            informe["sin_dato"].append(i)
            if es_suprimido(v):
                informe["suprimidos"].append(i)
            elif es_menor_unidad(v):
                informe["menores"].append(i)
        elif i in convertidos:
            if convertidos[i] is None:
                informe["no_interpretables"].append(i)
            else:
                if isinstance(v, str):
                    informe["convertidas"] += 1
                nuevos[i] = convertidos[i]
    return nuevos, informe


def numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if es_no_publicado(valor):
        return None  # «<5» es un dato suprimido, no el número 5; «<0,1» no es 0,1
    text = str(valor).strip()
    if not text or text.lower() in SIN_DATO:
        return None
    partes = partes_numero(text)
    if partes:
        # Sin contexto de columna, sólo se resuelve lo inequívoco: «1.234.567», «1,234,567»,
        # «(300.000)», «1.234-». «1.738» sigue leyéndose como hasta ahora.
        negativo, cuerpo = partes
        evidencia = evidencia_formato(cuerpo)
        if evidencia in {"es", "en"} and (cuerpo.count(".") > 1 or cuerpo.count(",") > 1 or negativo):
            convertido = numero_con_formato(cuerpo, evidencia)
            if convertido is not None:
                return -float(convertido) if negativo else float(convertido)
        if negativo:
            positivo = numero(cuerpo)
            return -positivo if positivo is not None else None
    if re.search(r"[A-Za-zÀ-ÿ]", text):
        norm = normalizar_texto(text)
        # Admitir unidades/currency habituales sin convertir fechas textuales como "mayo de 2026".
        resto = re.sub(
            r"\b(usd|ars|us|m|mm|miles?|millones?|mill|p\.?p\.?|pp|por ciento|porcentaje|pts?|puntos?|de|en)\b|\$|%",
            "",
            norm,
        )
        resto = re.sub(r"[\d\s,\.\-+/()]+", "", resto)
        if resto.strip():
            return None
    text = re.sub(r"[^\d,\.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    comma_decimal = "," in text and ("." not in text or text.rfind(",") > text.rfind("."))
    if comma_decimal:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


_TIENE_DIGITO_RE = re.compile(r"\d")


@lru_cache(maxsize=50000)
def _fecha_texto(text: str) -> datetime | None:
    # Ninguno de los formatos ni el patron de trimestre puede matchear sin
    # al menos un digito (dia/mes/anio, o el anio del trimestre) -- se
    # descarta la enorme mayoria de columnas de texto (nombres, descripciones)
    # antes de tocar datetime.strptime, que es lo que dominaba el costo.
    if not _TIENE_DIGITO_RE.search(text):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    norm = re.sub(r"[^a-z0-9]+", " ", normalizar_texto(text))
    mensual = re.fullmatch(r"(ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|set(?:iembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)\s+(\d{2}|\d{4})(?:\s+(?:p|e|preliminar))?", norm.strip())
    if mensual:
        meses = {"ene":1,"feb":2,"mar":3,"abr":4,"may":5,"jun":6,"jul":7,"ago":8,"sep":9,"set":9,"oct":10,"nov":11,"dic":12}
        anio = int(mensual.group(2))
        anio = 2000 + anio if anio < 100 else anio
        return datetime(anio, meses[mensual.group(1)[:3]], 1)
    trimestre = re.search(r"\b([1-4])\s*(?:er|ro|do|to|o)?\s*trim(?:estre)?\b.*\b((?:19|20)\d{2})\b", norm)
    if not trimestre:
        trimestre = re.search(r"\b(i{1,3}|iv)\s*trim(?:estre)?\b.*\b((?:19|20)\d{2})\b", norm)
    if trimestre:
        valor_trim = trimestre.group(1)
        mapa_romano = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
        q = mapa_romano.get(valor_trim, int(valor_trim) if valor_trim.isdigit() else 0)
        year = int(trimestre.group(2))
        if 1 <= q <= 4:
            return datetime(year, (q - 1) * 3 + 1, 1)
    return None


def fecha(valor: Any) -> datetime | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    return _fecha_texto(str(valor).strip())


_DECLARADAS_IDENTIFICADORAS: contextvars.ContextVar[frozenset] = contextvars.ContextVar(
    "columnas_declaradas_identificadoras", default=frozenset()
)


def declarar_identificadores(nombres) -> object:
    """Columnas que la consulta declaró como códigos: valen como identificadores.

    Se declara al empezar cada análisis, siempre, aunque el conjunto quede vacío: así ninguna
    corrida hereda la restricción de la anterior. Devuelve el testigo para restaurar el estado.
    """
    return _DECLARADAS_IDENTIFICADORAS.set(
        frozenset(normalizar_texto(n) for n in (nombres or []) if str(n).strip())
    )


def restaurar_identificadores(testigo) -> None:
    _DECLARADAS_IDENTIFICADORAS.reset(testigo)


def _actor_agregado(nombre: str, valores: list[Any]) -> bool:
    """«Clientes activos», «Facturación», «Beneficiarios» con cifras: agregados, no identificadores."""
    from services.sanitizacion import ACTOR_AGREGADO_RE, ACTOR_PLURAL_RE, COLUMNA_NOMINAL_RE, _solo_numeros

    texto = str(nombre or "")
    if COLUMNA_NOMINAL_RE.search(texto):
        return False
    return bool(_solo_numeros(valores) and (ACTOR_AGREGADO_RE.search(texto) or ACTOR_PLURAL_RE.search(texto)))


# Los roles se deciden por palabra completa: «mes» no está en «Comestibles», «ano» no
# está en «Recursos humanos» ni en «Gasto mano de obra», «persona» no está en «Personal».
_TEMPORAL_RE = re.compile(
    r"(?<![a-z])(?:fecha|date|periodo|mes|meses|anio|ano|ejercicio|trimestre|semestre|year|month)(?![a-z])"
)
_ACTOR_RE = re.compile(
    r"proveedor|contratista|adjudicatari[oa]|cliente|vendor|supplier|razon|beneficiario|"
    r"(?<![a-z])personas?(?![a-z])|cuit|cuil|dni|email|telefono|factura|expediente"
)
# Rótulos de persona (ver sanitizacion.COLUMNA_PERSONA_RE): con texto adentro nombran a alguien.
_PERSONA_RE = re.compile(
    r"(?<![a-z])(?:agentes?|emplead[oa]s?|titular(?:es)?|pacientes?|docentes?|soci[oa]s?|"
    r"afiliad[oa]s?|alumn[oa]s?|destinatari[oa]s?|contactos?)(?![a-z])"
)
_DIMENSION_RE = re.compile(
    r"cuenta|rubro|categoria|tipo|area|centro|sector|proyecto|programa|inciso|partida|jurisdiccion|ministerio|finalidad|organismo|dependencia|unidad"
)
# «Proyectos aprobados», «Centros de salud», «Cantidad de unidades vendidas» con cifras
# cuentan cosas: no son una dimensión de clasificación.
_DIMENSION_CONTADA_RE = re.compile(
    r"(?<![a-z])(?:cantidad|cant|numero|nro|total|cuentas|rubros|categorias|tipos|areas|centros|sectores|proyectos|"
    r"programas|incisos|partidas|jurisdicciones|ministerios|organismos|dependencias|unidades)(?![a-z])"
)
_IDENTIFICADOR_RE = re.compile(
    r"identificador|(?:^|[^a-z])id(?:$|[^a-z])|(?<![a-z])(?:numero|nro|documento)(?![a-z])|origen|fila|"
    r"extraccion_pdf|pagina_pdf|paginas_pdf|tabla_pdf|limite_paginas_pdf|"
    r"paginas_documento|pdf_truncado|caracteres_extraidos|cantidad_numeros_detectados|muestra_numeros"
)
# «Número de casos» cuenta; «Número de expediente» identifica.
_CONTEO_RE = re.compile(
    r"(?<![a-z])(?:numero|nro)[\s_]+de[\s_]+(?!documento|expediente|legajo|orden|registro|identific|inscripci|"
    r"cuit|cuil|dni|serie|fila|tramite|id(?![a-z]))"
)


def _proporcion_numerica(valores: list[Any]) -> float:
    no_nulos = [v for v in valores if v is not None and str(v).strip()]
    if not no_nulos:
        return 0.0
    return sum(numero(v) is not None for v in no_nulos) / len(no_nulos)


def inferir_rol(nombre: str, valores: list[Any]) -> str:
    norm = normalizar_texto(nombre)
    if norm in _DECLARADAS_IDENTIFICADORAS.get():
        return "identificador"
    # Una edad en el grupo de una variable («Menor de 1 año Total») no es un período.
    sin_edad = re.sub(r"\b(?:(?:menor|mayor)(?:es)? de \d+|\d+ a \d+) anos?\b", "", norm)
    if _TEMPORAL_RE.search(sin_edad):
        return "temporal"
    if _ACTOR_RE.search(norm) and not _actor_agregado(nombre, valores):
        return "identificador"
    if _PERSONA_RE.search(norm) and _proporcion_numerica(valores) <= 0.7:
        return "identificador"
    if re.search(
        r"(^|_)(jurisdiccion|jur|saf|pg|sp|med|unidad_medida|programa|subprograma|medida)(_codigo|_cod)|codigo|cod_|^saf$|^pg$|^sp$|^jur$",
        norm,
    ):
        return "identificador"
    if re.search(
        r"cuentas?[\s_]*(a|por)[\s_]*(cobrar|pagar)|importe|monto|valor|total|neto|bruto|debe|haber|gasto|precio|amount|cost|credito|devengado|pagado|comprometido|compromiso|preventivo|obligado|ejecutado|vigente|sancionado|presupuestado|ventas|ingresos|egresos|cobranzas|facturacion|recaudacion|saldo|deuda|patrimonio|activo|pasivo|existencias|avance",
        norm,
    ):
        return "importe"
    if _DIMENSION_RE.search(norm) and not (
        _DIMENSION_CONTADA_RE.search(norm) and _proporcion_numerica(valores) > 0.9
    ):
        return "dimension"
    if _IDENTIFICADOR_RE.search(norm) and not (_CONTEO_RE.search(norm) and _proporcion_numerica(valores) > 0.9):
        return "identificador"
    no_nulos = [v for v in valores if v is not None and str(v).strip()]
    nums_ok = [numero(v) for v in no_nulos]
    nums_ok = [v for v in nums_ok if v is not None]
    if no_nulos and len(nums_ok) / len(no_nulos) > 0.7:
        return "numero"
    return "texto"


def perfilar(datos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    columnas = sorted({c for fila in datos for c in fila.keys()}) if datos else []
    perfiles: list[dict[str, Any]] = []
    for col in columnas:
        valores = [fila.get(col) for fila in datos]
        no_nulos = [v for v in valores if v is not None and str(v).strip()]
        nums = [numero(v) for v in no_nulos]
        fechas = [fecha(v) for v in no_nulos]
        numeric_count = sum(v is not None for v in nums)
        date_count = sum(v is not None for v in fechas)
        role = inferir_rol(col, valores)
        if no_nulos and date_count / len(no_nulos) > 0.6 and date_count > numeric_count:
            dtype = "fecha"
            role = "temporal"
        elif no_nulos and numeric_count / len(no_nulos) > 0.7:
            dtype = "numero"
        else:
            dtype = "texto"
        if dtype == "texto" and role == "importe" and numeric_count == 0:
            role = "dimension"
        perfiles.append(
            {
                "name": col,
                "dtype": dtype,
                "role": role,
                "non_null": len(no_nulos),
                "unique": len({str(v) for v in no_nulos}),
                "null_pct": round((1 - len(no_nulos) / max(len(valores), 1)) * 100, 2),
                "examples": [str(v) for v in no_nulos[:3]],
            }
        )
    return perfiles


def columnas_numericas(datos: list[dict[str, Any]], roles: set[str] | None = None) -> list[str]:
    roles = roles or {"importe", "numero"}
    return [p["name"] for p in perfilar(datos) if p["dtype"] == "numero" and p["role"] in roles]


def columnas_importe(perfiles: list[dict[str, Any]]) -> list[str]:
    return [p["name"] for p in perfiles if p.get("dtype") == "numero" and p.get("role") == "importe"]


def columnas_temporales(perfiles: list[dict[str, Any]]) -> list[str]:
    return [p["name"] for p in perfiles if p.get("role") == "temporal"]


def columnas_dimension(perfiles: list[dict[str, Any]]) -> list[str]:
    return [p["name"] for p in perfiles if p.get("role") == "dimension"]


PRESUPUESTO_PATTERNS = [
    ("credito_original", r"credito.*(original|inicial)|presupuesto.*(original|inicial)|sancionado"),
    ("credito_vigente", r"credito.*vigente|presupuesto.*vigente|credito.*actual"),
    # Anclado al comienzo: «Ejecutado con modificaciones» sigue siendo devengado.
    ("modificaciones", r"^(modificacion|reasignacion|variacion[\s_]+de[\s_]+credito|ajustes?[\s_]+(presupuestari|de[\s_]+credito))"),
    ("compromiso", r"compromiso|comprometido|preventivo"),
    ("devengado", r"devengado|obligado|ejecutado"),
    ("pagado", r"pagado|pago"),
]


# En el presupuesto público, una columna «Presupuesto»/«Presupuestado» sin más
# calificativo es el crédito con el que se ejecuta: se toma como vigente cuando
# no hay otra columna de crédito vigente.
PRESUPUESTO_SIMPLE_RE = re.compile(
    r"^(?:presupuest(?:o|ado)|credito)(?:[\s_]+(?:asignado|aprobado|anual|total|\(?\$\)?|en[\s_]+pesos))*$"
)


def columnas_etapas_presupuesto(perfiles: list[dict[str, Any]]) -> dict[str, str]:
    etapas: dict[str, str] = {}
    for p in perfiles:
        # Las modificaciones pueden ser negativas y no siempre se perfilan como importe.
        if p.get("role") not in {"importe", "numero"}:
            continue
        nombre = normalizar_texto(p.get("name"))
        for etapa, patron in PRESUPUESTO_PATTERNS:
            if p.get("role") != "importe" and etapa != "modificaciones":
                continue
            if etapa not in etapas and re.search(patron, nombre):
                etapas[etapa] = p["name"]
                break
    if "credito_vigente" not in etapas and ("devengado" in etapas or "pagado" in etapas):
        from services import ambito

        if not ambito.es_organizacion():
            usadas = set(etapas.values())
            for p in perfiles:
                nombre = normalizar_texto(p.get("name")).strip()
                if (
                    p.get("dtype") == "numero"
                    and p.get("role") in {"importe", "numero"}
                    and p["name"] not in usadas
                    and PRESUPUESTO_SIMPLE_RE.match(nombre)
                ):
                    etapas["credito_vigente"] = p["name"]
                    break
    return etapas


def suma(datos: list[dict[str, Any]], columna: str) -> float:
    return sum(numero(fila.get(columna)) or 0.0 for fila in datos)
