"""Casos de la octava medición (14/10/2026): lecturas que fallaban en silencio."""

import io

from openpyxl import Workbook

from services import carga_archivos, cobertura_cifras, excel_cobertura
from services.controles_excel import periodos
from services.controles_excel.tablas_planas import _anio_rotulo
from services.reportes import registro


def _csv(texto):
    return texto.replace("\n", "\r\n").encode("utf-8")


def test_comilla_sin_cerrar_se_declara_como_cifras_sin_incorporar():
    contenido = _csv(
        "Sucursal;2019;2020;2021\n"
        "Rosario;2858,4;2925,1;2752,9\n"
        '"Paraje El Sauce;2374,4;2221,5;2245,1\n'
        "Tucumán;1636,3;1686,1;1643,6\n"
        "Total;6869,1;6832,7;6641,6\n"
    )
    datos, _ = carga_archivos._leer_csv_con_lectura(contenido, "a.csv")
    for f in datos:
        f["archivo_origen"] = "a.csv"
    [r] = cobertura_cifras.por_archivo([("a.csv", contenido)], datos)
    assert r["en_archivo"] == 12 and r["sin_incorporar"] >= 3 and r["declarar"]


def test_csv_correcto_con_miles_entre_comillas_no_declara():
    contenido = _csv('"Año","Mar del Plata","Tandil"\n"2017","229,720","20,794"\n"2018","230,258","20,838"\n')
    datos, _ = carga_archivos._leer_csv_con_lectura(contenido, "k.csv")
    for f in datos:
        f["archivo_origen"] = "k.csv"
    [r] = cobertura_cifras.por_archivo([("k.csv", contenido)], datos)
    assert r["sin_incorporar"] == 0 and not r["declarar"]


def test_registro_declara_las_cifras_perdidas_al_comienzo():
    informe = {"datos": [{"x": 1}], "saneamiento": {"cobertura_cifras": [
        {"archivo": "a.csv", "en_archivo": 56, "sin_incorporar": 28, "ejemplos": ["fila 6: «2374,4»"], "declarar": True}]}}
    reg = registro.construir(informe, [], {})
    assert reg["estado"] == "parcial" and "28 de 56 cifras del archivo" in reg["primera_linea"]


def test_pdf_cifras_del_texto_contra_la_tabla():
    texto = "Cuadro 2. Actas\nInfracción 2024 2025 Var.\nVelocidad 125.510 125.204 −0,2\nSemáforo 28.506 26.511 −7\nComuna 7 1.804 1.910 −1"
    originales = cobertura_cifras.cifras_texto(texto)
    assert "-7" in originales and "7" not in originales  # «Comuna 7» es rótulo
    # La tabla revisada escribe «1.804» como «1804»: no es un año.
    leidas = cobertura_cifras.cifras_tabla(["Infracción", "2024", "2025", "Var."], [
        ["Velocidad", "125510", "125204", "-0,2"], ["Semáforo", "28506", "26511", ""], ["Comuna 7", "1804", "1910", "-1"]])
    comp = cobertura_cifras.comparar(originales, leidas, cobertura_cifras.todas_las_cifras(texto))
    assert comp["faltan"] == 1 and comp["ejemplos_faltan"] == ["-7"] and comp["ajenas"] == 0


def test_pagina_sin_cuadros_con_cifras_avisa():
    comp = cobertura_cifras.comparar(["10.111", "10.379", "6.587", "6.718", "5.635", "5.765"], [])
    assert "No se reconoció ningún cuadro" in cobertura_cifras.aviso_pagina(comp, 0)


def test_signo_de_otra_fuente_queda_en_su_fila():
    palabras = [{"text": "Semáforo", "top": 99.2, "x0": 10, "x1": 60}, {"text": "26.511", "top": 99.4, "x0": 575, "x1": 600},
                {"text": "-7", "top": 97.1, "x0": 651, "x1": 656}, {"text": "Velocidad", "top": 84.0, "x0": 10, "x1": 60}]
    filas = carga_archivos._filas_por_posicion_pdf(palabras)
    assert [[w["text"] for w in f] for f in filas] == [["Velocidad"], ["Semáforo", "26.511", "-7"]]


def test_mes_con_de_y_total_al_pie_del_eje():
    assert periodos.leer("enero de 2025")["sub"] == 1
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio"]
    eje = periodos.leer_eje([m + " de 2025" for m in meses] + ["Total 2025"])
    assert eje["frecuencia"] == "mensual" and eje["periodos"][-1] is None


def test_anio_repetido_renombrado_en_la_revision():
    assert _anio_rotulo("2024 · 2024") == 2024 and _anio_rotulo("2024") == 2024
    assert _anio_rotulo("Concepto · Región") == "Concepto · Región"


def test_encabezado_repetido_a_mitad_del_csv():
    contenido = _csv("Natatorio;2019;2020\nSarmiento;30483;29944\nChacabuco;19124;18589\n\n"
                     "Natatorio;2019;2020\nCostanera;13505;12973\nTotal;63112;61506\n")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "p.csv")
    assert [f["Natatorio"] for f in datos] == ["Sarmiento", "Chacabuco", "Costanera", "Total"]
    assert any("encabezado se repite" in a for a in info["avisos"])


def test_rotulo_en_celda_combinada_vertical():
    wb = Workbook()
    ws = wb.active
    ws.title = "Obras"
    ws.append(["Obras de cloacas"])
    ws.append(["Tipo", "Región", 2023, 2024, 2025])
    ws.append(["Conexiones", "AMBA", 34, 69, 260])
    ws.append([None, "Interior", 140, 67, 255])
    ws.append(["Renovación", "AMBA", 259, 50, 174])
    ws.append([None, "Interior", 207, 60, 148])
    ws.append(["Total", None, 640, 246, 837])
    ws.merge_cells("A3:A4")
    ws.merge_cells("A5:A6")
    buffer = io.BytesIO()
    wb.save(buffer)
    filas, meta = excel_cobertura.leer_libro(buffer.getvalue(), "o.xlsx")
    grupos = [f.get("Tipo") for f in filas if f.get("Región") == "Interior"]
    assert grupos == ["Conexiones", "Renovación"]
    avisos = " ".join(a for h in meta["hojas"] for a in h.get("avisos_lectura") or [])
    assert "celda combinada en vertical" in avisos
