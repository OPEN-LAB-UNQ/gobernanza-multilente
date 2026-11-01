"""Borrar un informe mientras se analiza no detiene la cola.

Caso real (08/10/2026): se borró el informe 310 durante su análisis; el manejo del error leía
el trabajo ya borrado (ObjectDeletedError), el hilo del worker murió y el informe 312 quedó
«en cola» hasta reiniciar el servicio.
"""
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from services import jobs


def _base(monkeypatch, request):
    # Registro local del tipo JSONB en SQLite: otras pruebas lo retiran al terminar.
    @compiles(JSONB, "sqlite")
    def _json_sqlite(element, compiler, **kw):
        return "JSON"

    request.addfinalizer(lambda: deregister(JSONB))
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    monkeypatch.setattr(jobs, "enviar_analisis_finalizado", lambda *a, **k: ("sin_destinatario", None))
    with factory() as db:
        db.add(models.Usuario(id=1, email="a@test", nombre="A", password_hash="x", rol="analista"))
        db.add(models.Area(id=1, nombre="Área de prueba", codigo="prueba"))
        for i in (1, 2):
            db.add(models.Informe(id=i, usuario_id=1, area_id=1, periodo="2026-10", dominio="general",
                                  modo="intraarea", datos=[{"x": 1}], saneamiento={}))
            db.add(models.AnalysisJob(id=i, informe_id=i, usuario_id=1, estado="pendiente", modelos=[]))
        db.commit()
    return factory


def test_borrar_el_informe_durante_el_analisis_no_detiene_la_cola(monkeypatch, request):
    factory = _base(monkeypatch, request)

    def analisis_que_borra(db, informe, modelos):
        if informe.id == 1:
            with factory() as otra:  # otra sesión borra el informe y su trabajo, como el botón «Borrar»
                otra.query(models.AnalysisJob).filter_by(informe_id=1).delete()
                otra.query(models.Informe).filter_by(id=1).delete()
                otra.commit()
            db.expire_all()
            raise RuntimeError("el informe desapareció")
        yield {"tipo": "final", "resultado": None}

    monkeypatch.setattr(jobs, "ejecutar_analisis_stream", analisis_que_borra)
    assert jobs._process_one() is True          # el borrado no levanta una excepción
    assert jobs._process_one() is True          # el siguiente informe se procesa
    with factory() as db:
        assert db.get(models.AnalysisJob, 2).estado == "error"  # terminó (sin resultado), no quedó en cola


def test_el_worker_sigue_despues_de_una_falla_inesperada(monkeypatch):
    llamadas = []

    def falla_y_corta():
        llamadas.append(1)
        if len(llamadas) == 1:
            raise RuntimeError("falla inesperada")
        monkeypatch.setattr(jobs, "_stop", True)
        return True

    monkeypatch.setattr(jobs, "_stop", False)
    monkeypatch.setattr(jobs, "_process_one", falla_y_corta)
    jobs._worker_loop()
    assert len(llamadas) == 2
