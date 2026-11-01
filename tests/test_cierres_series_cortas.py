"""Series cortas (2 o 3 períodos): la misma relación repetida en otras hojas corrobora el total.

Caso real que lo motivó: un libro por provincia (una hoja por jurisdicción, 2016-2018, los mismos cuadros
en cada hoja) donde ningún total se comprobaba porque la regla pedía 4 períodos, y un total alterado en
una copia pasaba sin señal. Los libros de estas pruebas son sintéticos.
"""

import io

from openpyxl import Workbook

from services import carga_archivos, controles_excel, excel_cobertura, sanitizacion
from services.controles_excel.conciliacion import corroboradas_por_repeticion

COMPONENTES = ["Educación", "Salud", "Vivienda", "Cultura"]


def _valor(n, i, j, escala, enteros):
    v = (n + 1) * (120.5 + 37.25 * i) * (1 + 0.11 * j) * escala
    return int(round(v)) if enteros else round(v, 2)


def _libro(hojas=5, anios=(2016, 2017, 2018), alterar=(), rotulos=None, sin_dato=(), sumar=(), escala=None,
           enteros=False, total_arriba=False, cuadro_tasas=False):
    """Una hoja por jurisdicción con el mismo cuadro.

    `alterar` = [(hoja, columna, factor)] y `sumar` = [(hoja, columna, delta)] sobre el Total; `sin_dato` =
    [(hoja, fila, columna)] de componentes publicados «s/d» (el total queda como estaba); `escala` = {hoja:
    factor} para jurisdicciones chicas; `total_arriba`: el Total encabeza componentes con sangría;
    `cuadro_tasas`: debajo, un cuadro de tasas con los mismos rótulos cuyo Total no es la suma."""
    w = Workbook()
    w.remove(w.active)
    for n in range(hojas):
        ws = w.create_sheet(f"Jurisdicción {n + 1}")
        ws["A1"] = f"Jurisdicción {n + 1}"
        ws["A3"] = "Gasto por clase"
        ws["A4"] = "En millones de pesos corrientes"
        ws.cell(5, 1, "Clase")
        for j, anio in enumerate(anios):
            ws.cell(5, 2 + j, anio)
        nombres = (rotulos or {}).get(n, COMPONENTES)
        primera = 7 if total_arriba else 6
        fila_total = 6 if total_arriba else 6 + len(nombres)
        for i, nombre in enumerate(nombres):
            ws.cell(primera + i, 1, f"   {nombre}" if total_arriba else nombre)
            for j in range(len(anios)):
                ws.cell(primera + i, 2 + j, _valor(n, i, j, (escala or {}).get(n, 1), enteros))
        ws.cell(fila_total, 1, "Total")
        for j in range(len(anios)):
            total = sum(ws.cell(primera + i, 2 + j).value for i in range(len(nombres)))
            factor = next((f for h, c, f in alterar if h == n and c == j), 1)
            delta = next((d for h, c, d in sumar if h == n and c == j), 0)
            total = total * factor + delta
            ws.cell(fila_total, 2 + j, int(total) if enteros and factor == 1 else round(total, 2))
        for h, i, j in sin_dato:
            if h == n:
                ws.cell(primera + i, 2 + j, "s/d")
        if cuadro_tasas:
            ws["A14"] = "Tasa por mil habitantes"
            ws["A15"] = "Tasa por mil habitantes"
            ws.cell(16, 1, "Clase")
            for j, anio in enumerate(anios):
                ws.cell(16, 2 + j, anio)
            for i, nombre in enumerate(nombres + ["Total"]):
                ws.cell(17 + i, 1, nombre)
                for j in range(len(anios)):
                    ws.cell(17 + i, 2 + j, round(10 + 3.5 * i + 0.7 * j + 0.3 * n, 1))
    b = io.BytesIO()
    w.save(b)
    return b.getvalue()


def _analizar(contenido, nombre="libro.xlsx"):
    d, c = carga_archivos.parse_archivos_con_cobertura([(nombre, contenido)])
    d, r, _ = excel_cobertura.preparar(d, c, lambda x: (x, {}), sanitizacion.sanear)
    hs = controles_excel.analizar([(nombre, contenido)], d, r["excel"])
    return hs, r["excel"]["estructura_revision"]


def _conciliaciones(hs):
    return [h for h in hs if h["evidencia"].get("regla") == "conciliacion_aritmetica"]


def _lugares(hs):
    return sorted((h["evidencia"]["hoja"], h["evidencia"]["celda"]) for h in _conciliaciones(hs))


def test_original_cierra_por_repeticion_y_no_da_senales():
    hs, er = _analizar(_libro())
    assert _conciliaciones(hs) == []
    assert er["relaciones_corroboradas_por_repeticion"] == 5
    assert er["cantidad_cierres"] == 15  # 5 hojas × 3 años
    assert er["motivo_sin_cierres"] is None


def test_total_alterado_en_una_hoja_se_senala_en_su_celda():
    hs, er = _analizar(_libro(alterar=[(2, 1, 1.1)]))
    (h,) = _conciliaciones(hs)
    e = h["evidencia"]
    assert (e["hoja"], e["celda"]) == ("Jurisdicción 3", "C10")
    assert e["corroboracion"] == "repeticion_en_otras_hojas" and e["repeticiones_que_cierran"] == 4
    assert e["periodos_corroborrados"] == 2 and e["periodos_comparables"] == 3
    assert e["diferencia_porcentual"] > 9
    assert "otras 4 hojas o cuadros" in h["descripcion"]
    assert er["cantidad_cierres"] == 14  # el año alterado no se cuenta como cierre


def test_dos_periodos_comparables_tambien_se_corroboran():
    # Tres años con un componente «s/d» en 2016: quedan 2017 y 2018 para comparar, y 2018 está alterado.
    hs, _ = _analizar(_libro(alterar=[(0, 2, 1.1)], sin_dato=[(0, 3, 0)]))
    (h,) = _conciliaciones(hs)
    e = h["evidencia"]
    assert (e["hoja"], e["celda"]) == ("Jurisdicción 1", "D10")
    assert (e["periodos_corroborrados"], e["periodos_comparables"]) == (1, 2)


def test_dos_anios_los_cubre_el_total_de_columna():
    # Con dos años no se arman series de períodos: el cuadro se controla por el total de columna.
    hs, er = _analizar(_libro(anios=(2017, 2018), alterar=[(0, 1, 0.9)]))
    assert _conciliaciones(hs) == [] and er["relaciones_candidatas"] == 0
    assert any(h["evidencia"].get("regla") == "total_columna_no_cierra" and h["evidencia"].get("hoja") == "Jurisdicción 1"
               for h in hs)


def test_pocas_repeticiones_no_corroboran():
    hs, er = _analizar(_libro(hojas=3, alterar=[(1, 0, 1.1)]))
    assert _conciliaciones(hs) == []
    assert er["relaciones_corroboradas_por_repeticion"] == 0
    assert "menos de 4 períodos" in er["motivo_sin_cierres"] and "otras 3 hojas" in er["motivo_sin_cierres"]


def test_diferencia_repetida_en_varias_hojas_no_se_corrobora():
    # Dos de cinco hojas con el mismo desvío parecen un criterio distinto, no un error aislado.
    hs, _ = _analizar(_libro(alterar=[(1, 2, 1.1), (3, 2, 1.1)]))
    assert _conciliaciones(hs) == []


def test_mismo_anio_en_varias_hojas_de_un_libro_grande_no_se_corrobora():
    # 24 jurisdicciones, 5 con el mismo año fuera de cierre (19 de 23 completas pasa el 80 %): es un criterio.
    hs, _ = _analizar(_libro(hojas=24, alterar=[(h, 2, 1.1) for h in (1, 5, 9, 13, 17)]))
    assert _conciliaciones(hs) == []


def test_dos_errores_en_anios_distintos_se_senalan_los_dos():
    hs, _ = _analizar(_libro(hojas=24, alterar=[(3, 0, 1.1), (10, 2, 0.9)]))
    assert _lugares(hs) == [("Jurisdicción 11", "D10"), ("Jurisdicción 4", "B10")]


def test_redondeo_en_una_jurisdiccion_chica_no_se_senala():
    # Enteros: en la hoja chica una unidad de diferencia es 1,5 %, pero entra en el redondeo de cuatro sumandos.
    hs, _ = _analizar(_libro(hojas=6, enteros=True, escala={5: 0.05}, sumar=[(5, 0, 1)]))
    assert _conciliaciones(hs) == []
    hs, _ = _analizar(_libro(hojas=6, enteros=True, escala={5: 0.05}, sumar=[(5, 0, 10)]))
    assert _lugares(hs) == [("Jurisdicción 6", "B10")]


def test_rotulos_distintos_no_se_juntan():
    otros = ["Personal", "Bienes", "Servicios", "Transferencias"]
    hs, _ = _analizar(_libro(alterar=[(0, 1, 1.1)], rotulos={3: otros, 4: otros}))
    assert _conciliaciones(hs) == []


def test_cuadro_de_tasas_con_los_mismos_rotulos_no_tapa_el_error():
    # Debajo de cada cuadro de importes, uno de tasas con los mismos rótulos cuyo Total no es la suma; la
    # unidad «Tasa por mil habitantes» no se lee, así que la regla no puede depender de ella.
    hs, _ = _analizar(_libro(alterar=[(0, 1, 1.1)], cuadro_tasas=True))
    assert _lugares(hs) == [("Jurisdicción 1", "C10")]


def test_relaciones_en_cero_no_corroboran():
    # Tres jurisdicciones con el cuadro en cero no cuentan como repeticiones que cierran.
    hs, er = _analizar(_libro(alterar=[(0, 1, 1.1)], escala={1: 0, 2: 0, 3: 0}))
    assert _conciliaciones(hs) == []
    assert er["relaciones_corroboradas_por_repeticion"] == 0


def test_total_arriba_con_sangria_se_cuenta_una_vez():
    hs, er = _analizar(_libro(total_arriba=True, alterar=[(2, 1, 1.1)]))
    assert _lugares(hs) == [("Jurisdicción 3", "C6")]
    assert er["relaciones_corroboradas_por_repeticion"] == 5


def test_regla_de_repeticion():
    f, g = ("libro.xlsx", "jerarquia_por_sangria", None, "total", ("a", "b")), ("otra",)
    ok = frozenset()
    completas = [(f, 3, 3, ok)] * 4
    # La que falla en un año queda corroborada por las cuatro completas, y las completas siguen corroboradas.
    assert corroboradas_por_repeticion(completas + [(f, 2, 3, {2017})]) == {0: 3, 1: 3, 2: 3, 3: 3, 4: 4}
    assert 4 not in corroboradas_por_repeticion(completas + [(f, 1, 3, {2016, 2017})])  # falla en dos años
    assert 4 not in corroboradas_por_repeticion(completas + [(f, 4, 5, {2017})])  # serie larga: regla de siempre
    assert corroboradas_por_repeticion(completas + [(f, 1, 2, {2018})])[4] == 4  # dos períodos comparables
    # Borde del 80 %: 4 completas de 5 pasa; 3 de 4 no.
    assert 4 in corroboradas_por_repeticion(completas + [(f, 2, 3, {2016}), (f, 2, 3, {2018})])
    assert 3 not in corroboradas_por_repeticion([(f, 3, 3, ok)] * 3 + [(f, 2, 3, {2016}), (f, 2, 3, {2018})])
    # Otra que falla el mismo año: criterio, no error aislado.
    mismo_anio = corroboradas_por_repeticion(completas * 5 + [(f, 2, 3, {2017}), (f, 2, 3, {2017})])
    assert 20 not in mismo_anio and 21 not in mismo_anio and 0 in mismo_anio
    assert corroboradas_por_repeticion([(f, 3, 3, ok)] * 2 + [(g, 3, 3, ok)] * 2 + [(f, 2, 3, {2017})]) == {}
    # Repeticiones que no cierran nunca son otro cuadro con los mismos rótulos: no bloquean ni suman.
    nunca = [(f, 0, 3, frozenset({2016, 2017, 2018}))] * 5
    assert corroboradas_por_repeticion(completas + nunca + [(f, 2, 3, {2017})])[9] == 4
