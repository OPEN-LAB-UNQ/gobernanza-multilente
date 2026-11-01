"""«Dice qué no revisó»: todo lo que no se pudo leer o controlar se declara con su motivo.

Cuadros apilados en una hoja, períodos con la unidad anotada, controles que no corrieron, CSV
con títulos y punto de miles, libros hechos sólo de fórmulas, listas que coinciden con su
conteo, la fila «Total» de un cuadro con años en filas, el formato largo con una fila en otra
unidad y los períodos repetidos de un PDF. Cada caso tiene su contraparte correcta: lo que se
arregla no puede agregar falsas alarmas.
"""
import io
import itertools

import pytest
from openpyxl import Workbook

import models
from routers.carga_rapida import _aplicar_alcance_series
from services import carga_archivos, controles_excel, excel_cobertura, sanitizacion
from services.controles_excel import tablas_planas
from services.controles_excel.periodos import leer
from services.estructura_revision import preparar as preparar_estructura
from services.plural import muestra
from tests.flujo_confirmado import cargar_confirmado
from tests.test_ejemplos_zip import flujo  # noqa: F401  (fixture)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(filas, titulo="Hoja1"):
    wb = Workbook()
    ws = wb.active
    ws.title = titulo
    for f in filas:
        ws.append(list(f))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _cuadro(titulo, rotulo, columnas, componentes, ajuste=None):
    filas = [[titulo], [], [rotulo, *columnas]]
    for k, (nombre, base) in enumerate(componentes):
        filas.append([nombre] + [round(base * (1 + 0.04 * i + 0.01 * k)) for i in range(len(columnas))])
    total = ["Total"] + [sum(f[i + 1] for f in filas[3:]) for i in range(len(columnas))]
    if ajuste:
        total[ajuste[0]] += ajuste[1]
    return filas + [total]


ANIOS = [2019, 2020, 2021, 2022, 2023]
TRIMESTRES = ["T1 2024", "T2 2024", "T3 2024", "T4 2024", "T1 2025"]
REGIONES = [("Pampeana", 1200), ("NOA", 340), ("NEA", 210), ("Cuyo", 480), ("Patagonia", 610)]


def _apilado(segundo=TRIMESTRES, ajuste=None):
    primero = _cuadro("Cuadro 1. Exportaciones por región. En millones de dólares", "Región", ANIOS, REGIONES)
    otro = _cuadro("Cuadro 2. Exportaciones trimestrales. En millones de dólares", "Región", segundo,
                   [(n, b // 4) for n, b in REGIONES], ajuste)
    return _xlsx(primero + [[]] + otro, "Exportaciones")


def _controles(nombre, contenido):
    datos, cobertura, lectura = carga_archivos.parse_archivos_con_lectura([(nombre, contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(
        datos, cobertura, lambda f: _aplicar_alcance_series(f, "todas"), sanitizacion.sanear)
    hallazgos = controles_excel.analizar([(nombre, contenido)], saneados, reporte["excel"])
    reporte["excel"]["saneados"] = saneados
    return hallazgos, reporte["excel"]


def _planos(nombre, contenido):
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([(nombre, contenido)])
    hallazgos, _ = tablas_planas.analizar([(nombre, contenido)], [dict(f) for f in datos], lectura,
                                          lambda f: _aplicar_alcance_series(f, "todas"), sanitizacion.sanear)
    return hallazgos


def _reglas(hallazgos, severidad=None):
    return [h["evidencia"]["regla"] for h in hallazgos if severidad is None or h.get("severidad") == severidad]


# 1. Dos cuadros en una hoja ---------------------------------------------------------------

@pytest.mark.parametrize("segundo", [TRIMESTRES, [2014, 2015, 2016, 2017, 2018]])
def test_segundo_cuadro_apilado_se_lee_como_cuadro_propio(segundo):
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("expo.xlsx", _apilado(segundo))])
    hoja = cobertura["hojas"][0]
    assert [b["encabezados"] for b in cobertura["bloques"]] == [[3], [13]]
    # El encabezado del segundo cuadro no se lee como una fila de datos del primero.
    assert not hoja.get("celdas_no_numericas")
    assert not any("no interpretable" in a for a in hoja["advertencias"])
    assert list(cobertura["bloques"][1]["columnas"])[1] == str(segundo[0])


def test_error_en_el_segundo_cuadro_apilado_se_detecta_en_su_celda():
    hallazgos, _ = _controles("expo.xlsx", _apilado(ajuste=(3, 40)))
    altas = [h for h in hallazgos if h["evidencia"]["regla"] in {"conciliacion_aritmetica", "total_de_filas_no_cierra"}]
    assert altas and altas[0]["evidencia"]["celda"] == "D19"


def test_apilado_correcto_sin_falsas_alarmas():
    hallazgos, _ = _controles("expo.xlsx", _apilado())
    assert _reglas(hallazgos, "alta") == []


def test_encabezado_no_reconocido_dentro_del_cuadro_se_declara_sin_leer():
    from services.reportes.registro import construir

    excel = {"hojas": [{"archivo": "a.xlsx", "hoja": "H", "estado": "incluida", "filas_datos": 5,
                        "celdas_no_numericas": [{"columna": "2021", "letra": "B", "celdas": 4, "ejemplos": []}]}],
             "bloques": []}
    informe = models.Informe(id=1, datos=[{"x": 1, "archivo_origen": "a.xlsx"}], saneamiento={"excel": excel, "archivos_origen": ["a.xlsx"]}, periodo="2026-09")
    reg = construir(informe, [], {})
    assert reg["estado"] != "completo"
    assert any(p["donde"] == "4 celdas" and "números" in p["motivo"] for p in reg["pendientes"])


# 2. Unidad anotada en el encabezado ---------------------------------------------------------

def test_periodo_con_unidad_anotada_se_reconoce_y_conserva_la_unidad():
    p = leer("2024 (miles de asistentes)")
    assert (p["anio"], p["frecuencia"], p["unidad"]) == (2024, "anual", "miles de asistentes")
    assert leer("2023 (en millones)")["unidad"] == "en millones"
    assert leer("2023 (p)")["marca"] == "p" and not leer("2023 (p)").get("unidad")
    assert leer("Región (km2)") is None


def test_columna_con_unidad_anotada_entra_en_las_series():
    filas = [["Museo", "2019", "2020", "2021", "2022", "2023 (miles de asistentes)"]]
    filas += [[n, *(b + 10 * i for i in range(5))] for n, b in [("Bellas Artes", 410), ("Historia", 120), ("Ciencias", 220)]]
    contenido = _xlsx(filas)
    hallazgos, excel = _controles("museos.xlsx", contenido)
    assert excel["bloques"][0]["unidades_columna"]["2023 (miles de asistentes)"]["letra"] == "F"
    assert _reglas(hallazgos, "alta") == []
    lectura = controles_excel.cobertura_lectura([("museos.xlsx", contenido)], excel["saneados"], excel)
    assert lectura["series_aparentes"] == 3


def test_unidad_distinta_anotada_en_una_columna_es_senal():
    filas = [["Programa"] + [f"{a} (en millones)" for a in ANIOS[:-1]] + ["2023 (en miles)"]]
    for n, b in REGIONES:
        filas.append([n] + [b + 10 * i for i in range(4)] + [(b + 40) * 1000])
    hallazgos, _ = _controles("gasto.xlsx", _xlsx(filas))
    senal = [h for h in hallazgos if h["evidencia"]["regla"] == "unidad_columna_distinta"]
    assert senal and senal[0]["evidencia"]["celda"] == "F1"
    assert "en miles" in senal[0]["descripcion"] and "millones" in senal[0]["descripcion"]


def test_unidades_iguales_en_todas_las_columnas_no_son_senal():
    filas = [["Programa"] + [f"{a} (en millones)" for a in ANIOS]]
    filas += [[n] + [b + 10 * i for i in range(5)] for n, b in REGIONES]
    hallazgos, _ = _controles("gasto.xlsx", _xlsx(filas))
    assert "unidad_columna_distinta" not in _reglas(hallazgos)
    assert _reglas(hallazgos, "alta") == []


def test_columna_numerica_con_rotulo_no_reconocido_se_declara():
    from services.reportes.registro import construir

    filas = [["Fuente", 2019, 2020, 2021, 2022, "2023 - dato preliminar sujeto a revisión"]]
    filas += [[n, *(b + i for i in range(5))] for n, b in [("Hidráulica", 30), ("Térmica", 80), ("Nuclear", 8)]]
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("energia.xlsx", _xlsx(filas))])
    hoja = cobertura["hojas"][0]
    assert hoja["columnas_no_controladas"][0]["celda"] == "F1"
    informe = models.Informe(id=1, datos=datos, saneamiento={"excel": cobertura}, periodo="2026-09")
    reg = construir(informe, [], {})
    assert any("F1" in p["donde"] and p["tipo"] == "no_controlado" for p in reg["pendientes"])
    assert reg["primera_linea"].startswith("LECTURA PARCIAL")


# 3. Controles en cero ----------------------------------------------------------------------

def test_cero_cierres_no_se_informa_como_control_que_paso():
    vacio = preparar_estructura([])
    assert vacio["cantidad_cierres"] == 0 and "no se identificaron series" in vacio["motivo_sin_cierres"]
    serie = dict(archivo="a.xlsx", hoja="H", cuadro=1, nivel=0, periodos=[2021, 2022, 2023],
                 celdas=["B2", "C2", "D2"], valores=[1, 2, 3], unidad=None)
    sin_total = preparar_estructura([dict(serie, etiqueta="Norte"), dict(serie, etiqueta="Sur", celdas=["B3", "C3", "D3"])])
    assert "fila de total" in sin_total["motivo_sin_cierres"]


def test_reporte_dice_que_los_cierres_no_se_ejecutaron_y_por_que(flujo):  # noqa: F811
    client, factory, _ = flujo
    tres_anios = _cuadro("Gasto por programa", "Programa", ANIOS[:3], REGIONES)
    texto = _ejecutivo(client, factory, "gasto.xlsx", _xlsx(tres_anios))
    assert "0 cierres" not in texto
    assert "Cierres entre totales y componentes · no ejecutado:" in texto


# 4. CSV es-AR con títulos y punto de miles ------------------------------------------------

CSV_TITULO = (
    "Cuadro 3. Producción de leche por cuenca\nEn miles de litros\n\n"
    "Año;Abasto;Oeste;Central;Mar y Sierras;Total\n"
    "2019;4.280;15.043;12.110;2.305;33.738\n2020;4.351;15.502;12.380;2.410;34.643\n"
    "2021;4.402;15.910;12.720;2.388;35.420\n2022;4.390;16.120;12.950;2.420;35.880\n"
    "2023;4.455;16.402;13.210;2.501;36.568\n\nFuente: elaboración propia\n"
).encode()


def test_csv_con_titulos_y_punto_de_miles_se_lee():
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("leche.csv", CSV_TITULO)])
    assert len(datos) == 5 and datos[0]["Oeste"] == 15043 and datos[-1]["Total"] == 36568
    info = lectura[0]
    assert info["separador"] == "punto y coma"
    assert [t["fila"] for t in info["filas_titulo"]] == [1, 2]
    assert any("2 líneas de título antes del encabezado (fila 4)" in a for a in info["avisos"])


def test_csv_con_titulo_y_separadores_sobrantes_se_lee():
    texto = ("Cuadro 4. Población;;;;\n;;;;\nDepartamento;2020;2021;2022;2023\n"
             "Capital;1.262.100;1.271.500;1.283.900;1.294.000\nMaipú;193.200;195.800;198.300;200.900\n"
             "Las Heras;233.000;235.800;238.500;241.300\n").encode("latin1")
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("pob.csv", texto)])
    assert [f["Departamento"] for f in datos] == ["Capital", "Maipú", "Las Heras"]
    assert datos[0]["2023"] == 1294000


def test_csv_con_titulos_sin_falsas_alarmas():
    assert _reglas(_planos("leche.csv", CSV_TITULO), "alta") == []


def test_csv_sin_filas_tiene_motivo_exacto():
    _, cobertura, lectura = carga_archivos.parse_archivos_con_lectura([("vacio.csv", b"Concepto;2023;2024\n")])
    motivo = carga_archivos.motivo_sin_datos(lectura, cobertura)
    assert "encabezado (fila 1" in motivo and "ninguna fila de datos" in motivo


# 5 y 6. Fórmulas sin resultado guardado -----------------------------------------------------

def test_libro_solo_de_formulas_se_calcula():
    contenido = _xlsx([["Concepto", "2022", "2023"], ["Ingresos", "=100*12", "=110*12"],
                       ["Gastos", "=80*12", "=85*12"], ["Resultado", "=B2-B3", "=C2-C3"]])
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("calc.xlsx", contenido)])
    assert [f["2023"] for f in datos] == [1320, 1020, 300]
    hoja = cobertura["hojas"][0]
    assert hoja["formulas_calculadas"]["celdas"] == 6
    assert any("se muestran 5 de 6" in a for a in hoja["advertencias"])


def test_libro_de_formulas_no_calculables_se_rechaza_diciendo_por_que():
    contenido = _xlsx([["Concepto", "2022", "2023"], ["Ingresos", "=VLOOKUP(1,Z1:Z2,1)", "=VLOOKUP(2,Z1:Z2,1)"],
                       ["Gastos", "=INDEX(Z1:Z2,1)", "=INDEX(Z1:Z2,2)"]])
    datos, cobertura, lectura = carga_archivos.parse_archivos_con_lectura([("calc.xlsx", contenido)])
    assert not datos
    motivo = carga_archivos.motivo_sin_datos(lectura, cobertura)
    assert "fórmulas sin resultado guardado" in motivo and "4 celdas" in motivo


def test_conteo_y_lista_de_formulas_coinciden():
    filas = [["Provincia", 2020, 2021, 2022, 2023], ["Salta", 120, 130, 140, 150], ["Jujuy", 80, 85, 90, 96],
             ["Total", "=SUM(B2:B3)", "=SUM(C2:C3)", "=SUM(D2:D3)", "=SUM(E2:E3)"],
             ["Promedio", "=AVERAGE(B2:B3)", "=AVERAGE(C2:C3)", 0, 0]]
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("becas.xlsx", _xlsx(filas))])
    aviso = next(a for a in cobertura["hojas"][0]["advertencias"] if "sin resultado guardado" in a)
    assert aviso.startswith("6 celdas") and "se muestran 5 de 6" in aviso
    assert muestra(["A1", "A2"]) == "A1, A2"
    assert muestra(["A1", "A2", "A3"], total=7, maximo=2) == "A1, A2; se muestran 2 de 7"


# 7. «Total» al pie de un cuadro con años en filas ---------------------------------------------

def _anios_en_filas(error=0):
    filas = [["Llegadas de turistas por año"], ["Año", "Europa", "América", "Asia", "Total"]]
    for i, y in enumerate(range(2016, 2023)):
        a, b, c = 500 + 11 * i, 1300 + 23 * i, 210 + 7 * i
        filas.append([y, a, b, c, a + b + c])
    total = ["Total"] + [sum(f[j] for f in filas[2:]) for j in range(1, 5)]
    total[3] += error
    return _xlsx(filas + [total], "Turismo")


def test_total_de_un_cuadro_con_anios_en_filas_no_es_un_periodo():
    hallazgos, _ = _controles("turismo.xlsx", _anios_en_filas())
    assert not [h for h in hallazgos if "Total" in str(h["evidencia"].get("periodo"))]
    assert not {"anio_no_entero", "anio_duplicado"} & set(_reglas(hallazgos))


def test_total_con_error_en_anios_en_filas_se_detecta(flujo):  # noqa: F811
    client, factory, _ = flujo
    hallazgos = _hallazgos(client, factory, "turismo.xlsx", _anios_en_filas(error=47))
    assert any(h.evidencia.get("regla") in {"total_de_filas_no_cierra", "partes_no_suman_total"} for h in hallazgos)
    assert not any("Período Total" in (h.descripcion or "") for h in hallazgos)


def test_fila_de_datos_con_anio_e_importe_cercano_a_2000_no_es_encabezado():
    filas = [["Llegadas"], ["Año", "Europa", "América", "Asia", "Total"],
             [2018, 520, 1300, 210, 2030], [2019, 540, 1350, 233, 2123], [2020, 120, 300, 40, 460]]
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("t.xlsx", _xlsx(filas))])
    assert cobertura["bloques"][0]["encabezados"] == [2]


# 8. Formato largo con una fila en otra unidad -------------------------------------------------

def _largo(otra_unidad=True):
    lineas = ["provincia;anio;producto;unidad;valor"]
    bases = {"Córdoba": 100, "Santa Fe": 90, "Buenos Aires": 140, "Entre Ríos": 60}
    for (p, base), y, prod in itertools.product(bases.items(), range(2019, 2024), ["trigo", "maíz", "soja"]):
        v = base * (1 + 0.05 * (y - 2019)) * {"trigo": 10, "maíz": 15, "soja": 20}[prod]
        unidad = "toneladas"
        if otra_unidad and (p, y, prod) == ("Santa Fe", 2021, "maíz"):
            unidad, v = "miles de toneladas", v / 1000
        lineas.append(f"{p};{y};{prod};{unidad};{v:.1f}".replace(".", ","))
    return ("\n".join(lineas) + "\n").encode()


def test_fila_en_otra_unidad_es_la_senal_y_no_dispara_alarmas_de_periodo():
    hallazgos = _planos("granos.csv", _largo())
    reglas = _reglas(hallazgos)
    assert not [r for r in reglas if r.startswith("periodo_")]
    senal = [h for h in hallazgos if h["evidencia"]["regla"] == "unidad_fila_distinta"]
    assert len(senal) == 1 and "miles de toneladas" in senal[0]["descripcion"]
    assert "fila 24" in senal[0]["descripcion"]


@pytest.mark.parametrize("contenido", [
    _largo(otra_unidad=False),
    ("region;periodo;indicador;unidad;valor\n" + "\n".join(
        f"{r};{y};{ind};{u};{base + 10 * (y - 2018)}"
        for r, y in itertools.product(["Norte", "Sur", "Este"], range(2018, 2024))
        for ind, u, base in [("superficie", "hectáreas", 1000), ("producción", "toneladas", 5000)]) + "\n").encode(),
])
def test_formato_largo_correcto_sin_falsas_alarmas(contenido):
    hallazgos = _planos("largo.csv", contenido)
    assert _reglas(hallazgos, "alta") == []
    assert "unidad_fila_distinta" not in _reglas(hallazgos)


# 9. Período repetido en un PDF ----------------------------------------------------------------

def test_periodo_repetido_de_pdf_conserva_el_rotulo_original():
    assert tablas_planas.rotulo_original("2022_2", ["Provincia", "2019", "2022"]) == "2022"
    assert tablas_planas.rotulo_original("saldo_2", ["Provincia"]) == "saldo_2"


# Recorrido completo ---------------------------------------------------------------------------

def _cargar(client, factory, nombre, contenido):
    from services import jobs

    tipo = "text/csv" if nombre.endswith(".csv") else XLSX
    r = cargar_confirmado(client, "/api/analisis-rapido", data={"periodo": "2026-09", "notificar": "false", "alcance_series": "todas"},
                    files={"archivos": (nombre, contenido, tipo)})
    assert r.status_code == 200, r.text
    while jobs._process_one():
        pass
    return r.json()["informe_id"]


def _hallazgos(client, factory, nombre, contenido):
    ident = _cargar(client, factory, nombre, contenido)
    with factory() as db:
        informe = db.get(models.Informe, ident)
        hs = list(informe.hallazgos)
        for h in hs:
            db.expunge(h)
        return hs


def _ejecutivo(client, factory, nombre, contenido):
    from services import reporte_ejecutivo
    from services.prioridad_controles import clave

    ident = _cargar(client, factory, nombre, contenido)
    with factory() as db:
        informe = db.get(models.Informe, ident)
        return "\n".join(reporte_ejecutivo.lineas(informe, sorted(informe.hallazgos, key=clave)))


def test_apilado_con_trimestres_declara_lo_que_no_controlo(flujo):  # noqa: F811
    from services.reportes.registro import construir

    client, factory, _ = flujo
    ident = _cargar(client, factory, "expo.xlsx", _apilado())
    with factory() as db:
        informe = db.get(models.Informe, ident)
        reg = construir(informe, list(informe.hallazgos))
    # La evolución temporal sólo corrió en el cuadro anual: el trimestral queda declarado.
    assert reg["estado"] == "parcial"
    assert any("1 de 2 cuadros" in p["donde"] for p in reg["pendientes"])
    assert not any(h.severidad == "alta" for h in informe.hallazgos)


def test_csv_es_ar_con_titulos_no_se_rechaza(flujo):  # noqa: F811
    client, factory, _ = flujo
    hallazgos = _hallazgos(client, factory, "leche.csv", CSV_TITULO)
    assert not [h for h in hallazgos if h.severidad == "alta"]


def test_carga_sin_datos_dice_el_motivo(flujo):  # noqa: F811
    client, _, _ = flujo
    contenido = _xlsx([["Concepto", "2022"], ["Ingresos", "=VLOOKUP(1,Z1:Z2,1)"]])
    r = cargar_confirmado(client, "/api/analisis-rapido", data={"periodo": "2026-09", "notificar": "false"},
                    files={"archivos": ("calc.xlsx", contenido, XLSX)})
    assert r.status_code == 422
    assert "fórmulas sin resultado guardado" in r.json()["detail"]


def test_encabezado_regular_pegado_al_cuadro_anterior_se_separa():
    primero = _cuadro("Exportaciones", "Región", ANIOS, REGIONES)
    # Sin fila vacía ni título, pero con períodos en secuencia regular: es el encabezado de otro cuadro.
    segundo = _cuadro("x", "Región", TRIMESTRES, REGIONES)[2:]
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("expo.xlsx", _xlsx(primero + segundo))])
    hoja = cobertura["hojas"][0]
    assert hoja["cuadros_apilados"] == [10] and "encabezados_no_separados" not in hoja
    assert len(cobertura["bloques"]) == 2


def test_encabezado_de_otro_cuadro_que_no_se_separa_se_declara():
    from services.reportes.registro import construir

    primero = _cuadro("Exportaciones", "Región", ANIOS, REGIONES)
    # Sin fila vacía ni título entre los cuadros y con períodos salteados: no se reconoce como encabezado.
    segundo = _cuadro("x", "Región", ["T1 2024", "T3 2024", "T4 2024", "T2 2025", "T3 2025"], REGIONES)[2:]
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("expo.xlsx", _xlsx(primero + segundo))])
    hoja = cobertura["hojas"][0]
    assert hoja["encabezados_no_separados"][0]["fila"] == 10
    informe = models.Informe(id=1, datos=datos, saneamiento={"excel": cobertura}, periodo="2026-09")
    reg = construir(informe, [], {})
    assert any(p["donde"].endswith("fila 10") and "otro cuadro" in p["motivo"] for p in reg["pendientes"])
    assert reg["primera_linea"].startswith("LECTURA PARCIAL")


def test_csv_con_una_linea_de_mas_campos_no_se_rechaza_entero():
    texto = "Concepto;2022;2023\nPersonal;1.200;1.300\nBienes;400;450;nota suelta\nServicios;300;320\n".encode()
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("gasto.csv", texto)])
    assert [f["Concepto"] for f in datos] == ["Personal", "Servicios"]
    assert lectura[0]["filas_descartadas"] == [3]
    assert any("fila 3" in a for a in lectura[0]["avisos"])
