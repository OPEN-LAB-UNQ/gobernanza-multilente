"""Primera validación con errores reales (0.9.20): cuadros sintéticos que reproducen cada patrón.

1. Un «Total» separado de sus componentes por filas con rótulo y sin cifras: se une a ellos para
   armar el cierre; si no se puede, se declara al comienzo del informe.
2. Una nota que declara el cambio de unidad («1980-1986: miles; desde 1987: millones»): el cambio
   de escala de ese año queda como contexto, con la nota.
3. Jerarquías por código (1 / 1.1 / 1.1.1): cada padre es el total de sus hijos inmediatos, en
   Excel, CSV y PDF; sin afirmar nada si la jerarquía es ambigua.
4. La revisión de lectura no marca «No suma» en un total que cierra contra los subtotales de
   primer nivel (por código o intercalados).
"""

import io
from types import SimpleNamespace

from openpyxl import Workbook

from services import carga_archivos, controles_excel, excel_cobertura, ocr_local, sanitizacion
from services.controles_excel import jerarquia_codigos, tablas_planas
from services.controles_excel.modelo import cortes_unidad
from services.reportes import registro

ANIOS = list(range(2001, 2011))


def _analizar(w, nombre="libro.xlsx"):
    b = io.BytesIO()
    w.save(b)
    contenido = b.getvalue()
    d, c = carga_archivos.parse_archivos_con_cobertura([(nombre, contenido)])
    d, r, _ = excel_cobertura.preparar(d, c, lambda x: (x, {}), sanitizacion.sanear)
    hs = controles_excel.analizar([(nombre, contenido)], d, r["excel"])
    return hs, r["excel"]["estructura_revision"], r["excel"]


def _controles(hs):
    return [h for h in hs if h["evidencia"].get("naturaleza") == "control"]


def _pendientes(estructura):
    informe = SimpleNamespace(saneamiento={"archivos_origen": ["libro.xlsx"], "estructura_revision": estructura},
                              datos=[{"Rubro": "x", "2020": 1}], hallazgos=[], periodo=None, devolucion=None)
    return registro.construir(informe, [], {})["pendientes"]


# --------------------------------------------------------------------------- 1. total separado

COMPONENTES = {"Educación": 500.0, "Salud": 320.0, "Vivienda": 140.0, "Cultura": 60.0, "Deporte": 35.0}


def _bloque_partido(total_desplazado=False, sin_total=False, error_en=None):
    """Cuadro con dos rubros sin cifras (rótulo solo) entre los componentes y antes del total."""
    w = Workbook()
    s = w.active
    s.title = "Por categoría"
    s.append(["Gasto por categoría"])
    s.append(["En millones de pesos"])
    s.append([])
    s.append(["Categoría", *ANIOS])
    filas = {k: [round(v * (1.07 ** i) + 3 * ((i * 7 + len(k)) % 4), 1) for i in range(len(ANIOS))]
             for k, v in COMPONENTES.items()}
    nombres = list(filas)
    s.append([nombres[0], *filas[nombres[0]]])
    s.append(["   Rubro sin datos"])  # rubro vacío en este cuadro: sólo el rótulo
    for k in nombres[1:]:
        s.append([k, *filas[k]])
    s.append(["Otro rubro sin datos"])
    total = [round(sum(filas[k][i] for k in nombres), 1) for i in range(len(ANIOS))]
    if total_desplazado:
        total = [t - filas[nombres[0]][i] + 999 for i, t in enumerate(total)]
    if error_en is not None:
        total[error_en] += 250
    if not sin_total:
        s.append(["Total", *total])
    return w


def test_total_separado_por_filas_sin_datos_se_une_y_cierra():
    hs, er, excel = _analizar(_bloque_partido())
    bloques = [b for b in excel["bloques"] if b["hoja"] == "Por categoría"]
    assert len(bloques) == 1 and bloques[0]["total_separado"]["unido"]
    assert bloques[0]["total_separado"]["filas_sin_datos"] == [6, 11]
    assert any(c["total"].endswith("12") for c in er["cierres_verificados"])
    assert not er.get("totales_separados")
    assert not _controles(hs)


def test_total_separado_con_error_en_un_anio_se_senala():
    hs, er, _ = _analizar(_bloque_partido(error_en=4))
    conc = [h for h in _controles(hs) if h["evidencia"]["regla"] == "conciliacion_aritmetica"]
    assert [h["evidencia"]["celda"] for h in conc] == ["F12"]


def test_total_separado_que_no_cierra_con_nada_no_fusiona_y_se_declara():
    # Ningún grupo de arriba cierra con el total: los bloques no se fusionan y el comienzo dice que no se
    # armó el cierre, sin afirmar que el total no cierra.
    hs, er, excel = _analizar(_bloque_partido(total_desplazado=True))
    assert not [h for h in _controles(hs) if h["evidencia"]["regla"] == "conciliacion_aritmetica"]
    assert [b["filas"] for b in excel["bloques"] if b["hoja"] == "Por categoría"] == [[5], [7, 8, 9, 10], [12]]
    (sep,) = er["totales_separados"]
    assert sep["donde"] == "cierre de «Total» en fila 12 de «Por categoría»"
    assert "no se armó su cierre" in sep["motivo"] and "la fila 11" in sep["motivo"]
    assert "no cierra" not in sep["motivo"]
    assert any(p["donde"] == sep["donde"] and p["tipo"] == "no_controlado" for p in _pendientes(er))


def _secciones(A=ANIOS):
    def ser(v):
        return [round(v * 1.05 ** i + (i * 7 % 3), 1) for i in range(len(A))]
    return ser


def test_total_de_seccion_se_une_solo_con_su_seccion():
    # Un título de sección (texto sin cifras, sin sangría) corta la búsqueda: el «Total» es de la segunda.
    ser = _secciones()
    w = Workbook()
    s = w.active
    for f in (["Cuadro 3"], [], ["Concepto", *ANIOS], ["Ocupados", *ser(1000)], ["Desocupados", *ser(100)],
              ["Ocupados por rama (miles)"], ["Industria", *ser(300)], ["Comercio", *ser(500)], ["Servicios", *ser(200)],
              ["Otras ramas (s/d)"], ["Total", *[round(a + b + c, 1) for a, b, c in zip(ser(300), ser(500), ser(200))]]):
        s.append(f)
    hs, er, excel = _analizar(w)
    assert [b["filas"] for b in excel["bloques"]] == [[4, 5], [7, 8, 9, 11]]
    assert not _controles(hs) and not er.get("totales_separados")


def test_total_de_porcentajes_no_se_une_con_los_valores():
    ser = _secciones()
    w = Workbook()
    s = w.active
    for f in (["Concepto", *ANIOS], ["Educación", *ser(400)], ["Salud", *ser(600)], ["Estructura porcentual"],
              ["Educación ", *[40.0] * 10], ["Salud ", *[60.0] * 10], ["(sin datos)"], ["Total", *[100.0] * 10]):
        s.append(f)
    hs, er, excel = _analizar(w)
    assert [b["filas"] for b in excel["bloques"]] == [[2, 3], [5, 6, 8]]
    assert not _controles(hs)


def test_filas_sin_datos_sin_total_no_unen_ni_declaran():
    _, er, excel = _analizar(_bloque_partido(sin_total=True))
    assert not any(b.get("total_separado") for b in excel["bloques"])
    assert not er.get("totales_separados")


def test_total_suelto_despues_de_un_bloque_cerrado_se_declara_sin_unir():
    w = Workbook()
    s = w.active
    s.title = "Bloques"
    s.append(["Región", *ANIOS])
    for k, v in (("Norte", 10.0), ("Sur", 20.0)):
        s.append([k, *[v + i for i in range(len(ANIOS))]])
    s.append(["Subtotal", *[30.0 + 2 * i for i in range(len(ANIOS))]])
    s.append([])
    s.append(["Total general", *[30.0 + 2 * i for i in range(len(ANIOS))]])
    _, er, excel = _analizar(w)
    suelto = next(b for b in excel["bloques"] if b.get("total_separado"))
    assert suelto["total_separado"]["unido"] is False and suelto["filas"] == [6]
    assert er["totales_separados"][0]["donde"] == "cierre de «Total general» en fila 6 de «Bloques»"


# --------------------------------------------------------------------------- 2. unidad declarada

def _escala(nota, factor=1000):
    w = Workbook()
    s = w.active
    s.title = "Gasto"
    s.append(["Gasto consolidado"])
    s.append([nota] if nota else [])
    s.append([])
    anios = list(range(1980, 1996))
    s.append(["Función", *anios])
    base = {"Salud": 120.0, "Educación": 300.0, "Defensa": 80.0, "Justicia": 40.0}
    for k, v in base.items():
        fila = []
        for i, a in enumerate(anios):
            x = v * (1.5 ** i) * (1 + 0.02 * ((i + len(k)) % 3))
            fila.append(round(x / factor if a >= 1987 else x, 4))  # desde 1987 en millones
        s.append([k, *fila])
    return w


def _regla(hs, regla):
    return [h for h in hs if h["evidencia"].get("regla") == regla]


def test_cambio_de_unidad_declarado_en_la_nota_queda_como_contexto():
    hs, _, _ = _analizar(_escala("1980-1986: miles de pesos; Desde 1987: millones de pesos"))
    (h,) = _regla(hs, "cambio_escala_sostenido")
    e = h["evidencia"]
    assert e["naturaleza"] == "contexto" and e["cambio_unidad_declarado"] == 1987
    assert e["contexto_declarado"]["celda"] == "A2"
    assert "declara el cambio de unidad en 1987" in h["descripcion"]


def test_sin_nota_o_con_otra_unidad_el_cambio_sigue_siendo_control():
    for nota in (None, "En millones de pesos", "1980-1989: miles de pesos; Desde 1990: millones de pesos"):
        hs, _, _ = _analizar(_escala(nota))
        (h,) = _regla(hs, "cambio_escala_sostenido")
        assert h["evidencia"]["naturaleza"] == "control", nota


def test_cortes_de_unidad_por_texto():
    assert cortes_unidad("1980-1986: miles de pesos; Desde 1987: millones de pesos") == {1987}
    assert cortes_unidad("Hasta 1991 en australes; desde 1992 en pesos") == {1992}
    assert cortes_unidad("1990-1995: miles; 1996-2005: millones") == {1996}
    assert cortes_unidad("En millones de pesos") == set()
    assert cortes_unidad("2001-2020: millones de pesos corrientes") == set()
    assert cortes_unidad("Desde 2005 incluye a las provincias; en millones de pesos") == set()
    # La unidad tiene que venir inmediatamente después del año.
    assert cortes_unidad("Desde 2005 incluye a las provincias, en millones de pesos. Los subsidios se expresan "
                         "en miles de pesos") == set()
    assert cortes_unidad("En millones de pesos. A partir de 2016, incluye transferencias en millones de dólares") == set()
    assert cortes_unidad("Período 2003-2015 en millones de pesos; 2016-2023 en millones de dólares") == {2016}


NOTA_1987 = "1980-1986: miles de pesos; Desde 1987: millones de pesos"


def test_salto_en_sentido_contrario_a_la_nota_sigue_siendo_alarma():
    # La nota dice que desde 1987 los valores están en millones (bajan ×1.000); acá suben ×1.000.
    hs, _, _ = _analizar(_escala(NOTA_1987, factor=0.001))
    (h,) = _regla(hs, "cambio_escala_sostenido")
    assert h["evidencia"]["naturaleza"] == "control"


def test_nota_de_otro_cuadro_de_la_hoja_no_oculta_el_error():
    # Cuadro A declara el cambio de unidad; cuadro B, en la misma hoja, tiene un ×1.000 real desde 1987.
    anios = list(range(1980, 1996))

    def serie(v, k):
        return [round(v * (1.5 ** i) * (1 + 0.02 * ((i + len(k)) % 3)) / (1000 if a >= 1987 else 1), 4)
                for i, a in enumerate(anios)]

    w = Workbook()
    s = w.active
    s.title = "Gasto"
    s.append(["Cuadro A. Gasto por función"])
    s.append([NOTA_1987])
    s.append([])
    s.append(["Función", *anios])
    for k, v in {"Salud": 120.0, "Educación": 300.0, "Defensa": 80.0, "Justicia": 40.0}.items():
        s.append([k, *serie(v, k)])
    s.append([])
    s.append([])
    s.append(["Cuadro B. Recaudación (en miles de pesos)"])
    s.append([])
    s.append(["Impuesto", *anios])
    for k, v in {"IVA": 500.0, "Ganancias": 250.0, "Bienes": 60.0, "Sellos": 30.0}.items():
        s.append([k, *serie(v, k)])
    hs, _, _ = _analizar(w)
    por_celda = {h["evidencia"]["celda"]: h["evidencia"]["naturaleza"] for h in _regla(hs, "cambio_escala_sostenido")}
    assert por_celda == {"I5": "contexto", "I14": "control"}


# --------------------------------------------------------------------------- 3. jerarquía por código

HIJOS = {"1.1.1": [120, 130, 125], "1.1.2": [40, 45, 50], "1.2.1": [900, 950, 990], "1.2.2": [60, 70, 80],
         "2.1": [15, 18, 20], "2.2": [7, 9, 11], "2.3": [3, 3, 4]}
NOMBRES = {"1": "Deuda pública", "1.1": "Corto plazo", "1.1.1": "Bonos", "1.1.2": "Préstamos", "1.2": "Largo plazo",
           "1.2.1": "Bonos", "1.2.2": "Préstamos", "2": "Otros pasivos", "2.1": "Subrogación", "2.2": "Fideicomisos",
           "2.3": "Capitalización"}


def _jerarquia():
    v = {k: list(x) for k, x in HIJOS.items()}
    for padre in ("1.1", "1.2", "2", "1"):
        hijos = jerarquia_codigos._hijos_inmediatos(padre, set(v) | {"1.1", "1.2"})
        v[padre] = [sum(v[h][j] for h in hijos) for j in range(3)]
    orden = ["1", "1.1", "1.1.1", "1.1.2", "1.2", "1.2.1", "1.2.2", "2", "2.1", "2.2", "2.3"]
    return orden, v


def _libro_codigos(error=None, en_rotulo=False, codigos=None):
    orden, v = _jerarquia()
    if error:
        codigo, j, valor = error
        v[codigo][j] = valor
    w = Workbook()
    s = w.active
    s.title = "Deuda"
    s.append(["Estado de la deuda"])
    s.append([])
    s.append(["Concepto", "Saldo inicial", "Altas", "Saldo final"] if en_rotulo
             else ["Código", "Concepto", "Saldo inicial", "Altas", "Saldo final"])
    for k in orden:
        codigo = (codigos or {}).get(k, k)
        s.append([f"{codigo} {NOMBRES[k]}", *v[k]] if en_rotulo else [codigo, NOMBRES[k], *v[k]])
    total = [v["1"][j] + v["2"][j] for j in range(3)]
    s.append(["TOTAL", *total] if en_rotulo else [None, "TOTAL", *total])
    return w


def test_jerarquia_por_codigo_cierra_y_cuenta_sus_cierres():
    hs, er, _ = _analizar(_libro_codigos())
    assert not _controles(hs)
    por_codigo = [c for c in er["cierres_verificados"] if c["origen"] == "jerarquia_por_codigo"]
    assert len(por_codigo) == 4 * 3  # «1», «1.1», «1.2» y «2» (con tres hijos), en tres columnas
    assert any(c["origen"] == "total_de_codigos_de_primer_nivel" for c in er["cierres_verificados"])
    assert er["motivo_sin_cierres"] is None


def test_subcuenta_que_no_suma_se_senala_una_vez_en_su_fila():
    # «1.2» con un dígito perdido: sus hijos suman 1.040 y la fila dice 40. «1» y TOTAL cierran con los
    # demás valores: la diferencia es la de «1.2» y no se repite en sus padres.
    hs, _, _ = _analizar(_libro_codigos(error=("1.2", 1, 40)))
    conc = [h for h in _controles(hs) if h["evidencia"]["regla"] == "conciliacion_aritmetica"]
    assert [h["evidencia"]["celda"] for h in conc] == ["D8"]
    e = conc[0]["evidencia"]
    assert e["origen_relacion"] == "jerarquia_por_codigo" and e["total_declarado"] == 40
    assert e["total_reconstruido"] == 1020 and len(e["componentes"]) == 2


def test_jerarquia_por_codigo_en_el_rotulo_de_un_csv():
    orden, v = _jerarquia()
    v["1.2"][1] = 40
    lineas = ["Concepto;Saldo inicial;Altas;Saldo final"]
    lineas += [f"{k} {NOMBRES[k]};" + ";".join(str(x) for x in v[k]) for k in orden]
    lineas.append("TOTAL;" + ";".join(str(v["1"][j] + v["2"][j]) for j in range(3)))
    contenido = ("\n".join(lineas) + "\n").encode("utf-8")
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("deuda.csv", contenido)])
    hs, resumen = tablas_planas.analizar([("deuda.csv", contenido)], datos, lectura, lambda f: (f, {}), sanitizacion.sanear)
    conc = [h for h in hs if h["evidencia"].get("regla") == "conciliacion_aritmetica"]
    assert len(conc) == 1 and "1.2 Largo plazo" in conc[0]["evidencia"]["ubicacion_legible"]
    assert resumen[0]["estructura"]["cantidad_cierres"] > 0


def test_codigos_que_no_son_jerarquia_no_se_controlan():
    # Filas numeradas (1, 2, 3…), códigos presupuestarios planos y años: ningún cierre ni señal.
    for rotulos in ([str(i) for i in range(1, 9)],
                    ["21.1.1", "21.1.2", "21.2.1", "21.2.2", "22.1.1", "22.1.2", "23.1.1", "23.1.2"],
                    [str(a) for a in range(2015, 2023)]):
        w = Workbook()
        s = w.active
        s.append(["Código", "Programa", "Crédito", "Devengado"])
        for i, r in enumerate(rotulos):
            s.append([r, f"Programa {i}", 100.0 + 13 * i, 90.0 + 11 * i])
        hs, er, _ = _analizar(w)
        assert not [c for c in er["cierres_verificados"] if "codigo" in c["origen"]], rotulos
        assert not er.get("jerarquia_sin_comprobar"), rotulos


def test_subcuentas_salteadas_o_codigos_repetidos_se_declaran_sin_afirmar():
    # «2.2» se renumera como «2.4»: falta «2.2» y «2.3» sigue; no se afirma el cierre de «2».
    hs, er, _ = _analizar(_libro_codigos(codigos={"2.2": "2.4"}, error=("2", 0, 999)))
    assert not [h for h in _controles(hs) if h["evidencia"]["celda"].endswith("11")]
    assert any("numeración de sus subcuentas" in x["motivo"] for x in er["jerarquia_sin_comprobar"])
    assert any("cierre de «2»" in p["donde"] for p in _pendientes(er))


def test_padre_con_desglose_parcial_no_se_senala():
    # «2» con un solo hijo listado («de los cuales»): no hay cierre que afirmar.
    w = Workbook()
    s = w.active
    s.append(["Código", "Concepto", "2022", "2023", "2024"])
    for codigo, nombre, vs in (("1", "Corrientes", [30, 33, 36]), ("1.1", "Personal", [20, 22, 24]),
                               ("1.2", "Bienes", [10, 11, 12]), ("2", "Capital", [50, 55, 60]),
                               ("2.1", "De los cuales: obras", [20, 21, 22])):
        s.append([codigo, nombre, *vs])
    hs, er, _ = _analizar(w)
    assert not _controles(hs)
    assert len([c for c in er["cierres_verificados"] if c["origen"] == "jerarquia_por_codigo"]) == 3


def _libro_filas(filas):
    w = Workbook()
    s = w.active
    for f in filas:
        s.append(f)
    return w


def _alarmas_codigo(hs):
    return [h for h in _controles(hs) if h["evidencia"].get("origen_relacion") in
            ("jerarquia_por_codigo", "total_de_codigos_de_primer_nivel")]


def test_columnas_que_no_suman_aunque_su_nombre_no_lo_diga():
    # Rendimiento, haber medio y razón Dev/Cred: ningún padre cierra en ellas, no entran al control.
    def rinde(k, n, sup, prod):
        return [k, n, sup, prod, round(prod * 1000 / sup, 1)]
    agro = [["Código", "Cultivo", "Superficie (ha)", "Producción (t)", "Rendimiento (kg/ha)"],
            rinde("1", "Cereales", 1500, 7000), rinde("1.1", "Trigo", 1000, 3000), rinde("1.2", "Maíz", 500, 4000),
            rinde("2", "Oleaginosas", 500, 1100), rinde("2.1", "Soja", 300, 600), rinde("2.2", "Girasol", 200, 500),
            [None, "Total", 2000, 8100, 4050.0]]
    haber = [["Código", "Concepto", "Beneficios", "Monto ($ M)", "Haber ($)"]] + [
        [k, n, b, m, round(m * 1e6 / b / 1000, 2)] for k, n, b, m in
        (("1", "Contributivas", 300, 900), ("1.1", "Jubilaciones", 200, 700), ("1.2", "Pensiones", 100, 200),
         ("2", "No contributivas", 50, 60), ("2.1", "Invalidez", 30, 40), ("2.2", "Vejez", 20, 20))]
    razon = [["Código", "Concepto", "Crédito", "Devengado", "Dev/Cred"]] + [
        [k, n, c, d, round(d / c, 3)] for k, n, c, d in
        (("1", "Corrientes", 300, 240), ("1.1", "Personal", 200, 180), ("1.2", "Bienes", 100, 60),
         ("2", "Capital", 100, 50), ("2.1", "Obras", 70, 30), ("2.2", "Equipos", 30, 20))]
    for filas in (agro, haber, razon):
        hs, er, _ = _analizar(_libro_filas(filas))
        assert not _alarmas_codigo(hs), filas[0]
        columnas = {c["periodo"] for c in er["cierres_verificados"] if "codigo" in c["origen"]}
        assert filas[0][4] not in columnas and len(columnas) == 2


def test_desglose_parcial_de_las_cuales_con_una_columna():
    filas = [["Código", "Concepto", "Devengado 2024"]] + [list(r) for r in (
        ("1", "Personal", 100), ("1.1", "Planta", 60), ("1.2", "Contratados", 40), ("2", "Bienes", 50),
        ("2.1", "Insumos", 30), ("2.2", "Otros", 20), ("3", "Transferencias", 500),
        ("3.1", "de las cuales: becas", 80), ("3.2", "de las cuales: subsidios", 120))] + [[None, "Total", 650]]
    hs, er, _ = _analizar(_libro_filas(filas))
    assert not _alarmas_codigo(hs)
    assert any("desglose parcial" in x["motivo"] and x["concepto"] == "3" for x in er["jerarquia_sin_comprobar"])


def test_una_columna_con_fila_sin_codigo_dentro_del_padre_no_se_afirma():
    filas = [["Código", "Concepto", "Monto"]] + [list(r) for r in (
        ("1", "Personal", 100), ("1.1", "Planta", 60), ("1.2", "Contratados", 40), ("2", "Bienes", 50),
        ("2.1", "Insumos", 30), ("2.2", "Otros", 20), ("3", "Servicios", 90), ("3.1", "Limpieza", 30),
        (None, "Ajuste de cierre", 40), ("3.2", "Vigilancia", 20))]
    hs, er, _ = _analizar(_libro_filas(filas))
    assert not _alarmas_codigo(hs)
    assert any(x["concepto"] == "3" for x in er["jerarquia_sin_comprobar"])


def test_total_con_fila_sin_codigo_entre_los_de_primer_nivel_no_se_arma():
    for columnas in (1, 3):
        filas = [["Código", "Concepto", *["Monto", "2023", "2024"][:columnas]]]
        for k, n, v in (("1", "Corrientes", 100), ("1.1", "Personal", 60), ("1.2", "Bienes", 40),
                        ("2", "Capital", 50), ("2.1", "Obras", 30), ("2.2", "Equipos", 20)):
            filas.append([k, n, *[v + 5 * j for j in range(columnas)]])
        filas.append([None, "Otros gastos", *[25 + j for j in range(columnas)]])
        filas.append([None, "Total", *[175 + 11 * j for j in range(columnas)]])
        hs, er, _ = _analizar(_libro_filas(filas))
        assert not _alarmas_codigo(hs)
        assert not [c for c in er["cierres_verificados"] if c["origen"] == "total_de_codigos_de_primer_nivel"]
        assert "subcuentas" not in str(er.get("jerarquia_sin_comprobar"))


def test_total_que_no_cierra_con_el_primer_nivel_no_habla_de_subcuentas():
    orden, v = _jerarquia()
    w = _libro_codigos()
    s = w.active
    for j, col in enumerate("CDE"):
        s[f"{col}15"] = v["1"][j] + v["2"][j] + 500  # TOTAL distinto en las tres columnas
    hs, er, _ = _analizar(w)
    motivos = [x["motivo"] for x in er.get("jerarquia_sin_comprobar") or [] if "primer nivel" in x["motivo"]]
    assert motivos and not any("subcuentas" in m for m in motivos)


# --------------------------------------------------------------------------- 4. revisión de lectura

def _tabla_revision(error=None):
    orden, v = _jerarquia()
    if error:
        v[error[0]][error[1]] = error[2]
    filas = [[f"{k} {NOMBRES[k]}"] + [f"{x:,}".replace(",", ".") for x in v[k]] for k in orden]
    filas.append(["TOTAL"] + [f"{v['1'][j] + v['2'][j]:,}".replace(",", ".") for j in range(3)])
    return ["Concepto", "Inicial", "Altas", "Final"], filas


def test_revision_total_con_jerarquia_por_codigo_no_marca_no_suma():
    enc, filas = _tabla_revision()
    assert not [d for d in ocr_local.celdas_dudosas(enc, filas) if d["motivo"].startswith("No suma")]


def test_revision_marca_la_subcuenta_y_no_su_padre_ni_el_total():
    enc, filas = _tabla_revision(error=("1.2", 1, 40))
    marcas = [d for d in ocr_local.celdas_dudosas(enc, filas) if d["motivo"].startswith("No suma")]
    assert [(d["fila"], d["columna"]) for d in marcas] == [(4, 2)]
    assert "1.2.1, 1.2.2" in marcas[0]["motivo"]


def test_revision_subtotales_intercalados_de_varios_niveles():
    # Sin códigos: «A» = «A1» + «A2», cada uno con sus partes; el total es A + B.
    enc = ["Concepto", "2024"]
    filas = [["A", "100"], ["A1", "60"], ["A1a", "25"], ["A1b", "35"], ["A2", "40"], ["A2a", "15"], ["A2b", "25"],
             ["B", "50"], ["B1", "20"], ["B2", "30"], ["Total", "150"]]
    assert not [d for d in ocr_local.celdas_dudosas(enc, filas) if d["motivo"].startswith("No suma")]
    filas[-1] = ["Total", "170"]
    assert [d["fila"] for d in ocr_local.celdas_dudosas(enc, filas) if d["motivo"].startswith("No suma")] == [10]


def test_revision_codigos_que_no_son_jerarquia():
    assert ocr_local.codigos_jerarquia(["1 Uno", "2 Dos", "3 Tres", "Total"]) == {}
    assert ocr_local.codigos_jerarquia(["A Buenos Aires", "B Córdoba", "C Santa Fe"]) == {}
    assert ocr_local.codigos_jerarquia(["1.1 X", "1.1 Y", "1 Z", "1.2 W"]) == {}
    assert ocr_local.codigos_jerarquia(["1 X", "1.1 Y", "1.2 Z"]) == {0: "1", 1: "1.1", 2: "1.2"}


def test_revision_desglose_parcial_y_columna_no_sumable_no_marcan():
    enc = ["Concepto", "Superficie", "Rendimiento"]
    filas = [["1 Cereales", "1.500", "4.667"], ["1.1 Trigo", "1.000", "3.000"], ["1.2 Maíz", "500", "8.000"],
             ["2 Oleaginosas", "500", "2.200"], ["2.1 Soja", "300", "2.000"], ["2.2 Girasol", "200", "2.500"]]
    assert not [d for d in ocr_local.celdas_dudosas(enc, filas) if d["motivo"].startswith("No suma")]
    filas = [["1 Personal", "100"], ["1.1 Planta", "60"], ["1.2 Contratados", "40"], ["2 Transferencias", "500"],
             ["2.1 de las cuales: becas", "80"], ["2.2 de las cuales: subsidios", "120"]]
    assert not [d for d in ocr_local.celdas_dudosas(["Concepto", "Monto"], filas) if d["motivo"].startswith("No suma")]
