"""Regresiones del control de consistencia del 19/09/2026 (H01-H04).

Nadie se autorrevisa, no se pierde texto en silencio, la interfaz no confirma
una entrega fallida y la demo pública funciona bajo la CSP estricta del sitio.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user
from database import get_db
from routers import proyectos_ia

STATIC = Path(__file__).resolve().parents[1] / "static"
ROOT = STATIC.parent


def _cliente(monkeypatch):
    # El registro automático usa operadores JSON de PostgreSQL que el SQLite de la suite no ofrece.
    monkeypatch.setattr(proyectos_ia, "_registrar_aprendizajes_auto", lambda *a, **k: None)
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(models.Usuario(id=1, email="part@example.test", nombre="Participante", password_hash="x", rol="analista"))
    db.add(models.Usuario(id=2, email="doc@example.test", nombre="Docente", password_hash="x", rol="admin"))
    db.add(models.ProyectoIA(id=1, usuario_id=1, titulo="Caso", estado="en_proceso"))
    db.commit()
    app = FastAPI()
    app.include_router(proyectos_ia.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
    return app, db, TestClient(app)


def test_participante_no_puede_marcarse_revisado_pero_docente_si(monkeypatch):
    app, db, client = _cliente(monkeypatch)
    r = client.patch("/proyectos-ia/mio", json={"estado": "revisado"})
    assert r.status_code == 403
    assert "docente" in r.json()["detail"]
    assert db.get(models.ProyectoIA, 1).estado == "en_proceso"
    # Sin entrega final ni aportes propios no hay nada que entregar.
    vacio = client.patch("/proyectos-ia/mio", json={"estado": "entregado", "entrega_final": ""})
    assert vacio.status_code == 422 and "entrega final" in vacio.json()["detail"]
    assert db.get(models.ProyectoIA, 1).estado == "en_proceso"
    # Una conversación con aportes propios sí puede entregarse sin texto final.
    db.add(models.MensajeProyectoIA(proyecto_id=1, remitente="participante", contenido="Mi propuesta conversada"))
    db.commit()
    db.expire_all()
    assert client.patch("/proyectos-ia/mio", json={"estado": "entregado", "entrega_final": ""}).status_code == 200
    assert client.patch("/proyectos-ia/mio", json={"estado": "entregado", "entrega_final": "Propuesta"}).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 2)
    r = client.patch("/proyectos-ia/1/retro", json={"estado": "revisado", "retro_docente": "Devolución"})
    assert r.status_code == 200
    assert db.get(models.ProyectoIA, 1).estado == "revisado"
    # Un proyecto ya revisado por el docente puede guardarse sin perder ese estado.
    app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
    assert client.patch("/proyectos-ia/mio", json={"titulo": "Caso ajustado", "estado": "revisado"}).status_code == 200


def test_entrega_larga_se_rechaza_sin_recortar_ni_guardar(monkeypatch):
    _app, db, client = _cliente(monkeypatch)
    limite = proyectos_ia.MAX_ENTREGA_CHARS
    completa = "a" * (limite - 5) + "FINAL"
    assert client.patch("/proyectos-ia/mio", json={"entrega_final": completa}).status_code == 200
    assert db.get(models.ProyectoIA, 1).entrega_final.endswith("FINAL")
    r = client.patch("/proyectos-ia/mio", json={"entrega_final": "b" * (limite + 25), "estado": "entregado"})
    assert r.status_code == 422
    assert "No se guardó" in r.json()["detail"]
    db.expire_all()
    proyecto = db.get(models.ProyectoIA, 1)
    assert proyecto.entrega_final == completa
    assert proyecto.estado == "en_proceso"
    r = client.patch("/proyectos-ia/mio", json={"situacion": "c" * (proyectos_ia.MAX_SITUACION_CHARS + 1)})
    assert r.status_code == 422


def test_interfaz_confirma_entrega_solo_con_estado_persistido():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    guardar = js.split("async function guardarProyectoIA", 1)[1].split("\n}\n", 1)[0]
    assert "return data;" in guardar and "return null;" in guardar
    entrega = js.split("async function guardarEntregaProyecto", 1)[1].split("\n}\n", 1)[0]
    assert 'data && data.estado === "entregado"' in entrega
    assert entrega.index("const data = await guardarProyectoIA") < entrega.index("Entrega registrada")
    assert f"const MAX_ENTREGA_CHARS = {proyectos_ia.MAX_ENTREGA_CHARS};" in js
    assert 'id="proyecto-entrega-contador"' in (STATIC / "index.html").read_text(encoding="utf-8")
    assert "La entrega final está vacía" in entrega
    pre = js.split("function renderPredevolucionIA", 1)[1].split("\n}\n", 1)[0]
    assert "fmtFecha(pre.creado_en)" in pre and "puede no reflejar la versión actual" in pre


def test_demo_publica_es_compatible_con_csp_estricta():
    html = (STATIC / "probar.html").read_text(encoding="utf-8")
    assert "<script>" not in html and '<script src="/probar.js" defer></script>' in html
    assert "<iframe" not in html and "onclick=" not in html
    assert "[hidden] { display: none !important; }" in html
    js = (STATIC / "probar.js").read_text(encoding="utf-8")
    assert "/api/ejemplos/publicos" in js and ".src =" not in js
    from main import app as main_app
    publico = TestClient(main_app).get("/probar.js", follow_redirects=False)
    assert publico.status_code == 200
    assert "javascript" in publico.headers["content-type"]


def test_servicio_puede_escribir_los_aprendizajes_curados():
    unit = (ROOT / "systemd" / "gobernanza.service").read_text(encoding="utf-8")
    linea = next(fila for fila in unit.splitlines() if fila.startswith("ReadWritePaths="))
    for archivo in ("APRENDIZAJES.md", "APRENDIZAJES_INCUBADORA.md"):
        assert f"/home/gobernanza/{archivo}" in linea
