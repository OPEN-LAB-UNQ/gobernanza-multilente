"""El aviso de un análisis encolado sólo acepta una dirección con formato válido."""
import pytest
from fastapi import HTTPException

import models
from routers import jobs


@pytest.fixture(autouse=True)
def _sin_cuota(monkeypatch):
    # El tope diario se prueba en test_cuota_ia; acá solo interesa el correo de aviso.
    monkeypatch.setattr(jobs.cuota_ia, "verificar_encolado", lambda db, user, informe: None)


class _DB:
    def __init__(self, informe):
        self.informe = informe

    def get(self, modelo, ident):
        return self.informe


def test_encolar_rechaza_un_correo_invalido(monkeypatch):
    informe = models.Informe(id=5, usuario_id=7)
    user = models.Usuario(id=7, email="a@t.com", nombre="A", password_hash="x", rol="analista")
    monkeypatch.setattr(jobs.jobs_svc, "enqueue_analysis", lambda *a, **kw: pytest.fail("no debería encolar"))
    with pytest.raises(HTTPException) as err:
        jobs.encolar_informe(5, {"notify_email": "no es un correo\nBcc: x@y.z"}, user, _DB(informe))
    assert err.value.status_code == 422


def test_encolar_usa_el_correo_valido(monkeypatch):
    informe = models.Informe(id=5, usuario_id=7)
    user = models.Usuario(id=7, email="a@t.com", nombre="A", password_hash="x", rol="analista")
    visto = {}
    monkeypatch.setattr(jobs.jobs_svc, "enqueue_analysis", lambda *a, **kw: visto.update(kw) or {"id": 1})
    jobs.encolar_informe(5, {"notify_email": " Aviso@Ejemplo.com "}, user, _DB(informe))
    assert visto["notify_email"] == "aviso@ejemplo.com"
