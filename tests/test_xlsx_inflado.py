"""Un .xlsx que se infla al abrirse se rechaza antes de leerlo."""
import io
import zipfile

import pytest

from services import carga_archivos


def _zip(archivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in archivos.items():
            z.writestr(nombre, datos)
    return buf.getvalue()


def test_libro_que_se_infla_se_rechaza(monkeypatch):
    monkeypatch.setattr(carga_archivos, "MAX_XLSX_DESCOMPRIMIDO", 5 * 1024 * 1024)
    inflado = _zip({"xl/worksheets/sheet1.xml": b"0" * (6 * 1024 * 1024)})
    assert len(inflado) < 100 * 1024
    with pytest.raises(carga_archivos.ArchivoNoSoportado, match="al abrirse"):
        carga_archivos.parse_archivos_con_cobertura([("bomba.xlsx", inflado)])


def test_archivo_que_no_es_zip_se_rechaza_con_mensaje_claro():
    with pytest.raises(carga_archivos.ArchivoNoSoportado, match="no es un Excel"):
        carga_archivos.validar_xlsx("roto.xlsx", b"esto no es un zip")


def test_un_libro_normal_pasa():
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.append(["Concepto", "Total"])
    wb.active.append(["Ventas", 100])
    buf = io.BytesIO()
    wb.save(buf)
    carga_archivos.validar_xlsx("ok.xlsx", buf.getvalue())
