import io
from datetime import datetime
from types import SimpleNamespace

from openpyxl import Workbook

from routers.carga_rapida import _aplicar_alcance_series
from services import carga_archivos, excel_cobertura, sanitizacion
from services.lentes import ejecutar_lentes


def libro(hojas):
    w = Workbook()
    w.remove(w.active)
    for nombre, filas in hojas.items():
        s = w.create_sheet(nombre)
        for fila in filas:
            s.append(fila)
    b = io.BytesIO()
    w.save(b)
    return b.getvalue()


def cargar(hojas):
    d, m = carga_archivos.parse_archivos_con_cobertura([("prueba.xlsx", libro(hojas))])
    d, r, n = excel_cobertura.preparar(d, m, lambda x: _aplicar_alcance_series(x, "auto"), sanitizacion.sanear)
    return d, r


def test_todas_hojas_y_exclusiones_declaradas():
    d, r = cargar(
        {
            "Grande": [["concepto", "importe"], ["A", 10], ["B", 20], ["C", 30]],
            "Chica": [["concepto", "importe"], ["D", -12]],
            "Vacia": [],
            "Nota": [["Sólo texto"]],
        }
    )
    assert len(d) == 4
    assert d[-1]["importe"] == -12
    assert [h["estado"] for h in r["excel"]["hojas"]] == ["incluida", "incluida", "sin_datos", "sin_datos"]
    # La nota se leyó: no contiene cifras, y se conserva como estructura fuera del barrido numérico.
    nota = r["excel"]["hojas"][-1]
    assert nota["texto_sin_cifras"] and nota["filas_estructura"] == [1]
    assert nota["filas_no_interpretadas"] == [] and nota["filas_datos"] == 0


def test_cuadros_unidades_y_periodos_repetidos_separados():
    d, r = cargar(
        {
            "Mixta": [
                ["Indicador", 2016, 2017, 2018, 2019, 2020],
                ["En millones de $", 1, 2, 3, 4, 5],
                ["En % del PIB", 1, 2, 3, 4, 50],
                [],
                ["Provincia"],
                ["Concepto", 2016, 2017, 2018, 2019, 2019],
                ["A", 11, 12, 13, 14, 15],
            ]
        }
    )
    bs = r["excel"]["bloques"]
    assert len(bs) == 3
    assert [b["filas"] for b in bs] == [[2], [3], [7]]
    assert d[-1]["2019_2"] == 15
    assert "fila 6" in r["excel"]["hojas"][0]["advertencias"][0]
    assert sum(b["fin"] - b["inicio"] for b in bs) == len(d)


def test_saneamiento_no_reintroduce_columnas_privadas_ni_mezcla_esquemas():
    d, r = cargar(
        {"A": [["concepto", "importe", "DNI"], ["X", 10, "12345678"]], "B": [["rubro", "cantidad"], ["Y", 20]]}
    )
    assert "DNI" not in str(d)
    assert set(d[0]) == {"concepto", "importe"}
    assert set(d[1]) == {"rubro", "cantidad"}
    assert "DNI" not in r["excel"]["bloques"][0]["columnas"]


def test_lentes_reciben_cuadros_aislados_y_formulas_solo_una_vez():
    d, r = cargar({"A": [["concepto", "importe"], ["X", 10]], "B": [["concepto", "importe"], ["Y", -20]]})
    r["formula_hallazgos"] = [{"descripcion": "Fórmula de origen", "evidencia": {}, "severidad": "media"}]
    i = SimpleNamespace(
        id=1, area_id=1, periodo="2026-09", creado_en=datetime.now(), dominio="general", datos=d, saneamiento=r
    )
    visitas = []

    def motor(db, unidad, previos=None):
        visitas.append(unidad.datos)
        unidad._condiciones_lentes = {"ajedrecista": {"estado": "evaluado", "motivo": "prueba"}}
        yield (
            "_crudos_finales",
            [
                {
                    "lente": "ajedrecista",
                    "descripcion": "Señal",
                    "evidencia": {"filas": [0], "columnas": ["importe"]},
                    "severidad": "media",
                }
            ],
        )

    resultados = list(excel_cobertura.ejecutar_por_bloques(None, i, motor))[-1][1]
    assert [len(x) for x in visitas] == [1, 1]
    assert len(resultados) == 3
    assert resultados[1]["evidencia"]["ubicaciones_excel"] == ["B!B2"]
    assert resultados[1]["evidencia"]["filas"] == [1]


def test_serie_anual_de_una_fila_se_evalua_sin_mezclar_unidades():
    d, r = cargar(
        {
            "A": [
                ["Indicador", 2016, 2017, 2018, 2019, 2020, 2021, 2022],
                ["En % del PIB", 1, 1.1, 1.2, 1.3, 13, 1.5, 1.6],
            ]
        }
    )
    i = SimpleNamespace(
        id=1, area_id=1, periodo="2026-09", creado_en=datetime.now(), dominio="general", datos=d, saneamiento=r
    )
    h = ejecutar_lentes(None, i)
    assert i._condiciones_lentes["cronista"]["bloques_evaluados"] == 1
    cronista = [x for x in h if x["lente"] == "cronista"]
    assert cronista and cronista[0]["evidencia"]["ubicaciones_excel"]


def test_dos_archivos_no_comparten_offsets():
    a = libro({"Hoja": [["concepto", "importe"], ["A", 1]]})
    b = libro({"Hoja": [["concepto", "importe"], ["B", 2]]})
    d, c = carga_archivos.parse_archivos_con_cobertura([("a.xlsx", a), ("b.xlsx", b)])
    assert [(x["inicio"], x["fin"], x["archivo"]) for x in c["bloques"]] == [(0, 1, "a.xlsx"), (1, 2, "b.xlsx")]


def test_condiciones_criticas_de_unidad_se_comprueban_por_cuadro():
    d, r = cargar({"A": [["unidad", "importe"], ["pesos", 10]], "B": [["unidad", "importe"], ["personas", 20]]})
    r["contexto_validacion"] = {"condiciones_criticas": ["unidad"]}
    i = SimpleNamespace(datos=d, saneamiento=r)
    assert excel_cobertura.evaluar_carga(i)["puede_concluir"]


def test_no_convergencia_entre_hojas_con_periodo_igual():
    from services.convergencia import detectar_convergencia

    h = [
        {"id": 1, "lente": "cronista", "evidencia": {"periodo": "2020", "hoja": "A", "bloque_excel": 1}},
        {"id": 2, "lente": "orquesta", "evidencia": {"periodo": "2020", "hoja": "B", "bloque_excel": 2}},
    ]
    assert detectar_convergencia(h) == []


def test_anios_duplicados_se_conservan_pero_no_se_ordenan_como_serie_valida():
    d, r = cargar(
        {"A": [["Indicador", 2016, 2017, 2018, 2019, 2020, 2021, 2021], ["En % del PIB", 1, 2, 3, 4, 50, 6, 7]]}
    )
    assert d[0]["2021_2"] == 7
    i = SimpleNamespace(
        id=1, area_id=1, periodo="2026-09", creado_en=datetime.now(), dominio="general", datos=d, saneamiento=r
    )
    ejecutar_lentes(None, i)
    assert i._condiciones_lentes["cronista"]["estado"] == "no_evaluable"
    assert "repetidos" in i._excel_ejecucion["bloques"][0]["controles"]["cronista"]["motivo"]
