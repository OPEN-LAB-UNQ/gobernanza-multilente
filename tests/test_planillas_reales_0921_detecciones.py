"""Detecciones con planillas oficiales reales (validación externa 3, después de las falsas alarmas).

Cada caso reproduce en chico la forma de un cuadro público con un error real que el motor no veía:
columnas total sin la palabra «Total» (turismo emisivo), una fila total anual sobre sus meses, bloques
paralelos «Principal / Intereses» con un total que omite sectores (deuda externa), la identidad de
saldos de la posición de inversión, un trimestre que repite el anterior con el año en otra columna y un
salto de escala sostenido al final de una serie. Cada regla tiene su caso correcto, sin señal.
"""

import io
import json

from openpyxl import Workbook

from services import carga_archivos, controles_excel, excel_cobertura, sanitizacion


def _bytes(w):
    b = io.BytesIO()
    w.save(b)
    return b.getvalue()


def _analizar(w, nombre="libro.xlsx"):
    b = _bytes(w)
    d, c = carga_archivos.parse_archivos_con_cobertura([(nombre, b)])
    d, r, _ = excel_cobertura.preparar(d, c, lambda x: (x, {}), sanitizacion.sanear)
    hs = controles_excel.analizar([(nombre, b)], d, r["excel"])
    return hs, r


def _de(hs, regla):
    return [h for h in hs if h["evidencia"]["regla"] == regla]


def _celdas(hs, regla):
    return {u.split("!")[1] for h in _de(hs, regla) for u in h["evidencia"]["ubicaciones_excel"]}


# --- N1 · columnas total sin rótulo «Total» ---------------------------------------------------------

AEREA = [135.895, 162.558, 172.356, 167.419, 190.656, 197.837, 214.218, 234.155]
FLUVIAL = [50.445, 50.9, 40.554, 38.128, 30.118, 29.19, 43.554, 36.58]
TERRESTRE = [231.766, 254.897, 169.236, 166.236, 142.319, 133.673, 211.771, 154.612]
EXCURSIONISTAS = [140.799, 155.702, 134.181, 171.671, 203.445, 242.721, 251.577, 195.62]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto"]


def _turismo(terrestre=None, total_anual=None):
    """Turistas por vía (Total = Aérea + Fluvial + Terrestre), Visitantes terrestres = turistas +
    excursionistas por esa vía, una participación en % y el total del año arriba de sus meses."""
    terrestre = terrestre or TERRESTRE
    w = Workbook()
    s = w.active
    s.title = "turismo emisivo"
    s.append(["Mes", "Turistas Total", "Turistas Aérea", "Turistas Fluvial", "Turistas Terrestre",
              "Excursionistas Terrestre", "Visitantes Terrestre", "Participación aérea (%)"])
    filas = []
    for m, a, f, t, e, tc in zip(MESES, AEREA, FLUVIAL, terrestre, EXCURSIONISTAS, TERRESTRE):
        total = round(a + f + tc, 3)  # el total se calculó con el valor correcto
        filas.append([m, total, a, f, t, e, round(tc + e, 3), round(100 * a / total, 1)])
    anual = [round(sum(x[j] for x in filas), 3) for j in range(1, 7)]
    if total_anual:
        anual[3] = total_anual
    s.append(["Año 2022", *anual, 40.1])
    for fila in filas:
        s.append(fila)
    return w


def test_columna_total_sin_rotulo_que_cierra_no_alarma():
    hs, _ = _analizar(_turismo())
    assert not _de(hs, "columna_total_no_cierra") and not _de(hs, "total_sin_rotulo_no_cierra")


def test_columna_total_sin_rotulo_senala_la_fila_que_no_cierra():
    terrestre = list(TERRESTRE)
    terrestre[5] = 13.3673  # decimal corrido en Junio (E8)
    hs, _ = _analizar(_turismo(terrestre, total_anual=round(sum(TERRESTRE), 3)))
    celdas = _celdas(hs, "columna_total_no_cierra")
    assert {"B8", "G8"} <= celdas, celdas
    # La columna de participación (%) no se toma como total ni como sumando.
    assert not any(c.startswith("H") for c in celdas)
    # El total anual (fila 2) declara la suma con el valor correcto: no cierra contra los meses.
    assert "E2" in _celdas(hs, "total_sin_rotulo_no_cierra")


def test_tolerancia_por_la_resolucion_mas_gruesa_de_los_sumandos():
    # 193,2 con un decimal: la suma de 206,521 + 50,625 + 193,2 difiere de 450,308 en 0,038 (redondeo).
    terrestre = list(TERRESTRE)
    terrestre[2] = 169.2
    hs, _ = _analizar(_turismo(terrestre))
    assert "B5" not in _celdas(hs, "columna_total_no_cierra")


# --- N2 · fila total sin rótulo -----------------------------------------------------------------------

PROVINCIAS = ["Buenos Aires", "Catamarca", "Córdoba", "Corrientes", "Chaco", "Chubut", "Entre Ríos"]
POBLACION = [10367, 205, 2271, 595, 622, 343, 782]
INGRESO = [822550591, 12082247, 175251229, 36326877, 32686552, 40536175, 57846107]
NO_LABORAL = [199299673, 3621261, 52460888, 11593319, 9942085, 9930139, 17335858]


def _ingresos(no_laboral_total=None, promedio=False):
    w = Workbook()
    s = w.active
    s.title = "Cuadro 3.2"
    s.append(["Provincia", "Población", "Perceptores", "Ingreso total", "Ingresos laborales", "Ingresos no laborales",
              "Ingresos no laborales (%)"])
    perceptores = [round(n * 0.61) for n in POBLACION]
    laborales = [i - nl for i, nl in zip(INGRESO, NO_LABORAL)]
    for p, n, pc, i, lab, nl in zip(PROVINCIAS, POBLACION, perceptores, INGRESO, laborales, NO_LABORAL):
        s.append([p, n, pc, i, lab, nl, round(100 * nl / i, 1)])
    total_nl = no_laboral_total or sum(NO_LABORAL)
    s.append(["Población con ingresos", sum(POBLACION), sum(perceptores), sum(INGRESO), sum(laborales), total_nl,
              round(100 * total_nl / sum(INGRESO), 1)])
    if promedio:
        s.append(["Promedio por provincia", *[round(sum(x) / 7) for x in (POBLACION, perceptores, INGRESO, laborales,
                                                                            NO_LABORAL)], 20.1])
    return w


def test_fila_total_sin_rotulo_que_cierra_no_alarma():
    hs, _ = _analizar(_ingresos(promedio=True))
    assert not _de(hs, "total_sin_rotulo_no_cierra")


def test_fila_total_sin_rotulo_senala_un_desvio_chico():
    # 0,04 %: por debajo de la materialidad de la conciliación (0,2 %), por encima del redondeo.
    hs, _ = _analizar(_ingresos(no_laboral_total=sum(NO_LABORAL) + 122092))
    assert _celdas(hs, "total_sin_rotulo_no_cierra") == {"F9"}


def test_fila_de_promedio_no_se_toma_como_total():
    hs, _ = _analizar(_ingresos(promedio=True))
    assert not any(h["evidencia"]["celda"].endswith("10") for h in _de(hs, "total_sin_rotulo_no_cierra"))


# --- N3 · bloques paralelos -----------------------------------------------------------------------------

SECTORES = [
    ("Gobierno general", [2142.96, 3058.39, 2944.24, 935.26], [1695.13, 1542.48, 2269.40, 1475.19]),
    ("Banco Central", [120.5, 311.2, 54.16, 54.16], [66.62, 68.63, 92.42, 67.25]),
    ("Sociedades captadoras de depósitos", [16.48, 1139.24, 125.19, 15.39], [0, 0, 0, 0]),
]
SUBSECTORES = [
    ("Otras sociedades financieras", [307.52, 331.34, 68.74, 18.83], [0, 0, 0, 0]),
    ("Sociedades no financieras, hogares e ISFLSH", [9279.66, 12327.88, 2613.0, 1235.87], [0, 0, 0, 0]),
]
DIRECTA = ("Inversión directa: Crédito entre empresas", [21019.23, 17051.98, 1756.96, 953.61], [0, 0, 0, 0])


def _deuda(total="completo"):
    w = Workbook()
    s = w.active
    s.title = "Cuadro 25"
    s.append(["Sector", "De pago inmediato", "Más de 0 a 3", "Más de 3 a 6", "Más de 6 a 9"])

    def bloque(nombre, principal, intereses):
        s.append([nombre, *[round(a + b, 2) for a, b in zip(principal, intereses)]])
        s.append(["Principal", *principal])
        s.append(["Intereses", *intereses])

    for nombre, p, i in SECTORES:
        bloque(nombre, p, i)
    otros_p = [round(sum(x[1][j] for x in SUBSECTORES), 2) for j in range(4)]
    s.append(["Otros sectores", *otros_p])
    for nombre, p, i in SUBSECTORES:
        bloque(nombre, p, i)
    bloque(*DIRECTA)
    arriba = SECTORES + [("Otros sectores", otros_p, [0, 0, 0, 0]), DIRECTA]
    if total == "omite":
        arriba = arriba[2:]  # sin Gobierno general ni Banco Central
    tp = [round(sum(x[1][j] for x in arriba), 2) for j in range(4)]
    ti = [round(sum(x[2][j] for x in arriba), 2) for j in range(4)]
    if total == "otro":
        tp = [5.1, 7.3, 2.2, 9.9]
    bloque("Saldo bruto de la deuda externa", tp, ti)
    return w


def test_bloques_paralelos_con_total_que_cierra_no_alarman():
    hs, r = _analizar(_deuda())
    assert not _de(hs, "total_omite_bloques") and not _de(hs, "total_bloques_no_cierra")
    assert not r["excel"]["estructura_revision"].get("totales_aparentes_sin_comprobar")


def test_total_que_omite_bloques_se_senala():
    hs, _ = _analizar(_deuda("omite"))
    senal = _de(hs, "total_omite_bloques")
    # Ancla en la columna donde lo omitido pesa más («Más de 3 a 6»).
    assert senal and senal[0]["evidencia"]["celda"] == "D21", [h["descripcion"][:200] for h in hs]
    assert senal[0]["evidencia"]["bloques_omitidos"] == ["Gobierno general", "Banco Central"]


def test_total_aparente_que_no_cierra_de_ninguna_forma_se_declara():
    hs, r = _analizar(_deuda("otro"))
    assert not _de(hs, "total_omite_bloques")
    declarados = r["excel"]["estructura_revision"].get("totales_aparentes_sin_comprobar") or []
    assert declarados and "Saldo bruto" in declarados[0]["donde"]


# --- N4 · identidad de saldos ---------------------------------------------------------------------------

def _saldos(revalorizacion_iv=86.19):
    w = Workbook()
    s = w.active
    s.title = "Cuadro 20"
    s.append(["Concepto", 2019, 2020, 2021, 2022, 2023, 2024])
    inicial = [23396.05, 25896.59, 27543.43, 28788.81, 29900.12, 31010.4]
    trans = [2438.72, 1504.23, 1390.93, 1020.2, 998.31, 678.38]
    precio = [61.81, 142.61, -145.55, 91.1, 111.97, 86.19]
    tc = [0, 0, 0, 0, 0, 0]
    reval = [a + b for a, b in zip(precio, tc)]
    final = [round(a + b + c, 2) for a, b, c in zip(inicial, trans, reval)]
    reval[5] = revalorizacion_iv
    s.append(["Saldo inicial", *inicial])
    s.append(["Transacciones financieras", *trans])
    s.append(["Revalorizaciones durante el período", *reval])
    s.append(["     Variaciones de precio", *precio])
    s.append(["     Variaciones de tipo de cambio", *tc])
    s.append(["Otras variaciones de volumen", 0, 0, 0, 0, 0, 0])
    s.append(["Saldo final", *final])
    return w


def test_saldo_final_que_cierra_no_alarma():
    hs, _ = _analizar(_saldos())
    assert not _de(hs, "saldo_final_no_cierra")


def test_saldo_final_que_no_cierra_con_sus_flujos_se_senala():
    hs, _ = _analizar(_saldos(revalorizacion_iv=0))
    assert _celdas(hs, "saldo_final_no_cierra") == {"G8"}


# --- N5 · período repetido con año y trimestre en columnas separadas --------------------------------------

def _trimestral(repetir=False):
    w = Workbook()
    s = w.active
    s.title = "Cuadro14.1"
    s.append(["Año", "Trimestre", "PIB", "Importaciones", "Consumo Privado", "Exportaciones"])
    base = [229608.21, 19292.51, 159281.89, 16140.34]
    filas = []
    for k in range(12):
        filas.append([round(v * (1 + 0.013 * k + 0.002 * (k % 3) * (j + 1)), 2) for j, v in enumerate(base)])
    if repetir:
        filas[10] = list(filas[9])
    for k, valores in enumerate(filas):
        anio = 2003 + k // 4 if k % 4 == 0 else None
        s.append([anio, ["I", "II", "III", "IV"][k % 4], *valores])
    return w


def test_anio_y_trimestre_en_columnas_separadas_se_leen_como_periodo():
    from services.controles_excel import modelo

    w = _trimestral()
    ws = w.active
    c = modelo.armar("libro.xlsx", ws.title, 1, ws, _LibroSimple(ws), 1, list(range(2, 14)),
                     [(j, ws.cell(1, j).value) for j in range(1, 7)])
    assert c["eje"] == "filas" and c["frecuencia"] == "trimestral"
    assert c["periodos_fila"][13]["texto"] == "2005-T4"


def test_trimestre_que_repite_el_anterior_se_senala():
    hs, _ = _analizar(_trimestral(repetir=True))
    senal = _de(hs, "fila_repetida_periodo_anterior")
    assert senal and senal[0]["evidencia"]["celda"] == "C12"
    assert not _de(_analizar(_trimestral())[0], "fila_repetida_periodo_anterior")


def test_dos_rubros_iguales_que_no_son_periodos_no_alarman():
    w = Workbook()
    s = w.active
    s.title = "01-08"
    s.append(["Concepto", "Tesoro", "Organismos", "Fondos fiduciarios", "Total"])
    s.append(["Ingresos corrientes", 41000.5, 8200.1, 1200.3, 50400.9])
    s.append(["Gastos corrientes", 39800.2, 7900.4, 1100.7, 48801.3])
    s.append(["SUPERAVIT ECONOMICO", 1200.3, 299.7, 99.6, 1599.6])
    s.append(["SUPERAVIT FINANCIERO", 1200.3, 299.7, 99.6, 1599.6])
    s.append(["Fuentes financieras", 9000.0, 300.0, 120.0, 9420.0])
    hs, _ = _analizar(w)
    assert not _de(hs, "fila_repetida_periodo_anterior")


# --- N6 · salto de escala sostenido al final de la serie ---------------------------------------------------

def _agregados(cola):
    w = Workbook()
    s = w.active
    s.title = "Publicación-Agreg"
    s.append(["Indicador", *range(1994, 2003)])
    s.append(["A.F.8", 0.297, 0.313, 0.332, 0.322, 0.353, 0.391, 0.419, 0.501, 0.415])
    s.append(["A.F.9", "s/i", "s/i", 0.0512, 0.0403, 0.0440, 0.0584, *cola])
    s.append(["A.F.10", 0.159, 0.079, 0.115, 0.041, 0.111, 0.085, 0.050, 0.128, 0.093])
    return w


def test_serie_sin_salto_de_escala_no_alarma():
    hs, _ = _analizar(_agregados([0.0751, 0.112, 0.219]))
    assert not _de(hs, "salto_escala_final")


def test_salto_de_escala_sostenido_al_final_se_senala():
    hs, _ = _analizar(_agregados([0.0000751, 0.000112, 0.000219]))
    senal = _de(hs, "salto_escala_final")
    assert senal and senal[0]["evidencia"]["celda"] == "H3", [h["descripcion"][:160] for h in hs]
    assert senal[0]["severidad"] == "alta"


def test_salto_en_el_ultimo_periodo_solo_queda_para_el_control_del_extremo():
    hs, _ = _analizar(_agregados([0.0751, 0.112, 0.000219]))
    assert not _de(hs, "salto_escala_final")


# --- N7 · el aviso de lectura cita la marca real -----------------------------------------------------------

def test_aviso_de_dato_no_disponible_cita_la_marca_de_la_planilla():
    w = Workbook()
    s = w.active
    s.title = "turismo"
    s.append(["Mes", "Total", "Var. ia. (%)"])
    for k, (m, v) in enumerate(zip(MESES, AEREA)):
        s.append([m, v, "///" if k < 3 else 10.5 + k])
    b = _bytes(w)
    d, c = carga_archivos.parse_archivos_con_cobertura([("t.xlsx", b)])
    _, r, _ = excel_cobertura.preparar(d, c, lambda x: (x, {}), sanitizacion.sanear)
    texto = json.dumps([c, r], ensure_ascii=False, default=str)
    assert "sin dato («///»)" in texto
    assert "sin dato («-», «s/d»)" not in texto


class _LibroSimple:
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
