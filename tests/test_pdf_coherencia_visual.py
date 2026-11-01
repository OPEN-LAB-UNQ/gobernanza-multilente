from services import pdf_controles


def _filas_pdf():
    return [
        {
            "Período": "Julio",
            "Porcentaje": "58,4",
            "archivo_origen": "capacidad.pdf",
            "pagina_pdf": 4,
            "tabla_pdf": 2,
            "fila_tabla_pdf": 7,
            "extraccion_pdf": "tabla",
        },
        {
            "Período": "Julio",
            "Porcentaje": "58,2",
            "archivo_origen": "capacidad.pdf",
            "pagina_pdf": 4,
            "tabla_pdf": 2,
            "fila_tabla_pdf": 19,
            "extraccion_pdf": "tabla",
        },
    ]


def test_detecta_diferencia_entre_texto_visual_y_tabla(monkeypatch):
    monkeypatch.setattr(
        pdf_controles,
        "_ocr_pagina_pdf",
        lambda contenido, pagina: (
            "En julio de 2026, la utilización se ubica en 68,2% nivel inferior "
            "al del mismo mes de 2025, que fue de 68,4%"
        ),
    )

    hallazgos = pdf_controles.analizar_coherencia_visual(
        [("capacidad.pdf", b"pdf")],
        _filas_pdf(),
    )

    assert len(hallazgos) == 1
    assert hallazgos[0]["evidencia"]["regla"] == "texto_destacado_no_coincide_con_tabla"
    assert hallazgos[0]["evidencia"]["valor_actual_texto"] == 68.2
    assert hallazgos[0]["evidencia"]["valor_actual_tabla"] == 58.2
    assert hallazgos[0]["modo"] == "coherencia_interna_pdf"
    assert "cuál es el valor correcto" in hallazgos[0]["pregunta_institucional"]
    assert "68,2 %" in hallazgos[0]["pregunta_institucional"]
    assert hallazgos[0]["evidencia"]["fila_detalle"].startswith("registro de julio de 2026")


def test_no_alerta_si_texto_visual_y_tabla_coinciden(monkeypatch):
    monkeypatch.setattr(
        pdf_controles,
        "_ocr_pagina_pdf",
        lambda contenido, pagina: (
            "En julio de 2026, la utilización se ubica en 58,2% nivel inferior "
            "al del mismo mes de 2025, que fue de 58,4%"
        ),
    )

    assert pdf_controles.analizar_coherencia_visual(
        [("capacidad.pdf", b"pdf")],
        _filas_pdf(),
    ) == []
