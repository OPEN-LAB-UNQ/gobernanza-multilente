"""Borrar un informe no puede chocar con claves foráneas (Postgres las exige;
acá se activan en SQLite para reproducirlo)."""
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from routers.informes import borrar_informe


def test_borrar_informe_con_hipotesis_exploratorias():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda con, _: con.execute("PRAGMA foreign_keys=ON"))
    try:
        models.Base.metadata.create_all(engine)
        with Session(engine) as db:
            admin = models.Usuario(id=1, email="admin@test", nombre="Admin", password_hash="x", rol="admin")
            db.add_all([admin, models.Area(id=1, nombre="Area", codigo="A")])
            db.flush()
            informe = models.Informe(area_id=1, usuario_id=1, periodo="2026-09", dominio="general",
                                     datos=[{"total": 12}], saneamiento={})
            db.add(informe)
            db.flush()
            db.add(models.HipotesisExploratoria(informe_id=informe.id, tipo_pista="preguntas_no_formuladas",
                                                texto_hipotesis="¿Por qué sube?", modelo="gpt"))
            db.commit()

            assert borrar_informe(informe.id, db, admin) == {"ok": True}
            assert db.query(models.HipotesisExploratoria).count() == 0
            assert db.get(models.Informe, informe.id) is None
    finally:
        engine.dispose()
        deregister(JSONB)


def test_un_informe_con_sello_emitido_no_se_borra():
    import pytest
    from fastapi import HTTPException

    class _Q:
        def __init__(self, resultado):
            self.resultado = resultado

        def filter(self, *a):
            return self

        def first(self):
            return self.resultado

    class _DB:
        def get(self, modelo, ident):
            return models.Informe(id=ident, usuario_id=1)

        def query(self, modelo):
            return _Q(object())  # hay una evaluación con sello

    admin = models.Usuario(id=1, email="a@t", nombre="A", password_hash="x", rol="admin")
    with pytest.raises(HTTPException) as err:
        borrar_informe(5, _DB(), admin)
    assert err.value.status_code == 409
