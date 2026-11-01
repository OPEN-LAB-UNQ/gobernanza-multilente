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
from routers import votos_proyectos_ia


def test_endpoint_de_voto_y_payload_estan_publicados():
    assert callable(votos_proyectos_ia.votar_proyecto_ia)
    payload = votos_proyectos_ia.ProyectoIAVotoCreate(
        proyecto_id=12,
        justificacion="El problema esta bien delimitado y el uso de IA conserva revision humana.",
    )
    assert payload.proyecto_id == 12
    assert len(payload.justificacion) >= 40


def test_justificacion_corta_es_rechazada():
    with pytest.raises(ValueError):
        votos_proyectos_ia.ProyectoIAVotoCreate(proyecto_id=12, justificacion="Muy corto")


@pytest.fixture
def entorno(monkeypatch):
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        for i in range(1, 4):
            db.add(models.Usuario(id=i, email=f"test{i}@example.test", nombre=f"Test {i}", password_hash="unused", rol="analista"))
            db.add(models.ProyectoIA(id=i, usuario_id=i, titulo=f"Proyecto {i}"))
        db.add(models.ActividadVotacion(id=1, cohorte="Prueba", activa=True, primera_vuelta_abierta=True, segunda_vuelta_abierta=False, proyectos_ids=[1,2,3], finalistas=[2,3]))
        db.commit()
        app = FastAPI()
        app.include_router(votos_proyectos_ia.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
        with TestClient(app) as client:
            yield client, db, app
    engine.dispose()
    deregister(JSONB)


def test_emision_cambio_y_historial_con_argumentos(entorno):
    client, db, app = entorno
    primero = "El proyecto permite reducir demoras con control humano y datos anonimizados."
    segundo = "Cambio mi voto porque esta propuesta define una prueba y un indicador verificable."
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 2, "justificacion": primero}).status_code == 200
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 3, "justificacion": segundo}).status_code == 200
    assert db.query(models.VotoProyectoIA).count() == 1
    estado = client.get("/proyectos-ia/votos/estado").json()
    assert estado["mi_voto"]["proyecto_id"] == 3
    historial = client.get("/proyectos-ia/votos/historial").json()
    assert len(historial) == 2
    assert historial[0]["detalle"]["justificacion_anterior"] == primero
    assert historial[0]["detalle"]["justificacion"] == segundo
    app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 2)
    assert client.get("/proyectos-ia/votos/historial").json() == []


@pytest.mark.parametrize("proyecto, texto, status", [
    (1, "Una justificacion suficientemente extensa para validar el voto propio.", 400),
    (999, "Una justificacion suficientemente extensa para un proyecto inexistente.", 404),
    (2, "breve", 422),
    (2, " " * 50, 400),
])
def test_rechazos_no_dejan_votos_ni_eventos(entorno, proyecto, texto, status):
    client, db, _ = entorno
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": proyecto, "justificacion": texto}).status_code == status
    assert db.query(models.VotoProyectoIA).count() == 0
    assert db.query(models.ActivityEvent).count() == 0


def test_voto_sin_autenticacion(entorno):
    client, _, app = entorno
    del app.dependency_overrides[get_current_user]
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 2, "justificacion": "Argumento con extension suficiente para probar el acceso no autenticado."}).status_code == 401


def test_primera_vuelta_cerrada(entorno, monkeypatch):
    client, db, _ = entorno
    db.get(models.ActividadVotacion, 1).primera_vuelta_abierta = False
    db.commit()
    respuesta = client.post(
        "/proyectos-ia/votos",
        json={"proyecto_id": 2, "justificacion": "Argumento suficientemente extenso para un voto que ya no debe aceptarse."},
    )
    assert respuesta.status_code == 409
    assert db.query(models.VotoProyectoIA).count() == 0


def test_sin_actividad_no_impide_consultar_los_casos(entorno):
    client, db, _ = entorno
    db.get(models.ActividadVotacion, 1).activa = False
    db.commit()
    estado = client.get("/proyectos-ia/votos/estado")
    assert estado.status_code == 200 and estado.json()["cerrada"]
    assert estado.json()["actividad"] is None
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 2, "justificacion": "Preferencia suficientemente extensa pero sin actividad habilitada."}).status_code == 409
    assert db.query(models.ProyectoIA).count() == 3


def test_segunda_vuelta_admite_un_voto_actualizable(entorno, monkeypatch):
    client, db, _ = entorno
    actividad = db.get(models.ActividadVotacion, 1)
    actividad.primera_vuelta_abierta = False
    actividad.segunda_vuelta_abierta = True
    db.commit()

    assert client.post("/proyectos-ia/votos/segunda-vuelta", json={"proyecto_id": 2, "justificacion": "El proyecto permite una prueba acotada y mantiene la decisión bajo supervisión humana."}).status_code == 200
    assert client.post("/proyectos-ia/votos/segunda-vuelta", json={"proyecto_id": 3, "justificacion": "El proyecto permite una prueba acotada y mantiene la decisión bajo supervisión humana."}).status_code == 200
    assert db.query(models.VotoSegundaVuelta).count() == 1

    estado = client.get("/proyectos-ia/votos/segunda-vuelta/estado").json()
    assert estado["segunda_vuelta"]["mi_voto"]["proyecto_id"] == 3
    assert estado["segunda_vuelta"]["votos_por_proyecto"] == {"2": 0, "3": 1}
    assert estado["segunda_vuelta"]["votos_total"] == 1


def test_segunda_vuelta_rechaza_proyecto_no_finalista(entorno, monkeypatch):
    client, db, _ = entorno
    actividad = db.get(models.ActividadVotacion, 1)
    actividad.primera_vuelta_abierta = False
    actividad.segunda_vuelta_abierta = True
    db.commit()
    respuesta = client.post("/proyectos-ia/votos/segunda-vuelta", json={"proyecto_id": 1, "justificacion": "El proyecto permite una prueba acotada y mantiene la decisión bajo supervisión humana."})
    assert respuesta.status_code == 400
    assert db.query(models.VotoSegundaVuelta).count() == 0


def test_segunda_vuelta_cerrada_publica_estado_y_rechaza_nuevos_votos(entorno, monkeypatch):
    client, db, _ = entorno
    actividad = db.get(models.ActividadVotacion, 1)
    actividad.primera_vuelta_abierta = False
    actividad.segunda_vuelta_abierta = True
    db.commit()
    actividad.segunda_vuelta_abierta = False
    db.commit()

    estado = client.get("/proyectos-ia/votos/segunda-vuelta/estado")
    assert estado.status_code == 200
    assert estado.json()["segunda_vuelta"]["cerrada"] is True

    respuesta = client.post("/proyectos-ia/votos/segunda-vuelta", json={"proyecto_id": 2, "justificacion": "El proyecto permite una prueba acotada y mantiene la decisión bajo supervisión humana."})
    assert respuesta.status_code == 409
    assert db.query(models.VotoSegundaVuelta).count() == 0


def test_versiones_de_propuesta_conservan_antes_y_despues(entorno, monkeypatch):
    from routers import proyectos_ia
    from schemas import ProyectoIAUpdate
    _, db, _ = entorno
    monkeypatch.setattr(proyectos_ia, "_registrar_aprendizajes_auto", lambda *args: None)
    proyectos_ia.actualizar_mi_proyecto(ProyectoIAUpdate(titulo="Titulo actualizado"), db.get(models.Usuario, 1), db)
    evento = db.query(models.ActivityEvent).one()
    assert evento.metadata_evento["cambios"]["titulo"] == {"antes": "Proyecto 1", "despues": "Titulo actualizado"}


def test_configuracion_sin_redeploy_y_separacion_de_cohortes(entorno):
    client, db, app = entorno
    assert client.get("/proyectos-ia/votos/actividades").status_code == 403
    user = db.get(models.Usuario, 1)
    user.rol = "admin"
    db.commit()
    original = db.get(models.ProyectoIA, 2)
    previo = (original.estado, original.retro_docente, original.entrega_final)
    protocolo = models.VersionProtocolo(codigo="R-1", version="1.1", nombre="R-1", tipo_objeto="proyecto_ia", descripcion="Fixture institucional")
    db.add(protocolo)
    db.flush()
    evaluacion = models.EvaluacionCertificacion(protocolo_id=protocolo.id, proyecto_id=2, creado_por_id=1, hash_objeto="a"*64, snapshot_objeto={}, estado="en_revision")
    db.add(evaluacion)
    db.commit()
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 2, "justificacion": "Primera preferencia pedagógica justificada para la actividad original."}).status_code == 200
    config = {"cohorte": "Prueba", "activa": True, "primera_vuelta_abierta": False, "segunda_vuelta_abierta": False, "proyectos_ids": [1,2,3], "finalistas": [2,3]}
    assert client.put("/proyectos-ia/votos/actividades/1", json=config).status_code == 200
    assert client.get("/proyectos-ia/votos/estado").json()["cerrada"]
    config["cohorte"] = "Nueva cohorte"
    config["primera_vuelta_abierta"] = True
    nueva = client.post("/proyectos-ia/votos/actividades", json=config)
    assert nueva.status_code == 200, nueva.text
    assert client.get("/proyectos-ia/votos/estado").json()["mi_voto"] is None
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 3, "justificacion": "Segunda preferencia pedagógica justificada en una nueva cohorte."}).status_code == 200
    assert db.query(models.VotoProyectoIA).count() == 2
    db.refresh(original)
    assert (original.estado, original.retro_docente, original.entrega_final) == previo
    db.refresh(evaluacion)
    assert evaluacion.estado == "en_revision"
    assert evaluacion.hash_objeto == "a"*64 and evaluacion.conclusion_r1 is None
    assert db.query(models.ResultadoControl).count() == 0
    assert db.query(models.SelloCertificacion).count() == 0
    assert db.query(models.RegistroMonitoreo).count() == 0
    assert all(e.modulo in {"votacion", "incubadora"} for e in db.query(models.ActivityEvent))


def test_segunda_vuelta_exige_justificacion(entorno):
    client, db, _ = entorno
    actividad = db.get(models.ActividadVotacion, 1)
    actividad.primera_vuelta_abierta = False
    actividad.segunda_vuelta_abierta = True
    db.commit()
    assert client.post("/proyectos-ia/votos/segunda-vuelta", json={"proyecto_id": 2}).status_code == 422
    assert db.query(models.VotoSegundaVuelta).count() == 0
