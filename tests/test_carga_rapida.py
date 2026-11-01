"""Tests de inferencia de dominio en carga rapida."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from routers.carga_rapida import _inferir_dominio, _limpiar_orientacion_analisis


def test_inferir_dominio_explicito_gana_sobre_inferencia():
    """Un dominio elegido explicitamente desde la UI (incluido 'general' a
    proposito) no debe ser pisado por la inferencia automatica, aunque las
    columnas parezcan presupuestarias."""
    datos = [{"credito_vigente": 100, "devengado": 90, "pagado": 80}]
    assert _inferir_dominio(datos, "general") == "general"
    assert _inferir_dominio(datos, "presupuestario") == "presupuestario"


def test_inferir_dominio_auto_sigue_infiriendo_como_antes():
    datos_presupuestarios = [{"credito_vigente": 100, "devengado": 90}]
    datos_genericos = [{"programa": "A", "descripcion": "algo"}]
    assert _inferir_dominio(datos_presupuestarios, "auto") == "presupuestario"
    assert _inferir_dominio(datos_genericos, "auto") == "general"
    assert _inferir_dominio([], "auto") == "general"


def test_inferir_dominio_servicios_y_atencion():
    datos = [{"periodo": "2026-01", "consultas": 500, "resueltas": 455, "pendientes": 45, "satisfaccion_pct": 82}]
    assert _inferir_dominio(datos, "auto") == "servicios_atencion"


def test_orientacion_opcional_se_normaliza_sin_alterar_el_sentido():
    assert _limpiar_orientacion_analisis("  Quiero revisar\n diferencias entre áreas. ") == (
        "Quiero revisar diferencias entre áreas."
    )
    assert _limpiar_orientacion_analisis("   ") is None


def test_orientacion_rechaza_textos_excesivos():
    with pytest.raises(HTTPException) as exc:
        _limpiar_orientacion_analisis("x" * 1501)
    assert exc.value.status_code == 422
