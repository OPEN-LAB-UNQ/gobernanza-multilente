"""Tests del router de informes: validacion de rol al crear informe.

Regresion del bug `if user.rol == lector:` (sin comillas) que rompia
POST /api/informes con NameError para *cualquier* rol, no solo lector.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import schemas
from routers.informes import borrar_informe, crear_informe


class _DummyDB:
    def get(self, model, id_):
        return None  # fuerza 404 antes de tocar la DB real


class _DummyUsuario:
    def __init__(self, rol):
        self.rol = rol
        self.id = 1
        self.email = "test@example.com"


def _payload():
    return schemas.InformeCreate(area_id=1, periodo="2026-01", datos=[{"monto": 100}])


def test_crear_informe_rechaza_rol_lector():
    with pytest.raises(HTTPException) as exc:
        crear_informe(_payload(), _DummyDB(), _DummyUsuario("lector"))
    assert exc.value.status_code == 403


def test_crear_informe_no_rompe_por_nameerror_con_otros_roles():
    for rol in ("admin", "analista"):
        with pytest.raises(HTTPException) as exc:
            crear_informe(_payload(), _DummyDB(), _DummyUsuario(rol))
        # debe fallar por area inexistente (404), nunca por NameError
        assert exc.value.status_code == 404



class _InformeBorrable:
    def __init__(self, usuario_id=1):
        self.id = 22
        self.usuario_id = usuario_id
        self.trabajos_analisis = []
        self.learning_events = []
        self.hallazgos = []
        self.interpretaciones = []
        self.triangulacion = None
        self.devolucion = None


class _DBBorrado:
    def __init__(self, informe):
        self.informe = informe
        self.deleted = []
        self.committed = False

    def get(self, model, id_):
        return self.informe

    def add(self, obj):
        pass

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.committed = True

    def query(self, model):
        return _QueryVacia()


class _QueryVacia:
    def filter(self, *args, **kwargs):
        return self

    def __iter__(self):
        return iter(())

    def first(self):
        return None


def test_borrar_informe_rechaza_lector():
    db = _DBBorrado(_InformeBorrable(usuario_id=1))
    with pytest.raises(HTTPException) as exc:
        borrar_informe(22, db, _DummyUsuario("lector"))
    assert exc.value.status_code == 403
    assert not db.deleted


def test_borrar_informe_permite_analista_duenio():
    db = _DBBorrado(_InformeBorrable(usuario_id=1))
    resp = borrar_informe(22, db, _DummyUsuario("analista"))
    assert resp == {"ok": True}
    assert db.deleted == [db.informe]
    assert db.committed
