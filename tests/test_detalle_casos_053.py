"""Lectura íntegra de trabajos visibles, sin ampliar acceso al chat privado."""
import pytest

import models
from core.auth import get_current_user
from routers import proyectos_ia
from tests import test_recorrido_propio

entorno = test_recorrido_propio.entorno


def crear(db, *, rol="analista", email="otra@example.test", titulo="Obras preventivas"):
    db.add(models.Usuario(id=2, email=email, nombre="Otra persona", password_hash="unused", rol=rol))
    p = models.ProyectoIA(id=2, usuario_id=2, titulo=titulo, estado="en_proceso")
    db.add(p)
    db.commit()
    return p


def test_detalle_otro_participante_conserva_texto_completo_sin_campos_privados(entorno):
    client, db = entorno
    p = crear(db)
    p.situacion = "Primer párrafo.\n\n" + "Contexto con restricciones. " * 100
    p.entrega_final = "Propuesta completa\n" + "Detalle verificable. " * 1400
    p.retro_docente = "Devolución privada"
    db.add(models.MensajeProyectoIA(proyecto_id=2, remitente="participante", contenido="Chat privado"))
    db.commit()
    antes = db.query(models.ActivityEvent).count()
    respuesta = client.get("/proyectos-ia/casos/2")
    assert respuesta.status_code == 200
    data = respuesta.json()
    assert data["situacion"] == p.situacion and data["propuesta"] == p.entrega_final
    assert set(data) == {"id", "titulo", "organismo_area", "situacion", "propuesta", "estado", "actualizado_en"}
    assert "Chat privado" not in respuesta.text and "Devolución privada" not in respuesta.text
    assert "otra@example.test" not in respuesta.text
    assert db.query(models.ActivityEvent).count() == antes
    assert p.estado == "en_proceso"


@pytest.mark.parametrize("oculto", ["admin", "vacio", "excluido", "inexistente"])
def test_detalle_respeta_los_mismos_limites_de_la_galeria(entorno, monkeypatch, oculto):
    client, db = entorno
    if oculto != "inexistente":
        crear(db, rol="admin" if oculto == "admin" else "analista", titulo="" if oculto == "vacio" else "Título")
    if oculto == "excluido":
        monkeypatch.setattr(proyectos_ia, "USUARIOS_EXCLUIDOS_METRICAS", {"otra@example.test"})
    assert client.get("/proyectos-ia/casos/2").status_code == 404


def test_detalle_exige_sesion(entorno):
    client, db = entorno
    crear(db)
    del client.app.dependency_overrides[get_current_user]
    assert client.get("/proyectos-ia/casos/2").status_code == 401


def test_propuesta_ausente_no_se_inventa_ni_se_extrae_del_chat(entorno):
    client, db = entorno
    crear(db)
    db.add(models.MensajeProyectoIA(proyecto_id=2, remitente="ia", contenido="Propuesta sugerida privada"))
    db.commit()
    data = client.get("/proyectos-ia/casos/2").json()
    assert data["situacion"] == "" and data["propuesta"] == ""
