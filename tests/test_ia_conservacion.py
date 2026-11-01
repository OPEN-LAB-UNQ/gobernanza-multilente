"""7. Conservación: los hallazgos del motor se guardan en una transacción propia
antes de la IA; la etapa de IA es best-effort con su propio estado de error."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from services import analisis
from tests.conftest import _presupuesto_largo
from tests.flujo_confirmado import preparar_informe_fixture


@pytest.fixture
def db():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):  # noqa: ANN001
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as sesion:
        sesion.add(models.Usuario(id=1, email="admin@test", nombre="Admin", password_hash="x", rol="admin"))
        sesion.add(models.Area(id=1, nombre="Area", codigo="A"))
        sesion.commit()
        yield sesion
    engine.dispose()
    deregister(JSONB)


def _informe(db):
    i = models.Informe(area_id=1, usuario_id=1, periodo="2026-06", dominio="presupuesto",
                       datos=_presupuesto_largo(salto_area="Salud", salto_periodo="2026-03"), saneamiento={})
    preparar_informe_fixture(i)
    db.add(i)
    db.commit()
    return i


def _ia_que_falla(*args, **kwargs):
    raise RuntimeError("proveedor caído a mitad de la etapa")
    yield  # pragma: no cover


def test_falla_de_la_ia_no_borra_los_hallazgos_del_motor(db, monkeypatch):
    i = _informe(db)
    monkeypatch.setattr(analisis.triangulacion_svc, "interpretar_con_modelos_stream", _ia_que_falla)
    resultado = analisis.ejecutar_analisis(db, i, ["gpt"])
    assert resultado.hallazgos
    etapa = resultado.devolucion.cobertura["interpretacion_ia"]["etapa"]
    assert etapa["estado"] == "error" and "RuntimeError" in etapa["error"]
    assert "La etapa de interpretación con IA no se completó" in resultado.devolucion.mensaje
    assert db.query(models.Hallazgo).filter_by(informe_id=i.id).count() == len(resultado.hallazgos)


def test_hallazgos_sobreviven_a_un_rollback_posterior_y_el_reintento_no_duplica(db, monkeypatch):
    i = _informe(db)
    monkeypatch.setattr(analisis.triangulacion_svc, "interpretar_con_modelos_stream", lambda *a, **k: iter(()))

    def devolucion_rota(*a, **k):
        raise RuntimeError("falla posterior a la IA")

    monkeypatch.setattr(analisis.devolucion_svc, "armar_mensaje", devolucion_rota)
    with pytest.raises(RuntimeError):
        analisis.ejecutar_analisis(db, i, ["gpt"])
    db.rollback()  # lo que hace jobs._process_one ante una excepción
    guardados = db.query(models.Hallazgo).filter_by(informe_id=i.id).count()
    assert guardados > 0
    monkeypatch.undo()
    monkeypatch.setattr(analisis.triangulacion_svc, "interpretar_con_modelos_stream", lambda *a, **k: iter(()))
    db.refresh(i)
    resultado = analisis.ejecutar_analisis(db, i, ["gpt"])
    assert db.query(models.Hallazgo).filter_by(informe_id=i.id).count() == len(resultado.hallazgos) == guardados
