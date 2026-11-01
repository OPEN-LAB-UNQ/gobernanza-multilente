import json

from services import lectura_temporal
from services.excel_cobertura import ubicar
from services.lentes import cronista


def anual(etiqueta="En % del PIB", valores=(1, 1.1, 1.2, 1.3, 13, 1.5, 1.6)):
    # Reproduce el cambio de orden al almacenar y recuperar JSONB.
    return json.loads(
        json.dumps({"Indicador": etiqueta, **{str(2016 + i): v for i, v in enumerate(valores)}}, sort_keys=True)
    )


def test_etiqueta_no_depende_del_orden_jsonb():
    fila = anual()
    assert next(iter(fila)) == "2016"
    hs = cronista.analizar([fila])
    assert hs and hs[0]["evidencia"]["serie"] == "En % del PIB"
    assert "19" not in hs[0]["evidencia"]["serie"]
    assert hs[0]["severidad"] == "media"
    assert "no confirma un error" in hs[0]["descripcion"]
    assert "cambia de régimen" not in hs[0]["descripcion"]
    assert hs[0]["evidencia"]["valor_actual"] == 13


def test_sin_etiqueta_no_usa_un_importe():
    fila = anual()
    del fila["Indicador"]
    assert cronista.analizar([fila])[0]["evidencia"]["serie"] == "fila 1"


def test_grupo_anual_conserva_nombres_ubicaciones_y_valores():
    hs = cronista.analizar([anual("Salud"), anual("Educación")])
    assert len(hs) == 1
    h = hs[0]
    assert h["evidencia"]["series"] == ["Salud", "Educación"]
    assert h["evidencia"]["requiere_contexto_anual"]
    b = {
        "archivo": "a.xlsx",
        "hoja": "Cuadro",
        "bloque": 1,
        "inicio": 20,
        "filas": [8, 9],
        "columnas": {"2019": "E", "2020": "F"},
    }
    h = ubicar(h, b)
    assert h["evidencia"]["ubicaciones_excel"] == ["Cuadro!E8:F8", "Cuadro!E9:F9"]
    assert h["evidencia"]["detalle_series"][1]["filas"] == [21]


def test_resumen_prioriza_sin_eliminar_ni_sumar_magnitudes():
    hs = [{**cronista.analizar([anual()])[0], "lente": "cronista"} for _ in range(12)]
    for n, h in enumerate(hs):
        h["evidencia"]["hoja"] = f"H{n}"
        h["evidencia"]["ratio_vs_movimiento_tipico"] = 10 + n
    hs.append({"lente": "ajedrecista", "evidencia": {}, "descripcion": "Fórmula"})
    antes = json.dumps(hs)
    r = lectura_temporal.resumen(hs)
    assert r["cantidad"] == 12 and r["otras_senales"] == 1
    assert r["referencias"][0]["hoja"] == "H11"
    assert len(r["referencias"]) == 5 and len(hs) == 13
    assert json.dumps(hs) == antes
    assert sum(r["periodos"].values()) == 12


def test_mensual_no_se_reclasifica_como_anual():
    fila = dict(zip(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio"], [1, 1.1, 1.2, 1.3, 13, 1.5, 1.6]))
    fila["Indicador"] = "Cantidad"
    h = cronista.analizar([fila])[0]
    assert not h["evidencia"]["requiere_contexto_anual"]
