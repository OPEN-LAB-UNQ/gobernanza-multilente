"""Tests de la lente Rizoma."""
from __future__ import annotations

from services.lentes import rizoma


def test_rizoma_umbral_alto_no_comunica_relacion_obvia():
    datos = [
        {"periodo": f"2026-0{i}", "Valor actual 2026": i * 10, "Valor previo 2025": i * 9}
        for i in range(1, 8)
    ]
    assert rizoma.analizar(datos) == []


def test_rizoma_detecta_asociacion_no_obvia():
    """Dos columnas sin relacion presupuestaria/fisica/temporal esperable,
    pero con correlacion casi perfecta, deben abrir una pregunta
    exploratoria (nunca causal)."""
    datos = [
        {"periodo": f"2026-0{i}", "reclamos_vecinales": i * 10, "tiempo_resolucion": i * 5}
        for i in range(1, 8)
    ]
    hallazgos = rizoma.analizar(datos)
    assert hallazgos
    assert hallazgos[0]["modo"] == "exploratorio"
    assert set(hallazgos[0]["evidencia"]["columnas"]) == {"reclamos_vecinales", "tiempo_resolucion"}
    assert "causa" not in hallazgos[0]["descripcion"].lower() or "no se comunica como causa" in hallazgos[0]["descripcion"].lower()


def test_rizoma_documenta_estadistica_muestra_y_diferencias():
    datos = [
        {"periodo": f"2026-{i:02d}", "temperatura": t, "ventas_helados": v}
        for i, (t, v) in enumerate(((18, 120), (20, 140), (22, 160), (25, 190), (28, 230), (30, 260), (33, 300), (31, 280)), 1)
    ]
    hallazgo = rizoma.analizar(datos)[0]
    ev = hallazgo["evidencia"]
    assert ev["metodo"] == "correlación de Pearson"
    assert ev["coeficiente_pearson"] == 0.9963
    assert ev["n_observaciones"] == 8
    assert ev["periodo_desde"] == "2026-01" and ev["periodo_hasta"] == "2026-08"
    assert ev["datos_faltantes"] == 0
    assert ev["correlacion_primeras_diferencias"] == 0.9721
    assert ev["limitacion_muestra"]
    assert "tercer factor" in hallazgo["pregunta_institucional"]


def test_rizoma_conserva_evidencia_del_control_negativo():
    datos = [
        {"periodo": f"2026-{i:02d}", "temperatura": t, "visitantes_museo": v}
        for i, (t, v) in enumerate(((18, 500), (20, 420), (22, 610), (25, 390), (28, 550), (30, 480), (33, 530), (31, 600)), 1)
    ]
    assert rizoma.analizar(datos) == []
    evidencia = rizoma.evidencia_control_negativo(datos)
    assert evidencia is not None
    assert evidencia["coeficiente_pearson"] == 0.2935
    assert evidencia["n_observaciones"] == 8


def test_rizoma_no_comunica_relacion_obvia():
    datos = [
        {"periodo": f"2026-0{i}", "Valor actual 2026": i * 10, "Valor previo 2025": i * 9}
        for i in range(1, 8)
    ]
    assert rizoma.analizar(datos) == []




def test_rizoma_no_comunica_flujo_operativo_obvio():
    datos = [
        {"periodo": f"2026-0{i}", "consultas": i * 10, "resueltas": i * 9, "pendientes": i}
        for i in range(1, 8)
    ]
    assert rizoma.analizar(datos) == []


def test_rizoma_comunica_demanda_con_demora_no_obvia():
    datos = [
        {"periodo": f"2026-0{i}", "reclamos_recibidos": i * 11, "tiempo_resolucion_dias": i * 4}
        for i in range(1, 8)
    ]
    hallazgos = rizoma.analizar(datos)
    assert hallazgos
    assert set(hallazgos[0]["evidencia"]["columnas"]) == {"reclamos_recibidos", "tiempo_resolucion_dias"}
    assert hallazgos[0]["evidencia"]["criterio_pertinencia"]


def test_rizoma_no_comunica_productividad_derivada_por_unidad():
 datos = [
 {"periodo": f"2024-{i:02d}", "produccion_litros": i * 1000, "litros_por_tambo_por_dia": i * 25}
 for i in range(1, 8)
 ]
 assert rizoma.analizar(datos) == []
