"""Controles matemáticos livianos para tablas extraidas de PDF.

Trabaja solo sobre filas agregadas ya extraidas por `carga_archivos`. No intenta
reconstruir microdatos ni atribuir responsabilidades: convierte inconsistencias
aritméticas comunicables en hallazgos para la lente Matematico.
"""
from __future__ import annotations

import io
import re
import subprocess
from typing import Any

from services import perfilado

MAX_HALLAZGOS = 8
TOLERANCIA_PCT = 0.2
TOLERANCIA_MONTO = 1.0

PDF_META_RE = re.compile(
    r"^(extraccion_pdf|pagina_pdf|pagina_pdf_impresa|tabla_pdf|fila_tabla_pdf|archivo_origen|"
    r"paginas_documento|paginas_pdf_analizadas|limite_paginas_pdf|"
    r"pdf_truncado_por_paginas|tipo_documento|pagina|caracteres_extraidos|"
    r"cantidad_numeros_detectados|muestra_numeros)$",
    re.I,
)
CONTROL_TEXTUAL_RE = re.compile(
    r"\b(?:no\s+(?:coincide|cierra)|"
    r"(?:error|inconsisten\w*)\s+(?:aritm[eé]tic\w*|de\s+c[aá]lculo|"
    r"en\s+(?:(?:el|la)\s+)?(?:total|suma|saldo|resultado))|"
    r"diferencia\w*\s+(?:sin explicar|no explicad\w*|injustificad\w*))\b",
    re.I,
)
TEMPORAL_RE = re.compile(r"\b(?:[12]\s*s|[12]s|[1-4]\s*t|trim|(?:19|20)\d{2})\b", re.I)
MESES_RE = re.compile(
    r"^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)$",
    re.I,
)
NARRATIVA_MENSUAL_RE = re.compile(
    r"\ben\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+((?:19|20)\d{2}).{0,600}?\bse\s+ubica\s+en\s+([0-9][\d.,]*)\s*%?"
    r".{0,400}?\bmismo\s+mes\s+de\s+((?:19|20)\d{2}).{0,180}?\bfue\s+de\s+([0-9][\d.,]*)\s*%",
    re.I | re.S,
)
MAX_PAGINAS_OCR = 4


def _es_pdf(datos: list[dict[str, Any]]) -> bool:
    return any(
        str(fila.get("extraccion_pdf") or "").lower() in {"tabla", "texto_por_pagina"}
        or str(fila.get("archivo_origen") or "").lower().endswith(".pdf")
        for fila in datos
    )


def _numero_pdf(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    text = str(valor).strip()
    if not text:
        return None
    text = re.sub(r"\s+", "", text)
    text = text.replace("$", "").replace("%", "")
    text = re.sub(r"(?i)\b(miles?|millones?|p\.?p\.?|pp)\b", "", text)
    text = re.sub(r"[^\d,\.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    # Formato inequívoco por sí mismo: «2,078,000.0» o «1,234.5» (inglés) y «1.234,5» (castellano).
    # Una sola coma seguida de tres cifras («31,821») sigue leyéndose como decimal: el lector
    # decide esas columnas con la evidencia del cuadro y del documento, y las declara si no puede.
    evidencia = perfilado.evidencia_formato(text.lstrip("-")) if re.fullmatch(r"-?[\d.,]+", text) else None
    if evidencia == "en" and "," in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _norm(valor: Any) -> str:
    return perfilado.normalizar_texto(valor)


def _decimal_es(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _rotulo_fila(fila: dict[str, Any]) -> str:
    """El concepto del renglón. Si el cuadro no trae una columna con ese nombre, se usa la primera
    celda con texto: en estos cuadros la primera columna es la que dice de qué habla la fila."""
    for clave in ("Indicador", "Concepto", "concepto", "indicador"):
        if fila.get(clave):
            return str(fila[clave])
    for clave, valor in fila.items():
        if PDF_META_RE.match(str(clave)):
            continue
        texto = str(valor or "").strip()
        if texto and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3}", texto):
            return texto
    return ""


def _fila_detalle(fila: dict[str, Any], idx: int) -> str:
    # `idx` es la posicion de la fila en el dataset combinado de TODO el
    # informe (puede incluir varios archivos ademas del PDF), no una
    # posicion dentro de esa pagina o tabla -- usarlo como "fila N" confunde
    # a quien lee el hallazgo, porque no hay forma de ubicar esa fila
    # contando renglones en la pagina indicada. `fila_tabla_pdf` en cambio
    # es la posicion real dentro de la tabla de esa pagina (ver
    # carga_archivos._filas_tabla_pdf) y es lo que hay que mostrar cuando
    # esta disponible.
    etiqueta = _rotulo_fila(fila)
    fila_tabla = fila.get("fila_tabla_pdf")
    base = f"fila {fila_tabla}" if fila_tabla else "texto de la página"
    if etiqueta:
        base += f" ({str(etiqueta).strip()[:90]})"
    pagina = fila.get("pagina_pdf") or fila.get("pagina")
    tabla = fila.get("tabla_pdf")
    if pagina:
        base += f", página {pagina} del archivo PDF"
    if fila.get("pagina_pdf_impresa"):
        base += f" (numeración impresa: {fila['pagina_pdf_impresa']})"
    if tabla:
        base += f", tabla {tabla}"
    return base


def _hallazgo(
    descripcion: str,
    fila: dict[str, Any],
    idx: int,
    columnas: list[str],
    evidencia_extra: dict[str, Any] | None = None,
    severidad: str = "alta",
) -> dict:
    evidencia = {
        "fila_detalle": _fila_detalle(fila, idx),
        "columnas": columnas,
        "pagina_pdf": fila.get("pagina_pdf") or fila.get("pagina"),
        "pagina_pdf_impresa": fila.get("pagina_pdf_impresa"),
        "tabla_pdf": fila.get("tabla_pdf"),
        "archivo_origen": fila.get("archivo_origen"),
    }
    if evidencia_extra:
        evidencia.update(evidencia_extra)
    return {
        "modo": "consistencia_aritmetica_pdf",
        "descripcion": descripcion,
        "severidad": severidad,
        "evidencia": evidencia,
    }


def _valor_por_indicador(datos: list[dict[str, Any]], patron: str, columna: str = "Valor alterado") -> tuple[int, dict[str, Any], float] | None:
    regex = re.compile(patron, re.I)
    for idx, fila in enumerate(datos):
        indicador = fila.get("Indicador") or fila.get("indicador") or ""
        if regex.search(_norm(indicador)):
            valor = _numero_pdf(fila.get(columna))
            if valor is not None:
                return idx, fila, valor
    return None


def _hallazgos_composicion(datos: list[dict[str, Any]]) -> list[dict]:
    hallazgos: list[dict] = []
    total = _valor_por_indicador(datos, r"^pobreza en personas")
    indig = _valor_por_indicador(datos, r"^indigencia en personas")
    no_indig = _valor_por_indicador(datos, r"pobres no indigentes")
    no_pobres = _valor_por_indicador(datos, r"^no pobres")

    if total and indig and no_indig:
        idx, fila, total_val = total
        esperado = indig[2] + no_indig[2]
        if abs(esperado - total_val) > TOLERANCIA_PCT:
            hallazgos.append(_hallazgo(
                (
                    "La composición de pobreza no cierra: indigencia en personas "
                    f"({indig[2]:.1f}) + pobres no indigentes ({no_indig[2]:.1f}) = "
                    f"{esperado:.1f}, pero pobreza en personas declara {total_val:.1f}."
                ),
                fila,
                idx,
                ["Pobreza en personas (%)", "Indigencia en personas (%)", "Pobres no indigentes (%)"],
                {
                    "regla": "componentes_no_cierran_total",
                    "valor_calculado": round(esperado, 3),
                    "valor_declarado": total_val,
                    "diferencia": round(esperado - total_val, 3),
                },
            ))

    if total and no_pobres:
        idx, fila, total_val = total
        esperado = total_val + no_pobres[2]
        if abs(esperado - 100.0) > TOLERANCIA_PCT:
            hallazgos.append(_hallazgo(
                (
                    "El complemento poblacional no cierra: pobreza en personas "
                    f"({total_val:.1f}) + no pobres ({no_pobres[2]:.1f}) = {esperado:.1f}, "
                    "pero debería aproximar 100."
                ),
                fila,
                idx,
                ["Pobreza en personas (%)", "No pobres (%)"],
                {
                    "regla": "complemento_porcentual_no_cierra",
                    "valor_calculado": round(esperado, 3),
                    "valor_esperado": 100.0,
                    "diferencia": round(esperado - 100.0, 3),
                },
            ))
    return hallazgos


def _hallazgos_variacion(datos: list[dict[str, Any]]) -> list[dict]:
    hallazgos: list[dict] = []
    for idx, fila in enumerate(datos):
        decl_col = next((c for c in fila if "variacion declarada" in _norm(c)), None)
        if not decl_col:
            continue
        declarado = str(fila.get(decl_col) or "")
        temporales: list[tuple[str, float]] = []
        for col, valor in fila.items():
            if PDF_META_RE.search(str(col)) or col == decl_col:
                continue
            if not TEMPORAL_RE.search(str(col)):
                continue
            num = _numero_pdf(valor)
            if num is not None:
                temporales.append((str(col), num))
        if len(temporales) < 2:
            continue
        previo_col, previo = temporales[-2]
        actual_col, actual = temporales[-1]
        delta = actual - previo
        texto = _norm(declarado)
        contradice = ("aumento" in texto and delta < -TOLERANCIA_PCT) or (
            re.search(r"descenso|disminu|baja", texto) and delta > TOLERANCIA_PCT
        )
        if contradice:
            hallazgos.append(_hallazgo(
                (
                    f"La variación declarada contradice la serie: {previo_col}={previo:.1f} "
                    f"y {actual_col}={actual:.1f}, por lo que el cambio es {delta:.1f}; "
                    f"el texto declara '{declarado}'."
                ),
                fila,
                idx,
                [previo_col, actual_col, decl_col],
                {
                    "regla": "variacion_declarada_con_signo_inconsistente",
                    "valor_previo": previo,
                    "valor_actual": actual,
                    "diferencia": round(delta, 3),
                    "texto_declarado": declarado,
                },
            ))
    return hallazgos


def _hallazgos_porcentaje_de_base(datos: list[dict[str, Any]]) -> list[dict]:
    hallazgos: list[dict] = []
    patron = re.compile(r"([0-9][\d\.,]*)\s*%\s*de\s*([0-9][\d\.,]*)", re.I)
    for idx, fila in enumerate(datos):
        control = " ".join(
            str(valor or "")
            for col, valor in fila.items()
            if not PDF_META_RE.search(str(col))
        )
        match = patron.search(control)
        if not match:
            continue
        porcentaje = _numero_pdf(match.group(1))
        base_valor = _numero_pdf(match.group(2))
        declarado = _numero_pdf(
            fila.get("Valor alterado")
            or fila.get("valor alterado")
            or fila.get("Valor")
            or fila.get("valor")
        )
        if porcentaje is None or base_valor is None or declarado is None:
            continue
        esperado = base_valor * porcentaje / 100.0
        tolerancia = max(TOLERANCIA_MONTO, abs(esperado) * 0.01)
        if abs(esperado - declarado) <= tolerancia:
            continue
        hallazgos.append(_hallazgo(
            (
                f"El valor declarado no coincide con el porcentaje indicado en el control: "
                f"{porcentaje:.1f}% de {base_valor:.0f} = {esperado:.0f}, "
                f"pero se declara {declarado:.0f}."
            ),
            fila,
            idx,
            ["Valor alterado", "Control esperado"],
            {
                "regla": "porcentaje_de_base_no_cierra",
                "porcentaje": porcentaje,
                "base": base_valor,
                "valor_calculado": round(esperado, 3),
                "valor_declarado": declarado,
                "diferencia": round(declarado - esperado, 3),
            },
        ))
    return hallazgos


def _hallazgos_brecha(datos: list[dict[str, Any]]) -> list[dict]:
    hallazgos: list[dict] = []
    for idx, fila in enumerate(datos):
        canasta_col = next((c for c in fila if "canasta" in _norm(c)), None)
        ingreso_col = next((c for c in fila if "ingreso" in _norm(c)), None)
        brecha_col = next((c for c in fila if "brecha" in _norm(c)), None)
        if not (canasta_col and ingreso_col and brecha_col):
            continue
        canasta = _numero_pdf(fila.get(canasta_col))
        ingreso = _numero_pdf(fila.get(ingreso_col))
        brecha = _numero_pdf(fila.get(brecha_col))
        if canasta is None or ingreso is None or brecha is None:
            continue
        esperado = ingreso - canasta
        if abs(esperado - brecha) > TOLERANCIA_MONTO:
            hallazgos.append(_hallazgo(
                (
                    f"La brecha declarada no coincide con ingreso menos canasta: "
                    f"{ingreso:.0f} - {canasta:.0f} = {esperado:.0f}, "
                    f"pero se declara {brecha:.0f}."
                ),
                fila,
                idx,
                [ingreso_col, canasta_col, brecha_col],
                {
                    "regla": "brecha_b_menos_a_no_cierra",
                    "valor_calculado": round(esperado, 3),
                    "valor_declarado": brecha,
                    "diferencia": round(esperado - brecha, 3),
                },
            ))
    return hallazgos


def _hallazgos_textuales(datos: list[dict[str, Any]], filas_ocupadas: set[str]) -> list[dict]:
    hallazgos: list[dict] = []
    for idx, fila in enumerate(datos):
        if not _es_pdf([fila]):
            continue
        detalle = _fila_detalle(fila, idx)
        if detalle in filas_ocupadas:
            continue
        partes = []
        for col, valor in fila.items():
            if PDF_META_RE.search(str(col)):
                continue
            texto = str(valor or "").strip()
            if texto:
                partes.append(texto)
        texto_fila = " | ".join(partes)
        match = CONTROL_TEXTUAL_RE.search(texto_fila)
        if match:
            inicio = max(0, match.start() - 150)
            fin = min(len(texto_fila), match.end() + 250)
            fragmento = texto_fila[inicio:fin]
            hallazgos.append(_hallazgo(
                (
                    "El PDF contiene una mención textual que requiere revisión en contexto; "
                    "no constituye una inconsistencia aritmética comprobada."
                ),
                fila,
                idx,
                [],
                {
                    "regla": "control_textual_pdf",
                    "texto_control": fragmento,
                    "termino_detectado": match.group(0),
                },
                severidad="media",
            ))
            if len(hallazgos) >= 3:
                break
    return hallazgos


def _series_mensuales_pdf(datos: list[dict[str, Any]]) -> list[tuple[str, int, str, list[tuple[int, dict[str, Any], float]]]]:
    """Ubica tablas mensuales con dos años, candidatas a un cruce portada/detalle.

    El filtro se hace antes del OCR: así solo se renderizan las pocas páginas
    que contienen una serie mensual comparable y no cada página del documento.
    """
    grupos: dict[tuple[str, int, str], list[tuple[int, dict[str, Any], float]]] = {}
    for idx, fila in enumerate(datos):
        archivo = str(fila.get("archivo_origen") or "")
        pagina = int(fila.get("pagina_pdf") or 0)
        if not archivo.lower().endswith(".pdf") or pagina <= 0:
            continue
        periodo_col = next((c for c in fila if _norm(c) == "periodo"), None)
        porcentaje_col = next((c for c in fila if "porcentaje" in _norm(c)), None)
        if not periodo_col or not porcentaje_col:
            continue
        mes = _norm(fila.get(periodo_col))
        valor = _numero_pdf(fila.get(porcentaje_col))
        if not MESES_RE.match(mes) or valor is None:
            continue
        grupos.setdefault((archivo, pagina, mes), []).append((idx, fila, valor))
    return [(*clave, valores) for clave, valores in grupos.items() if len(valores) >= 2]


def _ocr_pagina_pdf(contenido: bytes, pagina: int) -> str:
    """Renderiza una página en memoria y obtiene su capa visual de texto.

    Es una ayuda conservadora: si el renderizador o Tesseract no están
    disponibles, el análisis tabular continúa sin fallar.
    """
    try:
        import pypdfium2 as pdfium

        documento = pdfium.PdfDocument(contenido)
        if pagina < 1 or pagina > len(documento):
            return ""
        imagen = documento[pagina - 1].render(scale=3).to_pil()
        buffer = io.BytesIO()
        imagen.save(buffer, format="PNG")
        resultado = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", "eng"],
            input=buffer.getvalue(),
            capture_output=True,
            check=False,
            timeout=25,
        )
        return resultado.stdout.decode("utf-8", errors="ignore") if resultado.returncode == 0 else ""
    except (ImportError, OSError, subprocess.SubprocessError, ValueError):
        return ""


def analizar_coherencia_visual(
    archivos: list[tuple[str, bytes]],
    datos: list[dict[str, Any]],
) -> list[dict]:
    """Contrasta un valor destacado visualmente con la tabla de la misma página.

    Algunos PDF alterados conservan el número correcto en la capa de texto pero
    muestran otro número en la capa gráfica. El extractor tabular no puede ver
    esa diferencia; este control OCR la comunica sin asumir que una fuente sea
    la verdadera.
    """
    contenidos = {nombre: contenido for nombre, contenido in archivos if nombre.lower().endswith(".pdf")}
    candidatos = _series_mensuales_pdf(datos)
    paginas_ocr: dict[tuple[str, int], str] = {}
    hallazgos: list[dict] = []

    for archivo, pagina, mes, valores in candidatos:
        clave_pagina = (archivo, pagina)
        if clave_pagina not in paginas_ocr:
            if len(paginas_ocr) >= MAX_PAGINAS_OCR:
                break
            contenido = contenidos.get(archivo)
            paginas_ocr[clave_pagina] = _ocr_pagina_pdf(contenido, pagina) if contenido else ""
        texto = paginas_ocr[clave_pagina]
        match = NARRATIVA_MENSUAL_RE.search(texto)
        if not match or _norm(match.group(1)) != mes:
            continue

        actual_visual = _numero_pdf(match.group(3))
        previo_visual = _numero_pdf(match.group(5))
        previo_tabla = valores[-2][2]
        actual_tabla = valores[-1][2]
        diferencias = []
        if actual_visual is not None and abs(actual_visual - actual_tabla) > TOLERANCIA_PCT:
            diferencias.append(
                f"{mes} de {match.group(2)} aparece como {_decimal_es(actual_visual)} % "
                f"en el texto destacado y {_decimal_es(actual_tabla)} % en la tabla"
            )
        if previo_visual is not None and abs(previo_visual - previo_tabla) > TOLERANCIA_PCT:
            diferencias.append(
                f"el mismo mes de {match.group(4)} aparece como {_decimal_es(previo_visual)} % "
                f"en el texto destacado y {_decimal_es(previo_tabla)} % en la tabla"
            )
        if not diferencias:
            continue

        idx, fila, _ = valores[-1]
        hallazgo = _hallazgo(
            "El texto destacado y la tabla del PDF no coinciden: " + "; ".join(diferencias) + ".",
            fila,
            idx,
            ["Período", "Porcentaje"],
            {
                "regla": "texto_destacado_no_coincide_con_tabla",
                "metodo": "OCR de la página y extracción tabular",
                "mes": mes,
                "anio_actual": int(match.group(2)),
                "valor_actual_texto": actual_visual,
                "valor_actual_tabla": actual_tabla,
                "anio_previo": int(match.group(4)),
                "valor_previo_texto": previo_visual,
                "valor_previo_tabla": previo_tabla,
            },
        )
        hallazgo.update({
            "modo": "coherencia_interna_pdf",
            "tipo_evidencia": "COHERENCIA_INTERNA",
            "pregunta_institucional": (
                f"Confirmar cuál es el valor correcto para {mes} de {match.group(2)} "
                f"({_decimal_es(actual_visual)} % en el texto destacado o "
                f"{_decimal_es(actual_tabla)} % en la tabla) "
                "e indicar la fuente que lo respalda."
            ),
        })
        hallazgo["evidencia"]["fila_detalle"] = (
            f"registro de {mes} de {match.group(2)}, página {pagina} del archivo PDF, "
            f"tabla {fila.get('tabla_pdf')}"
        )
        hallazgos.append(hallazgo)
        if len(hallazgos) >= MAX_HALLAZGOS:
            break
    return hallazgos


CORROBORACION_TOTAL_PDF = 0.8  # proporción de filas donde la igualdad tiene que cumplirse
MATERIAL_TOTAL_PDF = 0.002  # diferencia relativa que se considera material (0,2 %)


def _cuadros_pdf(datos: list[dict[str, Any]]) -> dict[tuple, list[dict[str, Any]]]:
    cuadros: dict[tuple, list[dict[str, Any]]] = {}
    for fila in datos:
        if not str(fila.get("extraccion_pdf") or "").startswith("tabla"):
            continue
        cuadros.setdefault((fila.get("archivo_origen"), fila.get("pagina_pdf"), fila.get("tabla_pdf")), []).append(fila)
    return cuadros


def _columnas_pdf(filas: list[dict[str, Any]]) -> list[str]:
    from services.carga_archivos import META_PDF

    return [str(k) for k in filas[0] if k not in META_PDF]


ANIO_PDF = re.compile(r"^(19|20)\d{2}$")
TOTAL_PDF = re.compile(r"total|consolidad", re.I)


def _columna_de_anio_pdf(filas: list[dict[str, Any]], columnas: list[str]) -> str | None:
    for columna in columnas:
        valores = [str(f.get(columna) or "").strip() for f in filas]
        if sum(1 for v in valores if ANIO_PDF.match(v)) >= max(2, 0.2 * len(filas)):
            return columna
    return None


def _bloques_pdf(filas, col_nivel, etiqueta_total, col_anio):
    """Agrupa las filas en bloques: cada bloque termina en su fila de total.

    El año de un bloque aparece una sola vez y en el PDF está en una celda combinada centrada, así
    que puede caer en cualquiera de las filas del bloque: se toma de donde esté, no se arrastra
    hacia abajo. Nada de esto modifica los datos del informe.
    """
    bloques: list[tuple[str, dict[str, dict]]] = []
    actual: dict[str, dict] = {}
    anio = ""
    for indice, fila in enumerate(filas):
        etiqueta = str(fila.get(col_nivel) or "").strip()
        if col_anio:
            valor = str(fila.get(col_anio) or "").strip()
            if ANIO_PDF.match(valor):
                anio = valor
        if etiqueta:
            actual[etiqueta] = {"fila": fila, "indice": indice}
        if etiqueta == etiqueta_total and actual:
            bloques.append((anio, actual))
            actual, anio = {}, ""
    if actual:
        bloques.append((anio, actual))
    return bloques


def _columna_de_nivel_pdf(filas: list[dict[str, Any]], columnas: list[str]) -> tuple[str, str, list[str]] | None:
    """Columna que reparte cada bloque en partes y un total: «Nación / Provincias / Total»."""
    for columna in columnas:
        valores = [str(f.get(columna) or "").strip() for f in filas]
        distintos = [v for v in dict.fromkeys(valores) if v]
        if not 3 <= len(distintos) <= 5:
            continue
        totales = [v for v in distintos if TOTAL_PDF.search(v)]
        partes = [v for v in distintos if v not in totales]
        if len(totales) == 1 and len(partes) >= 2:
            return columna, totales[0], partes
    return None


def _hallazgos_consolidado_pdf(datos: list[dict[str, Any]]) -> list[dict]:
    """Las partes de cada bloque tienen que sumar su total: Nación + Provincias = Total.

    Es la segunda igualdad que estos cuadros traen declarada, independiente de la suma por fila: se
    verifica rubro por rubro y año por año. Como en la planilla, no se afirma sin corroborar.
    """
    hallazgos: list[dict] = []
    for (_, pagina, tabla), filas in _cuadros_pdf(datos).items():
        columnas = _columnas_pdf(filas)
        nivel = _columna_de_nivel_pdf(filas, columnas)
        if not nivel:
            continue
        col_nivel, etiqueta_total, etiquetas_parte = nivel
        col_anio = _columna_de_anio_pdf(filas, [c for c in columnas if c != col_nivel])
        numericas = [
            c
            for c in columnas
            if c not in {col_nivel, col_anio}
            and not c.startswith("columna_")
            and sum(1 for f in filas if _numero_pdf(f.get(c)) is not None) >= 0.8 * len(filas)
        ]
        if not numericas:
            continue
        cierran, fallan = 0, []
        for anio, bloque in _bloques_pdf(filas, col_nivel, etiqueta_total, col_anio):
            if etiqueta_total not in bloque or not all(p in bloque for p in etiquetas_parte):
                continue
            for columna in numericas:
                declarado = _numero_pdf(bloque[etiqueta_total]["fila"].get(columna))
                partes = [_numero_pdf(bloque[p]["fila"].get(columna)) for p in etiquetas_parte]
                if declarado is None or None in partes or abs(declarado) < 1:
                    continue
                suma = sum(partes)
                relativo = abs(suma - declarado) / max(abs(declarado), 1e-9)
                # Un cuadro redondeado a la unidad produce diferencias de un punto que no son error.
                if relativo <= MATERIAL_TOTAL_PDF or abs(suma - declarado) <= TOLERANCIA_MONTO:
                    cierran += 1
                else:
                    fallan.append((anio, columna, bloque, declarado, suma, relativo))
        comparables = cierran + len(fallan)
        if comparables < 6 or cierran < CORROBORACION_TOTAL_PDF * comparables:
            continue
        for anio, columna, bloque, declarado, suma, relativo in fallan:
            referencia = bloque[etiqueta_total]
            periodo = f" en {anio}" if anio else ""
            hallazgos.append(_hallazgo(
                (
                    f"En el cuadro de la página {pagina}, «{columna}»{periodo}: "
                    f"{' + '.join(etiquetas_parte)} suman {_decimal_es(suma)} y «{etiqueta_total}» declara "
                    f"{_decimal_es(declarado)}, una diferencia de {_decimal_es(suma - declarado)} ({relativo:.1%}). "
                    f"La igualdad cierra en {cierran} de las {comparables} comparaciones del cuadro."
                ),
                referencia["fila"],
                referencia["indice"],
                [col_nivel, columna],
                {
                    "regla": "consolidado_no_cierra_pdf",
                    "columna": columna,
                    "periodo": anio or None,
                    "partes": etiquetas_parte,
                    "etiqueta_total": etiqueta_total,
                    "valor_declarado": declarado,
                    "valor_calculado": round(suma, 3),
                    "diferencia": round(suma - declarado, 3),
                    "diferencia_relativa": round(relativo, 5),
                    "comparaciones_que_cierran": cierran,
                    "comparaciones": comparables,
                    "pagina_pdf": pagina,
                    "tabla_pdf": tabla,
                },
            ))
            if len(hallazgos) >= MAX_HALLAZGOS:
                return hallazgos
    return hallazgos


def _hallazgos_total_por_fila(datos: list[dict[str, Any]]) -> list[dict]:
    """Los rubros de cada fila tienen que sumar el total que la propia fila declara.

    Es la misma igualdad que se revisa en una planilla, aplicada a un cuadro de PDF. No se afirma
    la relación sin corroborarla: la suma tiene que cerrar en la mayoría de las filas del cuadro
    para que las que no cierran signifiquen algo. Las diferencias por redondeo quedan afuera.
    """
    hallazgos: list[dict] = []
    for (_, pagina, tabla), filas in _cuadros_pdf(datos).items():
        columnas = _columnas_pdf(filas)
        totales = [c for c in columnas if re.search(r"total", c, re.I)]
        if len(totales) != 1 or len(columnas) < 5:
            continue
        total_col = totales[0]
        partes = [
            c
            for c in columnas
            if c != total_col
            and not c.startswith("columna_")
            and not re.search(r"%|a[nñ]o|nivel|categor|concepto|rubro|beneficio|tributo", c, re.I)
            and sum(1 for f in filas if _numero_pdf(f.get(c)) is not None) >= 0.8 * len(filas)
        ]
        if len(partes) < 3:
            continue
        cierran, fallan = 0, []
        for indice, fila in enumerate(filas):
            declarado = _numero_pdf(fila.get(total_col))
            valores = [_numero_pdf(fila.get(c)) for c in partes]
            if declarado is None or None in valores or abs(declarado) < 1:
                continue
            suma = sum(valores)
            relativo = abs(suma - declarado) / max(abs(declarado), 1e-9)
            if relativo <= MATERIAL_TOTAL_PDF or abs(suma - declarado) <= TOLERANCIA_MONTO:
                cierran += 1
            else:
                fallan.append((indice, fila, declarado, suma, relativo))
        comparables = cierran + len(fallan)
        if comparables < 4 or cierran < CORROBORACION_TOTAL_PDF * comparables:
            continue
        for indice, fila, declarado, suma, relativo in fallan:
            hallazgos.append(_hallazgo(
                (
                    f"En el cuadro de la página {pagina} los rubros de esta fila suman "
                    f"{_decimal_es(suma)} y la columna «{total_col}» declara {_decimal_es(declarado)}: "
                    f"una diferencia de {_decimal_es(suma - declarado)} ({relativo:.1%}). La igualdad cierra en "
                    f"{cierran} de las {comparables} filas del cuadro."
                ),
                fila,
                indice,
                [total_col, *partes],
                {
                    "regla": "total_de_fila_no_cierra_pdf",
                    "columna_total": total_col,
                    "componentes": partes,
                    "valor_declarado": declarado,
                    "valor_calculado": round(suma, 3),
                    "diferencia": round(suma - declarado, 3),
                    "diferencia_relativa": round(relativo, 5),
                    "filas_que_cierran": cierran,
                    "filas_comparables": comparables,
                    "pagina_pdf": pagina,
                    "tabla_pdf": tabla,
                },
            ))
            if len(hallazgos) >= MAX_HALLAZGOS:
                return hallazgos
    return hallazgos


def analizar(datos: list[dict[str, Any]]) -> list[dict]:
    from services.resultado_revision import separar_datos
    datos, _ = separar_datos(datos)
    if not datos or not _es_pdf(datos):
        return []

    hallazgos: list[dict] = []
    for bloque in (_hallazgos_total_por_fila, _hallazgos_consolidado_pdf, _hallazgos_composicion, _hallazgos_variacion, _hallazgos_porcentaje_de_base, _hallazgos_brecha):
        for hallazgo in bloque(datos):
            hallazgos.append(hallazgo)
            if len(hallazgos) >= MAX_HALLAZGOS:
                return hallazgos

    if hallazgos:
        return hallazgos[:MAX_HALLAZGOS]

    for hallazgo in _hallazgos_textuales(datos, set()):
        hallazgos.append(hallazgo)
        if len(hallazgos) >= MAX_HALLAZGOS:
            break
    return hallazgos
