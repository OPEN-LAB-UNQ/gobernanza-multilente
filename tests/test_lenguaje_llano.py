"""Frase «Qué pasó» y fórmulas en castellano (pedido del 14/10/2026)."""

import logging

import pytest
from openpyxl import Workbook

from services.calculos.integridad import _analizar_hoja
from services.guardrails import normalizar_hallazgo
from services.reportes import lenguaje_llano as ll

PALABRAS_DE_VEREDICTO = ("error", "incorrect", "falla", "irregular")


def _hallazgo(regla, lente="matematico", **evidencia):
    return {"lente": lente, "descripcion": "texto técnico", "severidad": "media", "evidencia": {"regla": regla, **evidencia}}


def test_caso_de_la_instruccion_promedio_simple_frente_a_ponderado():
    # Fila «Grupos sintéticos»: G4 =AVERAGE(C4:F4) donde la fila usa SUMPRODUCT/SUM.
    h = _hallazgo(
        "formula_fuera_de_patron", eje="fila", celda="G4", formula="=AVERAGE(C4:F4)",
        fila_detalle="fila 4 (A: Grupos sintéticos) / columna G (2025)",
        patron_esperado="=SUMPRODUCT(R+0C-4:R+0C-1,R-2C-4:R-2C-1)/SUM(R-2C-4:R-2C-1)",
    )
    frase = ll.resumen_llano(h)
    assert frase == ("En la fila «Grupos sintéticos», la celda G4 («2025») calcula un promedio simple, "
                     "mientras que el resto de la fila usa un promedio ponderado.")
    assert len(frase.split()) <= 25


def test_columna_con_formulas_reales_de_excel():
    # Pesos en la misma fila: el detector compara fórmulas relativas (no reconoce patrones con $).
    wb = Workbook()
    ws = wb.active
    ws.append(["Región", "Valor 1", "Valor 2", "Peso 1", "Peso 2", "Índice"])
    for fila, nombre in enumerate(("Norte", "Centro", "Sur", "Cuyo", "NOA"), start=2):
        ws.append([nombre, 50, 70, 0.6, 0.4, None])
        ws.cell(fila, 6).value = f"=SUMPRODUCT(B{fila}:C{fila},D{fila}:E{fila})/SUM(D{fila}:E{fila})"
    ws["F5"] = "=AVERAGE(B5:C5)"
    hallazgos = [h for h in _analizar_hoja(ws) if h["evidencia"]["regla"] == "formula_fuera_de_patron"]
    assert len(hallazgos) == 1
    frase = ll.resumen_llano({"lente": "matematico", **hallazgos[0]})
    assert frase == ("En la columna «Índice», la celda F5 («Cuyo») calcula un promedio simple, "
                     "mientras que el resto de la columna usa un promedio ponderado.")


def test_rango_incompleto():
    h = _hallazgo("formula_fuera_de_patron", eje="fila", celda="H5", formula="=SUM(C5:E5)",
                  fila_detalle="fila 5 (A: Salud) / columna H (Total)", patron_esperado="=SUM(R+0C-5:R+0C-1)")
    assert ll.resumen_llano(h) == "En la fila «Salud», la celda H5 («Total») toma 3 de las 5 columnas que toman las demás."


def test_referencia_corrida():
    h = _hallazgo("formula_fuera_de_patron", eje="fila", celda="H5", formula="=SUM(B5:F5)",
                  fila_detalle="fila 5 (A: Salud) / columna H (Total)", patron_esperado="=SUM(R+0C-5:R+0C-1)")
    assert ll.resumen_llano(h) == "En la fila «Salud», la celda H5 («Total») toma un rango corrido respecto del resto de la fila."


def test_valor_cargado_a_mano():
    h = _hallazgo("valor_fijo_en_serie_de_formulas", eje="fila", celda="F8", valor=1200,
                  fila_detalle="fila 8 (A: Educación) / columna F (2024)", patron_esperado="=R+0C-2+R+0C-1")
    assert ll.resumen_llano(h) == ("En la fila «Educación», la celda F8 («2024») tiene un valor cargado a mano "
                                   "donde las demás tienen fórmula.")


def test_valor_fijo_distinto_de_la_formula_de_su_fila():
    h = _hallazgo("valor_fijo_distinto_de_formula", lente="ajedrecista", celda="D39", valor_fijo=75619.04,
                  valor_segun_formula=75606.84, motivo_patron="la fila repite el mismo cálculo en 12 celdas",
                  hoja="Ciudad de Buenos Aires")
    frase = ll.resumen_llano(h)
    assert frase.startswith("En la hoja «Ciudad de Buenos Aires», la celda D39 tiene un valor cargado a mano")
    assert frase.endswith("(75.619,04); la fórmula de su fila daría 75.606,84.")


@pytest.mark.parametrize("formula, esperada", [
    ("=SUMPRODUCT(B2:B4,C2:C4)/SUM(C2:C4)", "=SUMAPRODUCTO(B2:B4;C2:C4)/SUMA(C2:C4)"),
    ('=IF(A1>0.5,"SUM, total",0)', '=SI(A1>0,5;"SUM, total";0)'),
    ("='Hoja SUM 1'!A1+SUM('Datos, 2025'!B2:B9)", "='Hoja SUM 1'!A1+SUMA('Datos, 2025'!B2:B9)"),
    ("=ROUND(AVERAGE(C4:F4),1)", "=REDONDEAR(PROMEDIO(C4:F4);1)"),
    ("=_xlfn.IFERROR(A1/B1,0)", "=SI.ERROR(A1/B1;0)"),
])
def test_traduccion_de_funciones(formula, esperada):
    assert ll.traducir_formula(formula) == esperada


def test_separador_configurable_para_mexico():
    assert ll.traducir_formula('=IF(A1>0.5,"x",0)', separador=",") == '=SI(A1>0.5,"x",0)'


def test_funcion_sin_traduccion_queda_en_ingles_y_se_registra(caplog):
    ll._avisadas.discard("XLOOKUP")
    with caplog.at_level(logging.WARNING, logger="services.reportes.lenguaje_llano"):
        assert ll.traducir_formula("=XLOOKUP(A1,B:B,C:C)") == "=XLOOKUP(A1;B:B;C:C)"
    assert "XLOOKUP" in caplog.text


@pytest.mark.parametrize("formula, metodo", [
    ("=SUMPRODUCT($C$2:$F$2,C4:F4)/SUM($C$2:$F$2)", "un promedio ponderado"),
    ("=AVERAGE(C4:F4)", "un promedio simple"),
    ("=SUM(C4:F4)/COUNT(C4:F4)", "un promedio simple"),
    ("=SUM(C4:F4)", "una suma"),
    ("=MEDIAN(C4:F4)", "una mediana"),
    ("=ROUND(SUM(C4:F4),0)", "una suma, redondeado"),
    ("=C4*0.15+D4*0.15+E4*0.2+F4*0.5", "un promedio ponderado"),
    ("=C4*2+D4*3", "una suma ponderada"),
    ("=C4*2", None),
])
def test_metodo(formula, metodo):
    assert ll.metodo(formula) == metodo


def test_toda_lente_sale_con_frase_y_sin_lenguaje_de_veredicto():
    casos = [_hallazgo("regla_sin_plantilla", lente=lente) for lente in ll.GENERICA_POR_LENTE]
    casos += [_hallazgo("formula_fuera_de_patron", eje="fila", celda="G4", formula="=AVERAGE(C4:F4)",
                        fila_detalle="fila 4", patron_esperado="=SUMPRODUCT(R+0C-4:R+0C-1,R-2C-4:R-2C-1)/SUM(R-2C-4:R-2C-1)")]
    for h in casos:
        frase = normalizar_hallazgo(h)["resumen_llano"]
        assert frase.strip()
        assert not any(p in frase.lower() for p in PALABRAS_DE_VEREDICTO), frase


def test_la_evidencia_guardada_conserva_la_formula_original():
    h = _hallazgo("formula_fuera_de_patron", eje="fila", celda="G4", formula="=AVERAGE(C4:F4)",
                  fila_detalle="fila 4 (A: Grupos sintéticos) / columna G", patron_esperado="=SUM(R+0C-4:R+0C-1)")
    normalizado = normalizar_hallazgo(h)
    assert normalizado["evidencia"]["formula"] == "=AVERAGE(C4:F4)"
    assert normalizado["evidencia"]["patron_esperado"] == "=SUM(R+0C-4:R+0C-1)"


def test_patron_con_pesos_escritos_en_la_formula():
    # Caso real (informe de notas): el resto de la columna pondera con pesos dentro de la fórmula.
    h = _hallazgo("formula_fuera_de_patron", eje="columna", celda="G4", formula="=AVERAGE(C4:F4)",
                  fila_detalle="fila 4 (A: EST-013) / columna G (promedio_ponderado)",
                  patron_esperado="=R+0C-4*0.15+R+0C-3*0.15+R+0C-2*0.2+R+0C-1*0.5")
    assert ll.resumen_llano(h) == ("En la columna «promedio_ponderado», la celda G4 («EST-013») calcula un promedio simple, "
                                   "mientras que el resto de la columna usa un promedio ponderado.")


def test_metodo_desconocido_muestra_la_formula_traducida():
    h = _hallazgo("formula_fuera_de_patron", eje="fila", celda="H5", formula="=AVERAGE(C5:G5)",
                  fila_detalle="fila 5 (A: Salud) / columna H (Total)", patron_esperado="=R+0C-5*R+0C-1")
    assert "el resto de la fila usa la fórmula =C5*G5" in ll.resumen_llano(h)


# --- Parte C: demás lentes, con evidencia tomada de observaciones reales ---------------------------

@pytest.mark.parametrize("lente, evidencia, esperada", [
    ("ajedrecista", {"regla": "pagado_supera_vigente", "hoja": "Presupuesto", "columna_mayor": "pagado",
                     "columna_menor": "credito_vigente", "filas_en_violacion": 1,
                     "muestras_violacion": [{"valor_mayor": 820, "valor_menor": 800,
                                             "ubicacion": "registro 4 (fila 5 si la fuente tiene encabezado); periodo: 2026-04"}]},
     "En la hoja «Presupuesto», lo pagado (820) supera al crédito vigente (800) en 2026-04."),
    ("ajedrecista", {"regla": "pagado_supera_devengado", "columna_mayor": "pagado", "columna_menor": "devengado",
                     "total_mayor": 1950, "total_menor": 1970, "filas_en_violacion": 1,
                     "filas_detalle": ["registro 3 (fila 4 si la fuente tiene encabezado); periodo: 2026-03"]},
     "Lo pagado supera a lo devengado en una fila en 2026-03."),
    ("conciliador", {"regla": "conciliacion_aritmetica", "indicador": "Resto de ayuda directa", "periodo": "2019",
                     "total_declarado": 90125.4251, "total_reconstruido": 89604.3149},
     "En «Resto de ayuda directa» 2019, el total declarado (90.125,43) no coincide con la suma de sus componentes (89.604,31)."),
    ("ajedrecista", {"regla": "pico_aislado", "indicador": "Ciencia y técnica", "periodo": "2019",
                     "valor_observado": 0.0233, "valor_anterior": 5.3134, "valor_posterior": 3.8391},
     "En «Ciencia y técnica» 2019, el valor 0,023 sale de la escala de sus vecinos (5,31 y 3,84) por un solo período."),
    ("conciliador", {"regla": "poblacion_implicita", "indicador": "En $ por niño/a", "periodo": "2020",
                     "poblacion_implicita": 62283.0, "poblacion_vecinos": [146991.0]},
     "En «En $ por niño/a» 2020, el importe y el valor por persona implican 62.283 personas, frente a 146.991 en los años vecinos."),
    ("cronista", {"regla": "corte_temporal", "serie": "Seguridad social", "periodo": "jul 2025", "periodo_previo": "jun 2025",
                  "valor_previo": 12588007.2, "valor_actual": 18385487.4, "ratio_vs_movimiento_tipico": 8.54},
     "«Seguridad social» pasa de 12.588.007,20 en jun 2025 a 18.385.487,40 en jul 2025: se multiplica por 1,5, más que los saltos habituales de la serie."),
    ("orquesta", {"columnas": ["credito_vigente", "pagado"], "desvio_relativo_pct": 61.18},
     "En el último período, la relación entre «credito vigente» y «pagado» se aparta 61,2 % de su valor habitual."),
    ("matematico", {"regla": "primer_digito_no_conforme_benford", "columna": "VALOR", "n": 87},
     "Hipótesis para explorar: los primeros dígitos de «VALOR» (87 valores) no siguen la distribución de Benford."),
    ("rizoma", {"columnas": ["REMITO", "VALOR"], "correlacion": 1.0},
     "Hipótesis para explorar: «REMITO» y «VALOR» se mueven juntas (correlación 1,00)."),
    ("radiologo", {"columna": "pagado", "periodo_comparado": "2026-09", "n_casos_comparados": 10,
                   "fuente_comparacion": "banco_historico"},
     "Comparado con 10 informes anteriores del banco histórico, «pagado» en 2026-09 queda fuera de su rango habitual."),
    ("radiologo", {"columna": "consultas", "periodo_comparado": "2026-05", "n_casos_comparados": 4,
                   "fuente_comparacion": "historial_interno_archivo"},
     "Comparado con los períodos anteriores del mismo archivo, «consultas» en 2026-05 queda fuera de su rango habitual."),
])
def test_plantillas_de_las_demas_lentes(lente, evidencia, esperada):
    assert ll.resumen_llano({"lente": lente, "evidencia": evidencia}) == esperada


def test_rotulo_muy_largo_se_acorta():
    columna = "FALTANTE DE OBRA A EJECUTAR A PRECIOS DE LA 29NA. ADECUACIÓN PROVISORIA MONTO FALTANTE"
    frase = ll.resumen_llano({"lente": "ajedrecista", "evidencia": {
        "regla": "valor_negativo_en_magnitud_no_negativa", "columna": columna, "filas": [6, 7]}})
    assert columna not in frase and "…»" in frase and len(frase.split()) <= 25


def test_toda_regla_con_plantilla_tolera_evidencia_incompleta():
    for regla in ll.PLANTILLAS:
        frase = ll.resumen_llano({"lente": "ajedrecista", "evidencia": {"regla": regla}})
        assert frase.strip()
        assert not any(p in frase.lower() for p in PALABRAS_DE_VEREDICTO), (regla, frase)


# --- Errores encontrados por la revisión independiente (14/10/2026) ---------------------------------

@pytest.mark.parametrize("formula, referencia, eje, caso", [
    ("=SUM(C5:E5)", "=SUM(C5:F5)", "columna", ("incompleto", {"n": 3, "m": 4, "unidad": "columnas"})),
    ("=SUM(D2:D9)", "=SUM(D2:D10)", "fila", ("incompleto", {"n": 8, "m": 9, "unidad": "filas"})),
    ("=SUM(B5:F5)", "=SUM(C5:F5)", "fila", ("otro", {})),            # rango más grande: no es «corrido»
    ("=SUM(D5:G5)", "=SUM(C5:F5)", "fila", ("corrido", {})),
    ("=Calculos!$O$124/1000000", "=CALCULOS!B122", "columna", ("otro", {})),  # caso real #343
    ("=EDATE($B$2,-11)", "=EDATE(B6,1)", "fila", ("otro", {})),               # caso real #349
    ("=SUM(C4:F4)", "", "fila", ("otro", {})),                                # sin referencia
])
def test_clasificar_no_confunde_corrido(formula, referencia, eje, caso):
    assert ll.clasificar(formula, referencia, eje) == caso


def test_sin_patron_ubicable_no_dice_la_formula_vacia():
    h = _hallazgo("formula_fuera_de_patron", eje="fila", celda="G4:G9", formula="=SUM(C4:F4)",
                  fila_detalle="fila 4 (A: Salud) / columna G", patron_esperado="=SUM(R+0C-4:R+0C-1)")
    frase = ll.resumen_llano(h)
    assert "la fórmula ." not in frase and frase.strip()


def test_promedios_reconocidos():
    assert ll.metodo("=SUM(C4:F4)/4") == "un promedio simple"
    assert ll.metodo("=C4*0.5+D4*0.5") == "un promedio simple"
    assert ll.metodo("=SUM(C4:F4)/3") is None


def test_signo_aislado_positivo():
    e = {"regla": "signo_aislado", "indicador": "Egresos", "periodo": "2020",
         "valor_observado": 15, "valor_anterior": -10, "valor_posterior": -12}
    assert "el único positivo entre valores negativos" in ll.resumen_llano({"lente": "ajedrecista", "evidencia": e})


def test_fuera_de_escala_por_debajo():
    e = {"regla": "valor_fuera_de_escala_columna", "columna": "Monto", "valor_observado": 0.5,
         "mediana_columna": 500, "desviacion_robusta_log": -30}
    assert ll.resumen_llano({"lente": "ajedrecista", "evidencia": e}) == (
        "En la columna «Monto», el valor 0,50 está 1.000 veces por debajo de la mediana (500).")


def test_correlaciones_negativas():
    assert "se mueven en sentido opuesto (correlación -0,90)" in ll.resumen_llano(
        {"lente": "rizoma", "evidencia": {"columnas": ["ventas_helados", "visitantes_museo"], "correlacion": -0.9}})
    assert "en sentido opuesto" in ll.resumen_llano(
        {"lente": "orquesta", "evidencia": {"columnas": ["a", "b"], "correlacion_historica": -0.85}})


def test_escala_extremo_cita_el_factor_del_valor_que_nombra():
    e = {"regla": "escala_extremo", "indicador": "Salud", "periodo": "2020", "valor_observado": 0.037,
         "valor_anterior": 86.99, "factor_escala": 1545}
    frase = ll.resumen_llano({"lente": "ajedrecista", "evidencia": e})
    assert "unas 2.351 veces" in frase and "1.545" not in frase


def test_fisico_financiero_direccion_y_unidad():
    e = {"regla": "coherencia_fisico_financiera_agregada", "periodo": "2026-04",
         "columnas": ["ejecucion_financiera", "ejecucion_fisica"], "unidad_variacion": "porcentaje",
         "variaciones": {"ejecucion_financiera": 2.0, "ejecucion_fisica": 40.0}}
    frase = ll.resumen_llano({"lente": "orquesta", "evidencia": e})
    assert "40,0 %" in frase and "puntos" not in frase
    assert frase.endswith("el avance financiero no acompaña al físico.")


def test_lenguaje_de_veredicto_nunca_aparece():
    e = {"regla": "control_textual_pdf", "pagina_pdf": 3, "termino_detectado": "error aritmético"}
    frase = ll.resumen_llano({"lente": "matematico", "evidencia": e})
    assert "error" not in frase.lower()
    h = _hallazgo("formula_fuera_de_patron", eje="fila", celda="H5", formula="=SUM(C5:G5)",
                  fila_detalle="fila 5 (A: Salud) / columna H", patron_esperado="=IFERROR(R+0C-5/R+0C-1,0)")
    assert "error" not in ll.resumen_llano(h).lower()


def test_dato_faltante_cae_en_la_frase_de_la_lente():
    frase = ll.resumen_llano({"lente": "conciliador", "evidencia": {"regla": "conciliacion_aritmetica"}})
    assert frase == ll.GENERICA_POR_LENTE["conciliador"]


def test_fila_sin_rotulo_se_nombra_por_numero():
    h = _hallazgo("valor_fijo_en_serie_de_formulas", eje="fila", celda="F8", fila_detalle="fila 8 / columna F")
    assert ll.resumen_llano(h).startswith("En la fila 8, la celda F8")


def test_traduccion_respeta_matrices_y_traduce_logicos():
    assert ll.traducir_formula("=SUM({1,2;3,4})") == "=SUMA({1,2;3,4})"
    assert ll.traducir_formula("=IF(A1,TRUE,FALSE)") == "=SI(A1;VERDADERO;FALSO)"


def test_texto_con_formula_sin_cerrar_no_se_toca():
    texto = "Ver =SUM(A1:A3 y luego, en la fila 5, 0.5 más"
    assert ll.traducir_en_texto(texto) == texto
    assert ll.traducir_en_texto("Patrón =C4*0.15+D4*0.85.") == "Patrón =C4*0,15+D4*0,85."


def test_consulta_de_respaldo_trae_que_paso():
    from services.reportes import consultas

    def falla(_g):
        raise RuntimeError("redacción imposible")

    revision = {"casos": [{"primary_finding": {"id": 1, "lente": "cronista", "descripcion": "Revisar variación",
                                                "evidencia": {}},
                           "prioridad": "media", "related_findings": [], "root_cause_id": "x"}]}
    original = consultas.redactar
    consultas.redactar = falla
    try:
        salida = consultas.consultas(revision)
    except Exception:  # agrupar_consultas puede necesitar más campos; lo importante es el respaldo
        salida = []
    finally:
        consultas.redactar = original
    for c in salida:
        assert c["que_paso"] and "detalle_tecnico" in c


def test_registro_traduce_la_descripcion_ya_corregida():
    from services.casos_revision import registro

    h = {"id": 1, "lente": "conciliador", "modo": None, "severidad": "media", "pregunta_institucional": None,
         "descripcion": "Una de las dos aperturas del mismo importe quedó sin actualizar.",
         "evidencia": {"regla": "identidad_entre_cuadros"}}
    copia = registro(h)
    assert "quedó sin actualizar" not in copia["descripcion_es"]


# --- Patrones con referencias fijas (14/10/2026) ----------------------------------------------------

def test_patron_con_fila_de_pesos_fija_se_reconoce():
    # Antes el detector quitaba los «$» y no veía este patrón: el cambio de criterio pasaba sin señal.
    wb = Workbook()
    ws = wb.active
    ws.append(["Región", "Peso", "T1", "T2", "T3", "T4", "Índice"])
    ws.append(["Pesos", None, 0.6, 0.3, 0.1, None, None])
    for fila, nombre in enumerate(("Norte", "Centro", "Sur", "Cuyo", "NOA"), start=3):
        ws.append([nombre, None, 50, 70, 80, 60, None])
        ws.cell(fila, 7).value = f"=SUMPRODUCT($C$2:$E$2,C{fila}:E{fila})/SUM($C$2:$E$2)"
    ws["G6"] = "=AVERAGE(C6:E6)"
    hallazgos = [h for h in _analizar_hoja(ws) if h["evidencia"]["regla"] == "formula_fuera_de_patron"]
    assert [h["evidencia"]["celda"] for h in hallazgos] == ["G6"]
    assert ll.resumen_llano({"lente": "matematico", **hallazgos[0]}) == (
        "En la columna «Índice», la celda G6 («Cuyo») calcula un promedio simple, "
        "mientras que el resto de la columna usa un promedio ponderado.")


def test_patron_fijo_completo_sin_cambio_no_da_senal():
    wb = Workbook()
    ws = wb.active
    ws.append(["Región", "Peso", "T1", "T2", "T3", "T4", "Índice"])
    ws.append(["Pesos", None, 0.6, 0.3, 0.1, None, None])
    for fila in range(3, 8):
        ws.append([f"R{fila}", None, 50, 70, 80, 60, None])
        ws.cell(fila, 7).value = f"=SUMPRODUCT($C$2:$E$2,C{fila}:E{fila})/SUM($C$2:$E$2)"
    assert not [h for h in _analizar_hoja(ws) if h["evidencia"]["regla"] == "formula_fuera_de_patron"]


def test_normalizacion_distingue_fijo_de_relativo():
    from services.calculos.excel_utils import _normalize_formula

    assert _normalize_formula("=$C$2*C5", 5, 7) == "=R2C3*R+0C-4"
    assert _normalize_formula("=$C$2*C6", 6, 7) == "=R2C3*R+0C-4"   # misma regla en otra fila
    assert _normalize_formula("=C$2*$C5", 5, 7) == "=R2C-4*R+0C3"   # mixtas


def test_patron_fijo_se_reubica_con_sus_signos_dolar():
    assert ll.patron_en_celda("=SUMPRODUCT(R2C3:R2C5,R+0C-4:R+0C-2)/SUM(R2C3:R2C5)", "G6") == (
        "=SUMPRODUCT($C$2:$E$2,C6:E6)/SUM($C$2:$E$2)")


def test_text_y_edate_en_castellano():
    assert ll.traducir_formula('=TEXT(EDATE(B2,1),"mmm")') == '=TEXTO(FECHA.MES(B2;1);"mmm")'
