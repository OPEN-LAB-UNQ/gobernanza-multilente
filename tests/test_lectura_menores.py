"""BOM en el rótulo, orden de columnas, filas de fuente en CSV y marcas de sin dato."""
import io

from openpyxl import Workbook

from services import carga_archivos, sanitizacion
from services.perfilado import numero


def test_bom_no_queda_dentro_del_nombre_de_columna():
    contenido = "﻿Concepto;2023;2024\nPersonal;1772343,91;2309004,70\nBienes;3302779,02;4715055,61\n".encode("utf-8")
    filas = carga_archivos.parse_archivo("bom.csv", contenido)
    assert list(filas[0]) == ["Concepto", "2023", "2024"]
    assert filas[0]["2023"] == 1772343.91
    saneados, _ = sanitizacion.sanear([{"﻿Concepto": "x", "2023": 1}])
    assert list(saneados[0]) == ["Concepto", "2023"]


def test_sanear_conserva_el_orden_original_de_las_columnas():
    datos = [{"Concepto": "A", "2024": 3, "2019": 1, "2020": 2, "Nota": "n"}]
    saneados, reporte = sanitizacion.sanear(datos)
    assert list(saneados[0]) == ["Concepto", "2024", "2019", "2020", "Nota"]
    # Determinista: el mismo resultado en cada corrida, no el orden de un conjunto.
    assert [list(sanitizacion.sanear(datos)[0][0]) for _ in range(5)] == [list(saneados[0])] * 5


def test_fila_fuente_de_un_csv_no_es_un_dato():
    contenido = (
        "Concepto\t2023\t2024\nPersonal\t1.234,5\t1.300,0\nBienes\t2.000,0\t2.100,0\n"
        "Fuente: un ministerio\n"
    ).encode("latin1")
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("gasto.csv", contenido)])
    assert [f["Concepto"] for f in datos] == ["Personal", "Bienes"]
    assert lectura[0]["filas_nota"] == [{"fila": 4, "texto": "Fuente: un ministerio"}]


def test_guion_y_sd_son_sin_dato_y_se_declaran():
    wb = Workbook()
    for fila in [["Concepto", 2019, 2020, 2021], ["Personal", 100, 110, 120], ["Bienes", 50, "-", 60],
                 ["Servicios", 30, 33, "s/d"], ["Total", 180, 143, 180]]:
        wb.active.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("gasto.xlsx", buf.getvalue())])
    hoja = cobertura["hojas"][0]
    assert hoja["celdas_sin_dato"] == {"celdas": 2, "ejemplos": ["C3", "D4"]}
    assert any("sin dato" in a and "no como cero" in a for a in hoja["advertencias"])
    # La celda se conserva tal cual y el lector numérico la trata como sin dato, no como valor.
    assert datos[1]["2020"] == "-" and numero(datos[1]["2020"]) is None
    assert numero("s/d") is None and numero("n/d") is None
