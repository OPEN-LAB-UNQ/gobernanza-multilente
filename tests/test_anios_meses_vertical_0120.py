"""Motor 0.10.20: una columna de años con sus meses debajo no genera «celdas vacías» en las filas de año."""
import io

import openpyxl


def test_filas_de_anio_sin_datos_no_son_celdas_vacias():
    from services import carga_archivos, controles_excel, excel_cobertura
    from services.sanitizacion import sanear

    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
             "Noviembre", "Diciembre"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Usuarios de energía eléctrica por tipo de público"])
    ws.append(["Año", "Total", "Residencial", "Comercial"])
    for k, anio in enumerate((2019, 2020, 2021)):
        ws.append([anio, None, None, None])
        for m, mes in enumerate(meses):
            ws.append([mes, 1_500_000 + 1000 * (12 * k + m), 1_300_000 + 900 * m, 180_000 + 100 * m])
    buf = io.BytesIO()
    wb.save(buf)
    contenido = buf.getvalue()
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("usuarios.xlsx", contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(datos, cobertura, lambda f: (f, {}), sanear)
    hs = controles_excel.analizar([("usuarios.xlsx", contenido)], saneados, reporte["excel"])
    reglas = [(h.get("evidencia") or {}).get("regla") for h in hs]
    assert "vacio_interior" not in reglas and "anio_no_entero" not in reglas
