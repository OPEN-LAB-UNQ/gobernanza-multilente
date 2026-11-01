from services.carga_archivos import _filas_tabla_pdf


def test_tabla_pdf_admite_filas_con_primera_celda_vacia():
    tabla = [
        ["", "Período", "Porcentaje"],
        ["2026", "Enero", "55,0"],
        ["", "Febrero", "58,6"],
    ]

    filas = _filas_tabla_pdf(tabla, pagina=4, tabla_idx=1, filename="informe.pdf")

    assert len(filas) == 2
    assert filas[1]["Período"] == "Febrero"
    assert filas[1]["Porcentaje"] == "58,6"
