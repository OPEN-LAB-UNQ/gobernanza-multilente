"""Automatic feedback remains private and separate from teacher decisions."""
import datetime as dt
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user
from database import get_db
from routers import proyectos_ia


def test_feedback_keeps_teacher_and_student_state_separate():
    p = models.ProyectoIA(id=1, usuario_id=1, titulo='Prueba', estado='entregado',
                          entrega_final='Propuesta propia', retro_docente='Devolución humana')
    p.mensajes = [models.MensajeProyectoIA(id=7, proyecto_id=1, remitente='predevolucion_ia',
                                         contenido='Pre-devolución automática', creado_en=dt.datetime(2026, 9, 19))]
    before = proyectos_ia._texto_diagnostico(p)
    data = proyectos_ia._proyecto_out(p)
    assert data['predevolucion_ia']['contenido'] == 'Pre-devolución automática'
    assert data['predevolucion_ia']['canal'] == 'predevolucion'
    assert data['retro_docente'] == 'Devolución humana'
    assert data['estado'] == 'entregado'
    assert data['entrega_final'] == 'Propuesta propia'
    assert data['conteos']['respuestas_docente'] == 0
    assert proyectos_ia._texto_diagnostico(p) == before
    assert 'Pre-devolución automática' not in before
    assert proyectos_ia._proyecto_out(p, incluir_mensajes=False)['predevolucion_ia']
    p.mensajes = []
    assert proyectos_ia._proyecto_out(p)['predevolucion_ia'] is None


def test_private_feedback_is_owner_or_admin_only():
    @compiles(JSONB, 'sqlite')
    def json_sqlite(element, compiler, **kw):
        return 'JSON'

    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    try:
        models.Base.metadata.create_all(engine)
        with Session(engine) as db:
            for i in (1, 2, 3):
                db.add(models.Usuario(id=i, email=f'pre{i}@example.test', nombre=f'Persona {i}',
                                      password_hash='unused', rol='admin' if i == 3 else 'analista'))
                db.add(models.ProyectoIA(id=i, usuario_id=i, titulo=f'Caso {i}'))
            db.add(models.MensajeProyectoIA(proyecto_id=1, remitente='predevolucion_ia', contenido='Privado del caso uno'))
            db.commit()
            app = FastAPI()
            app.include_router(proyectos_ia.router)
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
            with TestClient(app) as client:
                assert client.get('/proyectos-ia/mio').json()['predevolucion_ia']['contenido'] == 'Privado del caso uno'
                app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 2)
                assert client.get('/proyectos-ia/mio').json()['predevolucion_ia'] is None
                assert client.get('/proyectos-ia/1').status_code == 403
                assert 'Privado del caso uno' not in client.get('/proyectos-ia/casos').text
                app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 3)
                assert client.get('/proyectos-ia/1').json()['predevolucion_ia']['contenido'] == 'Privado del caso uno'
                del app.dependency_overrides[get_current_user]
                assert client.get('/proyectos-ia/mio').status_code == 401
    finally:
        engine.dispose()
        deregister(JSONB)


def test_ui_escapes_and_separates_automatic_feedback():
    root = Path(__file__).resolve().parents[1]
    js = (root / 'static/app.js').read_text(encoding='utf-8')
    html = (root / 'static/index.html').read_text(encoding='utf-8')
    assert 'escapeHtml(pre.contenido)' in js
    assert 'Pre-devolución automática · IA' in js
    assert 'id="proyecto-predevolucion-ia"' in html
    assert 'id="proyecto-retro"' in html
