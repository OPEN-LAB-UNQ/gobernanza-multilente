"""Aviso por correo al docente cuando un participante escribe en el espacio docente de la Incubadora."""
import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from config import settings
from core.auth import get_current_user
from database import get_db
from routers import proyectos_ia
from services import aviso_docente, notificaciones

TEXTO_CONSULTA = "Profe, ¿puedo usar los legajos 4521 del área de compras para entrenar el clasificador?"
TITULO = "Clasificador de expedientes de compras"


class _SMTPFalso:
    enviados: list = []
    falla = False

    def __init__(self, host, port, timeout=None):
        if _SMTPFalso.falla:
            raise OSError("SMTP caído")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        _SMTPFalso.enviados.append(msg)


@pytest.fixture
def entorno(monkeypatch):
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    _SMTPFalso.enviados = []
    _SMTPFalso.falla = False
    monkeypatch.setattr(notificaciones.smtplib, "SMTP", _SMTPFalso)
    monkeypatch.setattr(notificaciones.smtplib, "SMTP_SSL", _SMTPFalso)
    monkeypatch.setattr(settings, "smtp_host", "smtp.prueba.test")
    monkeypatch.setattr(settings, "smtp_from", "gobernanza@prueba.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_ssl", False)
    monkeypatch.setattr(settings, "docente_aviso_email", "docente@prueba.test")
    monkeypatch.setattr(settings, "public_base_url", "https://gobernanza.prueba.test")

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(models.Usuario(id=1, email="alumna@prueba.test", nombre="Alumna Prueba", password_hash="x", rol="analista"))
        db.add(models.Usuario(id=9, email="docente@prueba.test", nombre="Docente", password_hash="x", rol="admin"))
        db.add(models.ProyectoIA(id=7, usuario_id=1, titulo=TITULO))
        db.commit()
        app = FastAPI()
        app.include_router(proyectos_ia.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
        with TestClient(app) as client:
            yield client, db, engine
    engine.dispose()
    deregister(JSONB)


def _consultas(db):
    return db.query(models.MensajeProyectoIA).filter_by(remitente="consulta_docente").all()


def _avisos(db):
    return db.query(models.ActivityEvent).filter_by(accion=aviso_docente.ACCION_AVISO).all()


def test_consulta_envia_aviso_al_docente_configurado(entorno):
    client, db, _ = entorno
    r = client.post("/proyectos-ia/mio/docente", json={"mensaje": TEXTO_CONSULTA})
    assert r.status_code == 200
    assert len(_SMTPFalso.enviados) == 1
    msg = _SMTPFalso.enviados[0]
    assert msg["To"] == "docente@prueba.test"
    assert msg["Subject"] == f"Gobernanza · Nueva consulta en {TITULO}"
    cuerpo = msg.get_content()
    assert "https://gobernanza.prueba.test/#/proyecto-ia/7" in cuerpo
    assert TITULO in cuerpo
    db.expire_all()
    evento = _avisos(db)[0]
    assert evento.metadata_evento["estado"] == "enviada"
    assert evento.metadata_evento["mensaje_id"] == _consultas(db)[0].id


def test_el_correo_no_lleva_el_texto_ni_datos_del_alumno(entorno):
    client, _, _ = entorno
    client.post("/proyectos-ia/mio/docente", json={"mensaje": TEXTO_CONSULTA})
    msg = _SMTPFalso.enviados[0]
    completo = msg.as_string() + msg.get_content()
    for prohibido in ("legajos", "4521", "clasificador?", "Alumna", "alumna@prueba.test"):
        assert prohibido not in completo


def test_una_consulta_un_aviso(entorno):
    client, db, engine = entorno
    client.post("/proyectos-ia/mio/docente", json={"mensaje": TEXTO_CONSULTA})
    mensaje_id = _consultas(db)[0].id
    # Reintentar el aviso de la misma consulta (p. ej. una tarea repetida) no manda otro correo.
    assert aviso_docente.avisar_consulta_docente(engine, mensaje_id) == "duplicado"
    assert len(_SMTPFalso.enviados) == 1
    # Una segunda consulta sí tiene su propio aviso.
    client.post("/proyectos-ia/mio/docente", json={"mensaje": "Otra consulta distinta"})
    assert len(_SMTPFalso.enviados) == 2


def test_la_consulta_se_guarda_aunque_falle_el_smtp(entorno):
    client, db, _ = entorno
    _SMTPFalso.falla = True
    r = client.post("/proyectos-ia/mio/docente", json={"mensaje": TEXTO_CONSULTA})
    assert r.status_code == 200
    assert len(_consultas(db)) == 1
    assert _SMTPFalso.enviados == []
    db.expire_all()
    assert _avisos(db)[0].metadata_evento["estado"] == "error"


def test_la_consulta_se_guarda_aunque_el_aviso_explote(entorno, monkeypatch):
    client, db, _ = entorno

    def explota(*a, **kw):
        raise RuntimeError("falla inesperada")

    monkeypatch.setattr(notificaciones, "enviar_aviso_consulta_docente", explota)
    r = client.post("/proyectos-ia/mio/docente", json={"mensaje": TEXTO_CONSULTA})
    assert r.status_code == 200
    assert len(_consultas(db)) == 1


def test_sin_destinatario_no_envia(entorno, monkeypatch):
    client, db, _ = entorno
    monkeypatch.setattr(settings, "docente_aviso_email", "")
    assert client.post("/proyectos-ia/mio/docente", json={"mensaje": TEXTO_CONSULTA}).status_code == 200
    assert _SMTPFalso.enviados == []
    db.expire_all()
    assert _avisos(db)[0].metadata_evento["estado"] == "omitida"


def test_varios_docentes_y_titulo_en_una_linea(monkeypatch):
    monkeypatch.setattr(settings, "docente_aviso_email", " a@prueba.test, b@prueba.test ,A@prueba.test,,no-es-correo")
    assert notificaciones.destinatarios_docente() == ["a@prueba.test", "b@prueba.test"]
    assert notificaciones.nombre_proyecto(3, "Título\ncon salto") == "Título con salto"
    assert notificaciones.nombre_proyecto(3, None) == "proyecto #3"


def test_la_respuesta_docente_no_genera_aviso(entorno):
    client, db, _ = entorno
    client.app.dependency_overrides[proyectos_ia.require_admin] = lambda: db.get(models.Usuario, 9)
    assert client.post("/proyectos-ia/7/docente", json={"mensaje": "Respuesta del docente"}).status_code == 200
    assert _SMTPFalso.enviados == []


def test_pendientes_para_el_recordatorio(entorno):
    client, db, _ = entorno
    base = dt.datetime(2026, 10, 1, 12, 0)
    for i, (remitente, dia) in enumerate([("consulta_docente", 0), ("docente", 1), ("consulta_docente", 2), ("consulta_docente", 5)]):
        db.add(models.MensajeProyectoIA(proyecto_id=7, remitente=remitente, contenido=f"m{i}", creado_en=base + dt.timedelta(days=dia)))
    db.commit()
    ahora = base + dt.timedelta(days=6)
    todas = aviso_docente.consultas_sin_respuesta(db, ahora=ahora)
    assert [p["dias"] for p in todas] == [4, 1]  # la primera ya tuvo respuesta
    assert [p["dias"] for p in aviso_docente.consultas_sin_respuesta(db, ahora=ahora, mas_de_dias=2)] == [4]
    estado, _ = notificaciones.enviar_recordatorio_consultas(["docente@prueba.test"], todas, 2)
    assert estado == "enviada"
    cuerpo = _SMTPFalso.enviados[-1].get_content()
    assert "m2" not in cuerpo and "m3" not in cuerpo and "/#/proyecto-ia/7" in cuerpo
