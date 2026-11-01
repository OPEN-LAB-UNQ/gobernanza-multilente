"""0.10.62: grupos de cursada. Cada participante ve los proyectos y la votación de su grupo.

Una cuenta sin grupo es del grupo por defecto (las comisiones de Grupo A); la cuenta administradora ve todos.
Pedido del 29/10/2026: el grupo Grupo B no ve los trabajos de las comisiones 1 y 2 de Grupo A, y al revés.
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

import models
from core.auth import get_current_user
from routers import aprendizajes_incubadora, auth, votos_proyectos_ia
from services import grupos
from tests import test_recorrido_propio

entorno = test_recorrido_propio.entorno
JUSTIFICACION = "Propuesta sólida, con indicadores medibles y datos que el área ya tiene."


def _sembrar(db):
    """La persona que consulta (id 1, Grupo A), otra de Grupo A, dos de Grupo B y la administración."""
    db.add_all([
        models.Usuario(id=2, email="eco@example.test", nombre="Eco", password_hash="x", rol="analista"),
        models.Usuario(id=3, email="hac1@example.test", nombre="Hac 1", password_hash="x", rol="analista", grupo="Grupo B"),
        models.Usuario(id=4, email="hac2@example.test", nombre="Hac 2", password_hash="x", rol="analista", grupo="Grupo B"),
        models.Usuario(id=9, email="admin@example.test", nombre="Admin", password_hash="x", rol="admin"),
    ])
    for pid, uid, titulo in ((1, 1, "Propio de Grupo A"), (2, 2, "Otro de Grupo A"),
                             (3, 3, "Recaudación de Grupo B"), (4, 4, "Gasto de Grupo B")):
        db.add(models.ProyectoIA(id=pid, usuario_id=uid, titulo=titulo, estado="en_proceso"))
    db.commit()


def _como(client, db, usuario_id):
    client.app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, usuario_id)


def _titulos(respuesta):
    return {caso["titulo"] for caso in respuesta.json()}


def test_cada_grupo_ve_solo_sus_proyectos_en_la_galeria(entorno):
    client, db = entorno
    _sembrar(db)
    assert _titulos(client.get("/proyectos-ia/casos")) == {"Propio de Grupo A", "Otro de Grupo A"}
    _como(client, db, 3)
    assert _titulos(client.get("/proyectos-ia/casos")) == {"Recaudación de Grupo B", "Gasto de Grupo B"}
    _como(client, db, 9)
    assert len(client.get("/proyectos-ia/casos").json()) == 4


def test_el_trabajo_completo_de_otro_grupo_no_se_puede_abrir(entorno):
    client, db = entorno
    _sembrar(db)
    assert client.get("/proyectos-ia/casos/3").status_code == 404
    assert client.get("/proyectos-ia/casos/2").status_code == 200
    _como(client, db, 4)
    assert client.get("/proyectos-ia/casos/2").status_code == 404
    assert client.get("/proyectos-ia/casos/3").status_code == 200


def test_conexiones_cruza_solo_proyectos_del_mismo_grupo(entorno):
    client, db = entorno
    _sembrar(db)
    _como(client, db, 3)
    respuesta = client.get("/proyectos-ia/conexiones")
    datos = respuesta.json()
    assert datos["total_casos"] == 2
    assert {p["titulo"] for p in datos["proyectos"]} == {"Recaudación de Grupo B", "Gasto de Grupo B"}
    assert "de Grupo A" not in respuesta.text


def test_los_conteos_de_temas_de_la_tutora_son_del_propio_grupo(entorno, monkeypatch):
    client, db = entorno
    _sembrar(db)
    leidos = []
    monkeypatch.setattr(aprendizajes_incubadora, "_tema_presente", lambda texto, claves: leidos.append(texto) or False)
    aprendizajes_incubadora._cruces_rizoma(db, db.get(models.Usuario, 3))
    assert leidos and not any("Grupo A" in texto for texto in leidos)


def test_la_votacion_activa_de_economia_no_aparece_en_hacienda(entorno):
    client, db = entorno
    _sembrar(db)
    client.app.include_router(votos_proyectos_ia.router)
    db.add(models.ActividadVotacion(id=1, cohorte="Grupo A · septiembre", activa=True, primera_vuelta_abierta=True,
                                    proyectos_ids=[1, 2], finalistas=[]))
    db.commit()
    assert client.get("/proyectos-ia/votos/estado").json()["actividad_id"] == 1
    _como(client, db, 3)
    estado = client.get("/proyectos-ia/votos/estado").json()
    assert estado["actividad"] is None and estado["actividad_id"] is None
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 2, "justificacion": JUSTIFICACION}).status_code == 409
    assert client.get("/proyectos-ia/votos/segunda-vuelta/estado").status_code == 409


def test_cada_grupo_tiene_su_votacion_y_no_se_mezclan_proyectos(entorno):
    client, db = entorno
    _sembrar(db)
    client.app.include_router(votos_proyectos_ia.router)
    db.add(models.ActividadVotacion(id=1, cohorte="Grupo A · septiembre", activa=True, primera_vuelta_abierta=True,
                                    proyectos_ids=[1, 2], finalistas=[]))
    db.commit()
    _como(client, db, 9)
    base = {"cohorte": "Grupo B · noviembre", "activa": True, "primera_vuelta_abierta": True, "proyectos_ids": [3, 4]}
    mezcla = client.post("/proyectos-ia/votos/actividades", json={**base, "grupo": "Grupo B", "proyectos_ids": [2, 3]})
    assert mezcla.status_code == 422 and "otro grupo" in mezcla.json()["detail"]
    creada = client.post("/proyectos-ia/votos/actividades", json={**base, "grupo": " Grupo B "})
    assert creada.status_code == 200 and creada.json()["grupo"] == "Grupo B"
    db.expire_all()
    assert db.get(models.ActividadVotacion, 1).activa  # activar la de Grupo B no apaga la de Grupo A
    _como(client, db, 3)
    assert client.get("/proyectos-ia/votos/estado").json()["actividad"]["cohorte"] == "Grupo B · noviembre"
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 4, "justificacion": JUSTIFICACION}).status_code == 200
    _como(client, db, 2)
    assert client.get("/proyectos-ia/votos/estado").json()["actividad"]["cohorte"] == "Grupo A · septiembre"


def test_la_administracion_puede_crear_una_cuenta_en_un_grupo(entorno):
    client, db = entorno
    _sembrar(db)
    client.app.include_router(auth.router)
    _como(client, db, 9)
    r = client.post("/api/usuarios", json={"email": "Nueva@Example.test", "nombre": "Nueva", "password": "clave-de-prueba-1",
                                           "rol": "analista", "grupo": " Grupo B "})
    assert r.status_code == 200 and r.json()["grupo"] == "Grupo B"
    assert db.query(models.Usuario).filter_by(email="nueva@example.test").one().grupo == "Grupo B"
    sin_grupo = client.post("/api/usuarios", json={"email": "otra@example.test", "nombre": "Otra", "password": "clave-de-prueba-2",
                                                   "rol": "analista", "grupo": "  "})
    assert sin_grupo.status_code == 200 and sin_grupo.json()["grupo"] is None


def test_sin_grupo_es_el_grupo_por_defecto_y_no_todos():
    assert grupos.normalizar("   ") is None and grupos.normalizar(" Grupo B ") == "Grupo B"
    assert str(grupos.filtro(models.Usuario.grupo, None)).endswith("IS NULL")
    assert "IS NULL" not in str(grupos.filtro(models.Usuario.grupo, "Grupo B"))
    assert grupos.ve_todo(None) and grupos.ve_todo(models.Usuario(rol="admin"))
    assert not grupos.ve_todo(models.Usuario(rol="analista"))


def test_la_migracion_conserva_los_datos_y_permite_una_votacion_activa_por_grupo():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    ruta = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261029_grupos.py"
    spec = importlib.util.spec_from_file_location("m_grupos", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.down_revision == "20261024_respuestas_prioridad" and len(m.revision) <= 32
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, email VARCHAR(200))")
        conn.exec_driver_sql("CREATE TABLE actividades_votacion (id INTEGER PRIMARY KEY, activa BOOLEAN NOT NULL)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX uq_actividad_votacion_activa ON actividades_votacion (activa)")
        conn.exec_driver_sql("INSERT INTO usuarios (id, email) VALUES (1, 'a@example.test')")
        conn.exec_driver_sql("INSERT INTO actividades_votacion (id, activa) VALUES (1, 1)")
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
            # Nada se borra: la cuenta y la votación existentes quedan en el grupo por defecto.
            assert conn.exec_driver_sql("SELECT email, grupo FROM usuarios").all() == [("a@example.test", None)]
            conn.exec_driver_sql("INSERT INTO actividades_votacion (id, activa, grupo) VALUES (2, 1, 'Grupo B')")
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql("INSERT INTO actividades_votacion (id, activa, grupo) VALUES (3, 1, 'Grupo B')")
            conn.exec_driver_sql("DELETE FROM actividades_votacion WHERE id = 2")
            m.downgrade()
            assert "grupo" not in {c["name"] for c in sa_inspect(conn).get_columns("usuarios")}
            assert "grupo" not in {c["name"] for c in sa_inspect(conn).get_columns("actividades_votacion")}
    engine.dispose()


# --- Fugas que encontró la revisión independiente ---

def test_la_pagina_principal_no_entrega_las_sintesis_de_economia_a_otro_grupo():
    import main

    grupo_b = main.index_para(models.Usuario(rol="analista", grupo="Grupo B"))
    grupo_a = main.index_para(models.Usuario(rol="analista"))
    admin = main.index_para(models.Usuario(rol="admin"))
    for propio in (grupo_a, admin):
        assert "Circuito asistido de revisión de expedientes" in propio and 'data-abrir-caso="10"' in propio
        assert "Habilitado para el proyecto ganador" in propio and "Las de tu grupo todavía no están" not in propio
    assert "Circuito asistido de revisión de expedientes" not in grupo_b and 'data-abrir-caso="10"' not in grupo_b
    assert "Habilitado para el proyecto ganador" not in grupo_b and "Tres desarrollos conjuntos" not in grupo_b
    assert 'id="view-sintesis"' in grupo_b and "Las de tu grupo todavía no están" in grupo_b
    assert grupo_b.count("<div") - grupo_b.count("</div>") == grupo_a.count("<div") - grupo_a.count("</div>")


def test_las_metricas_de_calibracion_cuentan_solo_el_propio_grupo(entorno):
    from routers import aprendizajes

    client, db = entorno
    _sembrar(db)
    for usuario_id, esperado in ((3, 2), (1, 2), (9, 4)):
        assert aprendizajes._metricas_proyectos_ia(db, db.get(models.Usuario, usuario_id))["total_proyectos"] == esperado


def test_las_metricas_de_la_tutora_cuentan_solo_eventos_del_propio_grupo(entorno):
    client, db = entorno
    _sembrar(db)
    client.app.include_router(aprendizajes_incubadora.router)
    for evento_id, proyecto_id, tema in ((1, 2, "tema de Grupo A"), (2, 3, "tema de Grupo B")):
        db.add(models.AprendizajeIncubadora(id=evento_id, proyecto_id=proyecto_id, usuario_id=9, tipo="nota_docente",
                                            titulo="Nota", contenido="Contenido", estado="propuesto", tema=tema))
    db.commit()
    ruta = aprendizajes_incubadora.router.prefix + "/aprendizaje"
    _como(client, db, 3)
    metricas = client.get(ruta).json()["metricas"]
    assert metricas["total_eventos"] == 1 and set(metricas["por_tema"]) == {"tema de Grupo B"}
    _como(client, db, 9)
    assert client.get(ruta).json()["metricas"]["total_eventos"] == 2


def test_un_proyecto_cuyo_dueno_cambio_de_grupo_sale_de_la_votacion(entorno):
    client, db = entorno
    _sembrar(db)
    client.app.include_router(votos_proyectos_ia.router)
    db.add(models.ActividadVotacion(id=1, cohorte="Grupo A · septiembre", activa=True, primera_vuelta_abierta=True,
                                    proyectos_ids=[1, 2], finalistas=[]))
    db.get(models.Usuario, 2).grupo = "Grupo B"  # como una cuenta que pasa a Grupo B después de la votación
    db.commit()
    _como(client, db, 9)
    assert {r["titulo"] for r in client.get("/proyectos-ia/votos/resultados").json()} == {"Propio de Grupo A"}
    _como(client, db, 1)
    assert client.post("/proyectos-ia/votos", json={"proyecto_id": 2, "justificacion": JUSTIFICACION}).status_code == 404
