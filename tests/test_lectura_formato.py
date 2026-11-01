"""El lector se elige por el contenido del archivo, no por su extensión, y queda declarado."""
import io

from openpyxl import Workbook

from services import carga_archivos


def _xlsx():
    wb = Workbook()
    for fila in [["Concepto", "Monto"], ["A", 10], ["B", 20], ["Total", 30]]:
        wb.active.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_renombrado_xls_se_lee_como_xlsx_y_se_declara():
    datos, cobertura, lectura = carga_archivos.parse_archivos_con_lectura([("viejo.xls", _xlsx())])
    assert len(datos) == 3
    assert lectura[0]["tipo_detectado"] == "xlsx"
    assert lectura[0]["tipo_lectura"] == "Excel .xlsx (OOXML)"
    assert any("la extensión es .xls pero el contenido es Excel .xlsx" in a for a in lectura[0]["avisos"])


def test_tipo_por_contenido():
    assert carga_archivos.tipo_por_contenido("a.xls", _xlsx()) == "xlsx"
    assert carga_archivos.tipo_por_contenido("a.csv", b"a;b\n1;2\n") == "csv"
    assert carga_archivos.tipo_por_contenido("exportado.xls", b"Concepto\tMonto\nA\t1\n") == "csv"
    assert carga_archivos.tipo_por_contenido("a.pdf", b"%PDF-1.4\n...") == "pdf"


def test_cada_archivo_declara_el_tipo_de_lectura():
    _, _, lectura = carga_archivos.parse_archivos_con_lectura([("gasto.csv", "a;b\nx;1\ny;2\n".encode())])
    assert lectura[0]["tipo_lectura"] == "texto delimitado (CSV)"
    assert lectura[0]["separador"] == "punto y coma"
