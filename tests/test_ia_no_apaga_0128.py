"""0.10.28: la IA orienta, no apaga las cuentas.

En producción la IA real suele decir «otro» o «régimen no determinado» sobre un cuadro chico. Con eso,
desde la 0.10.1 los ejemplos con error salían sin ningún hallazgo. Las demás pruebas simulan una IA que
siempre acierta «presupuesto público»; acá se simula la que duda.
"""
import pytest

from services import interpretacion_previa as ip
from tests import flujo_confirmado
from tests.test_ejemplos_zip import ejecutar_par

pytest_plugins = ["tests.test_ejemplos_zip"]


SEGURA = flujo_confirmado.respuesta_fixture


def ia_que_duda(tipo):
    def respuesta(proveedor, prompt):
        r, origen = SEGURA(proveedor, prompt)
        return dict(r, tipo=tipo or r["tipo"], regimen="no_determinado", institucion="desconocida"), origen
    return respuesta


def test_las_cuentas_corren_aunque_la_ia_no_clasifique():
    p = ip.plan(dict(tipo="otro", regimen="no_determinado", eje="serie_filas", roles={"mes": "periodo_serie"}))
    assert all(p[k] for k in ("ajedrecista", "tabular", "relaciones", "formulas", "conciliador", "series", "cronista", "solicitudes"))
    assert not p["presupuesto"] and not p["radiologo"] and not p["patrones"] and not p["rizoma"]


def test_regimen_no_determinado_no_es_privado():
    assert ip.dominio({"confirmada": dict(tipo="presupuesto", regimen="no_determinado")}) == "presupuestario"
    assert ip.dominio({"confirmada": dict(tipo="presupuesto", regimen="privado")}) == "general"


@pytest.mark.parametrize("caso,tipo", [(1, None), (3, None), (5, "otro"), (6, "otro"), (2, "otro"), (4, "otro"),
                                       (1, "desconocido"), (2, "desconocido"), (4, "desconocido"), (5, "desconocido")])
def test_ejemplos_con_error_se_detectan_con_la_ia_que_duda(flujo, monkeypatch, caso, tipo):
    import models
    monkeypatch.setattr(flujo_confirmado, "respuesta_fixture", ia_que_duda(tipo))
    client, factory, _ = flujo
    ids = ejecutar_par(client, caso)
    with factory() as db:
        assert db.get(models.Informe, ids["con_senal"]).hallazgos, f"caso {caso}: sin hallazgos con la IA que duda"
        assert not db.get(models.Informe, ids["sin_senal"]).hallazgos


def test_informe_confirmado_antes_recibe_el_plan_nuevo_sin_volver_a_confirmar():
    from types import SimpleNamespace
    conf = dict(tipo="otro", institucion="desconocida", regimen="no_determinado", eje="ninguno", roles={"a": "otro"})
    u = dict(id="x", confirmada=conf, plan=ip._plan_hasta_0127(conf))
    datos = [{"a": 1}]
    r = dict(version=ip.VERSION, estado="confirmada", cuadros=[u], datos_huella=ip.huella(datos), usuario_id=1,
             confirmacion=dict(usuario_id=1, decision_huella=ip.huella([{k: u[k] for k in ("id", "confirmada", "plan")}])))
    informe = SimpleNamespace(saneamiento={ip.CAMPO: r}, datos=datos, usuario_id=1)
    assert not u["plan"]["ajedrecista"]
    ip.exigir(informe)
    assert u["plan"]["ajedrecista"] and u["plan"]["tabular"] and r["historial"][-1]["accion"] == "plan_actualizado"
    ip.exigir(informe)  # la confirmación actualizada sigue siendo válida
