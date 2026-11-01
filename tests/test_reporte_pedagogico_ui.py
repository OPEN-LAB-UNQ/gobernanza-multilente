from __future__ import annotations

from pathlib import Path


def test_reporte_pedagogico_esta_en_actividad():
    html = Path("static/index.html").read_text(encoding="utf-8")
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "Reporte pedagógico" in html
    assert 'id="actividad-reporte-pedagogico"' in html
    assert "renderReportePedagogicoActividad(data)" in js
    assert "function renderReportePedagogicoActividad" in js
