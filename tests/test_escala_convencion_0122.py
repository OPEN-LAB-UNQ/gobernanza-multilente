"""Motor 0.10.22: un valor repetido en varias filas y la columna «Total» no son errores de escala."""
import io

import openpyxl


def _fuera_de_escala(encabezado, filas):
    from services import carga_archivos, controles_excel, excel_cobertura
    from services.sanitizacion import sanear

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Deuda por instrumento (en millones de U$S)"])
    ws.append(["Instrumento", "Moneda", encabezado, "Intereses"])
    for f in filas:
        ws.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    contenido = buf.getvalue()
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("deuda.xlsx", contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(datos, cobertura, lambda f: (f, {}), sanear)
    hs = controles_excel.analizar([("deuda.xlsx", contenido)], saneados, reporte["excel"])
    return [h for h in hs if (h.get("evidencia") or {}).get("regla") == "valor_fuera_de_escala_columna"]


BONOS = [[f"Bono {k}", "U$S", 1520.0 + 37 * k, 12.0 + k] for k in range(8)]


def test_un_residuo_repetido_en_varias_filas_es_una_convencion():
    filas = BONOS + [[f"Bono residual {k}", "U$S", 0.00001, 1.0] for k in range(3)]
    assert _fuera_de_escala("Capital", filas) == []


def test_un_valor_suelto_fuera_de_escala_se_sigue_marcando():
    filas = BONOS + [["Bono residual", "U$S", 0.00001, 1.0]]
    assert _fuera_de_escala("Capital", filas)
