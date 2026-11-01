from __future__ import annotations

import pytest
from fastapi import HTTPException

import schemas
from routers.decisiones import decidir
from routers.informes import analizar_informe
from routers.jobs import encolar_informe


class _Usuario:
    def __init__(self, rol="lector", id_=1):
        self.id = id_
        self.rol = rol
        self.email = "lector@example.com"
        self.email_notificaciones = None


class _Informe:
    def __init__(self, usuario_id=1):
        self.id = 20
        self.usuario_id = usuario_id
        self.devolucion = None
        self.hallazgos = []


class _Hallazgo:
    def __init__(self, id_):
        self.id = id_


class _InformeConHallazgos:
    usuario_id = 1
    area = None
    hallazgos = [_Hallazgo(1)]


class _Devolucion:
    id = 10
    decision = None
    informe = _InformeConHallazgos()


class _DB:
    def __init__(self, obj):
        self.obj = obj

    def get(self, _model, _id):
        return self.obj


def test_lector_no_puede_analizar_informe_propio():
    with pytest.raises(HTTPException) as exc:
        analizar_informe(20, {}, _DB(_Informe(usuario_id=1)), _Usuario("lector", 1))
    assert exc.value.status_code == 403


def test_lector_no_puede_encolar_analisis_propio():
    with pytest.raises(HTTPException) as exc:
        encolar_informe(20, {}, _Usuario("lector", 1), _DB(_Informe(usuario_id=1)))
    assert exc.value.status_code == 403


def test_lector_no_puede_registrar_decision_propia():
    with pytest.raises(HTTPException) as exc:
        decidir(10, schemas.DecisionCreate(escalar=False), _DB(_Devolucion()), _Usuario("lector", 1))
    assert exc.value.status_code == 403
