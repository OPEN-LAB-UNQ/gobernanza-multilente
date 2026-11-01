"""Los pedidos que modifican datos sólo se aceptan desde la propia app (CSRF entre subdominios)."""
from config import settings
from core.auth import origen_confiable


def test_origen_propio_y_clientes_sin_navegador():
    assert origen_confiable({"origin": settings.public_base_url})
    assert origen_confiable({"origin": settings.public_base_url + "/"})
    assert origen_confiable({})  # tests y scripts del servidor
    assert origen_confiable({"origin": "http://127.0.0.1:6163"})
    assert origen_confiable({"sec-fetch-site": "same-origin"})


def test_otro_subdominio_u_otro_sitio_se_rechazan():
    assert not origen_confiable({"origin": "https://otro.entornodepruebas.com.ar"})
    assert not origen_confiable({"origin": "https://gobernanza.entornodepruebas.com.ar.evil.com"})
    assert not origen_confiable({"origin": "null"})
    assert not origen_confiable({"sec-fetch-site": "same-site"})
    assert not origen_confiable({"sec-fetch-site": "cross-site"})


def test_el_middleware_corta_antes_de_tocar_la_sesion():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.auth import require_password_middleware

    app = FastAPI()
    app.middleware("http")(require_password_middleware)

    @app.post("/api/algo")
    def algo():
        return {"ok": True}

    cliente = TestClient(app)
    r = cliente.post("/api/algo", headers={"Origin": "https://otro.entornodepruebas.com.ar"})
    assert r.status_code == 403 and r.json()["detail"] == "origen no permitido"
    assert cliente.post("/api/algo").status_code == 401  # sin Origin: sigue el control de sesión
