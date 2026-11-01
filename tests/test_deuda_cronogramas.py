"""Perfil de vencimientos y listados de deuda (ministerio, 6 ediciones del banco de planillas publicadas).

Los pagos de un instrumento van y vienen entre períodos y son coherentes con su total: un pico en una celda
que cierra exacto con su total y sus componentes es prioridad media; si la celda rompe la suma, sigue alta.
También: paneles [instrumento, CAPITAL, INTERÉS] con un TOTAL al pie, un componente de más leído por la
sangría, la fila de categoría sobre su único título, filas «Como % del total» entre importes y el ruido de
punto flotante con signo.
"""
import datetime as dt
import io

from openpyxl import Workbook

from services import carga_archivos, casos_revision, controles_excel, excel_cobertura
from services.controles_excel.conciliacion import analizar, relaciones_cuadro
from services.sanitizacion import sanear
from tests.test_formatos_adicionales import serie

ANIOS = list(range(2026, 2036))


def _libro(filas, hoja="A.3.6"):
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    for i, fila in enumerate(filas, 1):
        for j, v in enumerate(fila, 1):
            if v is not None:
                ws.cell(i, j, v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _casos(contenido, nombre="deuda.xlsx"):
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([(nombre, contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(datos, cobertura, lambda f: (f, {}), sanear)
    hs = controles_excel.analizar([(nombre, contenido)], saneados, reporte["excel"])
    return hs, casos_revision.agrupar([dict(h) for h in hs])["casos"]


def _altas(casos):
    return {f'{(c["primary_finding"]["evidencia"]).get("hoja")}!{c["primary_finding"]["evidencia"].get("celda")}'
            for c in casos if c["prioridad"] == "alta"}


def _perfil(capital_a=None, total_capital=None, titulo="PERFIL ANUAL DE VENCIMIENTOS DE LA DEUDA"):
    """Perfil anual: tres instrumentos con CAPITAL e INTERÉS y el TOTAL al pie, todo cerrando exacto."""
    capital = {"Bono A": capital_a or [5000, 5200, 40, 5600, 5800, 6000, 6200, 6400, 6600, 6800],
               "Bono B": [3000 + 150 * k for k in range(10)], "Letras": [2000 + 90 * k for k in range(10)]}
    interes = {"Bono A": [400 + 7 * k for k in range(10)], "Bono B": [300 + 5 * k for k in range(10)],
               "Letras": [200 + 3 * k for k in range(10)]}
    filas = [[titulo], [], ["TIPO DE ACREEDOR", *ANIOS]]
    for nombre in capital:
        filas.append([nombre, *[c + i for c, i in zip(capital[nombre], interes[nombre])]])
        filas.append(["    CAPITAL", *capital[nombre]])
        filas.append(["    INTERÉS", *interes[nombre]])
    tc = [sum(capital[n][k] for n in capital) for k in range(10)]
    ti = [sum(interes[n][k] for n in interes) for k in range(10)]
    filas.append(["TOTAL", *[c + i for c, i in zip(tc, ti)]])
    filas.append(["    CAPITAL", *(total_capital or tc)])
    filas.append(["    INTERÉS", *ti])
    return _libro(filas)


def test_paneles_sin_total_arriba_con_total_al_pie():
    filas, n = [], 2
    for encabezado in ("Bono A", "Bono B", "Letras", "TOTAL"):
        for rotulo in (encabezado, "CAPITAL", "INTERÉS"):
            filas.append(serie(rotulo, n, [1] * 6))
            n += 1
    relaciones = [(p["etiqueta"], [x["etiqueta"] for x in c], o) for p, c, o in relaciones_cuadro(filas)]
    assert relaciones[-3:] == [("TOTAL", ["Bono A", "Bono B", "Letras"], "total_de_paneles"),
                               ("CAPITAL", ["CAPITAL"] * 3, "total_de_paneles"),
                               ("INTERÉS", ["INTERÉS"] * 3, "total_de_paneles")]
    assert [o for _, _, o in relaciones[:4]] == ["panel_repetido"] * 4


def test_componente_de_mas_leido_por_la_sangria_se_saca():
    adelantos = [900, 0, 0, 0, 0, 0]
    filas = [serie("PRÉSTAMOS", 2, [60] * 6), serie("Organismos", 3, [10] * 6, 1), serie("Banca", 4, [20] * 6, 1),
             serie("Avales", 5, [30] * 6, 1), serie("Adelantos transitorios", 6, adelantos, 1)]
    (_, componentes, _), = relaciones_cuadro(filas)
    assert [x["etiqueta"] for x in componentes] == ["Organismos", "Banca", "Avales"]
    assert analizar(filas) == []


def test_componente_alterado_no_se_saca():
    filas = [serie("PRÉSTAMOS", 2, [60] * 6), serie("Organismos", 3, [10] * 6, 1), serie("Banca", 4, [20] * 6, 1),
             serie("Avales", 5, [30, 30, 300, 30, 30, 30], 1)]
    (_, componentes, _), = relaciones_cuadro(filas)
    assert len(componentes) == 3
    assert [h["evidencia"]["ubicaciones_excel"][0] for h in analizar(filas)] == ["Cuadro!D2"]


def test_pago_que_va_y_viene_y_cierra_exacto_no_es_alta():
    hs, casos = _casos(_perfil())
    picos = [h for h in hs if h["evidencia"].get("regla") == "pico_aislado" and h["evidencia"]["celda"] == "D5"]
    assert picos and picos[0]["evidencia"]["cierre_exacto"]["total"] == "A.3.6!D4"
    assert "A.3.6!D5" not in _altas(casos)


def test_fuera_de_un_cronograma_el_pico_que_cierra_sigue_alto():
    # Un error de carga que se propaga a subtotales y total recalculados también cierra exacto.
    _, casos = _casos(_perfil(titulo="GASTO POR FINALIDAD Y FUNCIÓN"))
    assert "A.3.6!D5" in _altas(casos)


def test_total_alterado_del_perfil_sigue_alto():
    tc = [sum(x) for x in zip([5000, 5200, 40, 5600, 5800, 6000, 6200, 6400, 6600, 6800],
                              [3000 + 150 * k for k in range(10)], [2000 + 90 * k for k in range(10)])]
    tc[5] *= 10
    _, casos = _casos(_perfil(total_capital=tc))
    assert _altas(casos) & {"A.3.6!G14", "A.3.6!G13"}


def test_categoria_sobre_su_unico_titulo_no_es_un_periodo_repetido():
    filas = [["Fecha de emisión", "Denominación", "Valor nominal original", "Valor nominal actual", "Valor efectivo"]]
    for k in range(10):
        filas.append([dt.datetime(2015 + k, 3, 15), f"BONO {k}", 10000 + 1111 * k, 9000 + 1011 * k, 15000 + 977 * k])
    filas.insert(4, [None, "BONOS DE CONSOLIDACIÓN", 87654, 76543, 123456])
    filas.insert(5, [dt.datetime(2018, 5, 2), "BOCON 10ºS", 87654, 76543, 123456])
    hs, _ = _casos(_libro(filas, hoja="A.1.7"))
    assert not [h for h in hs if h["evidencia"].get("regla") == "fila_repetida_periodo_anterior"]


def test_fila_como_porcentaje_entre_importes_no_esta_fuera_de_escala():
    filas = [["TIPO DE ACREEDOR", 2026, 2027, 2028, 2029, "2030/2089"]]
    for k in range(8):
        filas.append([f"Rubro {k}", *[1000 + 50 * k + j for j in range(4)], 1_500_000 + 37_000 * k])
    filas.insert(5, ["Como % del total de servicios (2)", 0.2, 0.15, 0.1, 0.08, 0.12])
    hs, _ = _casos(_libro(filas))
    assert not [h for h in hs if h["evidencia"].get("regla") == "valor_fuera_de_escala_columna"]


def test_ruido_de_punto_flotante_no_es_un_signo_cambiado():
    filas = [["Bono", "Capital", "Atrasos de interés"]]
    for k in range(8):
        filas.append([f"Bono {k}", 1000 + 13 * k, 50 + 3 * k])
    filas[4][2] = -1.3647240662740625e-06
    hs, _ = _casos(_libro(filas, hoja="A.1.10"))
    assert not [h for h in hs if h["evidencia"].get("regla") == "signo_opuesto_columna"]
