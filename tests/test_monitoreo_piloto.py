import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_calibracion_registro import entorno  # noqa: F401  (fixture reutilizada)

import models
from routers import monitoreo


@pytest.fixture
def piloto(entorno, monkeypatch):  # noqa: F811
    db, _ = entorno
    for ident in (2, 3):
        db.add(models.Usuario(id=ident, email=f"persona{ident}@test", nombre="Persona", password_hash="x", rol="analista"))
    db.flush()
    ganador = models.ProyectoIA(usuario_id=2, titulo="Piloto confirmado")
    cartera = models.ProyectoIA(usuario_id=3, titulo="En cartera")
    db.add_all([ganador, cartera])
    db.flush()
    registro = models.RegistroMonitoreo(proyecto_id=cartera.id, usuario_id=3, tipo="avance", titulo="Historial",
                                        contenido="Contenido anterior", estado="abierto")
    db.add(registro)
    db.commit()
    monkeypatch.setattr(monitoreo.settings, "monitoreo_proyecto_id", ganador.id)
    return db, ganador, cartera, registro


@pytest.mark.parametrize("usuario_id", [1, 3])
def test_cartera_lectura_sin_crear_ni_editar(piloto, usuario_id):
    db, ganador, cartera, registro = piloto
    usuario = db.get(models.Usuario, usuario_id)
    historial = monitoreo.listar_monitoreo(cartera.id, db, usuario)
    assert historial["habilitado"] is False
    assert historial["registros"][0]["contenido"] == "Contenido anterior"
    for accion in (
        lambda: monitoreo.registrar_monitoreo(cartera.id, {"tipo": "avance", "titulo": "Nuevo", "contenido": "Nuevo"}, db, usuario),
        lambda: monitoreo.actualizar_estado_monitoreo(registro.id, {"estado": "resuelto"}, db, usuario),
    ):
        with pytest.raises(HTTPException) as e:
            accion()
        assert e.value.status_code == 403
    db.refresh(registro)
    assert registro.estado == "abierto"
    assert db.scalar(select(func.count()).select_from(models.RegistroMonitoreo)) == 1
    assert db.scalar(select(func.count()).select_from(models.ActivityEvent)) == 0


@pytest.mark.parametrize("usuario_id", [1, 2])
def test_ganador_puede_registrar_y_cerrar_con_traza(piloto, usuario_id):
    db, ganador, cartera, registro = piloto
    usuario = db.get(models.Usuario, usuario_id)
    resultado = monitoreo.registrar_monitoreo(ganador.id, {"tipo": "avance", "titulo": "Prueba", "contenido": "Avance comprobado"}, db, usuario)
    assert resultado["habilitado"] is True
    nuevo = resultado["registros"][0]
    cerrado = monitoreo.actualizar_estado_monitoreo(nuevo["id"], {"estado": "resuelto"}, db, usuario)
    assert cerrado["estado"] == "resuelto"
    assert cerrado["metadata"]["cambios_estado"][0]["usuario_id"] == usuario_id


def test_ser_ganador_no_permite_acceso_a_otra_persona(piloto):
    db, ganador, cartera, registro = piloto
    otro = db.get(models.Usuario, 3)
    with pytest.raises(HTTPException) as e:
        monitoreo.listar_monitoreo(ganador.id, db, otro)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        monitoreo.registrar_monitoreo(ganador.id, {}, db, otro)
    assert e.value.status_code == 403


def test_sin_configuracion_solo_lectura(piloto, monkeypatch):
    db, ganador, cartera, registro = piloto
    monkeypatch.setattr(monitoreo.settings, "monitoreo_proyecto_id", None)
    admin = db.get(models.Usuario, 1)
    assert not monitoreo.listar_monitoreo(ganador.id, db, admin)["habilitado"]
    with pytest.raises(HTTPException) as e:
        monitoreo.registrar_monitoreo(ganador.id, {}, db, admin)
    assert e.value.status_code == 403
