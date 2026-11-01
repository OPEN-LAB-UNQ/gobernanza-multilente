"""El mapa de recorridos sólo puede afirmar lo que está registrado, y leerlo no escribe nada."""
import pytest
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


@pytest.fixture
def entorno():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(models.Area(id=1, nombre="Área de prueba", codigo="prueba"))
        db.add(models.Usuario(id=1, email="una@example.test", nombre="Una", password_hash="unused", rol="analista"))
        db.commit()
        app = FastAPI()
        app.include_router(proyectos_ia.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
        with TestClient(app) as client:
            yield client, db
    engine.dispose()
    deregister(JSONB)


def test_leer_el_recorrido_no_crea_el_proyecto(entorno):
    client, db = entorno
    datos = client.get("/proyectos-ia/mi-recorrido").json()
    assert db.query(models.ProyectoIA).count() == 0
    assert datos["incubadora"]["hechos"] == []
    assert datos["multilente"]["hechos"] == []
    assert "Todavía no" in datos["incubadora"]["detalle"]


def test_sin_informes_ni_proyecto_no_se_da_nada_por_hecho(entorno):
    client, db = entorno
    datos = client.get("/proyectos-ia/mi-recorrido").json()
    assert datos["conexiones"]["hechos"] == []
    assert datos["monitoreo"]["hechos"] == []
    assert datos["multilente"]["detalle"].startswith("Todavía no")


def test_un_informe_propio_marca_el_recorrido_de_analisis(entorno):
    client, db = entorno
    db.add(models.Informe(id=1, area_id=1, usuario_id=1, periodo="2026-09", datos={}, dominio="prueba"))
    db.commit()
    datos = client.get("/proyectos-ia/mi-recorrido").json()
    assert datos["multilente"]["hechos"] == ["cargar", "analizar", "leer"]
    assert datos["multilente"]["detalle"] == "1 informe propio."


def test_el_informe_de_otra_persona_no_cuenta(entorno):
    client, db = entorno
    db.add(models.Usuario(id=2, email="otra@example.test", nombre="Otra", password_hash="unused", rol="analista"))
    db.commit()
    db.add(models.Informe(id=2, area_id=1, usuario_id=2, periodo="2026-09", datos={}, dominio="prueba"))
    db.commit()
    datos = client.get("/proyectos-ia/mi-recorrido").json()
    assert datos["multilente"]["hechos"] == []


def test_un_proyecto_nombrado_entra_al_mapa_y_a_la_cartera(entorno):
    client, db = entorno
    db.add(models.ProyectoIA(id=1, usuario_id=1, titulo="Expedientes demorados",
                             organismo_area="Dirección de Prueba", situacion="Hoy la revisión demora treinta días."))
    db.commit()
    datos = client.get("/proyectos-ia/mi-recorrido").json()
    assert "problema" in datos["incubadora"]["hechos"]
    assert datos["conexiones"]["hechos"] == ["proyecto", "mapa"]
    assert datos["monitoreo"]["hechos"] == ["cartera"]
    assert "criterios" in datos["incubadora"]["detalle"]


def test_la_entrega_y_la_devolucion_docente_se_distinguen(entorno):
    client, db = entorno
    proyecto = models.ProyectoIA(id=1, usuario_id=1, titulo="Expedientes", situacion="Demoras de treinta días.",
                                 estado="entregado")
    db.add(proyecto)
    db.commit()
    entregado = client.get("/proyectos-ia/mi-recorrido").json()["incubadora"]["hechos"]
    assert "entregar" in entregado and "devolucion" not in entregado
    proyecto.estado = "revisado"
    db.commit()
    revisado = client.get("/proyectos-ia/mi-recorrido").json()["incubadora"]["hechos"]
    assert "devolucion" in revisado
