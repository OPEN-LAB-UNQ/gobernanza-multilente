"""No se puede borrar un informe mientras se analiza (detuvo la cola el 08/10); en espera, sí."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import informes


class _Db:
    def __init__(self, informe):
        self.informe = informe

    def get(self, _modelo, _id):
        return self.informe


@pytest.mark.parametrize("estado", ["procesando"])
def test_borrar_en_analisis_responde_409(monkeypatch, estado):
    informe = SimpleNamespace(id=5, usuario_id=1, trabajos_analisis=[SimpleNamespace(estado=estado)])
    monkeypatch.setattr(informes, "_puede_borrar_informe", lambda u, i: True)
    with pytest.raises(HTTPException) as exc:
        informes.borrar_informe(5, db=_Db(informe), user=SimpleNamespace(rol="admin", id=1))
    assert exc.value.status_code == 409 and "analizando" in exc.value.detail
