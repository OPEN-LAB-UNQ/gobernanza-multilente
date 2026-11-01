"""Sesiones revocables y desactivación de usuarios."""
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
from core.auth import COOKIE_NAME, hash_password, make_token, sesion_vigente
from database import get_db
from routers import auth


@pytest.fixture
def entorno():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            models.Usuario(id=1, email="admin@t", nombre="Admin", password_hash=hash_password("clave-admin"), rol="admin"),
            models.Usuario(id=2, email="alumno@t", nombre="Alumno", password_hash=hash_password("clave-vieja"), rol="analista"),
        ])
        db.commit()
        app = FastAPI()
        app.include_router(auth.router)
        app.dependency_overrides[get_db] = lambda: db
        yield db, app
    engine.dispose()
    deregister(JSONB)


def _cliente(app, uid, emitido_hace=0):
    client = TestClient(app, base_url="https://testserver")
    token = make_token(uid)
    if emitido_hace:
        uid_s, issued, _ = token.split(".")
        from core.auth import _sign
        payload = f"{uid_s}.{int(issued) - emitido_hace * 1000}"  # el token va en milisegundos
        token = f"{payload}.{_sign(payload)}"
    client.cookies.set(COOKIE_NAME, token)
    return client


def test_sesion_vigente_respeta_activo_y_cierre():
    user = models.Usuario(id=3, activo=True, sesiones_desde=None)
    ahora = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    assert sesion_vigente(user, ahora)
    user.sesiones_desde = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    assert not sesion_vigente(user, ahora - 60_000) and sesion_vigente(user, ahora + 1_000)
    user.activo = False
    assert not sesion_vigente(user, ahora + 1_000)


def test_admin_cierra_las_sesiones_de_un_usuario(entorno):
    db, app = entorno
    alumno = _cliente(app, 2, emitido_hace=30)
    assert alumno.get("/api/me").status_code == 200
    assert _cliente(app, 1).post("/api/usuarios/2/cerrar-sesiones").status_code == 200
    assert alumno.get("/api/me").status_code == 401
    assert _cliente(app, 2).get("/api/me").status_code == 200  # un login nuevo sí vale


def test_desactivar_corta_el_acceso_y_no_se_puede_desactivar_a_uno_mismo(entorno):
    db, app = entorno
    admin = _cliente(app, 1)
    assert admin.patch("/api/usuarios/1", json={"activo": False}).status_code == 409
    assert admin.patch("/api/usuarios/2", json={"activo": False}).json()["activo"] is False
    assert _cliente(app, 2).get("/api/me").status_code == 401
    assert admin.patch("/api/usuarios/2", json={"activo": True}).json()["activo"] is True
    assert _cliente(app, 2).get("/api/me").status_code == 200


def test_solo_un_admin_administra_usuarios(entorno):
    db, app = entorno
    alumno = _cliente(app, 2)
    assert alumno.patch("/api/usuarios/1", json={"activo": False}).status_code == 403
    assert alumno.post("/api/usuarios/1/cerrar-sesiones").status_code == 403


def test_cambiar_la_contrasena_cierra_las_otras_sesiones(entorno):
    db, app = entorno
    otra = _cliente(app, 2, emitido_hace=30)
    esta = _cliente(app, 2, emitido_hace=30)
    assert esta.post("/api/me/password", json={"actual": "mal", "nueva": "clave-nueva-1"}).status_code == 403
    assert esta.post("/api/me/password", json={"actual": "clave-vieja", "nueva": "corta"}).status_code == 422
    resp = esta.post("/api/me/password", json={"actual": "clave-vieja", "nueva": "clave-nueva-1"})
    assert resp.status_code == 200
    assert esta.get("/api/me").status_code == 200   # recibió un token nuevo
    assert otra.get("/api/me").status_code == 401


def test_cerrar_mis_sesiones_incluye_esta(entorno):
    db, app = entorno
    yo = _cliente(app, 2, emitido_hace=30)
    assert yo.post("/api/me/cerrar-sesiones").status_code == 200
    assert _cliente(app, 2, emitido_hace=30).get("/api/me").status_code == 401


def test_un_token_del_mismo_segundo_que_el_cierre_queda_revocado():
    from core.auth import revocar_sesiones, token_info
    user = models.Usuario(id=3, activo=True, sesiones_desde=None)
    viejo = token_info(make_token(3))[1]
    revocar_sesiones(user)
    user.sesiones_desde += dt.timedelta(milliseconds=5)  # el cierre ocurre milisegundos después
    assert not sesion_vigente(user, viejo)


def test_los_tokens_anteriores_en_segundos_siguen_valiendo():
    from core.auth import _sign, token_info
    segundos = int(dt.datetime.now(dt.timezone.utc).timestamp()) - 10
    payload = f"4.{segundos}"
    assert token_info(f"{payload}.{_sign(payload)}") == (4, segundos * 1000)


def test_cambio_de_password_frena_la_fuerza_bruta(entorno):
    db, app = entorno
    from core import auth as core_auth
    core_auth._login_intentos_fallidos.clear()
    alumno = _cliente(app, 2)
    codigos = [alumno.post("/api/me/password", json={"actual": f"mal{i}", "nueva": "otraclave123"}).status_code
               for i in range(9)]
    assert codigos[0] == 403 and codigos[-1] == 429


def test_salir_invalida_el_token(entorno):
    db, app = entorno
    alumno = _cliente(app, 2, emitido_hace=30)
    token = alumno.cookies.get(COOKIE_NAME)
    assert alumno.get("/api/me").status_code == 200
    assert alumno.get("/logout", follow_redirects=False).status_code == 303
    copia = _cliente(app, 2)
    copia.cookies.set(COOKIE_NAME, token)
    assert copia.get("/api/me").status_code == 401  # la copia robada ya no vale


def test_el_login_frena_por_cuenta_aunque_cambie_el_origen(entorno):
    from core import auth as core_auth
    db, app = entorno
    core_auth._login_intentos_fallidos.clear()
    for i in range(8):
        core_auth.registrar_login_fallido("cuenta:alumno@t")
    r = _cliente(app, 2).post("/login", data={"email": "alumno@t", "password": "x"})
    assert r.status_code == 429
    core_auth._login_intentos_fallidos.clear()
