"""Motor 0.10.19: años con sus meses en la misma columna y año.mes como número no son «año no entero»."""
from services.controles_excel import temporal


def _validar(periodos):
    return temporal.validar({"archivo": "a.xlsx", "hoja": "H", "cuadro": 1, "etiqueta": "Período",
                             "periodos": periodos, "celdas": [f"A{i + 4}" for i in range(len(periodos))],
                             "valores": periodos})


def test_anios_con_sus_meses_debajo_no_se_marcan_ni_se_comparan_como_una_serie():
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
             "Noviembre", "Diciembre"]
    errores, validos = _validar([2010, *meses, 2011, *meses])
    assert errores == [] and validos is False


def test_anio_punto_mes_se_valida_como_serie_mensual():
    periodos = [2021.04, 2021.05, 2021.06, 2021.07, 2021.08, 2021.09, 2021.1, 2021.11, 2021.12, 2022.01]
    errores, validos = _validar(periodos)
    assert errores == [] and validos is True
    con_repetido = periodos[:6] + [2021.09] + periodos[6:]
    errores, _ = _validar(con_repetido)
    assert [e["evidencia"]["regla"] for e in errores] == ["periodo_duplicado"]


def test_un_anio_con_decimales_sigue_siendo_una_senal():
    errores, _ = _validar([2015, 2016, 2017.5, 2018, 2019])
    assert "anio_no_entero" in [e["evidencia"]["regla"] for e in errores]
