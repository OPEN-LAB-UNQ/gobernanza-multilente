"""Una lectura sin respuestas nunca debe parecer un control exitoso."""
import json

import pytest

from services import lector_mapa as lm
from services.jobs import _evento_analisis


def ejecutar(fallan=(), relaciones=False):
    relacion = dict(tipo="filas", destino=15, expresion="3+4", columnas=["B"])

    def proveedor(nombre, prompt):
        if nombre in fallan:
            raise RuntimeError("detalle privado del proveedor")
        return {"relaciones": [relacion] if relaciones else []}, nombre

    san = {"grillas_lectura": [dict(archivo="a.xlsx", hoja="H", celdas={"B3": 10., "B4": 20., "B15": 99.})]}
    lectura = lm.analizar(san, proveedor, ["gpt", "gemini", "deepseek"], "activo")
    san["mapa_lectura"] = lectura["estado"]
    return lectura, lm.saneamiento_publico(san, puede_confirmar=True)


@pytest.mark.parametrize("fallan,estado,tramos", [
    ((), "completada", 1),
    (("deepseek",), "parcial", 1),
    (("deepseek", "gemini"), "no_completada", 0),
    (("deepseek", "gemini", "gpt"), "no_completada", 0),
])
def test_respuestas_sin_relaciones_no_se_confunden_con_fallas(fallan, estado, tramos):
    lectura, publico = ejecutar(fallan)
    resumen = publico["mapa_lectura"]["resumen"]
    assert resumen["estado"] == estado
    assert resumen["tramos_con_lectura"] == tramos
    assert resumen["lecturas_fallidas"] == len(fallan)
    assert resumen["relaciones_acordadas"] == 0
    assert lectura["senales"] == []
    assert "detalle privado" not in json.dumps(publico)
    evento = _evento_analisis(dict(tipo="lector", modo="activo", resumen=resumen), 7)
    assert evento["estado"] == ("completado" if estado == "completada" else "advertencia")
    assert "verificaron las relaciones" not in evento["mensaje"]


def test_recortes_y_varios_tramos_no_inflan_el_numero_de_hojas():
    lectura, _ = ejecutar(relaciones=True)
    mapa = lectura["estado"]
    mapa["hojas"].append(dict(mapa["hojas"][0]))
    mapa["sin_leer"] = [dict(archivo="a.xlsx", hoja="H", motivo="filas fuera del tope")]
    resumen = lm.resumen_lectura(mapa)
    assert resumen["estado"] == "parcial"
    assert resumen["hojas"] == 1 and resumen["tramos"] == 2


def test_lectura_valida_sigue_pidiendo_confirmacion_y_detectando_diferencia():
    lectura, _ = ejecutar(relaciones=True)
    mapa = lectura["estado"]
    assert lm.resumen_lectura(mapa)["relaciones_acordadas"] == 1
    assert len(mapa["preguntas"]) == 1
    pregunta = mapa["preguntas"][0]
    san, _ = lm.confirmar({"mapa_lectura": mapa}, pregunta["id"], True, 1)
    senales = lm.senales(mapa["hojas"], san["mapa_lectura"]["confirmaciones"])
    assert [s["evidencia"]["celda"] for s in senales] == ["B15"]


def test_inicio_y_error_del_lector_quedan_en_el_progreso():
    inicio = _evento_analisis({"tipo": "lector_inicio"}, 1)
    error = _evento_analisis({"tipo": "lector_error"}, 2)
    assert inicio["estado"] == "informativo" and "Comprobando" in inicio["mensaje"]
    assert error["estado"] == "advertencia" and "No se pudo" in error["mensaje"]


def test_sin_tramos_no_declara_lectura_completa():
    assert lm.resumen_lectura({})["estado"] == "no_completada"
