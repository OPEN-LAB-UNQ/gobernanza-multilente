"""Motor 0.10.18: llamadas de nota en el encabezado, paneles completos y filas de resultado con signo libre."""
import io

import openpyxl

from services.controles_excel import periodos as P
from services.controles_excel.series import admite_signo


def test_llamada_de_nota_sola_no_es_un_periodo():
    for v in ("(1)", "(2)", "(a)", "(*)", "²", " (3) "):
        assert P.es_llamada(v), v
    for v in ("2019", "(1) 2019", "2023 (p)", "Total", 2019):
        assert not P.es_llamada(v), v


def test_filas_de_resultado_admiten_cualquier_signo():
    assert admite_signo("III. Ahorro Corriente (I-II)")
    assert admite_signo("V. Necesidad de financiamiento (III - IV)")
    assert not admite_signo("Otros tributarios")
    assert not admite_signo("Gastos corrientes")


def test_columna_de_llamada_entre_anios_no_genera_vacios(tmp_path):
    """Encabezado 2018 2019 (1) 2020 con la columna «(1)» vacía: antes, «período −1» con una celda vacía por fila."""
    from services import carga_archivos, controles_excel, excel_cobertura
    from services.sanitizacion import sanear

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tasa de desocupación por aglomerado (%)"])
    ws.append([])
    ws.append(["Aglomerado", 2017, 2018, 2019, "(1)", 2020, 2021])
    for k, nombre in enumerate(["Córdoba", "Rosario", "Mendoza", "Salta", "Neuquén", "Tucumán"]):
        ws.append([nombre, 8.1 + k, 8.4 + k, 9.0 + k, None, 11.2 + k, 9.6 + k])
    buf = io.BytesIO()
    wb.save(buf)
    contenido = buf.getvalue()
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("tasa.xlsx", contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(datos, cobertura, lambda f: (f, {}), sanear)
    hs = controles_excel.analizar([("tasa.xlsx", contenido)], saneados, reporte["excel"])
    assert not [h for h in hs if (h.get("evidencia") or {}).get("regla") == "vacio_interior"]
    assert not [h for h in hs if str((h.get("evidencia") or {}).get("periodo")).startswith("-")]
