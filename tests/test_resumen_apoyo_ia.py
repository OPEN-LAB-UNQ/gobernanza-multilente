"""El resumen de apoyo de IA distingue la lectura de señales de la exploración del libro.

Informe 244 (28/09/2026): el resumen decía «respuesta estructurada utilizable» para cuatro
modelos mientras el detalle técnico mostraba que sólo uno había completado la exploración.
"""
from services import reporte_ejecutivo


def test_estado_de_exploracion_con_motivo_en_lenguaje_llano():
    f = reporte_ejecutivo._estado_exploracion
    assert f({"evaluada": True, "elementos_cubiertos": 1053, "elementos_totales": 1053}) == "completada (1053/1053 elementos)"
    assert f({"evaluada": False, "motivos": ["global-1: 429 RESOURCE_EXHAUSTED"]}).endswith("el proveedor no tenía cuota disponible")
    assert f({"evaluada": False, "motivos": ["Salida truncada por límite de tokens"]}).endswith("se cortó por límite de extensión")
    assert f({"evaluada": False, "motivos": ["Respuesta no utilizable tras validación de esquema"]}).endswith("no respetó el formato requerido")
    assert f({"evaluada": False, "motivos": []}) == "no completada: no se completó"


def test_el_resumen_no_presenta_como_completa_una_exploracion_fallida():
    # 0.9.6: el informe ejecutivo resume el apoyo de IA en una línea («disponible para N señales» o
    # «no disponible»), sin fallas internas; el detalle de cada intento queda en el reporte completo.
    import inspect
    fuente = inspect.getsource(reporte_ejecutivo.lineas)
    assert "respuesta estructurada utilizable" not in fuente
    cob = {"manifiesto": {"modelos": [{"proveedor": "global-1", "respondio": True, "alcance_ia": {"hallazgos_enviados": 5},
                                       "estrategia_semantica": {"evaluada": False, "motivos": ["Salida truncada por límite de tokens"]}}]}}
    linea = reporte_ejecutivo._linea_ia(cob)
    assert "5 señales" in linea and "completada" not in linea and "se cortó" not in linea
    assert "no disponible" in reporte_ejecutivo._linea_ia({})


def test_un_corte_por_tiempo_se_nombra_asi():
    f = reporte_ejecutivo._estado_exploracion
    assert f({"evaluada": False, "motivos": ["local-1: The read operation timed out"]}) == "no completada: no respondió a tiempo"


def test_el_reporte_completo_tambien_distingue_las_dos_tareas():
    import inspect

    from services.reportes import markdown
    fuente = inspect.getsource(markdown)
    assert "exploración del libro" in fuente
    assert "respondió y su lectura fue incorporada" not in inspect.getsource(markdown._estado_modelo_reporte)
