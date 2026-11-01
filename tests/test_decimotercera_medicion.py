"""Casos de la decimotercera medición (16/10/2026)."""

import datetime as dt
import io
from types import SimpleNamespace

from openpyxl import Workbook
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from services import carga_archivos, ocr_local
from services.estructura_revision import preparar as preparar_estructura
from services.reportes.markdown import _con_lectura_revisada

# CSV ---------------------------------------------------------------------------------------------


def test_punto_ambiguo_se_declara_con_un_ejemplo_del_archivo():
    contenido = ("Central;2023;2024;2025\nNorte;17.567;18.604;17.935\nSur;12.345;12.910;13.002\n"
                 "Total;29.912;31.514;30.937\n").encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "t.csv")
    [p] = info["pendientes_lectura"]
    assert p["tipo"] == "no_controlado" and "«17.567»" in p["motivo"] and "punto" in p["motivo"]
    assert not any("«1.738»" in a for a in info["avisos"])


def test_punto_con_evidencia_no_se_declara():
    contenido = "Central;2024;2025\nNorte;1.234.567;18.604\nSur;12.345;12.910\n".encode("utf-8")
    _, info = carga_archivos._leer_csv_con_lectura(contenido, "t.csv")
    assert not info.get("pendientes_lectura")


def test_csv_de_r_con_nombres_de_fila():
    contenido = ('"2017";"2018";"2019"\n"AMBA";5642;5955;5821\n"Centro";4048;4137;4053\n'
                 '"NOA";1210;1250;1301\n').encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "r.csv")
    assert len(datos) == 3 and datos[0]["2018"] == 5955
    assert any("exporta R" in a for a in info["avisos"])


# Excel -------------------------------------------------------------------------------------------


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    for f in filas:
        ws.append(list(f))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_anios_guardados_como_fechas_y_duraciones():
    filas = [["Región"] + [dt.datetime(a, 1, 1) for a in range(2021, 2025)],
             ["Norte", dt.timedelta(hours=9, minutes=45), 10, 11, 12], ["Sur", 4, 5, 6, 7]]
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("a.xlsx", _xlsx(filas))])
    avisos = " ".join(cobertura["hojas"][0].get("avisos_lectura") or [])
    assert "años como fechas" in avisos and "duración" in avisos
    norte = next(d for d in datos if d.get("Región") == "Norte")
    assert norte["2021"] == 9.75 and norte["2022"] == 10


# PDF ---------------------------------------------------------------------------------------------


def test_texto_ilegible():
    assert ocr_local._texto_ilegible("&XDGUR\x03\x14\x11\x03(QVD\\RV\x03FOtQLFRV\x03\x15\x13\x14\x1a" * 3)
    assert not ocr_local._texto_ilegible("Cuadro 3. Ensayos clínicos por especialidad. 2017-2025 Oncología 214 220")
    assert not ocr_local._texto_ilegible("1.204 1.250 1.301 2.405 2.410 2.522 3.333 3.444 3.555 4.010 4.020")


def _pdf_con_adjunto():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.drawString(40, 540, "Cuadro 2. Focos de aftosa notificados por provincia. 2023-2025")
    for i, fila in enumerate((("Provincia", "2023", "2024", "2025"), ("Salta", "12", "14", "13"),
                              ("Jujuy", "8", "9", "11"), ("Total", "20", "23", "24"))):
        for j, v in enumerate(fila):
            c.drawString(40 + 90 * j, 500 - 20 * i, v)
    c.showPage()
    c.save()
    w = PdfWriter()
    w.append(PdfReader(io.BytesIO(buf.getvalue())))
    w.add_attachment("serie_2015_2025.csv", b"Provincia;2015;2016\nSalta;10;11\n")
    salida = io.BytesIO()
    w.write(salida)
    return salida.getvalue()


def test_adjuntos_del_pdf_se_avisan_y_viajan_al_informe():
    r = ocr_local.extraer("aftosa.pdf", _pdf_con_adjunto())
    assert r["adjuntos"] == ["serie_2015_2025.csv"] and not r["cobertura_parcial"]
    [p] = r["paginas"]
    assert "adjunto" in p["aviso_cifras"]
    assert all("serie_2015_2025.csv" in t["cifras_pagina"]["fuera_del_texto"] for t in p["tablas"])


def test_tabla_leida_con_ocr_lo_dice_arriba_del_informe():
    from services.reporte_ejecutivo import lineas

    informe = SimpleNamespace(id=3, datos=[], periodo=None, creado_en=dt.datetime(2026, 10, 16), hallazgos=[],
                              devolucion=None,
                              saneamiento={"lectura_revisada": {"archivo_original": "aulas.pdf", "origen": "revision_ocr"}})
    assert "**Tabla leída con OCR de aulas.pdf" in "\n".join(lineas(informe, []))
    assert "**Tabla leída con OCR de aulas.pdf" in _con_lectura_revisada("# Informe\nresto", informe)


# Estructura --------------------------------------------------------------------------------------


def test_bloques_apilados_dicen_por_que_no_hay_cierres():
    serie = dict(archivo="v.csv", hoja="v", cuadro=1, nivel=0, periodos=[2021, 2022, 2023, 2024],
                 celdas=["B2", "C2", "D2", "E2"], valores=[1, 2, 3, 4], unidad=None, total_en_otra_columna=True)
    r = preparar_estructura([dict(serie, etiqueta="Nacimientos"), dict(serie, etiqueta="Defunciones", celdas=["B3", "C3", "D3", "E3"])])
    assert "bloques apilados" in r["motivo_sin_cierres"]


def _subtotales_trimestrales(alterar=0):
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun"]
    regiones = [("Norte", 100), ("Sur", 80), ("Centro", 150)]
    cabecera = ["Región", *meses[:3], "1.er trim.", *meses[3:], "2.º trim.", "Total semestre"]
    filas = [cabecera]
    for k, (n, b) in enumerate(regiones):
        v = [b + 3 * i + k for i in range(6)]
        filas.append([n, *v[:3], sum(v[:3]), *v[3:], sum(v[3:]), sum(v)])
    total = ["Total"] + [sum(f[j] for f in filas[1:]) for j in range(1, len(cabecera))]
    filas[1][4] += alterar  # el subtotal del primer trimestre de «Norte» (E4) no suma sus meses
    return [["Cuadro 1. Consultas por región. 2025, por mes"], []] + filas + [total]


def _controles(filas):
    from routers.carga_rapida import _aplicar_alcance_series
    from services import controles_excel, excel_cobertura, sanitizacion

    contenido = _xlsx(filas)
    datos, cobertura, _ = carga_archivos.parse_archivos_con_lectura([("t.xlsx", contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(
        datos, cobertura, lambda f: _aplicar_alcance_series(f, "todas"), sanitizacion.sanear)
    return controles_excel.analizar([("t.xlsx", contenido)], saneados, reporte["excel"]), reporte["excel"]


def test_subtotales_trimestrales_se_controlan_contra_sus_meses():
    hallazgos, excel = _controles(_subtotales_trimestrales())
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "subtotal_columna_no_cierra"]
    cierres = excel["estructura_revision"]["cierres_verificados"]
    assert any(c.get("origen") == "subtotal_columna" for c in cierres)
    hallazgos, _ = _controles(_subtotales_trimestrales(alterar=500))
    [h] = [h for h in hallazgos if h["evidencia"].get("regla") == "subtotal_columna_no_cierra"]
    assert h["evidencia"]["celda"] == "E4"


def test_fechas_reales_no_se_vuelven_anios():
    filas = [["Préstamo", "Monto", "Venc. 1", "Venc. 2", "Venc. 3"]]
    filas += [[f"P{k}", 1000 + k, *(dt.datetime(a, 3, 19) for a in (2024, 2025, 2026))] for k in range(3)]
    filas += [["Total", 3003, dt.datetime(2024, 1, 1), dt.datetime(2025, 1, 1), dt.datetime(2026, 1, 1)]]
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("v.xlsx", _xlsx(filas))])
    assert "años como fechas" not in " ".join(cobertura["hojas"][0].get("avisos_lectura") or [])


def test_subtotales_no_se_controlan_en_promedios_ni_stocks():
    filas = _subtotales_trimestrales()
    cab = filas[2]
    filas.insert(-1, ["Precio promedio"] + [10.0 + (j % 4) for j in range(1, len(cab))])
    filas.insert(-1, ["Stock al cierre"] + [500 + j for j in range(1, len(cab))])
    hallazgos, _ = _controles(filas)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "subtotal_columna_no_cierra"]


def test_columna_final_de_notas_no_es_formato_de_r():
    contenido = "Provincia;2020;2021\nBA;10;20;ok\nCBA;11;21;ok\nSF;12;22;revisar\n".encode("utf-8")
    _, info = carga_archivos._leer_csv_con_lectura(contenido, "n.csv")
    assert not any("exporta R" in a for a in info["avisos"])
