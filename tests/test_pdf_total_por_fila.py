"""El total que declara una fila de un cuadro de PDF tiene que cerrar con sus rubros."""

from services import pdf_controles

REGLA = "total_de_fila_no_cierra_pdf"


def _cuadro(totales):
    filas = []
    for indice, total in enumerate(totales, start=1):
        filas.append({
            "Nivel de gobierno": f"Fila {indice}",
            "Ayuda directa": 100 + indice,
            "Educación": 500 + indice,
            "Salud": 300 + indice,
            "Total General": total,
            "extraccion_pdf": "tabla_coordenadas",
            "pagina_pdf": 54,
            "tabla_pdf": 1,
            "fila_tabla_pdf": indice,
            "archivo_origen": "informe.pdf",
        })
    return filas


def _suma(indice):
    return (100 + indice) + (500 + indice) + (300 + indice)


def test_una_fila_que_no_cierra_se_senala_con_pagina_y_montos():
    totales = [_suma(i) for i in range(1, 7)]
    totales[3] = _suma(4) + 90  # una fila con 10 % de diferencia
    hallazgos = [h for h in pdf_controles._hallazgos_total_por_fila(_cuadro(totales)) if h["evidencia"]["regla"] == REGLA]
    assert len(hallazgos) == 1
    evidencia = hallazgos[0]["evidencia"]
    assert evidencia["pagina_pdf"] == 54 and evidencia["columna_total"] == "Total General"
    assert evidencia["filas_que_cierran"] == 5 and evidencia["filas_comparables"] == 6
    assert "página 54" in hallazgos[0]["descripcion"]


def test_un_cuadro_que_cierra_no_produce_observaciones():
    assert not pdf_controles._hallazgos_total_por_fila(_cuadro([_suma(i) for i in range(1, 7)]))


def test_las_diferencias_de_redondeo_no_se_senalan():
    totales = [_suma(i) for i in range(1, 7)]
    totales[2] = _suma(3) + 1  # 0,1 % sobre 900: redondeo
    assert not pdf_controles._hallazgos_total_por_fila(_cuadro(totales))


def test_si_la_igualdad_no_se_corrobora_no_se_afirma_nada():
    """Una columna llamada total que no es la suma de los rubros no habilita ninguna conclusión."""
    totales = [_suma(i) * 0.5 for i in range(1, 7)]
    assert not pdf_controles._hallazgos_total_por_fila(_cuadro(totales))


def test_no_se_aplica_a_filas_que_no_vienen_de_un_cuadro():
    filas = [dict(f, extraccion_pdf="texto_por_pagina") for f in _cuadro([1, 2, 3, 4, 5, 6])]
    assert not pdf_controles._hallazgos_total_por_fila(filas)


REGLA_CONSOLIDADO = "consolidado_no_cierra_pdf"


def _bloques(desvio_en=None):
    """Tres filas por año —Nación, Provincias, Total— con el año en la fila del medio."""
    filas = []
    indice = 0
    for anio in range(2016, 2022):
        nacion = {"Educación": 100.0 + anio, "Salud": 50.0}
        provincias = {"Educación": 900.0 + anio, "Salud": 250.0}
        total = {c: nacion[c] + provincias[c] for c in nacion}
        if desvio_en == anio:
            total["Educación"] += 120.0
        for etiqueta, valores, anio_celda in (
            ("Nación", nacion, ""), ("Provincias", provincias, str(anio)), ("Total", total, "")
        ):
            indice += 1
            filas.append({
                "Año": anio_celda, "Nivel de gobierno": etiqueta, **valores,
                "extraccion_pdf": "tabla_coordenadas", "pagina_pdf": 53, "tabla_pdf": 1,
                "fila_tabla_pdf": indice, "archivo_origen": "informe.pdf",
            })
    return filas


def test_nacion_mas_provincias_tiene_que_dar_el_total():
    hallazgos = [h for h in pdf_controles._hallazgos_consolidado_pdf(_bloques(desvio_en=2019))
                 if h["evidencia"]["regla"] == REGLA_CONSOLIDADO]
    assert len(hallazgos) == 1
    evidencia = hallazgos[0]["evidencia"]
    assert evidencia["periodo"] == "2019" and evidencia["columna"] == "Educación"
    assert evidencia["partes"] == ["Nación", "Provincias"] and evidencia["etiqueta_total"] == "Total"
    assert "página 53" in hallazgos[0]["descripcion"] and "en 2019" in hallazgos[0]["descripcion"]


def test_un_cuadro_consolidado_que_cierra_no_produce_observaciones():
    assert not pdf_controles._hallazgos_consolidado_pdf(_bloques())


def test_el_ano_se_toma_de_la_fila_del_medio_y_no_se_arrastra():
    """La celda combinada del año está centrada: el bloque no empieza donde aparece el año."""
    bloques = pdf_controles._bloques_pdf(_bloques(), "Nivel de gobierno", "Total", "Año")
    assert [anio for anio, _ in bloques] == [str(a) for a in range(2016, 2022)]
    assert all(set(bloque) == {"Nación", "Provincias", "Total"} for _, bloque in bloques)
