"""Falsas alarmas con planillas oficiales reales (validación externa 3, motor 0.9.20).

Cada caso reproduce en chico la forma de un cuadro público que alarmaba sin error: el encabezado año +
trimestre de los libros de balanza de pagos de un instituto de estadística, las marcas «s/i» de una oficina de presupuesto, una columna de
variación interanual, el resultado financiero negativo en una columna «TOTAL» y un código padre igual
a su único hijo. Los errores reales del mismo tipo siguen detectándose.
"""

import io

from openpyxl import Workbook

from services import carga_archivos, controles_excel, excel_cobertura, sanitizacion
from services.controles_excel import modelo
from services.lentes import ajedrecista


def _bytes(w):
    b = io.BytesIO()
    w.save(b)
    return b.getvalue()


def analizar_libro(w, nombre="libro.xlsx"):
    b = _bytes(w)
    d, c = carga_archivos.parse_archivos_con_cobertura([(nombre, b)])
    d, r, _ = excel_cobertura.preparar(d, c, lambda x: (x, {}), sanitizacion.sanear)
    return controles_excel.analizar([(nombre, b)], d, r["excel"])


def _altas(hs):
    return [h for h in hs if h["severidad"] == "alta" and h["evidencia"].get("naturaleza") == "control"]


def _reglas(hs):
    return {h["evidencia"]["regla"] for h in hs}


ANIOS = list(range(2014, 2020))
# Flujos de signo mixto: un valor chico entre dos grandes es el cruce por cero, no un error de escala.
TRANSACCIONES = [7480, 5899, -3802, -5252, 6712, -2788, 4000, 30, 3800, -2500, 1215, 3100, -2243, 5400, 2900, 41]
REVALORIZACIONES = [8342, 2587, 1499, 885, 1948, 801, 2014, 552, 557, 763, 3526, 1500, -570, 4635, 5334, 2200]
PRECIO = [5426, 1761, -1067, -532, 771, 233, 1349, -597, 3068, -390, 690, -430, 2675, -333, -779, 562]
SALDO = [161475, 177511, 206092, 210709, 220114, 231877, 240000, 242500, 245100, 247300, 249900, 252000, 254400,
         256800, 259100, 261700]


def _balanza(saldo=None):
    """«Cuadro 20» en chico: años 2014-2019 y, desde 2020, «Año 2020» con I, II, III, IV y Total debajo."""
    w = Workbook()
    s = w.active
    s.title = "Cuadro 20"
    s.append(["Cuadro 20: Factores que explican la variación de la posición de inversión"])
    s.append(["-En millones de dólares-"])
    s.append([])
    s.append([None, *ANIOS, "Año 2020", None, None, None, None, "Año 2021*", None, None, None, None])
    s.append([None, *([None] * len(ANIOS)), "I", "II", "III", "IV", "Total", "I", "II", "III", "IV", "Total"])
    s.append([])

    def fila(rotulo, valores):
        anuales, t20, t21 = valores[:6], valores[6:10], valores[10:14]
        s.append([rotulo, *anuales, *t20, sum(t20), *t21, sum(t21)])

    fila("Saldo inicial", saldo or SALDO)
    fila("Transacciones financieras", TRANSACCIONES)
    fila("Revalorizaciones durante el período", REVALORIZACIONES)
    fila("     Variaciones de precio", PRECIO)
    fila("     Variaciones de tipo de cambio", [a - b for a, b in zip(REVALORIZACIONES, PRECIO)])
    return w


def test_encabezado_anio_y_trimestre_se_lee_en_dos_niveles():
    w = _balanza()
    ws = w.active
    c = modelo.armar("libro.xlsx", ws.title, 1, ws, _LibroSimple(ws), 4, list(range(7, 12)),
                     [(j, ws.cell(4, j).value or f"columna_{j}") for j in range(1, ws.max_column + 1)])
    assert c["subperiodos"] and c["frecuencia"] == "trimestral"
    por_letra = {x["letra"]: x for x in c["columnas"]}
    assert por_letra["B"]["periodo"]["frecuencia"] == "anual" and por_letra["B"]["periodo"]["anio"] == 2014
    assert (por_letra["H"]["periodo"]["anio"], por_letra["H"]["periodo"]["sub"]) == (2020, 1)
    assert (por_letra["K"]["periodo"]["anio"], por_letra["K"]["periodo"]["sub"]) == (2020, 4)
    assert por_letra["L"].get("total_periodo") and not por_letra["L"].get("periodo")
    assert (por_letra["M"]["periodo"]["anio"], por_letra["M"]["periodo"]["sub"]) == (2021, 1)
    assert set(c["paneles"].values()) == {"anual", "trimestral"}


def test_balanza_con_flujos_de_signo_mixto_no_alarma():
    hs = analizar_libro(_balanza())
    assert not _altas(hs), [h["descripcion"][:160] for h in _altas(hs)]
    assert not _reglas(hs) & {"anio_no_entero", "signo_opuesto_columna", "valor_fuera_de_escala_columna",
                              "pico_aislado", "signo_aislado", "valor_aislado_en_cuadro"}


def test_balanza_detecta_un_valor_por_mil_en_una_serie_de_signo_constante():
    saldo = list(SALDO)
    saldo[12] = saldo[12] * 1000  # 2021-III cargado en otra unidad
    hs = analizar_libro(_balanza(saldo))
    altas = _altas(hs)
    assert any("Cuadro 20!O7" in h["evidencia"]["ubicaciones_excel"] for h in altas), [h["descripcion"][:160] for h in hs]


def _onp(marcas):
    w = Workbook()
    s = w.active
    s.title = "Publicación-Agreg"
    s.append(["Indicador", *range(1994, 2003)])
    s.append(["A.F.8", 10.2, 11.0, 11.9, 12.5, 13.1, 13.8, 14.6, 15.1, 15.9])
    s.append(["A.F.9", *marcas[0], 0.0584, 0.0611, 0.0632, 0.0660, 0.0691, 0.0702])
    s.append(["A.F.10", 0.31, 0.29, 0.30, 0.28, 0.27, 0.26, 0.25, 0.24, 0.23])
    s.append(["A.F.25", *marcas[1], 1.43, 1.51, 1.57, 1.62, 1.66, 1.71, 1.78])
    return w


def test_marca_sin_informacion_repetida_en_la_hoja_no_es_cambio_de_tipo():
    hs = analizar_libro(_onp([["s/i", "s/i", 0.0571], ["s/i", 1.38]]))
    assert "cambio_tipo" not in _reglas(hs)
    assert not _altas(hs)


def test_sin_dato_suelto_sigue_alertando():
    hs = analizar_libro(_onp([[0.0550, "s/d", 0.0571], [1.31, 1.38]]))
    assert any(h["evidencia"]["regla"] == "cambio_tipo" and h["evidencia"]["celda"] == "C3" for h in _altas(hs))


def _turismo(error=False):
    w = Workbook()
    s = w.active
    s.title = "turismo emisivo"
    s.append(["Mes", "Excursionistas Total", "Excursionistas Var. ia."])
    # Como en el cuadro de un instituto de estadística: un bloque de meses por año, con el total del año arriba.
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio"]
    totales = [210.5, 198.3, 205.1, 190.8, 215.6, 220.4, 231.9, 202.7, 199.4, 207.3, 211.8, 226.1]
    if error:
        totales[7] = 20.27  # decimal corrido: ×10 por debajo (Febrero de 2024, B11)
    # Variación interanual con valores cerca de cero (0,05 y 0,36 %), que no son un error de escala.
    variaciones = [37.5, 41.2, 12.3, 25.8, 0.05, 33.1, 0.36, 28.9, 45.6, 30.2, 18.4, 22.7]
    if error:
        variaciones = [37.5, 41.2, 32.3, 25.8, 30.5, 33.1, 36.1, 28.9, 45.6, 30.2, 18.4, 22.7]
    for n, anio in enumerate((2023, 2024)):
        bloque = slice(6 * n, 6 * n + 6)
        s.append([f"Año {anio}", round(sum(totales[bloque]), 2), 21.5 + n])
        for m, t, v in zip(meses, totales[bloque], variaciones[bloque]):
            s.append([m, t, v])
    return w


def test_columna_de_variacion_no_se_controla_por_escala():
    hs = analizar_libro(_turismo())
    assert not [h for h in hs if h["evidencia"]["regla"] == "valor_fuera_de_escala_columna"]


def test_escala_de_columna_sigue_detectando_un_decimal_corrido():
    hs = analizar_libro(_turismo(error=True))
    assert any(h["evidencia"]["regla"] == "valor_fuera_de_escala_columna" and h["evidencia"]["celda"] == "B11"
               for h in _altas(hs))


def _datos(w):
    d, _ = carga_archivos.parse_archivos_con_cobertura([("ago11.xlsx", _bytes(w))])
    return d


def _esquema(resultado=-1520.4, otro=210.3):
    w = Workbook()
    s = w.active
    s.title = "08-11"
    s.append(["Concepto", "TESORO", "ORGANISMOS", "TOTAL"])
    s.append(["Ingresos corrientes", 41000.5, 8200.1, 49200.6])
    s.append(["Gastos corrientes", 39800.2, 7900.4, 47700.6])
    s.append(["Gastos de capital", 2900.7, 120.3, 3021.0])
    s.append(["Ingresos de capital", otro, 15.1, otro + 15.1])
    s.append(["Resultado financiero", resultado - 164.5, 164.5, resultado])
    s.append(["Fuentes financieras", 9000.0, 300.0, 9300.0])
    s.append(["Aplicaciones financieras", 7479.6, 300.0, 7779.6])
    return w


def test_resultado_financiero_negativo_en_columna_total_no_es_imposible():
    hs = ajedrecista.imposibilidad(_datos(_esquema()))
    assert "valor_negativo_en_magnitud_no_negativa" not in _reglas(hs)


def test_ingreso_negativo_en_columna_total_sigue_siendo_imposible():
    hs = ajedrecista.imposibilidad(_datos(_esquema(otro=-210.3)))
    assert "valor_negativo_en_magnitud_no_negativa" in _reglas(hs)


def _codigos(copia=False):
    w = Workbook()
    s = w.active
    s.title = "Cuadro 6"
    s.append(["Concepto", 2018, 2019, 2020, 2021, 2022, 2023])
    base = [1203.3, 1450.8, 1388.2, 1602.5, 1755.1, 1810.9]
    s.append(["3.5 Otra inversión", *[v * 3 for v in base]])
    s.append(["3.5.1 Préstamos", *base])
    # Aperturas sin código entre el padre y su único hijo codificado (las filas no quedan vecinas).
    s.append(["Memo: corto plazo", 101.2, 98.4, 120.7, 133.9, 128.1, 140.6])
    s.append(["Memo: largo plazo", 1102.1, 1352.4, 1267.5, 1468.6, 1627.0, 1670.3])
    s.append(["3.5.1.1 Préstamos de bancos", *base])
    s.append(["3.5.2 Depósitos", *[v * 2 for v in base]])
    s.append(["3.6 Activos de reserva", 410.2, 455.1, 390.7, 512.4, 498.3, 530.6])
    s.append(["3.6.1 Oro monetario", 50.1, 52.2, 49.8, 55.3, 57.9, 60.4])
    # Con `copia`, «Divisas» repite la serie de «Depósitos», que no es su padre ni su hijo.
    s.append(["3.6.2 Divisas", *([v * 2 for v in base] if copia else [360.1, 402.9, 340.9, 457.1, 440.4, 470.2])])
    return w


def test_codigo_padre_igual_a_su_unico_hijo_no_es_fila_identica():
    hs = analizar_libro(_codigos())
    assert "filas_identicas" not in _reglas(hs)


def test_filas_identicas_sin_relacion_de_codigo_sigue_alertando():
    hs = analizar_libro(_codigos(copia=True))
    assert any(h["evidencia"]["regla"] == "filas_identicas" and "3.6.2" in h["descripcion"] for h in hs)


class _LibroSimple:
    """Libro mínimo para armar el modelo desde una hoja en memoria (valores = lo escrito)."""

    formulas_desconocidas = False

    def __init__(self, ws):
        self.ws = ws

    def crudo(self, hoja, r, j):
        return self.ws.cell(r, j).value

    def formula(self, hoja, r, j):
        return None

    def valor(self, hoja, r, j):
        v = self.ws.cell(r, j).value
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _senal(regla, **evidencia):
    return {"lente": "ajedrecista", "severidad": "media", "descripcion": "",
            "evidencia": {"regla": regla, "naturaleza": "control", **evidencia}}


def test_salto_recurrente_calibrado_por_volatilidad_no_sube_a_alta():
    from services import casos_revision

    base = dict(factor_escala=26.5, calibrado_por_volatilidad=True)
    assert casos_revision.prioridad(_senal("pico_aislado", **base, saltos_parecidos_en_la_serie=3)) != "alta"
    # Un salto único en una serie volátil conserva la rareza por su factor.
    assert casos_revision.prioridad(_senal("pico_aislado", **base, saltos_parecidos_en_la_serie=0)) == "alta"


def test_fuera_de_escala_sin_separacion_clara_no_sube_a_alta():
    from services import casos_revision

    assert casos_revision.prioridad(_senal("valor_fuera_de_escala_columna", factor_escala=37.2,
                                           rareza_media_sin_separacion=True)) != "alta"
    assert casos_revision.prioridad(_senal("valor_fuera_de_escala_columna", factor_escala=37.2)) == "alta"


def test_balanza_controla_la_jerarquia_por_sangria_en_los_trimestres():
    # Revalorizaciones = Variaciones de precio + Variaciones de tipo de cambio; en 2021-IV queda en 0 (E1 de la validación 3).
    w = _balanza()
    w.active["P9"] = 0
    hs = analizar_libro(w)
    assert any(h["evidencia"]["regla"] == "conciliacion_aritmetica" and h["evidencia"]["celda"] == "P9" for h in _altas(hs))
