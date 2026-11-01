"""La franja «Uso registrado» se calcula en vivo, sin la cuenta admin, con respaldo."""
import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from services import uso_publico


def test_calcula_conteos_sin_la_cuenta_admin_y_en_hora_argentina():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    try:
        models.Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([models.Usuario(id=1, email="a@t", nombre="A", password_hash="x", rol="admin"),
                        models.Usuario(id=2, email="b@t", nombre="B", password_hash="x", rol="analista"),
                        models.Area(id=1, nombre="Area", codigo="A")])
            db.flush()
            # 01:30 UTC del 29/09 es el 28/09 a las 22:30 en Argentina.
            tarde = dt.datetime(2026, 9, 29, 1, 30)
            for usuario, cuando in ((1, tarde), (2, dt.datetime(2026, 8, 25, 15, 0)), (2, tarde)):
                db.add(models.Informe(area_id=1, usuario_id=usuario, periodo="2026", dominio="general",
                                      datos=[], saneamiento={}, creado_en=cuando))
            db.commit()
            uso = uso_publico.calcular(db)
    finally:
        engine.dispose()
        deregister(JSONB)
    assert uso["informes"] == 2 and uso["participantes"] == 1 and uso["informes_sin_senales"] == 0 and uso["informes_con_devolucion"] == 0
    assert uso["desde"] == "25/08/2026" and uso["hasta"] == "28/09/2026"


def test_si_la_base_falla_muestra_la_ultima_foto(monkeypatch):
    monkeypatch.setitem(uso_publico._cache, "valor", None)
    monkeypatch.setattr(uso_publico, "calcular", lambda db: (_ for _ in ()).throw(RuntimeError("sin base")))
    assert uso_publico.vigente(respaldo={"informes": 7}) == {"informes": 7}


def test_la_presentacion_no_deja_marcadores_sin_reemplazar(monkeypatch):
    from main import app
    monkeypatch.setattr(uso_publico, "vigente", lambda respaldo=None: {
        "informes": 109, "informes_con_devolucion": 100, "participantes": 38, "observaciones": 454, "informes_sin_senales": 35,
        "proyectos": 50, "proyectos_entregados": 30, "desde": "25/08/2026", "hasta": "28/09/2026", "fecha": "28/09/2026"})
    html = TestClient(app).get("/presentacion").text
    assert "__USO_" not in html
    assert "<strong>109</strong><span>informes cargados por 38 participantes; 100 terminaron con devolución</span>" in html
    assert "Actividad formativa con agentes" not in html  # la nota se retiró de la portada (04/10/2026)


def test_la_base_caida_no_se_consulta_en_cada_visita(monkeypatch):
    llamadas = []
    monkeypatch.setitem(uso_publico._cache, "valor", None)
    monkeypatch.setitem(uso_publico._cache, "hasta", 0.0)

    def falla(db):
        llamadas.append(1)
        raise RuntimeError("sin base")
    monkeypatch.setattr(uso_publico, "calcular", falla)
    for _ in range(3):
        assert uso_publico.vigente(respaldo={"informes": 7}) == {"informes": 7}
    assert len(llamadas) == 1
