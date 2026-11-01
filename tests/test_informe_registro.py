"""El informe dice la verdad: un registro único de lo leído y controlado, sin contradicciones."""
import datetime
from types import SimpleNamespace

from services.reportes.registro import construir


def informe(**kw):
    base = dict(id=1, datos=[{"Concepto": "Salud", "2023": 1.0}], saneamiento={}, periodo=None,
                creado_en=datetime.datetime(2026, 10, 3), devolucion=SimpleNamespace(cobertura={}), hallazgos=[])
    base.update(kw)
    return SimpleNamespace(**base)


def nota(regla, **ev):
    return dict(lente="cronista", modo="control_tabular", severidad="baja", descripcion=f"nota {regla}",
                evidencia=dict(regla=regla, naturaleza="contexto", nota_cruce=True, **ev))


LENTES_OK = [{"lente": "ajedrecista", "estado": "con_senales", "hallazgos": 1, "ejecutado": True}]


def test_lo_no_leido_y_no_controlado_va_en_la_primera_linea_del_informe_y_la_pantalla():
    from services.reportes.markdown import render_reporte_markdown

    excel = {"hojas": [
        {"archivo": "a.xlsx", "hoja": "Datos", "estado": "incluida", "filas_preparadas": 5},
        {"archivo": "a.xlsx", "hoja": "Notas", "estado": "no_interpretable", "motivo": "No se reconoció un encabezado tabular",
         "filas_preparadas": 0},
        {"archivo": "a.xlsx", "hoja": "Oculta", "estado": "incluida", "filas_preparadas": 3, "oculta": True,
         "formulas_sin_valor": [1, 2], "celdas_no_interpretables": 4, "campo_nuevo_de_otra_etapa": "x"},
    ]}
    cob = {"lentes": LENTES_OK + [{"lente": "rizoma", "estado": "no_evaluable", "motivo": "Cuadro ancho de años", "ejecutado": False}],
           "excel": excel}
    i = informe(saneamiento={"archivos_origen": ["a.xlsx"], "excel": excel}, devolucion=SimpleNamespace(cobertura=cob))
    reg = construir(i, [], cob)
    assert reg["estado"] == "parcial"
    for texto in ("Notas", "4 celdas", "2 fórmulas", "Oculta", "Conexiones exploratorias"):
        assert texto in reg["primera_linea"], texto
    assert reg["archivos"][0]["extras"] == {"Oculta": {"campo_nuevo_de_otra_etapa": "x"}}  # tolerante a campos nuevos
    md = render_reporte_markdown(i, [], False, True, pieza="ejecutivo")
    assert md.split("\n")[2].startswith("**LECTURA PARCIAL.")  # primera línea después del título


def test_registro_lectura_generico_de_otras_etapas_se_consume():
    i = informe(saneamiento={"archivos_origen": ["x.pdf"], "registro_lectura": [
        {"archivo": "x.pdf", "pagina": 151, "estado": "no_leido", "motivo": "fuera del límite de páginas"}]})
    reg = construir(i, [], {"lentes": LENTES_OK})
    assert "página 151" in reg["primera_linea"] and "registro_lectura" in reg["fuentes"]


def test_interdocumental_sin_contradiccion_con_los_cruces_realizados():
    cob = {"lentes": LENTES_OK, "control_interdocumental": {"estado": "no_evaluable", "motivo": "Los cuadros se revisaron por separado"}}
    i = informe(saneamiento={"archivos_origen": ["e23.xlsx", "e24.xlsx"]})
    reg = construir(i, [nota("cobertura_cruce_ediciones", filas_emparejadas=7, filas_totales=7)], cob)
    assert reg["cruces"]["estado"] == "evaluado" and "7 de 7 filas emparejadas" in reg["cruces"]["texto"]
    reg = construir(i, [nota("cruce_no_comparable", dimensiones_no_comparables=["concepto"])], cob)
    assert reg["cruces"]["estado"] == "no_comparable" and "concepto" in reg["cruces"]["texto"]


def test_dos_archivos_sin_origen_por_fila_no_dice_que_hay_un_solo_archivo():
    cob = {"lentes": LENTES_OK, "control_interdocumental": {"estado": "no_aplicable", "motivo": "No hay dos archivos que conciliar"}}
    i = informe(saneamiento={"archivos_origen": ["a.csv", "b.csv"]}, datos=[{"x": 1}, {"x": 2}])
    reg = construir(i, [], cob)
    assert "No hay dos archivos" not in reg["cruces"]["texto"]
    assert "2 archivos" in reg["cruces"]["texto"] and "archivo de origen" in reg["primera_linea"]


def test_periodo_por_defecto_no_se_presenta_como_declarado():
    from services.reporte_ejecutivo import lineas

    i = informe(periodo="2026-10", datos=[{"año": 2019, "v": 1}, {"año": 2024, "v": 2}])
    texto = "\n".join(lineas(i, []))
    assert "no declarado" in texto and "Período declarado: 2026-10" not in texto
    assert "Diferencia temporal a aclarar" not in texto
    i.saneamiento = {"periodo_declarado": True}
    texto = "\n".join(lineas(i, []))
    assert "Diferencia temporal a aclarar" in texto


def test_tabla_chica_leida_completa_no_es_insuficiente():
    from services.resultado_revision import alcance

    pdf = dict(cantidad_archivos=1, paginas_documento=1, paginas_analizadas=1, filas_pdf=6, filas_pdf_utiles=6,
               cuadros_pdf=1, modos_extraccion=["tabla"])
    i = informe(saneamiento={"pdf": pdf})
    assert alcance(i)["pdf"]["estado"] == "completa"
    assert construir(i, [], {"lentes": LENTES_OK})["estado"] != "insuficiente"


def test_alcance_con_enie_cero_casos_y_proximos_pasos_no_genericos():
    from services.reporte_ejecutivo import lineas

    i = informe(devolucion=SimpleNamespace(cobertura={"estado": "CON_SENALES_COMUNICABLES", "lentes": LENTES_OK}))
    texto = "\n".join(lineas(i, []))
    assert "SENALES" not in texto
    assert "0 casos de revisión" in texto
    assert "Revisar primero los casos estructurales" not in texto
    assert "No hay casos ni pendientes de lectura" in texto


def test_cobertura_parcial_una_sola_vez_y_diciendo_que_falta():
    from services.reportes.markdown import render_reporte_markdown

    cob = {"estado": "COBERTURA_PARCIAL", "lentes": LENTES_OK + [
        {"lente": "rizoma", "estado": "no_evaluable", "motivo": "Se requieren dos columnas numéricas", "ejecutado": False}]}
    pdf = dict(cantidad_archivos=1, paginas_documento=10, paginas_analizadas=4, filas_pdf=60, filas_pdf_utiles=60,
               cuadros_pdf=2, modos_extraccion=["tabla"], truncado_por_paginas=True)
    i = informe(saneamiento={"pdf": pdf, "archivos_origen": ["x.pdf"]}, devolucion=SimpleNamespace(cobertura=cob))
    md = render_reporte_markdown(i, [], False, True, pieza="ejecutivo")
    assert md.count("COBERTURA PARCIAL") + md.count("LECTURA PARCIAL") == 1
    primera = md.split("\n")[2]
    assert "páginas 5 a 10" in primera and "Conexiones exploratorias" in primera


def test_un_solo_modelo_no_es_coincidencia_entre_varios_y_cada_lectura_se_atribuye():
    from services.devolucion import armar_mensaje

    h = dict(lente="ajedrecista", modo="control_tabular", severidad="alta", descripcion="Señal", evidencia={"regla": "x"})
    consolidado = {"coincidencias": [], "divergencias": [],
                   "priorizacion_sin_contraste": ["Hallazgo #0: priorizado por 1 de 1 modelo que lo recibió (gpt)."],
                   "hallazgos_singulares": [{"modelo": "gpt", "rol": "principal", "lectura": "Revisar.",
                                             "lectura_atribuida": "gpt (principal): Revisar."}],
                   "lecturas_descartadas": [{"modelo": "gemini", "rol": "respaldo", "motivos": ["niega una señal del motor"]}],
                   "linea_estado": "Estado de la lectura con IA: respondieron gpt (principal). Señales leídas por algún modelo: 1 de 1."}
    mensaje, _ = armar_mensaje([h], consolidado)
    assert "Varios modelos coincidieron" not in mensaje
    assert "gpt (principal): Revisar." in mensaje and "1 de 1 modelo" in mensaje
    assert "Estado de la lectura con IA" in mensaje
    assert "gemini" in mensaje and "niega una señal del motor" in mensaje


def test_estado_del_modelo_sin_lectura_no_dice_que_leyo_las_senales():
    from services.reportes.markdown import _estado_modelo_reporte

    solo_exploro = SimpleNamespace(contenido={"estrategia": {}}, error="Lectura de señales: tiempo agotado")
    assert "leyó las señales" not in _estado_modelo_reporte(solo_exploro)
    assert "tiempo agotado" in _estado_modelo_reporte(solo_exploro)
    assert "leyó las señales" in _estado_modelo_reporte(SimpleNamespace(contenido={"lectura": "ok"}, error=None))


def test_lectura_de_otras_etapas_fallidos_no_revisadas_y_avisos_en_la_primera_linea():
    san = {
        "archivos_origen": ["a.xlsx", "roto.csv"],
        "lectura_archivos": [
            {"archivo": "a.xlsx", "tipo_detectado": "xlsx", "estado": "leido", "filas": 5, "avisos": []},
            {"archivo": "roto.csv", "tipo_detectado": "csv", "estado": "fallido", "motivo": "codificación no reconocida", "avisos": []},
        ],
        "avisos_lectura": ["«a.xlsx» · Datos: 3 celdas con fórmula sin resultado guardado (B4, C4, D4)"],
        "pdf": {"avisos": ["P05.pdf: páginas 151 a 200 fuera del límite"]},
        "excel": {"hojas": [
            {"archivo": "a.xlsx", "hoja": "Datos", "estado": "incluida", "filas_preparadas": 5,
             "formulas_sin_valor": {"celdas": 3, "ejemplos": ["B4"], "mensaje": "x"},
             "visibilidad": {"estado_hoja": "hidden", "filas_ocultas": [], "columnas_ocultas": []}},
            {"archivo": "a.xlsx", "hoja": "Anexo", "estado": "sin_datos", "filas_preparadas": 0,
             "no_revisada": {"celdas_numericas": 40, "motivo": "sin encabezado de períodos"}},
        ]},
    }
    reg = construir(informe(saneamiento=san), [], {"lentes": LENTES_OK})
    primera = reg["primera_linea"]
    assert "roto.csv" in primera and "codificación no reconocida" in primera
    assert "Anexo" in primera and "40 celdas numéricas sin revisar" in primera
    assert "3 fórmulas" in primera and "Datos" in reg["archivos"][0]["ocultas"]
    assert "Avisos de lectura" in primera and "páginas 151 a 200" in " ".join(reg["avisos"])
    assert "lectura_archivos" in reg["fuentes"]


def test_ubicacion_de_contenido_no_visible_junto_a_la_senal():
    from services.reporte_ejecutivo import lineas

    h = dict(id=1, lente="ajedrecista", modo="control_tabular", severidad="alta", descripcion="Dato", pregunta_institucional="?",
             evidencia=dict(regla="signo_aislado", hoja="Datos", celda="C5", periodo=2020, visibilidad_origen=["hoja «Datos» oculta"]))
    texto = "\n".join(lineas(informe(), [h]))
    assert "hoja «Datos» oculta" in texto
