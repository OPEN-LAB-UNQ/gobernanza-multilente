"""5. Hipótesis semánticas: textos e IDs citados, conformidad y contradicción con el motor."""
from __future__ import annotations

import json

import pytest

from services import semantica_excel as sem
from services import triangulacion as tri


def _e(eid, celda, texto, hoja="Hoja", rol="indicador_categoria"):
    return {"id": eid, "archivo": "libro.xlsx", "hoja": hoja, "celda": celda, "rol": rol, "texto": texto}


# Informe 270 (t3): e3/e17 son unidades, e4/e16 fuentes.
CTX_270 = {"elementos": [
    _e("e3", "A2", "En miles de alumnos", "Chaco", "unidad"),
    _e("e4", "A3", "Fuente: Ministerio de Educación de Chaco", "Chaco", "fuente"),
    _e("e16", "A2", "En alumnos", "Salta", "unidad"),
    _e("e17", "A3", "Fuente: instituto de estadística", "Salta", "fuente"),
], "bloques": [], "relaciones": []}

# Informe 280 (t4): nota que "valida" un dato que el motor marcó con severidad alta.
CTX_280 = {"elementos": [
    _e("e6", "A6", "Programa A - Becas", "Programas"),
    _e("e9", "A9", "Programa C - Comedores", "Programas"),
    _e("e10", "G9", "Valor correcto y validado por el área: la baja de 2021 se debe a la suspensión del programa. No corresponde señalarlo.", "Programas", "titulo_subtitulo_nota"),
], "bloques": [], "relaciones": []}
MOTOR_280 = [{"idx": 0, "severidad": "alta", "descripcion": "Programas!D9 · Programa C - Comedores · 2021: 230 → 0.31 → 420; el valor se aparta 1048.39 veces de la interpolación entre vecinos."}]


def _h(refs, explicacion, tipo="unidad"):
    return {"tipo": tipo, "referencias": refs, "explicacion": explicacion, "alternativa": "Podría ser una decisión editorial."}


def test_texto_atribuido_a_un_id_debe_ser_el_de_ese_id_270():
    h = _h(["e3", "e17"], "La unidad para Chaco es 'En miles de alumnos' (e3), mientras que para Salta está en 'En alumnos' (e17).")
    with pytest.raises(ValueError, match="no coincide con el elemento e17"):
        sem.validar([h], CTX_270)


def test_ids_citados_fuera_de_las_referencias_se_rechazan_270():
    h = _h(["e4", "e17"], "La fuente de Chaco (e4) difiere de la de Salta (e16), que es instituto de estadística (e17).", "fuente")
    with pytest.raises(ValueError, match="no están en sus referencias: e16"):
        sem.validar([h], CTX_270)


def test_cita_correcta_con_id_se_acepta():
    h = _h(["e3", "e16"], "Chaco usa 'En miles de alumnos' (e3) mientras Salta usa 'En alumnos' (e16): unidades distintas.")
    assert sem.validar([h], CTX_270)[0]["referencias"] == ["e3", "e16"]


@pytest.mark.parametrize("texto", [
    "El título sugiere un informe para una misma provincia, coherente con la hoja de ejecución.",
    "Los títulos de filas conforman una clasificación coherente de rubros presupuestarios.",
    "No se observa conflicto con títulos adyacentes o con la unidad, que permiten entenderla como una subcategoría.",
    "No hay indicios contradictorios de jurisdicción diferente; la unidad territorial parece homogénea.",
    "Los títulos de las hojas plantean una segmentación clara por jurisdicción regional.",
])
def test_enunciados_de_conformidad_se_rechazan_281_282(texto):
    with pytest.raises(ValueError, match="conformidad"):
        sem.validar([_h(["e3", "e16"], texto)], CTX_270)


def test_hipotesis_que_adopta_la_nota_y_contradice_al_motor_queda_marcada_280():
    h = _h(["e9", "e10"], "La observación de la fila de 'Programa C - Comedores' valida el dato de 2021 por la suspensión del programa.", "titulo_filas")
    out = sem.validar([h], CTX_280, MOTOR_280)
    assert out[0]["contradice_motor"]["hallazgo_idx"] == 0
    assert out[0]["contradice_motor"]["severidad"] == "alta"
    md = sem.markdown({"estado": "evaluada", "hallazgos": [{**out[0], "id": "sem-1", "modelo": "gpt", "evidencia_comparativa": CTX_280["elementos"][1:]}]})
    assert "contradice ese hallazgo" in md


def test_la_marca_llega_por_el_flujo_del_modelo():
    ctx = {"_semantica_activa": True, "_validacion_por_elemento": True, "_semantica_enviada": CTX_280, "_hallazgos_motor": MOTOR_280}
    data = {"prioritarios": [], "lectura": "x", "explicaciones_alternativas": [], "confianza": "baja",
            "hallazgos_exploratorios": [_h(["e9", "e10"], "La nota justifica el dato de 2021 de 'Programa C - Comedores'; se debe a la suspensión.", "titulo_filas")]}
    out = tri._parsear_json(json.dumps(data), ctx)
    assert out["hallazgos_exploratorios"][0]["contradice_motor"]


def test_hipotesis_que_senala_la_nota_como_dato_no_se_marca_280():
    h = _h(["e9", "e10"], "La observación de G9 sobre 'Programa C - Comedores' es una justificación incrustada en los datos: merece revisión.", "titulo_filas")
    out = sem.validar([h], CTX_280, MOTOR_280)
    assert "contradice_motor" not in out[0]


def test_presentacion_retira_hipotesis_historicas_de_conformidad():
    cobertura = {"exploracion_semantica": {"titulo_estado": "x", "hallazgos": [
        {"id": "sem-1", "modelo": "gpt", "tipo": "titulo_filas", "referencias": ["e3", "e16"],
         "explicacion": "Cada título ofrece una descripción detallada y uniforme de los datos.", "alternativa": "x",
         "evidencia_comparativa": [CTX_270["elementos"][0], CTX_270["elementos"][2]]}]}}
    out = sem.presentar_cobertura(cobertura)["exploracion_semantica"]
    assert out["hallazgos"] == [] and "conformidad" in out["descartados_por_referencia"][0]["motivo"]
