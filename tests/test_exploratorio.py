"""Tests de services/exploratorio.py: calculo determinista, parseo y
persistencia. No pegan a la red -- fuerzan la rama sin API key donde
corresponde y verifican el calculo puro de correlaciones por separado."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from enums import Lente
from services import exploratorio
from services.lens_matrix import LENS_MATRIX


def test_tipo_pista_tiene_solo_las_dos_pistas_del_diseno():
    assert {p.value for p in exploratorio.TipoPista} == {
        "preguntas_no_formuladas",
        "correlaciones_no_declaradas",
    }


def test_estado_hipotesis_es_el_unico_valor_posible():
    assert exploratorio.ESTADO_HIPOTESIS_NO_VALIDADA == "HIPOTESIS_NO_VALIDADA"


def test_preguntas_canonicas_cubre_las_siete_lentes():
    preguntas = exploratorio.preguntas_canonicas_de_las_lentes()
    esperadas = sum(1 + len(lente["preguntas"]) for lente in LENS_MATRIX)
    assert len(preguntas) == esperadas
    assert len(LENS_MATRIX) == len(Lente)


def test_partir_preguntas_limita_y_limpia_numeracion():
    texto = "1. Primera pregunta?\n- Segunda pregunta?\n\n* Tercera?\nCuarta?\nQuinta?\nSexta (de mas)?"
    preguntas = exploratorio._partir_preguntas(texto)
    assert preguntas == ["Primera pregunta?", "Segunda pregunta?", "Tercera?", "Cuarta?", "Quinta?"]


def test_generar_pista_a_sin_api_key_no_lanza_y_devuelve_error(monkeypatch):
    monkeypatch.setattr(exploratorio.settings, "openai_api_key", None)
    informe = SimpleNamespace(periodo="2026-09", dominio="general", datos=[{"a": 1}])
    hipotesis, error = exploratorio.generar_pista_a(informe)
    assert hipotesis == []
    assert error and "OPENAI_API_KEY" in error


def test_calcular_correlaciones_detecta_relacion_lineal_fuerte():
    datos = [
        {"a": 1, "b": 10, "concepto": "x"},
        {"a": 2, "b": 20, "concepto": "y"},
        {"a": 3, "b": 29, "concepto": "z"},
        {"a": 4, "b": 41, "concepto": "w"},
        {"a": 5, "b": 48, "concepto": "v"},
    ]
    informe = SimpleNamespace(datos=datos)
    pares = exploratorio.calcular_correlaciones(informe)
    assert pares
    assert {pares[0]["columna_a"], pares[0]["columna_b"]} == {"a", "b"}
    assert pares[0]["r"] > 0.9


def test_calcular_correlaciones_es_determinista():
    datos = [{"a": i, "b": i * 3 + 1, "c": (i * 7) % 5} for i in range(1, 8)]
    informe = SimpleNamespace(datos=datos)
    assert exploratorio.calcular_correlaciones(informe) == exploratorio.calcular_correlaciones(informe)


def test_calcular_correlaciones_excluye_pares_casi_identicos():
    # r cercano a 1.0 (p.ej. la misma magnitud en dos unidades) se excluye:
    # casi seguro es la misma columna duplicada, no un hallazgo interesante.
    datos = [{"a": i, "b": i * 2} for i in range(1, 6)]
    informe = SimpleNamespace(datos=datos)
    assert exploratorio.calcular_correlaciones(informe) == []


def test_generar_pista_b_sin_api_key_usa_plantilla_determinista(monkeypatch):
    monkeypatch.setattr(exploratorio.settings, "openai_api_key", None)
    datos = [
        {"a": 1, "b": 10}, {"a": 2, "b": 21}, {"a": 3, "b": 29},
        {"a": 4, "b": 39}, {"a": 5, "b": 52},
    ]
    informe = SimpleNamespace(datos=datos)
    hipotesis = exploratorio.generar_pista_b(informe)
    assert hipotesis
    for h in hipotesis:
        assert h["tipo_pista"] == "correlaciones_no_declaradas"
        assert h["modelo"] == "plantilla_determinista"
        assert "causal" in h["texto_hipotesis"].lower()


def test_guardar_hipotesis_fuerza_el_estado_unico_pase_lo_que_pase():
    @compiles(JSONB, "sqlite")
    def _json_sqlite(element, compiler, **kw):  # noqa: ANN001
        return "JSON"

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine, tables=[models.Area.__table__, models.Informe.__table__, models.HipotesisExploratoria.__table__])
    try:
        with Session(engine) as db:
            area = models.Area(id=1, nombre="Prueba", codigo="PRUEBA")
            db.add(area)
            db.flush()
            informe = models.Informe(
                id=1, area_id=area.id, periodo="2026-09", dominio="general",
                modo="intraarea", datos=[], saneamiento={},
            )
            db.add(informe)
            db.flush()

            guardadas = exploratorio.guardar_hipotesis(db, informe.id, [
                {"tipo_pista": "preguntas_no_formuladas", "texto_hipotesis": "texto", "modelo": "m", "version_modelo": "v1"},
            ])
            assert len(guardadas) == 1
            assert guardadas[0].estado == "HIPOTESIS_NO_VALIDADA"

            listadas = exploratorio.listar_hipotesis(db, informe.id)
            assert len(listadas) == 1
            assert listadas[0].texto_hipotesis == "texto"
    finally:
        engine.dispose()
        deregister(JSONB)


def test_guardar_hipotesis_estado_distinto_viola_la_restriccion_de_base():
    @compiles(JSONB, "sqlite")
    def _json_sqlite(element, compiler, **kw):  # noqa: ANN001
        return "JSON"

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine, tables=[models.Area.__table__, models.Informe.__table__, models.HipotesisExploratoria.__table__])
    try:
        with Session(engine) as db:
            area = models.Area(id=1, nombre="Prueba", codigo="PRUEBA")
            db.add(area)
            db.flush()
            informe = models.Informe(
                id=1, area_id=area.id, periodo="2026-09", dominio="general",
                modo="intraarea", datos=[], saneamiento={},
            )
            db.add(informe)
            db.flush()
            db.add(models.HipotesisExploratoria(
                informe_id=informe.id, tipo_pista="preguntas_no_formuladas",
                texto_hipotesis="x", modelo="m", estado="CONFIRMADA",
            ))
            with pytest.raises(Exception):
                db.commit()
    finally:
        engine.dispose()
        deregister(JSONB)
