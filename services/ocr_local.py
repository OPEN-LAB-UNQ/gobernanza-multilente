"""Lectura local transitoria para la revisión de lectura. Ningún resultado entra al motor sin revisión.

Los PDF con texto se leen de su texto (con la extracción de tablas de services.carga_archivos);
el OCR local (tesseract) se usa sólo para páginas sin texto y para imágenes. Nada sale del servidor.
"""

import base64
import csv
import hashlib
import io
import logging
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

from services import carga_archivos

MAX_BYTES = 15 * 1024 * 1024
MAX_PAGES = 5  # páginas leídas con OCR (escaneadas o imágenes) por lectura
MAX_PAGINAS_TEXTO = 60  # páginas de un PDF con texto que entran en el índice
MAX_PAGINAS_DETALLE = 10  # páginas que se devuelven con imagen y tablas por lectura
LECTURA_LEGIBLE = {"texto_pdf": "texto del PDF", "ocr_local": "OCR: revisá números y signos"}
MAX_PIXELS = 24_000_000
LOCK = threading.BoundedSemaphore(1)


class OCRNoDisponible(ValueError):
    pass


def reconocer(imagen):
    with tempfile.TemporaryDirectory(prefix="gobernanza-ocr-") as tmp:
        path = Path(tmp) / "pagina.png"
        imagen.save(path)
        try:
            result = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", "spa+eng", "--psm", "6", "tsv"],
                capture_output=True,
                timeout=25,
                check=True,
                env={"PATH": "/usr/bin:/bin", "OMP_THREAD_LIMIT": "1"},
            )
        except FileNotFoundError as exc:
            raise OCRNoDisponible("OCR local no instalado.") from exc
        except subprocess.TimeoutExpired as exc:
            raise OCRNoDisponible("Se agotó el tiempo de lectura de esta página.") from exc
        except subprocess.CalledProcessError as exc:
            raise OCRNoDisponible("El motor OCR no pudo leer la página. Verificá los idiomas instalados.") from exc
    groups = {}
    for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8", errors="replace")), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        key = tuple(row[k] for k in ("block_num", "par_num", "line_num"))
        word = {
            "texto": row["text"],
            "confianza": float(row["conf"]),
            "caja": [int(row[k]) for k in ("left", "top", "width", "height")],
        }
        groups.setdefault(key, []).append(word)
    lines = []
    for words in groups.values():
        words.sort(key=lambda x: x["caja"][0])
        parts = []
        prev = None
        for word in words:
            x, y, w, h = word["caja"]
            if prev:
                gap = x - (prev["caja"][0] + prev["caja"][2])
                parts.append("\t" if gap > max(18, h * 1.3) else " ")
            parts.append(word["texto"])
            prev = word
        x = min(w["caja"][0] for w in words)
        y = min(w["caja"][1] for w in words)
        right = max(w["caja"][0] + w["caja"][2] for w in words)
        bottom = max(w["caja"][1] + w["caja"][3] for w in words)
        lines.append({"texto": "".join(parts), "caja": [x, y, right - x, bottom - y], "palabras": words})
    return lines


def _preview(imagen):
    out = io.BytesIO()
    imagen.save(out, format="JPEG", quality=75)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def _pagina(imagen, numero, texto_nativo=None):
    imagen = ImageOps.exif_transpose(imagen).convert("RGBA")
    fondo = Image.new("RGBA", imagen.size, "white")
    imagen = Image.alpha_composite(fondo, imagen).convert("RGB")
    imagen.thumbnail((1800, 2400))
    truncado = texto_nativo is not None and len(texto_nativo) > 30000
    if texto_nativo is not None:
        lines = []
        text = texto_nativo[:30000]
        method = "texto_pdf"
    else:
        lines = reconocer(imagen)
        text = "\n".join(x["texto"] for x in lines)
        method = "ocr_local"
    dudas = [w for line in lines for w in line["palabras"] if w["confianza"] < 80]
    return {
        "pagina": numero,
        "metodo": method,
        "estado": "para_revisar" if text.strip() else "sin_texto",
        "texto": text,
        "texto_truncado": truncado,
        "lineas": lines,
        "dudas": len(dudas),
        "ancho": imagen.width,
        "alto": imagen.height,
        "imagen": _preview(imagen),
        "advertencia": (
            "Texto recortado a 30000 caracteres; queda contenido fuera de esta lectura. " if truncado else ""
        )
        + "La confianza del OCR no garantiza exactitud. Revisá números, signos, unidades y columnas.",
    }


# --- Tablas para revisar ---------------------------------------------------------------------
# La herramienta propone una tabla por cuadro: encabezado + filas tal como se leyeron (texto, sin
# convertir números) y las celdas que conviene mirar contra el original. Nada de esto se analiza
# hasta que la persona confirma la tabla.

PERIODO_RE = re.compile(
    r"^(?:(?:19|20)\d{2}(?:[-/](?:0?[1-9]|1[0-2]))?|(?:0?[1-9]|1[0-2])[-/](?:19|20)\d{2}|(?:19|20)\d{2}\s*\*+)$"
)
ROTULOS_PERIODO = {"ano", "anio", "anos", "periodo", "mes", "fecha", "year", "trimestre", "semestre", "ejercicio"}
AMBIGUO_RE = re.compile(r"^[-+(]?\d{1,3}[.,]\d{3}\)?%?$")
NUMERO_RE = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
ROTULO_CUADRO_RE = re.compile(r"^\s*(TABLA|CUADRO|TABLE|Tabla|Cuadro|Table)\s*\d.*$", re.M)


def _sin_acentos(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c)).strip()


def _limpio(celda):
    return " ".join(str(celda or "").replace("\n", " ").split())


def _token_numerico(texto):
    t = str(texto or "").strip().replace(" ", "").replace(" ", "").replace("$", "")
    if t.endswith("%"):
        t = t[:-1]
    negativo = t.startswith("(") and t.endswith(")")
    if negativo:
        t = t[1:-1]
    return t, negativo


def numero(texto, formato):
    """Valor numérico de una celda según el formato de la tabla ("es": 1.234,56; "en": 1,234.56).

    Devuelve el número como texto normalizado («-1234.56») o None si la celda no es un número.
    """
    t, negativo = _token_numerico(texto)
    if not t or not re.fullmatch(r"[-+]?[\d.,]+", t) or not re.search(r"\d", t):
        return None
    if formato == "en":
        if not re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?", t):
            return None
        t = t.replace(",", "")
    else:
        if not re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})*(?:,\d+)?|[-+]?\d+(?:,\d+)?", t):
            return None
        t = t.replace(".", "").replace(",", ".")
    if not NUMERO_RE.match(t):
        return None
    if negativo and not t.startswith("-"):
        t = "-" + t.lstrip("+")
    return t


def detectar_formato(filas):
    """"es", "en" o "ambiguo" según las celdas que deciden el separador decimal."""
    es = en = 0
    for fila in filas:
        for celda in fila:
            t, _ = _token_numerico(celda)
            if re.fullmatch(r"-?\d+,\d{1,2}|-?\d{1,3}(?:\.\d{3})+,\d+|-?\d{1,3}(?:\.\d{3}){2,}|-?\d+,\d{4,}", t):
                es += 1
            elif re.fullmatch(r"-?\d+\.\d{1,2}|-?\d{1,3}(?:,\d{3})+\.\d+|-?\d{1,3}(?:,\d{3}){2,}|-?\d+\.\d{4,}", t):
                en += 1
    if es > en:
        return "es"
    if en > es:
        return "en"
    return "ambiguo"


def _columna_periodo(encabezado, filas, j):
    rotulo = _sin_acentos(encabezado[j] if j < len(encabezado) else "")
    valores = [_limpio(f[j]) for f in filas if j < len(f) and _limpio(f[j])]
    if rotulo in ROTULOS_PERIODO:
        return True
    return len(valores) >= 2 and sum(bool(PERIODO_RE.match(v)) for v in valores) >= 0.8 * len(valores)


def columnas_periodo(encabezado, filas):
    ancho = max([len(encabezado)] + [len(f) for f in filas]) if filas or encabezado else 0
    return [j for j in range(ancho) if _columna_periodo(encabezado, filas, j)]


def _es_total(texto):
    return _sin_acentos(texto).startswith("total")


def _decimales(t):
    return len(t.split(".")[1]) if "." in t else 0


def celdas_dudosas(encabezado, filas, formato=None):
    """Celdas que conviene revisar contra el original: [{fila, columna, motivo}] (fila -1 = encabezado)."""
    formato = formato or detectar_formato(filas)
    dudosas = []
    vistas = set()

    def marcar(i, j, motivo):
        if (i, j) not in vistas:
            vistas.add((i, j))
            dudosas.append({"fila": i, "columna": j, "motivo": motivo})

    ancho = max([len(encabezado)] + [len(f) for f in filas]) if (filas or encabezado) else 0
    rotulos = [_limpio(encabezado[j]) if j < len(encabezado) else "" for j in range(ancho)]
    for j, rotulo in enumerate(rotulos):
        if not rotulo:
            marcar(-1, j, "Columna sin rótulo: escribí qué contiene.")
        elif rotulos.count(rotulo) > 1:
            marcar(-1, j, "Rótulo repetido: aclaralo para distinguir esta columna.")
    periodos = set(columnas_periodo(rotulos, filas))
    for j in sorted(periodos):
        llenas = [i for i, f in enumerate(filas) if j < len(f) and _limpio(f[j])]
        if not llenas:
            continue
        for i, f in enumerate(filas):
            if not (j < len(f) and _limpio(f[j])):
                marcar(i, j, "Período vacío: probablemente una celda combinada. Usá «Completar hacia abajo» en esta columna.")
    for i, f in enumerate(filas):
        for j, celda in enumerate(f):
            texto = _limpio(celda)
            if not texto or j in periodos:
                continue
            if carga_archivos.celda_con_varios_numeros(texto):
                marcar(i, j, "Hay más de un número en la celda: separalos en sus columnas.")
            elif formato == "ambiguo" and AMBIGUO_RE.match(texto.replace(" ", "")):
                marcar(i, j, f"Formato numérico ambiguo («{texto}»): elegí el formato de la tabla (1.234,56 o 1,234.56).")
    # Totales: una fila «Total» debe sumar las filas de su bloque y una columna «Total», las
    # columnas de importes de su fila. Los porcentajes y los períodos no entran en la suma.
    valores = [[numero(c, "en" if formato == "en" else "es") for c in f] for f in filas]
    sumables = [
        j for j in range(ancho)
        if j not in periodos and "%" not in rotulos[j] and "porc" not in _sin_acentos(rotulos[j])
        and not _es_total(rotulos[j]) and sum(1 for v in valores if j < len(v) and v[j] is not None) >= 2
    ]

    def tolerancia(partes, total):
        unidad = 10 ** -max([_decimales(p) for p in partes + [total]] or [0])
        return max(0.5 * unidad * (len(partes) + 1), abs(float(total)) * 0.001)

    rotulos_fila = [next((_limpio(c) for j, c in enumerate(f) if j not in periodos and _limpio(c)
                          and numero(c, "es") is None and numero(c, "en") is None), "") for f in filas]
    codigos = codigos_jerarquia(rotulos_fila)
    # Jerarquía por código: cada código padre es la suma de sus hijos inmediatos. De abajo hacia arriba:
    # si una subcuenta no cierra, el padre se compara con lo que suman las suyas y no se marca dos veces.
    # Sin desgloses parciales («de las cuales») y sólo en columnas donde algún padre cierra: un
    # rendimiento o un haber medio no suman aunque su rótulo no lo diga.
    padres = {i: hs for i, hs in _padres_por_codigo(codigos).items()
              if not any(DESGLOSE.search(_sin_acentos(rotulos_fila[k])) for k in hs)}

    def cierra(i, j):
        total = valores[i][j] if j < len(valores[i]) else None
        partes = [valores[k][j] if j < len(valores[k]) else None for k in padres[i]]
        return (total is not None and all(p is not None for p in partes)
                and abs(sum(float(p) for p in partes) - float(total)) <= tolerancia(partes, total))

    sumables_codigo = [j for j in sumables if any(cierra(i, j) for i in padres)]
    reconstruido = {}
    for i in sorted(padres, key=lambda i: (-codigos[i].count("."), i)):
        hijos = padres[i]
        comparables = []
        for j in sumables_codigo:
            total = valores[i][j] if j < len(valores[i]) else None
            partes = [valores[k][j] if j < len(valores[k]) else None for k in hijos]
            if total is None or any(p is None for p in partes):
                continue
            suma = sum(float(p) for p in partes)
            ok = abs(suma - float(total)) <= tolerancia(partes, total)
            alternativa = sum(reconstruido.get((k, j), float(p)) for k, p in zip(hijos, partes))
            explicado = (not ok and any((k, j) in reconstruido for k in hijos)
                         and abs(alternativa - float(total)) <= tolerancia(partes, total))
            if not ok and not explicado:
                reconstruido[(i, j)] = alternativa
            comparables.append((j, suma, partes, ok or explicado))
        # Un padre que no cierra en ninguna columna puede ser un desglose parcial: no se marca.
        if len(comparables) > 1 and not any(ok for *_, ok in comparables):
            continue
        for j, suma, partes, ok in comparables:
            if not ok:
                nombres = ", ".join(codigos[k] for k in hijos[:4]) + ("…" if len(hijos) > 4 else "")
                marcar(i, j, f"No suma: sus subcuentas ({nombres}) dan {_fmt_es(suma, partes)} y la fila dice {celda_txt(filas[i][j])}.")
    inicio = 0
    for i, f in enumerate(filas):
        if not _es_total(rotulos_fila[i]):
            continue
        bloque = [k for k in range(inicio, i) if not any(
            _es_total(_limpio(c)) for j, c in enumerate(filas[k]) if j not in periodos)]
        inicio = i + 1
        if len(bloque) < 2:
            continue
        # Con jerarquía por código, el total es la suma de los códigos de primer nivel del bloque.
        primer_nivel = _primer_nivel(codigos, bloque)
        for j in sumables:
            total = valores[i][j] if j < len(valores[i]) else None
            partes = [valores[k][j] for k in bloque if j < len(valores[k]) and valores[k][j] is not None]
            if total is None or len(partes) < 2:
                continue
            suma = sum(float(p) for p in partes)
            if abs(suma - float(total)) > tolerancia(partes, total):
                columna = [valores[k][j] if j < len(valores[k]) else None for k in bloque]
                ajustada = _suma_sin_subtotales(columna, tolerancia)
                if ajustada is not None and abs(ajustada - float(total)) <= tolerancia(partes, total):
                    continue
                superiores = [valores[k][j] if j < len(valores[k]) else None for k in primer_nivel]
                if (len(superiores) >= 2 and all(v is not None for v in superiores)
                        and abs(sum(float(v) for v in superiores) - float(total)) <= tolerancia(superiores, total)):
                    continue
                marcar(i, j, f"No suma: las filas de arriba dan {_fmt_es(suma, partes)} y el total dice {celda_txt(filas[i][j])}.")
    for jt in [j for j in range(ancho) if _es_total(rotulos[j]) and j not in periodos]:
        partes_j = [j for j in sumables if j < jt]
        if len(partes_j) < 2:
            continue
        for i, v in enumerate(valores):
            total = v[jt] if jt < len(v) else None
            partes = [v[j] for j in partes_j if j < len(v) and v[j] is not None]
            if total is None or len(partes) < 2:
                continue
            suma = sum(float(p) for p in partes)
            if abs(suma - float(total)) > tolerancia(partes, total):
                marcar(i, jt, f"No suma: las columnas de la fila dan {_fmt_es(suma, partes)} y el total dice {celda_txt(filas[i][jt])}.")
    return dudosas


def _suma_sin_subtotales(columna, tolerancia):
    """Suma de un bloque sin contar dos veces los subtotales.

    Una fila que es la suma de las 2 o más filas que la siguen («Ayuda directa» = Asignaciones +
    Resto) es un subtotal: se suma ella y no sus componentes. Se repite hasta que no cambie, para
    los subtotales de varios niveles («1» = «1.1» + «1.2», cada uno con sus propias subcuentas).
    """
    valores = [float(v) if v is not None else None for v in columna]
    textos = [v for v in columna]
    excluidas = set()
    cambio = True
    while cambio:
        cambio = False
        for k, v in enumerate(valores):
            if v is None or k in excluidas:
                continue
            acumulado, partes, usadas = 0.0, [], []
            for m in range(k + 1, len(valores)):
                if m in excluidas:
                    continue
                if valores[m] is None:
                    break
                acumulado += valores[m]
                partes.append(textos[m])
                usadas.append(m)
                if len(partes) >= 2 and abs(acumulado - v) <= tolerancia(partes, textos[k]):
                    excluidas.update(usadas)
                    cambio = True
                    break
    if not excluidas:
        return None
    return sum(v for k, v in enumerate(valores) if v is not None and k not in excluidas)


# Código jerárquico al comienzo del rótulo («1», «1.2», «1.2.1.», «A.1», «II.1»), solo o seguido del texto.
# Debe coincidir con codigoFila de static/ocr.js y con services/controles_excel/jerarquia_codigos.py.
CODIGO_FILA = re.compile(r"^((?:\d{1,3}|[A-Z]|[IVX]{1,5})(?:\.\d{1,3})*)(\.?)(\s+\S.*)?$")
DESGLOSE = re.compile(r"\b(?:de (?:las|los) cuales|del cual|de la cual|incluye|entre (?:ellos|ellas))\b")


def codigo_fila(rotulo):
    m = CODIGO_FILA.match(rotulo or "")
    if not m:
        return None
    codigo = m.group(1)
    if m.group(3) and "." not in codigo and not codigo.isdigit() and not m.group(2):
        return None  # «A Buenos Aires», «I Parte»: una letra sin punto es la primera palabra del rótulo
    return codigo


def codigos_jerarquia(rotulos):
    """{fila: código} si los rótulos forman una jerarquía por código; {} si no (o si es ambigua)."""
    codigos = {i: k for i, r in enumerate(rotulos) if (k := codigo_fila(r))}
    if len(codigos) < 3 or not any("." in k for k in codigos.values()):
        return {}
    if len(set(codigos.values())) != len(codigos):
        return {}  # códigos repetidos: la jerarquía es ambigua
    if not _padres_por_codigo(codigos):
        return {}
    return codigos


def _padres_por_codigo(codigos):
    """{fila padre: [filas de sus hijos inmediatos]} con dos o más hijos, después del padre y sin saltos."""
    fila_de = {k: i for i, k in codigos.items()}
    salida = {}
    for k, i in fila_de.items():
        hijos = sorted((x for x in fila_de if x.startswith(k + ".") and "." not in x[len(k) + 1:]),
                       key=lambda x: fila_de[x])
        if len(hijos) < 2 or any(fila_de[h] < i for h in hijos):
            continue
        ultimos = [h.split(".")[-1] for h in hijos]
        if all(u.isdigit() for u in ultimos):
            numeros = sorted(int(u) for u in ultimos)
            if numeros[0] > 1 or numeros != list(range(numeros[0], numeros[0] + len(numeros))):
                continue  # subcuentas salteadas: no se afirma el cierre
        salida[i] = [fila_de[h] for h in hijos]
    return salida


def _primer_nivel(codigos, bloque):
    """Filas del bloque cuyo código no tiene un ancestro en el bloque (si todas las filas tienen código)."""
    propios = {k: codigos.get(k) for k in bloque}
    if not codigos or any(v is None for v in propios.values()):
        return []
    valores = set(propios.values())
    return [k for k, v in propios.items() if not any(v.startswith(p + ".") for p in valores if p != v)]


def celda_txt(celda):
    return _limpio(celda)


def _fmt_es(valor, partes):
    dec = max([_decimales(p) for p in partes] or [0])
    texto = f"{valor:,.{dec}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def completar_hacia_abajo(filas, columna):
    """Completa una columna de celdas combinadas (p. ej. el año de un grupo de filas).

    Si el valor aparece al comienzo de cada grupo, copia hacia abajo. Si aparece centrado (como
    en muchos PDF: «Nación / 2001 Provincias / Total»), detecta el tamaño del grupo por la
    distancia regular entre valores y reparte cada valor entre las filas de su grupo.
    """
    filas = [list(f) for f in filas]
    llenas = [i for i, f in enumerate(filas) if columna < len(f) and _limpio(f[columna])]
    if not llenas:
        return filas
    pasos = [b - a for a, b in zip(llenas, llenas[1:])]
    paso = max(set(pasos), key=pasos.count) if pasos else None
    desfase = llenas[0]
    regular = bool(paso) and desfase < paso and all(p == paso for p in pasos)
    for i, f in enumerate(filas):
        while len(f) <= columna:
            f.append("")
        if _limpio(f[columna]):
            continue
        if regular:
            # El grupo de la fila i empieza en (i // paso) * paso y su rótulo está «desfase» filas más abajo.
            origen = (i // paso) * paso + desfase
            if 0 <= origen < len(filas) and origen in llenas:
                f[columna] = filas[origen][columna]
                continue
        anteriores = [k for k in llenas if k < i]
        if anteriores:
            f[columna] = filas[anteriores[-1]][columna]
    return filas


def _nombres_unicos(encabezado):
    nombres = []
    for j, rotulo in enumerate(encabezado):
        nombre = _limpio(rotulo) or f"columna_{j + 1}"
        if nombre in nombres:
            previo = nombres[-1] if nombres else ""
            candidato = f"{previo} · {nombre}" if previo else nombre
            k = 2
            while candidato in nombres:
                candidato = f"{nombre} ({k})"
                k += 1
            nombre = candidato
        nombres.append(nombre)
    return nombres


def csv_revisado(encabezado, filas, formato):
    """CSV de la tabla confirmada: UTF-8, «;» como separador, coma decimal y sin punto de miles."""
    formato = "en" if formato == "en" else "es"

    def celda(valor):
        texto = _limpio(valor)
        n = numero(texto, formato)
        if n is not None:
            return n.lstrip("+").replace(".", ",")
        if re.match(r"^[=+@\-]", texto):
            texto = "'" + texto
        if any(c in texto for c in ';"\n\r') or texto != texto.strip():
            texto = '"' + texto.replace('"', '""') + '"'
        return texto

    def cabecera(valor):
        texto = str(valor)
        if re.match(r"^[=+@\-]", texto):
            texto = "'" + texto
        return '"' + texto.replace('"', '""') + '"' if any(c in texto for c in ';"\n\r') else texto

    ancho = max([len(encabezado)] + [len(f) for f in filas])
    encabezado = list(encabezado) + [""] * (ancho - len(encabezado))
    lineas = [";".join(cabecera(n) for n in _nombres_unicos(encabezado))]
    for f in filas:
        f = list(f) + [""] * (ancho - len(f))
        if not any(_limpio(c) for c in f):
            continue
        lineas.append(";".join(celda(c) for c in f))
    return "﻿" + "\r\n".join(lineas) + "\r\n"


# Palabras funcionales inglesas: sin ellas no hay inglés (las abreviaturas de mes y «Total» son
# compartidas con el castellano y no deciden nada).
FUNCIONALES_EN = frozenset("the of and by in for from per with to thousand thousands million millions".split())
PALABRAS_EN = FUNCIONALES_EN | frozenset(
    "source table note notes units month year quarter country number jan apr aug dec january february march "
    "april june july august september october november december annual monthly quarterly installed exports "
    "imports tonnes".split())
FUNCIONALES_ES = frozenset("de la el en y por del los las con para sobre".split())
# Palabras de la estructura de un cuadro en castellano: con alguna, el texto es castellano o bilingüe
# («Fuente / Source») y el idioma no decide el formato.
ESTRUCTURA_ES = frozenset(
    "cuadro fuente nota notas mes año anio región miles millones unidades trimestre enero febrero marzo abril "
    "mayo junio julio agosto septiembre setiembre octubre noviembre diciembre provincia elaboración propia "
    "datos según toneladas".split())
MILES_COMA = re.compile(r"^-?\(?\d{1,3}(?:,\d{3})+\)?$")
MILES_PUNTO = re.compile(r"^-?\(?\d{1,3}(?:\.\d{3})+\)?$")
# «0,875»: un primer grupo 0 no es separador de miles, es coma decimal.
COMA_DECIMAL_CERO = re.compile(r"^-?\(?0,\d+\)?$")


def _texto_en_ingles(texto):
    """El texto de la página está en inglés: al menos 2 palabras funcionales inglesas, 3 inglesas en total,
    claramente más que las funcionales castellanas, y ninguna palabra de cuadro en castellano."""
    palabras = re.findall(r"[a-záéíóúñü]+", (texto or "").lower())
    funcionales = sum(1 for p in palabras if p in FUNCIONALES_EN)
    en = sum(1 for p in palabras if p in PALABRAS_EN)
    es = sum(1 for p in palabras if p in FUNCIONALES_ES)
    if any(p in ESTRUCTURA_ES for p in palabras):
        return False
    return funcionales >= 2 and en >= 3 and en >= 3 * es


def _formato_por_idioma(datos, texto):
    """«24,328» sin otra evidencia es ambiguo; en una página en inglés, con cifras con coma de miles y
    ninguna con punto de miles ni con coma decimal («0,875»), la coma separa miles. Si no, sigue ambiguo."""
    celdas = [_token_numerico(c)[0] for f in datos for c in f]
    if (_texto_en_ingles(texto) and any(MILES_COMA.match(c) for c in celdas)
            and not any(MILES_PUNTO.match(c) or COMA_DECIMAL_CERO.match(c) for c in celdas)):
        return "en"
    return "ambiguo"


def _armar_tabla(filas, origen, titulo=None, encabezado_en=None, texto=""):
    filas = [[_limpio(c) for c in f] for f in filas if f and sum(1 for c in f if _limpio(c)) >= 1]
    if len(filas) < 2:
        return None
    ancho = max(len(f) for f in filas)
    filas = [f + [""] * (ancho - len(f)) for f in filas]
    vacias = [j for j in range(ancho) if not any(f[j] for f in filas)]
    filas = [[c for j, c in enumerate(f) if j not in vacias] for f in filas]
    if not filas or len(filas[0]) < 2:
        return None
    if encabezado_en is None:
        primera_dato = next((i for i, f in enumerate(filas) if carga_archivos._fila_parece_datos_pdf(f)), None)
        if primera_dato:
            # Encabezado: de las filas anteriores al primer dato, la que nombra más columnas.
            encabezado_en = max(range(primera_dato), key=lambda i: (sum(1 for c in filas[i] if c), i))
        else:
            encabezado_en = carga_archivos._detectar_header_pdf(filas) or 0
    encabezado = filas[encabezado_en]
    notas = [" ".join(c for c in dict.fromkeys(f) if c) for f in filas[:encabezado_en]]
    datos = filas[encabezado_en + 1:]
    if not datos:
        return None
    formato = detectar_formato(datos)
    if formato == "ambiguo" and texto:
        formato = _formato_por_idioma(datos, texto)
    return {
        "titulo": titulo or "",
        "notas": [n for n in notas if n],
        "origen": origen,
        "encabezado": encabezado,
        "filas": datos,
        "formato_numerico": formato,
        "columnas_periodo": columnas_periodo(encabezado, datos),
        "dudosas": celdas_dudosas(encabezado, datos, formato),
    }


def _puntaje(tablas):
    bien = mal = 0
    for t in tablas:
        for f in t["filas"]:
            for c in f:
                if carga_archivos.celda_con_varios_numeros(c):
                    mal += 1
                elif carga_archivos.NUMERO_SUELTO_PDF.match(c.replace(" ", "")):
                    bien += 1
    return bien - 3 * mal


def _sin_superindices_pagina(page):
    """La página sin las llamadas de nota en superíndice (dígitos o «*» de letra mucho más chica que
    la de las cifras): pegadas a una cifra, «9.857» con su llamada «1» se leía «9.8571». Vale para las
    dos lecturas de la tabla, por coordenadas y por líneas dibujadas."""
    try:
        letras = page.chars or []
        tamanos = sorted(float(ch.get("size") or 0) for ch in letras
                         if str(ch.get("text", "")).isdigit() and ch.get("upright", True))
        if not tamanos:
            return page
        normal = tamanos[len(tamanos) // 2]

        def queda(obj):
            if obj.get("object_type") != "char":
                return True
            # Sólo texto derecho: los dígitos de un encabezado girado («Año 2017» vertical) no son llamadas.
            return not (obj.get("upright", True) and float(obj.get("size") or normal) < 0.75 * normal
                        and str(obj.get("text", "")) in "0123456789*†‡")

        return page.filter(queda)
    except Exception:
        return page


def _cuadros_de_la_pagina(page):
    """Franjas de la página, una por rótulo «Cuadro N»: con dos cuadros en la misma página, sus
    columnas no coinciden y una sola grilla no reconoce ninguno."""
    try:
        palabras = page.extract_words() or []
    except Exception:
        return []
    arranques = [fila[0]["top"] for fila in carga_archivos._filas_por_posicion_pdf(palabras)
                 if ROTULO_CUADRO_RE.match(" ".join(str(w["text"]) for w in fila))]
    if len(arranques) < 2:
        return []
    limites = [float(a) for a in arranques] + [float(page.height)]
    return [page.crop((0, max(0.0, a - 1), float(page.width), b - 0.5)) for a, b in zip(limites, limites[1:]) if b - a > 20]


def tablas_pagina_pdf(page, texto="", dividir=True):
    """Tablas de una página con texto: por coordenadas de palabras o por líneas dibujadas.

    Se queda con la lectura que deja más celdas con un único número (columnas bien separadas).
    """
    for nombre in ("pdfminer", "pdfplumber"):
        logging.getLogger(nombre).setLevel(logging.ERROR)
    if dividir:
        page = _sin_superindices_pagina(page)
        tablas = [t for franja in _cuadros_de_la_pagina(page) for t in tablas_pagina_pdf(franja, "", dividir=False)]
        if tablas:
            return tablas
    try:
        # El texto de pdfplumber respeta mejor los espacios de los títulos que el de pypdf.
        texto = page.extract_text() or texto
    except Exception:
        pass
    titulo = (ROTULO_CUADRO_RE.search(texto or "") or [None])[0]
    titulo = _limpio(titulo) if titulo else ""
    candidatas = []
    grilla = carga_archivos._grilla_por_coordenadas_pdf(page)
    tabla = _armar_tabla(grilla, "texto_pdf", titulo, texto=texto) if grilla else None
    if tabla:
        candidatas.append([tabla])
    try:
        crudas = page.extract_tables(table_settings={
            "vertical_strategy": "lines", "horizontal_strategy": "lines",
            "intersection_tolerance": 6, "snap_tolerance": 4, "join_tolerance": 4,
        }) or []
    except Exception:
        crudas = []
    por_lineas = []
    for cruda in crudas:
        filas = carga_archivos._normalizar_tabla_pdf(cruda)
        if len(filas) >= 3:
            t = _armar_tabla(filas, "texto_pdf", titulo, texto=texto)
            if t:
                por_lineas.append(t)
    if por_lineas:
        candidatas.append(por_lineas)
    if not candidatas:
        return []
    return max(candidatas, key=_puntaje)


def _unir_continuaciones(pages):
    """Un cuadro que sigue en la página siguiente sin repetir el encabezado: su primera fila es de
    datos, no un encabezado. Sus filas se suman a la tabla de la página anterior, con el encabezado
    de esa tabla, y la pantalla lo avisa."""
    for k in range(1, len(pages)):
        previa, hoja = pages[k - 1], pages[k]
        if previa.get("metodo") != "texto_pdf" or hoja.get("metodo") != "texto_pdf":
            continue
        if not previa.get("tablas") or not hoja.get("tablas"):
            continue
        a, b = previa["tablas"][-1], hoja["tablas"][0]
        if len(a["encabezado"]) != len(b["encabezado"]) or (b.get("titulo") and b.get("titulo") != a.get("titulo")):
            continue
        if not carga_archivos._fila_parece_datos_pdf(b["encabezado"]):
            continue
        a["filas"] = a["filas"] + [list(b["encabezado"])] + b["filas"]
        a["columnas_periodo"] = columnas_periodo(a["encabezado"], a["filas"])
        a["dudosas"] = celdas_dudosas(a["encabezado"], a["filas"], a.get("formato_numerico"))
        a["notas"] = list(a.get("notas") or []) + [
            f"El cuadro sigue en la página {hoja['pagina']} sin repetir el encabezado: sus filas se unieron a esta tabla."]
        hoja["tablas"] = hoja["tablas"][1:]
        hoja["aviso_cifras"] = (f"El cuadro de esta página continúa el de la página {previa['pagina']}: "
                                "sus filas se unieron a esa tabla, con su encabezado.")
        ca = a.get("cifras_pagina") or {}
        cb = hoja.get("cifras_pagina") or {}
        a["cifras_pagina"] = {clave: list(ca.get(clave) or []) + list(cb.get(clave) or [])
                              for clave in ("filas", "todas", "palabras")}


def _cifras_pagina(hoja, page, texto, renglones=None):
    """Cifras del texto de la página contra las de las tablas propuestas. Si la lectura dejó cifras
    afuera o trae cifras que el texto no tiene (un cuadro impreso de costado), la pantalla lo avisa, y
    cada tabla lleva las cifras de la página que le corresponden para que el informe lo declare."""
    from services import cobertura_cifras as cc

    # Dos textos de la página: el de pypdf (sigue el orden del documento, pero a veces da una palabra
    # por renglón) y el de pdfplumber (con renglones). Por defecto, el de renglones: con una palabra por
    # renglón sólo se reconocerían las cifras de los párrafos. Pero si con el de pypdf la tabla trae
    # cifras que el texto no tiene y con el de renglones no, la tabla está tan desarmada como el texto
    # de renglones (un cuadro impreso de costado): manda pypdf.
    if renglones is None:
        try:
            renglones = _sin_superindices_pagina(page).extract_text() or ""
        except Exception:
            renglones = ""
    try:
        tablas = hoja.get("tablas") or []
        por_tabla = [cc.cifras_tabla(t["encabezado"], t["filas"]) for t in tablas]
        leidas = [c for x in por_tabla for c in x]
        candidatos = []
        for tx in [texto] + ([renglones] if renglones else []):
            originales, todas = cc.cifras_texto(tx), cc.todas_las_cifras(tx)
            candidatos.append((tx, originales, todas, cc.comparar(originales, leidas, todas)))
        elegido = candidatos[-1]
        primero = candidatos[0]
        if (len(candidatos) > 1 and cc.declarable(primero[3]["ajenas"], primero[3]["en_lectura"])
                and not cc.declarable(elegido[3]["ajenas"], elegido[3]["en_lectura"])):
            elegido = primero
        texto, originales, todas, comp = elegido
    except Exception:  # noqa: BLE001 — el conteo no puede impedir la lectura
        return
    hoja["cobertura_cifras"] = comp
    aviso = cc.aviso_pagina(comp, len(tablas))
    if aviso:
        hoja["aviso_cifras"] = aviso
    # Las palabras del texto: el informe compara con ellas los rótulos de la tabla confirmada.
    # De los dos textos, y separando palabras pegadas («JuanSantiago»).
    # Sólo del texto de pypdf: el de renglones trae los mismos rótulos desarmados que la tabla.
    crudas = re.findall(r"[^\W\d_]{3,}", candidatos[0][0])
    partes = [p for w in crudas for p in re.split(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", w)]
    palabras = sorted({w.lower() for w in crudas + partes if len(w) >= 3})[:8000]
    hoja["cifras_pagina"] = {"filas": originales[:5000], "todas": todas[:20000], "palabras": palabras}
    for k, t in enumerate(tablas):
        otras = [c for j, x in enumerate(por_tabla) if j != k for c in x]
        t["cifras_pagina"] = {"filas": cc.restar(originales, otras)[:5000], "todas": todas[:20000], "palabras": palabras}



def _campos_con_valor(pagina_pypdf, pagina_plumber):
    """Campos de formulario completados (anotaciones /Widget con /V): sus valores no son texto de la página.

    Devuelve None o {n, ejemplo, texto}: el texto rearma los renglones de la página con las palabras impresas
    y los valores de los campos según su posición, separando con tabulación lo que está a más de 6 puntos.
    Un campo cuyo valor también está impreso en su recuadro no se cuenta. En una página girada el recuadro
    de los campos no coincide con las palabras: el texto queda en None y sólo se avisa.
    """
    try:
        alto = float(pagina_plumber.height)
        palabras = [((float(w["top"]) + float(w["bottom"])) / 2, float(w["x0"]), float(w["x1"]), str(w["text"]))
                    for w in pagina_plumber.extract_words() or []]
    except Exception:  # noqa: BLE001
        alto, palabras = 0.0, []
    try:
        piezas = []
        for ref in pagina_pypdf.get("/Annots") or []:
            anotacion = ref.get_object()
            if anotacion.get("/Subtype") != "/Widget":
                continue
            v = anotacion.get("/V")
            if v is None and anotacion.get("/Parent") is not None:
                v = anotacion["/Parent"].get_object().get("/V")
            if v is None or not isinstance(v, str) or str(v).startswith("/") or not str(v).strip():
                continue
            x0, y0, x1, y1 = (float(z) for z in anotacion["/Rect"])
            arriba, abajo, izquierda, derecha = alto - max(y0, y1), alto - min(y0, y1), min(x0, x1), max(x0, x1)
            valor = str(v).strip()
            impreso = "".join(t for c, a0, a1, t in palabras
                              if arriba <= c <= abajo and izquierda - 1 <= (a0 + a1) / 2 <= derecha + 1)
            if impreso.replace(" ", "") == valor.replace(" ", ""):
                continue  # el valor también está impreso: ya es texto de la página
            piezas.append(((arriba + abajo) / 2, izquierda, derecha, valor))
        girada = int(pagina_pypdf.get("/Rotate") or 0) % 360
    except Exception:  # noqa: BLE001 — un formulario raro no puede impedir la lectura
        return None
    if not piezas:
        return None
    n, ejemplo = len(piezas), piezas[0][3]
    if girada:
        return {"n": n, "ejemplo": ejemplo, "texto": None}
    piezas += palabras
    # Renglones por el centro vertical: el recuadro de un campo es más alto que la letra impresa a su lado.
    renglones = []
    for centro, x0, x1, texto in sorted(piezas):
        if renglones and centro - renglones[-1][0] <= 5:
            renglones[-1][1].append((x0, x1, texto))
        else:
            renglones.append((centro, [(x0, x1, texto)]))
    lineas = []
    for _, piezas_renglon in renglones:
        partes, fin = [], None
        for x0, x1, texto in sorted(piezas_renglon):
            if fin is not None:
                partes.append("\t" if x0 - fin > 6 else " ")
            partes.append(texto)
            fin = x1
        lineas.append("".join(partes))
    return {"n": n, "ejemplo": ejemplo, "texto": "\n".join(lineas)}


def _tabla_de_campos(texto):
    """Una tabla con los renglones rearmados de un formulario (rótulo impreso y valores de los campos)."""
    filas = [linea.split("\t") for linea in texto.splitlines()]
    filas = [f for f in filas if sum(1 for c in f if c.strip()) >= 2]
    tabla = _armar_tabla(filas, "texto_pdf", "Armada con los campos de formulario de la página") if len(filas) >= 3 else None
    return [tabla] if tabla else []


def _imagenes_grandes(pagina_plumber, desplazamiento=(0.0, 0.0)):
    """Imágenes que ocupan una parte grande de una página con texto: no un membrete ni un pie (pegados al
    borde de arriba o de abajo), ni la página entera escaneada con su capa de texto (las imágenes suman
    80 % o más). Las dos más grandes. `desplazamiento` lleva las coordenadas a la zona visible de la página
    (cropbox), que es la que se dibuja para el OCR."""
    try:
        ancho, alto = float(pagina_plumber.width) or 1.0, float(pagina_plumber.height) or 1.0
        dx, dy = desplazamiento
        salida, total = [], 0.0
        for im in pagina_plumber.images or []:
            x0, x1, top, bottom = (float(im[k]) for k in ("x0", "x1", "top", "bottom"))
            parte = max(0.0, x1 - x0) * max(0.0, bottom - top) / (ancho * alto)
            total += parte
            if bottom <= 0.15 * alto or top >= 0.85 * alto:
                continue
            if parte >= 0.10 or ((x1 - x0) / ancho >= 0.5 and parte >= 0.05):
                salida.append({"x0": x0 - dx, "top": top - dy, "x1": x1 - dx, "bottom": bottom - dy, "parte": parte})
        if total >= 0.8:  # la página escaneada (aunque venga en franjas) con su capa de texto
            return []
        return sorted(salida, key=lambda g: -g["parte"])[:2]
    except Exception:  # noqa: BLE001
        return []


def _desplazamiento_visible(pagina_pypdf):
    """Cuánto corre la zona visible (cropbox) respecto de la página completa (mediabox) que mide pdfplumber,
    en puntos, desde arriba a la izquierda. En una página girada no se corrige."""
    try:
        if int(pagina_pypdf.get("/Rotate") or 0) % 360:
            return (0.0, 0.0)
        mb, cb = pagina_pypdf.mediabox, pagina_pypdf.cropbox
        return (float(cb.left) - float(mb.left), float(mb.top) - float(cb.top))
    except Exception:  # noqa: BLE001
        return (0.0, 0.0)


def _tablas_de_imagenes(img, escala, grandes):
    """Lee con OCR las imágenes grandes de una página con texto: cada cuadro, una tabla aparte. Devuelve las
    tablas y cuántas cifras leyó el OCR (sin cifras, la imagen no era un cuadro: un logo, una foto)."""
    from services import cobertura_cifras as cc

    tablas, cifras = [], 0
    for g in grandes:
        recorte = img.crop(tuple(int(g[k] * escala) for k in ("x0", "top", "x1", "bottom")))
        lineas = reconocer(recorte)
        texto = "\n".join(x["texto"].replace("\t", " ") for x in lineas)
        filas = cc.cifras_texto(texto)
        cifras += len(filas)
        for t in tablas_ocr(lineas):
            t["titulo"] = "Cuadro en una imagen de la página, leído con OCR"
            t["origen"] = "ocr"
            palabras = sorted({w.lower() for w in re.findall(r"[^\W\d_]{3,}", texto)})[:8000]
            # Su original es la imagen: se compara con lo que leyó el OCR, no con el texto del PDF.
            t["cifras_pagina"] = {"filas": filas[:5000], "todas": cc.todas_las_cifras(texto)[:20000], "palabras": palabras}
            tablas.append(t)
    return tablas, cifras


def tablas_ocr(lineas):
    filas = [[c.strip() for c in linea["texto"].split("\t")] for linea in lineas]
    filas = [f for f in filas if sum(1 for c in f if c) >= 2]
    tabla = _armar_tabla(filas, "ocr") if len(filas) >= 2 else None
    return [tabla] if tabla else []



def _texto_ilegible(texto):
    """El texto que extrae el PDF no corresponde a lo que se ve: una fuente con un mapa de caracteres inútil
    da letras corridas, dígitos como caracteres de control y símbolos de uso privado («&XDGUR» por «Cuadro»)."""
    s = [c for c in texto if not c.isspace()]
    raros = sum(1 for c in s if ord(c) < 32 or 0x7F <= ord(c) < 0xA0 or 0xE000 <= ord(c) <= 0xF8FF or c == "\ufffd")
    return len(s) >= 40 and raros >= 0.10 * len(s)


def _adjuntos(reader, alcance):
    """Nombres de los archivos adjuntos al PDF (del documento o de una anotación en sus páginas)."""
    nombres = []
    try:
        nombres.extend(str(n) for n in (reader.attachments or {}))
    except Exception:  # noqa: BLE001
        pass
    for i in range(alcance):
        try:
            for ref in reader.pages[i].get("/Annots") or []:
                a = ref.get_object()
                if a.get("/Subtype") == "/FileAttachment":
                    fs = a.get("/FS")
                    fs = fs.get_object() if fs is not None else {}
                    nombre = fs if isinstance(fs, str) else (fs.get("/UF") or fs.get("/F") or "sin nombre")
                    nombres.append(str(nombre))
        except Exception:  # noqa: BLE001
            continue
    return list(dict.fromkeys(nombres))


def _declarar_adjuntos(pages, adjuntos):
    """Los adjuntos no se leen: se dice en cada página y viaja con las cifras de cada tabla, para que el
    informe lo declare al comienzo con cualquier tabla que se confirme (también una leída con OCR)."""
    if not adjuntos:
        return
    aviso = (f"el PDF trae {'un archivo adjunto' if len(adjuntos) == 1 else f'{len(adjuntos)} archivos adjuntos'} "
             f"que no se {'leyó' if len(adjuntos) == 1 else 'leyeron'} ({', '.join(n[:40] for n in adjuntos[:3])}"
             + (" y otros" if len(adjuntos) > 3 else "") + "): si trae datos, cargalo aparte")
    for hoja in pages:
        for c in [hoja] + (hoja.get("tablas") or []):
            d = c.get("cifras_pagina")
            if not isinstance(d, dict):
                d = c["cifras_pagina"] = {}
            # El adjunto primero: el informe recorta este texto a 300 caracteres.
            d["fuera_del_texto"] = "; ".join(x for x in (aviso, d.get("fuera_del_texto")) if x)
        if hoja.get("metodo"):
            hoja["aviso_cifras"] = (aviso[0].upper() + aviso[1:] + ". " + (hoja.get("aviso_cifras") or "")).strip()


def _indice_pdf(reader, alcance):
    indice, textos = [], []
    for i in range(alcance):
        try:
            texto = (reader.pages[i].extract_text() or "").strip()
        except Exception:
            texto = ""
        ilegible = _texto_ilegible(texto)
        if ilegible:
            texto = ""  # se lee como una página escaneada: por OCR y con su cupo
        textos.append(texto)
        titulo = ROTULO_CUADRO_RE.search(texto)
        numericas = sum(
            1 for linea in texto.splitlines()
            if sum(1 for t in linea.split() if carga_archivos.NUMERO_SUELTO_PDF.match(t)) >= 3
        )
        indice.append({
            "pagina": i + 1,
            "con_texto": len(texto) >= 40,
            "texto_ilegible": ilegible,
            "titulo": _limpio(titulo[0])[:160] if titulo else "",
            "filas_numericas": numericas,
        })
    return indice, textos


def _seleccion(indice, paginas):
    if paginas:
        try:
            elegidas = sorted({int(p) for p in paginas})
        except (TypeError, ValueError):
            raise ValueError("Indicá las páginas con números, por ejemplo 3,4,10.")
        fuera = [p for p in elegidas if p < 1 or p > len(indice)]
        if fuera:
            raise ValueError(f"Página fuera del documento o del límite de {MAX_PAGINAS_TEXTO} páginas: {fuera[0]}.")
        if len(elegidas) > MAX_PAGINAS_DETALLE:
            raise ValueError(f"Elegí hasta {MAX_PAGINAS_DETALLE} páginas por lectura.")
        return elegidas
    if len(indice) <= MAX_PAGINAS_DETALLE:
        return [p["pagina"] for p in indice]
    con_cuadros = [p["pagina"] for p in indice if p["titulo"] or p["filas_numericas"] >= 3]
    return (con_cuadros or [p["pagina"] for p in indice])[:MAX_PAGINAS_DETALLE]



MAX_IMAGENES_OCR = 4  # cuadros en imagen leídos con OCR por documento, aparte del cupo de páginas escaneadas


def _fuera_del_texto(hoja, campos, pagina_plumber, img, escala, leidas, desplazamiento=(0.0, 0.0), con_tiempo=True):
    """Lo que la página muestra y no está en su texto (campos de formulario, cuadros en imagen) se dice en
    pantalla y viaja con las cifras de la página para que el informe lo declare. Una imagen que el OCR lee
    sin cifras (un logo, una foto) no se declara. Devuelve cuántas imágenes del documento pasaron por OCR."""
    avisos, sin_leer = [], []
    if campos:
        hoja["campos_formulario"] = campos["n"]
        cuantos = f"{campos['n']} {'campo' if campos['n'] == 1 else 'campos'} de formulario completados"
        ejemplo = campos["ejemplo"][:30]
        if campos["texto"]:
            avisos.append(f"La página tiene {cuantos} (por ejemplo «{ejemplo}»): sus valores no son texto impreso "
                          "del PDF; se agregaron al texto leído según su posición.")
        else:
            sin_leer.append(f"la página tiene {cuantos} (por ejemplo «{ejemplo}») que no son texto impreso; la "
                            "página está girada, sus valores no se ubicaron junto a sus rótulos y no se leyeron")
    grandes = _imagenes_grandes(pagina_plumber, desplazamiento)
    if grandes:
        parte = round(100 * sum(g["parte"] for g in grandes))
        que = (f"una imagen que ocupa el {parte} % de la página" if len(grandes) == 1
               else f"{len(grandes)} imágenes que ocupan el {parte} % de la página")
        tablas, cifras, leida = [], 0, False
        if leidas < MAX_IMAGENES_OCR and con_tiempo:
            leidas += 1
            try:
                tablas, cifras = _tablas_de_imagenes(img, escala, grandes)
                leida = True
            except Exception:  # noqa: BLE001 — sin OCR, se avisa igual
                tablas, cifras = [], 0
        if tablas:
            hoja["imagenes_grandes"] = len(grandes)
            # Se agregan después de unir los cuadros que siguen en otra página (extraer).
            hoja["_tablas_imagen"] = tablas
            avisos.append(f"La página tiene {que}: no es texto del PDF. Se leyó con OCR como "
                          f"{'una tabla aparte' if len(tablas) == 1 else 'tablas aparte'} («Cuadro en una imagen…»): "
                          "revisá números y signos contra el original.")
        elif cifras or not leida:
            hoja["imagenes_grandes"] = len(grandes)
            sin_leer.append(f"la página tiene {que}; " + (
                "el OCR encontró cifras en ella pero no pudo armar un cuadro, y no se leyeron" if leida
                else "si contiene un cuadro, sus cifras no están en el texto del PDF y no se leyeron"))
    if sin_leer:
        texto = "; ".join(sin_leer)
        hoja["contenido_sin_leer"] = True
        avisos.append(texto[0].upper() + texto[1:] + ".")
        for t in hoja.get("tablas") or []:
            if t.get("cifras_pagina") is not None:
                t["cifras_pagina"]["fuera_del_texto"] = texto
        if hoja.get("cifras_pagina") is not None:
            hoja["cifras_pagina"]["fuera_del_texto"] = texto
    if avisos:
        hoja["aviso_cifras"] = " ".join(avisos + ([hoja["aviso_cifras"]] if hoja.get("aviso_cifras") else []))
    return leidas


def _ids(lista):
    ids = {getattr(x, "idnum", None) for x in (lista or [])}
    ids.discard(None)
    return ids


def _capas_de_formularios(recursos, vistos=None):
    """Capas (OCG) que usan los Form XObject de la página, en sus recursos o en su propio /OC."""
    vistos = set() if vistos is None else vistos
    capas = set()
    xobjetos = recursos.get("/XObject")
    for ref in (xobjetos.get_object().values() if xobjetos else []):
        if getattr(ref, "idnum", None) in vistos:
            continue
        vistos.add(getattr(ref, "idnum", None))
        x = ref.get_object()
        if x.get("/Subtype") != "/Form":
            continue
        if x.get("/OC") is not None:
            capas |= _ids([x.raw_get("/OC")]) or {-1}
        propios = x.get("/Resources")
        propios = propios.get_object() if propios else {}
        props = propios.get("/Properties")
        capas |= _ids((props.get_object() if props else {}).values())
        capas |= _capas_de_formularios(propios, vistos)
    return capas


def _capas_apagadas(reader, i):
    """«todas» si todas las capas opcionales (OCG) que usa la página, desde su contenido, están apagadas en
    la vista por defecto del PDF (/OCProperties /D /OFF): ese texto se puede separar. «no_separable» si
    alguna capa usada está apagada pero no se puede separar con seguridad (sólo algunas apagadas, estado
    base /OFF con lista /ON, o capas usadas desde un Form XObject). None si no hay capas apagadas en uso."""
    try:
        ocp = reader.trailer["/Root"].get("/OCProperties")
        if not ocp:
            return None
        ocp = ocp.get_object()
        defecto = ocp.get("/D")
        defecto = defecto.get_object() if defecto else {}
        base_apagada = defecto.get("/BaseState") == "/OFF"
        if base_apagada:
            apagadas = _ids(ocp.get("/OCGs")) - _ids(defecto.get("/ON"))
        else:
            apagadas = _ids(defecto.get("/OFF"))
        if not apagadas:
            return None
        recursos = reader.pages[i].get("/Resources")
        recursos = recursos.get_object() if recursos else {}
        propiedades = recursos.get("/Properties")
        capas = _ids((propiedades.get_object() if propiedades else {}).values())
        de_formularios = _capas_de_formularios(recursos)
        usadas = capas | de_formularios
        if not usadas & apagadas and -1 not in de_formularios:
            return None
        if base_apagada or (de_formularios & apagadas) or -1 in de_formularios or not capas <= apagadas:
            return "no_separable"
        return "todas"
    except Exception:  # noqa: BLE001 — sin poder leer las capas, la página se lee como siempre
        return None


def _es_char_oculto(obj):
    return obj.get("object_type") == "char" and obj.get("tag") == "OC"


def _ejemplo_oculto(oculto):
    """Un renglón del texto oculto para citar en el aviso: mejor uno con palabras que una cifra suelta."""
    lineas = [_limpio(x) for x in oculto.splitlines() if x.strip()]
    return next((x for x in lineas if re.search(r"[^\W\d_]{3}", x)), lineas[0] if lineas else "")[:60]


def _sin_capas_apagadas(reader, i, pagina_plumber, native):
    """(página, texto, aviso). Texto en una capa opcional apagada («VERSIÓN PRELIMINAR», cifras viejas
    debajo de las nuevas): no se ve en pantalla ni al imprimir. Si todas las capas de la página están
    apagadas y su texto viene marcado como contenido opcional, se lee la página sin ese texto y se
    avisa; en cualquier otro caso (sólo algunas apagadas, estado base apagado, capas en un Form XObject,
    texto sin la marca) no se quita nada y se avisa que hay capas que no se pudieron separar.
    El texto invisible por modo de render (la capa OCR de un escaneo) no es una capa: no se toca."""
    estado = _capas_apagadas(reader, i)
    if not estado:
        return pagina_plumber, native, None
    try:
        oculto = (pagina_plumber.filter(_es_char_oculto).extract_text() or "").strip()
    except Exception:  # noqa: BLE001
        return pagina_plumber, native, None
    if estado == "todas" and oculto:
        try:
            visible = pagina_plumber.filter(lambda o: not _es_char_oculto(o))
            texto = (visible.extract_text() or "").strip()
        except Exception:  # noqa: BLE001
            return pagina_plumber, native, None
        ejemplo = _ejemplo_oculto(oculto)
        return visible, texto, (f"La página tiene texto oculto (una capa apagada) que no se tomó (por ejemplo «{ejemplo}»).")
    ejemplo = f" (por ejemplo «{_ejemplo_oculto(oculto)}»)" if oculto else ""
    return pagina_plumber, native, (
        f"La página tiene capas opcionales apagadas que no se pudieron separar{ejemplo}: se leyó todo el texto; "
        "revisá que no se hayan mezclado cifras que no se ven en el documento.")


def extraer(nombre, contenido, paginas=None):
    if not contenido or len(contenido) > MAX_BYTES:
        raise ValueError("Subí un archivo de hasta 15 MB.")
    ext = Path(nombre).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".pdf"):
        raise ValueError("Usá JPG, PNG o PDF.")
    if not LOCK.acquire(blocking=False):
        raise OCRNoDisponible("Hay otra lectura OCR en curso. Intentá nuevamente en unos minutos.")
    try:
        pages = []
        adjuntos = []
        total = 1
        indice = None
        seleccion = [1]
        start = time.monotonic()
        if ext == ".pdf":
            import pdfplumber
            import pypdfium2 as pdfium
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(contenido))
            if reader.is_encrypted:
                # Muchos PDF públicos sólo restringen copiar o imprimir: se abren sin clave y se leen.
                try:
                    abierto = reader.decrypt("")
                except Exception:
                    abierto = 0
                if not abierto:
                    raise ValueError("El PDF pide una contraseña para abrirse. Subí una copia sin contraseña.")
            total = len(reader.pages)
            if total == 0:
                raise ValueError("El PDF no contiene páginas.")
            indice, textos = _indice_pdf(reader, min(total, MAX_PAGINAS_TEXTO))
            adjuntos = _adjuntos(reader, min(total, MAX_PAGINAS_TEXTO))
            seleccion = _seleccion(indice, paginas)
            con_ocr = 0
            ocr_imagenes = 0
            doc = pdfium.PdfDocument(contenido)
            try:
                doc.init_forms()  # que la imagen de la página muestre los campos de formulario completados
            except Exception:  # noqa: BLE001
                pass
            plumber = pdfplumber.open(io.BytesIO(contenido))
            try:
                for numero_pagina in seleccion:
                    i = numero_pagina - 1
                    native = textos[i]
                    pagina_plumber = plumber.pages[i]
                    aviso_oculto = None
                    if native:  # una página escaneada o con texto ilegible se lee con OCR: no hay capas que quitar
                        pagina_plumber, native, aviso_oculto = _sin_capas_apagadas(reader, i, pagina_plumber, native)
                    tiene_texto = len(native) >= 40
                    if time.monotonic() - start > 100:
                        pages.append(
                            {"pagina": i + 1, "estado": "no_leida", "error": "Límite de tiempo del documento."}
                        )
                        continue
                    if not tiene_texto:
                        con_ocr += 1
                        if con_ocr > MAX_PAGES:
                            pages.append({"pagina": i + 1, "estado": "no_leida", "error": (
                                f"Límite de {MAX_PAGES} páginas leídas con OCR por vez: elegí menos páginas escaneadas.")})
                            continue
                    page = None
                    try:
                        page = doc[i]
                        width, height = page.get_size()
                        scale = min(2.0, 1800 / max(width, 1), 2400 / max(height, 1))
                        bitmap = page.render(scale=scale)
                        try:
                            img = bitmap.to_pil().copy()
                        finally:
                            bitmap.close()
                        hoja = _pagina(img, i + 1, native if tiene_texto else None)
                        if indice[i].get("texto_ilegible"):
                            hoja["aviso_cifras"] = ("El texto del PDF no es legible (sus caracteres no corresponden a "
                                                   "lo que se ve): la página se leyó con OCR. Revisá números y signos.")
                        if hoja.get("metodo") == "texto_pdf":
                            try:
                                hoja["tablas"] = tablas_pagina_pdf(pagina_plumber, native)
                            except Exception:
                                hoja["tablas"] = []
                            campos = _campos_con_valor(reader.pages[i], pagina_plumber)
                            if campos and campos["texto"]:
                                hoja["texto"] = campos["texto"]
                                if not hoja["tablas"]:
                                    hoja["tablas"] = _tabla_de_campos(campos["texto"])
                                _cifras_pagina(hoja, pagina_plumber, campos["texto"], renglones=campos["texto"])
                            else:
                                _cifras_pagina(hoja, pagina_plumber, native)
                            ocr_imagenes = _fuera_del_texto(
                                hoja, campos, pagina_plumber, img, scale, ocr_imagenes,
                                _desplazamiento_visible(reader.pages[i]), time.monotonic() - start <= 60)
                        if aviso_oculto:
                            hoja["aviso_cifras"] = " ".join(x for x in (aviso_oculto, hoja.get("aviso_cifras")) if x)
                        pages.append(hoja)
                    except OCRNoDisponible as exc:
                        pages.append({"pagina": i + 1, "estado": "no_leida", "error": str(exc)})
                    except Exception:
                        pages.append(
                            {
                                "pagina": i + 1,
                                "estado": "no_leida",
                                "error": "No se pudo procesar esta página. Probá exportarla como imagen o generar otro PDF.",
                            }
                        )
                    finally:
                        if page is not None:
                            page.close()
            finally:
                plumber.close()
                doc.close()
        else:
            with Image.open(io.BytesIO(contenido)) as image:
                if image.format not in ("JPEG", "PNG"):
                    raise ValueError("El contenido no corresponde a una imagen JPG o PNG.")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("Imagen demasiado grande: máximo 24 millones de píxeles.")
                if getattr(image, "n_frames", 1) > 1:
                    raise ValueError("Subí una imagen estática, sin animación.")
                pages.append(_pagina(image.copy(), 1))
        _unir_continuaciones(pages)
        for hoja in pages:
            # Los cuadros en imagen van después de unir continuaciones: un cuadro de texto que sigue en la
            # página siguiente se une al cuadro de texto, no a la tabla leída con OCR.
            if hoja.get("_tablas_imagen"):
                hoja["tablas"] = (hoja.get("tablas") or []) + hoja.pop("_tablas_imagen")
        for hoja in pages:
            if hoja.get("metodo") == "ocr_local" and "tablas" not in hoja:
                hoja["tablas"] = tablas_ocr(hoja.get("lineas") or [])
            if hoja.get("metodo"):
                hoja["lectura"] = LECTURA_LEGIBLE[hoja["metodo"]]
        _declarar_adjuntos(pages, adjuntos)
        alcance = len(indice) if indice is not None else 1
        return {
            "archivo": Path(nombre.replace("\\", "/")).name,
            "sha256": hashlib.sha256(contenido).hexdigest(),
            "tipo": "pdf" if ext == ".pdf" else "imagen",
            "paginas_totales": total,
            "paginas_incluidas": len(pages),
            "paginas_seleccionadas": seleccion,
            "indice": indice or [],
            "limite_paginas": MAX_PAGES,
            "limite_paginas_ocr": MAX_PAGES,
            "limite_paginas_texto": MAX_PAGINAS_TEXTO,
            "limite_paginas_por_lectura": MAX_PAGINAS_DETALLE,
            "adjuntos": adjuntos,
            "cobertura_parcial": total > len(pages)
            or alcance > len(pages)
            or any(p["estado"] != "para_revisar" or p.get("texto_truncado", False) or p.get("contenido_sin_leer")
                   for p in pages),
            "paginas": pages,
            "estado": "pendiente_revision_humana",
            "alcance": "Lectura preliminar para revisar contra el original. Nada se analiza hasta que confirmes la tabla. "
            "No se enviaron datos a proveedores de IA.",
        }
    finally:
        LOCK.release()
