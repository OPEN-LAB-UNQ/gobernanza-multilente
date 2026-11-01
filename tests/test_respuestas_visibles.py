"""Respuestas visibles (24/10/2026): 0 respuestas en 832 señales porque el botón estaba sólo en el anexo plegado.

Ahora: «¿Qué resultó ser?» en los cinco casos principales y una línea en el PDF; la respuesta guarda la prioridad del
caso y la versión del motor; pregunta de cierre por informe en activity_events; casilla «Es una prueba» al cargar, y
scripts/indicador_valor.py con el indicador A y el tiempo hasta la respuesta, excluyendo pruebas, sólo agregados.
"""
import datetime
import importlib.util
import inspect
import io
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user
from database import get_db
from routers import informes

RAIZ = Path(__file__).resolve().parent.parent


def _modulo(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
                              creado_en=datetime.datetime(2026, 10, 20, 10, 0)))
        db.commit()
        db.add(models.Hallazgo(id=10, informe_id=1, lente="ajedrecista", descripcion="Total que no cierra", severidad="alta",
                               evidencia={"regla": "fila_no_cierra_total", "hoja": "H", "celda": "B5"}))
        db.add(models.Hallazgo(id=11, informe_id=1, lente="cronista", descripcion="Salto", severidad="media",
                               evidencia={"regla": "pico_aislado", "hoja": "H", "celda": "C7"}))
        db.add(models.Devolucion(informe_id=1, mensaje="ok", hay_hallazgos=True,
                                 cobertura={"manifiesto": {"version_motor": "multilente-9.9.9"}}))
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


def _responder(client, respuesta, hallazgo=10, informe=1):
    return client.post(f"/informes/{informe}/hallazgos/{hallazgo}/respuesta", json={"respuesta": respuesta})


def _cierre(client, payload, informe=1):
    return client.post(f"/informes/{informe}/cierre", json=payload)


# --- 2) prioridad del caso y versión del motor al responder -------------------------------------------------

def test_la_respuesta_guarda_la_prioridad_del_caso_y_la_version_del_motor(entorno):
    client, db, _ = entorno
    assert _responder(client, "error_real").status_code == 200
    fila = db.query(models.RespuestaSenal).one()
    assert fila.version_motor == "multilente-9.9.9"
    from services import casos_revision
    casos = casos_revision.agrupar(db.get(models.Informe, 1).hallazgos)["casos"]
    esperado = next(c["prioridad"] for c in casos
                    if 10 in [x.get("id") for x in [c["primary_finding"], *c["related_findings"]]])
    assert fila.prioridad == esperado and fila.prioridad in {"alta", "media", "baja"}


def test_sin_manifiesto_la_version_sale_del_ultimo_trabajo(entorno):
    client, db, _ = entorno
    db.get(models.Informe, 1).devolucion.cobertura = {}
    db.add(models.AnalysisJob(informe_id=1, estado="finalizado", resultado={"_version_analisis": "multilente-8.8"}))
    db.commit()
    assert _responder(client, "no_se").status_code == 200
    assert db.query(models.RespuestaSenal).one().version_motor == "multilente-8.8"


def test_la_migracion_agrega_las_dos_columnas_y_se_puede_revertir_en_sqlite():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    previa = _modulo(RAIZ / "alembic" / "versions" / "20261021_respuestas_senal.py", "m_respuestas")
    nueva = _modulo(RAIZ / "alembic" / "versions" / "20261024_respuestas_prioridad.py", "m_prioridad")
    assert nueva.down_revision == "20261022_biblioteca_casos"
    # alembic_version.version_num es VARCHAR(32) en PostgreSQL: un identificador más largo rompe el arranque.
    for p in (RAIZ / "alembic" / "versions").glob("*.py"):
        m = re.search(r'^revision(?:: *str)? *= *["\']([^"\']+)["\']', p.read_text(encoding="utf-8"), re.M)
        assert m and len(m.group(1)) <= 32, p.name
    sucesoras = [p.name for p in (RAIZ / "alembic" / "versions").glob("*.py")
                 if f'down_revision = "{nueva.revision}"' in p.read_text(encoding="utf-8")]
    assert sucesoras in ([], ["20261029_grupos.py"])  # una sola cadena: la sigue, a lo sumo, la de grupos (0.10.62)
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for tabla in ("informes", "usuarios", "hallazgos"):  # sólo lo que referencian sus claves foráneas
            conn.exec_driver_sql(f"CREATE TABLE {tabla} (id INTEGER PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(conn)):
            previa.upgrade()
            conn.exec_driver_sql("INSERT INTO respuestas_senal (informe_id, usuario_id, respuesta) VALUES (1, 1, 'no_se')")
            nueva.upgrade()
            columnas = {c["name"] for c in sa_inspect(conn).get_columns("respuestas_senal")}
            assert {"prioridad", "version_motor"} <= columnas
            # La respuesta anterior queda como estaba, sin dato: nada se borra.
            assert conn.exec_driver_sql("SELECT respuesta, prioridad, version_motor FROM respuestas_senal").all() == [
                ("no_se", None, None)]
            nueva.downgrade()
            columnas = {c["name"] for c in sa_inspect(conn).get_columns("respuestas_senal")}
            assert not {"prioridad", "version_motor"} & columnas
    engine.dispose()


# --- 3) pregunta de cierre por informe ------------------------------------------------------------------------

def test_cierre_queda_en_activity_events_y_vale_el_ultimo(entorno):
    client, db, _ = entorno
    assert informes._cierre_informe(db, db.get(models.Informe, 1), db.get(models.Usuario, 1))["pendiente"] is True
    r = _cierre(client, {"corrigio": "todavia_no"})
    assert r.status_code == 200, r.text
    assert r.json()["cierre"]["texto"] == "Todavía no" and "no para evaluarte" in r.json()["aviso"]
    r = _cierre(client, {"corrigio": "si", "errores_no_senalados": 2})
    assert r.json()["cierre"]["errores_no_senalados"] == 2
    eventos = db.query(models.ActivityEvent).filter_by(accion="cierre_informe_registrado").all()
    assert len(eventos) == 2  # nada se borra
    assert eventos[-1].metadata_evento == {"corrigio": "si", "errores_no_senalados": 2,
                                           "version_motor": "multilente-9.9.9", "es_prueba": False}
    estado = informes._cierre_informe(db, db.get(models.Informe, 1), db.get(models.Usuario, 1))
    assert estado["pendiente"] is False and estado["respuesta"]["corrigio"] == "si"


@pytest.mark.parametrize("payload", [{"corrigio": "quizas"}, {}, {"corrigio": "si", "errores_no_senalados": -1},
                                     {"corrigio": "si", "errores_no_senalados": "dos"},
                                     {"corrigio": "si", "errores_no_senalados": True},
                                     {"corrigio": "no", "errores_no_senalados": 1001}])
def test_cierre_invalido_no_registra_nada(entorno, payload):
    client, db, _ = entorno
    assert _cierre(client, payload).status_code == 422
    assert db.query(models.ActivityEvent).filter_by(accion="cierre_informe_registrado").count() == 0


@pytest.mark.parametrize("usuario", [2, 3])
def test_cierre_sólo_lo_responde_quien_hizo_el_informe(entorno, usuario):
    client, db, quien = entorno
    quien["id"] = usuario
    assert _cierre(client, {"corrigio": "no"}).status_code == 403
    estado = informes._cierre_informe(db, db.get(models.Informe, 1), db.get(models.Usuario, usuario))
    assert estado["puede_responder"] is False and estado["pendiente"] is False


def test_cierre_espera_al_analisis(entorno):
    client, db, _ = entorno
    db.add(models.Informe(id=2, area_id=1, usuario_id=1, periodo="2026-09", datos=[], dominio="prueba"))
    db.commit()
    assert _cierre(client, {"corrigio": "no"}, informe=2).status_code == 409


def test_historial_marca_cierre_pendiente_y_prueba(entorno):
    client, db, _ = entorno
    db.add(models.Informe(id=2, area_id=1, usuario_id=1, periodo="2026-09", datos=[], dominio="prueba",
                          saneamiento={"es_prueba": True}))
    db.commit()
    db.add(models.Devolucion(informe_id=2, mensaje="ok", hay_hallazgos=False, cobertura={}))
    db.add(models.ActivityEvent(usuario_id=1, informe_id=2, modulo="multilente", accion="analisis_rapido_encolado",
                                metadata_evento={"modo_revision": "rapida", "es_prueba": True}))
    db.commit()
    filas = {f["id"]: f for f in client.get("/informes").json()}
    assert filas[1]["cierre_pendiente"] is True and filas[1]["es_prueba"] is False
    assert filas[2]["es_prueba"] is True and filas[2]["cierre_pendiente"] is False  # una prueba no queda pendiente
    _cierre(client, {"corrigio": "no"})
    assert {f["id"]: f for f in client.get("/informes").json()}[1]["cierre_pendiente"] is False


# --- 4) casilla «Es una prueba» y medición sin pruebas ---------------------------------------------------------

def test_la_carga_recibe_y_guarda_es_prueba():
    from routers.carga_rapida import analisis_rapido

    assert inspect.signature(analisis_rapido).parameters["es_prueba"].default.default is False
    fuente = (RAIZ / "routers" / "carga_rapida.py").read_text(encoding="utf-8")
    assert 'reporte["es_prueba"] = True' in fuente and '"es_prueba": bool(es_prueba)' in fuente
    html = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")
    assert "Es una prueba (no cuenta para las mediciones)" in html and 'id="opt-es-prueba"' in html
    js = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")
    assert 'formData.append("es_prueba", optEsPrueba?.checked ? "true" : "false")' in js
    assert 'form.append("es_prueba", "true")' in js  # los ejemplos del catálogo son siempre prueba


def _datos_para_medir(client, db):
    _responder(client, "no_se")
    _responder(client, "error_real")  # vale la última
    _responder(client, "dato_correcto", hallazgo=11)
    _cierre(client, {"corrigio": "si", "errores_no_senalados": 1})
    # Un informe marcado como prueba y uno de la administración: no entran en la medición.
    db.add(models.Informe(id=2, area_id=1, usuario_id=1, periodo="2026-09", datos=[], dominio="prueba",
                          saneamiento={"es_prueba": True}))
    db.add(models.Informe(id=3, area_id=1, usuario_id=3, periodo="2026-09", datos=[], dominio="prueba"))
    db.commit()
    db.add(models.Hallazgo(id=20, informe_id=2, lente="ajedrecista", descripcion="x", severidad="alta",
                           evidencia={"regla": "r", "hoja": "H", "celda": "A1"}))
    db.commit()
    db.add(models.RespuestaSenal(hallazgo_id=20, informe_id=2, usuario_id=1, respuesta="error_real", prioridad="alta"))
    db.commit()


def test_la_exportacion_deja_afuera_las_pruebas_y_dice_de_donde_sale_la_prioridad(entorno):
    client, db, _ = entorno
    _datos_para_medir(client, db)
    db.add(models.RespuestaSenal(informe_id=1, usuario_id=1, respuesta="no_se", lente="rizoma", regla="vieja",
                                 hoja="H", celda="Z9"))  # anterior al registro de la prioridad
    db.commit()
    mod = _modulo(RAIZ / "scripts" / "exportar_respuestas_senal.py", "exportar_respuestas_senal_v")
    datos = mod.exportar(db)
    assert len(datos) == 3 and all(d["regla"] != "r" for d in datos)
    assert {d["prioridad_origen"] for d in datos} == {"registrada", None}
    assert all(d["version_motor"] == "multilente-9.9.9" for d in datos if d["prioridad_origen"] == "registrada")
    con_pruebas = mod.exportar(db, incluir_pruebas=True)
    assert len(con_pruebas) == 4 and sum(d["es_prueba"] for d in con_pruebas) == 1


def test_indicador_valor_sólo_agregados_y_sin_pruebas(entorno):
    client, db, _ = entorno
    _datos_para_medir(client, db)
    mod = _modulo(RAIZ / "scripts" / "indicador_valor.py", "indicador_valor")
    r = mod.calcular(db)
    assert r["informes"] == {"incluidos": 1, "excluidos_por_prueba": 1, "excluidos_administracion": 1}
    total = {k: sum(v[k] for v in r["indicador_a"].values()) for k in ("error_real", "dato_correcto", "no_se", "n")}
    assert total == {"error_real": 1, "dato_correcto": 1, "no_se": 0, "n": 2}
    assert all(v["estado"] == "insuficiente" for v in r["indicador_a"].values())  # menos de 10 respondidas
    assert r["tiempo_hasta_respuesta_dias"]["n"] == 2 and r["tiempo_hasta_respuesta_dias"]["mediana"] > 0
    assert r["indicador_b"] == {"informes_con_cierre": 1, "corrigio_si": 1, "corrigio_no": 0, "todavia_no": 0,
                                "informes_con_omisiones": 1, "errores_no_senalados": 1}
    assert r["cobertura_alta"]["medicion"] in {"valida", "sin medición"}
    texto = json.dumps(r, ensure_ascii=False)
    assert "example.test" not in texto and "Dueña" not in texto and "fila_no_cierra_total" not in texto
    con_admin = mod.calcular(db, incluir_admin=True)
    assert con_admin["informes"]["incluidos"] == 2 and con_admin["informes"]["excluidos_por_prueba"] == 1


def test_indicador_a_con_diez_respondidas_se_calcula():
    mod = _modulo(RAIZ / "scripts" / "indicador_valor.py", "indicador_valor_b")
    p = mod.precision({"error_real": 4, "dato_correcto": 7, "no_se": 3})
    assert p == {"error_real": 4, "dato_correcto": 7, "no_se": 3, "n": 11, "texto": "4 de 11",
                 "proporcion": 0.364, "estado": "calculado"}


# --- 1) a la vista: pantalla y PDF ----------------------------------------------------------------------------

def test_el_pdf_invita_a_responder_al_final_de_cada_caso_sin_enlaces():
    import pypdf

    from services.reporte_ejecutivo import INVITACION_RESPUESTA_PDF
    from services.reportes.markdown import render_reporte_markdown, render_reporte_pdf

    dec = _modulo(RAIZ / "tests" / "test_informe_decisor.py", "decisor_para_pdf")
    s49, s10 = dec._s49_s10()
    hs = [s10, s49, dec.pico("K40", 2010, 26.67, 0.552, 18.89), dec.pico("L40", 2011, 0.552, 18.89, 0.586)]
    md = render_reporte_markdown(dec._informe(hs), hs, True, True, pieza="ejecutivo")
    detalle = md.split("## Detalle de las consultas")[1].split("<!-- salto-pagina -->")[0]
    casos = [b for b in detalle.split("\n### ")[1:]]
    assert casos and all(b.rstrip().splitlines()[-1] == f"- {INVITACION_RESPUESTA_PDF}" for b in casos)
    assert md.count(INVITACION_RESPUESTA_PDF) == len(casos)
    assert "http" not in INVITACION_RESPUESTA_PDF and "/informes/" not in INVITACION_RESPUESTA_PDF
    texto = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(render_reporte_pdf(md))).pages)
    assert "Respondé en la aplicación" in " ".join(texto.split())


def test_la_pantalla_pregunta_en_los_casos_principales_y_al_cierre():
    js = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")
    simple = js[js.index("function renderResumenSimple("):js.index("function renderResumenTiles(")]
    assert "renderRespuestaCaso(porId.get(Number(h.id)))" in simple
    for texto in ("¿Qué resultó ser?", '"Error real"', '"Dato correcto"', '"Todavía no sé"',
                  "Sirve para medir la herramienta, no a vos.",
                  "¿Corregiste algo del informe antes de entregarlo?",
                  "¿Encontraste errores que la herramienta no señaló?"):
        assert texto in simple
    # Mismo envío que el anexo (no se duplica la lógica) y la pregunta de cierre va a su propio endpoint.
    assert 'b.addEventListener("click", responderSenal)' in simple
    assert "/informes/${Number(c.informe_id)}/cierre" in js
    assert "renderCierreInforme(d);" in js and 'cierre_informe_registrado: "Pregunta de cierre del informe"' in js
    html = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")
    # Al final del informe y fuera de «Ver todo el detalle» (visible también en el modo básico).
    previo = html[html.index('id="detalle-completo"'):html.index('id="cierre-informe"')]
    assert previo.count("<details") + 1 == previo.count("</details>")  # ya se cerró «Ver todo el detalle»
