"""Incubadora admite 30.000 caracteres de punta a punta (consulta de una participante, 24/10/2026).

La entrega del proyecto quedó cortada en 16.000 caracteres: hasta el 19/09/2026 el servidor la recortaba
en silencio (``_limpiar_texto(payload.entrega_final, 16000)``) y, después, la pantalla volvía a mostrar
esa versión vieja encima del texto recién pegado cada vez que se guardaba el contexto o se consultaba al
docente. Estas pruebas guardan y releen textos de 29.999 caracteres sin recorte (entrega, contexto y
consulta al docente) y comprueban que 30.001 se rechaza con un mensaje claro y sin tocar lo guardado.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
import schemas
from core.auth import get_current_user, require_admin
from database import get_db
from routers import proyectos_ia

TOPE = 30000


def _texto(n: int) -> str:
    """Texto realista (acentos, eñes, saltos de línea y un emoji) de exactamente n caracteres, sin bordes en blanco."""
    base = "Párrafo de la propuesta: ñandú, acción y gestión pública 📊.\nSegunda línea con «comillas».\n"
    texto = (base * (n // len(base) + 2))[:n - 1] + "."
    assert len(texto) == n and texto == texto.strip()
    return texto


def _cliente(monkeypatch):
    # Se registra en cada llamada, como el resto de la batería: otra prueba puede haber
    # reemplazado la compilación de JSONB para SQLite antes de que corra ésta.
    @compiles(JSONB, "sqlite")
    def _json_sqlite(element, compiler, **kw):
        return "JSON"

    monkeypatch.setattr(proyectos_ia, "_registrar_aprendizajes_auto", lambda *a, **k: None)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(models.Usuario(id=1, email="part@example.test", nombre="Participante", password_hash="x", rol="analista"))
    db.add(models.Usuario(id=2, email="doc@example.test", nombre="Docente", password_hash="x", rol="admin"))
    db.add(models.ProyectoIA(id=1, usuario_id=1, titulo="Caso", estado="en_proceso",
                             entrega_final="v" * 16000))
    db.commit()
    app = FastAPI()
    app.include_router(proyectos_ia.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
    app.dependency_overrides[require_admin] = lambda: db.get(models.Usuario, 2)
    return db, TestClient(app)


def test_los_topes_del_servidor_son_30000():
    assert proyectos_ia.MAX_ENTREGA_CHARS == proyectos_ia.MAX_SITUACION_CHARS == TOPE
    assert proyectos_ia.MAX_MENSAJE_DOCENTE_CHARS == TOPE


def test_entrega_final_de_29999_se_guarda_y_se_relee_completa(monkeypatch):
    db, client = _cliente(monkeypatch)
    texto = _texto(29999)
    r = client.patch("/proyectos-ia/mio", json={"entrega_final": texto})
    assert r.status_code == 200, r.text
    assert r.json()["entrega_final"] == texto
    db.expire_all()
    assert db.get(models.ProyectoIA, 1).entrega_final == texto
    assert client.get("/proyectos-ia/mio").json()["entrega_final"] == texto


def test_entrega_y_marcar_entregado_con_30000_exactos(monkeypatch):
    db, client = _cliente(monkeypatch)
    texto = _texto(TOPE)
    r = client.patch("/proyectos-ia/mio", json={"entrega_final": texto, "estado": "entregado"})
    assert r.status_code == 200, r.text
    db.expire_all()
    proyecto = db.get(models.ProyectoIA, 1)
    assert proyecto.entrega_final == texto and proyecto.estado == "entregado"


def test_contexto_de_29999_se_guarda_y_se_relee_completo(monkeypatch):
    db, client = _cliente(monkeypatch)
    texto = _texto(29999)
    r = client.patch("/proyectos-ia/mio", json={"situacion": texto})
    assert r.status_code == 200, r.text
    assert client.get("/proyectos-ia/mio").json()["situacion"] == texto
    # Guardar sólo el contexto no toca la entrega guardada.
    db.expire_all()
    assert db.get(models.ProyectoIA, 1).entrega_final == "v" * 16000


def test_consulta_al_docente_de_29999_se_guarda_y_se_relee_completa(monkeypatch):
    db, client = _cliente(monkeypatch)
    texto = _texto(29999)
    r = client.post("/proyectos-ia/mio/docente", json={"mensaje": texto})
    assert r.status_code == 200, r.text
    db.expire_all()
    guardado = db.query(models.MensajeProyectoIA).filter_by(proyecto_id=1, remitente="consulta_docente").one()
    assert guardado.contenido == texto
    leidos = [m["contenido"] for m in client.get("/proyectos-ia/mio").json()["mensajes"] if m["remitente"] == "consulta_docente"]
    assert leidos == [texto]


def test_respuesta_docente_de_29999_se_guarda_completa(monkeypatch):
    db, client = _cliente(monkeypatch)
    texto = _texto(29999)
    r = client.post("/proyectos-ia/1/docente", json={"mensaje": texto})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(models.MensajeProyectoIA).filter_by(proyecto_id=1, remitente="docente").one().contenido == texto


def _rechazo_claro(r, campo: str):
    assert r.status_code == 422, r.text
    detalle = r.json()["detail"]
    assert isinstance(detalle, str), "el rechazo debe ser un texto legible, no la lista de pydantic"
    assert detalle.startswith(campo)
    assert "30.000" in detalle and "30.001" in detalle and "No se guardó" in detalle


def test_entrega_de_30001_se_rechaza_con_mensaje_claro_y_no_pisa_lo_guardado(monkeypatch):
    db, client = _cliente(monkeypatch)
    _rechazo_claro(client.patch("/proyectos-ia/mio", json={"entrega_final": _texto(30001)}), "La entrega final")
    db.expire_all()
    assert db.get(models.ProyectoIA, 1).entrega_final == "v" * 16000


def test_contexto_de_30001_se_rechaza_con_mensaje_claro(monkeypatch):
    db, client = _cliente(monkeypatch)
    _rechazo_claro(client.patch("/proyectos-ia/mio", json={"situacion": _texto(30001)}), "La situación a mejorar")
    db.expire_all()
    assert db.get(models.ProyectoIA, 1).situacion is None


def test_consulta_al_docente_de_30001_se_rechaza_con_mensaje_claro(monkeypatch):
    db, client = _cliente(monkeypatch)
    _rechazo_claro(client.post("/proyectos-ia/mio/docente", json={"mensaje": _texto(30001)}), "El mensaje")
    assert db.query(models.MensajeProyectoIA).count() == 0


def test_espacios_de_los_bordes_no_cuentan_para_el_tope(monkeypatch):
    db, client = _cliente(monkeypatch)
    texto = _texto(TOPE)
    r = client.post("/proyectos-ia/mio/docente", json={"mensaje": "\n  " + texto + "  \n"})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(models.MensajeProyectoIA).one().contenido == texto


def test_el_esquema_no_corta_antes_que_el_router():
    # pydantic sólo frena cuerpos desmesurados; el tope de 30.000 lo explica el router.
    assert schemas.ProyectoIADocenteMensajeCreate(mensaje="x" * 30001).mensaje
