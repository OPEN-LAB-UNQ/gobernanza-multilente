"""Casos de la duodécima medición (15/10/2026)."""

import io
import json

from openpyxl import Workbook
from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import models
from routers.carga_rapida import (
    _aplicar_alcance_series,
    _celdas_marcadas_revision,
    _cifras_revision,
    _lectura_revisada,
    _marcar_lectura_dudosa,
)
from services import (
    carga_archivos,
    casos_revision,
    cobertura_cifras,
    controles_excel,
    excel_cobertura,
    ocr_local,
    sanitizacion,
)
from services.controles_excel import periodos, tablas_planas
from services.reportes.registro import construir

# CSV ---------------------------------------------------------------------------------------------


def test_lineas_enteras_entre_comillas_se_separan():
    contenido = ('Provincia;2023;2024;2025\r\n"Buenos Aires;4,8;5,1;5,3"\r\n"Córdoba;2,1;2,2;2,4"\r\n'
                 '"Total;6,9;7,3;7,7"\r\n').encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "b.csv")
    assert [f["Provincia"] for f in datos] == ["Buenos Aires", "Córdoba", "Total"]
    assert datos[0]["2024"] == 5.1 and info["lineas_desenvueltas"] == [2, 3, 4]
    assert any("enteras entre comillas" in a for a in info["avisos"])


def test_textos_entre_comillas_no_se_desenvuelven():
    texto = 'Cuadro 1,,\n"Nota; datos provisorios"\nRubro,2024,2025\nA,1,2\n"Fuente; instituto de estadística"\n'
    assert carga_archivos.desenvolver_lineas_csv(texto) == (texto, [])
    # Título y fuente de una celda con tantos «;» como el encabezado (así los escribe csv.writer).
    texto = ('"Cuadro 1; Casos por provincia; 2023-2024"\nProvincia;2023;2024\nSalta;12;13\nJujuy;8;9\n'
             '"Fuente: instituto de estadística; encuesta de hogares; 2024"\n')
    assert carga_archivos.desenvolver_lineas_csv(texto) == (texto, [])
    # Notas de texto en un bloque al final: sin cifras, no son datos.
    texto = 'Provincia;Casos\nSalta;12\n"Nota;a"\n"Fuente;b"\n"Aclaración;c"\n"Contacto;d"\n'
    assert carga_archivos.desenvolver_lineas_csv(texto) == (texto, [])


def test_columna_de_periodo_parcial_en_un_csv_se_declara():
    contenido = ("Reserva;2021;2022;2023;2024;Ene-jun 2025\n"
                 "Costanera;120;131;140;152;80\nRibera;95;99;104;110;57\nTotal;215;230;244;262;137\n").encode("utf-8")
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("r.csv", contenido)])
    for _ in range(2):  # un reanálisis no la declara dos veces
        tablas_planas.analizar([("r.csv", contenido)], datos, lectura, lambda f: (f, {}), sanitizacion.sanear)
    [p] = [p for p in lectura[0]["pendientes_lectura"] if "Ene-jun 2025" in p["donde"]]
    assert p["tipo"] == "no_controlado" and "período" in p["motivo"]


# Períodos y columnas auxiliares --------------------------------------------------------------------


def test_meses_en_codigo_sdmx():
    p = periodos.leer("2025M01")
    assert p["frecuencia"] == "mensual" and p["anio"] == 2025 and p["sub"] == 1
    assert periodos.leer("2025M12")["sub"] == 12 and periodos.leer("2025-03")["sub"] == 3


def test_columnas_auxiliares():
    for rotulo in ("CV (%)", "C.V.", "C.V. (%) 2021", "Coef. de variación", "Error estándar", "Var. %", "IC 95 %", "%"):
        assert periodos.es_auxiliar(rotulo), rotulo
    for rotulo in ("2021", "Buenos Aires", "Total", "Región", 2021, None):
        assert not periodos.es_auxiliar(rotulo), rotulo


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.title = "Cuadro 2"
    for f in filas:
        ws.append(list(f))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_columnas_cv_entre_los_anios_no_son_periodos():
    filas = [["Región", 2021, "CV (%)", 2022, "CV (%)", 2023, "CV (%)", 2024, "CV (%)"]]
    filas += [[n, b, 4.1, b + 3, 3.9, b + 5, 4.4, b + 9, 4.0] for n, b in (("Norte", 120), ("Sur", 95), ("Centro", 210))]
    filas.append(["Total", 425, 2.2, 436, 2.1, 445, 2.5, 461, 2.4])
    contenido = _xlsx(filas)
    datos, cobertura, _ = carga_archivos.parse_archivos_con_lectura([("cv.xlsx", contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(
        datos, cobertura, lambda f: _aplicar_alcance_series(f, "todas"), sanitizacion.sanear)
    [hoja] = reporte["excel"]["hojas"]
    [aux] = [c for c in hoja["columnas_no_controladas"] if "auxiliares" in c["motivo"]]
    assert aux["letra"] == "C, E, G, I" and aux["columna"] == "CV (%)"
    assert not any("Encabezados repetidos" in a for a in hoja.get("avisos_lectura") or [])
    hallazgos = controles_excel.analizar([("cv.xlsx", contenido)], saneados, reporte["excel"])
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "anio_no_entero"]
    lectura = controles_excel.cobertura_lectura([("cv.xlsx", contenido)], saneados, reporte["excel"])
    assert "íntegramente" not in json.dumps(lectura, ensure_ascii=False)
    informe = models.Informe(id=1, datos=saneados, saneamiento={"excel": reporte["excel"]}, periodo="2026-10")
    assert any("auxiliares" in p["motivo"] for p in construir(informe, [], {})["pendientes"])


# PDF: rótulos y página a dos columnas -------------------------------------------------------------


def _w(texto, x0, x1, top=100.0):
    return {"text": texto, "x0": x0, "x1": x1, "top": top}


def test_mar_del_plata_no_pierde_mar():
    arriba = [_w("Mendoza", 525.7, 559.9), _w("Mar", 580.6, 594.8), _w("del", 597.0, 608.6), _w("Plata", 610.8, 629.9)]
    rangos = [(546.6, 559.9), (616.6, 629.9)]
    assert carga_archivos._rotulos_de_columna_pdf([arriba], rangos) == ["Mendoza", "Mar del Plata"]


class _Pagina:
    def __init__(self, palabras):
        self.palabras = palabras

    def extract_words(self, **_):
        return self.palabras


def _prosa(top, n, x=330.0):
    salida = []
    for k in range(n):
        salida.append(_w(f"palabra{k}", x, x + 30, top))
        x += 33
    return salida


def test_pagina_a_dos_columnas_no_suma_la_columna_de_texto():
    columnas = (100, 140, 180, 220, 260)
    palabras = [_w("Provincia", 10, 60, 80)] + [_w(str(2021 + k), x, x + 25, 80) for k, x in enumerate(columnas)]
    filas = [("Buenos", "Aires", 100), ("Santa", "Fe", 130), ("Entre", "Ríos", 160), ("La", "Pampa", 190)]
    for k, (a, b, top) in enumerate(filas):
        palabras += [_w(a, 10, 45, top), _w(b, 48, 80, top)]
        palabras += [_w(f"{900 + 10 * k + j}", x, x + 25, top) for j, x in enumerate(columnas)]
        palabras += _prosa(top, 5)  # renglón de la columna vecina a la altura de la fila
        if top < 190:
            palabras += _prosa(top + 15, 9)  # renglón de la columna vecina entre dos filas
    palabras += _prosa(215, 9) + _prosa(230, 9)  # la columna vecina sigue debajo del cuadro
    grilla = carga_archivos._grilla_por_coordenadas_pdf(_Pagina(palabras))
    assert grilla[0] == ["Provincia", "2021", "2022", "2023", "2024", "2025"]
    assert all(len(f) == 6 for f in grilla) and grilla[1][0] == "Buenos Aires"


def test_columna_observaciones_no_es_la_columna_vecina():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setFont("Helvetica", 8)
    c.drawString(40, 560, "Cuadro 5. Obras por provincia. En millones de pesos")
    for j, t in enumerate(("Provincia", "2022", "2023", "2024")):
        c.drawString(40 + 90 * j, 530, t)
    c.drawString(420, 530, "Observaciones")
    filas = [("Salta", "1.210", "1.250", "1.300", "obra finalizada con", "recepcion provisoria emitido por la direccion provincial de vialidad"),
             ("Jujuy", "820", "860", "900", "obra en ejecucion", "contratista y verificado por la inspeccion de obra del organismo"),
             ("Tucuman", "2.100", "2.150", "2.230", "obra paralizada por", "aprobacion por parte de la autoridad de aplicacion del contrato"),
             ("Total", "4.130", "4.260", "4.430", "", "")]
    y = 505
    for f in filas:
        for j in range(4):
            c.drawString(40 + 90 * j, y, f[j])
        c.drawString(420, y, f[4])
        c.drawString(420, y - 11, f[5])
        y -= 30
    c.showPage()
    c.save()
    import pdfplumber

    with pdfplumber.open(io.BytesIO(buf.getvalue())) as pdf:
        grilla = carga_archivos._grilla_por_coordenadas_pdf(pdf.pages[0])
    assert grilla[0][-1] == "Observaciones"


# Señales sobre celdas declaradas como mal leídas ---------------------------------------------------


def test_celdas_ajenas_por_posicion():
    filas = [["Norte", "12", "13"], ["Sur", "55.488377", "15"]]
    assert cobertura_cifras.celdas_ajenas(filas, ["12", "13", "15", "5.487", "8.377"]) == [(1, 1)]


def test_celdas_de_lectura_y_no_las_del_original():
    csv = "Región;Columna 2;2017;2018\r\nNorte;;12;13\r\nSur;5;14;15\r\nTotal;5;30;28\r\n".encode("utf-8")
    marcas = _celdas_marcadas_revision([("x (revisado).csv", csv)])
    assert "B1" in marcas["celdas_lectura"]  # rótulo genérico puesto en la revisión
    assert "C4" not in marcas["celdas_lectura"]  # un total que no suma es un error del original


def test_senal_sobre_celdas_mal_leidas_no_llega_como_alta():
    h = {"evidencia": {"regla": "cambio_tipo", "hoja": "x (revisado).csv", "celda": "E3"}}
    otra = {"evidencia": {"regla": "cambio_tipo", "hoja": "x (revisado).csv", "celda": "E4"}}
    assert casos_revision.ejes(h)["prioridad"] == "alta"
    _marcar_lectura_dudosa([h, otra], {"cifras": {"celdas_ajenas": ["E3", "G5"]}})
    assert h["evidencia"]["lectura_dudosa"] and "lectura_dudosa" not in otra["evidencia"]
    ejes = casos_revision.ejes(h)
    assert ejes["prioridad"] == "media" and "mal leídas" in ejes["motivo_tope"]
    assert casos_revision.ejes(otra)["prioridad"] == "alta"


# PDF: lo que la página muestra y no está en su texto ----------------------------------------------


def _pdf_formulario():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setFont("Helvetica", 10)
    c.drawString(40, 540, "Cuadro 3. Existencias de granos en planta, por mes. En miles de toneladas")
    c.drawString(40, 500, "Grano")
    for j, mes in enumerate(("Ene-25", "Feb-25", "Mar-25")):
        c.drawString(180 + 90 * j, 500, mes)
    valores = (("Trigo", ("120.700", "121.654", "120.809")), ("Soja", ("27.844", "28.266", "30.186")),
               ("Total", ("148.544", "149.920", "150.995")))
    for i, (grano, fila) in enumerate(valores):
        y = 475 - 25 * i
        c.drawString(40, y, grano)
        for j, v in enumerate(fila):
            c.acroForm.textfield(name=f"c{i}{j}", value=v, x=170 + 90 * j, y=y - 4, width=70, height=16,
                                 borderWidth=0, fieldFlags="readOnly")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_cifras_en_campos_de_formulario():
    r = ocr_local.extraer("granos.pdf", _pdf_formulario())
    [p] = r["paginas"]
    assert p["campos_formulario"] == 9 and "campos de formulario" in p["aviso_cifras"]
    [t] = p["tablas"]
    assert t["encabezado"] == ["Grano", "Ene-25", "Feb-25", "Mar-25"]
    assert t["filas"][0] == ["Trigo", "120.700", "121.654", "120.809"]
    assert t["cifras_pagina"]["filas"]  # la salvaguarda ve las cifras de los campos


def test_campo_con_el_valor_ya_impreso_no_se_cuenta():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setFont("Helvetica", 10)
    c.drawString(40, 540, "Cuadro 3. Existencias de granos en planta, por mes. En miles de toneladas")
    c.drawString(40, 500, "Trigo")
    c.drawString(180, 500, "120.700")
    c.acroForm.textfield(name="t", value="120.700", x=176, y=496, width=70, height=16, borderWidth=0)
    c.showPage()
    c.save()
    r = ocr_local.extraer("granos.pdf", buf.getvalue())
    assert "campos_formulario" not in r["paginas"][0]


def _pdf_con_imagen(abajo=300, alto=150):
    png = io.BytesIO()
    Image.new("RGB", (600, 150), "white").save(png, format="PNG")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.drawString(40, 300 if abajo > 400 else 540,
                 "En 2025 se registraron 18.087 intervenciones, 4,5 % más que en 2024. El cuadro 4 presenta la serie.")
    c.drawImage(ImageReader(io.BytesIO(png.getvalue())), 40, abajo, width=600, height=alto)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_imagen_sin_cifras_o_membrete_no_se_declara(monkeypatch):
    monkeypatch.setattr(ocr_local, "reconocer", lambda imagen: [{"texto": "Ministerio\tde Seguridad"}])
    [p] = ocr_local.extraer("logo.pdf", _pdf_con_imagen())["paginas"]
    assert "imagen" not in (p.get("aviso_cifras") or "") and not p.get("contenido_sin_leer")

    def no_ocr(imagen):
        raise AssertionError("un membrete no pasa por OCR")

    monkeypatch.setattr(ocr_local, "reconocer", no_ocr)
    [p] = ocr_local.extraer("membrete.pdf", _pdf_con_imagen(abajo=530, alto=60))["paginas"]
    assert not p.get("imagenes_grandes")


def test_cuadro_en_imagen_se_lee_con_ocr(monkeypatch):
    lineas = [{"texto": t} for t in ("Provincia\t2024\t2025", "Norte\t1.200\t1.300", "Sur\t800\t900", "Total\t2.000\t2.200")]
    monkeypatch.setattr(ocr_local, "reconocer", lambda imagen: lineas)
    r = ocr_local.extraer("defensa.pdf", _pdf_con_imagen())
    [p] = r["paginas"]
    assert p["metodo"] == "texto_pdf" and "imagen" in p["aviso_cifras"] and "OCR" in p["aviso_cifras"]
    [t] = [t for t in p["tablas"] if t.get("origen") == "ocr"]
    assert t["encabezado"] == ["Provincia", "2024", "2025"] and t["cifras_pagina"]["filas"]


def test_cuadro_en_imagen_sin_ocr_se_declara(monkeypatch):
    def fallar(imagen):
        raise ocr_local.OCRNoDisponible("OCR local no instalado.")

    monkeypatch.setattr(ocr_local, "reconocer", fallar)
    r = ocr_local.extraer("defensa.pdf", _pdf_con_imagen())
    [p] = r["paginas"]
    assert "no se leyeron" in p["aviso_cifras"] and r["cobertura_parcial"]
    assert "imagen" in p["cifras_pagina"]["fuera_del_texto"]


def test_contenido_fuera_del_texto_llega_al_comienzo_del_informe():
    cifras = {"filas": ["12", "13", "14", "15"], "todas": ["12", "13", "14", "15"], "palabras": [],
              "fuera_del_texto": "la página tiene una imagen que ocupa el 16 % de la página; si contiene un cuadro, "
                                 "sus cifras no están en el texto del PDF y no se leyeron"}
    csv = "Región;2024;2025\r\nNorte;12;13\r\nSur;14;15\r\n".encode("utf-8")
    comp = _cifras_revision(json.dumps(cifras), [("x (revisado).csv", csv)])["cifras"]
    assert comp["fuera_del_texto"].startswith("la página tiene una imagen")
    informe = models.Informe(id=1, datos=[], periodo="2026-10",
                             saneamiento={"lectura_revisada": {"archivo_original": "x.pdf", "cifras": comp}})
    reg = construir(informe, [], {})
    assert any(p["donde"] == "contenido del PDF fuera del texto leído" for p in reg["pendientes"])


def test_tabla_leida_con_ocr_lo_dice_en_la_leyenda():
    leidos = [("x (revisado).csv", b"Region;2024\r\nNorte;12\r\n")]
    assert _lectura_revisada("revision_ocr", "x.pdf", leidos)["leyenda"].startswith("Tabla leída con OCR de x.pdf")
    assert _lectura_revisada("revision_pdf", "x.pdf", leidos)["leyenda"].startswith("Tabla leída de x.pdf")
