import hashlib
import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from routers import ocr
from services import ocr_local

pytest_plugins = ["tests.test_ejemplos_zip"]


def imagen():
    im = Image.new("RGB", (1400, 650), "white")
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 36)
    for y, t in enumerate(
        [
            "Informe de ejecución presupuestaria",
            "Concepto          2024          2025",
            "Salud               1250          1500",
            "Total                1250          1500",
        ]
    ):
        d.text((40, 40 + y * 100), t, font=font, fill="black")
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def test_ocr_real_espanol_y_coordenadas():
    raw = imagen()
    r = ocr_local.extraer("prueba.png", raw)
    p = r["paginas"][0]
    assert r["sha256"] == hashlib.sha256(raw).hexdigest()
    assert r["estado"] == "pendiente_revision_humana" and not r["cobertura_parcial"]
    assert p["metodo"] == "ocr_local" and "Salud" in p["texto"] and "1250" in p["texto"]
    for linea in p["lineas"]:
        x, y, w, h = linea["caja"]
        assert 0 <= x < x + w <= p["ancho"] and 0 <= y < y + h <= p["alto"]


@pytest.mark.parametrize(
    "nombre,contenido", [("x.exe", b"x"), ("x.png", b""), ("x.jpg", b"x" * (ocr_local.MAX_BYTES + 1))]
)
def test_limites(nombre, contenido):
    with pytest.raises(ValueError):
        ocr_local.extraer(nombre, contenido)


def test_pdf_mixto_preserva_texto_y_lee_imagen():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(50, 760, "Documento digital: conservar este texto original sin volver a reconocerlo.")
    c.showPage()
    c.drawImage(ImageReader(io.BytesIO(imagen())), 30, 380, width=540, height=250)
    c.showPage()
    c.save()
    r = ocr_local.extraer("mixto.pdf", buf.getvalue())
    assert [p["metodo"] for p in r["paginas"]] == ["texto_pdf", "ocr_local"]
    assert "conservar este texto" in r["paginas"][0]["texto"] and "Salud" in r["paginas"][1]["texto"]


def test_pdf_limite_explicito():
    # Un PDF con texto entra completo hasta 10 páginas por lectura (y hasta 60 en el índice).
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i in range(6):
        c.drawString(50, 750, "Página digital con texto suficientemente extenso para leer sin OCR.")
        c.showPage()
    c.save()
    r = ocr_local.extraer("seis.pdf", b.getvalue())
    assert r["paginas_totales"] == 6 and r["paginas_incluidas"] == 6 and not r["cobertura_parcial"]


def test_pdf_escaneado_limite_ocr_explicito(monkeypatch):
    # Las páginas sin texto se leen con OCR hasta 5 por lectura; las demás quedan declaradas.
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i in range(6):
        c.showPage()
    c.save()
    monkeypatch.setattr(ocr_local, "reconocer", lambda imagen: [])
    r = ocr_local.extraer("escaneado.pdf", b.getvalue())
    assert r["paginas_incluidas"] == 6 and r["cobertura_parcial"]
    assert [p["estado"] for p in r["paginas"]][-1] == "no_leida" and "OCR" in r["paginas"][-1]["error"]
    assert all(p.get("metodo") == "ocr_local" for p in r["paginas"][:5])



def test_fallo_ocr_pdf_queda_explicito(monkeypatch):
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.showPage()
    c.save()

    def fallar(*a):
        raise ocr_local.OCRNoDisponible("Tiempo agotado")

    monkeypatch.setattr(ocr_local, "reconocer", fallar)
    r = ocr_local.extraer("blanco.pdf", b.getvalue())
    assert r["cobertura_parcial"] and r["paginas"][0]["estado"] == "no_leida"
    assert "Tiempo" in r["paginas"][0]["error"]


def test_concurrencia():
    assert ocr_local.LOCK.acquire(False)
    try:
        with pytest.raises(ocr_local.OCRNoDisponible):
            ocr_local.extraer("a.png", b"x")
    finally:
        ocr_local.LOCK.release()


def test_api_permisos_y_archivo_roto(flujo):
    client, _, actual = flujo
    client.app.include_router(ocr.router, prefix="/api")
    actual["id"] = 3
    assert client.get("/api/ocr").status_code == 403
    assert client.post("/api/ocr/leer", files={"archivo": ("x.png", b"x")}).status_code == 403
    actual["id"] = 1
    assert client.get("/api/ocr").status_code == 200
    assert client.post("/api/ocr/leer", files={"archivo": ("x.png", b"x")}).status_code == 422
    assert not ocr_local.LOCK._value == 0


def test_pdf_sin_paginas():
    from pypdf import PdfWriter

    out = io.BytesIO()
    PdfWriter().write(out)
    with pytest.raises(ValueError, match="páginas"):
        ocr_local.extraer("vacio.pdf", out.getvalue())
