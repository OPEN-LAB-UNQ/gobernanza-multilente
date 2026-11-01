"""0.10.29: totales por panel, «Total» arriba y columnas con guiones; resguardos ante datos no publicados."""
from io import BytesIO

from openpyxl import Workbook

from services import carga_archivos, controles_excel, excel_cobertura
from services.sanitizacion import sanear


def analizar(filas, nombre="cuadro.xlsx"):
    wb = Workbook()
    ws = wb.active
    ws.title = "2024"
    for fila in filas:
        ws.append(fila)
    buf = BytesIO()
    wb.save(buf)
    contenido = buf.getvalue()
    datos, cob = carga_archivos.parse_archivos_con_cobertura([(nombre, contenido)])
    san, rep, _ = excel_cobertura.preparar(datos, cob, lambda f: (f, {}), sanear)
    return [((h.get("evidencia") or {}).get("regla"), (h.get("evidencia") or {}).get("celda"))
            for h in controles_excel.analizar([(nombre, contenido)], san, rep["excel"])]


CARRERAS = [
    ["Estudiantes, nuevos inscriptos y egresados por carrera. Año 2024"],
    ["Título", "Estudiantes", None, None, "Nuevos inscriptos", None, None],
    [None, "Total", "Varón", "Mujer", "Total", "Varón", "Mujer"],
    ["Total", 1081, 186, 895, 217, 49, 168],
    ["Enfermero", "-", "-", "-", "-", "-", "-"],
    ["Licenciado en Educación Física", 78, 48, 30, 31, 19, 12],
    ["Licenciado en Enfermería", 279, 36, 243, 61, 8, 53],
    ["Licenciado en Kinesiología", 37, 16, 21, 24, 10, 14],
    ["Licenciado en Órtesis", 68, 32, 36, 11, 4, 7],
    ["Licenciado en Rehabilitación", 81, 10, 71, "-", "-", "-"],
    ["Licenciado en Terapia Ocupacional", 526, 40, 486, 90, 8, 82],
    ["Licenciado en Terapia Ocupacional - Ciclo", 4, 1, 3, "-", "-", "-"],
    ["Técnico en Ortesis", "-", "-", "-", "-", "-", "-"],
    ["Terapista Ocupacional", 8, 3, 5, "-", "-", "-"],
]


def test_original_sin_senales():
    assert not [x for x in analizar(CARRERAS) if x[0] in ("columna_total_no_cierra", "total_columna_no_cierra")]


def test_error_en_columna_con_guiones_bajo_un_total_arriba_se_detecta():
    filas = [list(f) for f in CARRERAS]
    filas[3][5] = 51.47  # varones nuevos inscriptos en el total: ni la fila ni la columna cierran
    reglas = analizar(filas)
    assert ("columna_total_no_cierra", "E4") in reglas and ("total_columna_no_cierra", "F4") in reglas


def test_componente_alterado_en_un_panel_se_detecta():
    filas = [list(f) for f in CARRERAS]
    filas[6][2] = 63  # varones de Enfermería: su fila deja de cerrar con «Estudiantes Total»
    assert ("componente_no_cierra_fila_y_columna", "C7") in analizar(filas)  # la celda alterada, por triangulación


def test_dato_no_publicado_explica_la_diferencia():
    filas = [["Distribución de los hogares por cantidad de hijos (%)"], ["Edad", "Total", "1", "2", "3"]]
    filas += [[f"{20 + 5 * i}-{24 + 5 * i}", 100, 50.1 + i, 30.4, 19.5 - i] for i in range(6)]
    filas.append(["60-64", 100, 78.2, 19.0, "---"])
    assert not [x for x in analizar(filas) if x[0] == "columna_total_no_cierra"]


def test_diferencia_igual_a_otra_columna_no_es_un_total_que_falla():
    filas = [["Viviendas y población por municipio"], ["Municipio", "Población", "En viviendas particulares", "En viviendas colectivas", "En situación de calle"]]
    filas += [[f"Municipio {i}", 10000 + 37 * i + 211, 10000 + 37 * i, 211, "-"] for i in range(8)]
    filas.append(["Municipio 9", 203043, 201764, 1237, 42])
    assert not [x for x in analizar(filas) if x[0] == "columna_total_no_cierra"]


def test_distribucion_que_suma_99_8_no_es_un_total_que_falla():
    filas = [["Mujeres por condición de maternidad (%)"], ["Edad", "Mujeres", None], [None, "Total", "No madres", "Madres"]]
    filas += [["Total", 100, 38.7, 61.1], ["14-19", 100, 96.3, 3.7], ["20-24", 100, 84.6, 15.4], ["25-29", 100, 69.3, 30.7],
              ["30-39", 100, 36.1, 63.7], ["40-49", 100, 20.5, 79.5], ["50-59", 100, 17.7, 82.3]]
    assert not [x for x in analizar(filas) if x[0] == "columna_total_no_cierra"]


def test_limites_del_intervalo_de_confianza_no_se_suman():
    from services.controles_excel.transversal import NO_SUMABLE
    assert all(NO_SUMABLE.search(s) for s in ("LI", "LS", "Límite superior", "CV (%)", "Intervalo de confianza"))
    assert not any(NO_SUMABLE.search(s) for s in ("Licenciados", "Liquidación", "Lima", "Total"))


def test_anios_en_filas_controlan_total_estatal_privado():
    filas = [["Establecimientos y cargos docentes. Años 2019-2023"],
             ["Año", "Establecimientos", None, None, "Cargos docentes", None, None],
             [None, "Total", "Estatal", "Privado", "Total", "Estatal", "Privado"]]
    datos = [(835, 687, 148, 21043, 18023, 3020), (838, 688, 150, 21278, 18244, 3034), (851, 703, 148, 22598, 19364, 3234),
             (863, 713, 150, 22925, 19775, 3150), (879, 724, 155, 24232, 20905, 3327)]
    filas += [[str(2019 + i), *d] for i, d in enumerate(datos)]
    assert not [x for x in analizar(filas) if x[0] == "columna_total_no_cierra"]
    filas[5][1] = 876.53
    assert ("columna_total_no_cierra", "B6") in analizar(filas)


def test_columna_de_conteo_con_guiones_no_es_dato_personal():
    from services.sanitizacion import columna_sensible
    assert not columna_sensible("Tipo de delito Contra las personas (1)", [32, 32, "-", 40, 11, 1943, "-"])
    assert columna_sensible("Personas", ["Juan Pérez", "-", "Ana Gómez"])


def test_categoria_tipo_de_con_cifras_no_es_dato_personal():
    from services.sanitizacion import columna_sensible
    assert not columna_sensible("Tipo de población usuaria Cliente oficial", [89547335, 104631223.2, 96369537.2])
    assert columna_sensible("Cliente", ["ACME SA", "Juan Pérez"])
    assert columna_sensible("Tipo de documento Nombre", ["Juan"])  # lo nominal se excluye siempre


def test_total_publicado_redondeado_no_falla_y_300000_de_mas_si():
    filas = [["Energía eléctrica facturada (kWh)"], ["Año", "Total", "Residencial", "Comercial", "Otro"]]
    filas += [[f"Mes {i}", 1000000 + 3 * i + 0.4, 400000.21 + i, 500000.13 + i, 100000.12 + i] for i in range(8)]
    filas[3][1] = round(filas[3][2] + filas[3][3] + filas[3][4])  # total redondeado a entero: cierra
    assert not [x for x in analizar(filas) if "cierra" in (x[0] or "")]
    filas[5][1] += 300000
    assert ("fila_no_cierra_total", "B6") in analizar(filas)


def test_decimal_en_una_columna_de_conteos():
    filas = [["Establecimientos asistenciales por departamento"], ["Departamento", "Hospitales", "Centros de salud"]]
    filas += [[f"Departamento {i}", 3 + i % 4, 5 + i % 3] for i in range(12)]
    assert not [x for x in analizar(filas) if x[0] == "decimal_en_columna_de_enteros"]
    filas[7][2] = 19.54
    assert ("decimal_en_columna_de_enteros", "C8") in analizar(filas)


def test_ruido_de_punto_flotante_y_columna_de_ceros_no_son_decimal_aislado():
    filas = [["Encuesta"], ["Rubro", "Porcentaje de locales", "Ns/Nc"]]
    filas += [[f"Rubro {i}", 30 + i, 0] for i in range(12)]
    filas[6][1] = 57.99999999999999
    filas[9][2] = 0.1
    assert not [x for x in analizar(filas) if x[0] == "decimal_en_columna_de_enteros"]


def test_columna_periodo_numerica_no_entra_en_la_suma():
    filas = [["Exportaciones mensuales"], ["Período", "Total", "Primarios", "Manufacturas", "Combustibles"]]
    filas += [[2023 + m / 100, 300.0 + 7 * m, 100.0 + 3 * m, 150.0 + 2 * m, 50.0 + 2 * m] for m in range(1, 13)]
    assert not [x for x in analizar(filas) if "cierra" in (x[0] or "")]
    filas[8][1] += 40
    assert ("fila_no_cierra_total", "B9") in analizar(filas)
