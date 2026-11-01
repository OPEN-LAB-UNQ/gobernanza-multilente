from __future__ import annotations

from types import SimpleNamespace

from services import certificaciones, sanitizacion


def _informe(**overrides):
    base = {
        "id": 8,
        "area_id": 2,
        "periodo": "2026-08",
        "dominio": "presupuesto",
        "modo": "intraarea",
        "datos": [{"programa": "A", "monto": 100}],
        "saneamiento": {},
        "hallazgos": [],
        "devolucion": SimpleNamespace(
            cobertura={
                "estado": "SIN_SENALES_COMUNICABLES",
                "lentes": [
                    {"lente": "ajedrecista", "hallazgos": 0},
                    {"lente": "cronista", "hallazgos": 0},
                    {"lente": "matematico", "hallazgos": 0},
                    {"lente": "orquesta", "hallazgos": 0},
                ],
            },
            decision=SimpleNamespace(tipo_decision="cerrar"),
        ),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _control(codigo, obligatorio=True):
    return SimpleNamespace(codigo=codigo, nombre=codigo, obligatorio=obligatorio)


def _resultado(estado="conforme", aplica=True, evidencias=None, obligatorio=True, justificacion=None):
    return SimpleNamespace(
        estado=estado,
        aplica=aplica,
        evidencias=[object()] if evidencias is None else evidencias,
        justificacion_aplicabilidad=justificacion,
        control=_control("X", obligatorio),
    )


def test_hash_del_objeto_es_estable_y_detecta_cambios():
    _, primero = certificaciones.snapshot_informe(_informe())
    _, segundo = certificaciones.snapshot_informe(_informe())
    _, cambiado = certificaciones.snapshot_informe(_informe(datos=[{"programa": "A", "monto": 101}]))
    assert primero == segundo
    assert primero != cambiado


def test_b1_no_confunde_ausencia_de_hallazgo_con_lente_no_ejecutada():
    informe = _informe()
    assert certificaciones.estado_inicial_b1(_control("B1-04"), informe) == "conforme"
    assert certificaciones.estado_inicial_b1(_control("B1-07"), informe) == "conforme"
    informe.devolucion.cobertura["lentes"] = []
    assert certificaciones.estado_inicial_b1(_control("B1-04"), informe) == "no_evaluable"


def test_hallazgo_de_una_lente_deja_control_observado():
    informe = _informe(hallazgos=[SimpleNamespace(id=4, lente="cronista", evidencia={"fila": 2})])
    assert certificaciones.estado_inicial_b1(_control("B1-05"), informe) == "observado"


def test_b1_v12_excluye_exploracion_sin_reinterpretar_v11():
    hipotesis = SimpleNamespace(id=999, lente="rizoma", evidencia={"naturaleza": "exploratoria"})
    informe = _informe(hallazgos=[hipotesis])
    informe.devolucion.cobertura["lentes"] = [{"lente": "rizoma", "ejecutado": True}]
    control = _control("B1-07")
    control.protocolo = SimpleNamespace(model_policy={})
    assert certificaciones.estado_inicial_b1(control, informe) == "observado"
    control.protocolo = SimpleNamespace(model_policy={"excluir_resultados_exploratorios": True})
    assert certificaciones.estado_inicial_b1(control, informe) == "no_evaluable"
    assert certificaciones.evidencia_inicial_b1(control, informe) is None
    informe.devolucion.cobertura["lentes"].append({"lente": "orquesta", "ejecutado": True})
    assert certificaciones.estado_inicial_b1(control, informe) == "conforme"
    assert "999" not in certificaciones.evidencia_inicial_b1(control, informe)["referencia"]
    hipotesis.lente = "matematico"  # Benford conserva la misma pared.
    assert certificaciones.hallazgos_institucionales(informe, control.protocolo) == []


def test_estado_lista_para_emision_exige_conformidad_y_evidencia():
    evaluacion = SimpleNamespace(resultados=[_resultado(), _resultado()])
    assert certificaciones.estado_evaluacion(evaluacion) == "lista_para_emision"
    evaluacion.resultados[0].evidencias = []
    assert certificaciones.estado_evaluacion(evaluacion) == "en_revision"
    evaluacion.resultados[0].estado = "observado"
    assert certificaciones.estado_evaluacion(evaluacion) == "con_observaciones"


def test_control_no_aplicable_requiere_justificacion():
    resultado = _resultado(aplica=False, obligatorio=False, justificacion=None)
    evaluacion = SimpleNamespace(resultados=[resultado])
    assert certificaciones.estado_evaluacion(evaluacion) == "en_revision"
    resultado.justificacion_aplicabilidad = "El archivo no contiene población numérica compatible."
    evaluacion.resultados.append(_resultado())
    assert certificaciones.estado_evaluacion(evaluacion) == "lista_para_emision"


def test_evaluacion_totalmente_no_aplicable_nunca_habilita_sello_vacio():
    resultados = [
        _resultado(aplica=False, justificacion="No aplica: proyecto descartado antes de esta etapa."),
        _resultado(aplica=False, justificacion="No corresponde usar IA para este caso."),
    ]
    evaluacion = SimpleNamespace(resultados=resultados)
    assert certificaciones.estado_evaluacion(evaluacion) == "en_revision"
    motivos = certificaciones.motivos_bloqueo(SimpleNamespace(hash_objeto="x", resultados=resultados), "x")
    assert any("constancia vacía" in motivo for motivo in motivos)


def test_control_obligatorio_no_aplicable_bloquea_aunque_este_justificado():
    resultado = _resultado(aplica=False, obligatorio=True, justificacion="Justificado")
    evaluacion = SimpleNamespace(hash_objeto="x", resultados=[resultado])
    motivos = certificaciones.motivos_bloqueo(evaluacion, "x")
    assert any("obligatorio" in motivo for motivo in motivos)


def test_evaluacion_sin_resultados_queda_en_revision():
    evaluacion = SimpleNamespace(resultados=[])
    assert certificaciones.estado_evaluacion(evaluacion) == "en_revision"


def test_r1_informacion_insuficiente_no_habilita_emision():
    evaluacion = SimpleNamespace(
        hash_objeto="x",
        resultados=[_resultado()],
        protocolo=SimpleNamespace(codigo="R-1", model_policy={}),
        conclusion_r1="informacion_insuficiente",
        manifiesto_modelos=[],
    )
    assert certificaciones.estado_evaluacion(evaluacion) == "en_revision"
    assert any("información es insuficiente" in motivo for motivo in certificaciones.motivos_bloqueo(evaluacion, "x"))


def test_emision_bloqueada_si_objeto_cambio_o_falta_evidencia():
    sin_evidencia = _resultado(evidencias=[])
    evaluacion = SimpleNamespace(hash_objeto="a", resultados=[sin_evidencia])
    motivos = certificaciones.motivos_bloqueo(evaluacion, "b")
    assert any("objeto cambió" in motivo for motivo in motivos)
    assert any("falta evidencia" in motivo for motivo in motivos)


def test_quien_reviso_en_soledad_no_puede_emitir_el_sello():
    resultado = _resultado()
    resultado.revisado_por_id = 7
    resultado.historial = [SimpleNamespace(modificado_por_id=7)]
    evaluacion = SimpleNamespace(resultados=[resultado])
    motivos = certificaciones.motivos_separacion_emisor(evaluacion, emisor_id=7)
    assert any("segundo responsable" in motivo for motivo in motivos)


def test_un_segundo_administrador_puede_emitir_el_sello():
    resultado = _resultado()
    resultado.revisado_por_id = 7
    resultado.historial = [SimpleNamespace(modificado_por_id=7)]
    evaluacion = SimpleNamespace(resultados=[resultado])
    assert certificaciones.motivos_separacion_emisor(evaluacion, emisor_id=9) == []


def test_redaccion_de_texto_libre_para_salida_publica():
    original = "CUIT 30-12345678-9, DNI 12345678 y persona@example.org"
    publicado = sanitizacion.redactar_texto_libre(original)
    assert "30-12345678-9" not in publicado
    assert "12345678" not in publicado
    assert "persona@example.org" not in publicado
    assert "REDACTADO" in publicado
