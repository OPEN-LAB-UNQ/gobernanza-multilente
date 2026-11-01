"""Criterio 1 («dice qué no revisó»): casos de la quinta medición que quedaban en silencio (14/10/2026)."""

import io

from openpyxl import Workbook

from services import excel_cobertura
from services.controles_excel import _con_formato, _formatos_texto
from services.reportes import registro


def _libro_texto_punto_miles() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cuadro 1"
    ws.append(["Cuadro 1. Despachos por modalidad"])
    ws.append(["En toneladas"])
    ws.append([])
    ws.append(["Rubro", "2017", "2018", "2019", "2020"])
    ws.append(["En bolsa", "506.809", "475.735", "444.190", "422.603"])
    ws.append(["A granel", "441.680", "449.192", "449.000", "419.603"])
    ws.append(["Exportación", "51.511", "53.116", "54.499", "54.561"])
    ws.append(["Total", "1.000.000", "978.043", "947.689", "896.767"])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_numeros_como_texto_con_un_solo_punto_se_leen_como_miles():
    # Antes pandas convertía «475.735» a 475,735 en las columnas sin un «1.000.000»: en silencio.
    filas, _meta = excel_cobertura.leer_libro(_libro_texto_punto_miles(), "texto.xlsx")
    por_rubro = {f["Rubro"]: f for f in filas}
    assert por_rubro["En bolsa"]["2018"] == 475735
    assert por_rubro["A granel"]["2019"] == 449000
    assert por_rubro["Total"]["2017"] == 1000000


def test_los_controles_por_celda_usan_el_mismo_criterio():
    wb = Workbook()
    ws = wb.active
    for fila in (["475.735"], ["449.192"], ["53.116"]):
        ws.append(fila)
    formatos = _formatos_texto(ws, [1, 2, 3], ["A"])
    assert formatos == {"A": "es"}
    assert _con_formato("475.735", formatos["A"]) == 475735
    assert _con_formato("s/d", formatos["A"]) == "s/d"


class _Informe:
    def __init__(self, saneamiento):
        self.saneamiento = saneamiento
        self.devolucion = None
        self.hallazgos = []
        self.datos = [{"Rubro": "x", "2020": 1}]


def test_cierre_de_totales_no_comprobado_va_al_comienzo():
    informe = _Informe({"archivos_origen": ["unidad.csv"], "estructura_revision": {
        "cantidad_cierres": 0, "relaciones_candidatas": 1,
        "motivo_sin_cierres": "los totales identificados no cierran con sus componentes en suficientes períodos"}})
    reg = registro.construir(informe, [], {})
    assert reg["estado"] != "completo"
    assert any(p["donde"] == "Cierres entre totales y componentes" for p in reg["pendientes"])


def test_sin_totales_en_el_archivo_no_hay_cierre_pendiente():
    informe = _Informe({"archivos_origen": ["sin_total.csv"], "estructura_revision": {
        "cantidad_cierres": 0, "relaciones_candidatas": 0,
        "motivo_sin_cierres": "no se identificó una fila de total con sus componentes dentro de un mismo cuadro"}})
    reg = registro.construir(informe, [], {})
    assert not any(p["donde"] == "Cierres entre totales y componentes" for p in reg["pendientes"])
