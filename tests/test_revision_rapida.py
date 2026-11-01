"""Revisión rápida: sin IA ni confirmación, con el plan aritmético. Carga HTTP → cola real → motor → informe."""

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import HTTPException

import models
from routers import ejemplos, informes
from services import analisis, cuota_ia, jobs, lector_mapa
from services import interpretacion_previa as ip
from services.reportes.markdown import render_reporte_markdown
from tests.test_ejemplos_zip import CATALOGO, flujo  # noqa: F401 — fixture compartida

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# El caso 8 es una asociación exploratoria (Rizoma): la rápida no la corre y lo declara al comienzo del informe.
SOLO_PROFUNDA = {8}


@pytest.fixture
def sin_ia(flujo, monkeypatch):  # noqa: F811
    """Ninguna llamada a la IA: ni el lector del cuadro ni la lectura de señales ni el cupo de IA."""
    def prohibido(*a, **kw):
        raise AssertionError("la revisión rápida llamó a la IA")
    monkeypatch.setattr(lector_mapa, "llamar", prohibido)
    monkeypatch.setattr(analisis.triangulacion_svc, "interpretar_con_modelos_stream", prohibido)
    monkeypatch.setattr(cuota_ia, "verificar_analisis", prohibido)
    return flujo


def cargar(client, caso, lado, **extra):
    item = next(d for d in CATALOGO if d["orden"] == caso and d["columna"] == lado)
    path = ejemplos.SAMPLES / Path(item["archivo"]).name
    data = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in item["opciones"].items()}
    data.update(periodo="2026-09", notificar="false", modo_revision="rapida")
    data.update(extra)
    return client.post("/api/analisis-rapido", data=data, files={"archivos": (path.name, path.read_bytes(), XLSX)})


@pytest.mark.parametrize("caso", range(1, 9))
def test_rapida_detecta_los_ocho_ejemplos_sin_ia_ni_confirmacion(sin_ia, caso):
    client, factory, _ = sin_ia
    ids = {}
    for lado in ("bueno", "malo"):
        r = cargar(client, caso, lado)
        assert r.status_code == 200, r.text
        assert "job" in r.json() and "interpretacion" not in r.json()
        ids[lado] = r.json()["informe_id"]
    while jobs._process_one():
        pass
    with factory() as db:
        assert not db.query(models.AnalysisJob).filter(models.AnalysisJob.estado != "finalizado").count()
        # Ninguna lectura previa: sólo los dos análisis, sin modelos y marcados como rápidos.
        trabajos = db.query(models.AnalysisJob).all()
        assert len(trabajos) == 2
        assert all((j.resultado or {}).get("fase") is None and j.modelos == [] for j in trabajos)
        assert all(j.resultado["modo_revision"] == "rapida" for j in trabajos)
        for lado, informe_id in ids.items():
            informe = db.get(models.Informe, informe_id)
            meta = informe.saneamiento
            assert meta["modo_revision"] == "rapida"
            registro = meta[ip.CAMPO]
            assert registro["origen"] == ip.ORIGEN_RAPIDA and registro["estado"] == "confirmada"
            assert registro["confirmacion"]["automatica"] is True
            assert ip.exigir(informe)  # la interpretación automática pasa la barrera legítimamente
            for u in registro["cuadros"]:
                assert not u["plan"]["radiologo"] and not u["plan"]["rizoma"] and not u["plan"]["orquesta"]
                assert u["plan"]["presupuesto"] == (informe_opciones(caso)["dominio"] == "presupuestario")
            assert "mapa_lectura" not in meta  # el lector del cuadro no corrió
            cobertura = informe.devolucion.cobertura
            assert cobertura["interpretacion_ia"]["etapa"]["estado"] == "no_solicitada"
            if lado == "bueno" or caso in SOLO_PROFUNDA:
                assert not informe.hallazgos, [h.descripcion for h in informe.hallazgos]
            else:
                assert informe.hallazgos
            texto = render_reporte_markdown(informe, list(informe.hallazgos), False, True)
            primeras = [x for x in texto.split("\n") if x.strip()][:2]
            assert primeras[1].startswith("**Revisión rápida: sin IA. No se corrieron: lector del cuadro con IA, "
                                          "lectura de señales con IA, antecedentes, asociaciones exploratorias.**"), primeras
            assert ("Las reglas de presupuesto corrieron" in primeras[1]) == (informe_opciones(caso)["dominio"] == "presupuestario")
            assert "Lector del cuadro: lectura" not in texto


def informe_opciones(caso):
    return next(d for d in CATALOGO if d["orden"] == caso and d["columna"] == "malo")["opciones"]


def test_profunda_sigue_exigiendo_interpretacion_y_confirmacion(flujo):  # noqa: F811
    client, factory, _ = flujo
    r = cargar(client, 1, "malo", modo_revision="profunda", modelos="claude")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "interpretando"
    with factory() as db:
        trabajos = db.query(models.AnalysisJob).all()
        assert [(j.resultado or {}).get("fase") for j in trabajos] == ["interpretacion"]
        informe = db.get(models.Informe, r.json()["informe_id"])
        assert informe.saneamiento[ip.CAMPO]["estado"] == "interpretando"
        with pytest.raises(HTTPException) as e:
            ip.exigir(informe)
        assert e.value.status_code == 409


def test_sin_modo_revision_es_la_rapida(sin_ia):
    """La rápida es la opción por defecto: una carga sin el campo no llama a la IA ni pide confirmar."""
    client, factory, _ = sin_ia
    item = next(d for d in CATALOGO if d["orden"] == 1 and d["columna"] == "malo")
    path = ejemplos.SAMPLES / Path(item["archivo"]).name
    r = client.post("/api/analisis-rapido", data={"periodo": "2026-09", "notificar": "false"},
                    files={"archivos": (path.name, path.read_bytes(), XLSX)})
    assert r.status_code == 200, r.text
    assert "job" in r.json() and "interpretacion" not in r.json()
    with factory() as db:
        assert db.get(models.Informe, r.json()["informe_id"]).saneamiento["modo_revision"] == "rapida"
        assert [j.resultado.get("modo_revision") for j in db.query(models.AnalysisJob).all()] == ["rapida"]


def test_historial_dice_que_revision_fue(flujo):  # noqa: F811
    client, _, _ = flujo
    client.app.include_router(informes.router, prefix="/api")
    rapida = cargar(client, 2, "malo").json()["informe_id"]
    profunda = cargar(client, 2, "bueno", modo_revision="profunda").json()["informe_id"]
    lista = {i["id"]: i["modo_revision"] for i in client.get("/api/informes").json()}
    assert lista == {rapida: "rapida", profunda: "profunda"}


def test_rapida_no_confirma_ni_relee(sin_ia):
    client, _, _ = sin_ia
    for accion in ("confirmar", "detallada"):
        r = cargar(client, 1, "malo", interpretacion_accion=accion, interpretacion_id="1", interpretacion_revision="1")
        assert r.status_code == 422, r.text
    assert cargar(client, 1, "malo", modo_revision="otra").status_code == 422


def test_la_barrera_rechaza_una_interpretacion_rapida_alterada(sin_ia):
    client, factory, _ = sin_ia
    r = cargar(client, 3, "malo")
    assert r.status_code == 200, r.text
    with factory() as db:
        informe = db.get(models.Informe, r.json()["informe_id"])
        meta = deepcopy(informe.saneamiento)
        # Prender los antecedentes a mano rompe la huella de la decisión y el plan: no pasa.
        meta[ip.CAMPO]["cuadros"][0]["plan"]["radiologo"] = True
        informe.saneamiento = meta
        with pytest.raises(HTTPException) as e:
            ip.exigir(informe)
        assert e.value.status_code == 409


def test_rapida_declara_cruces_entre_ediciones_con_dos_archivos(sin_ia):
    client, factory, _ = sin_ia
    archivos = []
    for lado in ("bueno", "malo"):
        item = next(d for d in CATALOGO if d["orden"] == 2 and d["columna"] == lado)
        path = ejemplos.SAMPLES / Path(item["archivo"]).name
        archivos.append(("archivos", (path.name, path.read_bytes(), XLSX)))
    r = client.post("/api/analisis-rapido", data={"periodo": "2026-09", "notificar": "false", "modo_revision": "rapida"},
                    files=archivos)
    assert r.status_code == 200, r.text
    with factory() as db:
        meta = db.get(models.Informe, r.json()["informe_id"]).saneamiento
        assert "cruces entre ediciones" in meta["revision_rapida"]["no_corrieron"]
