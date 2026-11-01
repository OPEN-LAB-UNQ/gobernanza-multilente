"""Etapa 2 del motor: reclasificación entre categorías y prioridad según el peso sobre el total."""
from services import casos_revision
from services.estructura_revision import _compensaciones
from services.reportes.consultas import _compensacion


def _serie(etiqueta):
    return {"etiqueta": etiqueta}


def _pruebas(filas, totales, periodos=(2016, 2017)):
    # (periodo, índice, columnas, valores de los componentes, total, cierra)
    return [(p, i, [i] * len(filas), [f[i] for f in filas], totales[i], True) for i, p in enumerate(periodos)]


def _padre(periodos=(2016, 2017)):
    return {"periodos": list(periodos), "valores": [0] * len(periodos), "archivo": "a.xlsx", "hoja": "Jurisdicción A",
            "cuadro": 1, "celdas": ["R43", "S43"], "etiqueta": "Total"}


def test_caida_compensada_por_otras_categorias_fuera_de_ritmo():
    # Jurisdicción A 2016→2017: Ayuda directa cae 759 y Condiciones de vida y Desarrollo suben mucho más que el total.
    filas = [[759.30, 0.16], [991.65, 2193.72], [174.11, 705.65], [36000.0, 46000.0]]
    hijos = [_serie(x) for x in ("Ayuda directa", "Condiciones de vida", "Desarrollo e integración", "Resto")]
    totales = [sum(f[0] for f in filas), sum(f[1] for f in filas)]
    padre = _padre()
    from unittest.mock import patch
    with patch("services.estructura_revision.mapa_periodos", lambda s: {2016: 0, 2017: 1}), \
         patch("services.estructura_revision.referencia", lambda s, i: f"Jurisdicción A!{'RS'[i]}43"):
        _compensaciones(padre, hijos, _pruebas(filas, totales))
    c = hijos[0]["compensacion"]["2017"]
    assert [x["etiqueta"] for x in c["componentes"]] == ["Condiciones de vida", "Desarrollo e integración"]
    assert c["cobertura"] >= 0.5 and c["celda_total"] == "Jurisdicción A!S43"
    hecho, pregunta = _compensacion({"periodo": 2017, "compensacion": c})
    assert pregunta == "¿se reasignaron partidas entre categorías en 2017?"
    assert "«Condiciones de vida» sube 1.202,07" in hecho and "y el total cierra" in hecho


def test_crecer_al_ritmo_del_total_no_es_compensacion():
    # Con inflación todo sube: si las demás crecen como el total, la caída no tiene contrapartida.
    filas = [[759.30, 0.16], [1000.0, 1300.0], [2000.0, 2600.0]]
    hijos = [_serie(x) for x in ("Ayuda directa", "Otra", "Resto")]
    totales = [sum(f[0] for f in filas), sum(f[1] for f in filas)]
    from unittest.mock import patch
    with patch("services.estructura_revision.mapa_periodos", lambda s: {2016: 0, 2017: 1}), \
         patch("services.estructura_revision.referencia", lambda s, i: "X!A1"):
        _compensaciones(_padre(), hijos, _pruebas(filas, totales))
    assert "compensacion" not in hijos[0]


def test_total_que_no_cierra_no_habilita_la_hipotesis():
    filas = [[759.30, 0.16], [991.65, 2193.72], [36000.0, 46000.0]]
    hijos = [_serie(x) for x in ("Ayuda directa", "Condiciones de vida", "Resto")]
    pruebas = [(p, i, [i] * 3, [f[i] for f in filas], 999999.0, i == 0) for i, p in enumerate((2016, 2017))]
    from unittest.mock import patch
    with patch("services.estructura_revision.mapa_periodos", lambda s: {2016: 0, 2017: 1}), \
         patch("services.estructura_revision.referencia", lambda s, i: "X!A1"):
        _compensaciones(_padre(), hijos, pruebas)
    assert all("compensacion" not in h for h in hijos)


def _patron(pct, regla="pico_aislado", factor=20, extremo=False):
    return {"lente": "ajedrecista", "severidad": "alta", "evidencia": {
        "regla": regla, "factor_escala": factor, "extremo_de_serie": extremo, "naturaleza": "control",
        "materialidad": {"porcentaje_revision": pct, "celda_total": "H!C24"}}}


def test_patron_con_poco_peso_no_es_alta():
    # Jurisdicción B «BP» 2002: 0,16 % del total del cuadro.
    assert casos_revision.ejes(_patron(0.155))["prioridad"] == "media"
    assert casos_revision.ejes(_patron(0.77))["prioridad"] == "alta"
    assert casos_revision.ejes(_patron(3.7))["prioridad"] == "alta"


def test_extremo_de_serie_con_peso_alto_no_baja_por_ser_el_ultimo_anio():
    # Jurisdicción C 2018: 1,5 % del total, sin vecino posterior.
    x = casos_revision.ejes(_patron(1.51, regla="escala_extremo", extremo=True))
    assert x["prioridad"] == "alta" and x["motivo_tope"] is None
    y = casos_revision.ejes(_patron(0.4, regla="escala_extremo", extremo=True))
    assert y["prioridad"] == "media"
