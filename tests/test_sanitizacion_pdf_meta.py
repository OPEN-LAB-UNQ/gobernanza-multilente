from services import sanitizacion


def test_metadatos_pdf_no_se_clasifican_como_datos_personales():
    datos = [{"paginas_documento": 7, "pagina_pdf": 4, "Porcentaje": "58,2"}]

    saneados, reporte = sanitizacion.sanear(datos)

    assert reporte["columnas_excluidas"] == []
    assert saneados[0]["paginas_documento"] == 7
