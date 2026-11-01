"""Cobertura de los requisitos del protocolo B-1 multilente: siete anexos
autónomos por lente, "Para concluir se requiere", política de modelos
obligatoria y versionada, y bloqueo de emisión cuando no se cumple."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from core.auth import require_admin
from services import certificaciones
from services.lens_matrix import LENS_BY_ID, LENS_MATRIX


def _control(codigo, lente=None):
    return SimpleNamespace(codigo=codigo, nombre=codigo, lente=lente)


def _resultado(codigo, lente=None, estado="conforme", aplica=True, justificacion=None,
               evidencias=None, observacion=None, accion_requerida=None, reevaluado_en=None):
    return SimpleNamespace(
        control=_control(codigo, lente),
        estado=estado,
        aplica=aplica,
        justificacion_aplicabilidad=justificacion,
        evidencias=[SimpleNamespace(descripcion=f"evidencia {codigo}")] if evidencias is None else evidencias,
        observacion=observacion,
        accion_requerida=accion_requerida,
        reevaluado_en=reevaluado_en,
    )


def _evaluacion_b1_completa(**overrides):
    resultados = [
        _resultado("B1-04", "ajedrecista"),
        _resultado("B1-05", "cronista"),
        _resultado("B1-06", "matematico"),
        _resultado("B1-07", "orquesta"),
        _resultado("B1-08", "conciliador"),
    ]
    base = dict(
        protocolo=SimpleNamespace(
            codigo="B-1", version="1.0", nombre="Gobernanza Multilente B-1", tipo_objeto="informe",
            model_policy={},
        ),
        informe=SimpleNamespace(hallazgos=[]),
        resultados=resultados,
        manifiesto_modelos=[],
        hash_objeto="hash-actual",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_siete_anexos_autonomos_con_estructura_identica_y_preguntas_de_la_matriz():
    evaluacion = _evaluacion_b1_completa()
    anexos = certificaciones.anexos_lentes(evaluacion)
    assert len(anexos) == 7
    ids = {a["lente"] for a in anexos}
    assert ids == set(LENS_BY_ID)
    campos_esperados = {
        "lente", "nombre", "pregunta_central", "preguntas", "evidencia_minima",
        "controles_ejecutados", "evidencia_utilizada", "hallazgos", "informacion_faltante",
        "estado", "observaciones", "accion_requerida", "reevaluacion", "limites",
        "justificacion_no_aplicable",
    }
    for anexo in anexos:
        assert set(anexo) == campos_esperados
        # las preguntas nunca se hardcodean por fuera de LENS_MATRIX
        assert anexo["preguntas"] == LENS_BY_ID[anexo["lente"]]["preguntas"]
        assert anexo["pregunta_central"] == LENS_BY_ID[anexo["lente"]]["pregunta_central"]


def test_control_b1_07_alimenta_tres_anexos_independientes():
    evaluacion = _evaluacion_b1_completa()
    anexos = {a["lente"]: a for a in certificaciones.anexos_lentes(evaluacion)}
    for lente_id in ("orquesta", "radiologo", "rizoma"):
        assert "B1-07" in anexos[lente_id]["controles_ejecutados"]


def test_anexo_no_aplicable_siempre_trae_justificacion():
    resultados = [_resultado("B1-04", "ajedrecista", aplica=False, justificacion="No hay componentes numéricos.")]
    evaluacion = _evaluacion_b1_completa(resultados=resultados)
    anexo = next(a for a in certificaciones.anexos_lentes(evaluacion) if a["lente"] == "ajedrecista")
    assert anexo["estado"] == "no_aplicable"
    assert anexo["justificacion_no_aplicable"] == "No hay componentes numéricos."

    # aunque el revisor no haya cargado justificación, el anexo nunca queda
    # en None -- motivos_bloqueo() ya exige esa justificación para poder
    # sellar, pero el anexo igual debe ser legible por sí solo.
    resultados_sin_justificar = [_resultado("B1-04", "ajedrecista", aplica=False, justificacion=None)]
    evaluacion2 = _evaluacion_b1_completa(resultados=resultados_sin_justificar)
    anexo2 = next(a for a in certificaciones.anexos_lentes(evaluacion2) if a["lente"] == "ajedrecista")
    assert anexo2["justificacion_no_aplicable"] is not None


def test_para_concluir_no_duplica_y_omite_el_cambio_de_objeto():
    resultados = [
        _resultado("B1-04", "ajedrecista", estado="observado", accion_requerida="Explicar la excepción."),
        _resultado("B1-05", "cronista", estado="no_evaluable"),
    ]
    evaluacion = _evaluacion_b1_completa(resultados=resultados, hash_objeto="hash-viejo")
    items = certificaciones.resumen_para_concluir(evaluacion, "hash-viejo")
    assert len(items) == len(set(items))
    assert not any("objeto cambió" in item for item in items)
    assert any("B1-04" in item for item in items)
    assert any("B1-05" in item for item in items)

    # si además cambió el objeto, ese motivo integra motivos_bloqueo() pero no
    # "para concluir" -- cambiar el objeto no se resuelve completando datos,
    # exige iniciar una evaluación nueva.
    motivos = certificaciones.motivos_bloqueo(evaluacion, "hash-nuevo")
    assert any("objeto cambió" in m for m in motivos)


def test_politica_de_modelos_bloquea_emision_sin_contraste_suficiente():
    protocolo = SimpleNamespace(
        codigo="B-1", version="1.0", nombre="x", tipo_objeto="informe",
        model_policy={
            "aplica": True,
            "modelos_habilitados": ["gpt", "gemini"],
            "modelos_minimos_con_respuesta": 2,
            "controles_con_contraste_obligatorio": ["B1-06"],
        },
    )
    evaluacion = _evaluacion_b1_completa(
        protocolo=protocolo,
        resultados=[_resultado("B1-06", "matematico")],
        manifiesto_modelos=[{"modelo": "gpt", "respondio": True}],
    )
    motivos = certificaciones.motivos_bloqueo(evaluacion, evaluacion.hash_objeto)
    assert any("contraste" in m for m in motivos)


def test_politica_de_modelos_conforme_no_bloquea():
    protocolo = SimpleNamespace(
        codigo="B-1", version="1.0", nombre="x", tipo_objeto="informe",
        model_policy={
            "aplica": True,
            "modelos_habilitados": ["gpt", "gemini"],
            "modelos_minimos_con_respuesta": 2,
            "controles_con_contraste_obligatorio": ["B1-06"],
        },
    )
    evaluacion = _evaluacion_b1_completa(
        protocolo=protocolo,
        resultados=[_resultado("B1-06", "matematico")],
        manifiesto_modelos=[{"modelo": "gpt", "respondio": True}, {"modelo": "gemini", "respondio": True}],
    )
    motivos = certificaciones.motivos_bloqueo(evaluacion, evaluacion.hash_objeto)
    assert motivos == []


def test_modelo_fuera_de_politica_habilitada_se_reporta():
    protocolo = SimpleNamespace(model_policy={"aplica": True, "modelos_habilitados": ["gpt"], "modelos_minimos_con_respuesta": 0})
    motivos = certificaciones.motivos_incumplimiento_model_policy(
        protocolo, [{"modelo": "modelo_no_autorizado", "respondio": True}]
    )
    assert any("modelo_no_autorizado" in m for m in motivos)


def test_politica_que_no_aplica_no_genera_motivos():
    protocolo = SimpleNamespace(model_policy={"aplica": False, "motivo": "no corresponde"})
    assert certificaciones.motivos_incumplimiento_model_policy(protocolo, []) == []


def test_manifiesto_modelos_se_construye_desde_interpretaciones_reales():
    informe = SimpleNamespace(
        hallazgos=[SimpleNamespace(lente="matematico")],
        interpretaciones=[
            SimpleNamespace(modelo="gpt", error=None, creado_en=None),
            SimpleNamespace(modelo="gemini", error="timeout", creado_en=None),
        ],
    )
    manifiesto = certificaciones.construir_manifiesto_modelos(informe)
    assert {item["modelo"] for item in manifiesto} == {"gpt", "gemini"}
    gpt = next(item for item in manifiesto if item["modelo"] == "gpt")
    assert gpt["respondio"] is True
    assert gpt["proveedor"] == "OpenAI"
    assert "B1-06" in gpt["controles"]
    gemini = next(item for item in manifiesto if item["modelo"] == "gemini")
    assert gemini["respondio"] is False


def test_estado_visible_nunca_dice_aprobado_por_ia():
    assert certificaciones.estado_visible("lista_para_emision") == "Apto para instancia humana de decisión"
    for etiqueta in certificaciones.ESTADOS_VISIBLES.values():
        assert "aprobado por ia" not in etiqueta.lower()
        assert "ia dice" not in etiqueta.lower()


def test_emision_de_sello_exige_humano_administrador():
    """Ninguna IA puede emitir el sello por sí sola: el endpoint de emisión
    depende de require_admin, un usuario humano autenticado con rol admin."""
    import routers.certificaciones as rc

    sig = inspect.signature(rc.emitir_sello)
    assert sig.parameters["user"].default.dependency is require_admin


def test_r1_no_genera_anexos_por_lente():
    evaluacion = _evaluacion_b1_completa(
        protocolo=SimpleNamespace(codigo="R-1", version="1.0", nombre="x", tipo_objeto="proyecto_ia", model_policy={"aplica": False}),
    )
    assert certificaciones.anexos_lentes(evaluacion) == []


def test_las_siete_lentes_de_la_matriz_no_cambiaron():
    assert {item["id"] for item in LENS_MATRIX} == {
        "ajedrecista", "conciliador", "cronista", "orquesta", "radiologo", "rizoma", "matematico",
    }


def test_anexos_usan_snapshot_de_la_version_y_no_matriz_global():
    matriz = [dict(item) for item in LENS_MATRIX]
    matriz[0] = {**matriz[0], "pregunta_central": "Pregunta congelada de la versión"}
    evaluacion = _evaluacion_b1_completa()
    evaluacion.protocolo.matriz_lentes = matriz
    anexos = certificaciones.anexos_lentes(evaluacion)
    assert anexos[0]["pregunta_central"] == "Pregunta congelada de la versión"
