"""Carga HTTP → cola real → motor → PDF → ZIP, sin proveedores ni datos reales."""

import json
import re
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user
from database import get_db
from routers import carga_rapida, ejemplos
from routers import jobs as jobs_router
from services import analisis, jobs
from tests.flujo_confirmado import cargar_confirmado

CATALOGO = json.loads((ejemplos.SAMPLES / "manifest.json").read_text())


@pytest.fixture
def flujo(monkeypatch):
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    monkeypatch.setattr(jobs, "wake_worker", lambda: None)
    # Sólo sustituimos las dependencias externas; el motor y los PDF son reales.
    monkeypatch.setattr(analisis.triangulacion_svc, "interpretar_con_modelos_stream", lambda *a, **kw: iter([]))
    monkeypatch.setattr(jobs, "enviar_analisis_finalizado", lambda *a: ("sin_destinatario", None))
    with factory() as db:
        db.add_all(
            [
                models.Usuario(
                    id=i, nombre=f"Usuario {i}", email=f"usuario{i}@example.test", password_hash="unused", rol=rol
                )
                for i, rol in [(1, "analista"), (2, "analista"), (3, "lector"), (4, "admin")]
            ]
        )
        db.commit()
    actual = {"id": 1}

    def db_request():
        with factory() as db:
            yield db

    def usuario_request():
        with factory() as db:
            return db.get(models.Usuario, actual["id"])

    app = FastAPI()
    for router in (carga_rapida.router, ejemplos.router, jobs_router.router):
        app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = db_request
    app.dependency_overrides[get_current_user] = usuario_request
    try:
        with TestClient(app) as client:
            yield client, factory, actual
    finally:
        engine.dispose()
        deregister(JSONB)


def cargar(client, caso=1, lado="bueno", notificar=False):
    item = next(d for d in CATALOGO if d["orden"] == caso and d["columna"] == lado)
    path = ejemplos.SAMPLES / Path(item["archivo"]).name
    data = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in item["opciones"].items()}
    data.update(modelos="claude", periodo="2026-09", modo_uso_multilente="informe_en_construccion")
    if notificar is not None:
        data["notificar"] = str(notificar).lower()
    r = cargar_confirmado(client, "/api/analisis-rapido",
        data=data,
        files={
            "archivos": (
                path.name,
                path.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def ejecutar_par(client, caso=1):
    cargas = [cargar(client, caso, lado) for lado in ("bueno", "malo")]
    for _ in cargas:
        assert jobs._process_one()
    for carga in cargas:
        job = client.get(f"/api/jobs/{carga['job']['id']}").json()
        assert job["estado"] == "finalizado", job
    return {"sin_senal": cargas[0]["informe_id"], "con_senal": cargas[1]["informe_id"]}


@pytest.mark.parametrize("caso", range(1, 9))
def test_ocho_pares_producen_cuatro_archivos_con_originales_exactos_y_pdf_reales(flujo, caso):
    client, factory, _ = flujo
    ids = ejecutar_par(client, caso)
    respuesta = client.post(f"/api/ejemplos/{caso}/zip", json=ids)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"] == "application/zip"
    assert respuesta.headers["cache-control"] == "no-store"
    with ZipFile(BytesIO(respuesta.content)) as z:
        assert z.testzip() is None
        assert z.namelist() == [
            "01-original-sin-senal-esperada.xlsx",
            "02-reporte-sin-senal-esperada.pdf",
            "03-original-con-senal-esperada.xlsx",
            "04-reporte-con-senal-esperada.pdf",
        ]
        for i, lado in enumerate(("bueno", "malo")):
            original = next(d for d in CATALOGO if d["orden"] == caso and d["columna"] == lado)
            assert z.read(z.namelist()[i * 2]) == (ejemplos.SAMPLES / Path(original["archivo"]).name).read_bytes()
            pdf = z.read(z.namelist()[i * 2 + 1])
            assert pdf.startswith(b"%PDF")
            texto = " ".join(" ".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages).split())
            # Un párrafo puede continuar en otra página: quitar solo el
            # encabezado repetido para no interrumpir las frases de evidencia.
            texto = re.sub(r"GOBERNANZA MULTILENTE Reporte de apoyo para la revisión · Una segunda lectura antes de decidir Página \d+ ", "", texto)
            assert "GOBERNANZA" in texto.upper() and "2026-09" in texto
            assert "La presencia o ausencia de señales no demuestra" in texto
            assert "No detectar inconsistencias no demuestra" not in texto
            assert "no requiere una segunda validación humana" not in texto
            if caso == 1:
                assert "Diferencia temporal a aclarar" in texto
            if lado == "bueno":
                assert "Revisá la cobertura y los controles no evaluables" in texto
                assert "No se requiere información adicional" not in texto
                assert "registrar la cobertura y los controles no evaluables" in texto
                assert "Primer foco sugerido: -" not in texto
            if caso == 2 and lado == "malo":
                assert "Servicios!C5:E5" in texto
                assert "525 resueltas + 42 pendientes = 567" in texto
                assert "regla formal o aritmética" in texto
            if caso == 3:
                assert "No se incorporaron comentarios de IA sobre las señales" in texto
                assert "Que dos modelos coincidan" not in texto
                assert "Radiólogo: no evaluable (No hay preinformes con comparabilidad verificada)" in texto
                assert texto.count("No hay preinformes con comparabilidad verificada") >= 2
                if lado == "malo":
                    assert "crédito vigente" in texto
                    assert "Columnas: devengado / crédito vigente" in texto
                    assert "Presupuesto!C4:D4; Presupuesto!C5:D5" in texto
                    assert "Presupuesto!C5:E5" in texto
                    assert "no equivale al número de errores ni de hechos independientes" in texto
            if caso == 4:
                assert "La coincidencia entre modelos no convierte" not in texto
                if lado == "malo":
                    assert "ejecutado acumulado" in texto
                    assert "pagado acumulado" in texto
                    assert "Acumulados!C5" in texto and "Acumulados!D5" in texto
                    assert "C5:C5" not in texto and "D5:D5" not in texto
                    assert "Ajedrecista aplica una regla de consistencia de acumulados" in texto
    with factory() as db:
        informes = [db.get(models.Informe, informe_id) for informe_id in ids.values()]
        assert not informes[0].hallazgos
        assert informes[1].hallazgos
        assert db.query(models.EjecucionAnalisis).count() == 2
        assert db.query(models.SelloCertificacion).count() == 0
        assert db.query(models.EvaluacionCertificacion).count() == 0
        trabajos = db.query(models.AnalysisJob).all()
        lecturas = [j for j in trabajos if (j.resultado or {}).get("fase") == "interpretacion"]
        analisis = [j for j in trabajos if (j.resultado or {}).get("fase") != "interpretacion"]
        assert len(lecturas) == len(analisis) == 2
        assert all(j.notify_email is None for j in trabajos)
        assert all(j.modelos == ["claude"] for j in analisis)
        assert all(j.metricas["controles_ejecutados"] == 0 for j in lecturas)
        assert db.query(models.ActivityEvent).filter_by(accion="reporte_descargado").count() == 2
    # Descargar otra vez no repite análisis ni crea informes.
    assert client.post(f"/api/ejemplos/{caso}/zip", json=ids).status_code == 200
    with factory() as db:
        assert db.query(models.Informe).count() == 2
        assert db.query(models.AnalysisJob).count() == 4  # dos lecturas previas y dos análisis; descargar no crea tareas


@pytest.mark.parametrize(
    "alteracion,status",
    [
        ("ajeno", 404),
        ("lector", 403),
        ("pendiente", 409),
        ("error", 409),
        ("sin_devolucion", 409),
        ("mismo_id", 422),
        ("invertidos", 409),
        ("otro_caso", 409),
        ("inexistente", 404),
        ("hash_original", 409),
        ("nombre_original", 409),
        ("datos_modificados", 409),
        ("sin_fuentes", 409),
    ],
)
def test_zip_rechaza_pares_incompletos_ajenos_o_no_correspondientes(flujo, alteracion, status):
    client, factory, actual = flujo
    ids = ejecutar_par(client)
    caso = 1
    if alteracion == "ajeno":
        actual["id"] = 2
    elif alteracion == "lector":
        actual["id"] = 3
    elif alteracion == "mismo_id":
        ids["con_senal"] = ids["sin_senal"]
    elif alteracion == "invertidos":
        ids["sin_senal"], ids["con_senal"] = ids["con_senal"], ids["sin_senal"]
    elif alteracion == "otro_caso":
        caso = 2
    elif alteracion == "inexistente":
        caso = 999
    else:
        with factory() as db:
            informe = db.get(models.Informe, ids["con_senal"])
            if alteracion in {"pendiente", "error"}:
                jobs.latest_job(db, informe.id).estado = alteracion
            elif alteracion == "sin_devolucion":
                db.delete(informe.devolucion)
            elif alteracion == "datos_modificados":
                informe.datos = [{"credito_vigente": 999}]
            else:
                saneamiento = deepcopy(informe.saneamiento)
                fuente = saneamiento["proveniencia"]["fuentes"][0]
                if alteracion == "hash_original":
                    fuente["sha256_bruto"] = "incorrecto"
                elif alteracion == "nombre_original":
                    fuente["nombre_original"] = "otro.xlsx"
                elif alteracion == "sin_fuentes":
                    saneamiento["proveniencia"]["fuentes"] = []
                informe.saneamiento = saneamiento
            db.commit()
    respuesta = client.post(f"/api/ejemplos/{caso}/zip", json=ids)
    assert respuesta.status_code == status, respuesta.text
    assert respuesta.headers["content-type"] == "application/json"
    with factory() as db:
        assert db.query(models.ActivityEvent).filter_by(accion="reporte_descargado").count() == 0


def test_carga_manual_conserva_notificaciones_por_defecto(flujo):
    client, factory, _ = flujo
    carga = cargar(client, notificar=None)
    with factory() as db:
        assert db.get(models.AnalysisJob, carga["job"]["id"]).notify_email == "usuario1@example.test"


def test_administrador_puede_descargar_par_de_otro_analista(flujo):
    client, _, actual = flujo
    ids = ejecutar_par(client)
    actual["id"] = 4
    assert client.post("/api/ejemplos/1/zip", json=ids).status_code == 200
