"""Ausencia de texto, transparencias y fallos parciales de un documento."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

from services import ocr_local


@pytest.mark.parametrize("formato", ["PNG", "JPEG"])
def test_imagen_vacia_no_se_declara_leida(formato):
    out = io.BytesIO()
    Image.new("RGB", (600, 300), "white").save(out, format=formato)
    r = ocr_local.extraer("blanco." + formato.lower(), out.getvalue())
    assert r["cobertura_parcial"] and r["paginas"][0]["estado"] == "sin_texto"
    assert r["paginas"][0]["imagen"]


def test_png_transparente_se_compone_sobre_blanco():
    im = Image.new("RGBA", (1000, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 40)
    draw.text((30, 40), "Salud 1250", font=font, fill=(0, 0, 0, 255))
    out = io.BytesIO()
    im.save(out, format="PNG")
    r = ocr_local.extraer("transparente.png", out.getvalue())
    assert "Salud" in r["paginas"][0]["texto"] and "1250" in r["paginas"][0]["texto"]


def test_texto_recortado_declara_limite():
    p = ocr_local._pagina(Image.new("RGB", (20, 20), "white"), 1, "A" * 30001)
    assert len(p["texto"]) == 30000
    assert p.get("texto_truncado") is True
    assert "recort" in p["advertencia"].lower()


def test_fallo_pagina_no_pierde_las_demas(monkeypatch):
    out = io.BytesIO()
    c = canvas.Canvas(out)
    for i in range(2):
        c.drawString(30, 700, "Texto suficientemente largo para conservar la lectura digital original.")
        c.showPage()
    c.save()
    real = ocr_local._pagina

    def intermitente(image, numero, *args):
        if numero == 1:
            raise RuntimeError("fallo simulado de renderizado")
        return real(image, numero, *args)

    monkeypatch.setattr(ocr_local, "_pagina", intermitente)
    r = ocr_local.extraer("dos.pdf", out.getvalue())
    assert r["cobertura_parcial"] and len(r["paginas"]) == 2
    assert r["paginas"][0]["estado"] == "no_leida"
    assert r["paginas"][1]["estado"] == "para_revisar"
    assert "simulado" not in r["paginas"][0]["error"]


@pytest.mark.parametrize("raw", [b"archivo roto", b"%PDF-1.7\nroto"])
def test_archivo_roto_libera_turno(raw):
    with pytest.raises(Exception):
        ocr_local.extraer("roto.pdf", raw)
    assert ocr_local.LOCK.acquire(False)
    ocr_local.LOCK.release()
