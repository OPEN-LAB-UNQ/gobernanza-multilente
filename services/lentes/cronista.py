"""Cronista: lectura temporal de series.

Mira cortes, saltos y cambios de régimen dentro de una serie. No acusa ni
concluye causa: identifica meses o períodos bisagra que piden contexto.
"""
from __future__ import annotations

import re
from datetime import date
from statistics import median
from typing import Any

from services import perfilado, plural

from .util import columna_etiqueta_fila, columnas_numericas, valor_numero

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
MESES_CORTOS = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}
MES_COL_RE = re.compile(r"^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+(\d{4}))?$", re.I)
CONTEXTO_ESTACIONAL_RE = re.compile(
 r"mensual|interanual|variaci[oó]n|producci[oó]n|productividad|tambo|lech|campaña|campania|estacional",
 re.I,
)
# Remuneraciones: en Argentina el aguinaldo (SAC) se liquida en junio y diciembre.
SALARIAL_RE = re.compile(r"sueldo|salari|remuneraci|cargas? social|aguinaldo|\bsac\b|haberes|n[oó]mina|personal", re.I)
CONTEXTO_AGUINALDO = (
    "En remuneraciones, junio y diciembre incluyen el aguinaldo (SAC): confirmar si el salto lo explica "
    "antes de leerlo como cambio de régimen."
)
MAX_HALLAZGOS = 3
# Proporción de los períodos en que conviven dos o más valores de una columna para que sea clave del formato largo.
CRUCE_CLAVE = 0.5
CONTEXTO_ANUAL = (
    "La variación por sí sola no confirma un error ni un cambio de régimen. "
    "Verificar unidad, base de comparación, cobertura y cambios metodológicos. "
    "Si son importes en moneda corriente, distinguir crecimiento nominal y real antes de priorizar."
)


def _periodo_columna(col: str) -> tuple[int, int] | None:
    if re.fullmatch(r"(?:19|20)\d{2}", str(col).strip()):
        return (int(col), 1)
    m = MES_COL_RE.match(str(col).strip())
    if not m:
        # Año con marca de provisorio o estimado («2023 (p)», «2024*»): la marca es un metadato.
        from services.controles_excel.periodos import leer
        p = leer(str(col))
        if p and p["frecuencia"] == "anual" and (p.get("marca") or p.get("unidad")):
            return (p["anio"], 1)
        if p and p["frecuencia"] == "bimestral" and p.get("anio"):
            # «Ene-feb 24»: el bimestre se ubica en su primer mes; la cadencia queda en 2 meses.
            return (p["anio"], 2 * p["sub"] - 1)
        return None
    return (int(m.group(2) or 0), MESES[m.group(1).lower()])


# Prefijo que R agrega a los nombres de columna que empiezan con un número («X2017» por «2017»).
PREFIJO_R_RE = re.compile(r"^X(?=\d)", re.I)


def _series_formato_ancho(datos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not datos:
        return []
    columnas = list(datos[0].keys())
    meses: list[tuple[str, tuple[int, int]]] = []
    for c in columnas:
        periodo = _periodo_columna(c)
        if periodo is not None:
            meses.append((c, periodo))
    if len(meses) < 5:
        # Columnas exportadas desde R: «X2017», «X2018»… son los años 2017, 2018…
        con_x = [(c, _periodo_columna(PREFIJO_R_RE.sub("", str(c).strip())))
                 for c in columnas if PREFIJO_R_RE.match(str(c).strip())]
        con_x = [(c, p) for c, p in con_x if p is not None]
        if len(con_x) >= 5:
            meses = con_x
    if len(meses) < 5:
        return []
    meses.sort(key=lambda x: x[1])
    # JSONB no conserva el orden de claves. La etiqueta se identifica por su
    # significado y contenido, nunca por su posición frente a los años.
    periodos = {c for c, _ in meses}
    dimensiones = [{c: v for c, v in fila.items() if c not in periodos} for fila in datos]
    label_col = columna_etiqueta_fila(dimensiones)
    arrastre = _fila_de_arrastre(datos, label_col)
    out = []
    for idx, fila in enumerate(datos):
        valores = []
        for col, periodo in meses:
            v = valor_numero(fila.get(col))
            if v is not None:
                valores.append((col, periodo, v))
        if len(valores) >= 5:
            etiqueta = str(fila.get(label_col) or f"fila {idx + 1}").strip()
            if idx == arrastre or VIENE_RE.match(perfilado.normalizar_texto(etiqueta)):
                # Sumas de página («Transporte» al pie, «Viene de la página anterior» arriba): su
                # evolución es la del cuadro parcial, no la de un rubro.
                continue
            out.append({"etiqueta": etiqueta, "valores": valores, "orientacion": "fila", "fila_origen": idx})
    return out


VIENE_RE = re.compile(r"^vienen?\s+de\b")


def _fila_de_arrastre(datos: list[dict[str, Any]], label_col: str | None) -> int | None:
    """Índice de la última fila si es un total de arrastre de página («Transporte», «Van») con evidencia
    (suma de las filas de arriba o una fila «Viene de…»); el mismo criterio que los cierres."""
    from services.controles_excel.conciliacion import arrastre_en_filas

    return arrastre_en_filas(datos, label_col)


MEDIDA_RE = re.compile(r"%|porcentaje|tasa|promedio|[ií]ndice|ratio|rotaci[oó]n|variaci[oó]n", re.I)


def _es_medida(col: str, datos: list[dict[str, Any]]) -> bool:
    """Una tasa o un valor con decimales no agrupa filas: es una medida, no una categoría."""
    if MEDIDA_RE.search(str(col)):
        return True
    for fila in datos:
        v = valor_numero(fila.get(col))
        if v is not None and not float(v).is_integer():
            return True
    return False


def _dimension_formato_largo(datos: list[dict[str, Any]], tcol: str, nums: list[str]) -> str | None:
    columnas_numericas_set = set(nums)
    candidatos = []
    total = max(len(datos), 1)
    for col in datos[0].keys():
        if col == tcol or col in columnas_numericas_set:
            continue
        valores = [str(fila.get(col) or "").strip() for fila in datos]
        no_vacios = [v for v in valores if v]
        unicos = set(no_vacios)
        if len(no_vacios) / total < 0.7:
            continue
        if _es_medida(col, datos):
            continue
        if 2 <= len(unicos) <= min(500, max(3, total // 2)):
            candidatos.append((len(unicos), col))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: item[0])
    return candidatos[0][1]


def _series_formato_largo(datos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    perfiles = perfilado.perfilar(datos)
    temporales = perfilado.columnas_temporales(perfiles)
    nums = columnas_numericas(datos)
    if not temporales or not nums:
        return []
    def parseables(col: str) -> int:
        return sum(1 for fila in datos if perfilado.fecha(fila.get(col)) is not None)

    tcol = max(temporales, key=parseables)
    if parseables(tcol) < 5:
        return []

    dim_col = _dimension_formato_largo(datos, tcol, nums)
    out = []
    for col in nums:
        if dim_col:
            grupos: dict[str, list[tuple[str, tuple[int, int], float, int]]] = {}
            for idx, fila in enumerate(datos):
                f = perfilado.fecha(fila.get(tcol))
                v = valor_numero(fila.get(col))
                dimension = str(fila.get(dim_col) or "").strip()
                if f is not None and v is not None and dimension:
                    grupos.setdefault(dimension, []).append((str(fila.get(tcol)), (f.year, f.month), v, idx))
            for dimension, valores in grupos.items():
                valores.sort(key=lambda x: x[1])
                indices = [x[3] for x in valores]
                valores = [x[:3] for x in valores]
                periodos = {p for _, p, _ in valores}
                if len(valores) >= 5 and len(periodos) == len(valores):
                    out.append({
                        "etiqueta": f"{col} · {dimension}",
                        "valores": valores,
                        "indices": indices,
                        "columna": col,
                        "orientacion": "formato_largo_dimension",
                        "dimension_col": dim_col,
                        "dimension_valor": dimension,
                    })
            continue

        valores = []
        for idx, fila in enumerate(datos):
            f = perfilado.fecha(fila.get(tcol))
            v = valor_numero(fila.get(col))
            if f is not None and v is not None:
                valores.append((str(fila.get(tcol)), (f.year, f.month), v, idx))
        valores.sort(key=lambda x: x[1])
        indices = [x[3] for x in valores]
        valores = [x[:3] for x in valores]
        periodos = {p for _, p, _ in valores}
        if len(valores) >= 5 and len(periodos) == len(valores):
            out.append({"etiqueta": col, "valores": valores, "orientacion": "columna", "indices": indices, "columna": col})
    return out


def _distancia_meses(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (b[0] - a[0]) * 12 + (b[1] - a[1])

def _requiere_contexto_estacional(serie: dict[str, Any], cadencia: int) -> bool:
    if cadencia != 1:
        return False
    etiqueta = str(serie.get("etiqueta") or "")
    valores = serie.get("valores") or []
    periodos = [p for _, p, _ in valores if isinstance(p, tuple) and len(p) == 2]
    meses = [p[1] for p in periodos]
    anios = {p[0] for p in periodos if p[0]}
    meses_repetidos = len(anios) >= 2 and len(meses) != len(set(meses))
    return bool(meses_repetidos or CONTEXTO_ESTACIONAL_RE.search(etiqueta) or SALARIAL_RE.search(etiqueta))


def _salto_de_aguinaldo(serie: dict[str, Any], periodo_previo: Any, periodo_actual: Any) -> bool:
    if not SALARIAL_RE.search(str(serie.get("etiqueta") or "")):
        return False
    meses = {p[1] for p in (periodo_previo, periodo_actual) if isinstance(p, tuple) and len(p) == 2}
    return bool(meses & {6, 12})

def _fmt_periodo_label(valor: Any) -> str:
    raw = str(valor or "").strip()
    if re.fullmatch(r"X(?:19|20)\d{2}", raw, re.I):
        return raw[1:]  # «X2020» (columna exportada desde R) es el año 2020
    if "trim" in perfilado.normalizar_texto(raw):
        return raw
    fecha = perfilado.fecha(raw)
    if fecha is not None and fecha.day == 1:
        return f"{MESES_CORTOS.get(fecha.month, fecha.month)} {fecha.year}"
    return raw or "-"


def _partes_indice_apertura(serie: str) -> tuple[str, str] | None:
    m = re.match(r"^indice_(ipim|ipib|ipp)\s*·\s*(.+)$", str(serie), re.I)
    if not m:
        return None
    return (m.group(1).upper(), m.group(2))


def _label_apertura(apertura: str) -> str:
    texto = str(apertura).replace("_", " ").strip()
    texto = re.sub(r"\bn\.c\.e\.p\.?\b", "n.c.e.p.", texto, flags=re.I)
    return texto

def _fmt_num(valor: float) -> str:
    # Formato es-AR (punto de miles, coma decimal): «1.014», no «1,014».
    from services.reportes.formato import numero

    if abs(valor) >= 1000 or float(valor).is_integer():
        return numero(round(valor), 0)
    return numero(valor)


def _normalizar_anio(valor: Any) -> int | None:
    numero = valor_numero(valor)
    if numero is None:
        return None
    anio = int(numero)
    return anio if 1900 <= anio <= 2100 else None


def _normalizar_mes(valor: Any) -> int | None:
    numero = valor_numero(valor)
    if numero is not None:
        mes = int(numero)
        return mes if 1 <= mes <= 12 else None
    texto = str(valor or "").strip().lower()
    return MESES.get(texto)


def _series_formato_anio_mes(datos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not datos:
        return []
    columnas = list(datos[0].keys())
    anio_col = next((c for c in columnas if str(c).strip().lower() in {"anio", "año", "ano", "year"}), None)
    mes_col = next((c for c in columnas if str(c).strip().lower() in {"mes", "month"}), None)
    if not anio_col or not mes_col:
        return []

    periodos = []
    anio, mes_previo = None, None
    for fila in datos:
        escrito = fila.get(anio_col)
        mes = _normalizar_mes(fila.get(mes_col))
        if escrito is not None and str(escrito).strip():
            anio = _normalizar_anio(escrito)
        elif mes is None or (mes_previo is not None and mes < mes_previo):
            # No inventar un año nuevo cuando falta su rótulo al reiniciar los meses.
            anio = None
        periodos.append((anio, mes))
        mes_previo = mes
    nums = [c for c in columnas_numericas(datos) if c not in {anio_col, mes_col}]
    out = []
    for col in nums:
        valores = []
        for idx, (fila, (anio, mes)) in enumerate(zip(datos, periodos)):
            v = valor_numero(fila.get(col))
            if anio is not None and mes is not None and v is not None:
                valores.append((f"{anio}-{mes:02d}", (anio, mes), v, idx))
        valores.sort(key=lambda x: x[1])
        if len(valores) >= 5:
            out.append({"etiqueta": col, "valores": [v[:3] for v in valores], "orientacion": "anio_mes",
                        "indices": [v[3] for v in valores], "columna": col})
    return out


def _analizar_serie(serie: dict[str, Any]) -> dict | None:
    valores = serie["valores"]
    distancias = [
        _distancia_meses(valores[i - 1][1], valores[i][1])
        for i in range(1, len(valores))
        if _distancia_meses(valores[i - 1][1], valores[i][1]) > 0
    ]
    if len(distancias) < 4:
        return None
    cadencia = max(1, int(round(median(distancias))))
    cambios = []
    for i in range(1, len(valores)):
        periodo_previo = valores[i - 1][1]
        periodo_actual = valores[i][1]
        if _distancia_meses(periodo_previo, periodo_actual) != cadencia:
            continue
        prev = valores[i - 1][2]
        actual = valores[i][2]
        delta = actual - prev
        cambios.append((i, delta, prev, actual))
    if len(cambios) < 4:
        return None
    magnitudes = [abs(x[1]) for x in cambios[:-1]] or [abs(x[1]) for x in cambios]
    base = median(magnitudes) or 0
    if base <= 0:
        # Serie plana: la mediana de cambios es cero. Se usa como movimiento típico el
        # 1 % del nivel mediano, para que un ×10 en una serie constante no quede mudo.
        nivel = median([abs(v[2]) for v in valores])
        base = 0.01 * nivel
    if base <= 0:
        return None
    candidatos = sorted(cambios, key=lambda x: abs(x[1]), reverse=True)
    i, delta, prev, actual = candidatos[0]
    ratio = abs(delta) / base
    if ratio < 3.0:
        return None
    periodo_raw = valores[i][0]
    previo_raw = valores[i - 1][0]
    periodo = _fmt_periodo_label(periodo_raw)
    previo = _fmt_periodo_label(previo_raw)
    direccion = "sube" if delta > 0 else "baja"
    requiere_contexto = _requiere_contexto_estacional(serie, cadencia)
    anual = cadencia == 12
    lectura = "presenta una variación anual que requiere contexto" if anual else "presenta un salto temporal" if requiere_contexto else "cambia de régimen"
    cierre = (
        "Antes de leerlo como cambio de régimen, conviene validar estacionalidad, efecto de base de comparación, metodología de carga y conocimiento sectorial."
        if requiere_contexto
        else "Conviene revisar si hubo evento extraordinario, cambio de criterio, arrastre o recorte de período."
    )
    if anual:
        cierre = CONTEXTO_ANUAL
    elif _salto_de_aguinaldo(serie, valores[i - 1][1], valores[i][1]):
        cierre = CONTEXTO_AGUINALDO
    return {
        "modo": "corte_temporal",
        "descripcion": (
            f"La serie '{serie['etiqueta']}' {lectura} entre {previo} y {periodo}: "
            f"{direccion} de {_fmt_num(prev)} a {_fmt_num(actual)}. El salto es {ratio:.1f} veces mayor que el movimiento típico de la serie. "
            f"{cierre}"
        ),
        "severidad": "media" if requiere_contexto or anual else ("alta" if ratio >= 6 else "media"),
        "evidencia": {
            "regla": "corte_temporal",
            "serie": serie["etiqueta"],
            "filas": [serie["fila_origen"]] if "fila_origen" in serie else (
                [serie["indices"][i]] if serie.get("indices") else []),
            "columnas": [previo_raw, periodo_raw] if "fila_origen" in serie else (
                [serie["columna"]] if serie.get("columna") else []),
            **_forma_del_salto(valores, i, cadencia),
            "periodo_previo": previo,
            "periodo": periodo,
            "periodo_previo_raw": previo_raw,
            "periodo_raw": periodo_raw,
            "valor_previo": round(prev, 2),
            "valor_actual": round(actual, 2),
            "delta": round(delta, 2),
            "ratio_vs_movimiento_tipico": round(ratio, 2),
            "movimiento_tipico": base,
            "metodo_movimiento_tipico": "mediana de cambios absolutos, excluida la última transición",
            "cambios_referencia": magnitudes,
            "umbral_ratio": 3.0,
            "orientacion": serie["orientacion"],
            "cadencia_meses": cadencia,
            "requiere_contexto_anual": anual,
            "criterio_priorizacion_temporal": "Mayor salto absoluto relativo a la mediana histórica de cambios; es una orientación, no confirma errores.",
                "requiere_contexto_estacional": requiere_contexto,
                "validaciones_sugeridas": [
                    "estacionalidad",
                    "efecto_base_comparacion",
                    "metodologia_o_controles_del_archivo",
                    "conocimiento_sectorial",
                ] if requiere_contexto else [],
        },
    }


def _forma_del_salto(valores: list, i: int, cadencia: int) -> dict:
    """Si el salto revierte, si es un factor de unidad y si se repite el mismo mes del año anterior."""
    import math
    prev, actual = valores[i - 1][2], valores[i][2]
    salida = {"revierte": False, "factor_unidad": False, "estacional": False}
    siguiente = valores[i + 1][2] if i + 1 < len(valores) else None
    if prev and actual and siguiente is not None and prev * actual > 0 and siguiente * prev > 0:
        salto = abs(math.log(abs(actual / prev)))
        vuelta = abs(math.log(abs(siguiente / prev)))
        salida["revierte"] = salto > 0 and vuelta < salto / 3
    if prev and actual and prev * actual > 0:
        exponente = abs(math.log10(abs(actual / prev)))
        salida["factor_unidad"] = any(abs(exponente - k) < 0.15 for k in (3, 6))
    if cadencia == 1 and prev and actual:
        por_periodo = {p: v for _, p, v in valores}
        a, b = valores[i - 1][1], valores[i][1]
        pa, pb = por_periodo.get((a[0] - 1, a[1])), por_periodo.get((b[0] - 1, b[1]))
        if pa and pb and pa * pb > 0 and prev * actual > 0:
            ahora = math.log(abs(actual / prev))
            antes = math.log(abs(pb / pa))
            salida["estacional"] = ahora * antes > 0 and abs(antes) >= 0.5 * abs(ahora)
    return salida


def _clasificar(hallazgos: list[dict], notas: list[dict] | None) -> None:
    """Un cambio de nivel sostenido, estacional o documentado es contexto; un salto que revierte
    o un factor de unidad sigue siendo control. Las series anuales conservan su tratamiento."""
    for h in hallazgos:
        ev = h["evidencia"]
        if ev.get("requiere_contexto_anual"):
            continue
        serie = perfilado.normalizar_texto(str(ev.get("serie") or "")).replace("_", " ")
        nota = next((n for n in notas or [] if len(serie) >= 5 and serie in perfilado.normalizar_texto(n.get("texto", "")).replace("_", " ")), None)
        if nota:
            ev["contexto_declarado"] = {"celda": nota.get("celda"), "hoja": nota.get("hoja"), "texto": nota.get("texto", "")[:400]}
        motivo = None
        if nota:
            motivo = "documentado en una nota del archivo"
        elif ev.get("estacional"):
            motivo = "el mismo movimiento ocurre en el mismo mes del año anterior (estacionalidad)"
        elif not ev.get("revierte") and not ev.get("factor_unidad"):
            motivo = "cambio de nivel sostenido, no un valor aislado que revierte"
        if motivo:
            ev["naturaleza"] = "contexto"
            ev["motivo_contexto"] = motivo
            h["descripcion"] += f" Se informa como contexto: {motivo}."
        elif ev.get("factor_unidad"):
            h["severidad"] = "alta"
            h["descripcion"] += " El cambio es cercano a un factor de mil: posible cambio de unidad en la carga."


def _agrupar_cortes_simultaneos(hallazgos: list[dict]) -> list[dict]:
    grupos: dict[tuple[str, str], list[dict]] = {}
    for h in hallazgos:
        ev = h.get("evidencia") or {}
        key = (str(ev.get("periodo_previo")), str(ev.get("periodo")))
        grupos.setdefault(key, []).append(h)

    salida: list[dict] = []
    usados: set[int] = set()
    for (previo, periodo), items in grupos.items():
        if len(items) < 2:
            continue
        items = sorted(items, key=lambda h: abs((h.get("evidencia") or {}).get("ratio_vs_movimiento_tipico") or 0), reverse=True)
        grupos_series: dict[str, list[dict]] = {}
        for h in items:
            ev = h.get("evidencia") or {}
            serie = str(ev.get("serie"))
            partes_serie = _partes_indice_apertura(serie)
            serie_key = partes_serie[1] if partes_serie else serie
            grupos_series.setdefault(serie_key, []).append(h)
            usados.add(id(h))

        grupos_ordenados = sorted(
            grupos_series.items(),
            key=lambda kv: max(abs((h.get("evidencia") or {}).get("ratio_vs_movimiento_tipico") or 0) for h in kv[1]),
            reverse=True,
        )
        series = []
        fragmentos = []
        max_ratio = 0.0
        for apertura, grupo in grupos_ordenados[:6]:
            grupo = sorted(grupo, key=lambda h: abs((h.get("evidencia") or {}).get("ratio_vs_movimiento_tipico") or 0), reverse=True)
            ref = grupo[0]
            ev = ref.get("evidencia") or {}
            serie_ref = str(ev.get("serie"))
            partes_indices = [_partes_indice_apertura(str((h.get("evidencia") or {}).get("serie"))) for h in grupo]
            partes_validas = [p for p in partes_indices if p]
            if len(partes_validas) >= 2 and len({p[1] for p in partes_validas}) == 1:
                indices = "/".join(sorted({p[0] for p in partes_validas}))
                etiqueta = f"{_label_apertura(apertura)} ({indices})"
            else:
                etiqueta = serie_ref
            delta = float(ev.get("delta") or 0)
            direccion = "sube" if delta > 0 else "baja"
            ratio = abs(float(ev.get("ratio_vs_movimiento_tipico") or 0))
            max_ratio = max(max_ratio, ratio)
            series.append(etiqueta)
            fragmentos.append(
                f"{etiqueta} {direccion} de {_fmt_num(float(ev.get('valor_previo') or 0))} a {_fmt_num(float(ev.get('valor_actual') or 0))}"
            )
        extra = "" if len(grupos_ordenados) <= 6 else f" y {plural.contar(len(items) - sum(len(g) for _, g in grupos_ordenados[:6]), 'serie')} más"
        requiere_contexto = any((h.get("evidencia") or {}).get("requiere_contexto_estacional") for h in items)
        cierre = (
            "Antes de leerlo como cambio de régimen, conviene validar estacionalidad, efecto de base de comparación, metodología de carga y conocimiento sectorial."
            if requiere_contexto
            else "Conviene revisar si hubo cambio de alcance, inicio de ciclo, carga tardía, migración de sistema o recorte de período."
        )
        anual = all((h.get("evidencia") or {}).get("requiere_contexto_anual") for h in items)
        if anual:
            cierre = CONTEXTO_ANUAL
        contextos = [(h.get("evidencia") or {}).get("motivo_contexto") for h in items]
        en_contexto = all(contextos)
        unidad = any((h.get("evidencia") or {}).get("factor_unidad") for h in items)
        salida.append({
            "modo": "corte_temporal_conjunto",
            "descripcion": (
                f"Varias series presentan un salto temporal simultáneo entre {previo} y {periodo}: "
                + "; ".join(fragmentos)
                + extra
                + f". El mayor salto es {max_ratio:.1f} veces mayor que el movimiento típico. "
                + cierre
            ),
            "severidad": "alta" if unidad and not en_contexto else (
                "media" if requiere_contexto or anual else ("alta" if max_ratio >= 6 else "media")),
            "evidencia": {
                "regla": "corte_temporal_conjunto",
                "serie": " / ".join(series[:6]),
                "series": series,
                "series_compactas": series,
                "periodo_previo": previo,
                "periodo": periodo,
                "ratio_maximo_vs_movimiento_tipico": round(max_ratio, 2),
                "periodo_raw": (items[0].get("evidencia") or {}).get("periodo_raw"),
                "cantidad_series": len(items),
                "requiere_contexto_anual": anual,
                "cadencia_meses": 12 if anual else None,
                "detalle_series": [h.get("evidencia", {}) for h in items],
                **({"naturaleza": "contexto", "motivo_contexto": contextos[0]} if en_contexto and not anual else {}),
                "factor_unidad": unidad,
                "requiere_contexto_estacional": requiere_contexto,
                "validaciones_sugeridas": [
                    "estacionalidad",
                    "efecto_base_comparacion",
                    "metodologia_o_controles_del_archivo",
                    "conocimiento_sectorial",
                ] if requiere_contexto else [],
            },
        })

    for h in hallazgos:
        if id(h) not in usados:
            salida.append(h)
    salida.sort(
        key=lambda h: abs((h.get("evidencia") or {}).get("ratio_maximo_vs_movimiento_tipico") or (h.get("evidencia") or {}).get("ratio_vs_movimiento_tipico") or 0),
        reverse=True,
    )
    return salida


def analizar(datos: list[dict[str, Any]], notas: list[dict] | None = None) -> list[dict]:
    series = _series_formato_largo(datos) or _series_formato_anio_mes(datos) or _series_formato_ancho(datos)
    hallazgos = [h for h in (_analizar_serie(s) for s in series) if h]
    hallazgos.sort(key=lambda h: abs(h["evidencia"]["ratio_vs_movimiento_tipico"]), reverse=True)
    _clasificar(hallazgos, notas)
    return _agrupar_cortes_simultaneos(hallazgos)[:MAX_HALLAZGOS]


def columna_tiempo(datos: list[dict[str, Any]]) -> str | None:
    """Columna de períodos elegida por contenido: la que más valores interpretables como fecha tiene.

    Un rótulo como «Acumulado del año» no la vuelve temporal si sus valores son importes.
    """
    if not datos:
        return None
    columnas = list(dict.fromkeys(c for fila in datos for c in fila))
    mejor, cuenta, distintas = None, 0, 0
    for c in columnas:
        fechas = [perfilado.fecha(fila.get(c)) for fila in datos if isinstance(fila.get(c), str)]
        fechas = [f for f in fechas if f is not None]
        # A igual cobertura gana la más fina: con «Year» y «Date» juntas, el período es la fecha.
        n, d = len(fechas), len(set(fechas))
        if n >= 3 and d < 2:
            # La misma fecha en todas las filas («fecha_actualizacion») es un metadato, no un eje.
            continue
        if (n, d) > (cuenta, distintas):
            mejor, cuenta, distintas = c, n, d
    return mejor if cuenta >= max(3, 0.6 * len(datos)) else None


def _claves_categoricas(datos: list[dict[str, Any]], tcol: str, periodos: int) -> list[str]:
    """Todas las columnas que clasifican filas en un formato largo: textos o códigos enteros («clae3»,
    «zona_prov», «letra») que se repiten en cada período. Una medida (con decimales, o con casi un valor
    distinto por fila) no es una clave. Tampoco una columna que describe al período en vez de clasificar
    filas («Estado: provisorio» en los últimos meses, «Fuente»): en una clave conviven dos o más valores
    en la mayoría de los períodos; si no, tomarla como clave ocultaría un período repetido de verdad."""
    total = len(datos)
    if not total or periodos < 2:
        return []
    maximo = max(2, 2 * total // periodos)
    claves = []
    for col in datos[0].keys():
        if col == tcol or _es_medida(col, datos):
            continue
        valores = [str(fila.get(col) or "").strip() for fila in datos]
        if sum(1 for v in valores if v) < 0.7 * total:
            continue
        if 2 <= len(set(valores)) <= maximo and _cruza_periodos(datos, tcol, col):
            claves.append(col)
    return claves


def _cruza_periodos(datos: list[dict[str, Any]], tcol: str, col: str) -> bool:
    """En la mayoría de los períodos conviven dos o más valores de la columna (provincias, ramas, sexos)."""
    por_periodo: dict[str, set] = {}
    for fila in datos:
        t = str(fila.get(tcol) or "").strip()
        if t:
            por_periodo.setdefault(t, set()).add(str(fila.get(col) or "").strip())
    if not por_periodo:
        return False
    return sum(1 for vs in por_periodo.values() if len(vs) >= 2) >= CRUCE_CLAVE * len(por_periodo)


def problemas_periodo(datos: list[dict[str, Any]]) -> list[dict]:
    """Períodos duplicados o fuera de secuencia en la columna de tiempo.

    En formato largo la secuencia se controla dentro de cada valor de la dimensión. Un período repetido
    sólo es un duplicado si se repite también la combinación completa de las columnas que clasifican
    las filas (provincia y rama, código de actividad): con una clave incompleta, «2007-01» aparece una
    vez por cada valor de la dimensión que falta. Devuelve el registro y el rótulo de cada período
    problemático; vacío si la secuencia es válida.
    """
    tcol = columna_tiempo(datos)
    if not tcol:
        return []
    nums = columnas_numericas(datos)
    dim = _dimension_formato_largo(datos, tcol, nums)
    if dim and not _cruza_periodos(datos, tcol, dim):
        dim = None  # «Estado», «Fuente»: describe el período, no separa series
    periodos = len({str(fila.get(tcol) or "").strip() for fila in datos} - {""})
    claves = _claves_categoricas(datos, tcol, periodos)
    fechas = [(i, fila, perfilado.fecha(fila.get(tcol))) for i, fila in enumerate(datos)]
    fechas = [(i, fila, f) for i, fila, f in fechas if f is not None]
    # Datos diarios: varios días del mismo mes no son el mismo período; se compara la fecha completa.
    diaria = len({(f.year, f.month, f.day) for _, _, f in fechas}) > len({(f.year, f.month) for _, _, f in fechas})

    def distancia(a, b):
        return (date(*b) - date(*a)).days if diaria else _distancia_meses(a, b)

    grupos: dict[str, list[tuple[int, tuple[int, ...]]]] = {}
    for i, fila, f in fechas:
        clave = str(fila.get(dim) or "").strip() if dim else ""
        grupos.setdefault(clave, []).append((i, (f.year, f.month, f.day) if diaria else (f.year, f.month)))
    salida = []

    def completa(i):
        return tuple(str(datos[i].get(k) or "").strip() for k in claves)

    for clave, items in grupos.items():
        vistos: dict[tuple[int, ...], int] = {}
        completos: set = set()
        previo = None
        pasos = [distancia(a[1], b[1]) for a, b in zip(items, items[1:])]
        descendente = bool(pasos) and all(p <= 0 for p in pasos) and any(p < 0 for p in pasos)
        for i, p in items:
            tipo = None
            repetido_completo = (p, completa(i)) in completos
            completos.add((p, completa(i)))
            if p in vistos and (repetido_completo or not claves):
                tipo = "periodo_duplicado"
            elif p in vistos:
                vistos.setdefault(p, i)
                continue  # el mismo período con otra combinación de la clave completa: no es un duplicado
            elif previo is not None and (distancia(previo, p) < 0) != descendente and distancia(previo, p) != 0:
                tipo = "periodo_fuera_de_secuencia"
            if tipo:
                salida.append({"fila": i, "columna": tcol, "valor": str(datos[i].get(tcol)), "tipo": tipo,
                               "primera_aparicion": vistos.get(p), "dimension": clave or None})
            vistos.setdefault(p, i)
            previo = p
    return salida


def alertas_periodo(datos: list[dict[str, Any]], problemas: list[dict] | None = None) -> list[dict]:
    """Alerta propia (prioridad alta, con la celda) por cada período duplicado o fuera de secuencia."""
    problemas = problemas_periodo(datos) if problemas is None else problemas
    out = []
    for p in problemas:
        que = "repite un período ya informado" if p["tipo"] == "periodo_duplicado" else "rompe el orden de la secuencia"
        out.append({
            "modo": "periodo_invalido",
            "descripcion": (
                f"El período '{p['valor']}' de la columna '{p['columna']}' {que}"
                + (f" (dimensión «{p['dimension']}»)" if p.get("dimension") else "")
                + ". Mientras no se corrija, la lectura temporal de este cuadro no es evaluable: las comparaciones "
                "entre períodos podrían mezclar meses o años distintos."
            ),
            "severidad": "alta",
            "evidencia": {
                "regla": p["tipo"],
                "naturaleza": "control",
                "filas": [p["fila"]],
                "columnas": [p["columna"]],
                "columna": p["columna"],
                "periodo": p["valor"],
                "registro_primera_aparicion": p.get("primera_aparicion"),
                "analisis_temporal": "no_evaluable",
            },
        })
    return out
