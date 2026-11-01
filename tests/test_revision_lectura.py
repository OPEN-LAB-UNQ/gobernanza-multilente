"""Revisión de lectura 0.9.7: Multilente analiza directo sólo Excel y CSV.

Los PDF y las imágenes pasan antes por la revisión de lectura (/api/ocr): la persona ve el original
al lado de la tabla leída, corrige y confirma; recién después la tabla se analiza como CSV, y el
informe dice arriba que fue revisada por una persona.
"""

import io
import re
from pathlib import Path

import pytest
from openpyxl import Workbook
from PIL import Image

import models
from routers import ocr
from services import jobs, ocr_local
from services.reportes.markdown import render_reporte_markdown
from tests.flujo_confirmado import cargar_confirmado

pytest_plugins = ["tests.test_ejemplos_zip"]

PDF_CORPUS = Path("/ruta/no/publicada/corpus.pdf")


def _pdf_tabla(titulo="Cuadro 1. Matrícula por nivel", filas=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    filas = filas or [
        ["Nivel", "2021", "2022", "2023", "2024"],
        ["Inicial", "1.204", "1.250", "1.301", "1.322"],
        ["Primario", "4.510", "4.602", "4.655", "4.701"],
        ["Secundario", "3.120", "3.180", "3.260", "3.299"],
        ["Superior", "2.004", "2.051", "2.120", "2.188"],
        ["Total", "10.838", "11.083", "11.336", "11.510"],
    ]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, alto = A4
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, alto - 60, titulo)
    c.setFont("Helvetica", 10)
    y = alto - 100
    for fila in filas:
        c.drawString(50, y, fila[0])
        for i, v in enumerate(fila[1:]):
            c.drawRightString(260 + i * 80, y, v)
        y -= 16
    c.showPage()
    c.save()
    return buf.getvalue()


def _png():
    out = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(out, format="PNG")
    return out.getvalue()


def _xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"
    ws.append(["Región", "2021", "2022", "2023", "2024"])
    for i, region in enumerate(["Norte", "Sur", "Centro", "Cuyo", "Litoral"]):
        ws.append([region] + [1000 + 50 * i + 30 * k for k in range(4)])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv():
    filas = ["Provincia;2021;2022;2023;2024"] + [
        f"{p};{100 + 7 * i};{108 + 7 * i};{115 + 7 * i};{121 + 7 * i}"
        for i, p in enumerate(["Salta", "Jujuy", "Chaco", "Formosa", "Misiones", "Corrientes"])
    ]
    return ("\n".join(filas) + "\n").encode("utf-8")


def _post(client, files, **data):
    data = {"periodo": "2026-09", "notificar": "false", **data}
    return cargar_confirmado(client, "/api/analisis-rapido", data=data, files=[("archivos", f) for f in files])


# 1. Carga directa -------------------------------------------------------------------------------

def test_pdf_a_la_carga_directa_responde_422_con_codigo(flujo):
    client, _, _ = flujo
    r = _post(client, [("anexo.pdf", _pdf_tabla(), "application/pdf")])
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["codigo"] == "requiere_revision_lectura" and d["archivos"] == ["anexo.pdf"]
    assert d["url"] == "/api/ocr"
    assert d["mensaje"] == (
        "Los PDF y las imágenes primero se leen y se revisan: abrí la revisión de lectura, "
        "confirmá la tabla y después se analiza."
    )


@pytest.mark.parametrize("nombre,contenido", [("foto.png", _png()), ("foto.jpg", b"\xff\xd8\xff\xe0 algo")])
def test_imagen_a_la_carga_directa_responde_422(flujo, nombre, contenido):
    client, _, _ = flujo
    r = _post(client, [(nombre, contenido, "image/png")])
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "requiere_revision_lectura"


def test_pdf_renombrado_como_excel_tambien_pasa_por_revision(flujo):
    client, _, _ = flujo
    r = _post(client, [("cuadro.xlsx", _pdf_tabla(), "application/octet-stream")])
    assert r.status_code == 422 and r.json()["detail"]["archivos"] == ["cuadro.xlsx"]


def test_carga_mixta_con_pdf_no_analiza_nada_y_nombra_los_archivos(flujo):
    client, factory, _ = flujo
    r = _post(client, [("anexo.pdf", _pdf_tabla(), "application/pdf"), ("prov.csv", _csv(), "text/csv")])
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["archivos"] == ["anexo.pdf"] and d["otros_archivos"] == ["prov.csv"]
    assert d["codigo"] == "requiere_revision_lectura" and d["url"] == "/api/ocr"
    with factory() as db:
        assert db.query(models.Informe).count() == 0


# 2. Excel y CSV siguen entrando directo ---------------------------------------------------------

def test_excel_y_csv_se_analizan_directo(flujo):
    client, factory, _ = flujo
    r = _post(client, [("regiones.xlsx", _xlsx(), "application/vnd.ms-excel"), ("prov.csv", _csv(), "text/csv")])
    assert r.status_code == 200, r.text
    with factory() as db:
        informe = db.get(models.Informe, r.json()["informe_id"])
        assert informe.datos and informe.saneamiento["archivos_origen"] == ["regiones.xlsx", "prov.csv"]
        assert "lectura_revisada" not in informe.saneamiento


# 3. Herramienta de revisión ---------------------------------------------------------------------

def test_pdf_con_texto_se_lee_sin_ocr(monkeypatch):
    def no_ocr(*a, **kw):
        raise AssertionError("un PDF con texto no debe pasar por OCR")

    monkeypatch.setattr(ocr_local, "reconocer", no_ocr)
    r = ocr_local.extraer("matricula.pdf", _pdf_tabla())
    p = r["paginas"][0]
    assert p["metodo"] == "texto_pdf" and p["lectura"] == "texto del PDF"
    t = p["tablas"][0]
    assert t["encabezado"][:2] == ["Nivel", "2021"] and t["filas"][0][:2] == ["Inicial", "1.204"]
    # «1.204» sin otro número que decida el formato: queda ambiguo y marcado para revisar.
    assert t["formato_numerico"] == "ambiguo" and r["indice"][0]["con_texto"]
    assert any("ambiguo" in d["motivo"] for d in t["dudosas"])



def test_celdas_dudosas_ambiguas_sin_rotulo_y_totales():
    enc = ["Concepto", "", "Valor"]
    filas = [["A", "31,821", "10"], ["B", "1.054", "5"], ["Total", "9", "18"]]
    d = ocr_local.celdas_dudosas(enc, filas)
    motivos = {(x["fila"], x["columna"]): x["motivo"] for x in d}
    assert motivos[(-1, 1)].startswith("Columna sin rótulo")
    assert "ambiguo" in motivos[(0, 1)] and "ambiguo" in motivos[(1, 1)]
    assert motivos[(2, 2)].startswith("No suma")
    # Con formato elegido, los números dejan de ser ambiguos.
    assert not any("ambiguo" in x["motivo"] for x in ocr_local.celdas_dudosas(enc, filas, "en"))


def test_completar_hacia_abajo_con_rotulo_centrado_y_al_comienzo():
    centrado = [["", "N"], ["2001", "P"], ["", "T"], ["", "N"], ["2002", "P"], ["", "T"]]
    assert [f[0] for f in ocr_local.completar_hacia_abajo(centrado, 0)] == ["2001"] * 3 + ["2002"] * 3
    arriba = [["2001", "N"], ["", "P"], ["2002", "N"], ["", "P"], ["", "T"]]
    assert [f[0] for f in ocr_local.completar_hacia_abajo(arriba, 0)] == ["2001", "2001", "2002", "2002", "2002"]


def test_csv_revisado_coma_decimal_sin_miles_y_formula_neutralizada():
    csv = ocr_local.csv_revisado(["Concepto", "Valor", "%"], [["=A1", "1.234,5", "12,5"], ["B", "(2.000)", "3"]], "es")
    assert csv.startswith("﻿Concepto;Valor;%\r\n")
    assert "'=A1;1234,5;12,5" in csv and "B;-2000;3" in csv
    assert ocr_local.csv_revisado(["A", "B"], [["x", "1,234.56"]], "en").endswith("x;1234,56\r\n")


def test_api_ocr_acepta_paginas_elegidas(flujo):
    client, _, _ = flujo
    client.app.include_router(ocr.router, prefix="/api")
    r = client.post("/api/ocr/leer", data={"paginas": "1"}, files={"archivo": ("m.pdf", _pdf_tabla(), "application/pdf")})
    assert r.status_code == 200 and r.json()["paginas_seleccionadas"] == [1]
    r = client.post("/api/ocr/leer", data={"paginas": "3"}, files={"archivo": ("m.pdf", _pdf_tabla(), "application/pdf")})
    assert r.status_code == 422


def _pdf_paginas(n):
    from reportlab.pdfgen import canvas

    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i in range(n):
        c.drawString(50, 750, f"Página {i + 1} digital con texto suficientemente extenso para leer sin OCR.")
        c.showPage()
    c.save()
    return b.getvalue()


def test_pdf_con_texto_admite_mas_paginas_y_se_eligen():
    r = ocr_local.extraer("largo.pdf", _pdf_paginas(14))
    assert len(r["indice"]) == 14 and r["paginas_incluidas"] == ocr_local.MAX_PAGINAS_DETALLE and r["cobertura_parcial"]
    r = ocr_local.extraer("largo.pdf", _pdf_paginas(14), ["12", "14"])
    assert [p["pagina"] for p in r["paginas"]] == [12, 14]


# 3c. Analizar la tabla revisada ------------------------------------------------------------------

def _analizar_revisado(client, factory, csv, original="matricula.pdf"):
    r = _post(client, [(f"{Path(original).stem} (revisado).csv", csv.encode("utf-8"), "text/csv")],
              origen_lectura="revision_pdf", archivo_original=original)
    assert r.status_code == 200, r.text
    assert jobs._process_one()
    with factory() as db:
        informe = db.get(models.Informe, r.json()["informe_id"])
        return informe, list(informe.hallazgos), render_reporte_markdown(informe, list(informe.hallazgos), False, False)


def test_csv_revisado_se_analiza_y_el_informe_lo_dice_arriba(flujo):
    client, factory, _ = flujo
    t = ocr_local.extraer("matricula.pdf", _pdf_tabla())["paginas"][0]["tablas"][0]
    csv = ocr_local.csv_revisado(t["encabezado"], t["filas"], t["formato_numerico"])
    informe, _, md = _analizar_revisado(client, factory, csv)
    lr = informe.saneamiento["lectura_revisada"]
    assert lr["origen"] == "revision_pdf" and lr["archivo_original"] == "matricula.pdf" and lr["revisada_por_persona"]
    assert lr["archivo_revisado"] == "matricula (revisado).csv"
    primeras = "\n".join(md.splitlines()[:6])
    assert "Tabla leída de matricula.pdf y revisada por una persona antes de analizar" in primeras


def test_origen_lectura_se_valida(flujo):
    client, _, _ = flujo
    r = _post(client, [("t.csv", _csv(), "text/csv")], origen_lectura="otra_cosa", archivo_original="x.pdf")
    assert r.status_code == 422
    r = _post(client, [("t.csv", _csv(), "text/csv"), ("u.csv", _csv(), "text/csv")],
              origen_lectura="revision_pdf", archivo_original="x.pdf")
    assert r.status_code == 422
    r = _post(client, [("t.csv", _csv(), "text/csv")], origen_lectura="revision_pdf")
    assert r.status_code == 422


# 6. PDF real con años en celdas combinadas -----------------------------------------------------

@pytest.mark.skipif(not PDF_CORPUS.exists(), reason="PDF real del corpus no disponible")
def test_gpsdn_anios_combinados_se_marcan_y_completados_no_dan_periodo_vacio(flujo):
    client, factory, _ = flujo
    r = ocr_local.extraer(PDF_CORPUS.name, PDF_CORPUS.read_bytes(), [53, 54])
    for p in r["paginas"]:
        assert p["metodo"] == "texto_pdf" and p["lectura"] == "texto del PDF"
        t = p["tablas"][0]
        assert t["encabezado"][0] == "Año" and t["columnas_periodo"] == [0]
        vacias = {(d["fila"], d["columna"]) for d in t["dudosas"] if d["motivo"].startswith("Período vacío")}
        assert vacias == {(i, 0) for i, f in enumerate(t["filas"]) if not f[0]}
        # Desde 0.9.19 el año de la celda combinada en vertical (entre dos bordes de la cuadrícula) se
        # completa en cada fila del grupo al leer: ya no quedan años vacíos para completar a mano.
        assert not vacias and [f[0] for f in t["filas"][:4]] == ["2001", "2001", "2001", "2002"]
    t = r["paginas"][0]["tablas"][0]
    filas = ocr_local.completar_hacia_abajo(t["filas"], 0)
    assert all(f[0] for f in filas) and filas[0][:2] == ["2001", "Nación"] and filas[3][:2] == ["2002", "Nación"]
    assert not any(d["motivo"].startswith("Período vacío") for d in ocr_local.celdas_dudosas(t["encabezado"], filas))
    csv = ocr_local.csv_revisado(t["encabezado"], filas, t["formato_numerico"])
    informe, hallazgos, md = _analizar_revisado(client, factory, csv, PDF_CORPUS.name)
    assert all(str(f.get("Año") or "").strip() not in {"", "None", "nan"} for f in informe.datos)
    # Sin completar, el motor da una alarma ALTA «Período None» por cada fila sin año (40 en esta página).
    texto = " ".join(h.descripcion for h in hallazgos)
    assert not re.search(r"per[ií]odo (vac[ií]o|None)", texto, re.I)
    assert not any("periodo" in (h.evidencia or {}) and (h.evidencia or {})["periodo"] is None and h.severidad == "alta"
                   for h in hallazgos)
    assert f"Tabla leída de {PDF_CORPUS.name} y revisada por una persona" in md
