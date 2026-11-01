"""0.10.17.1: un salto de página sobre una página ya vacía no agrega una hoja en blanco."""
import io

import pypdf

from services.reportes.markdown import render_reporte_pdf


def _paginas(md):
    return len(pypdf.PdfReader(io.BytesIO(render_reporte_pdf(md))).pages)


def test_salto_sobre_pagina_vacia_no_deja_hoja_en_blanco():
    md = "# Informe de revisión\n\nPrimera página.\n\n<!-- salto-pagina -->\n\n<!-- salto-pagina -->\n## Anexo técnico\n\nTexto.\n"
    assert _paginas(md) == 2


def test_espacios_al_final_de_una_pagina_llena_no_pasan_solos_a_la_siguiente():
    lleno = "\n".join(f"{n}. Consulta número {n} con texto suficiente para ocupar una línea completa del informe." for n in range(1, 60))
    md = f"# Informe de revisión\n\n{lleno}\n\n\n\n<!-- salto-pagina -->\n## Detalle\n\nTexto.\n"
    con = _paginas(md)
    sin_espacios = _paginas(md.replace("\n\n\n\n<!-- salto", "\n<!-- salto"))
    assert con == sin_espacios
