"""Motor 0.10.23: en una hoja de variaciones el signo distinto queda en media; en otra hoja sigue siendo alta."""
import io

import openpyxl


def _signos(nombre_hoja):
    from services import carga_archivos, controles_excel, excel_cobertura
    from services.sanitizacion import sanear

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = nombre_hoja
    ws.append(["Recursos tributarios"])
    ws.append(["Concepto", 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025])
    ws.append(["Ingresos Brutos", 12.5, 14.1, 9.8, 15.2, 13.7, 11.9, 16.4, 12.2])
    ws.append(["Automotor", 8.2, 7.9, -3.1, 9.4, 8.8, 10.1, 7.5, 8.6])
    ws.append(["Sellos", 5.5, 6.1, 5.9, 6.4, 7.0, 6.6, 6.9, 7.3])
    buf = io.BytesIO()
    wb.save(buf)
    contenido = buf.getvalue()
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("v.xlsx", contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(datos, cobertura, lambda f: (f, {}), sanear)
    hs = controles_excel.analizar([("v.xlsx", contenido)], saneados, reporte["excel"])
    return [h for h in hs if (h.get("evidencia") or {}).get("regla") == "signo_aislado"]


def test_hoja_de_variaciones_registra_el_signo_con_prioridad_media():
    from services.casos_revision import ejes

    hs = _signos("Variaciones_Anual")
    assert hs and all(h["evidencia"].get("en_hoja_de_variaciones") for h in hs)
    assert all(ejes(h)["prioridad"] != "alta" for h in hs)


def test_en_otra_hoja_el_negativo_aislado_se_sigue_marcando():
    hs = _signos("Recaudacion")
    assert hs and not any(h["evidencia"].get("en_hoja_de_variaciones") for h in hs)
