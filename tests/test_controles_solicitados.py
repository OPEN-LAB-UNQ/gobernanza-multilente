from types import SimpleNamespace

import models
from services import controles_solicitados, guardrails
from services.reportes import markdown

ORIENTACION = (
    "Verificar si la deuda bruta total es la suma de las tres filas inferiores "
    "e identificar el mayor incremento porcentual entre meses."
)


def _datos(deuda_agosto=150):
    return [
        {"concepto": "Deuda bruta total", "2026-06": 100, "2026-07": 120, "2026-08": deuda_agosto},
        {"concepto": "Títulos públicos", "2026-06": 40, "2026-07": 50, "2026-08": 60},
        {"concepto": "Organismos internacionales", "2026-06": 30, "2026-07": 40, "2026-08": 50},
        {"concepto": "Otras obligaciones", "2026-06": 30, "2026-07": 30, "2026-08": 40},
    ]


def test_responde_suma_y_mayor_incremento_con_evidencia():
    resultado = controles_solicitados.evaluar(_datos(), ORIENTACION)

    assert resultado["estado"] == "evaluado"
    assert resultado["hallazgos"] == []
    assert [control["estado"] for control in resultado["controles"]] == ["conforme", "informado"]
    variacion = resultado["controles"][1]
    assert variacion["evidencia"]["mayor_incremento"]["desde"] == "2026-07"
    assert variacion["evidencia"]["mayor_incremento"]["hasta"] == "2026-08"
    assert variacion["evidencia"]["mayor_incremento"]["variacion_pct"] == 25.0


def test_total_que_no_cierra_produce_hallazgo_aritmetico():
    resultado = controles_solicitados.evaluar(_datos(deuda_agosto=155), ORIENTACION)

    assert resultado["estado"] == "evaluado_con_observaciones"
    assert resultado["controles"][0]["estado"] == "observado"
    hallazgo = resultado["hallazgos"][0]
    assert hallazgo["lente"] == "ajedrecista"
    assert hallazgo["severidad"] == "alta"
    assert hallazgo["evidencia"]["comparaciones"][0]["periodo"] == "2026-08"
    assert hallazgo["evidencia"]["comparaciones"][0]["diferencia"] == 5.0


def test_declara_no_evaluable_si_no_identifica_la_fila_pedida():
    datos = [{"concepto": "Otro indicador", "2026-06": 10, "2026-07": 12}]
    resultado = controles_solicitados.evaluar(datos, ORIENTACION)

    assert resultado["estado"] == "no_evaluable"
    assert all(control["estado"] == "no_evaluable" for control in resultado["controles"])
    assert "No se identificó" in resultado["controles"][0]["resultado"]


def test_cobertura_distingue_pregunta_no_evaluada_de_cero_senales():
    informe = SimpleNamespace(
        datos=[{"concepto": "Otro indicador", "2026-06": 10}],
        saneamiento={
            "controles_solicitados": {
                "estado": "no_evaluable",
                "controles": [{"estado": "no_evaluable"}],
            }
        },
    )

    cobertura = guardrails.cobertura_informe(informe, [])
    assert cobertura["estado"] == "PREGUNTA_NO_EVALUADA"


def test_reporte_no_presenta_como_conforme_un_control_no_evaluado():
    control = {
        "codigo": "suma_total_componentes",
        "nombre": "Total versus componentes",
        "estado": "no_evaluable",
        "resultado": "No se identificó la fila total mencionada.",
    }
    area = models.Area(nombre="Área de prueba", codigo="TEST")
    informe = models.Informe(
        area=area,
        periodo="2026-09",
        dominio="general",
        datos=[{"concepto": "Otro indicador", "2026-06": 10}],
        saneamiento={
            "orientacion_analisis": ORIENTACION,
            "controles_solicitados": {
                "estado": "no_evaluable",
                "controles": [control],
            },
        },
    )
    informe.devolucion = models.Devolucion(
        mensaje="Pregunta no evaluada",
        hay_hallazgos=False,
        estado="PREGUNTA_NO_EVALUADA",
        cobertura={
            "estado": "PREGUNTA_NO_EVALUADA",
            "lentes": [],
            "controles_solicitados": {
                "estado": "no_evaluable",
                "controles": [control],
            },
        },
    )

    texto = markdown.render_reporte_markdown(
        informe,
        [],
        incluir_triangulacion=False,
        incluir_devolucion=False,
    )

    assert "no pudo evaluarse por completo" in texto
    assert "Cero señales no equivale a conformidad" in texto
    assert "quedaron **no evaluados**" in texto
