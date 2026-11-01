"""Lector del cuadro en la pantalla: preguntas a quien hizo el informe; la grilla con números no viaja al navegador."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user
from database import get_db
from routers import informes
from services import lector_mapa as lm

PREGUNTA = {"id": "abc123def456", "archivo": "a.xlsx", "hoja": "H", "relacion": "15 = 3 + 4",
            "fundamento": "la fila 15 es el total", "lectoras": ["gpt", "gemini"], "respuesta": None}


def _saneamiento():
    return {
        "otra_cosa": {"x": 1},
        "grillas_lectura": [{"archivo": "a.xlsx", "hoja": "H", "celdas": {"B3": 1234.0}}],
        "mapa_lectura": {"version": lm.VERSION, "modo": "observar", "senales": 0, "preguntas": [dict(PREGUNTA)],
                         "confirmaciones": {}, "hojas": [{"archivo": "a.xlsx", "hoja": "H", "huella": "h",
                                                          "mapas": {"gpt": {"que_es": "altas", "relaciones": [{"x": 1}],
                                                                            "error": None}},
                                                          "grupos": [{"id": "abc123def456"}]}]},
    }


@pytest.fixture
def entorno():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(models.Area(id=1, nombre="Área de prueba", codigo="prueba"))
        db.add(models.Usuario(id=1, email="duena@example.test", nombre="Dueña", password_hash="x", rol="analista"))
        db.add(models.Usuario(id=2, email="otra@example.test", nombre="Otra", password_hash="x", rol="analista"))
        db.add(models.Usuario(id=3, email="admin@example.test", nombre="Admin", password_hash="x", rol="admin"))
        db.commit()
        db.add(models.Informe(id=1, area_id=1, usuario_id=1, periodo="2026-09", datos=[], dominio="prueba",
                              saneamiento=_saneamiento()))
        db.commit()
        quien = {"id": 1}
        app = FastAPI()
        app.include_router(informes.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, quien["id"])
        with TestClient(app) as client:
            yield client, db, quien
    engine.dispose()
    deregister(JSONB)


def _confirmar(client, confirma, pregunta="abc123def456"):
    return client.post(f"/informes/1/lector/{pregunta}", json={"confirma": confirma})


def test_la_pantalla_no_recibe_la_grilla_ni_las_respuestas_crudas_de_los_modelos():
    pub = lm.saneamiento_publico(_saneamiento(), puede_confirmar=True)
    assert "grillas_lectura" not in pub and pub["otra_cosa"] == {"x": 1}
    m = pub["mapa_lectura"]
    assert m["preguntas"][0]["id"] == "abc123def456" and m["puede_confirmar"] is True
    assert m["hojas"][0]["lecturas"]["gpt"] == {"que_es": "altas", "error": False}
    assert "1234" not in str(pub) and "'relaciones':" not in str(m["hojas"])
    assert lm.saneamiento_publico({"a": 1}) == {"a": 1} and lm.saneamiento_publico(None) is None


def test_el_detalle_y_el_informe_llegan_sin_grilla(entorno):
    client, db, _ = entorno
    for ruta in ("/informes/1", "/informes/1/detalle"):
        r = client.get(ruta)
        assert r.status_code == 200, (ruta, r.text)
        san = r.json()["saneamiento"]
        assert "grillas_lectura" not in san and san["mapa_lectura"]["preguntas"][0]["id"] == "abc123def456"
    # La base conserva la grilla: hace falta para volver a analizar.
    assert "grillas_lectura" in db.get(models.Informe, 1).saneamiento


def test_quien_hizo_el_informe_confirma_y_queda_registrado(entorno):
    client, db, _ = entorno
    r = _confirmar(client, True)
    assert r.status_code == 200, r.text
    assert r.json()["pregunta"]["respuesta"] is True and "volver a analizar" in r.json()["aviso"]
    assert _confirmar(client, False).status_code == 200
    mapa = db.get(models.Informe, 1).saneamiento["mapa_lectura"]
    assert mapa["confirmaciones"]["abc123def456"]["confirma"] is False
    assert [h["confirma"] for h in mapa["historial_confirmaciones"]] == [True, False]
    assert mapa["preguntas"][0]["respuesta"] is False
    assert "grillas_lectura" in db.get(models.Informe, 1).saneamiento


@pytest.mark.parametrize("usuario", [2, 3])
def test_nadie_confirma_por_otra_persona(entorno, usuario):
    client, db, quien = entorno
    quien["id"] = usuario
    assert _confirmar(client, True).status_code == 403
    assert db.get(models.Informe, 1).saneamiento["mapa_lectura"]["confirmaciones"] == {}
    detalle = client.get("/informes/1/detalle")
    if usuario == 3:  # la administración ve el informe pero no responde por quien lo hizo
        assert detalle.json()["saneamiento"]["mapa_lectura"]["puede_confirmar"] is False
    else:  # otra analista ni siquiera lo ve
        assert detalle.status_code == 403


def test_respuestas_invalidas_o_pregunta_inexistente(entorno):
    client, db, _ = entorno
    assert _confirmar(client, "si").status_code == 422
    assert _confirmar(client, True, pregunta="no-existe").status_code == 404
    assert client.post("/informes/9/lector/abc123def456", json={"confirma": True}).status_code == 404


def test_con_un_analisis_en_curso_se_pide_esperar(entorno):
    client, db, _ = entorno
    db.add(models.AnalysisJob(informe_id=1, estado="procesando"))
    db.commit()
    assert _confirmar(client, True).status_code == 409


def test_la_confirmacion_hace_efecto_al_volver_a_analizar():
    celdas = {"A3": "Enero", "B3": 10.0, "A4": "Febrero", "B4": 20.0, "A15": "Total", "B15": 99.0}
    total = {"tipo": "filas", "destino": 15, "expresion": "3 + 4", "columnas": ["B"], "fundamento": "total"}
    fn = lambda lectora, prompt: ({"relaciones": [total]}, lectora)  # noqa: E731
    san = {"grillas_lectura": [{"archivo": "a.xlsx", "hoja": "H", "celdas": celdas}]}
    r = lm.analizar(san, fn, ["gpt", "gemini"], "activo")
    assert r["senales"] == []
    san["mapa_lectura"] = r["estado"]
    san, pregunta = lm.confirmar(san, r["estado"]["preguntas"][0]["id"], True, 1)
    r2 = lm.analizar(san, fn, ["gpt", "gemini"], "activo")
    assert [s["evidencia"]["celda"] for s in r2["senales"]] == ["B15"]
    assert r2["estado"]["preguntas"][0]["respuesta"] is True


def test_la_pantalla_pregunta_y_avisa_que_es_a_ciegas():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(encoding="utf-8")
    assert "Así se leyó el cuadro." in js and "sin ver los números" in js
    assert "/lector/${encodeURIComponent(id)}" in js and "renderLecturaCuadro(d.saneamiento?.mapa_lectura)" in js
    assert "todavía no genera señales" in js



def test_confirmacion_por_http_solo_se_aplica_a_la_hoja_elegida(entorno):
    client, db, _ = entorno
    total = dict(tipo="filas", destino=15, expresion="3+4", columnas=["B"])

    def fn(lectora, prompt):
        return {"relaciones": [total]}, lectora

    san = {"grillas_lectura": [dict(archivo="a.xlsx", hoja=hoja,
                                   celdas={"B3": 10.0, "B4": 20.0, "B15": 99.0})
                              for hoja in ("Norte", "Sur")]}
    san["mapa_lectura"] = lm.analizar(san, fn, ["gpt", "gemini"], "activo")["estado"]
    informe = db.get(models.Informe, 1)
    informe.saneamiento = san
    db.commit()
    qs = client.get("/informes/1/detalle").json()["saneamiento"]["mapa_lectura"]["preguntas"]
    assert _confirmar(client, True, qs[0]["id"]).status_code == 200
    r = lm.analizar(informe.saneamiento, fn, ["gpt", "gemini"], "activo")
    informe.saneamiento = dict(informe.saneamiento, mapa_lectura=r["estado"])
    db.commit()
    assert [(s["evidencia"]["hoja"], s["evidencia"]["celda"]) for s in r["senales"]] == [("Norte", "B15")]
    publico = client.get("/informes/1/detalle").json()["saneamiento"]["mapa_lectura"]
    assert [q["respuesta"] for q in publico["preguntas"]] == [True, None]
    assert len(informe.saneamiento["mapa_lectura"]["historial_confirmaciones"]) == 1


def test_informe_antiguo_pide_reanalizar_antes_de_confirmar(entorno):
    client, db, _ = entorno
    informe = db.get(models.Informe, 1)
    san = _saneamiento()
    san["mapa_lectura"]["version"] = "lector-1.1"
    informe.saneamiento = san
    db.commit()
    r = _confirmar(client, True)
    assert r.status_code == 409 and "Volvé a analizar" in r.json()["detail"]
    publico = client.get("/informes/1/detalle").json()["saneamiento"]["mapa_lectura"]
    assert publico["requiere_reanalisis"] is True and publico["puede_confirmar"] is False
    assert informe.saneamiento["mapa_lectura"]["confirmaciones"] == {}
