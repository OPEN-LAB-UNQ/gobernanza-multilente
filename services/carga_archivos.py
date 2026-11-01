"""Convierte archivos subidos (CSV, Excel o PDF) en registros JSON-seguros.

La lectura de Excel usa detección de hoja y encabezado adaptada de Benford:
muchas planillas públicas traen títulos, celdas combinadas o varias hojas, y
`read_excel` con encabezado fijo pierde estructura.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from typing import Any

import pandas as pd

from services.plural import contar, muestra

EXTENSIONES_SOPORTADAS = {"csv", "xlsx", "xls", "pdf"}
# La carga directa de análisis sólo acepta Excel y CSV. Los PDF y las imágenes pasan antes por la
# revisión de lectura (/api/ocr): la persona ve el original al lado de la tabla leída, corrige y
# confirma. El lector de PDF de este módulo sigue disponible como biblioteca para esa herramienta.
EXTENSIONES_REVISION_LECTURA = {"pdf", "jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp", "heic", "heif"}
FIRMAS_IMAGEN = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"II*\x00", b"MM\x00*")
URL_REVISION_LECTURA = "/api/ocr"
MENSAJE_REVISION_LECTURA = (
    "Los PDF y las imágenes primero se leen y se revisan: abrí la revisión de lectura, "
    "confirmá la tabla y después se analiza."
)


def requiere_revision_lectura(filename: str, contenido: bytes) -> bool:
    """True si el archivo es un PDF o una imagen (por extensión o por contenido).

    Esos archivos no se analizan directo: primero pasan por la revisión de lectura. Se mira también
    el contenido para que un PDF renombrado como .xlsx o .csv no entre sin revisión.
    """
    if _extension(filename) in EXTENSIONES_REVISION_LECTURA:
        return True
    cabeza = (contenido or b"")[:1024]
    if b"%PDF-" in cabeza:
        return True
    if cabeza.startswith(FIRMAS_IMAGEN) or (cabeza[:4] == b"RIFF" and cabeza[8:12] == b"WEBP"):
        return True
    # «BM» abre también textos comunes («BMW;...»): un BMP tiene ceros reservados en los bytes 6 a 9.
    return cabeza.startswith(b"BM") and cabeza[6:10] == b"\x00\x00\x00\x00"

MIN_PAGINAS_PDF = 1
DEFAULT_LIMITE_PAGINAS_PDF = 150  # los cuadros de estos informes suelen estar en el anexo
MAX_PAGINAS_PDF = 300
MAX_TEXTO_PAGINA = 5000
MAX_FILAS_TABLAS_PDF = 1500
MINIMO_FILAS_TABLA_PDF = 20  # por debajo de esto se intenta también la lectura por texto alineado


def normalizar_limite_paginas_pdf(limite: int | None = None) -> int:
    """Devuelve un limite operativo seguro para lectura de PDF."""
    if limite is None:
        return DEFAULT_LIMITE_PAGINAS_PDF
    try:
        valor = int(limite)
    except (TypeError, ValueError):
        return DEFAULT_LIMITE_PAGINAS_PDF
    return max(MIN_PAGINAS_PDF, min(MAX_PAGINAS_PDF, valor))



class ArchivoNoSoportado(ValueError):
    pass


def _extension(filename: str) -> str:
    return (filename or "").lower().rsplit(".", 1)[-1] if "." in (filename or "") else ""


def _compactar(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    return re.sub(r"\s+", " ", str(valor).strip())


def _parece_encabezado(valor: Any) -> bool:
    text = unicodedata.normalize("NFKD", _compactar(valor).lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    if not text or text.startswith("unnamed"):
        return False
    return bool(
        re.search(
            r"concepto|indicador|jur|saf|programa|institucion|organismo|jurisdiccion|credito|vigente|devengado|pagado|compromiso|importe|monto|valor|total|inciso|partida|objeto|fuente|finalidad|funcion|periodo|fecha|mes|anio|ano|"
            r"exportacion|exportaciones|importacion|importaciones|saldo|precio|cantidad|porcentaje|sector|variacion|var\.?|mensual|trimestral|trimestre|trim|unidad|medida|participacion|pais|region|rubro|uso|turista|visitante|pernoctacion|estadia|via|destino|residencia|"
            # Encabezados habituales fuera del sector público: presupuesto vs real,
            # estados contables y tableros de indicadores.
            r"presupuest|real|desvio|ventas|costo|gasto|ingreso|egreso|resultado|margen|meta|objetivo|cumplimiento|avance|cuenta|"
            r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre",
            text,
        )
    ) or bool(re.fullmatch(r"(?:19|20)\d{2}(?:\.0)?", text))


def _flatten_columnas(columnas) -> list[str]:
    out = []
    vistos: dict[str, int] = {}
    for index, col in enumerate(columnas):
        valores = col if isinstance(col, tuple) else (col,)
        partes = []
        for valor in valores:
            parte = _compactar(valor)
            if not parte or parte.lower().startswith("unnamed"):
                continue
            if parte.endswith(".0") and parte[:-2].isdigit():
                parte = parte[:-2]
            if parte not in partes:
                partes.append(parte)
        nombre = " ".join(partes).strip() or f"columna_{index + 1}"
        nombre = re.sub(r"\s+", " ", nombre)
        count = vistos.get(nombre, 0)
        vistos[nombre] = count + 1
        if count:
            nombre = f"{nombre}_{count + 1}"
        out.append(nombre)
    return out


PERIODO_ENCABEZADO_RE = re.compile(r"(?:19|20)\d{2}(?:[-/]\d{1,2})?(?:[-/]\d{1,2})?")


def _celda_presente(v: Any) -> bool:
    return v is not None and not (isinstance(v, float) and v != v) and bool(str(v).strip())


def _celda_numerica(v: Any) -> bool:
    """Número guardado como número o escrito como texto («1.234,5», «(300)»); no un año ni una fecha."""
    if v is None or isinstance(v, bool) or hasattr(v, "year"):
        return False
    if isinstance(v, (int, float)):
        return v == v
    if isinstance(v, str):
        from services.perfilado import partes_numero

        return partes_numero(v) is not None
    return False


def _celda_periodo(v: Any) -> bool:
    if hasattr(v, "year"):
        return True
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)) and v == v and float(v).is_integer():
        return 1900 <= v <= 2100
    return bool(PERIODO_ENCABEZADO_RE.fullmatch(_compactar(v)))


def _encabezado_por_estructura(filas: list[list[Any]]) -> int | None:
    """Encabezado reconocido por la forma del cuadro, no por palabras de una lista.

    Una fila con al menos dos rótulos (textos o períodos, ningún importe) seguida de filas cuyos
    números caen en las columnas que esa fila nombra es un encabezado: «Concepto / Ejercicio
    2025», «Rubro / 30/06/2025» o «Provincia / Población / Tasa…» lo son aunque ninguna palabra
    figure en una lista. Un título de una sola celda no alcanza.
    """
    for idx, fila in enumerate(filas):
        celdas = {j: v for j, v in enumerate(fila) if _celda_presente(v)}
        if len(celdas) < 2:
            continue
        textos = [j for j, v in celdas.items() if isinstance(v, str) and not _celda_numerica(v)]
        periodos = [j for j, v in celdas.items() if j not in textos and _celda_periodo(v)]
        if not textos or len(textos) + len(periodos) < len(celdas):
            continue
        posiciones = set(celdas)
        con_numeros = consistentes = 0
        for abajo in filas[idx + 1 : idx + 13]:
            numericas = {j for j, v in enumerate(abajo) if _celda_numerica(v)}
            if not numericas:
                continue
            con_numeros += 1
            if numericas <= posiciones:
                consistentes += 1
            if con_numeros >= 6:
                break
        if consistentes >= 2 and consistentes >= 0.6 * con_numeros:
            return idx
    return None


def _encabezado_apilado(filas: list[list[Any]]) -> list[int] | None:
    """Reconoce rótulos repartidos en dos o tres filas antes del primer dato.

    Exige que las columnas numéricas del cuerpo tengan un rótulo en alguna de esas
    filas. Así una fila de título o una nota aislada no se convierte en encabezado.
    """
    for fin in range(min(len(filas) - 2, 48)):
        for largo in (2, 3, 4):
            inicio = fin - largo + 1
            if inicio < 0:
                continue
            niveles = filas[inicio:fin + 1]
            if any(any(_celda_numerica(v) and not _celda_periodo(v) for v in fila)
                   for fila in niveles):
                continue
            if any(sum(_celda_presente(v) for v in fila) < 2 for fila in niveles):
                continue
            rotuladas = {j for fila in niveles for j, v in enumerate(fila) if _celda_presente(v)}
            if len(rotuladas) < 3:
                continue
            cuerpo = []
            for fila in filas[fin + 1:fin + 9]:
                nums = {j for j, v in enumerate(fila) if _celda_numerica(v)}
                if len(nums) >= 2:
                    cuerpo.append(nums)
                if len(cuerpo) >= 3:
                    break
            if len(cuerpo) >= 2 and all(nums <= rotuladas for nums in cuerpo):
                return list(range(inicio, fin + 1))
    return None


def _detectar_filas_encabezado(contenido: bytes, sheet_name=0, libro=None) -> list[int] | None:
    """`libro`: el pd.ExcelFile ya abierto. Volver a abrir el archivo por cada hoja costaba, en un libro con
    cientos de miles de estilos, unos doce segundos por hoja; la lectura es la misma."""
    from services.excel_estructura import anios_plausibles, continua_fila_de_datos

    if libro is not None:
        preview = libro.parse(sheet_name, header=None, nrows=50)
    else:
        preview = pd.read_excel(io.BytesIO(contenido), sheet_name=sheet_name, header=None, nrows=50)
    filas_preview = preview.values.tolist()
    mejor_idx = None
    mejor_score = -1
    for idx, row in preview.iterrows():
        valores = [_compactar(v) for v in row.tolist()]
        no_vacios = [v for v in valores if v]
        # Una fila con importes no es un encabezado aunque alguno caiga entre 1900 y 2100
        # («2018 · 520 · 1.300 · 2.030» en un cuadro con años en filas).
        numeros_fila = [float(v) for v in row.tolist()
                        if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v]
        if numeros_fila and not (all(1800 <= n <= 2200 for n in numeros_fila) and anios_plausibles(numeros_fila)):
            continue
        if numeros_fila and continua_fila_de_datos(filas_preview, int(idx)):
            continue
        hits = sum(1 for v in valores if _parece_encabezado(v))
        # Antes el patrón tenía la barra duplicada dentro de un texto crudo y nunca reconocía
        # «2024»; además se miraba el texto compactado, que nunca tiene `.year`.
        fechas_o_periodos = sum(
            1
            for v in row.tolist()
            if hasattr(v, "year") or PERIODO_ENCABEZADO_RE.fullmatch(_compactar(v))
        )
        below = preview.iloc[idx + 1:min(idx + 8, len(preview))] if idx + 1 < len(preview) else None
        datos_abajo = int(below.notna().sum(axis=1).max() or 0) if below is not None else 0
        numericos_abajo = 0
        if below is not None:
            for _, fila_abajo in below.iterrows():
                numericos_abajo = max(
                    numericos_abajo,
                    sum(
                        1
                        for v in fila_abajo.tolist()
                        if pd.to_numeric(pd.Series([v]), errors="coerce").notna().iloc[0]
                    ),
                )
        # Evita tomar titulos sueltos ("Principales indicadores", "Fuentes") como encabezado.
        if len(no_vacios) < 3 or datos_abajo < 3:
            continue
        score = hits * 5 + fechas_o_periodos * 4 + min(len(no_vacios), 10) + min(datos_abajo, 10) + min(numericos_abajo, 10)
        if (hits >= 2 or fechas_o_periodos >= 2) and score > mejor_score:
            mejor_idx = int(idx)
            mejor_score = score
    if mejor_idx is None:
        mejor_idx = _encabezado_por_estructura(preview.values.tolist())
        if mejor_idx is None:
            return _encabezado_apilado(preview.values.tolist())

    filas = [mejor_idx]
    actual_no_vacios = int(preview.iloc[mejor_idx].notna().sum())
    if mejor_idx > 0:
        arriba = preview.iloc[mejor_idx - 1]
        hits_arriba = sum(1 for v in arriba.tolist() if _parece_encabezado(v))
        if hits_arriba >= 2 and int(arriba.notna().sum()) < actual_no_vacios:
            filas.insert(0, mejor_idx - 1)
    if mejor_idx + 1 < len(preview):
        next_hits = sum(1 for v in preview.iloc[mejor_idx + 1].tolist() if _parece_encabezado(v))
        sparse = actual_no_vacios < max(3, int(preview.shape[1] * 0.75))
        if next_hits >= 2 and sparse:
            filas.append(mejor_idx + 1)
    return filas


def _leer_hoja(contenido: bytes, sheet_name, header_rows: list[int]) -> pd.DataFrame:
    crudo = pd.read_excel(io.BytesIO(contenido), sheet_name=sheet_name, header=None)
    if len(header_rows) == 1:
        datos = crudo.iloc[header_rows[0] + 1:].reset_index(drop=True)
        datos.columns = _flatten_columnas(crudo.iloc[header_rows[0]].tolist())
        return datos

    niveles = []
    for fila in header_rows[:-1]:
        valores = crudo.iloc[fila].map(_compactar).replace("", None).ffill().fillna("")
        niveles.append(valores.tolist())
    niveles.append(crudo.iloc[header_rows[-1]].map(_compactar).tolist())
    datos = crudo.iloc[header_rows[-1] + 1:].reset_index(drop=True)
    datos.columns = _flatten_columnas(list(zip(*niveles)))
    return datos


def _numeric_count(frame: pd.DataFrame) -> int:
    count = 0
    for col in frame.columns:
        serie = pd.to_numeric(frame[col], errors="coerce")
        if len(serie.dropna()) >= max(3, int(len(frame) * 0.4)):
            count += 1
    return count


def _leer_excel(contenido: bytes) -> pd.DataFrame:
    from services.excel_cobertura import leer_libro
    datos, cobertura = leer_libro(contenido, "Excel")
    frame = pd.DataFrame(datos)
    frame.attrs["excel"] = cobertura
    return frame


def _fila_no_vacia_pdf(row: list[Any]) -> bool:
    return sum(1 for cell in row if _compactar(cell)) >= 2


def _normalizar_tabla_pdf(table: list[list[Any]]) -> list[list[str]]:
    rows = [[_compactar(cell) for cell in row] for row in table if row]
    rows = [row for row in rows if _fila_no_vacia_pdf(row)]
    if not rows:
        return []
    ancho = max(len(row) for row in rows)
    return [row + [""] * (ancho - len(row)) for row in rows]


def _score_header_pdf(row: list[str], rows_below: list[list[str]]) -> int:
    hits = sum(1 for cell in row if _parece_encabezado(cell))
    texto = sum(1 for cell in row if cell and re.search(r"[A-Za-zÀ-ÿ]", cell))
    numeros = sum(1 for cell in row if re.fullmatch(r"[-+]?\d[\d\.,%$ ]*", cell or ""))
    datos_abajo = 0
    for below in rows_below[:4]:
        datos_abajo = max(datos_abajo, sum(1 for cell in below if re.search(r"\d", cell or "")))
    return hits * 8 + texto * 2 + min(datos_abajo, 10) - numeros


def _detectar_header_pdf(rows: list[list[str]]) -> int | None:
    if len(rows) < 2:
        return None
    limite = min(6, len(rows) - 1)
    score, idx = max((_score_header_pdf(rows[i], rows[i + 1:]), i) for i in range(limite))
    if score >= 4:
        return idx
    return 0


TEXTO_PDF_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3}")


def _tiene_rotulos_pdf(columnas: list[str], filas: list[list[Any]]) -> bool:
    """Un cuadro dice de qué habla: o el encabezado nombra las columnas, o la primera celda de
    cada renglón trae el concepto. Sin ninguna de las dos cosas, lo extraído suele ser la serie
    de rótulos de un gráfico, que son números sueltos y no una tabla."""
    if any(not str(c).startswith("columna_") and TEXTO_PDF_RE.search(str(c or "")) for c in columnas):
        return True
    con_texto = sum(1 for f in filas if f and TEXTO_PDF_RE.search(str(f[0] or "")))
    return con_texto >= max(3, 0.6 * len(filas))


FECHA_CORTA_PDF = re.compile(r"^\d{1,2}[/-]\d{2,4}(?:[/-]\d{2,4})?$")


def _fila_parece_datos_pdf(row: list[str]) -> bool:
    """Una fila de datos, no un encabezado: la mayoría de sus celdas son importes o fechas.
    Un año suelto («2024») no cuenta: es el rótulo típico de un encabezado de períodos."""
    celdas = [c.replace(" ", "") for c in row if c]
    if not celdas:
        return False
    datos = sum(
        1 for c in celdas
        if (NUMERO_SUELTO_PDF.match(c) or FECHA_CORTA_PDF.match(c)) and not re.fullmatch(r"(?:19|20)\d{2}", c)
    )
    return datos >= max(1, (len(celdas) + 1) // 2)


def _filas_tabla_pdf(
    table: list[list[Any]],
    pagina: int,
    tabla_idx: int,
    filename: str,
    encabezado_previo: list[str] | None = None,
    estado: dict | None = None,
) -> list[dict[str, Any]]:
    rows = _normalizar_tabla_pdf(table)
    # Una tabla partida entre páginas suele seguir sin repetir el encabezado: si la primera
    # fila es de datos y el ancho coincide con el cuadro anterior, se hereda su encabezado en
    # lugar de convertir esa fila de datos en nombres de columna.
    if (
        encabezado_previo
        and rows
        and len(rows[0]) == len(encabezado_previo)
        and _fila_parece_datos_pdf(rows[0])
    ):
        columnas = list(encabezado_previo)
        data_rows = rows
        if estado is not None:
            estado["encabezado_heredado"] = True
    elif len(rows) < 2:
        return []
    else:
        header_idx = _detectar_header_pdf(rows)
        if header_idx is None:
            columnas = [f"columna_{i + 1}" for i in range(len(rows[0]))]
            data_rows = rows
        else:
            columnas = _flatten_columnas(rows[header_idx])
            data_rows = rows[header_idx + 1:]

    if not _tiene_rotulos_pdf(columnas, data_rows):
        return []
    registros: list[dict[str, Any]] = []
    header_normalizado = [c.lower() for c in columnas]
    for fila_idx, row in enumerate(data_rows, start=1):
        if not _fila_no_vacia_pdf(row):
            continue
        # En PDFs maquetados es frecuente que la primera celda quede vacía
        # porque el año o el rótulo abarca varias filas. No descartamos la
        # fila por esa celda: alcanza con que tenga contenido y algún número.
        if not any(_compactar(cell) for cell in row) or not any(re.search(r"\d", cell or "") for cell in row):
            continue
        row_norm = [_compactar(c).lower() for c in row]
        coincidencias = sum(1 for a, b in zip(row_norm, header_normalizado) if a and a == b)
        if coincidencias >= max(2, int(len(header_normalizado) * 0.6)):
            continue
        registro: dict[str, object] = {col: row[i] if i < len(row) else "" for i, col in enumerate(columnas)}
        registro.update(
            {
                "extraccion_pdf": "tabla",
                "pagina_pdf": pagina,
                "tabla_pdf": tabla_idx,
                "fila_tabla_pdf": fila_idx,
                "archivo_origen": filename,
            }
        )
        registros.append(registro)
    return registros


def _pagina_impresa_pdf(texto: str, total_paginas: int) -> int | None:
    # Only accept an unambiguous standalone number near the header/footer.
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    extremos = lineas[:12] + lineas[-4:]
    candidatos = {int(linea) for linea in extremos if re.fullmatch(r"\d{1,3}", linea) and 1 <= int(linea) <= total_paginas}
    return candidatos.pop() if len(candidatos) == 1 else None


def _filas_con_datos_pdf(table: list[list[Any]]) -> int:
    return sum(1 for row in _normalizar_tabla_pdf(table) if _fila_parece_datos_pdf(row))


def _extraer_tablas_pdf(
    contenido: bytes, filename: str, limite_paginas_pdf: int | None = None, diagnostico: dict | None = None
) -> list[dict[str, Any]]:
    # Algunos PDFs oficiales incluyen instrucciones graficas que pdfminer
    # advierte por stderr/logging aunque la extracción siga funcionando.
    for logger_name in ("pdfminer", "pdfminer.pdfinterp", "pdfminer.converter", "pdfplumber"):
        logging.getLogger(logger_name).setLevel(logging.ERROR)
    try:
        import pdfplumber
    except ImportError:
        return []

    filas: list[dict[str, Any]] = []
    encabezado_previo: list[str] | None = None
    pagina_encabezado = None
    settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "intersection_tolerance": 6,
        "snap_tolerance": 4,
        "join_tolerance": 4,
    }
    limite = normalizar_limite_paginas_pdf(limite_paginas_pdf)
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        total_paginas = len(pdf.pages)
        paginas_analizadas = min(limite, total_paginas)
        pdf_meta = {
            "paginas_documento": total_paginas,
            "paginas_pdf_analizadas": paginas_analizadas,
            "limite_paginas_pdf": limite,
            "pdf_truncado_por_paginas": total_paginas > paginas_analizadas,
        }
        for page_idx, page in enumerate(pdf.pages[:paginas_analizadas], start=1):
            try:
                tables = page.extract_tables(table_settings=settings) or []
                if not tables:
                    tables = page.extract_tables() or []
            except Exception:
                tables = []
            for table_idx, table in enumerate(tables, start=1):
                if diagnostico is not None:
                    detectadas = diagnostico.setdefault("filas_detectadas", {})
                    detectadas[page_idx] = detectadas.get(page_idx, 0) + _filas_con_datos_pdf(table)
                estado: dict = {}
                nuevas = _filas_tabla_pdf(table, page_idx, table_idx, filename, encabezado_previo, estado)
                # Un único renglón suele ser una caja gráfica de portada que
                # pdfplumber confundió con tabla. Para análisis cuantitativo
                # exigimos al menos dos filas relacionadas, salvo que continúe el cuadro anterior.
                if len(nuevas) < 2 and not (nuevas and estado.get("encabezado_heredado")):
                    continue
                if estado.get("encabezado_heredado") and diagnostico is not None:
                    diagnostico.setdefault("encabezados_heredados", []).append(
                        {"pagina": page_idx, "tabla": table_idx, "de_pagina": pagina_encabezado}
                    )
                else:
                    pagina_encabezado = page_idx
                encabezado_previo = [str(k) for k in nuevas[0] if k not in META_PDF]
                for fila in nuevas:
                    fila.update(pdf_meta)
                    fila["pagina_pdf_impresa"] = _pagina_impresa_pdf(page.extract_text() or "", total_paginas)
                filas.extend(nuevas)
                if len(filas) >= MAX_FILAS_TABLAS_PDF:
                    if diagnostico is not None:
                        diagnostico["tope_filas"] = MAX_FILAS_TABLAS_PDF
                    return filas[:MAX_FILAS_TABLAS_PDF]

    if filas:
        frame = pd.DataFrame(filas)
        if len(filas) >= 3 and _numeric_count(frame) >= 1:
            return filas
    return []


def _extraer_texto_pdf(contenido: bytes, limite_paginas_pdf: int | None = None) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ArchivoNoSoportado(
            "El servidor todavía no tiene soporte PDF instalado. Avisá para instalar pypdf."
        ) from exc

    reader = PdfReader(io.BytesIO(contenido))
    total_paginas = len(reader.pages)
    limite = normalizar_limite_paginas_pdf(limite_paginas_pdf)
    paginas_analizadas = min(limite, total_paginas)
    truncado = total_paginas > paginas_analizadas
    filas: list[dict[str, Any]] = []
    for idx, page in enumerate(reader.pages[:paginas_analizadas], start=1):
        texto_original = page.extract_text() or ""
        texto = _compactar(texto_original)
        if not texto:
            continue
        numeros = re.findall(r"[-+]?\d[\d\.,]*", texto)
        filas.append(
            {
                "tipo_documento": "pdf",
                "pagina": idx,
                "pagina_pdf_impresa": _pagina_impresa_pdf(texto_original, total_paginas),
                "paginas_documento": total_paginas,
                "paginas_pdf_analizadas": paginas_analizadas,
                "limite_paginas_pdf": limite,
                "pdf_truncado_por_paginas": truncado,
                "texto": texto[:MAX_TEXTO_PAGINA],
                "caracteres_extraidos": len(texto),
                "cantidad_numeros_detectados": len(numeros),
                "muestra_numeros": ", ".join(numeros[:12]),
            }
        )

    if not filas:
        raise ArchivoNoSoportado(
            "No se pudo extraer texto del PDF. Puede ser un escaneo/imagen; por ahora usá un PDF con texto seleccionable. "
            "Para un escaneo podés usar la lectura OCR local (sección OCR) y revisar el resultado antes de cargarlo."
        )
    return filas


def _limpiar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() or f"columna_{i + 1}" for i, c in enumerate(df.columns)]
    unnamed = [c for c in df.columns if str(c).lower().startswith("unnamed")]
    if unnamed:
        df = df.drop(columns=unnamed)
    return df.dropna(how="all").reset_index(drop=True)


# Un número de cuadro en formato local («1.234,5») o en inglés («1,234.5», «2,078,000.0»).
NUMERO_TABLA_TEXTO = re.compile(r"^-?(?:\d[\d.]*(,\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?)%?$")
# Rótulo de un cuadro en castellano o en inglés: «Cuadro 3», «Tabla 1», «Table 2».
RE_ROTULO_CUADRO_PDF = r"^(TABLA|CUADRO|TABLE|Tabla|Cuadro|Table)\s*\d"
RE_ROTULO_CUADRO_PDF_LINEA = re.compile(r"^\s*(TABLA|CUADRO|TABLE|Cuadro|Tabla|Table)\s*\d", re.M)


def _filas_texto_alineado_pdf(texto: str) -> list[list[str]]:
    """Filas de una tabla maquetada sin líneas: columnas separadas por dos o más espacios."""
    filas = []
    for linea in (texto or "").split("\n"):
        celdas = [c.strip() for c in re.split(r"\s{2,}", linea.strip()) if c.strip()]
        # Los ejes de un gráfico dejan dígitos sueltos: una celda de dato tiene al menos dos
        # caracteres o un separador decimal.
        if any(len(c) < 2 for c in celdas):
            filas.append([])
            continue
        numeros = sum(bool(NUMERO_TABLA_TEXTO.match(c.replace(" ", ""))) for c in celdas)
        if len(celdas) >= 4 and numeros >= 3 and numeros >= len(celdas) - 2:
            filas.append(celdas)
        elif filas and filas[-1]:
            filas.append([])  # corta el bloque: las tablas son tramos contiguos
    return filas


NUMERO_SUELTO_PDF = re.compile(r"^-?\(?(?:\d[\d.]*(?:,\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?)\)?%?$")
META_PDF = {
    "extraccion_pdf", "pagina_pdf", "pagina_pdf_impresa", "tabla_pdf", "fila_tabla_pdf", "archivo_origen",
    "paginas_documento", "paginas_pdf_analizadas", "limite_paginas_pdf", "pdf_truncado_por_paginas",
    "tipo_documento", "pagina", "caracteres_extraidos", "cantidad_numeros_detectados", "muestra_numeros",
}


def celda_con_varios_numeros(valor) -> bool:
    """Una celda que trae dos o más números juntos es una columna que no se pudo separar."""
    return sum(1 for token in str(valor or "").split() if NUMERO_SUELTO_PDF.match(token)) >= 2


def fila_sin_separar(fila: dict) -> bool:
    celdas = [v for k, v in fila.items() if k not in META_PDF]
    return sum(1 for v in celdas if celda_con_varios_numeros(v)) >= 2


def rotulos_poco_confiables(fila: dict) -> bool:
    """Un cuadro cuyas columnas no se pueden nombrar tampoco queda revisado.

    Al reconstruir columnas por coordenadas, un encabezado de varias palabras puede repartirse
    entre columnas vecinas y dejar nombres como «de vida» o «Sociales». Otras veces el encabezado
    detectado era una fila de datos y los nombres quedan numéricos. En los dos casos los valores
    están, pero no se sabe de qué son.
    """
    nombres = [str(k) for k in fila if k not in META_PDF]
    if len(nombres) < 3:
        return False
    def dudoso(nombre: str) -> bool:
        limpio = nombre.strip()
        if not limpio or limpio.startswith("columna_"):
            return True
        # Un año sí nombra una columna: es el período. Otro número, no.
        if re.fullmatch(r"(19|20)\d{2}", limpio):
            return False
        if NUMERO_SUELTO_PDF.match(limpio):
            return True
        return limpio[0].islower()
    return sum(1 for n in nombres if dudoso(n)) >= max(2, 0.3 * len(nombres))


def filas_separadas(filas: list[dict]) -> int:
    return sum(1 for f in filas if not fila_sin_separar(f))


TOLERANCIA_FILA_PDF = 3.0  # puntos de diferencia vertical que siguen siendo la misma fila
HUECO_COLUMNA_PDF = 4.0  # franja vertical sin palabras que separa dos columnas
MINIMO_PALABRAS_PDF = 12


def _numerica(texto: str) -> bool:
    return bool(NUMERO_SUELTO_PDF.match(str(texto).strip()))


def _sin_superindices_pdf(palabras: list[dict]) -> list[dict]:
    """Quita las llamadas de nota en superíndice pegadas a una cifra: letra mucho más chica, corta y
    justo a continuación de un número. Sin esto, «9.857» con su llamada «1» se leía «9.8571»."""
    tamanos = sorted(float(w.get("size") or 0) for w in palabras if _numerica(str(w["text"])))
    if not tamanos:
        return palabras
    normal = tamanos[len(tamanos) // 2]
    salida = []
    for w in palabras:
        previa = salida[-1] if salida else None
        if (previa is not None and float(w.get("size") or normal) < 0.75 * normal
                and re.fullmatch(r"[0-9*†‡a-z]{1,3}", str(w["text"]).strip())
                and _numerica(str(previa["text"])) and abs(float(w["x0"]) - float(previa["x1"])) <= 2.0):
            continue
        salida.append(w)
    return salida


def _es_prosa_pdf(fila: list[dict]) -> bool:
    """Un renglón de texto corrido: muchas palabras y más palabras que cifras."""
    textos = [str(w["text"]) for w in fila]
    numericas = sum(1 for t in textos if _numerica(t))
    return len(textos) - numericas >= 8 and len(textos) - numericas > 2 * numericas


def _filas_por_posicion_pdf(palabras: list[dict]) -> list[list[dict]]:
    """Agrupa palabras en filas por su posición vertical.

    Una palabra va con la fila que empieza a menos de la tolerancia. Con franjas fijas, un signo «−»
    de otra fuente, uno o dos puntos más arriba, caía en la franja vecina y su celda llegaba vacía.
    """
    filas: list[tuple[float, list[dict]]] = []
    for palabra in sorted(palabras, key=lambda w: float(w["top"])):
        arriba = float(palabra["top"])
        if filas and arriba - filas[-1][0] <= TOLERANCIA_FILA_PDF:
            filas[-1][1].append(palabra)
        else:
            filas.append((arriba, [palabra]))
    return [sorted(f, key=lambda w: float(w["x0"])) for _, f in filas]


def _cortes_de_columna_pdf(filas: list[list[dict]]) -> list[float]:
    """Los cortes entre columnas son las franjas verticales que ninguna palabra cruza.

    Se calculan sólo con las filas de datos: un título que ocupa el ancho de la página taparía
    todos los huecos y dejaría una sola columna.
    """
    ocupado: list[tuple[float, float]] = []
    for fila in filas:
        for palabra in fila:
            ocupado.append((float(palabra["x0"]), float(palabra["x1"])))
    if not ocupado:
        return []
    ocupado.sort()
    cortes: list[float] = []
    fin = ocupado[0][1]
    for inicio, termina in ocupado[1:]:
        if inicio - fin >= HUECO_COLUMNA_PDF:
            cortes.append((fin + inicio) / 2)
        fin = max(fin, termina)
    return cortes


HUECO_FRASE_PDF = 6.0  # separación entre dos rótulos distintos del encabezado


def _frases_pdf(fila: list[dict]) -> list[tuple[float, float, str]]:
    """Palabras contiguas del encabezado agrupadas en un rótulo, con su franja horizontal."""
    frases: list[tuple[float, float, str]] = []
    for palabra in fila:
        x0, x1, texto = float(palabra["x0"]), float(palabra["x1"]), str(palabra["text"]).strip()
        if not texto:
            continue
        if frases and x0 - frases[-1][1] <= HUECO_FRASE_PDF:
            inicio, _, previo = frases.pop()
            frases.append((inicio, x1, f"{previo} {texto}"))
        else:
            frases.append((x0, x1, texto))
    return frases


def _unir_niveles_pdf(partes: list[str]) -> str:
    """Un rótulo cortado en dos líneas —«Condiciones» / «de vida»— es un solo nombre, no dos niveles."""
    texto = ""
    for parte in dict.fromkeys(p for p in partes if p):
        if not texto:
            texto = parte
        elif parte[:1].islower():
            texto = f"{texto} {parte}"
        else:
            texto = f"{texto} · {parte}"
    return texto


def _es_titulo_pdf(fila: list[dict], ancho: float) -> bool:
    """El título del cuadro no es un nivel del encabezado: no nombra ninguna columna."""
    frases = _frases_pdf(fila)
    if not frases:
        return True
    if any(re.match(RE_ROTULO_CUADRO_PDF, texto) for _, _, texto in frases):
        return True
    return len(frases) == 1 and ancho > 0 and (frases[0][1] - frases[0][0]) >= 0.6 * ancho


def _rotulos_de_columna_pdf(encabezados: list[list[dict]], rangos: list[tuple[float, float]]) -> list[str]:
    """Compone el nombre de cada columna con los niveles del encabezado que la cubren.

    Un rótulo que abarca varias columnas —«Ayuda directa» sobre Nación, Provincias y Total— se
    reparte entre todas, y el nivel de abajo distingue cada una: «Ayuda directa · Nación». Así un
    encabezado de dos niveles deja de producir nombres partidos como «de vida».
    """
    nombres: list[list[str]] = [[] for _ in rangos]
    for r, fila in enumerate(encabezados):
        frases = _frases_por_columna_pdf(fila, encabezados[r + 1:], rangos)
        for indice, (inicio, fin) in enumerate(rangos):
            ancho = max(fin - inicio, 1.0)
            cubre = [
                texto
                for x0, x1, texto in frases
                if min(x1, fin) - max(x0, inicio) >= min(ancho, x1 - x0) * 0.5
            ]
            if cubre:
                nombres[indice].append(cubre[0])
    finales = [_unir_niveles_pdf(partes) for partes in nombres]
    if any(finales[i] and finales[i] == finales[i - 1] for i in range(1, len(finales))):
        # Dos columnas vecinas con el mismo nombre: un rótulo que abarca ambas sin un nivel que las
        # distinga, o dos rótulos pegados en una sola palabra («Miembro inferiorMiembro superior»).
        # Si repartiendo cada palabra a la columna donde está los nombres se distinguen, se usan esos.
        por_palabra = _rotulos_por_palabra_pdf(encabezados, rangos)
        i = 0
        while i < len(finales):
            j = i
            while j + 1 < len(finales) and finales[j + 1] and finales[j + 1] == finales[i]:
                j += 1
            if j > i:
                tramo = por_palabra[i : j + 1]
                if all(tramo) and len(set(tramo)) == len(tramo):
                    finales[i : j + 1] = tramo
            i = j + 1
    return finales


def _cubre_pdf(x0: float, x1: float, inicio: float, fin: float) -> bool:
    ancho = max(fin - inicio, 1.0)
    return min(x1, fin) - max(x0, inicio) >= min(ancho, x1 - x0) * 0.5


def _frases_por_columna_pdf(fila: list[dict], abajo: list[list[dict]], rangos: list[tuple[float, float]]):
    """Frases del encabezado, cada una con su franja horizontal, listas para repartir por columna.

    Dos rótulos vecinos pueden llegar pegados en una sola palabra («JuanSantiago»): la costura
    (minúscula seguida de una mayúscula que abre otra palabra) separa la frase. Además, una frase
    que cae sobre varias columnas se reparte por palabra salvo que sea un rótulo que abarca columnas
    con un nivel de abajo que las distingue («Ayuda directa» sobre «Nación», «Provincias»), o que
    sólo desborde sobre una columna que ya tiene su propio rótulo en esa línea.
    """
    def centro(w):
        return (float(w["x0"]) + float(w["x1"])) / 2

    palabras = []  # (palabra, empieza en una costura)
    for w in fila:
        texto = str(w["text"]).strip()
        if not texto:
            continue
        cortes = [m.start() for m in _COSTURA_PDF_RE.finditer(texto)]
        if not cortes:
            palabras.append((w, False))
            continue
        x0, x1 = float(w["x0"]), float(w["x1"])
        bordes = [0, *cortes, len(texto)]
        for i, (a, b) in enumerate(zip(bordes, bordes[1:])):
            palabras.append((dict(w, text=texto[a:b], x0=x0 + (x1 - x0) * a / len(texto),
                                  x1=x0 + (x1 - x0) * b / len(texto)), i > 0))
    frases: list[tuple[float, float, str, list[dict]]] = []
    for w, costura in palabras:
        x0, x1, texto = float(w["x0"]), float(w["x1"]), str(w["text"]).strip()
        if frases and not costura and x0 - frases[-1][1] <= HUECO_FRASE_PDF:
            desde, _, previo, ws = frases.pop()
            frases.append((desde, x1, f"{previo} {texto}", ws + [w]))
        else:
            frases.append((x0, x1, texto, [w]))

    debajo = [w for f in abajo for w in f if str(w["text"]).strip()]
    salida = []
    for n, (x0, x1, texto, ws) in enumerate(frases):
        por_columna = _rotulos_por_palabra_pdf([ws], rangos)
        columnas = [k for k, nombre in enumerate(por_columna) if nombre]
        cubiertas = sorted(set(columnas) | {k for k, (a, z) in enumerate(rangos) if _cubre_pdf(x0, x1, a, z)})
        nivel_abajo = all(any(rangos[k][0] <= centro(w) <= rangos[k][1] for w in debajo) for k in cubiertas)
        propias = {k for m, (y0, y1, _, _) in enumerate(frases) if m != n
                   for k, (a, z) in enumerate(rangos) if _cubre_pdf(y0, y1, a, z)}
        principal = max(cubiertas, key=lambda k: min(x1, rangos[k][1]) - max(x0, rangos[k][0]))
        if len(columnas) < 2 or nivel_abajo or any(k in propias for k in columnas if k != principal):
            salida.append((x0, x1, texto))
            continue
        for k in columnas:
            salida.append((rangos[k][0], rangos[k][1], por_columna[k]))
    return salida


# Costura entre dos rótulos pegados: «JuanSantiago», «inferiorMiembro» (no «PyMEs» ni «McDonald»).
_COSTURA_PDF_RE = re.compile(r"(?<=[a-záéíóúñ]{3})(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2})")


_PEGADAS_PDF_RE = re.compile(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])")


def _rotulos_por_palabra_pdf(encabezados: list[list[dict]], rangos: list[tuple[float, float]]) -> list[str]:
    """Nombre de cada columna con las palabras cuyo centro cae en ella; separa palabras pegadas."""
    nombres: list[list[str]] = [[] for _ in rangos]
    for fila in encabezados:
        por_columna: list[list[str]] = [[] for _ in rangos]
        for palabra in fila:
            texto = str(palabra["text"]).strip()
            if not texto:
                continue
            x0, x1 = float(palabra["x0"]), float(palabra["x1"])
            cortes = [m.start() for m in _PEGADAS_PDF_RE.finditer(texto)]
            bordes = [0, *cortes, len(texto)]
            for a, b in zip(bordes, bordes[1:]):
                trozo = texto[a:b]
                centro = x0 + (x1 - x0) * (a + b) / 2 / max(len(texto), 1)
                indice = min(range(len(rangos)), key=lambda k: 0 if rangos[k][0] <= centro <= rangos[k][1]
                             else min(abs(centro - rangos[k][0]), abs(centro - rangos[k][1])))
                por_columna[indice].append(trozo)
        for indice, palabras in enumerate(por_columna):
            if palabras:
                nombres[indice].append(" ".join(palabras))
    return [_unir_niveles_pdf(partes) for partes in nombres]


def _completar_combinadas_pdf(page, datos, filas_grilla, franja) -> None:
    """Primera columna con celdas combinadas en vertical («Patagonia» centrada en un grupo de tres
    filas): la cuadrícula sólo la corta en los bordes de cada grupo. Las filas de datos entre dos
    bordes horizontales que cruzan la primera columna forman un grupo; si en un grupo de dos o más
    filas sólo una tiene rótulo y todas tienen dato en la segunda columna, el rótulo va a todas."""
    a, b = franja
    if b <= a:
        return
    try:
        bordes = sorted({round(float(e["top"]), 1) for e in (page.edges or [])
                         if e.get("orientation") == "h" and float(e["x0"]) <= a + 1 and float(e["x1"]) >= b - 1})
        if len(bordes) < 3:
            return
        grupos: dict[int, list[int]] = {}
        for d, fila in enumerate(datos):
            arriba = min(float(w["top"]) for w in fila)
            grupos.setdefault(sum(1 for y in bordes if y <= arriba + 1), []).append(d)
        for ds in grupos.values():
            llenos = [d for d in ds if filas_grilla[d][0]]
            if (len(ds) >= 2 and len(llenos) == 1
                    and all(len(filas_grilla[d]) > 1 and filas_grilla[d][1] for d in ds)):
                for d in ds:
                    filas_grilla[d][0] = filas_grilla[llenos[0]][0]
    except Exception:  # noqa: BLE001 — una franja recortada sin bordes legibles queda como estaba
        return


def _grilla_por_coordenadas_pdf(page) -> list[list[str]]:
    """Reconstruye las columnas por la posición de cada palabra, no por los espacios del texto.

    Con un encabezado de dos niveles o columnas muy juntas, el texto sale pegado y separar por
    espacios mete varios valores en una celda. Una columna, en cambio, es una franja vertical de
    la página que ninguna palabra cruza, y eso no depende de cómo quedó el espaciado.
    """
    try:
        # Con el tamaño de letra, una llamada de nota en superíndice («9.857¹») sale como palabra aparte.
        letras = getattr(page, "chars", None) or []
        girada = bool(letras) and sum(1 for ch in letras if not ch.get("upright", True)) > 0.3 * len(letras)
        palabras = page.extract_words(keep_blank_chars=False, **({} if girada else {"extra_attrs": ["size"]})) or []
    except Exception:
        return []
    if len(palabras) < MINIMO_PALABRAS_PDF:
        return []
    palabras = _sin_superindices_pdf(palabras)
    filas = _filas_por_posicion_pdf(palabras)
    # Un renglón de un párrafo que menciona cifras («informaron 23.037 cortes… 3,1 %») no es una fila
    # del cuadro: con él adentro, las columnas no se separan.
    datos = [f for f in filas if sum(1 for w in f if _numerica(w["text"])) >= 2 and not _es_prosa_pdf(f)]
    if len(datos) < 3:
        return []
    cortes = _cortes_de_columna_pdf(datos)
    if len(cortes) < 2:
        return []

    def indice_columna(palabra: dict) -> int:
        centro = (float(palabra["x0"]) + float(palabra["x1"])) / 2
        return sum(1 for corte in cortes if centro > corte)

    def celdas(fila: list[dict]) -> list[str]:
        columnas: list[list[str]] = [[] for _ in range(len(cortes) + 1)]
        for palabra in fila:
            columnas[indice_columna(palabra)].append(str(palabra["text"]))
        return [" ".join(c).strip() for c in columnas]

    # Franja horizontal real de cada columna, según las palabras de datos que cayeron en ella.
    rangos: list[list[float]] = [[float("inf"), float("-inf")] for _ in range(len(cortes) + 1)]
    for fila in datos:
        for palabra in fila:
            indice = indice_columna(palabra)
            rangos[indice][0] = min(rangos[indice][0], float(palabra["x0"]))
            rangos[indice][1] = max(rangos[indice][1], float(palabra["x1"]))
    franjas = [(a, b) if a <= b else (0.0, 0.0) for a, b in rangos]

    primera = filas.index(datos[0])
    ancho_tabla = max(b for _, b in franjas) - min(a for a, _ in franjas if a)
    encabezados = [
        f
        for f in filas[max(0, primera - 3) : primera]
        if len([w for w in f if w["text"].strip()]) >= 2 and not _es_titulo_pdf(f, ancho_tabla)
    ]
    rotulos = _rotulos_de_columna_pdf(encabezados, franjas)
    # Un rótulo de fila partido en dos líneas: la segunda, sin cifras y toda dentro de la primera
    # columna, completa el rótulo de la fila de datos de arriba (antes se perdía).
    posicion = {id(f): k for k, f in enumerate(filas)}
    indices_datos = [posicion[id(f)] for f in datos]
    de_datos = set(indices_datos)
    extra: dict[int, list[str]] = {}
    for k in range(indices_datos[0] + 1, indices_datos[-1]):
        f = filas[k]
        if k in de_datos or not f or any(_numerica(w["text"]) for w in f):
            continue
        if any(indice_columna(w) != 0 for w in f):
            continue
        arriba = max(d for d, kd in enumerate(indices_datos) if kd < k)
        extra.setdefault(arriba, []).append(" ".join(str(w["text"]) for w in f))
    filas_grilla = []
    for d, f in enumerate(datos):
        c = celdas(f)
        if d in extra:
            c[0] = " ".join([c[0], *extra[d]]).strip()
        filas_grilla.append(c)
    _completar_combinadas_pdf(page, datos, filas_grilla, franjas[0])
    grilla = ([rotulos] if any(rotulos) else []) + filas_grilla
    # Una página a dos columnas: los renglones de texto corrido de la columna vecina caen enteros en una
    # franja del cuadro, entre sus filas, y siguen por encima o por debajo del cuadro. Esa franja no es una
    # columna del cuadro: sin cifras, se quita. (Una columna «Observaciones» no sigue fuera del cuadro.)
    prosa = [f for f in filas[indices_datos[0]:indices_datos[-1]] if f and _es_prosa_pdf(f)]
    afuera = [f for f in filas[:indices_datos[0]] + filas[indices_datos[-1] + 1:] if f and _es_prosa_pdf(f)]
    ajenas = {j for j in range(1, len(cortes) + 1)
              if sum(1 for f in prosa if all(indice_columna(w) == j for w in f)) >= 2
              and any(all(indice_columna(w) == j for w in f) for f in afuera)
              and not any(_numerica(c[j]) for c in filas_grilla)}
    if ajenas:
        grilla = [[c for j, c in enumerate(f) if j not in ajenas] for f in grilla]
    # Una grilla de verdad tiene casi todas sus filas con la misma cantidad de celdas con contenido.
    llenas = [sum(1 for c in fila if c) for fila in grilla]
    if max(llenas) < 3 or sum(1 for n in llenas if n >= max(llenas) - 1) < 0.6 * len(llenas):
        return []
    return grilla


def _valor_pdf(texto) -> float | None:
    """Número de una celda de PDF, con el mismo criterio que usa el resto del sistema."""
    from services.perfilado import numero

    return numero(texto)


MILES_ES_PDF = re.compile(r"^-?\(?\d{1,3}(\.\d{3})+(,\d+)?\)?$")
ENTERO_PDF = re.compile(r"^-?\(?\d{1,3}\)?$")


def _normalizar_miles_pdf(registros: list[dict[str, Any]]) -> None:
    """Quita el punto de miles cuando la columna lo usa como separador de miles.

    «1.738» es ambiguo: en inglés es uno con setecientos treinta y ocho milésimos y acá es mil
    setecientos treinta y ocho. En estos cuadros la coma es el decimal, así que un punto seguido de
    exactamente tres dígitos es separador de miles. Se decide por columna y sólo cuando el patrón se
    repite: si no, el valor queda como está.
    """
    if not registros:
        return
    from services.perfilado import formato_columna, preferencia_formato

    columnas = list(dict.fromkeys(str(k) for r in registros for k in r if k not in META_PDF))
    preferencia = preferencia_formato(
        str(r.get(c) or "").strip() for r in registros for c in columnas
    )
    for columna in columnas:
        textos = [str(r.get(columna) or "").strip() for r in registros]
        con_valor = [x for x in textos if x]
        con_miles = [x for x in con_valor if MILES_ES_PDF.match(x)]
        if not con_miles:
            continue
        formato, origen = formato_columna(con_valor, preferencia)
        # Una columna de enteros sin separador («984») en la que los mayores llevan punto cada
        # tres cifras («1.054») usa el punto como miles: en inglés serían los únicos valores con
        # decimales, y siempre con tres. Pasaba en cuadros con montos de tres y cuatro cifras.
        resto = [x for x in con_valor if not MILES_ES_PDF.match(x)]
        enteros_y_miles = len(con_valor) >= 3 and bool(resto) and all(ENTERO_PDF.match(x) for x in resto)
        if not enteros_y_miles:
            # Con pocos valores y sin nada que lo confirme, «1.738» queda como está.
            if formato != "es" or (len(con_valor) < 3 and origen != "columna"):
                continue
            if origen != "columna" and len(con_miles) < 0.6 * len(con_valor):
                continue
        for registro in registros:
            texto = str(registro.get(columna) or "").strip()
            if MILES_ES_PDF.match(texto):
                registro[columna] = texto.replace(".", "")


def _nombrar_columnas_por_relacion_pdf(registros: list[dict[str, Any]]) -> None:
    """Una columna sin rótulo cuyos valores son el porcentaje de otra se nombra por lo que hace.

    Si la columna B es el porcentaje de la columna A sobre un total, entonces 100·A/B da ese total y
    es el mismo en todas las filas. Eso se puede verificar sin conocer el total y sin adivinar el
    rótulo: cuando se cumple, la columna pasa a llamarse «A · %».
    """
    from statistics import median

    if len(registros) < 4:
        return
    columnas = [str(k) for k in registros[0] if k not in META_PDF]
    valores = {c: [_valor_pdf(r.get(c)) for r in registros] for c in columnas}
    renombrar: dict[str, str] = {}
    for posicion, columna in enumerate(columnas):
        if posicion == 0 or not columna.startswith("columna_"):
            continue
        referencia = columnas[posicion - 1]
        if referencia.startswith("columna_") or referencia in renombrar:
            continue
        pares = [
            (a, b)
            for a, b in zip(valores[referencia], valores[columna])
            if a is not None and b is not None and a > 0 and b > 0
        ]
        if len(pares) < 4:
            continue
        implicitos = [100 * a / b for a, b in pares]
        total = median(implicitos)
        # El cuadro puede incluir su propia fila de total: ahí la parte más grande es el total.
        if total <= 0 or total < max(a for a, _ in pares) * 0.98:
            continue
        estables = sum(1 for x in implicitos if abs(x - total) <= 0.05 * total)
        if estables >= 0.8 * len(implicitos):
            renombrar[columna] = f"{referencia} · %"
    if not renombrar:
        return
    # Se reconstruye cada fila para no alterar el orden de las columnas al renombrarlas.
    for indice, registro in enumerate(registros):
        registros[indice] = {renombrar.get(str(k), k): v for k, v in registro.items()}


def _tablas_coordenadas_pdf(contenido: bytes, filename: str, limite_paginas_pdf: int | None = None) -> list[dict[str, Any]]:
    """Tercera estrategia: columnas por coordenadas, para los cuadros que salen con celdas pegadas."""
    try:
        import pdfplumber
    except ImportError:
        return []
    limite = normalizar_limite_paginas_pdf(limite_paginas_pdf)
    registros: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        total_paginas = len(pdf.pages)
        paginas_analizadas = min(limite, total_paginas)
        meta = {
            "paginas_documento": total_paginas,
            "paginas_pdf_analizadas": paginas_analizadas,
            "limite_paginas_pdf": limite,
            "pdf_truncado_por_paginas": total_paginas > paginas_analizadas,
        }
        for pagina, page in enumerate(pdf.pages[:paginas_analizadas], start=1):
            try:
                texto = page.extract_text() or ""
            except Exception:
                continue
            if not re.search(RE_ROTULO_CUADRO_PDF_LINEA, texto):
                continue
            grilla = _grilla_por_coordenadas_pdf(page)
            if not grilla:
                continue
            nuevas = _filas_tabla_pdf(grilla, pagina, 1, filename)
            _normalizar_miles_pdf(nuevas)
            _nombrar_columnas_por_relacion_pdf(nuevas)
            for registro in nuevas:
                registro["extraccion_pdf"] = "tabla_coordenadas"
                registro.update(meta)
            registros.extend(nuevas)
            if len(registros) >= MAX_FILAS_TABLAS_PDF:
                break
    return registros


def _tablas_texto_pdf(contenido: bytes, filename: str, limite_paginas_pdf: int | None = None) -> list[dict[str, Any]]:
    """Segunda estrategia: muchos informes oficiales maquetan sus cuadros sin líneas.

    Sólo se toman tramos contiguos de filas numéricas alineadas, que es lo que distingue un
    cuadro de un gráfico o de un párrafo. Cada fila queda marcada como 'tabla_texto' para que
    el origen de cada dato sea reconocible.
    """
    try:
        import pdfplumber
    except ImportError:
        return []
    limite = normalizar_limite_paginas_pdf(limite_paginas_pdf)
    registros: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        total_paginas = len(pdf.pages)
        paginas_analizadas = min(limite, total_paginas)
        meta = {
            "paginas_documento": total_paginas,
            "paginas_pdf_analizadas": paginas_analizadas,
            "limite_paginas_pdf": limite,
            "pdf_truncado_por_paginas": total_paginas > paginas_analizadas,
        }
        for pagina, page in enumerate(pdf.pages[:paginas_analizadas], start=1):
            try:
                texto = page.extract_text(layout=True) or ""
            except Exception:
                continue
            # Los cuadros de estos informes vienen rotulados; sin rótulo suele ser un gráfico.
            if not re.search(RE_ROTULO_CUADRO_PDF_LINEA, texto):
                continue
            bloque: list[list[str]] = []
            tabla_idx = 0
            for fila in _filas_texto_alineado_pdf(texto) + [[]]:
                if fila:
                    bloque.append(fila)
                    continue
                anchos = {len(f) for f in bloque}
                if len(bloque) >= 3 and len(anchos) <= 2:
                    tabla_idx += 1
                    nuevas = _filas_tabla_pdf(bloque, pagina, tabla_idx, filename)
                    for registro in nuevas:
                        registro["extraccion_pdf"] = "tabla_texto"
                        registro.update(meta)
                    registros.extend(nuevas)
                bloque = []
            if len(registros) >= MAX_FILAS_TABLAS_PDF:
                break
    return registros


def _leer_csv(contenido: bytes, **extra):
    try:
        return pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", **extra), "utf-8"
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", encoding="latin1", **extra), "latin1"


def _csv_usa_miles_con_punto(contenido: bytes, codificacion: str) -> bool:
    """Compatibilidad: ¿alguna columna decide punto de miles con la evidencia de todo el archivo?

    Ya no se usa para releer el archivo entero: cada columna se lee con su propio formato
    (ver `_leer_csv_con_lectura`).
    """
    from services.perfilado import formato_columna, preferencia_formato

    try:
        crudo, _ = _leer_csv(contenido, dtype=str)
    except Exception:
        return False
    todos = [str(v).strip() for c in crudo.columns for v in crudo[c].tolist() if str(v).strip() and str(v) != "nan"]
    preferencia = preferencia_formato(todos)
    for columna in crudo.columns:
        valores = [str(v).strip() for v in crudo[columna].tolist() if str(v).strip() and str(v) != "nan"]
        con_miles = sum(1 for v in valores if MILES_ES_PDF.match(v))
        if con_miles >= max(3, 0.6 * len(valores)) and formato_columna(valores, preferencia)[0] == "es":
            return True
    return False


def muestra_segura(columna: str, valores: list, valor: Any) -> str:
    """Texto de una celda citada en la cobertura, con la misma barrera que el resto de los datos:
    una columna que la sanitización excluye no se cita, y el texto libre pasa por la redacción."""
    from services import sanitizacion

    if sanitizacion.columna_sensible(str(columna), list(valores)):
        return "valor de una columna excluida por identificar personas o documentos"
    return sanitizacion.redactar_texto_libre(str(valor))[:60]


NOTA_CSV_RE = re.compile(
    r"^\s*(?:fuente|fuentes|nota|notas|elaboraci[oó]n|referencias?|aclaraci[oó]n|observaci[oó]n|"
    r"\(\d+\)|\*|\d\)\s)",
    re.IGNORECASE,
)


def _decodificar(contenido: bytes) -> tuple[str, str, bool]:
    bom = contenido.startswith(b"\xef\xbb\xbf")
    try:
        return contenido.decode("utf-8-sig"), "utf-8", bom
    except UnicodeDecodeError:
        return contenido.decode("latin1"), "latin1", False


def _contar_fuera_de_comillas(linea: str, sep: str) -> int:
    n, dentro = 0, False
    for ch in linea:
        if ch == '"':
            dentro = not dentro
        elif ch == sep and not dentro:
            n += 1
    return n


def _separador_csv(texto: str) -> str:
    """El separador es el que aparece la misma cantidad de veces en el encabezado y en las filas.

    Se mira la cantidad más repetida entre las líneas, no la de la primera: un CSV publicado suele
    empezar con una o dos líneas de título («Cuadro 3. Producción…») antes del encabezado.
    """
    lineas = [linea for linea in texto.splitlines() if linea.strip()][:30]
    if not lineas:
        return ","
    mejor = None
    for orden, sep in enumerate(("\t", ";", "|", ",")):
        cuentas = [_contar_fuera_de_comillas(linea, sep) for linea in lineas]
        positivas = [c for c in cuentas if c]
        if not positivas:
            continue
        moda = max(set(positivas), key=lambda c: (positivas.count(c), c))
        cabecera = cuentas[0] if cuentas[0] else moda
        iguales = sum(1 for c in cuentas[1:] if c == cabecera)
        if cabecera != moda:
            iguales = max(iguales, cuentas.count(moda) - 1)
        clave = (iguales / max(1, len(lineas) - 1), -orden)
        if mejor is None or clave > mejor[0]:
            mejor = (clave, sep)
    return mejor[1] if mejor else ","


_LINEA_ENVUELTA_CSV = re.compile(r'^\s*"((?:[^"]|"")*)"\s*$')
_CIFRA_CSV = re.compile(r"^[-−(]?\d[\d.,]*\)?\s*%?$")


def desenvolver_lineas_csv(texto: str) -> tuple[str, list[int]]:
    """Líneas guardadas enteras entre comillas («"Salta;12,5;13,1"») vuelven a separarse en sus campos.

    Así deja Excel un CSV al guardarlo con otra configuración regional: cada línea de datos es un solo
    campo de texto y el cuadro parece no tener filas. Se desenvuelven sólo si forman un bloque seguido que
    es la mayoría de las líneas, cada una con alguna cifra después del rótulo y, con el separador que
    resulta, tantos campos como el encabezado. Un título o una fuente entre comillas con un «;» adentro no
    son líneas de datos. Devuelve el texto y las filas desenvueltas (contadas desde 1).
    """
    lineas = texto.splitlines(keepends=True)
    envueltas = {}
    for k, linea in enumerate(lineas):
        cuerpo = linea.rstrip("\r\n")
        m = _LINEA_ENVUELTA_CSV.match(cuerpo)
        if m and any(s in m.group(1) for s in ("\t", ";", "|")):
            envueltas[k] = m.group(1).replace('""', '"') + linea[len(cuerpo):]
    llenas = [k for k, linea in enumerate(lineas) if linea.strip()]
    bloque = [k for k in llenas if k in envueltas]
    if len(bloque) < 2 or 2 * len(bloque) < len(llenas):
        return texto, []
    desde = llenas.index(bloque[0])
    if llenas[desde:desde + len(bloque)] != bloque:
        return texto, []
    prueba = [envueltas.get(k, linea) for k, linea in enumerate(lineas)]
    sep = _separador_csv("".join(prueba))
    # El encabezado es la línea anterior al bloque (o la primera del bloque, si también vino envuelta).
    encabezado = prueba[llenas[desde - 1]] if desde else prueba[bloque[0]]
    ancho = _contar_fuera_de_comillas(encabezado, sep)
    if not ancho or any(_contar_fuera_de_comillas(prueba[k], sep) != ancho for k in bloque):
        return texto, []
    import csv as _csv

    for k in (bloque if desde else bloque[1:]):
        campos = next(_csv.reader([prueba[k].rstrip("\r\n")], delimiter=sep), [])
        if not any(_CIFRA_CSV.match(c.strip()) for c in campos[1:]):
            return texto, []
    return "".join(prueba), [k + 1 for k in bloque]


def _comentarios_y_corte_csv(texto: str, sep: str) -> tuple[str, list[tuple[int, str]], tuple[int, str] | None]:
    """Líneas de comentario («# …») fuera de los datos, y la última línea si el archivo se cortó.

    Una línea que empieza con «#» es un comentario de la exportación, no un registro. Un archivo
    que no termina en salto de línea y cuya última línea tiene menos campos que las demás se cortó
    (descarga interrumpida): esa línea no se incorpora y se declara. Las líneas se dejan vacías para
    no cambiar la numeración de las filas.
    """
    import csv as _csv

    lineas = texto.splitlines(keepends=True)
    comentarios = []
    for k, linea in enumerate(lineas):
        if linea.lstrip().startswith("#"):
            comentarios.append((k + 1, linea.strip()))
            lineas[k] = "\n"

    def campos(linea):
        try:
            return next(_csv.reader([linea], delimiter=sep), [])
        except _csv.Error:
            return linea.split(sep)

    cortada = None
    if lineas and lineas[-1].strip() and not lineas[-1].endswith(("\n", "\r")):
        ancho = max((len(campos(x)) for x in lineas[:-1] if x.strip()), default=0)
        if ancho and len(campos(lineas[-1])) < ancho:
            cortada = (len(lineas), lineas[-1].strip())
            lineas[-1] = ""
    return "".join(lineas), comentarios, cortada


def _inicio_tabla_csv(texto: str, sep: str) -> int:
    """Línea del encabezado: la primera con al menos la mitad de los campos que usan las filas.

    Las líneas de arriba con un solo texto («Cuadro 3. Producción de leche», «En miles de
    litros», aun con separadores sobrantes) son títulos, no el encabezado.
    """
    import csv as _csv

    llenos = []
    for linea in texto.splitlines()[:200]:
        try:
            campos = next(_csv.reader([linea], delimiter=sep), [])
        except _csv.Error:
            campos = linea.split(sep)
        llenos.append(sum(1 for c in campos if c.strip()))
    if not llenos:
        return 0
    maximo = max(llenos)
    minimo = max(2, (maximo + 1) // 2)
    return next((i for i, n in enumerate(llenos) if n >= minimo), 0)


def _csv_con_lineas_largas(texto: str, sep: str):
    import csv as _csv

    filas = list(_csv.reader(io.StringIO(texto), delimiter=sep))
    while filas and not any(c.strip() for c in filas[0]):
        filas.pop(0)
    encabezado = filas[0] if filas else []
    ancho = len(encabezado)
    cuerpo, descartadas = [], []
    for n, fila in enumerate(filas[1:], start=2):
        if not any(c.strip() for c in fila):
            continue
        if len(fila) > ancho:
            # Sólo se repara lo inequívoco: campos de más vacíos al final. Si traen datos, la fila
            # está corrida y no se sabe qué campo sobra: se declara y queda afuera.
            if any(c.strip() for c in fila[ancho:]):
                descartadas.append((n, len(fila)))
                continue
            fila = fila[:ancho]
        cuerpo.append(fila + [""] * (ancho - len(fila)))
    crudo = pd.DataFrame(cuerpo, columns=[c if c.strip() else f"Unnamed: {j}" for j, c in enumerate(encabezado)], dtype=str)
    return crudo, descartadas


def _hay_lineas_largas_csv(texto: str, sep: str) -> bool:
    """¿Alguna fila trae más campos que el encabezado? Ver `campos_de_mas_csv`."""
    import csv as _csv

    filas = [f for f in _csv.reader(io.StringIO(texto), delimiter=sep) if any(c.strip() for c in f)]
    return bool(filas) and any(len(f) > len(filas[0]) for f in filas[1:])


NOMBRE_SEPARADOR = {"\t": "tabulación", ";": "punto y coma", "|": "barra vertical", ",": "coma"}


def _leer_csv_con_lectura(contenido: bytes, filename: str) -> tuple[list[dict], dict]:
    """Lee un CSV con un único criterio numérico por columna, decidido con todo el archivo.

    El separador decimal y el de miles se deciden por columna con la evidencia de todas sus
    celdas, y el resto del archivo desempata. Nunca se relee el archivo entero por el patrón de
    una sola columna: así «0.125» no pasa a ser 125 porque otra columna use punto de miles.
    """
    from services.perfilado import es_sin_dato, interpretar_columna, preferencia_formato

    texto, codificacion, bom = _decodificar(contenido)
    texto = texto.replace("\ufeff", "")
    texto, desenvueltas = desenvolver_lineas_csv(texto)
    sep = _separador_csv(texto)
    texto, comentarios, cortada = _comentarios_y_corte_csv(texto, sep)
    inicio = _inicio_tabla_csv(texto, sep)
    titulos = []
    if inicio:
        lineas = texto.splitlines(keepends=True)
        titulos = [(k + 1, linea.strip().strip(sep).strip().strip('"')) for k, linea in enumerate(lineas[:inicio]) if linea.strip().strip(sep).strip()]
        texto = "".join(lineas[inicio:])
    import csv as _csv

    # CSV de R (write.table con nombres de fila): el encabezado tiene un campo menos que TODAS las filas.
    filas_csv = [f for f in _csv.reader(io.StringIO(texto), delimiter=sep) if any(c.strip() for c in f)]
    rotulo_de_fila = len(filas_csv) >= 3 and all(
        len(f) == len(filas_csv[0]) + 1 and f[0].strip() and not _celda_numerica(f[0].strip())
        and _celda_numerica(f[-1].strip()) for f in filas_csv[1:])
    if rotulo_de_fila:
        texto = sep + texto.lstrip("\r\n")
    descartadas = []
    try:
        if _hay_lineas_largas_csv(texto, sep):
            raise pd.errors.ParserError("líneas con más campos que el encabezado")
        crudo = pd.read_csv(io.StringIO(texto), sep=sep, engine="python", dtype=str, keep_default_na=False)
    except pd.errors.ParserError:
        # Una línea con más campos que el encabezado no invalida el archivo entero: si los
        # campos de más están vacíos se recortan; si no, esa línea se declara y queda afuera.
        # (pandas no siempre falla: a veces toma la primera columna como índice y corre la fila.)
        crudo, descartadas = _csv_con_lineas_largas(texto, sep)
    nombres = []
    for i, c in enumerate(crudo.columns):
        nombre = re.sub(r"\s+", " ", str(c).replace("\ufeff", "")).strip()
        if not nombre or nombre.lower().startswith("unnamed"):
            nombre = f"columna_{i + 1}"
        nombres.append(nombre)
    filas = [[("" if v is None else str(v)).strip() for v in fila] for fila in crudo.itertuples(index=False, name=None)]
    vacias_por_columna = [all(not f[j] for f in filas) for j in range(len(nombres))]
    # Una columna sin nombre y sin datos es un separador sobrante al final de la línea.
    columnas_validas = [j for j, n in enumerate(nombres) if not (n.startswith("columna_") and vacias_por_columna[j])]

    info: dict[str, Any] = {
        "tipo_lectura": "csv",
        "codificacion": codificacion,
        "bom": bom,
        "separador": NOMBRE_SEPARADOR.get(sep, sep),
        "filas_nota": [],
        "columnas_numericas": {},
        "celdas_no_interpretables": [],
        "celdas_sin_dato": 0,
        "avisos": [],
    }
    if rotulo_de_fila:
        info["avisos"].append("El encabezado tiene un campo menos que todas las filas (así exporta R con nombres de "
                              "fila): la primera columna se tomó como rótulo de cada fila.")
    if desenvueltas:
        info["lineas_desenvueltas"] = desenvueltas
        info["avisos"].append(
            f"{len(desenvueltas)} líneas venían enteras entre comillas (así las deja Excel al guardar con otra "
            f"configuración regional): se separaron sus campos por el {info['separador']}.")
    if comentarios:
        info["lineas_comentario"] = [n for n, _ in comentarios]
        info["avisos"].append(
            f"{contar(len(comentarios), 'línea de comentario', 'líneas de comentario')} («#») "
            + ("se separó" if len(comentarios) == 1 else "se separaron") + " de los datos: "
            + muestra([f"fila {n}" for n, _ in comentarios], maximo=4, separador="; ") + "."
        )
    if cortada:
        info["linea_cortada"] = cortada[0]
        info.setdefault("pendientes_lectura", []).append(dict(
            tipo="no_leido", donde=f"fila {cortada[0]}",
            motivo=f"el archivo termina a mitad de esa línea («{cortada[1][:40]}»): parece cortado, puede faltar el "
                   "resto y esa fila no se incorporó"))
    if descartadas:
        ancho = len(crudo.columns)
        info["filas_descartadas"] = [n + inicio for n, _ in descartadas]
        info["avisos"].append(
            f"{contar(len(descartadas), 'línea tiene', 'líneas tienen')} más campos que el encabezado ({ancho}) y no se "
            f"{'incorporó' if len(descartadas) == 1 else 'incorporaron'} para no correr sus valores de columna: "
            + muestra([f"fila {n + inicio}: {campos} campos" for n, campos in descartadas], maximo=4, separador="; ") + "."
        )
    if titulos:
        from services.sanitizacion import redactar_texto_libre

        info["filas_titulo"] = [{"fila": n, "texto": redactar_texto_libre(t)[:200]} for n, t in titulos]
        info["avisos"].append(
            f"{contar(len(titulos), 'línea de título', 'líneas de título')} antes del encabezado (fila {inicio + 1}) "
            + ("se separó" if len(titulos) == 1 else "se separaron") + " de los datos: "
            + muestra([f"fila {x['fila']}: «{x['texto'][:60]}»" for x in info["filas_titulo"]], maximo=3, separador="; ") + "."
        )

    def numerica(fila):
        return any(fila[j] and not es_sin_dato(fila[j]) and _celda_numerica(fila[j]) for j in columnas_validas[1:])

    con_numeros = [i for i, f in enumerate(filas) if numerica(f)]
    ultima = con_numeros[-1] if con_numeros else -1
    conservadas = []
    for i, f in enumerate(filas):
        presentes = [j for j in columnas_validas if f[j]]
        if not presentes:
            continue
        # «Fuente: …», «Nota: …» o una línea suelta después del cuadro no son una fila de datos.
        if len(presentes) == 1 and not numerica(f) and (NOTA_CSV_RE.match(f[presentes[0]]) or i > ultima):
            from services.sanitizacion import redactar_texto_libre

            info["filas_nota"].append({"fila": i + 2 + inicio, "texto": redactar_texto_libre(f[presentes[0]])[:200]})
            continue
        if len(presentes) >= 2 and all(f[j] == nombres[j] for j in presentes):
            info.setdefault("filas_encabezado_repetido", []).append(i + 2 + inicio)
            continue
        conservadas.append((i, f))
    if info.get("filas_encabezado_repetido"):
        repetidas = info["filas_encabezado_repetido"]
        info["avisos"].append(
            f"El encabezado se repite en {'la fila' if len(repetidas) == 1 else 'las filas'} "
            + ", ".join(str(n) for n in repetidas[:5])
            + " (parecen exportaciones pegadas): se tomó como encabezado, no como un registro."
        )

    from services.perfilado import es_formula_texto, unidad_pegada

    formulas = sum(1 for _, f in conservadas for j in columnas_validas if es_formula_texto(f[j]))
    if formulas:
        info["avisos"].append(
            f"{contar(formulas, 'cifra venía', 'cifras venían')} como fórmula de texto de Excel («=\"12345\"»): "
            + ("se leyó" if formulas == 1 else "se leyeron") + " como número.")
    unidades = sorted({u for _, f in conservadas for j in columnas_validas if (u := unidad_pegada(f[j]))})
    if unidades:
        info["avisos"].append(
            "Las cifras traían la unidad pegada (" + ", ".join(f"«{u}»" for u in unidades)
            + "): se leyeron sin ella.")
    todos = [f[j] for _, f in conservadas for j in columnas_validas]
    preferencia = preferencia_formato(todos)
    columnas = {}
    ambiguas_punto = []
    suprimidas = []  # (columna, fila del archivo, texto) de los datos suprimidos («<5»)
    menores = []  # ídem, de los valores menores que la unidad mínima publicada («<0,1»)
    marcas_sin_dato = []  # marcas de dato no disponible tal como están escritas («-», «///», «s/i»)
    for j in columnas_validas:
        valores = [f[j] or None for _, f in conservadas]
        nuevos, informe = interpretar_columna(valores, preferencia)
        columnas[j] = nuevos
        if informe["numerica"]:
            info["columnas_numericas"][nombres[j]] = {
                "formato": informe["formato"],
                "decidido_por": informe["formato_decidido_por"],
            }
            # Los suprimidos («<5») se avisan aparte: no son una marca de «sin dato» («-», «s/d»).
            info["celdas_sin_dato"] += (len(informe["sin_dato"]) - len(informe.get("suprimidos", []))
                                        - len(informe.get("menores", [])))
            apartados = set(informe.get("suprimidos", [])) | set(informe.get("menores", []))
            marcas_sin_dato.extend(str(valores[k]).strip() for k in informe["sin_dato"]
                                   if k not in apartados and str(valores[k] or "").strip())
            suprimidas.extend((nombres[j], conservadas[k][0] + 2 + inicio, str(valores[k]).strip())
                              for k in informe.get("suprimidos", []))
            menores.extend((nombres[j], conservadas[k][0] + 2 + inicio, str(valores[k]).strip())
                           for k in informe.get("menores", []))
            if informe["no_interpretables"]:
                ejemplos = [
                    f"fila {conservadas[k][0] + 2 + inicio}: «{muestra_segura(nombres[j], valores, valores[k])}»"
                    for k in informe["no_interpretables"][:5]
                ]
                info["celdas_no_interpretables"].append(
                    {"columna": nombres[j], "celdas": len(informe["no_interpretables"]), "ejemplos": ejemplos}
                )
                info["avisos"].append(
                    f"{contar(len(informe['no_interpretables']), 'celda no interpretable', 'celdas no interpretables')} como número en columna "
                    f"«{nombres[j]}» ({muestra(ejemplos, len(informe['no_interpretables']), 3, '; ')}): se conservan como texto y no entran en los controles numéricos."
                )
            if informe["formato_decidido_por"] == "predeterminado_ambiguo":
                from services.perfilado import evidencia_formato, partes_numero

                coma = next((v for v in valores if isinstance(v, str) and (p := partes_numero(v))
                             and evidencia_formato(p[1]) == "ambiguo_coma"), None)
                if coma:
                    # «31,821» puede ser treinta y un mil (inglés) o treinta y uno con decimales:
                    # se declara, porque leerlo mal cambia la escala por mil.
                    info["avisos"].append(
                        f"Columna «{nombres[j]}»: números como «{coma.strip()}» (una coma seguida de tres cifras) sin otra "
                        "evidencia en el archivo; se leyó la coma como decimal. Si es separador de miles, la escala es mil veces mayor."
                    )
                    info.setdefault("pendientes_lectura", []).append(dict(
                        tipo="no_controlado", donde=f"columna «{nombres[j]}»",
                        motivo=f"formato numérico ambiguo («{coma.strip()}»): ningún valor del archivo decide si la coma "
                               "separa miles o decimales; se leyó como decimal"))
                else:
                    punto = next((v for v in valores if isinstance(v, str) and (p := partes_numero(v))
                                  and evidencia_formato(p[1]) == "ambiguo_punto"), None)
                    ejemplo = (punto or "1.738").strip()
                    info["avisos"].append(
                        f"Columna «{nombres[j]}»: números como «{ejemplo}» sin otra evidencia en el archivo; "
                        "se leyó el punto como separador de miles. Si es decimal, la escala es mil veces menor."
                    )
                    if punto:
                        ambiguas_punto.append((nombres[j], ejemplo))
    if suprimidas:
        # «<5» no es un 5 ni un vacío: es un dato que existe y no se publica. Los totales lo incluyen,
        # así que sus cierres no se pueden comprobar; se dice aparte de las celdas no interpretables.
        marcas = list(dict.fromkeys(f"«{t}»" for _, _, t in suprimidas))
        info["celdas_suprimidas"] = {"celdas": len(suprimidas), "marcas": marcas[:5],
                                     "ejemplos": [f"{c}, fila {r}" for c, r, _ in suprimidas[:10]]}
        info["avisos"].append(
            f"{contar(len(suprimidas), 'celda', 'celdas')} con dato suprimido por confidencialidad estadística "
            f"({', '.join(marcas[:3])}; {muestra([f'fila {r} en «{c}»' for c, r, _ in suprimidas], maximo=3, separador='; ')}): "
            "no son un número y no entran en los controles numéricos; los totales que las incluyen no se pueden comprobar.")
    if menores:
        # «<0,1»: valor menor que la unidad mínima publicada; existe, pero no se informa la cifra.
        marcas = list(dict.fromkeys(f"«{t}»" for _, _, t in menores))
        info["celdas_menores_que_unidad"] = {"celdas": len(menores), "marcas": marcas[:5],
                                             "ejemplos": [f"{c}, fila {r}" for c, r, _ in menores[:10]]}
        info["avisos"].append(
            f"{contar(len(menores), 'celda', 'celdas')} con valor menor que la unidad mínima publicada "
            f"({', '.join(marcas[:3])}; {muestra([f'fila {r} en «{c}»' for c, r, _ in menores], maximo=3, separador='; ')}): "
            "no se informa la cifra; no entran en los controles numéricos y los totales que las incluyen no se pueden comprobar.")
    if ambiguas_punto:
        # Leer el punto como miles o como decimal cambia la escala por mil: va al comienzo del informe.
        info.setdefault("pendientes_lectura", []).append(dict(
            tipo="no_controlado",
            donde=("columna " if len(ambiguas_punto) == 1 else "columnas ")
            + muestra([f"«{n}»" for n, _ in ambiguas_punto], maximo=3),
            motivo=f"formato numérico ambiguo («{ambiguas_punto[0][1]}»): ningún valor del archivo decide si el punto "
                   "separa miles o decimales; se leyó como separador de miles (si es decimal, las cifras son mil veces menores)"))
    if info["filas_nota"]:
        info["avisos"].append(
            f"{contar(len(info['filas_nota']), 'fila de nota o fuente separada', 'filas de nota o fuente separadas')} de los datos: "
            + muestra([f"fila {n['fila']}: «{n['texto'][:60]}»" for n in info["filas_nota"]], maximo=3, separador="; ")
        )
    if info["celdas_sin_dato"]:
        info["avisos"].append(
            f"{contar(info['celdas_sin_dato'], 'celda marcada', 'celdas marcadas')} sin dato "
            f"({', '.join(dict.fromkeys(f'«{m}»' for m in marcas_sin_dato)) or '«-», «s/d»'}): "
            "se tratan como sin dato, no como cero ni como un valor."
        )
    registros = []
    for k, _ in enumerate(conservadas):
        registros.append({nombres[j]: columnas[j][k] for j in columnas_validas})
    if not registros:
        info["motivo"] = (
            f"se leyó el encabezado (fila {inicio + 1}, separador {info['separador']}) pero ninguna fila de datos debajo"
            if len(columnas_validas) >= 2
            else "no se reconoció un cuadro: ninguna línea tiene dos o más campos separados por tabulación, punto y coma, barra o coma"
        )
    return registros, info


FIRMA_ZIP = b"PK\x03\x04"
FIRMA_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# Una página web guardada con extensión de datos (descarga fallida, sesión vencida). «<5;…» no lo es.
PAGINA_WEB = re.compile(rb"\s*(?:<!doctype\s+html|<html[\s>]|<\?xml)", re.I)
# Open XML estricto («Guardar como» de Excel): los mismos datos con otros espacios de nombres, que
# openpyxl no reconoce. El de relaciones va al final: es prefijo de los otros dos de relaciones.
_ESTRICTO_A_TRANSICIONAL = (
    (b"http://purl.oclc.org/ooxml/spreadsheetml/main", b"http://schemas.openxmlformats.org/spreadsheetml/2006/main"),
    (b"http://purl.oclc.org/ooxml/drawingml/main", b"http://schemas.openxmlformats.org/drawingml/2006/main"),
    (b"http://purl.oclc.org/ooxml/officeDocument/relationships/extendedProperties",
     b"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"),
    (b"http://purl.oclc.org/ooxml/officeDocument/extendedProperties",
     b"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"),
    (b"http://purl.oclc.org/ooxml/officeDocument/relationships",
     b"http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
)
AVISO_ESTRICTO = "libro Open XML estricto: se leyó convirtiéndolo a .xlsx común."


# Tope de celdas con datos de un libro: por encima, la lectura y los controles necesitan más memoria que la
# del servicio (un libro de 11 MB con ~2,8 millones de celdas superó 3 GB). Se cuenta sin cargar el libro.
MAX_CELDAS_LIBRO = 1_500_000
MAX_BYTES_DESCOMPRIMIDOS = 1_500_000_000  # un .xlsx que se infla más que esto no se lee (bomba de compresión)
_CELDA_XLSX = re.compile(rb"<(?:\w+:)?(?:v|is)>")


def celdas_con_datos(filename: str, contenido: bytes) -> int | None:
    """Celdas con un valor en un libro .xlsx o .xls, contadas sin cargarlo entero (las hojas de un .xlsx
    se leen descomprimiendo por partes; las de un .xls, de a una). None si no es un libro o no se pudo
    contar: en ese caso la lectura sigue y declara lo que no pudo leer."""
    try:
        if contenido[:4] == FIRMA_ZIP:
            import zipfile

            total = descomprimido = 0
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                for item in z.infolist():
                    if not re.match(r"xl/worksheets/[^/]+\.xml$", item.filename):
                        continue
                    with z.open(item) as f:
                        cola = b""
                        while True:
                            bloque = f.read(1 << 20)
                            if not bloque:
                                break
                            descomprimido += len(bloque)
                            if descomprimido > MAX_BYTES_DESCOMPRIMIDOS:
                                return MAX_CELDAS_LIBRO * 10
                            texto = cola + bloque
                            # Lo que queda al final del bloque puede ser el comienzo de una marca: se cuenta en el siguiente.
                            corte = max(0, len(texto) - 8)
                            total += len(_CELDA_XLSX.findall(texto, 0, corte))
                            cola = texto[corte:]
                        total += len(_CELDA_XLSX.findall(cola))
            return total
        if contenido[:8] == FIRMA_OLE and _extension(filename) == "xls":
            import xlrd

            libro = xlrd.open_workbook(file_contents=contenido, on_demand=True, formatting_info=False)
            try:
                total = 0
                for k in range(libro.nsheets):
                    hoja = libro.sheet_by_index(k)
                    total += sum(1 for r in range(hoja.nrows) for t in hoja.row_types(r)
                                 if t not in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK))
                    libro.unload_sheet(k)
                    if total > MAX_CELDAS_LIBRO:
                        break
                return total
            finally:
                libro.release_resources()
    except Exception:  # noqa: BLE001 — sin contar, la lectura sigue y declara lo que no pudo leer
        return None
    return None


def motivo_libro_demasiado_grande(filename: str, contenido: bytes) -> str | None:
    """Motivo claro para rechazar un libro que no entra en la memoria del análisis; None si entra."""
    celdas = celdas_con_datos(filename, contenido)
    if celdas is None or celdas <= MAX_CELDAS_LIBRO:
        return None
    cifra = f"{celdas:,}".replace(",", ".") if celdas < MAX_CELDAS_LIBRO * 10 else f"más de {MAX_CELDAS_LIBRO * 10:,}".replace(",", ".")
    return (f"«{filename}»: el libro tiene {cifra} celdas con datos; el máximo es "
            f"{MAX_CELDAS_LIBRO:,}".replace(",", ".") + ": dividilo o quitá las hojas que no hacen falta y volvé a cargarlo.")


def libro_transicional(contenido: bytes) -> bytes:
    """Un libro Open XML estricto reescrito como .xlsx común (transicional); cualquier otro contenido,
    o un error al convertir, devuelve el original sin tocar (el mismo objeto)."""
    if contenido[:4] != FIRMA_ZIP:
        return contenido
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            if b"purl.oclc.org/ooxml" not in z.read("xl/workbook.xml"):
                return contenido
            salida = io.BytesIO()
            with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zo:
                for item in z.infolist():
                    datos = z.read(item.filename)
                    if item.filename.endswith((".xml", ".rels")):
                        for estricto, transicional in _ESTRICTO_A_TRANSICIONAL:
                            datos = datos.replace(estricto, transicional)
                    zo.writestr(item, datos)
            return salida.getvalue()
    except Exception:  # noqa: BLE001 — sin convertir, la lectura sigue y declara lo que no pudo leer
        return contenido


def _motivo_marcado(filename: str, ext: str, contenido: bytes) -> str:
    """Por qué no se lee un archivo de texto marcado (HTML o XML) con extensión de datos."""
    texto = contenido[:65536].lower()
    if b"urn:schemas-microsoft-com:office:spreadsheet" in texto:
        return (f"'{filename}': es una Hoja de cálculo XML 2003 (no un .xlsx ni un .xls binario): abrila en Excel y "
                "guardala como .xlsx")
    if b"<table" in texto:
        return (f"'{filename}': es una tabla HTML guardada con extensión .{ext}: abrila en Excel y guardala como .xlsx")
    # Una descarga fallida (la página de inicio de sesión de un portal) guardada como «.csv»: no es un
    # cuadro de una fila con etiquetas HTML, es un archivo sin datos.
    return (f"'{filename}': no es un CSV ni un Excel: es una página web (HTML), posiblemente una descarga fallida "
            "o una sesión vencida; descargá de nuevo el archivo de datos")


def tipo_por_contenido(filename: str, contenido: bytes) -> str:
    """xlsx, xls, pdf o csv según la firma del archivo, no según la extensión."""
    ext = _extension(filename)
    if ext not in EXTENSIONES_SOPORTADAS:
        raise ArchivoNoSoportado(f"'{filename}': formato no soportado, usar CSV, Excel o PDF (.csv, .xlsx, .xls, .pdf)")
    cabeza = contenido[:1024]
    if contenido[:4] == FIRMA_ZIP:
        return "xlsx"
    if contenido[:8] == FIRMA_OLE:
        return "xls"
    if PAGINA_WEB.match(cabeza[3:] if cabeza.startswith(b"\xef\xbb\xbf") else cabeza):
        raise ArchivoNoSoportado(_motivo_marcado(filename, ext, contenido))
    if b"%PDF-" in cabeza:
        return "pdf"
    if ext in {"xlsx", "xls"}:
        # Muchos sistemas exportan «.xls» que en realidad son texto separado por comas o tabs.
        try:
            muestra = contenido[:4096].decode("utf-8")
        except UnicodeDecodeError:
            muestra = contenido[:4096].decode("latin1")
        if "\x00" not in muestra and any(sep in muestra for sep in ("\t", ";", ",")) and "<" not in muestra[:200]:
            return "csv"
        if "<table" in muestra.lower():
            raise ArchivoNoSoportado(_motivo_marcado(filename, ext, contenido))
        raise ArchivoNoSoportado(f"'{filename}': el contenido no es un Excel (.xlsx o .xls) ni un CSV reconocible")
    if ext == "pdf":
        raise ArchivoNoSoportado(f"'{filename}': el contenido no es un PDF")
    return "csv"


DESCRIPCION_LECTURA = {
    "xlsx": "Excel .xlsx (OOXML)",
    "xls": "Excel .xls (formato binario)",
    "csv": "texto delimitado (CSV)",
    "pdf": "PDF",
}


def _leer_pdf_con_lectura(contenido: bytes, filename: str, limite_paginas_pdf: int | None = None) -> tuple[list[dict], dict]:
    limite_pdf = normalizar_limite_paginas_pdf(limite_paginas_pdf)
    diagnostico: dict = {}
    filas = _extraer_tablas_pdf(contenido, filename, limite_pdf, diagnostico)
    # Pocas filas, o muchas filas con las columnas pegadas: en los dos casos vale probar otra
    # estrategia. Un cuadro leído con tres valores en una celda no es un cuadro leído.
    if len(filas) < MINIMO_FILAS_TABLA_PDF or filas_separadas(filas) < 0.7 * len(filas):
        # Entre estrategias no gana la que trae más filas, sino la que trae más filas con las
        # columnas separadas: una celda con tres números juntos no es una fila revisable.
        for otra in (_tablas_coordenadas_pdf(contenido, filename, limite_pdf),
                     _tablas_texto_pdf(contenido, filename, limite_pdf)):
            if (filas_separadas(otra), len(otra)) > (filas_separadas(filas), len(filas)):
                filas = otra
    info: dict[str, Any] = {"tipo_lectura": "pdf_tablas", "avisos": [], "bloques_descartados": []}
    if filas:
        # Mismo criterio numérico para todas las estrategias, decidido con todo el archivo.
        _normalizar_miles_pdf(filas)
        ambiguas = _formato_numerico_pdf(filas, contenido, limite_pdf)
        if ambiguas:
            info["formato_ambiguo"] = ambiguas
            por_pagina: dict[Any, list[dict]] = {}
            for a in ambiguas:
                por_pagina.setdefault(a["pagina"], []).append(a)
            info["pendientes_lectura"] = [
                dict(tipo="no_controlado",
                     donde=f"página {pagina}, " + (f"columna «{grupo[0]['columna']}»" if len(grupo) == 1 else
                                                   f"columnas {muestra(['«' + a['columna'] + '»' for a in grupo], maximo=4)}"),
                     motivo=f"formato numérico ambiguo («{grupo[0]['ejemplo']}»): ningún valor del cuadro ni del documento "
                            "decide si la coma separa miles o decimales; se leyó como decimal")
                for pagina, grupo in por_pagina.items()
            ]
            info["avisos"].append(
                f"«{filename}»: {contar(len(ambiguas), 'columna', 'columnas')} con números como «{ambiguas[0]['ejemplo']}» "
                "(una coma seguida de tres cifras) sin otro valor del cuadro o del documento que decida el formato: "
                "puede ser separador de miles (inglés) o decimal (castellano). Se leyó la coma como decimal; verificá la escala: "
                + muestra([f"página {a['pagina']}, «{a['columna']}»" for a in ambiguas], maximo=3, separador="; ") + "."
            )
        info["modos_extraccion"] = sorted({str(f.get("extraccion_pdf") or "") for f in filas})
        info["celdas_no_interpretables"] = _no_interpretables_pdf(filas)
        for d in info["celdas_no_interpretables"]:
            info["avisos"].append(
                f"«{filename}»: {contar(d['celdas'], 'celda no interpretable', 'celdas no interpretables')} como número en columna «{d['columna']}» "
                f"({muestra(d['ejemplos'], d['celdas'], 3, '; ')}); quedan como texto."
            )
    else:
        filas = _extraer_texto_pdf(contenido, limite_pdf)
        for fila in filas:
            fila["archivo_origen"] = filename
            fila["extraccion_pdf"] = "texto_por_pagina"
        info["tipo_lectura"] = "pdf_texto_por_pagina"
        info["modos_extraccion"] = ["texto_por_pagina"]
    primera = filas[0] if filas else {}
    total = primera.get("paginas_documento")
    analizadas = primera.get("paginas_pdf_analizadas")
    sin_texto = paginas_sin_texto_pdf(contenido, limite_pdf)
    if sin_texto:
        # Una página que es sólo imagen no se leyó aunque esté dentro del rango analizado.
        info["paginas_sin_texto"] = sin_texto
        info.setdefault("pendientes_lectura", []).append(dict(
            tipo="no_leido",
            donde=("página " if len(sin_texto) == 1 else "páginas ") + muestra(sin_texto, maximo=6),
            motivo="sin texto extraíble: probablemente escaneada; sus cuadros no se leyeron ni se controlaron",
        ))
        info["avisos"].append(
            f"«{filename}»: {'la página' if len(sin_texto) == 1 else 'las páginas'} {muestra(sin_texto, maximo=6)} "
            f"no {'tiene' if len(sin_texto) == 1 else 'tienen'} texto extraíble (probablemente escaneada"
            f"{'' if len(sin_texto) == 1 else 's'}): no se leyó su contenido."
        )
    info.update(paginas_documento=total, paginas_analizadas=analizadas, limite_paginas_pdf=limite_pdf,
                truncado_por_paginas=bool(primera.get("pdf_truncado_por_paginas")))
    incorporadas: dict[int, int] = {}
    for f in filas:
        if f.get("pagina_pdf") is not None:
            incorporadas[int(f["pagina_pdf"])] = incorporadas.get(int(f["pagina_pdf"]), 0) + 1
    if info["tipo_lectura"] == "pdf_tablas" or diagnostico.get("filas_detectadas"):
        for pagina, detectadas in sorted((diagnostico.get("filas_detectadas") or {}).items()):
            faltan = detectadas - incorporadas.get(pagina, 0)
            if faltan > 0 and info.get("modos_extraccion") == ["tabla"]:
                info["bloques_descartados"].append({"pagina": pagina, "filas": faltan})
    for d in info["bloques_descartados"]:
        info["avisos"].append(
            f"«{filename}» página {d['pagina']}: {contar(d['filas'], 'fila de cuadro no incorporada', 'filas de cuadro no incorporadas')} "
            "(sin encabezado reconocible o sin columnas separadas)."
        )
    if diagnostico.get("encabezados_heredados"):
        info["encabezados_heredados"] = diagnostico["encabezados_heredados"]
        paginas = ", ".join(str(h["pagina"]) for h in diagnostico["encabezados_heredados"])
        info["avisos"].append(
            f"«{filename}»: el cuadro continúa sin repetir el encabezado en "
            f"{'la página' if len(diagnostico['encabezados_heredados']) == 1 else 'las páginas'} {paginas}; "
            "se usó el encabezado del bloque anterior porque las columnas coinciden."
        )
    if diagnostico.get("tope_filas"):
        info["avisos"].append(
            f"«{filename}»: se alcanzó el máximo de {diagnostico['tope_filas']} filas de cuadros; el resto no se incorporó."
        )
    if info["truncado_por_paginas"]:
        info["avisos"].append(aviso_truncado_pdf(filename, total, analizadas, limite_pdf,
                                                 sin_cuadros=info["tipo_lectura"] != "pdf_tablas"))
    return filas, info


def _tokens_numericos_texto_pdf(contenido: bytes, limite: int) -> list[str]:
    """Números escritos en el texto del documento: desempatan el formato de un cuadro ambiguo."""
    try:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(contenido))
        textos = [(pagina.extract_text() or "") for pagina in lector.pages[:limite]]
    except Exception:  # noqa: BLE001 — sin texto no hay desempate
        return []
    return re.findall(r"(?<![\w.,])\d[\d.,]*\d(?![\w])", " ".join(textos))


def _formato_numerico_pdf(filas: list[dict], contenido: bytes, limite: int) -> list[dict]:
    """Decide por cuadro y columna si la coma es separador de miles o decimal.

    «31,821» es ambiguo: en inglés es treinta y un mil ochocientos veintiuno y en castellano
    treinta y uno con ochocientos veintiún milésimos. Decide la columna con sus propios valores
    («2,078,000.0» o «1,234.5» son inglés; «1.234,5» es castellano); si no alcanza, los valores
    inequívocos del mismo cuadro; después los del resto del documento, incluido su texto. Una
    columna que se decide en inglés se convierte a número para que ningún control vuelva a leer
    la coma como decimal. Devuelve las columnas que quedaron ambiguas, para declararlas.
    """
    from services.perfilado import (
        evidencia_formato,
        formato_columna,
        numero_con_formato,
        partes_numero,
        preferencia_formato,
        votos_formato,
    )

    columnas = list(dict.fromkeys(str(k) for f in filas for k in f if k not in META_PDF))
    preferencia_doc = preferencia_formato(
        f.get(c) for f in filas for c in columnas if isinstance(f.get(c), str)
    )
    texto_doc = None
    cuadros: dict[tuple, list[dict]] = {}
    for f in filas:
        cuadros.setdefault((f.get("pagina_pdf"), f.get("tabla_pdf")), []).append(f)
    ambiguas: list[dict] = []
    for (pagina, _), registros in cuadros.items():
        preferencia = preferencia_formato(
            r.get(c) for r in registros for c in columnas if isinstance(r.get(c), str)
        ) or preferencia_doc
        for columna in columnas:
            textos = [r.get(columna) for r in registros if isinstance(r.get(columna), str) and r.get(columna).strip()]
            votos = votos_formato(textos)
            if not (votos["en"] or votos["ambiguo_coma"] or votos["ambiguo_punto"]):
                continue
            formato, origen = formato_columna(textos, preferencia)
            if origen == "predeterminado_ambiguo" and votos["ambiguo_coma"]:
                if texto_doc is None:
                    texto_doc = _tokens_numericos_texto_pdf(contenido, limite)
                formato = preferencia_formato(texto_doc) or "ambiguo"
            if formato == "ambiguo":
                ejemplo = next(t for t in textos if (p := partes_numero(t)) and evidencia_formato(p[1]) == "ambiguo_coma")
                ambiguas.append({"pagina": pagina, "columna": columna, "ejemplo": ejemplo.strip()})
                continue
            if formato != "en":
                continue
            for r in registros:
                valor = r.get(columna)
                if not isinstance(valor, str):
                    continue
                partes = partes_numero(valor)
                if partes and ("," in partes[1] or evidencia_formato(partes[1]) == "ambiguo_punto"):
                    convertido = numero_con_formato(valor, "en")
                    if convertido is not None:
                        r[columna] = convertido
    return ambiguas


def paginas_sin_texto_pdf(contenido: bytes, limite: int) -> list[int]:
    """Páginas con imagen y sin texto extraíble: un escaneo dentro de un PDF con texto.

    Una página en blanco (sin texto ni imágenes) no es contenido sin leer.
    """
    try:
        import pdfplumber

        sin_texto = []
        with pdfplumber.open(io.BytesIO(contenido)) as pdf:
            for numero, page in enumerate(pdf.pages[:limite], start=1):
                try:
                    texto = (page.extract_text() or "").strip()
                except Exception:  # noqa: BLE001 — una página ilegible tampoco se leyó
                    texto = ""
                if len(re.sub(r"\s+", "", texto)) < 10 and page.images:
                    sin_texto.append(numero)
        return sin_texto
    except Exception:  # noqa: BLE001
        return []


def _no_interpretables_pdf(filas: list[dict]) -> list[dict]:
    from services.perfilado import interpretar_columna, preferencia_formato

    columnas = list(dict.fromkeys(str(k) for f in filas for k in f if k not in META_PDF))
    preferencia = preferencia_formato(str(f.get(c) or "") for f in filas for c in columnas)
    salida = []
    for columna in columnas:
        valores = [f.get(columna) or None for f in filas]
        _, informe = interpretar_columna(valores, preferencia, minimo=0.8)
        if informe["numerica"] and informe["no_interpretables"]:
            salida.append({
                "columna": columna,
                "celdas": len(informe["no_interpretables"]),
                "ejemplos": [
                    f"página {filas[k].get('pagina_pdf')}: «{muestra_segura(columna, valores, valores[k])}»"
                    for k in informe["no_interpretables"][:5]
                ],
            })
    return salida


def aviso_truncado_pdf(filename, total, analizadas, limite, sin_cuadros: bool) -> str:
    if limite >= MAX_PAGINAS_PDF:
        sugerencia = f"el máximo es {MAX_PAGINAS_PDF}: dividí el PDF y cargá la parte con los cuadros"
    else:
        sugerencia = f"subí limite_paginas_pdf (hasta {MAX_PAGINAS_PDF})"
    if sin_cuadros:
        return (f"«{filename}»: se leyeron {analizadas} de {total} páginas sin encontrar cuadros; "
                f"si la tabla está más adelante, {sugerencia}.")
    return f"«{filename}»: se leyeron {analizadas} de {total} páginas; las siguientes no se revisaron ({sugerencia})."


def _leer_archivo(filename: str, contenido: bytes, limite_paginas_pdf: int | None = None):
    """(filas, lectura, cobertura_excel | None) de un archivo, eligiendo el lector por contenido."""
    tipo = tipo_por_contenido(filename, contenido)
    ext = _extension(filename)
    lectura: dict[str, Any] = {"archivo": filename, "extension": ext, "tipo_detectado": tipo,
                               "tipo_lectura": DESCRIPCION_LECTURA[tipo], "estado": "leido", "avisos": []}
    if tipo != ext and not (tipo == "csv" and ext == "csv"):
        lectura["avisos"].append(
            f"«{filename}»: la extensión es .{ext} pero el contenido es {DESCRIPCION_LECTURA[tipo]}; se leyó según el contenido."
        )
    if tipo in {"xlsx", "xls"}:
        from services.excel_cobertura import leer_libro

        if tipo == "xlsx":
            convertido = libro_transicional(contenido)
            if convertido is not contenido:
                contenido = convertido
                lectura["avisos"].append(f"«{filename}»: {AVISO_ESTRICTO}")
            validar_xlsx(filename, contenido)
            contenido, recortes = recortar_rango_inflado(filename, contenido)
            lectura["avisos"].extend(recortes)
        validar_tamano_libro(filename, contenido, tipo)
        filas, meta = leer_libro(contenido, filename)
        return filas, lectura, meta
    if tipo == "pdf":
        filas, info = _leer_pdf_con_lectura(contenido, filename, limite_paginas_pdf)
    else:
        filas, info = _leer_csv_con_lectura(contenido, filename)
    lectura["avisos"].extend(info.pop("avisos", []))
    lectura.update(info)
    lectura["tipo_lectura"] = DESCRIPCION_LECTURA[tipo] + (
        f" · {info['tipo_lectura'].replace('_', ' ')}" if tipo == "pdf" else ""
    )
    return filas, lectura, None


def parse_archivo(filename: str, contenido: bytes, limite_paginas_pdf: int | None = None) -> list[dict]:
    return _leer_archivo(filename, contenido, limite_paginas_pdf)[0]


# Un .xlsx es un ZIP: su tamaño descomprimido, no el del archivo subido, es lo que ocupa
# memoria cada vez que se lee (pandas, openpyxl, fórmulas, controles). Un libro armado
# para inflarse podría agotar la memoria del servicio antes de cualquier otro control.
MAX_XLSX_DESCOMPRIMIDO = 120 * 1024 * 1024  # el mayor libro real del corpus ocupa 1,3 MB
MAX_XLSX_RELACION = 200


def validar_xlsx(filename: str, contenido: bytes) -> None:
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
            total = sum(item.file_size for item in libro.infolist())
    except zipfile.BadZipFile as e:
        raise ArchivoNoSoportado(f"{filename}: no es un Excel .xlsx válido") from e
    relacion = total / max(len(contenido), 1)
    if total > MAX_XLSX_DESCOMPRIMIDO or (relacion > MAX_XLSX_RELACION and total > 40 * 1024 * 1024):
        raise ArchivoNoSoportado(
            f"{filename}: el libro ocupa {total // (1024 * 1024)} MB al abrirse; el máximo es "
            f"{MAX_XLSX_DESCOMPRIMIDO // (1024 * 1024)} MB. Dividilo en archivos más chicos o quitá hojas que no hagan falta."
        )


# Tamaño de un libro sin abrirlo: el XML de cada hoja se recorre con expresiones regulares (sin
# openpyxl ni pandas). La lectura completa crea un objeto por cada celda del rango usado de cada
# hoja (de la fila 1 a la última y de la columna A a la última, aunque estén vacías: basta una fila
# con formato hasta la columna XFD) y otro por cada celda con dato, en dos copias del libro (valores
# y fórmulas). Medido en 0.9.21 con libros reales de un ministerio: 16,6 millones de celdas de rango
# (planilla_oficial) o 1 millón con datos en 65 hojas (planilla_oficial) superan 3 GB; el servicio
# tiene 2 GB. Los mayores que entran: 2,7 millones de rango con 19.000 datos (planilla_oficial,
# pico 1,3 GB) y 537.000 datos en 44 hojas (planilla_oficial, pico 1,2 GB). Calibración en
# HISTORIA.md (0.9.21).
MAX_CELDAS_RANGO = 3_000_000
MAX_CELDAS_CON_DATOS = 600_000
_CELDA_XLSX = re.compile(rb'<(?:\w{1,8}:)?c\b[^>]*?\br=["\']\$?([A-Z]{1,3})\$?([0-9]{1,7})["\']')
_COMBINADA_XLSX = re.compile(rb'<(?:\w{1,8}:)?mergeCell\b[^>]*?\bref=["\'][A-Z]{1,3}[0-9]{1,7}:([A-Z]{1,3})([0-9]{1,7})["\']')
_ETIQUETA_CELDA_XLSX = re.compile(rb"<(?:\w{1,8}:)?c[\s>/]")
_DATO_XLSX = re.compile(rb"<(?:\w{1,8}:)?(?:v|is)[\s>]")
_DIMENSION_XLSX = re.compile(rb'<(?:\w{1,8}:)?dimension\b[^>]*?\bref=["\'](?:[A-Z]{1,3}[0-9]{1,7}:)?([A-Z]{1,3})([0-9]{1,7})["\']')
_HOJA_XLSX = re.compile(rb"<(?:\w{1,8}:)?sheet\b[^>]*>")
_REL_XLSX = re.compile(rb"<(?:\w{1,8}:)?Relationship\b[^>]*>")
_NOMBRE_ATRIBUTO = re.compile(rb'\bname="([^"]*)"')
_ID_ATRIBUTO = re.compile(rb'\s(?:\w{1,40}:)id="([^"]+)"')
_REL_ID = re.compile(rb'\bId="([^"]+)"')
_REL_DESTINO = re.compile(rb'\bTarget="([^"]+)"')


def _columna_numero(letras: bytes) -> int:
    n = 0
    for ch in letras:
        n = n * 26 + ch - 64
    return n


def _columna_letras(n: int) -> str:
    letras = ""
    while n:
        n, r = divmod(n - 1, 26)
        letras = chr(65 + r) + letras
    return letras or "A"


def _nombres_hojas_xlsx(libro) -> dict[str, str]:
    """{ruta del XML de la hoja: nombre visible}; sin el índice del libro, la ruta misma."""
    import html

    try:
        rels = {}
        for etiqueta in _REL_XLSX.findall(libro.read("xl/_rels/workbook.xml.rels")):
            ident, destino = _REL_ID.search(etiqueta), _REL_DESTINO.search(etiqueta)
            if ident and destino:
                ruta = destino.group(1).decode("utf-8", "replace").lstrip("/")
                rels[ident.group(1)] = ruta if ruta.startswith("xl/") else "xl/" + ruta
        nombres = {}
        for etiqueta in _HOJA_XLSX.findall(libro.read("xl/workbook.xml")):
            nombre, ident = _NOMBRE_ATRIBUTO.search(etiqueta), _ID_ATRIBUTO.search(etiqueta)
            if nombre and ident and ident.group(1) in rels:
                nombres[rels[ident.group(1)]] = html.unescape(nombre.group(1).decode("utf-8", "replace"))
        return nombres
    except Exception:  # noqa: BLE001 — sin nombres, el aviso cita la ruta interna de la hoja
        return {}


def medir_libro(contenido: bytes, tipo: str) -> list[dict]:
    """Por hoja: filas y columnas del rango usado y celdas con dato, sin cargar el libro."""
    hojas = []
    if tipo == "xlsx":
        import zipfile

        with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
            nombres = _nombres_hojas_xlsx(libro)
            for item in libro.infolist():
                if not (item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml")):
                    continue
                xml = libro.read(item)
                filas = columnas = 0
                # Las celdas escritas y las combinadas fijan el rango de la lectura completa; la
                # dimensión declarada, el de la lectura liviana (que rellena cada fila hasta ese ancho).
                for patron in (_CELDA_XLSX, _COMBINADA_XLSX, _DIMENSION_XLSX):
                    for m in patron.finditer(xml):
                        columnas = max(columnas, _columna_numero(m.group(1)))
                        filas = max(filas, int(m.group(2)))
                # Celdas sin referencia («<c>» sin r=): la lectura las ubica una tras otra; el rango
                # no puede ser menor que la cantidad de celdas escritas.
                hojas.append({"hoja": nombres.get(item.filename, item.filename), "filas": filas, "columnas": columnas,
                              "celdas": sum(1 for _ in _ETIQUETA_CELDA_XLSX.finditer(xml)),
                              "con_datos": sum(1 for _ in _DATO_XLSX.finditer(xml))})
                del xml
    elif tipo == "xls":
        import xlrd

        libro = xlrd.open_workbook(file_contents=contenido, on_demand=True)
        try:
            for i in range(libro.nsheets):
                hoja = libro.sheet_by_index(i)
                vacias = (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK)
                con_datos = sum(1 for r in range(hoja.nrows) for t in hoja.row_types(r) if t not in vacias)
                hojas.append({"hoja": hoja.name, "filas": hoja.nrows, "columnas": hoja.ncols, "con_datos": con_datos})
                libro.unload_sheet(i)
        finally:
            libro.release_resources()
    return hojas


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def validar_tamano_libro(filename: str, contenido: bytes, tipo: str) -> None:
    """Rechaza antes de leerlo un libro cuya lectura agotaría la memoria del servicio."""
    try:
        hojas = medir_libro(contenido, tipo)
    except Exception:  # noqa: BLE001 — si no se puede medir, la lectura normal declara el daño
        return
    con_datos = sum(h["con_datos"] for h in hojas)
    if con_datos > MAX_CELDAS_CON_DATOS:
        raise ArchivoNoSoportado(
            f"{filename}: el libro tiene {_miles(con_datos)} celdas con datos en {contar(len(hojas), 'hoja')}; "
            f"el máximo es {_miles(MAX_CELDAS_CON_DATOS)}. Dividilo en archivos más chicos o quitá hojas que no hagan falta."
        )
    for h in hojas:
        h["rango"] = max(h["filas"] * h["columnas"], h.get("celdas", 0))
    rango = sum(h["rango"] for h in hojas)
    if rango > MAX_CELDAS_RANGO:
        mayor = max(hojas, key=lambda h: h["rango"])
        raise ArchivoNoSoportado(
            f"{filename}: el libro abarca {_miles(rango)} celdas contando las vacías dentro del rango usado de cada hoja; "
            f"el máximo es {_miles(MAX_CELDAS_RANGO)}. La hoja «{mayor['hoja']}» llega hasta la fila {_miles(mayor['filas'])} "
            f"y la columna {_columna_letras(mayor['columnas'])} ({_miles(mayor['rango'])} celdas): "
            "borrá las filas y columnas sobrantes (suelen tener sólo formato), dividilo en archivos más chicos o quitá "
            "hojas que no hagan falta."
        )


# Libros con el rango inflado: una fila con formato hasta la columna XFD, filas con formato hasta el final de la
# hoja o una celda suelta lejos del cuadro hacen que un libro con pocos datos se rechace por el rango usado. Sólo
# en ese caso, antes de rechazarlo, las hojas se recortan al bloque con datos y la lectura dice qué se recortó.
# Primero sólo el formato; las celdas sueltas con datos se dejan fuera únicamente si con eso no alcanza.
SALTO_COLUMNAS = 100  # columnas vacías seguidas que separan una celda suelta del cuadro
SALTO_FILAS = 1000
MAX_CELDAS_SUELTAS = 20  # más celdas con datos lejos del cuadro ya son otro cuadro: no se descartan
MIN_CELDAS_RECORTE = 100_000  # una hoja cuyo rango baja menos que esto se deja como está
# Celdas escritas («<c>») que se recorren para recortar: el recorte guarda las posiciones de las que tienen dato y
# reescribe el XML, así que un libro con más que esto se rechaza como antes, sin recortarlo.
MAX_CELDAS_RECORTE = 1_500_000
_CELDA_COMPLETA_XLSX = re.compile(
    rb'<(?:\w{1,8}:)?c\b[^>]*?\br=["\']\$?([A-Z]{1,3})\$?([0-9]{1,7})["\'][^>]*?(?:/>|>.*?</(?:\w{1,8}:)?c>)', re.S)
_DATO_CELDA_XLSX = re.compile(rb"<(?:\w{1,8}:)?(?:v|is|f)[\s>/]")
_FILA_COMPLETA_XLSX = re.compile(
    rb'<(?:\w{1,8}:)?row\b[^>]*?\br=["\']([0-9]{1,7})["\'][^>]*?(?:/>|>.*?</(?:\w{1,8}:)?row>)', re.S)
_COMBINADA_COMPLETA_XLSX = re.compile(
    rb'(<(?:\w{1,8}:)?mergeCell\b[^>]*?\bref=["\'])([A-Z]{1,3})([0-9]{1,7}):([A-Z]{1,3})([0-9]{1,7})(["\'][^>]*?/>)')
_CANTIDAD_COMBINADAS_XLSX = re.compile(rb'(<(?:\w{1,8}:)?mergeCells\b[^>]*?\bcount=["\'])[0-9]+')
# Con etiqueta de cierre o sin ella, y de una celda o de un rango: la lectura crea cada celda del vínculo.
_HIPERVINCULO_COMPLETO_XLSX = re.compile(
    rb'<(?:\w{1,8}:)?hyperlink\b[^>]*?\bref=["\']([A-Z]{1,3})([0-9]{1,7})(?::([A-Z]{1,3})([0-9]{1,7}))?["\'][^>]*?'
    rb'(?:/>|>.*?</(?:\w{1,8}:)?hyperlink>)', re.S)
_DIMENSION_COMPLETA_XLSX = re.compile(rb'(<(?:\w{1,8}:)?dimension\b[^>]*?\bref=["\'])[^"\']*(["\'])')
_COMENTARIO_XLSX = re.compile(rb'<(?:\w{1,8}:)?comment\b[^>]*?\bref=["\']([A-Z]{1,3})([0-9]{1,7})')
_REL_TIPO = re.compile(rb'\bType="([^"]+)"')


def _hasta_el_salto(valores, salto: int) -> int:
    """Último valor del bloque que empieza en el menor; corta en el primer hueco mayor que `salto` y que el bloque."""
    usados = sorted(set(valores))
    hasta = usados[0]
    for v in usados[1:]:
        if v - hasta > max(salto, hasta):
            break
        hasta = v
    return hasta


def _comentarios_por_hoja(libro) -> dict[str, list[tuple[int, int]]]:
    """{ruta del XML de la hoja: [(columna, fila)] de sus comentarios}: la lectura completa crea esas celdas."""
    import posixpath

    salida = {}
    for item in libro.infolist():
        m = re.match(r"xl/worksheets/_rels/([^/]+\.xml)\.rels$", item.filename)
        if not m:
            continue
        for etiqueta in _REL_XLSX.findall(libro.read(item)):
            tipo, destino = _REL_TIPO.search(etiqueta), _REL_DESTINO.search(etiqueta)
            if not (tipo and destino and tipo.group(1).endswith(b"/comments")):
                continue
            ruta = destino.group(1).decode("utf-8", "replace")
            ruta = ruta.lstrip("/") if ruta.startswith("/") else posixpath.normpath(posixpath.join("xl/worksheets", ruta))
            try:
                xml = libro.read(ruta)
            except KeyError:
                continue
            salida.setdefault(f"xl/worksheets/{m.group(1)}", []).extend(
                (_columna_numero(c.group(1)), int(c.group(2))) for c in _COMENTARIO_XLSX.finditer(xml))
    return salida


def _medir_hoja(xml: bytes, comentarios) -> dict:
    """Rango de la hoja (como lo cuenta validar_tamano_libro) y los dos bloques posibles: con todos sus datos y sin
    las celdas sueltas. Sin bloques si no se puede recortar por posición (celdas sin referencia «r», que la lectura
    ubica una tras otra). Sólo se guardan las posiciones de las celdas con dato, no las demás."""
    antes_f = antes_c = 0
    for patron in (_CELDA_XLSX, _COMBINADA_XLSX, _DIMENSION_XLSX):
        for m in patron.finditer(xml):
            antes_c, antes_f = max(antes_c, _columna_numero(m.group(1))), max(antes_f, int(m.group(2)))
    escritas = sum(1 for _ in _ETIQUETA_CELDA_XLSX.finditer(xml))
    hoja = dict(antes=max(antes_f * antes_c, escritas), alcance=(antes_f, antes_c), completo=None, recorte=None,
                sueltas=[])
    con_referencia, datos = 0, []
    for m in _CELDA_COMPLETA_XLSX.finditer(xml):
        con_referencia += 1
        if _DATO_CELDA_XLSX.search(m.group(0)):
            datos.append((_columna_numero(m.group(1)), int(m.group(2))))
    if con_referencia != escritas:
        return hoja
    fijas = datos + list(comentarios)
    hoja["completo"] = (max(f for _, f in fijas), max(c for c, _ in fijas)) if fijas else (1, 1)
    if datos:
        columnas = _hasta_el_salto([c for c, _ in datos], SALTO_COLUMNAS)
        filas = _hasta_el_salto([f for _, f in datos], SALTO_FILAS)
        # Cada borde se mide con las celdas que quedan dentro del otro: una suelta a la derecha no estira las filas.
        columnas, filas = (_hasta_el_salto([c for c, f in datos if f <= filas], SALTO_COLUMNAS),
                           _hasta_el_salto([f for c, f in datos if c <= columnas], SALTO_FILAS))
        sueltas = sorted((f, c) for c, f in datos if c > columnas or f > filas)
        # Un comentario fuera del bloque se volvería a crear al leer: esa hoja no se recorta sin sus sueltas.
        if 0 < len(sueltas) <= MAX_CELDAS_SUELTAS and all(c <= columnas and f <= filas for c, f in comentarios):
            hoja.update(recorte=(filas, columnas), sueltas=sueltas)
    return hoja


def _reescribir_hoja(xml: bytes, filas: int, columnas: int) -> tuple[bytes, int]:
    """La hoja sin lo que queda fuera de A1:<columnas><filas>, y cuántas celdas sin dato se quitaron."""
    sin_dato = 0

    def fuera(c, f):
        return _columna_numero(c) > columnas or int(f) > filas

    def celda(m):
        nonlocal sin_dato
        if not fuera(m.group(1), m.group(2)):
            return m.group(0)
        sin_dato += not _DATO_CELDA_XLSX.search(m.group(0))
        return b""

    def combinada(m):
        c1, f1 = _columna_numero(m.group(2)), int(m.group(3))
        c2, f2 = min(_columna_numero(m.group(4)), columnas), min(int(m.group(5)), filas)
        if c1 > columnas or f1 > filas or (c1, f1) == (c2, f2):
            return b""
        return m.group(1) + m.group(2) + m.group(3) + f":{_columna_letras(c2)}{f2}".encode() + m.group(6)

    def vinculo(m):
        lejos = fuera(m.group(1), m.group(2)) or (m.group(3) is not None and fuera(m.group(3), m.group(4)))
        return b"" if lejos else m.group(0)

    nuevo = _CELDA_COMPLETA_XLSX.sub(celda, xml)
    nuevo = _FILA_COMPLETA_XLSX.sub(lambda m: b"" if int(m.group(1)) > filas else m.group(0), nuevo)
    nuevo = _COMBINADA_COMPLETA_XLSX.sub(combinada, nuevo)
    cantidad = str(len(_COMBINADA_COMPLETA_XLSX.findall(nuevo))).encode()
    nuevo = _CANTIDAD_COMBINADAS_XLSX.sub(lambda m: m.group(1) + cantidad, nuevo)
    nuevo = _HIPERVINCULO_COMPLETO_XLSX.sub(vinculo, nuevo)
    nuevo = _DIMENSION_COMPLETA_XLSX.sub(
        lambda m: m.group(1) + f"A1:{_columna_letras(columnas)}{filas}".encode() + m.group(2), nuevo)
    return nuevo, sin_dato


def _aviso_recorte(archivo: str, hoja: str, antes, despues, sueltas, con_formato: bool) -> str:
    texto = (f"«{archivo}», hoja «{hoja}»: el rango usado llegaba hasta la fila {_miles(antes[0])} y la columna "
             f"{_columna_letras(antes[1])}; se leyó el bloque con datos, hasta la celda "
             f"{_columna_letras(despues[1])}{despues[0]}.")
    if sueltas:
        lugares = ", ".join(f"{_columna_letras(c)}{f}" for f, c in sueltas[:5]) + (" y otras" if len(sueltas) > 5 else "")
        texto += (f" Quedó fuera de la lectura 1 celda con datos separada del cuadro por columnas o filas vacías: {lugares}."
                  if len(sueltas) == 1 else
                  f" Quedaron fuera de la lectura {len(sueltas)} celdas con datos separadas del cuadro por columnas o filas "
                  f"vacías: {lugares}.")
    if con_formato:
        texto += " Fuera del bloque había celdas sin datos (sólo formato)."
    return texto


def recortar_rango_inflado(filename: str, contenido: bytes) -> tuple[bytes, list[str]]:
    """El .xlsx recortado al bloque con datos de sus hojas y los avisos, si sólo así entra en el rango máximo.

    Un libro que entra, que se rechazaría por otro motivo (tamaño al abrirse, celdas con datos, celdas escritas de
    más para recorrerlas) o que no alcanza a entrar ni recortado se devuelve tal cual (el mismo objeto), y el control
    de tamaño decide. Primero se quitan sólo las celdas sin datos; si no alcanza, también hasta MAX_CELDAS_SUELTAS
    celdas con datos separadas del cuadro. Las combinaciones se recortan al bloque y se quitan los vínculos que salen.
    """
    import zipfile

    if contenido[:4] != FIRMA_ZIP:
        return contenido, []
    try:
        validar_xlsx(filename, contenido)
        hojas = medir_libro(contenido, "xlsx")
        if (sum(max(h["filas"] * h["columnas"], h.get("celdas", 0)) for h in hojas) <= MAX_CELDAS_RANGO
                or sum(h["con_datos"] for h in hojas) > MAX_CELDAS_CON_DATOS
                or sum(h.get("celdas", 0) for h in hojas) > MAX_CELDAS_RECORTE):
            return contenido, []
        with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
            nombres = _nombres_hojas_xlsx(libro)
            comentarios = _comentarios_por_hoja(libro)
            medidas = {}
            for item in libro.infolist():
                if item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                    medidas[item.filename] = _medir_hoja(libro.read(item), comentarios.get(item.filename, ()))

            def area(bloque):
                return bloque[0] * bloque[1]

            # Primero sólo el formato: cada hoja a su bloque con todos los datos, si así baja lo suficiente.
            elegidos = {r: m["completo"] for r, m in medidas.items()
                        if m["completo"] and m["antes"] - area(m["completo"]) >= MIN_CELDAS_RECORTE}

            def actual(r):
                return area(elegidos[r]) if r in elegidos else medidas[r]["antes"]

            def total():
                return sum(actual(r) for r in medidas)

            # Si no alcanza, las celdas sueltas quedan fuera de a una hoja, la que más baja primero, hasta entrar.
            for r in sorted((r for r, m in medidas.items() if m["recorte"]),
                            key=lambda r: actual(r) - area(medidas[r]["recorte"]), reverse=True):
                if total() <= MAX_CELDAS_RANGO:
                    break
                elegidos[r] = medidas[r]["recorte"]
            if not elegidos or total() > MAX_CELDAS_RANGO:
                return contenido, []
            nuevas, avisos = {}, []
            for ruta, (filas, columnas) in elegidos.items():
                m = medidas[ruta]
                nuevas[ruta], sin_dato = _reescribir_hoja(libro.read(ruta), filas, columnas)
                sueltas = m["sueltas"] if (filas, columnas) == m["recorte"] else []
                avisos.append(_aviso_recorte(filename, nombres.get(ruta, ruta), m["alcance"], (filas, columnas), sueltas,
                                             bool(sin_dato)))
            salida = io.BytesIO()
            with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as nuevo:
                for item in libro.infolist():
                    nuevo.writestr(item, nuevas[item.filename] if item.filename in nuevas else libro.read(item))
        return salida.getvalue(), avisos
    except Exception:  # noqa: BLE001 — sin recorte, el control de tamaño decide sobre el libro original
        return contenido, []

MENSAJE_ARCHIVO_DANADO = (
    "no se pudo leer: puede estar dañado o tener un formato que no reconocemos. "
    "Probá guardarlo de nuevo como .xlsx o .csv"
)


def motivo_archivo_danado(filename: str, contenido: bytes, exc: Exception) -> str:
    """Motivo legible del fallo de lectura de un archivo, con su nombre y el tipo de daño."""
    try:
        tipo = tipo_por_contenido(filename, contenido)
    except ArchivoNoSoportado:
        tipo = _extension(filename)
    detalle = re.sub(r"\s+", " ", str(exc) or type(exc).__name__).strip()[:120]
    if tipo == "pdf":
        return (f"'{filename}': el PDF no se pudo abrir; parece dañado o incompleto ({detalle}). "
                "Probá descargarlo o exportarlo de nuevo")
    return f"'{filename}': {MENSAJE_ARCHIVO_DANADO} ({detalle})"


def parse_archivos_con_lectura(archivos, limite_paginas_pdf=None):
    """(datos, cobertura, lectura): datos de todos los archivos, la cobertura por cuadro y la
    lectura de cada archivo (tipo de lectura, avisos y fallos).

    Cada archivo es un bloque propio: con dos o más archivos la cobertura los separa para que
    sus filas no se mezclen. Si un archivo no se puede leer, se procesa el resto y el fallo
    queda declarado con el nombre del archivo; sólo si ninguno se lee se rechaza la carga.
    """
    datos, hojas, bloques, lectura = [], [], [], []
    errores = []
    for filename, contenido in archivos:
        try:
            nuevos, info, meta = _leer_archivo(filename, contenido, limite_paginas_pdf)
        except Exception as exc:  # noqa: BLE001 — se declara por archivo y sigue con el resto
            errores.append(exc)
            motivo = str(exc) if isinstance(exc, ArchivoNoSoportado) else motivo_archivo_danado(filename, contenido, exc)
            lectura.append({"archivo": filename, "extension": _extension(filename), "estado": "fallido",
                            "motivo": motivo, "filas": 0,
                            "avisos": [f"«{filename}» no se procesó: {motivo}"]})
            continue
        offset = len(datos)
        if meta is not None:
            for b in meta["bloques"]:
                b.update(inicio=b["inicio"] + offset, fin=b["fin"] + offset, bloque=len(bloques) + 1)
                bloques.append(b)
            hojas.extend(meta["hojas"])
            info["hojas"] = len(meta["hojas"])
            for h in meta["hojas"]:
                info["avisos"].extend(f"«{filename}» · {h['hoja']}: {a}" for a in h.get("avisos_lectura", []))
        else:
            for fila in nuevos:
                # Las filas de CSV también dicen de qué archivo salen: con varios archivos no se mezclan.
                fila.setdefault("archivo_origen", filename)
            bloques.append({"archivo": filename, "hoja": None, "bloque": len(bloques) + 1,
                            "inicio": offset, "fin": offset + len(nuevos), "filas": [], "columnas": {}})
        info["filas"] = len(nuevos)
        if not nuevos:
            info["estado"] = "sin_datos"
        lectura.append(info)
        datos.extend(nuevos)
    if errores and len(errores) == len(archivos):
        # El rechazo siempre nombra el archivo y el motivo, nunca «alguno de los archivos».
        if len(errores) == 1:
            raise ArchivoNoSoportado(lectura[0]["motivo"]) from errores[0]
        raise ArchivoNoSoportado("Ningún archivo se pudo leer: " + " | ".join(i["motivo"] for i in lectura))
    if hojas or len(archivos) > 1:
        cobertura = {"version": 1, "hojas": hojas, "bloques": bloques, "archivos": lectura}
    else:
        cobertura = {}
    return datos, cobertura, lectura


def motivo_sin_datos(lectura, cobertura) -> str:
    """Por qué no quedó ninguna fila con datos, archivo por archivo y con el motivo exacto."""
    hojas = (cobertura or {}).get("hojas") or []
    partes = []
    for info in lectura or []:
        nombre = info.get("archivo")
        if info.get("estado") == "fallido":
            partes.append(f"«{nombre}»: {info.get('motivo') or 'no se pudo leer'}")
            continue
        propias = [h for h in hojas if h.get("archivo") == nombre]
        if propias:
            motivos = []
            for h in propias:
                fsv = h.get("formulas_sin_valor") or {}
                if fsv.get("celdas"):
                    ejemplos = ", ".join((fsv.get("ejemplos") or [])[:5])
                    motivos.append(
                        f"hoja «{h['hoja']}»: sus valores son fórmulas sin resultado guardado "
                        f"({contar(fsv['celdas'], 'celda', 'celdas')}{', p. ej. ' + ejemplos if ejemplos else ''}) que no se pudieron "
                        "calcular; abrí el archivo en la planilla, guardalo y volvé a cargarlo"
                    )
                elif h.get("motivo"):
                    motivos.append(f"hoja «{h['hoja']}»: {h['motivo'][0].lower() + h['motivo'][1:]}")
            partes.append(f"«{nombre}»: " + ("; ".join(motivos) if motivos else "sin hojas con filas de datos"))
            continue
        partes.append(f"«{nombre}»: {info.get('motivo') or 'no se encontraron filas con datos después del encabezado'}")
    return "; ".join(partes) or "no se encontraron filas con datos"


def parse_archivos_con_cobertura(archivos, limite_paginas_pdf=None):
    datos, cobertura, _ = parse_archivos_con_lectura(archivos, limite_paginas_pdf)
    return datos, cobertura


def avisos_lectura(lectura) -> list[str]:
    return [a for info in lectura or [] for a in info.get("avisos", [])]


def parse_archivos(archivos, limite_paginas_pdf=None):
    return parse_archivos_con_cobertura(archivos, limite_paginas_pdf)[0]


def origen_excel_verificado(archivos, datos):
    """Compatibilidad para consumidores de una tabla única; nunca inventa una hoja global."""
    originales, cobertura = parse_archivos_con_cobertura(archivos)
    bloques = cobertura.get('bloques', [])
    if len(bloques) != 1 or len(originales) != len(datos):
        return {}
    if any(any(k not in original or original[k] != v for k,v in fila.items()) for original,fila in zip(originales,datos)):
        return {}
    b=bloques[0]
    return {'hoja':b['hoja'], 'filas':b['filas'], 'columnas':{c:v for c,v in b['columnas'].items() if datos and c in datos[0]}}
