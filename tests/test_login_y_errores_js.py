"""El login no anuncia el usuario administrador y errores.js carga en las tres páginas."""
from pathlib import Path

from fastapi.testclient import TestClient

from main import app

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_login_no_anuncia_usuario_administrador():
    html = TestClient(app).get("/login").text
    assert "administrador inicial" not in html


def test_errores_js_se_referencia_en_la_raiz_y_es_publico():
    for pagina in ("index.html", "probar.html", "ocr.html"):
        html = (STATIC / pagina).read_text(encoding="utf-8")
        assert "/static/errores.js" not in html and 'src="/errores.js' in html
    resp = TestClient(app).get("/errores.js", follow_redirects=False)
    assert resp.status_code == 200 and "javascript" in resp.headers["content-type"]


def test_ningun_html_carga_scripts_desde_static():
    """La carpeta static se sirve en la raíz: /static/... no existe y el script no carga."""
    for pagina in STATIC.glob("*.html"):
        assert 'src="/static/' not in pagina.read_text(encoding="utf-8"), pagina.name
