"""Una confirmación no se extiende a otro archivo, hoja o fórmula."""
import copy

import pytest

from services import lector_mapa as lm

TOTAL = dict(tipo="filas", destino=15, expresion="3+4", columnas=["B"])


def grilla(archivo="a.xlsx", hoja="Norte"):
    return dict(archivo=archivo, hoja=hoja, celdas={"B3": 10.0, "B4": 20.0, "B15": 99.0})


def leer(lectora, prompt):
    return {"relaciones": [TOTAL]}, lectora


@pytest.mark.parametrize("segunda", [grilla(hoja="Sur"), grilla(archivo="b.xlsx")])
def test_confirmar_y_rechazar_no_afectan_otro_archivo_u_hoja(segunda):
    san = {"grillas_lectura": [grilla(), segunda]}
    r = lm.analizar(san, leer, ["gpt", "gemini"], "activo")
    preguntas = r["estado"]["preguntas"]
    assert len(preguntas) == 2 and preguntas[0]["id"] != preguntas[1]["id"]
    assert r["senales"] == []
    san["mapa_lectura"] = r["estado"]
    san, _ = lm.confirmar(san, preguntas[0]["id"], True, 7)
    r = lm.analizar(san, leer, ["gpt", "gemini"], "activo")
    assert [(s["evidencia"]["archivo"], s["evidencia"]["hoja"]) for s in r["senales"]] == [("a.xlsx", "Norte")]
    assert [q["respuesta"] for q in r["estado"]["preguntas"]] == [True, None]
    san["mapa_lectura"] = r["estado"]
    san, _ = lm.confirmar(san, preguntas[1]["id"], False, 7)
    r = lm.analizar(san, leer, ["gpt", "gemini"], "activo")
    assert len(r["senales"]) == 1 and r["senales"][0]["evidencia"]["hoja"] == "Norte"
    assert [q["respuesta"] for q in r["estado"]["preguntas"]] == [True, False]
    assert [x["confirma"] for x in r["estado"]["historial_confirmaciones"]] == [True, False]


def test_formulas_distintas_en_las_mismas_celdas_no_comparten_confirmacion():
    otra = dict(TOTAL, expresion="3-4")

    def fn(lectora, prompt):
        return {"relaciones": [TOTAL, otra]}, lectora

    san = {"grillas_lectura": [grilla()]}
    r = lm.analizar(san, fn, ["gpt", "gemini"], "activo")
    preguntas = r["estado"]["preguntas"]
    assert len(preguntas) == 2 and preguntas[0]["id"] != preguntas[1]["id"]
    san["mapa_lectura"] = r["estado"]
    san, _ = lm.confirmar(san, preguntas[0]["id"], True, 7)
    r = lm.analizar(san, fn, ["gpt", "gemini"], "activo")
    assert len(r["senales"]) == 1 and r["senales"][0]["evidencia"]["calculado"] == 30.0


def test_identidad_estable_ante_orden_de_modelos_y_sumandos():
    g = grilla()
    mapas = {"gpt": {"relaciones": [TOTAL]}, "gemini": {"relaciones": [dict(TOTAL, expresion="4 + 3")]}}
    a = lm.acordar(mapas, g["celdas"], archivo=g["archivo"], hoja=g["hoja"])
    b = lm.acordar(dict(reversed(list(mapas.items()))), g["celdas"], archivo=g["archivo"], hoja=g["hoja"])
    assert a[0]["id"] == b[0]["id"]


def test_confirmacion_antigua_no_se_propaga_y_su_historial_se_conserva():
    san = {"grillas_lectura": [grilla(), grilla(hoja="Sur")]}
    r = lm.analizar(san, leer, ["gpt", "gemini"], "activo")
    antiguo = copy.deepcopy(r["estado"])
    antiguo["version"] = "lector-1.1"
    for q in antiguo["preguntas"]:
        q.update(id="id-antiguo-compartido", respuesta=True)
    registro = dict(confirma=True, usuario_id=7, fecha="2026-10-21T12:00:00")
    antiguo["confirmaciones"] = {"id-antiguo-compartido": registro}
    antiguo["historial_confirmaciones"] = [dict(registro, id="id-antiguo-compartido")]
    san["mapa_lectura"] = antiguo
    with pytest.raises(ValueError, match="Volvé a analizar"):
        lm.confirmar(san, "id-antiguo-compartido", False, 7)
    publico = lm.saneamiento_publico(san, True)["mapa_lectura"]
    assert publico["requiere_reanalisis"] and not publico["puede_confirmar"]
    r = lm.analizar(san, leer, ["gpt", "gemini"], "activo")
    assert r["senales"] == []
    assert [q["respuesta"] for q in r["estado"]["preguntas"]] == [None, None]
    assert r["estado"]["historial_confirmaciones"] == antiguo["historial_confirmaciones"]
    assert r["estado"]["confirmaciones"] == antiguo["confirmaciones"]
