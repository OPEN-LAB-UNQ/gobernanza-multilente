"""Tests de la lente Ajedrecista."""
from __future__ import annotations

from conftest import _presupuesto_largo

from services import guardrails
from services.lentes import ajedrecista


def test_ajedrecista_detecta_devengado_supera_vigente():
    datos = _presupuesto_largo(salto_area="Infraestructura", salto_periodo="2026-05", salto_factor=2.6)
    hallazgos = ajedrecista.analizar(datos, None)
    modos = {h["modo"] for h in hallazgos}
    assert "restriccion_formal_a_validar" in modos
    h = next(h for h in hallazgos if h["modo"] == "restriccion_formal_a_validar")
    assert h["evidencia"]["regla"] == "devengado_supera_vigente"
    assert h["evidencia"]["requiere_regla_explicita"] is True


def test_ajedrecista_reporta_evidencia_numerica_y_fila_de_planilla():
    datos = [
        {"periodo": "2026-01", "credito_vigente": 1000, "devengado": 300, "pagado": 260},
        {"periodo": "2026-02", "credito_vigente": 1000, "devengado": 450, "pagado": 410},
        {"periodo": "2026-03", "credito_vigente": 1000, "devengado": 520, "pagado": 610},
        {"periodo": "2026-04", "credito_vigente": 1000, "devengado": 700, "pagado": 670},
    ]
    h = next(x for x in ajedrecista.analizar(datos, None) if x["evidencia"].get("regla") == "pagado_supera_devengado")
    muestra = h["evidencia"]["muestras_violacion"][0]
    assert muestra["fila_fuente_con_encabezado"] == 4
    assert muestra["diferencia_absoluta"] == 90
    assert muestra["exceso_sobre_menor_pct"] == 17.31
    assert h["severidad"] == "alta"


def test_ajedrecista_imposibilidad_valor_negativo():
    datos = [
        {"periodo": "2026-01", "credito_vigente": 100, "monto_ejecutado": 50},
        {"periodo": "2026-02", "credito_vigente": 100, "monto_ejecutado": -5},
        {"periodo": "2026-03", "credito_vigente": 100, "monto_ejecutado": 48},
    ]
    hallazgos = ajedrecista.analizar(datos, None)
    modos = {h["modo"] for h in hallazgos}
    assert "imposibilidad" in modos
    h = next(h for h in hallazgos if h["evidencia"].get("regla") == "valor_negativo_en_magnitud_no_negativa")
    assert h["severidad"] == "alta"


def test_ajedrecista_acumulado_retrocede():
    datos = [
        {"periodo": "2026-01", "gasto_acumulado": 100},
        {"periodo": "2026-02", "gasto_acumulado": 150},
        {"periodo": "2026-03", "gasto_acumulado": 90},
        {"periodo": "2026-04", "gasto_acumulado": 220},
    ]
    hallazgos = ajedrecista.analizar(datos, None)
    reglas = {h["evidencia"].get("regla") for h in hallazgos}
    assert "serie_acumulada_retrocede" in reglas


def test_comparacion_con_preinforme_prioriza_sin_regla_dura():
    """La priorización histórica se conserva como insumo de Radiólogo."""
    anterior = [{"id": i, "periodo": "2026-01", "monto_ejecutado": v} for i, v in enumerate((100.0, 102.0, 98.0, 101.0, 99.0))]
    actual = [
        {"id": 0, "periodo": "2026-02", "monto_ejecutado": 101.0},
        {"id": 1, "periodo": "2026-02", "monto_ejecutado": 99.0},
        {"id": 2, "periodo": "2026-02", "monto_ejecutado": 500.0},
        {"id": 3, "periodo": "2026-02", "monto_ejecutado": 100.0},
        {"id": 4, "periodo": "2026-02", "monto_ejecutado": 98.0},
    ]
    hallazgos = ajedrecista.priorizacion(actual, anterior)
    priorizados = [h for h in hallazgos if h["modo"] == "priorizacion"]
    assert priorizados
    assert priorizados[0]["evidencia"]["fila"] == 2
    assert "regla" not in priorizados[0]["evidencia"]











def test_ajedrecista_priorizacion_sin_datos_periodo_anterior_no_hace_nada():
    actual = [{"periodo": "2026-02", "monto_ejecutado": v} for v in (100.0, 500.0, 99.0)]
    assert ajedrecista.priorizacion(actual, None) == []


def test_ajedrecista_total_roto_estructurado():
    datos = [
        {"concepto": "uno", "a": 10, "b": 20, "total": 30},
        {"concepto": "dos", "a": 5, "b": 5, "total": 10},
        {"concepto": "tres", "a": 4, "b": 6, "total": 10},
        {"concepto": "cuatro", "a": 2, "b": 3, "total": 99},
    ]
    crudos = [{**h, "lente": "ajedrecista"} for h in ajedrecista.analizar(datos, None)]
    normalizados = guardrails.normalizar_hallazgos(crudos)
    assert normalizados
    assert normalizados[0]["tipo_evidencia"] == "REGLA_FORMAL_O_ARITMETICA"
    assert normalizados[0]["alcance"] == "agregado"


def test_ajedrecista_detecta_cierre_operativo_de_consultas():
    datos = [
        {"periodo": "2026-01", "consultas": 500, "resueltas": 455, "pendientes": 45},
        {"periodo": "2026-02", "consultas": 530, "resueltas": 486, "pendientes": 44},
        {"periodo": "2026-03", "consultas": 545, "resueltas": 502, "pendientes": 43},
        {"periodo": "2026-04", "consultas": 560, "resueltas": 525, "pendientes": 42},
    ]
    hallazgo = next(
        h for h in ajedrecista.analizar(datos, None)
        if h["evidencia"].get("regla") == "resueltas_mas_pendientes_no_cierran_consultas"
    )
    assert hallazgo["evidencia"]["filas_en_violacion"] == 1
    assert hallazgo["evidencia"]["muestra"]["declarado"] == 560
    assert hallazgo["evidencia"]["muestra"]["calculado"] == 567
    assert hallazgo["evidencia"]["columnas"] == ["consultas", "resueltas", "pendientes"]
    assert hallazgo["evidencia"]["muestra"]["fila_fuente_con_encabezado"] == 5
    assert hallazgo["evidencia"]["muestra"]["diferencia_absoluta"] == 7
    assert hallazgo["evidencia"]["muestra"]["diferencia_pct_consultas"] == 1.25
    assert "2026-04" in hallazgo["pregunta_institucional"]


def test_ajedrecista_verifica_los_tres_eslabones_presupuestarios():
    datos = [
        {"periodo": "2026-01", "credito_vigente": 800, "devengado": 220, "pagado": 210},
        {"periodo": "2026-02", "credito_vigente": 800, "devengado": 430, "pagado": 390},
        {"periodo": "2026-03", "credito_vigente": 800, "devengado": 860, "pagado": 790},
        {"periodo": "2026-04", "credito_vigente": 800, "devengado": 900, "pagado": 820},
    ]
    hallazgos = ajedrecista.analizar(datos, None)
    por_regla = {h["evidencia"].get("regla"): h for h in hallazgos}
    assert "devengado_supera_vigente" in por_regla
    assert "pagado_supera_vigente" in por_regla
    assert "pagado_supera_devengado" not in por_regla
    assert por_regla["devengado_supera_vigente"]["severidad"] == "alta"
    assert por_regla["pagado_supera_vigente"]["evidencia"]["muestras_violacion"][0]["diferencia_absoluta"] == 20


def test_ajedrecista_no_marca_consultas_que_cierran():
    datos = [
        {"periodo": "2026-01", "consultas": 500, "resueltas": 455, "pendientes": 45},
        {"periodo": "2026-02", "consultas": 530, "resueltas": 486, "pendientes": 44},
        {"periodo": "2026-03", "consultas": 545, "resueltas": 502, "pendientes": 43},
        {"periodo": "2026-04", "consultas": 560, "resueltas": 518, "pendientes": 42},
    ]
    hallazgos = ajedrecista.analizar(datos, None)
    assert not [
        h for h in hallazgos
        if h["evidencia"].get("regla") == "resueltas_mas_pendientes_no_cierran_consultas"
    ]




def test_ajedrecista_no_trata_variacion_negativa_como_imposibilidad():
    datos = [
        {"rubro": "A", "Total Variación %": -12.5},
        {"rubro": "B", "Total Variación %": 4.2},
        {"rubro": "C", "Total Variación %": -1.1},
    ]
    hallazgos = ajedrecista.analizar(datos, None)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "valor_negativo_en_magnitud_no_negativa"]






def test_ajedrecista_priorizacion_no_compara_historial_sin_clave_comun():
    anterior = [{"Período": "Acumulado hasta julio", "Exportaciones": 1000}]
    actual = [{"rubro": "MOA", "Exportaciones": 5000}]
    assert ajedrecista.priorizacion(actual, anterior) == []



def test_ajedrecista_priorizacion_no_repite_senal_si_fila_no_cambio():
    anterior = [
        {"Período": "Enero", "Exportaciones": 100, "Importaciones": 80},
        {"Período": "Febrero", "Exportaciones": 300, "Importaciones": 220},
    ]
    actual = [dict(fila) for fila in anterior]
    assert ajedrecista.priorizacion(actual, anterior) == []



def test_ajedrecista_priorizacion_no_compara_informes_con_estructura_distinta():
    anterior = [
        {"columna_1": "Paraguay", "2025*": 10, "2026*": 20, "archivo_origen": "combo.pdf"},
        {"columna_1": "Oceanía", "2025*": 5, "2026*": 8, "archivo_origen": "combo.pdf"},
        {"columna_1": "Medio Oriente", "2025*": 7, "2026*": 9, "archivo_origen": "combo.pdf"},
    ]
    actual = [
        {"columna_1": "Paraguay", "2025*": 1000, "2026*": 1200},
        {"columna_1": "Oceanía", "2025*": 500, "2026*": 520},
        {"columna_1": "Medio Oriente", "2025*": 700, "2026*": 740},
    ]
    assert ajedrecista.priorizacion(actual, anterior) == []
