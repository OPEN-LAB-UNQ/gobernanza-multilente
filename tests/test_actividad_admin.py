from __future__ import annotations

import inspect

from fastapi.params import Depends

from core.auth import require_admin
from routers.sistema import actividad_admin


def test_actividad_exige_admin():
    depend = inspect.signature(actividad_admin).parameters["_admin"].default
    assert isinstance(depend, Depends)
    assert depend.dependency == require_admin
