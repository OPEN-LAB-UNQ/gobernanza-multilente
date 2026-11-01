from services.controles_excel.conciliacion import analizar
from services.controles_excel.temporal import mapa_periodos
from tests.test_controles_tabulares import analizar_libro, caso


def test_encabezado_duplicado_no_oculta_pico_en_tramo_valido():
    hs = analizar_libro(caso([100, 110, 1200, 130, 140, 150, 160], [2000, 2001, 2002, 2003, 2004, 2005, 2005]))
    assert {h["evidencia"]["regla"] for h in hs} == {"anio_duplicado", "pico_aislado"}
    pico = next(h for h in hs if h["evidencia"]["regla"] == "pico_aislado")
    assert pico["evidencia"]["periodos_ventana"] == [2001, 2002, 2003]
    assert pico["evidencia"]["periodos_ambiguos_excluidos"] == ["2005"]


def test_ambas_apariciones_del_duplicado_se_excluyen():
    s = {"periodos": [2000, 2001, 2001, 2003, 2004, 2005]}
    assert 2001 not in mapa_periodos(s)
    hs = analizar_libro(caso([100, 110, 1200, 130, 140, 150], s["periodos"]))
    assert not any(h["evidencia"]["regla"] == "pico_aislado" for h in hs)


def test_extremo_duplicado_no_permite_extrapolar():
    hs = analizar_libro(caso([100, 110, 120, 130, 140, 15000], [2000, 2001, 2002, 2003, 2004, 2004]))
    assert not any(h["evidencia"]["regla"] == "escala_extremo" for h in hs)


def test_conciliacion_alinea_anios_y_celdas_no_posiciones():
    base = dict(archivo="a.xlsx", hoja="Prueba", unidad="pesos", nivel=0, periodos_validos=False)
    total = {
        **base,
        "cuadro": 1,
        "etiqueta": "Total",
        "periodos": [2000, 2001, 2002, 2003, 2004, 2005, 2005],
        "valores": [10, 20, 35, 40, 50, 60, 7000],
        "celdas": [f"A{i}" for i in range(1, 8)],
    }
    repetido = {
        **base,
        "cuadro": 2,
        "etiqueta": "En millones de pesos",
        "periodos": [2006, 2005, 2004, 2003, 2002, 2001, 2000],
        "valores": [70, 60, 50, 40, 30, 20, 10],
        "celdas": [f"B{i}" for i in range(1, 8)],
    }
    hs = analizar([total, repetido])
    assert len(hs) == 1
    ev = hs[0]["evidencia"]
    assert ev["periodo"] == 2002 and ev["diferencia_absoluta"] == 5
    assert ev["celdas_participantes"] == ["Prueba!A3", "Prueba!B5"]
    assert ev["periodos_ambiguos_excluidos"] == ["2005"]
