"""0.10.25: las cifras públicas dicen exactamente qué se midió."""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"


def test_cifras_publicas_dicen_que_se_midio():
    for nombre in ("presentacion.html", "detalle-body.html"):
        texto = (STATIC / nombre).read_text(encoding="utf-8")
        assert "planillas oficiales correctas salen" not in texto and "Las falsas alarmas bajaron" not in texto
        assert "copias de planillas oficiales con un error escondido" in texto and "más de 9 de cada 10" in texto
        assert "el motor actual marca los 8" in texto
        # 0.10.61: cifras de la medición del 28/10/2026 con multilente-0.10.59 (119 de 123; 169 altas; 88 sin ninguna).
        assert "lo señala en 119: más de 9 de cada 10" in texto and "sin alterar, 88 salen" in texto
        assert "lo señala en 115" not in texto and "lo señala en 113" not in texto
    # 0.10.42: la presentación muestra tres cifras; las finas (revisión del 22/10, 951 a 172) viven en la ficha.
    ficha = (STATIC / "detalle-body.html").read_text(encoding="utf-8")
    assert "la revisión del 22/10/2026 encontró 8 posibles errores" in ficha
    assert "no todas las que quedan son falsas alarmas" in ficha and "bajaron de 951 a 172" in ficha
    assert "Los 8 ejemplos con error de la aplicación se detectan por el recorrido completo" in ficha
    presentacion = (STATIC / "presentacion.html").read_text(encoding="utf-8")
    medido = presentacion.split('id="medido"', 1)[1].split("</section>", 1)[0]
    for cifra in ("<strong>119 de 123</strong>", "<strong>88 de 132</strong>", "<strong>8 de 8</strong>"):
        assert cifra in medido
    assert 'class="usage-note">No promete encontrarlo todo' in medido
    for nombre in ("presentacion.html", "detalle-body.html", "multilente-body.html"):
        assert "sin la lectura con IA" in (STATIC / nombre).read_text(encoding="utf-8")
        assert "motor multilente-0.10.59, sin la lectura con IA" in (STATIC / nombre).read_text(encoding="utf-8")


def test_ficha_cita_el_documento_vigente_y_se_lee_el_recuadro():
    ficha = (STATIC / "detalle-body.html").read_text(encoding="utf-8")
    assert "zenodo.23851688" in ficha and "zenodo.[versión anterior]" not in ficha and "zenodo.[versión anterior]" not in ficha and "zenodo.[versión anterior]" not in ficha and "zenodo.[versión anterior]" not in ficha and "Publicado en Zenodo el 1/11/2026" in ficha
    css = (STATIC / "presentacion.html").read_text(encoding="utf-8")
    assert "body .detail-hero p.detail-callout, body.page-detail .detail-hero p.detail-callout { margin-top: 18px; color: var(--ink); }" in css


def test_paginas_publicas_cuentan_las_dos_revisiones():
    """0.10.35: rápida (sin IA, por defecto) y profunda; las mediciones son de lo que corre en la rápida."""
    presentacion = (STATIC / "presentacion.html").read_text(encoding="utf-8")
    charla = (STATIC / "multilente-body.html").read_text(encoding="utf-8")
    ficha = (STATIC / "detalle-body.html").read_text(encoding="utf-8")
    for texto in (presentacion, charla, ficha):
        assert "Revisión rápida" in texto or "Dos revisiones" in texto
        assert 'id="dos-revisiones"' in texto
        assert "rayos X a todo" in texto
    # 0.10.42: en la presentación, la tercera tarjeta es «Qué sale del servidor»; el octavo ejemplo se explica en la ficha.
    assert "<h3>Qué sale del servidor</h3>" in presentacion
    assert "el octavo es una asociación exploratoria: sólo lo ve la profunda" in ficha
    assert "son del motor sin la lectura con IA, es decir, de lo que corre en la revisión rápida" in ficha
    assert "<tr><th>Asociaciones exploratorias (Rizoma)</th><td>No</td><td>Sí</td></tr>" in ficha
    # La etapa del lector liviano todavía no se publica: nada de libros grandes de un ministerio en estas páginas.
    for texto in (presentacion, charla, ficha):
        assert "lector liviano" not in texto and "Sirve para cualquier tamaño" not in texto


def test_la_interpretacion_orienta_y_no_apaga_las_cuentas():
    """0.10.39: desde 0.10.28 la interpretación con IA suma controles, no los selecciona; la rápida no la tiene."""
    for nombre in ("presentacion.html", "detalle-body.html", "multilente-body.html"):
        texto = (STATIC / nombre).read_text(encoding="utf-8")
        assert "selecciona los controles" not in texto and "selecciona las lentes" not in texto
        assert "orienta y suma" in texto
    for nombre in ("detalle-body.html", "multilente-body.html"):
        assert "en la revisión rápida no hay interpretación con ia" in (STATIC / nombre).read_text(encoding="utf-8").lower()
