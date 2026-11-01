"""Total de filas que no cierra en una tabla de un solo período (presupuesto contra real)."""
from services.lentes import ajedrecista

REGLA = "total_de_filas_no_cierra"


def _reglas(datos):
    return [h for h in ajedrecista.imposibilidad(datos) if h["evidencia"].get("regla") == REGLA]


def _pvr(real_total=860):
    return [
        {"Rubro": "Ventas", "Presupuesto": 1000, "Real": 1100, "Desvío": 100},
        {"Rubro": "Otros ingresos", "Presupuesto": 100, "Real": 90, "Desvío": -10},
        {"Rubro": "Total ingresos", "Presupuesto": 1100, "Real": 1190, "Desvío": 90},
        {"Rubro": "Costo de ventas", "Presupuesto": 600, "Real": 650, "Desvío": 50},
        {"Rubro": "Gastos de administración", "Presupuesto": 200, "Real": 210, "Desvío": 10},
        {"Rubro": "Total egresos", "Presupuesto": 800, "Real": real_total, "Desvío": real_total - 800},
    ]


def test_total_inflado_se_detecta_en_la_columna_correcta():
    hallazgos = _reglas(_pvr(real_total=2360))
    assert len(hallazgos) == 1
    ev = hallazgos[0]["evidencia"]
    assert ev["columna"] == "Real" and ev["declarado"] == 2360 and ev["calculado"] == 860
    assert ev["columnas_que_cierran"] == ["Presupuesto"]
    assert hallazgos[0]["severidad"] == "alta"


def test_totales_que_cierran_no_generan_senal():
    assert _reglas(_pvr()) == []


def test_sin_otra_columna_que_cierre_no_se_afirma_la_suma():
    datos = _pvr(real_total=2360)
    datos[5]["Presupuesto"] = 5000  # ninguna columna cierra: no hay estructura de suma corroborada
    assert _reglas(datos) == []


def test_grupo_con_subtotales_no_se_evalua():
    datos = [
        {"Rubro": "A", "Presupuesto": 10, "Real": 10},
        {"Rubro": "B", "Presupuesto": 20, "Real": 20},
        {"Rubro": "Subtotal AB", "Presupuesto": 30, "Real": 30},
        {"Rubro": "C", "Presupuesto": 5, "Real": 5},
        {"Rubro": "Total general", "Presupuesto": 35, "Real": 99},
    ]
    # El grupo del total general va desde el subtotal: sólo C, un componente: no se evalúa.
    assert _reglas(datos) == []


def test_tabla_ancha_de_anios_queda_para_la_conciliacion_por_series():
    anios = ["2019", "2020", "2021", "2022"]
    datos = [{"Rubro": r, **{a: v for a in anios}} for r, v in (("A", 1), ("B", 2))]
    datos.append({"Rubro": "Total", **{a: 3 for a in anios}, "2022": 30})
    assert _reglas(datos) == []


def test_columnas_de_porcentaje_no_se_suman():
    datos = [
        {"Rubro": "A", "Monto": 10, "Participación %": 40},
        {"Rubro": "B", "Monto": 15, "Participación %": 60},
        {"Rubro": "Total", "Monto": 25, "Participación %": 70},
    ]
    assert _reglas(datos) == []


def test_columna_de_promedios_o_tasas_no_se_trata_como_suma():
    datos = [
        {"Programa": "A", "Credito": 100, "Ejecucion": 80},
        {"Programa": "B", "Credito": 200, "Ejecucion": 75},
        {"Programa": "Total", "Credito": 300, "Ejecucion": 76.7},
    ]
    assert _reglas(datos) == []


def test_totales_en_plural_y_redondeo_de_muchas_filas():
    filas = [{"Rubro": f"R{i}", "Presupuesto": 1.1, "Real": 1.1} for i in range(40)]
    assert _reglas(filas + [{"Rubro": "Totales", "Presupuesto": 44.0, "Real": 47.0}])  # 3 de 44: no es redondeo
    assert not _reglas(filas + [{"Rubro": "Totales", "Presupuesto": 44.0, "Real": 44.9}])  # 40 × 0,05 = 2
