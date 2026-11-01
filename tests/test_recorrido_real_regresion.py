"""Regresiones del recorrido público: categorías, agregados y lectura parcial."""
from services.lentes import rizoma


def unlp():
    return [dict(categoria=c, Especializacion=e, Maestria=m)
            for c, e, m in [("A", 16, 19), ("B", 36, 16), ("C", 19, 11),
                            ("No corresponde", 54, 22), ("Sin categoría", 3, 6),
                            ("Suma total", 128, 74)]]


def test_unlp_total_no_es_observacion():
    resultados = rizoma.evaluar_relaciones(unlp())
    assert len(resultados) == 1
    assert resultados[0]["n_observaciones"] == 5
    assert resultados[0]["coeficiente_pearson"] == 0.7946
    assert rizoma.analizar(unlp()) == []


def test_categorias_no_generan_diferencias_ni_recomendaciones_temporales():
    datos = [dict(categoria=f"grupo {i}", temperatura=i * 3, visitantes=i * 8) for i in range(7)]
    h = rizoma.analizar(datos)[0]
    assert h["evidencia"]["correlacion_primeras_diferencias"] is None
    assert h["evidencia"]["n_primeras_diferencias"] == 0
    assert not any(palabra in str(h).lower() for palabra in ("estacionalidad", "mismos meses", "ampliar el número de períodos"))


def test_confirmacion_ninguno_prevalece_sobre_nombre_periodo():
    datos = [dict(periodo=f"2024-{i:02d}", temperatura=i * 3, visitantes=i * 8) for i in range(1, 8)]
    h = rizoma.analizar(datos, interpretacion={"eje": "ninguno", "roles": {"periodo": "categoria"}})[0]
    assert h["evidencia"]["n_primeras_diferencias"] == 0


def test_serie_real_conserva_diferencias_y_ordena_periodos():
    datos = [dict(periodo=f"2024-{i:02d}", temperatura=i * 3, visitantes=i * 8) for i in range(1, 8)]
    h = rizoma.analizar(list(reversed(datos)))[0]
    assert h["evidencia"]["n_primeras_diferencias"] == 6
    assert h["evidencia"]["periodo_desde"] == "2024-01"


def test_periodos_duplicados_no_se_diferencian_como_serie_unica():
    datos = [dict(periodo="2024-01", temperatura=i * 3, visitantes=i * 8) for i in range(7)]
    assert rizoma.analizar(datos)[0]["evidencia"]["n_primeras_diferencias"] == 0


def test_texto_libre_no_excluye_una_observacion():
    datos = [dict(categoria=f"grupo {i}", nota="Total de encuestados verificado", temperatura=i * 3, visitantes=i * 8) for i in range(7)]
    assert rizoma.analizar(datos)[0]["evidencia"]["n_observaciones"] == 7


def test_importe_estadistico_no_afirma_imposibilidad_del_signo():
    from services.lentes import ajedrecista
    datos = [{"periodo": f"2024-{i:02d}", "Total Sector Bancario": -i * 20} for i in range(1, 8)]
    regla = "valor_negativo_en_magnitud_no_negativa"
    hs = ajedrecista.imposibilidad(datos, presupuestario=False, importes_estadisticos={"Total Sector Bancario"})
    assert not any(h["evidencia"].get("regla") == regla for h in hs)
    # El mismo signo en una magnitud presupuestaria continúa detectándose.
    assert any(h["evidencia"].get("regla") == regla for h in ajedrecista.imposibilidad(datos))


def test_lectura_parcial_no_se_presenta_como_no_ejecutada():
    from types import SimpleNamespace

    from services.reportes.registro import construir
    mapa = {"hojas": [{"hoja": "Datos", "mapas": {"gpt": {}, "gemini": {}, "deepseek": {"error": "timeout"}}}]}
    informe = SimpleNamespace(datos=[], saneamiento={"mapa_lectura": mapa}, hallazgos=[], devolucion=None, periodo="2026-10")
    control = next(c for c in construir(informe)["controles"] if c["control"] == "lector_cuadro")
    assert control["estado"] == "ejecutado"
    assert "parcial" in control["motivo"]
    mapa["hojas"][0]["mapas"] = {"gpt": {"error": "timeout"}}
    control = next(c for c in construir(informe)["controles"] if c["control"] == "lector_cuadro")
    assert control["estado"] == "no_ejecutado"


def test_ia_no_publica_evolucion_temporal_de_categorias():
    from services.triangulacion_validacion import validar_lectura
    contenido = {"lectura": "Se observa una fuerte co-evolución temporal entre categorías."}
    contexto = {"interpretacion_confirmada": [{"eje": "ninguno"}]}
    assert validar_lectura(contenido, [], [], 0, contexto)["estado"] == "descartada"
    contexto["interpretacion_confirmada"][0]["eje"] = "serie_filas"
    assert validar_lectura(contenido, [], [], 0, contexto)["estado"] == "incorporada"


def test_periodo_mixto_conserva_ambas_frecuencias():
    from services.reportes.markdown import _periodo_observado
    datos = [{"Periodo": p, "valor": 10} for p in ["1992", "1993", "1994", "I-94", "II-94", "III-94"]]
    periodo = _periodo_observado(datos)
    assert "1992" in periodo and "1994-T3" in periodo
    # ministerio guarda años numéricos y trimestres como texto en la misma columna.
    datos = [{"FECHA": p, "valor": 10} for p in [1992, 1993.0, 1994, "I-94", "II-94", "III-94"]]
    periodo = _periodo_observado(datos)
    assert "1992" in periodo and "1994-T3" in periodo


def test_ia_respeta_eje_de_la_senal_en_un_libro_mixto():
    from services.triangulacion_validacion import validar_lectura
    contenido = {"lectura": "El hallazgo 0 muestra evolución temporal."}
    items = [{"idx": 0, "evidencia": {"eje_temporal_verificado": False}}]
    contexto = {"interpretacion_confirmada": [{"eje": "serie_filas"}, {"eje": "ninguno"}]}
    assert validar_lectura(contenido, items, [0], 1, contexto)["estado"] == "descartada"


def test_plan_ninguno_no_activa_cronista_por_rol_residual():
    from services.interpretacion_previa import plan
    assert not plan({"tipo": "estadistica", "eje": "ninguno", "roles": {"Año": "periodo_serie"}})["cronista"]


def test_conciliador_no_reintroduce_negativos_estadisticos_como_reversas():
    from services.lentes import conciliador
    datos = [{"periodo": f"2024-{i:02d}", "Utilidades y Dividendos Pagados": -i,
              "Exportaciones": i*10, "Importaciones": i*8} for i in range(1,8)]
    # Reproduce la segunda vía de falsa alerta encontrada al ejecutar ministerio.
    assert conciliador.analizar(datos)["hallazgo_general"] is not None
    interpretacion = {"tipo": "estadistica", "eje": "serie_filas", "roles": {"Utilidades y Dividendos Pagados": "importe"}}
    assert conciliador.analizar(datos, interpretacion=interpretacion)["hallazgo_general"] is None
    presupuesto = [{"periodo": f"2024-{i:02d}", "credito_vigente": 0, "devengado": 100, "pagado": 80} for i in range(1,8)]
    assert conciliador.analizar(presupuesto, interpretacion={"tipo":"presupuesto","eje":"serie_filas"})["hallazgo_general"] is not None


def test_detalle_recupera_estado_ia_del_manifiesto_sin_inventar_fallo():
    from types import SimpleNamespace

    from services.analisis import modelos_consultados_publicos
    item = SimpleNamespace(modelo="gpt", contenido={"hallazgos_exploratorios": []}, error=None)
    manifiesto = {"modelos": [{"proveedor": "gpt", "estado_tareas": {"lectura_senales": {"estado": "no_solicitada"}}}]}
    assert modelos_consultados_publicos([item], manifiesto=manifiesto)[0]["estado"] == "solo_exploracion"
    from services.reporte_ejecutivo import _linea_ia
    assert "no había señales" in _linea_ia({"manifiesto": manifiesto})
    from services.reportes.markdown import _estado_modelo_reporte
    assert "sin señales para interpretar" in _estado_modelo_reporte(item, manifiesto)
    manifiesto["modelos"][0]["estado_tareas"]["lectura_senales"]["estado"] = "fallida"
    assert modelos_consultados_publicos([item], manifiesto=manifiesto)[0]["estado"] == "sin_respuesta"
    assert "no disponible" in _linea_ia({"manifiesto": manifiesto})
