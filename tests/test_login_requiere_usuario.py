from __future__ import annotations

from core.auth import authenticate_user


class _DBNoDebeUsarse:
    def query(self, _model):
        raise AssertionError("no debe consultar usuarios si el email viene vacío")


def test_login_no_autentica_admin_con_usuario_vacio():
    assert authenticate_user(_DBNoDebeUsarse(), "", "clave-segura-123") is None
