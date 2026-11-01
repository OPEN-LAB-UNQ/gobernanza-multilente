"""Tests de la lente Orquesta."""
from __future__ import annotations

from services.lentes import orquesta


def test_orquesta_detecta_incoherencia_demanda_personal_espera():
    """Demanda sube, personal se mantiene, espera cae fuerte -- combinacion
    que pide explicacion segun la heuristica de coherencia operativa."""
    datos = [
        {"periodo": "2026-01", "demanda_turnos": 100, "personal_disponible": 50, "tiempo_espera_promedio": 20},
        {"periodo": "2026-02", "demanda_turnos": 102, "personal_disponible": 50, "tiempo_espera_promedio": 20},
        {"periodo": "2026-03", "demanda_turnos": 103, "personal_disponible": 50, "tiempo_espera_promedio": 19},
        {"periodo": "2026-04", "demanda_turnos": 104, "personal_disponible": 50, "tiempo_espera_promedio": 19},
        {"periodo": "2026-05", "demanda_turnos": 120, "personal_disponible": 50, "tiempo_espera_promedio": 13},
    ]
    hallazgos = orquesta.analizar(datos, [])
    assert hallazgos
    assert hallazgos[0]["modo"] == "coherencia_operativa"
    assert hallazgos[0]["evidencia"]["regla"] == "coherencia_operativa_espera"


def test_orquesta_sin_falsos_positivos_variables_coordinadas():
    """Calibracion: si demanda, personal y espera se mueven de forma
    coordinada (sin la combinacion sospechosa), no debe haber hallazgos."""
    datos = [
        {"periodo": "2026-01", "demanda_turnos": 100, "personal_disponible": 50, "tiempo_espera_promedio": 20},
        {"periodo": "2026-02", "demanda_turnos": 105, "personal_disponible": 53, "tiempo_espera_promedio": 20},
        {"periodo": "2026-03", "demanda_turnos": 110, "personal_disponible": 55, "tiempo_espera_promedio": 21},
        {"periodo": "2026-04", "demanda_turnos": 108, "personal_disponible": 54, "tiempo_espera_promedio": 20},
        {"periodo": "2026-05", "demanda_turnos": 112, "personal_disponible": 56, "tiempo_espera_promedio": 21},
    ]
    assert orquesta.analizar(datos, []) == []


def test_orquesta_concilia_estados_contables_entre_archivos():
    datos = [
        {"archivo_origen": "estado_situacion_patrimonial.xlsx", "concepto": "Caja y bancos", "saldo": 1000},
        {"archivo_origen": "estado_situacion_patrimonial.xlsx", "concepto": "Resultado del ejercicio", "saldo": 300},
        {"archivo_origen": "flujo_de_caja.xlsx", "concepto": "Saldo final de efectivo", "saldo": 700},
        {"archivo_origen": "estado_de_resultados.xlsx", "concepto": "Resultado neto del ejercicio", "saldo": 250},
    ]

    hallazgos = orquesta.analizar(datos, [])
    reglas = {hallazgo["evidencia"]["regla"] for hallazgo in hallazgos}
    assert "efectivo_final_concilia_con_estado_patrimonial" in reglas
    assert "resultado_concilia_con_patrimonio" in reglas
    assert all(hallazgo["modo"] == "coherencia_interdocumental" for hallazgo in hallazgos)


def test_orquesta_no_observa_estados_contables_que_concilian():
    datos = [
        {"archivo_origen": "estado_situacion_patrimonial.xlsx", "concepto": "Caja y bancos", "saldo": 1000},
        {"archivo_origen": "estado_situacion_patrimonial.xlsx", "concepto": "Resultado del ejercicio", "saldo": 300},
        {"archivo_origen": "flujo_de_caja.xlsx", "concepto": "Saldo final de efectivo", "saldo": 1000},
        {"archivo_origen": "estado_de_resultados.xlsx", "concepto": "Resultado neto del ejercicio", "saldo": 300},
    ]

    assert orquesta.analizar(datos, []) == []


def test_orquesta_no_compara_totales_de_preinformes_no_comparables():
    """Regresión del reporte 114: variar la cantidad de filas entre archivos
    no convierte una columna constante en una variación histórica."""
    actual = [
        {"periodo": "2026-01", "credito_vigente": 1000, "devengado": 300, "pagado": 260},
        {"periodo": "2026-02", "credito_vigente": 1000, "devengado": 450, "pagado": 410},
        {"periodo": "2026-03", "credito_vigente": 1000, "devengado": 520, "pagado": 610},
        {"periodo": "2026-04", "credito_vigente": 1000, "devengado": 700, "pagado": 670},
    ]
    historicos = [
        [{"periodo": f"2025-{m:02d}", "credito_vigente": 1000, "devengado": 100 * m, "pagado": 90 * m} for m in range(1, n)]
        for n in (4, 5, 6, 7)
    ]
    assert orquesta.analizar(actual, historicos) == []
