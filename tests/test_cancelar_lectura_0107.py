"""«Cancelar lectura»: quien pidió la interpretación previa la cancela y no se piden más lecturas a los modelos."""
import time

import pytest

import models
from services import interpretacion_previa as ip
from services import jobs
from tests.test_interpretacion_libro_grande_0107 import _libro
from tests.test_interpretacion_previa import archivo, entorno  # noqa: F401 - el entorno es una fixture


def _preparar(client):
    r = client.post("/api/analisis-rapido", data={"notificar": "false", "modo_revision": "profunda"}, files=archivo())
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "interpretando"
    return r.json()["informe_id"]


def test_cancelar_lectura_la_deja_cancelada_y_no_se_retoma(entorno):  # noqa: F811
    client, db, quien = entorno
    informe_id = _preparar(client)
    quien["id"] = 2
    assert client.post(f"/api/interpretacion-previa/{informe_id}/cancelar").status_code == 404  # sólo quien la pidió
    quien["id"] = 1
    r = client.post(f"/api/interpretacion-previa/{informe_id}/cancelar")
    assert r.status_code == 200 and r.json()["estado"] == "cancelada"
    job = db.query(models.AnalysisJob).filter_by(informe_id=informe_id).one()
    assert job.estado == "error" and job.resultado["cancelada"] and job.error == jobs.LECTURA_CANCELADA
    consulta = client.get(f"/api/interpretacion-previa/{informe_id}").json()
    assert consulta["estado"] == "error" and consulta["cancelada"] and consulta["error"] == jobs.LECTURA_CANCELADA
    # Una lectura ya cancelada (o terminada) no se cancela dos veces.
    assert client.post(f"/api/interpretacion-previa/{informe_id}/cancelar").status_code == 409


def test_la_lectura_en_curso_se_detiene_al_cancelar(entorno, monkeypatch):  # noqa: F811
    client, db, quien = entorno
    informe_id = _preparar(client)
    job = db.query(models.AnalysisJob).filter_by(informe_id=informe_id).one()
    llamadas = []

    def interpretar(*args, avance=None, **kw):
        avance(0, 10, None)
        llamadas.append(1)
        client.post(f"/api/interpretacion-previa/{informe_id}/cancelar")  # la persona aprieta el botón
        avance(1, 10, "Hoja")
        llamadas.append(2)  # no se llega: el avance detecta la cancelación
        raise AssertionError("la lectura siguió después de cancelar")

    monkeypatch.setattr(ip, "interpretar", interpretar)
    with pytest.raises(jobs.LecturaCancelada):
        jobs.procesar_interpretacion(db, job)
    assert llamadas == [1]
    db.refresh(job)
    assert job.estado == "error" and job.error == jobs.LECTURA_CANCELADA


MEDIDAS = ("Gasto", "Monto", "Importe", "Erogación", "Inversión", "Transferencia", "Aporte", "Subsidio", "Beca", "Pensión")


def test_interpretar_deja_de_pedir_lecturas_cuando_el_avance_lo_corta():
    # Diez cuadros distintos (ninguno reutiliza otra lectura); se cancela al primero leído.
    datos, bloques, grillas = [], [], []
    for medida in MEDIDAS:
        d, r = _libro([f"Hoja {medida}"], columnas=("Indicador", medida, "Personas"))
        for b in r["excel"]["bloques"]:
            b["inicio"] += len(datos)
            b["fin"] += len(datos)
        datos += d
        bloques += r["excel"]["bloques"]
        grillas += r["grillas_lectura"]
    reporte = {"excel": {"bloques": bloques}, "grillas_lectura": grillas}
    pedidas = []

    def fn(proveedor, prompt):
        pedidas.append(proveedor)
        time.sleep(0.05)
        return {"institucion": "organismo_publico", "regimen": "publico", "tipo": "estadistica", "eje": "ninguno",
                "descripcion": "x", "roles": {}, "fuentes": ["col_1"], "relaciones": []}, "m"

    def avance(leidos, total, hoja):
        if leidos >= 1:
            raise jobs.LecturaCancelada()

    with pytest.raises(jobs.LecturaCancelada):
        ip.interpretar(datos, reporte, [("libro.xlsx", b"x")], {}, 1, fn=fn, proveedoras=["gpt"], avance=avance)
    time.sleep(0.3)  # las lecturas que estaban en curso terminan; las encoladas no empiezan
    assert len(pedidas) <= 2 * ip.CUADROS_EN_PARALELO < len(MEDIDAS)
