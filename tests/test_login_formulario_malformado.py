"""Un formulario multipart roto en /login responde 400, no 500 (escáneres automáticos)."""
from fastapi.testclient import TestClient

from main import app


def test_login_multipart_malformado_responde_400():
    cliente = TestClient(app, raise_server_exceptions=False)
    cuerpo = b"--xyzQ\r\nContent-Disposition: form-data; name=\"email\"\r\n\r\na@b.c\r\n--xyz--\r\n"
    res = cliente.post("/login", content=cuerpo,
                       headers={"Content-Type": "multipart/form-data; boundary=xyz"})
    assert res.status_code == 400
