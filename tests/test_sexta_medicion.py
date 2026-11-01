"""Casos de la sexta medición que el informe callaba o no señalaba (14/10/2026)."""

from routers.carga_rapida import _celdas_marcadas_revision, _derivados_revision
from services.controles_excel import rubro_escala
from services.reporte_ejecutivo import _contenido_oculto
from services.reportes import registro


def _serie(etiqueta, valores, nivel=0, fila=1):
    periodos = list(range(2017, 2017 + len(valores)))
    return {"archivo": "a.xlsx", "hoja": "Cuadro", "cuadro": 1, "etiqueta": etiqueta, "nivel": nivel,
            "periodos": periodos, "valores": valores, "celdas": [f"{c}{fila}" for c in "BCDEFGHIJ"[: len(valores)]],
            "periodos_validos": periodos, "unidad": None}


def _cuadro(entre_rios):
    filas = [
        _serie("Buenos Aires", [2517, 2440, 2414, 2380, 2625], fila=2),
        _serie("Córdoba", [1780, 1786, 1802, 1688, 1848], fila=3),
        _serie("Entre Ríos", entre_rios, fila=4),
    ]
    total = [a + b + c for a, b, c in zip([2517, 2440, 2414, 2380, 2625], [1780, 1786, 1802, 1688, 1848],
                                          [1411, 1447, 1445, 1384, 1546])]
    return [_serie("Total", total, fila=5)] + filas


def test_rubro_entero_en_otra_escala_se_senala():
    serie = _cuadro([1411000, 1447000, 1445000, 1384000, 1546000])
    hallazgos = rubro_escala.analizar(serie)
    assert len(hallazgos) == 1
    ev = hallazgos[0]["evidencia"]
    assert ev["regla"] == "rubro_en_otra_escala" and ev["factor_que_cierra"] == 0.001
    assert ev["indicador"] == "Entre Ríos" and hallazgos[0]["severidad"] == "alta"


def test_cuadro_que_cierra_no_da_senal():
    assert rubro_escala.analizar(_cuadro([1411, 1447, 1445, 1384, 1546])) == []


def test_miles_leidos_como_decimales_no_se_confunde_con_un_rubro_en_otra_escala():
    # «6,097» leído como 6,097: todas las filas tienen tres decimales salvo la que no traía coma.
    total = [(6097 + 2786 + 881) / 1000, (6297 + 2863 + 896) / 1000, (6552 + 3025 + 984) / 1000,
             (6341 + 2926 + 910) / 1000, (6190 + 3001 + 891) / 1000]
    series = [_serie("Total", total, fila=5), _serie("Algodón", [6.097, 6.297, 6.552, 6.341, 6.19], fila=2),
              _serie("Poliéster", [2.786, 2.863, 3.025, 2.926, 3.001], fila=3),
              _serie("Otras", [881, 896, 984, 910, 891], fila=4)]
    assert rubro_escala.analizar(series) == []


class _Informe:
    def __init__(self, saneamiento):
        self.saneamiento = saneamiento
        self.devolucion = None
        self.hallazgos = []
        self.datos = [{"Rubro": "x", "2020": 1}]


def test_cierres_sin_dato_van_al_comienzo():
    informe = _Informe({"archivos_origen": ["h.xlsx"], "estructura_revision": {
        "cantidad_cierres": 7, "relaciones_candidatas": 1,
        "cierres_sin_comprobar": [{"concepto": "Total", "periodo": 2020}, {"concepto": "Total", "periodo": 2024}]}})
    reg = registro.construir(informe, [], {})
    assert reg["estado"] != "completo"
    assert any("«Total» en 2020, 2024" in p["donde"] for p in reg["pendientes"])


def test_celdas_marcadas_en_la_revision_de_lectura_van_al_comienzo():
    csv = "Cuadro 1. Producción;Columna 2;Columna 3\nEne 2025 3.849;1515;1411\nFeb 2025 3.911;1446;1363\n".encode()
    marcas = _celdas_marcadas_revision([("t (revisado).csv", csv)])
    assert marcas["celdas_marcadas"] >= 2
    informe = _Informe({"archivos_origen": ["t (revisado).csv"],
                        "lectura_revisada": {"archivo_original": "t.pdf", **marcas}})
    reg = registro.construir(informe, [], {})
    assert any("revisión de lectura" in p["donde"] for p in reg["pendientes"])


def test_tabla_revisada_sin_marcas_no_agrega_nada():
    csv = "Mes;Ventas;Costos\nEne 2025;1515;1411\nFeb 2025;1446;1363\n".encode()
    assert _celdas_marcadas_revision([("t (revisado).csv", csv)]) == {}


def test_archivo_derivado_a_revision_se_declara():
    assert _derivados_revision("a.pdf\nC:\\\\docs\\\\b.pdf\n\na.pdf") == ["a.pdf", "b.pdf"]
    informe = _Informe({"archivos_origen": ["x.xlsx"], "derivados_revision_lectura": ["dañado.pdf"]})
    reg = registro.construir(informe, [], {})
    assert any(p.get("archivo") == "dañado.pdf" for p in reg["pendientes"])


def test_hoja_oculta_se_dice_al_comienzo():
    excel = {"hojas": [{"hoja": "Base mensual", "visibilidad": {"estado_hoja": "hidden", "filas_ocultas": [],
                                                                "columnas_ocultas": []}}]}
    assert _contenido_oculto(excel) == "hoja «Base mensual» (la hoja está oculta)"


def test_frase_llana_del_rubro_en_otra_escala():
    from services.reportes.lenguaje_llano import resumen_llano

    e = {"regla": "rubro_en_otra_escala", "indicador": "Entre Ríos", "fila_total": "Total", "factor_que_cierra": 0.001,
         "periodos_que_cierran": 9, "periodos_comparables": 9}
    assert resumen_llano({"lente": "ajedrecista", "evidencia": e}) == (
        "«Entre Ríos» parece estar en otra escala: «Total» cierra en 9 de 9 períodos si sus valores se dividen por 1.000.")
