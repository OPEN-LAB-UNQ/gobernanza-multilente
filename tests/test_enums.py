"""Tests del vocabulario cerrado (Lente/Severidad) y su validacion en guardrails/schemas."""
from __future__ import annotations

import warnings

import pytest

import schemas
from enums import Lente, Severidad
from services import guardrails


def test_lentes_enum_coincide_con_guardrails():
    assert set(guardrails.LENTES) == {lente.value for lente in Lente}


def test_lente_tiene_exactamente_siete_miembros():
    """Guardia contra un descuido: agregar una octava lente (p.ej. la capa
    exploratoria) tiene que ser una decision deliberada, nunca un efecto
    colateral de tocar otro archivo."""
    assert len(list(Lente)) == 7


def test_normalizar_hallazgo_avisa_por_lente_desconocida_tipo_typo():
    with pytest.warns(UserWarning, match="lente desconocida"):
        guardrails.normalizar_hallazgo({
            "lente": "matemático",  # typo real: con tilde, no matchea "matematico"
            "descripcion": "x",
            "severidad": "media",
            "evidencia": {},
        })


def test_normalizar_hallazgo_avisa_por_severidad_desconocida():
    with pytest.warns(UserWarning, match="severidad desconocida"):
        h = guardrails.normalizar_hallazgo({
            "lente": "ajedrecista",
            "descripcion": "x",
            "severidad": "critica",  # no es un valor valido
            "evidencia": {},
        })
    assert h["severidad"] == "media"  # sigue cayendo al default, no rompe el flujo


def test_normalizar_hallazgo_lente_y_severidad_validas_no_avisan():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        guardrails.normalizar_hallazgo({
            "lente": Lente.RIZOMA.value,
            "descripcion": "x",
            "severidad": Severidad.BAJA.value,
            "evidencia": {},
        })


def test_hallazgo_out_rechaza_lente_invalida():
    with pytest.raises(Exception):
        schemas.HallazgoOut(
            id=1, lente="lente_inventada", descripcion="x", severidad="media", evidencia={},
        )


def test_hallazgo_out_rechaza_severidad_invalida():
    with pytest.raises(Exception):
        schemas.HallazgoOut(
            id=1, lente="rizoma", descripcion="x", severidad="urgente", evidencia={},
        )
