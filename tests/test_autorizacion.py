from __future__ import annotations

import inspect

import pytest
from fastapi import HTTPException
from fastapi.params import Depends

import core.auth as auth
import schemas
from core.auth import require_admin
from routers.areas import crear_area
from routers.decisiones import decidir


class _Usuario:
    def __init__(self, id_=1, rol="analista", email="u.example@test.local"):
        self.id = id_
        self.rol = rol
        self.email = email


class _Hallazgo:
    def __init__(self, id_):
        self.id = id_


class _Informe:
    def __init__(self, usuario_id=1):
        self.usuario_id = usuario_id
        self.hallazgos = [_Hallazgo(1)]
        self.area = None


class _Devolucion:
    def __init__(self, informe):
        self.id = 10
        self.informe = informe
        self.decision = None


class _DBConDevolucion:
    def __init__(self, devolucion):
        self.devolucion = devolucion
        self.agregado = None

    def get(self, model, id_):
        return self.devolucion

    def add(self, obj):
        self.agregado = obj

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_decision_rechaza_informe_de_otro_usuario():
    db = _DBConDevolucion(_Devolucion(_Informe(usuario_id=1)))
    with pytest.raises(HTTPException) as exc:
        decidir(10, schemas.DecisionCreate(escalar=False), db, _Usuario(id_=2))
    assert exc.value.status_code == 403


def test_decision_permite_admin_y_duenio():
    for usuario in (_Usuario(id_=2, rol="admin"), _Usuario(id_=1, rol="analista")):
        db = _DBConDevolucion(_Devolucion(_Informe(usuario_id=1)))
        decision = decidir(10, schemas.DecisionCreate(escalar=False), db, usuario)
        assert decision.decidido_por == usuario.email


def test_decision_valida_hallazgo_ids_no_numericos():
    db = _DBConDevolucion(_Devolucion(_Informe(usuario_id=1)))
    payload = schemas.DecisionCreate.model_construct(hallazgo_ids=["x"])
    with pytest.raises(HTTPException) as exc:
        decidir(10, payload, db, _Usuario(id_=1))
    assert exc.value.status_code == 422


def test_crear_area_exige_admin():
    depend = inspect.signature(crear_area).parameters["_admin"].default
    assert isinstance(depend, Depends)
    assert depend.dependency == require_admin


class _DBToken:
    def __init__(self, activo: bool):
        self.activo = activo

    def get(self, model, id_):
        return type("UsuarioToken", (), {"activo": self.activo})()

    def close(self):
        pass


@pytest.mark.parametrize("activo,esperado", [(True, True), (False, False)])
def test_cookie_respeta_desactivacion_del_usuario(monkeypatch, activo, esperado):
    monkeypatch.setattr(auth, "SessionLocal", lambda: _DBToken(activo))
    assert auth.active_token(auth.make_token(7)) is esperado
