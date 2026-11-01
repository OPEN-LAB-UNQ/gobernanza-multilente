"""robots.txt y sitemap.xml son públicos y solo exponen la presentación y la ficha."""
from fastapi.testclient import TestClient

from main import app


def test_robots_y_sitemap_publicos():
    c = TestClient(app)
    r = c.get("/robots.txt", follow_redirects=False)
    assert r.status_code == 200 and "Allow: /presentacion" in r.text and "Disallow: /" in r.text
    s = c.get("/sitemap.xml", follow_redirects=False)
    assert s.status_code == 200 and "/detalle</loc>" in s.text and "/presentacion</loc>" in s.text
    assert "/login" not in s.text
