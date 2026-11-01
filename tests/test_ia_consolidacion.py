"""2. Consolidación por k de n modelos que efectivamente recibieron cada señal."""
from __future__ import annotations

from services import triangulacion
from tests.test_ia_datos_eval import HALLAZGOS_264, HALLAZGOS_265, LECTURAS_264, LECTURAS_265, interpretacion, lectura


def test_senal_mayoritaria_y_unanime_no_son_desacuerdo_265():
    its = [interpretacion(m, c) for m, c in LECTURAS_265.items() if m != "llama"]
    its.append(interpretacion("claude", lectura("La serie 'pendientes' sube de 52 a 88 entre enero y febrero de 2026 (idx 1).", [1])))
    c = triangulacion.consolidar(HALLAZGOS_265, its)
    coincidencia = next(x for x in c["coincidencias"] if x.startswith("Hallazgo #0"))
    assert "priorizado por 3 de 5" in coincidencia and "no lo priorizaron: renderix, claude" in coincidencia
    assert "Hallazgo #1: priorizado por 5 de 5" in " ".join(c["coincidencias"])
    assert not any(x.startswith("Hallazgo #1") for x in c["divergencias"])


def test_unanime_entre_quienes_la_recibieron_nunca_sale_como_desacuerdo_264():
    its = [interpretacion(m, c) for m, c in LECTURAS_264.items() if m != "llama"]
    c = triangulacion.consolidar(HALLAZGOS_264, its)
    assert any(x.startswith("Hallazgo #0: priorizado por 4 de 4") for x in c["coincidencias"])
    assert not any(x.startswith("Hallazgo #0") for x in c["divergencias"])


def test_no_recibirla_no_es_no_priorizarla():
    # renderix sólo recibió la señal 0 (presupuesto de prompt chico).
    its = [
        interpretacion("gpt", lectura("Revisar el dato 0.452 de 2021 (idx 0) y el salto de 2023 (idx 1).", [0, 1]), [0, 1]),
        interpretacion("gemini", lectura("El valor 0.452 de 2021 (idx 0) y la variación de 2023 (idx 1).", [0, 1]), [0, 1]),
        interpretacion("renderix", lectura("El valor 0.452 de 2021 en E11 (idx 0) se aparta de sus vecinos.", [0]), [0]),
    ]
    c = triangulacion.consolidar(HALLAZGOS_264, its)
    senal1 = next(s for s in c["senales"] if s["idx"] == 1)
    assert senal1["k"] == 2 and senal1["n"] == 2 and senal1["no_recibida_por"] == ["renderix"]
    assert senal1["no_priorizada_por"] == []
    texto = next(x for x in c["coincidencias"] if x.startswith("Hallazgo #1"))
    assert "2 de 2" in texto and "no lo recibió" in texto and "renderix" in texto


def test_minoria_si_es_divergencia_y_dice_quien_no_la_priorizo():
    its = [
        interpretacion("gpt", lectura("Revisar el dato 0.452 de 2021 (idx 0).", [0])),
        interpretacion("gemini", lectura("El valor 0.452 de 2021 (idx 0) y la variación de 2023 (idx 1).", [0, 1])),
        interpretacion("deepseek", lectura("El valor 0.452 de 2021 (idx 0).", [0])),
    ]
    c = triangulacion.consolidar(HALLAZGOS_264, its)
    div = next(x for x in c["divergencias"] if x.startswith("Hallazgo #1"))
    assert "1 de 3" in div and "no lo priorizaron: gpt, deepseek" in div


def test_salidas_sustitutas_y_fallidas_no_cuentan():
    sustituta = {"prioritarios": [], "lectura": "Exploración semántica independiente; consultar su alcance y evidencia comparativa.",
                 "explicaciones_alternativas": [], "confianza": "media", "hallazgos_exploratorios": []}
    its = [
        interpretacion("gpt", lectura("Revisar el dato 0.452 de 2021 (idx 0).", [0])),
        interpretacion("deepseek", sustituta),
        {"modelo": "gemini", "contenido": None, "error": "429 RESOURCE_EXHAUSTED"},
    ]
    c = triangulacion.consolidar(HALLAZGOS_264, its)
    assert [s["modelo"] for s in c["hallazgos_singulares"]] == ["gpt"]
    assert c["coincidencias"] == [] and c["divergencias"] == []
    assert c["priorizacion_sin_contraste"] and "1 de 1" in c["priorizacion_sin_contraste"][0]


def test_senal_priorizada_por_4_de_5_es_coincidencia_y_no_desacuerdo():
    its = [interpretacion(m, c) for m, c in LECTURAS_264.items() if m != "llama"]
    its.append(interpretacion("claude", lectura("La variación de 2023 (idx 1) requiere contexto de inflación.", [1])))
    c = triangulacion.consolidar(HALLAZGOS_264, its)
    assert any(x.startswith("Hallazgo #0: priorizado por 4 de 5") and "no lo priorizó: claude" in x for x in c["coincidencias"])
    assert not any(x.startswith("Hallazgo #0") for x in c["divergencias"])
