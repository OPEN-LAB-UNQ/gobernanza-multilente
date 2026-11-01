"""Tests de la lente Radiologo."""
from __future__ import annotations

from services.lentes import radiologo


def _banco_historico_presupuestario(valor_ultimo_periodo=1_000_000.0):
    periodos = ["2025-08", "2025-09", "2025-10", "2025-11", "2025-12"]
    banco = []
    for p in periodos:
        banco.append({
            "periodo": p,
            "datos": [{"periodo": p, "credito_devengado": 1_000_000.0 + (hash(p) % 5) * 1000}],
        })
    return banco

def test_radiologo_detecta_caso_fuera_de_rango_vs_banco_historico():
    banco = _banco_historico_presupuestario()
    datos_actuales = [{"periodo": "2026-01", "credito_devengado": 9_000_000.0}]
    hallazgos = radiologo.analizar("presupuestario", "2026-01", datos_actuales, banco)
    assert hallazgos
    assert hallazgos[0]["modo"] == "semejanza"
    assert hallazgos[0]["evidencia"]["fuente_comparacion"] == "banco_historico"


def test_radiologo_sin_banco_dominio_no_soportado_no_hace_nada():
    banco = _banco_historico_presupuestario()
    datos_actuales = [{"periodo": "2026-01", "credito_devengado": 9_000_000.0}]
    assert radiologo.analizar("educativo", "2026-01", datos_actuales, banco) == []


def test_radiologo_no_reemplaza_preinformes_con_historial_del_mismo_archivo():
    datos = [
        {"periodo": f"2026-{mes:02d}", "credito_devengado": 1_000_000.0 if mes < 6 else 9_000_000.0}
        for mes in range(1, 7)
    ]
    assert radiologo.analizar("presupuestario", "2026-06", datos, []) == []


def test_radiologo_expone_periodo_comparado_y_periodos_de_referencia():
    """Regresion: el hallazgo debe decir de que periodo habla, no solo el
    desvio -- antes la triangulacion rellenaba el dato faltante y podia
    atribuir el desvio a un periodo equivocado."""
    banco = [
        {"periodo": p, "datos": [{"periodo": p, "credito_devengado": 1_000_000.0 + i * 1000}]}
        for i, p in enumerate(["2025-08", "2025-09", "2025-10", "2025-11", "2025-12"])
    ]
    datos_actuales = [{"periodo": "2026-12", "credito_devengado": 9_000_000.0}]
    hallazgos = radiologo.analizar("presupuestario", "2026-12", datos_actuales, banco)
    assert hallazgos
    h = hallazgos[0]
    assert "2026-12" in h["descripcion"]
    assert h["evidencia"]["periodo_comparado"] == "2026-12"
    assert h["evidencia"]["periodos_de_referencia"] == ["2025-08", "2025-09", "2025-10", "2025-11", "2025-12"]
