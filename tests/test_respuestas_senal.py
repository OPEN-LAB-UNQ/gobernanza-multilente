"""«¿Qué resultó ser esta señal?» (21/10/2026): quien hizo el informe responde si cada señal era un error real, un
dato correcto o no sabe. Cada respuesta es una fila nueva (nada se borra); vale la última. Sirve para medir la
herramienta con casos reales, nunca para evaluar a la persona."""
import json
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
        db.add(models.Informe(id=1, area_id=1, usuario_id=1, periodo="2026-09", datos=[], dominio="prueba"))
        db.commit()
        db.add(models.Hallazgo(id=10, informe_id=1, lente="ajedrecista", descripcion="Total que no cierra", severidad="alta",
                               evidencia={"regla": "fila_no_cierra_total", "hoja": "H", "celda": "B5"}))
        db.add(models.Hallazgo(id=11, informe_id=1, lente="cronista", descripcion="Salto", severidad="media",
                               evidencia={"regla": "pico_aislado", "hoja": "H", "celda": "C7"}))
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


def _responder(client, respuesta, comentario="", hallazgo=10, informe=1):
    return client.post(f"/informes/{informe}/hallazgos/{hallazgo}/respuesta",
                       json={"respuesta": respuesta, "comentario": comentario})


def test_quien_hizo_el_informe_responde_y_queda_registrado(entorno):
    client, db, _ = entorno
    r = _responder(client, "error_real", "  se corrigió   en la edición siguiente ")
    assert r.status_code == 200, r.text
    assert r.json()["respuesta"]["texto"] == "Era un error real"
    assert r.json()["respuesta"]["comentario"] == "se corrigió en la edición siguiente"
    assert "no para evaluarte" in r.json()["aviso"]
    fila = db.query(models.RespuestaSenal).one()
    assert (fila.hallazgo_id, fila.informe_id, fila.usuario_id, fila.respuesta) == (10, 1, 1, "error_real")
    # La señal que generó el motor no se modifica.
    assert db.get(models.Hallazgo, 10).estado_validacion == "pendiente_decision_humana"


def test_cambiar_la_respuesta_agrega_una_fila_y_vale_la_ultima(entorno):
    client, db, _ = entorno
    assert _responder(client, "no_se").status_code == 200
    assert _responder(client, "dato_correcto", "el área explicó la reclasificación").status_code == 200
    assert db.query(models.RespuestaSenal).count() == 2
    detalle = informes._hallazgos_con_respuesta(db, db.get(models.Informe, 1), db.get(models.Usuario, 1))
    por_id = {h.id: h for h in detalle}
    assert por_id[10].respuesta["respuesta"] == "dato_correcto" and por_id[10].puede_responder
    assert por_id[11].respuesta is None


@pytest.mark.parametrize("usuario", [2, 3])
def test_nadie_responde_por_otra_persona_ni_siquiera_un_admin(entorno, usuario):
    client, db, quien = entorno
    quien["id"] = usuario
    r = _responder(client, "error_real")
    assert r.status_code == 403 and "sólo quien hizo el informe" in r.json()["detail"]
    assert db.query(models.RespuestaSenal).count() == 0


def test_quien_solo_mira_ve_la_respuesta_pero_no_puede_responder(entorno):
    client, db, quien = entorno
    _responder(client, "error_real")
    detalle = informes._hallazgos_con_respuesta(db, db.get(models.Informe, 1), db.get(models.Usuario, 3))
    h = next(x for x in detalle if x.id == 10)
    assert h.respuesta["texto"] == "Era un error real" and not h.puede_responder


@pytest.mark.parametrize("payload, codigo", [({"respuesta": "quizas"}, 422), ({}, 422),
                                             ({"respuesta": "no_se", "comentario": "x" * 501}, 422)])
def test_respuestas_invalidas_se_rechazan_sin_registrar_nada(entorno, payload, codigo):
    client, db, _ = entorno
    r = client.post("/informes/1/hallazgos/10/respuesta", json=payload)
    assert r.status_code == codigo
    assert db.query(models.RespuestaSenal).count() == 0


def test_senal_de_otro_informe_o_inexistente(entorno):
    client, db, _ = entorno
    assert _responder(client, "no_se", hallazgo=999).status_code == 404
    assert _responder(client, "no_se", informe=999).status_code == 404


def test_exportacion_para_medir_sin_datos_de_la_persona(entorno):
    import importlib.util

    client, db, _ = entorno
    _responder(client, "no_se")
    _responder(client, "error_real", "corregido")
    _responder(client, "dato_correcto", hallazgo=11)
    ruta = Path(__file__).resolve().parent.parent / "scripts" / "exportar_respuestas_senal.py"
    spec = importlib.util.spec_from_file_location("exportar_respuestas_senal", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    datos = mod.exportar(db)
    assert sorted((d["regla"], d["respuesta"]) for d in datos) == [("fila_no_cierra_total", "error_real"),
                                                                   ("pico_aislado", "dato_correcto")]
    texto = json.dumps(datos, ensure_ascii=False)
    assert "usuario" not in texto and "example.test" not in texto and "Dueña" not in texto
    assert "informe_id" not in datos[0] and "hallazgo_id" not in datos[0]
    # Seudónimo del informe: el mismo dentro de una exportación, distinto entre exportaciones.
    assert datos[0]["informe"] == datos[1]["informe"] and datos[0]["informe"] != mod.exportar(db)[0]["informe"]


def test_la_pantalla_pregunta_en_cada_senal_y_explica_para_que_sirve():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(encoding="utf-8")
    assert "¿Qué resultó ser esta señal?" in js
    for texto in ("Era un error real", "El dato estaba bien", "No sé todavía", "no para evaluarte"):
        assert texto in js
    assert "${renderRespuestaSenal(h)}" in js and "/hallazgos/${Number(bloque.dataset.hallazgo)}/respuesta" in js
    # El detalle llega escapado: se escapa una sola vez; el comentario vigente se precarga para no perderlo.
    assert "escapeHtmlUnaVez(r.comentario)" in js and "escapeHtml(r.comentario)" not in js
    assert 'value="${escapeHtmlUnaVez(h.respuesta?.comentario || "")}"' in js


def test_la_migracion_crea_la_tabla_sobre_la_ultima():
    m = (Path(__file__).resolve().parent.parent / "alembic" / "versions" / "20261021_respuestas_senal.py").read_text(encoding="utf-8")
    assert 'down_revision = "20261014_resumen_llano"' in m and '"respuestas_senal"' in m


def test_la_respuesta_guarda_copia_de_la_senal_y_sobrevive_al_reanalisis(entorno):
    client, db, _ = entorno
    _responder(client, "error_real", "corregido")
    fila = db.query(models.RespuestaSenal).one()
    assert (fila.lente, fila.regla, fila.hoja, fila.celda) == ("ajedrecista", "fila_no_cierra_total", "H", "B5")
    # Lo que hace el reanálisis: desvincula las respuestas y regenera las señales.
    db.query(models.RespuestaSenal).filter(models.RespuestaSenal.informe_id == 1).update(
        {models.RespuestaSenal.hallazgo_id: None}, synchronize_session=False)
    db.query(models.Hallazgo).filter(models.Hallazgo.informe_id == 1).delete(synchronize_session=False)
    db.commit()
    assert db.query(models.RespuestaSenal).count() == 1
    import importlib.util
    ruta = Path(__file__).resolve().parent.parent / "scripts" / "exportar_respuestas_senal.py"
    spec = importlib.util.spec_from_file_location("exportar_respuestas_senal", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    datos = mod.exportar(db)
    assert len(datos) == 1 and datos[0]["vigente"] is False and datos[0]["regla"] == "fila_no_cierra_total"


def test_el_reanalisis_desvincula_antes_de_borrar_las_senales():
    fuente = (Path(__file__).resolve().parent.parent / "services" / "analisis.py").read_text(encoding="utf-8")
    i = fuente.index("models.RespuestaSenal.hallazgo_id: None")
    assert i < fuente.index("db.query(models.Hallazgo).filter(models.Hallazgo.informe_id == informe.id).delete(")


def test_borrar_el_informe_borra_sus_respuestas(entorno):
    client, db, _ = entorno
    _responder(client, "error_real")
    r = client.delete("/informes/1")
    assert r.status_code in (200, 204), r.text
    assert db.query(models.RespuestaSenal).count() == 0


def test_una_senal_de_otro_informe_no_se_puede_responder_desde_este(entorno):
    client, db, _ = entorno
    db.add(models.Informe(id=2, area_id=1, usuario_id=2, periodo="2026-09", datos=[], dominio="prueba"))
    db.commit()
    db.add(models.Hallazgo(id=20, informe_id=2, lente="ajedrecista", descripcion="Ajena", severidad="alta", evidencia={}))
    db.commit()
    assert _responder(client, "error_real", hallazgo=20, informe=1).status_code == 404
    assert _responder(client, "error_real", hallazgo=20, informe=2).status_code == 403
    assert db.query(models.RespuestaSenal).count() == 0


def test_el_rol_lector_no_responde_aunque_sea_el_dueno(entorno):
    client, db, _ = entorno
    db.get(models.Usuario, 1).rol = "lector"
    db.commit()
    assert _responder(client, "error_real").status_code == 403
    detalle = informes._hallazgos_con_respuesta(db, db.get(models.Informe, 1), db.get(models.Usuario, 1))
    assert not any(h.puede_responder for h in detalle)


def test_con_un_analisis_en_curso_se_pide_esperar(entorno):
    client, db, _ = entorno
    db.add(models.AnalysisJob(informe_id=1, estado="procesando"))
    db.commit()
    r = _responder(client, "error_real")
    assert r.status_code == 409 and "analizando" in r.json()["detail"]
    assert db.query(models.RespuestaSenal).count() == 0


def test_respuestas_sin_ubicacion_no_se_juntan_en_la_exportacion(entorno):
    import importlib.util

    client, db, _ = entorno
    for i in (1, 2):
        db.add(models.RespuestaSenal(informe_id=1, usuario_id=1, respuesta="no_se", lente="rizoma"))
    db.commit()
    ruta = Path(__file__).resolve().parent.parent / "scripts" / "exportar_respuestas_senal.py"
    spec = importlib.util.spec_from_file_location("exportar_respuestas_senal", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod.exportar(db)) == 2
