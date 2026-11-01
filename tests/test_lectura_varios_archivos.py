"""Varios archivos: cada uno es un bloque con su origen; un archivo que falla no tumba la carga."""
import io

from routers.carga_rapida import _aplicar_alcance_series
from services import carga_archivos, excel_cobertura, sanitizacion

CSV_A = "Concepto;2023;2024\nPersonal;1.234,5;1.300,0\nBienes;2.000,0;2.100,0\nTotal;3.234,5;3.400,0\n".encode()
CSV_B = "Indicador,2023,2024\nTasa,0.125,0.118\nCobertura,0.612,0.623\nEscolaridad,9.875,9.912\n".encode()


def _pdf_sin_texto() -> bytes:
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_filas_de_csv_dicen_de_que_archivo_salen_y_forman_bloques_propios():
    datos, cobertura, _ = carga_archivos.parse_archivos_con_lectura([("a.csv", CSV_A), ("b.csv", CSV_B)])
    assert [f["archivo_origen"] for f in datos] == ["a.csv"] * 3 + ["b.csv"] * 3
    assert [(b["archivo"], b["inicio"], b["fin"]) for b in cobertura["bloques"]] == [("a.csv", 0, 3), ("b.csv", 3, 6)]
    # Cada archivo se normaliza y sanea por separado: las columnas de uno no aparecen en el otro.
    saneados, reporte, _ = excel_cobertura.preparar(
        datos, cobertura, lambda f: _aplicar_alcance_series(f, "todas"), sanitizacion.sanear
    )
    assert "Indicador" not in saneados[0] and "Concepto" not in saneados[-1]
    assert saneados[-1]["2023"] == 9.875


def test_un_pdf_escaneado_no_rechaza_toda_la_carga_y_queda_nombrado():
    datos, cobertura, lectura = carga_archivos.parse_archivos_con_lectura(
        [("a.csv", CSV_A), ("escaneado.pdf", _pdf_sin_texto())]
    )
    assert len(datos) == 3
    fallido = next(a for a in lectura if a["archivo"] == "escaneado.pdf")
    assert fallido["estado"] == "fallido"
    assert "escaneo" in fallido["motivo"] and "OCR" in fallido["motivo"]
    texto = " ".join(excel_cobertura.resumen_lineas(cobertura))
    assert "Archivos: 1 de 2 leídos" in texto
    assert "escaneado.pdf: no se procesó" in texto
    assert any("escaneado.pdf" in a for a in carga_archivos.avisos_lectura(lectura))


def test_si_ningun_archivo_se_lee_la_carga_se_rechaza_nombrando_cada_uno():
    import pytest

    with pytest.raises(carga_archivos.ArchivoNoSoportado, match="Ningún archivo"):
        carga_archivos.parse_archivos_con_lectura([("x.pdf", _pdf_sin_texto()), ("y.pdf", _pdf_sin_texto())])
