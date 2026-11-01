"""Tope diario de uso de IA por usuario."""
import datetime as dt

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from services import cuota_ia


@pytest.fixture
def db():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as sesion:
        sesion.add_all([
            models.Usuario(id=1, email="admin@t", nombre="A", password_hash="x", rol="admin"),
            models.Usuario(id=2, email="alumno@t", nombre="B", password_hash="x", rol="analista"),
            models.Area(id=1, nombre="Area", codigo="A"),
        ])
        sesion.flush()
        sesion.add(models.Informe(id=1, area_id=1, usuario_id=2, periodo="2026", dominio="general", datos=[], saneamiento={}))
        sesion.add(models.ProyectoIA(id=1, usuario_id=2, titulo="P", estado="en_proceso"))
        sesion.commit()
        yield sesion
    engine.dispose()
    deregister(JSONB)


def _jobs(db, usuario_id, n, hace_horas=1):
    cuando = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(hours=hace_horas)
    for _ in range(n):
        db.add(models.AnalysisJob(informe_id=1, usuario_id=usuario_id, estado="finalizado", creado_en=cuando,
                                  iniciado_en=cuando))
    db.commit()


def test_el_tope_de_analisis_corta_en_el_limite(db, monkeypatch):
    monkeypatch.setattr(cuota_ia.settings, "limite_analisis_ia_dia", 3)
    alumno = db.get(models.Usuario, 2)
    _jobs(db, 2, 2)
    cuota_ia.verificar_analisis(db, alumno)
    _jobs(db, 2, 1)
    with pytest.raises(HTTPException) as err:
        cuota_ia.verificar_analisis(db, alumno)
    assert err.value.status_code == 429 and "3 análisis" in err.value.detail


def test_lo_de_hace_mas_de_un_dia_no_cuenta(db, monkeypatch):
    monkeypatch.setattr(cuota_ia.settings, "limite_analisis_ia_dia", 3)
    _jobs(db, 2, 5, hace_horas=30)
    cuota_ia.verificar_analisis(db, db.get(models.Usuario, 2))


def test_la_administracion_queda_exenta_y_cero_desactiva(db, monkeypatch):
    monkeypatch.setattr(cuota_ia.settings, "limite_analisis_ia_dia", 1)
    _jobs(db, 1, 5)
    cuota_ia.verificar_analisis(db, db.get(models.Usuario, 1))
    _jobs(db, 2, 5)
    monkeypatch.setattr(cuota_ia.settings, "limite_analisis_ia_dia", 0)
    cuota_ia.verificar_analisis(db, db.get(models.Usuario, 2))


def test_tope_de_mensajes_de_la_incubadora(db, monkeypatch):
    monkeypatch.setattr(cuota_ia.settings, "limite_mensajes_incubadora_dia", 2)
    for remitente in ("participante", "ia", "participante"):
        db.add(models.MensajeProyectoIA(proyecto_id=1, usuario_id=2, remitente=remitente, contenido="x"))
    db.commit()
    with pytest.raises(HTTPException) as err:
        cuota_ia.verificar_incubadora(db, db.get(models.Usuario, 2))
    assert err.value.status_code == 429


def test_fallidos_y_reaperturas_no_gastan_cupo_pero_los_directos_si(db, monkeypatch):
    monkeypatch.setattr(cuota_ia.settings, "limite_analisis_ia_dia", 2)
    alumno = db.get(models.Usuario, 2)
    ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    db.add_all([
        models.AnalysisJob(informe_id=1, usuario_id=2, estado="error", creado_en=ahora, iniciado_en=ahora),
        models.AnalysisJob(informe_id=1, usuario_id=2, estado="finalizado", creado_en=ahora),  # reabre una devolución
        models.AnalysisJob(informe_id=1, usuario_id=2, estado="finalizado", creado_en=ahora, iniciado_en=ahora),
    ])
    db.commit()
    cuota_ia.verificar_analisis(db, alumno)
    db.add(models.ActivityEvent(usuario_id=2, modulo="multilente", accion="analisis_stream_solicitado", creado_en=ahora))
    db.commit()
    with pytest.raises(HTTPException):
        cuota_ia.verificar_analisis(db, alumno)


def test_la_exploracion_cuenta_cada_pedido_de_quien_explora(db, monkeypatch):
    monkeypatch.setattr(cuota_ia.settings, "limite_analisis_ia_dia", 2)
    admin_informe = db.get(models.Usuario, 2)
    ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for _ in range(2):  # mismo informe dos veces: son dos llamadas a la IA
        db.add(models.ActivityEvent(usuario_id=2, informe_id=1, modulo="multilente", accion="exploracion_generada", creado_en=ahora))
    db.commit()
    with pytest.raises(HTTPException):
        cuota_ia.verificar_exploracion(db, admin_informe)


def test_reabrir_un_informe_analizado_no_pide_cupo(db, monkeypatch):
    monkeypatch.setattr(cuota_ia.settings, "limite_analisis_ia_dia", 1)
    alumno = db.get(models.Usuario, 2)
    _jobs(db, 2, 3)
    import types
    informe = types.SimpleNamespace(id=1, devolucion=object())
    cuota_ia.verificar_encolado(db, alumno, informe)
    informe.devolucion = None
    with pytest.raises(HTTPException):
        cuota_ia.verificar_encolado(db, alumno, informe)
