"""Formato del informe: números en es-AR y textos que nunca reescriben identificadores.

Los controles redactan sus descripciones con formatos distintos («2.11356e+10», «21,135,555,929»,
«192.828.843.503,00»). El informe que lee una persona usa uno solo: punto para miles y coma para
decimales. Los nombres de archivo, las referencias de celda, las versiones y los hashes son
identificadores y se dejan exactamente como están.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

# Un token que no debe tocarse: archivo con extensión, referencia de celda, versión, hash, ruta,
# fecha ISO o identificador con guion bajo.
_IDENTIFICADOR = re.compile(
    r"""(
        [\w\-.()]*[\w\-]\.(?:xlsx|xlsm|xls|csv|pdf|ods|txt|json|zip|docx?)\b   # archivos
      | (?<![\w])[A-Za-zÁÉÍÓÚÑáéíóúñ_(][\wÁÉÍÓÚÑáéíóúñ ()\-]{0,30}![A-Z]{1,3}\d+(?::[A-Z]{1,3}\d+)?  # Hoja!B5
      | \b[A-Z]{1,3}\d+:[A-Z]{1,3}\d+\b                                        # rangos sueltos
      | \b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{12,}\b                     # hashes
      | \b\w*_\w*\b                                                            # snake_case
      | \bv?\d+\.\d+\.\d+(?:[.\-]\w+)*\b                                       # versiones 0.8.74
      | \b\d{4}-\d{2}(?:-\d{2})?(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b              # fechas ISO
      | https?://\S+
      | `[^`]*`
    )""",
    re.X,
)

_CIENTIFICO = re.compile(r"(?<![\w.,])(-?\d+(?:\.\d+)?[eE][+-]?\d+)(?![\w.])")
_MILES_COMA = re.compile(r"(?<![\w.,])(-?\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?|-?\d{1,3},\d{3}\.\d+)(?![\w,]|\.\d)")
_UN_GRUPO_COMA = re.compile(r"(?<![\w.,])(-?\d{1,3},\d{3})(?![\w,]|[.,]\d)")
_DECIMAL_PUNTO = re.compile(r"(?<![\w.,])(-?\d+)\.(\d+)(?![\w]|[.,]\d)")


def _miles_coma(m):
    token = m.group(1)
    decimales = len(token.split(".")[1]) if "." in token else 0
    return numero(float(token.replace(",", "")), decimales)


def _decimal_punto(m, valores=()):
    entero, decimales = m.group(1), m.group(2)
    v = float(f"{entero}.{decimales}")
    # «1.590» puede ser mil quinientos noventa (es-AR) o uno coma cinco nueve. Si la evidencia tiene
    # el valor decimal (374,0846 para «374.085») y no el entero, es un decimal; si no, se deja.
    if len(decimales) == 3 and entero.lstrip("-") != "0" and len(entero.lstrip("-")) <= 3:
        enteros = {round(x) for x in valores if abs(x) < 1e15}
        cercanos = [x for x in valores if abs(x - v) <= 0.0005 + 1e-9]
        if int(entero + decimales) in enteros or not cercanos:
            return m.group(0)
        return _numero_de_texto(min(cercanos, key=lambda x: abs(x - v)))
    # Un único formato: más de dos decimales se redondean (hasta cuatro cifras significativas bajo 1).
    if len(decimales) > 2:
        return _numero_de_texto(v, len(decimales))
    return numero(v, len(decimales))


def _decimales_por_defecto(v: float) -> int:
    """Enteros sin coma; importes con 2 decimales; menores que 1 con 2 cifras significativas."""
    if float(v).is_integer():
        return 0
    a = abs(v)
    if a >= 1:
        return 2
    return min(10, max(2, 1 - math.floor(math.log10(a))))


def _numero_de_texto(v: float, maximo_decimales: int = 10) -> str:
    """Un número que vino escrito en un texto: importes con 2 decimales; bajo 1, hasta 4 cifras significativas.

    En los textos de los controles los valores menores que 1 suelen ser coeficientes (0,9963) o
    proporciones (0,0161 %): redondearlos a dos cifras les cambiaría el sentido.
    """
    a = abs(v)
    if a >= 1 or a == 0:
        return numero(v)
    return numero(v, min(maximo_decimales, 10, max(2, 3 - math.floor(math.log10(a)))))


def numero(valor, decimales=None):
    """Un número como se escribe acá: punto para miles, coma para decimales, nunca notación científica.

    Sin decimales pedidos: enteros sin coma, importes con 2 decimales y valores menores que 1 con
    dos cifras significativas (0,55; 0,023; 0,0087), para no mostrar 0,00 donde hay un dato.
    """
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if not math.isfinite(v):
        return str(valor)
    if decimales is None:
        decimales = _decimales_por_defecto(v)
    texto = f"{v:,.{decimales}f}"
    if decimales and float(texto.replace(",", "")) == 0 and v != 0:
        texto = f"{v:,.{_decimales_por_defecto(v)}f}"
    texto = texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return "0" if texto in {"-0", "-0,00"} else texto


def cifra(valor):
    """El formateador único del informe (es-AR). Alias explícito de `numero` sin decimales fijos."""
    return numero(valor)


_UNIDAD_PESOS = re.compile(r"\bpesos_(unidades|miles_de_millones|miles|millones)(?:_(corrientes|constantes))?\b")


def unidad_legible(unidad) -> str:
    """«pesos_millones_corrientes» → «millones de pesos corrientes»; el resto, sin guiones bajos."""
    texto = str(unidad or "").strip()
    if not texto:
        return ""

    def reemplazo(m):
        escala, tipo = m.group(1), m.group(2)
        base = "pesos" if escala == "unidades" else escala.replace("_", " ") + " de pesos"
        return base + (f" {tipo}" if tipo else "")

    texto = _UNIDAD_PESOS.sub(reemplazo, texto)
    return texto.replace("_", " ")


def porcentaje(valor, decimales=2):
    return numero(valor, decimales) + " %"


def _significativos(texto):
    mantisa = texto.lower().split("e")[0].lstrip("-")
    return len(mantisa.replace(".", "").lstrip("0")) or 1


def _cientifico(m, valores):
    token = m.group(1)
    v = float(token)
    for exacto in valores:
        if exacto and abs(exacto - v) <= abs(v) * 10 ** (1 - _significativos(token)) / 2 + 1e-12:
            return numero(exacto, 0 if float(exacto).is_integer() else 2)
    # Sin el valor exacto a mano: se escribe con los dígitos que trae, sin inventar precisión.
    digitos = _significativos(token)
    exponente = math.floor(math.log10(abs(v))) if v else 0
    decimales = max(0, digitos - 1 - exponente)
    return "≈" + numero(round(v, digitos - 1 - exponente), decimales)


def _numeros_de(evidencia) -> list[float]:
    out = []

    def recorrer(x, profundidad=0):
        if profundidad > 4:
            return
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            out.append(float(x))
        elif isinstance(x, dict):
            for v in x.values():
                recorrer(v, profundidad + 1)
        elif isinstance(x, (list, tuple)):
            for v in x[:200]:
                recorrer(v, profundidad + 1)

    recorrer(evidencia)
    return out


def _numeros_segmento(segmento: str, valores: Iterable[float]) -> str:
    valores = list(valores or [])
    segmento = _CIENTIFICO.sub(lambda m: _cientifico(m, valores), segmento)
    segmento = _MILES_COMA.sub(_miles_coma, segmento)
    if valores:
        # «10,425» es ambiguo; si la evidencia tiene 10.424,8 o 10.425, es un separador de miles.
        enteros = {round(v) for v in valores}
        segmento = _UN_GRUPO_COMA.sub(
            # «0,036» es un decimal en es-AR, nunca treinta y seis con separador de miles.
            lambda m: numero(float(m.group(1).replace(",", "")), 0)
            if int(m.group(1).replace(",", "")) in enteros and not m.group(1).lstrip("-").startswith("0,")
            else m.group(0),
            segmento,
        )
    segmento = _DECIMAL_PUNTO.sub(lambda m: _decimal_punto(m, valores), segmento)
    return segmento


def proteger(texto: str, transformar) -> str:
    """Aplica `transformar` sólo fuera de los identificadores."""
    salida, ultimo = [], 0
    for m in _IDENTIFICADOR.finditer(texto):
        salida.append(transformar(texto[ultimo:m.start()]))
        salida.append(m.group(0))
        ultimo = m.end()
    salida.append(transformar(texto[ultimo:]))
    return "".join(salida)


def normalizar_numeros(texto, evidencia=None, valores=None) -> str:
    """Reescribe en es-AR los números de un texto libre, sin tocar identificadores."""
    if texto is None:
        return ""
    valores = list(valores or []) + (_numeros_de(evidencia) if evidencia is not None else [])
    return proteger(str(texto), lambda s: _numeros_segmento(s, valores))


def valores_de_hallazgos(hallazgos) -> list[float]:
    """Valores exactos de la evidencia: con ellos «2.11356e+10» se reescribe con todos sus dígitos."""
    out = []
    for h in hallazgos or []:
        ev = h.get("evidencia") if isinstance(h, dict) else getattr(h, "evidencia", None)
        out.extend(_numeros_de(ev))
    return out


_DECIMAL_COMA_LARGO = re.compile(r"(?<![\w.,])(-?\d{1,3}(?:\.\d{3})*|-?\d+),(\d{3,})(?![\w]|[.,]\d)")


def _decimal_coma_largo(m):
    entero, decimales = m.group(1), m.group(2)
    if len(decimales) == 3 and "." not in entero and entero.lstrip("-") != "0":
        return m.group(0)  # «10,425» puede ser diez mil cuatrocientos veinticinco en otra convención
    return _numero_de_texto(float(entero.replace(".", "") + "." + decimales), len(decimales))


def unidades_legibles(texto: str) -> str:
    return _UNIDAD_PESOS.sub(lambda m: unidad_legible(m.group(0)), str(texto))


def normalizar_documento(markdown: str, valores=None) -> str:
    """Normaliza números de un documento completo, línea por línea (sin tocar bloques de código)."""
    valores = list(valores or [])
    lineas = []
    en_codigo = False
    for linea in str(markdown).split("\n"):
        if linea.strip().startswith("```"):
            en_codigo = not en_codigo
            lineas.append(linea)
            continue
        if en_codigo or linea.startswith("<!--"):
            lineas.append(linea)
            continue
        linea = normalizar_numeros(linea, valores=valores)
        linea = proteger(linea, lambda seg: _DECIMAL_COMA_LARGO.sub(_decimal_coma_largo, seg))
        lineas.append(unidades_legibles(linea))
    return "\n".join(lineas)
