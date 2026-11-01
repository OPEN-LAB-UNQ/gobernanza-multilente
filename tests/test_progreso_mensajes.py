"""La pantalla de progreso cuenta como el comprobante y habla en lenguaje llano.

Informe 245 (28/09/2026): mostraba «Evolución temporal: 259 señales para revisar» mientras el
comprobante separaba esas 259 variaciones como contexto; los motivos de la IA aparecían en jerga
(«local-1: Respuesta no utilizable tras validación de esquema») y «no aplicable» se veía como alerta.
"""
from services.jobs import _evento_analisis


def test_las_variaciones_de_contexto_no_se_cuentan_como_senales():
    evento = _evento_analisis({"tipo": "lente", "lente": "cronista", "cantidad": 259, "contexto": 259}, 1)
    assert evento["detalle"] == "259 variaciones separadas como contexto, no como error."
    mixto = _evento_analisis({"tipo": "lente", "lente": "cronista", "cantidad": 20, "contexto": 4}, 1)
    assert mixto["detalle"] == "16 señales para revisar; 4 variaciones separadas como contexto, no como error."
    uno = _evento_analisis({"tipo": "lente", "lente": "cronista", "cantidad": 1, "contexto": 1}, 1)
    assert uno["detalle"] == "1 variación separada como contexto, no como error."


def test_sin_senales_en_lenguaje_llano():
    assert _evento_analisis({"tipo": "lente", "lente": "matematico", "cantidad": 0}, 1)["detalle"] == "Sin señales para revisar."


def test_no_aplicable_es_informativo_y_no_una_alerta():
    evento = _evento_analisis({"tipo": "lente", "lente": "radiologo", "cantidad": 0,
                               "condiciones": {"estado": "no_aplicable", "motivo": "Fuera del dominio"}}, 1)
    assert evento["estado"] == "informativo" and evento["mensaje"].endswith("no corresponde a este archivo.")
    no_evaluable = _evento_analisis({"tipo": "lente", "lente": "rizoma", "cantidad": 0,
                                     "condiciones": {"estado": "no_evaluable", "motivo": "x"}}, 1)
    assert no_evaluable["estado"] == "advertencia"


def test_el_motivo_de_la_ia_se_explica_sin_jerga():
    evento = _evento_analisis({"tipo": "modelo", "modelo": "renderix", "ok": True, "exploracion_completada": False,
                               "motivos_exploracion": ["local-1: Respuesta no utilizable tras validación de esquema"]}, 1)
    assert evento["mensaje"] == "RENDERIX: leyó las señales; la exploración del libro quedó parcial."
    assert evento["estado"] == "informativo"
    assert evento["detalle"] == "La respuesta no respetó el formato requerido. No afecta a los controles automáticos."
    assert "local-1" not in evento["detalle"]


def test_sin_contexto_semantico_no_se_anuncia_una_exploracion():
    # CSV, PDF o informes sin contexto: exploracion_completada llega como None.
    evento = _evento_analisis({"tipo": "modelo", "modelo": "gpt", "ok": True, "exploracion_completada": None}, 1)
    assert evento["mensaje"] == "GPT: lectura de las señales recibida." and "exploración" not in evento["mensaje"]


def test_si_fallan_las_dos_tareas_se_dicen_las_dos():
    evento = _evento_analisis({"tipo": "modelo", "modelo": "deepseek", "ok": False, "exploracion_completada": False,
                               "motivos_exploracion": ["Salida truncada por límite de tokens"], "error": "x"}, 1)
    assert evento["mensaje"] == "DEEPSEEK: no pudo leer las señales ni completar la exploración del libro."


def test_sugerencias_de_alumnos_en_pantalla():
    """Sugerencias del 28/09: opcionalidad clara, acción que se guarda y cuánto lleva la Incubadora."""
    from pathlib import Path
    static = Path(__file__).resolve().parent.parent / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert "(opcional, recomendado)" in html and "podés analizar sin abrirlas" in html
    assert "Evaluación de IA responsable (protocolo R-1)" in html
    assert "No hace falta responder todas las preguntas" in html
    assert "Ya lo respondí" in js and "Dar por respondido" not in js
