"""Recorrido HTTP autenticado del comprobante de controles automáticos."""
from __future__ import annotations

from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user
from database import get_db
from routers import informes as router_informes


def test_descarga_autenticada_del_comprobante_pdf_y_registra_actividad():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    tablas = [
        models.Usuario.__table__,
        models.Area.__table__,
        models.Informe.__table__,
        models.Hallazgo.__table__,
        models.Devolucion.__table__,
        models.AnalysisJob.__table__,
        models.ActivityEvent.__table__,
    ]
    models.Base.metadata.create_all(engine, tables=tablas)
    try:
        with Session(engine) as db:
            usuario = models.Usuario(
                id=1,
                email="analista@example.test",
                nombre="Analista de prueba",
                password_hash="unused",
                rol="analista",
            )
            area = models.Area(id=1, nombre="Presupuesto", codigo="PRES")
            informe = models.Informe(
                id=1,
                area_id=area.id,
                usuario_id=usuario.id,
                periodo="2026-09",
                dominio="presupuestario",
                modo="intraarea",
                datos=[{"credito_vigente": 1000, "devengado": 700, "pagado": 650}],
                saneamiento={},
            )
            devolucion = models.Devolucion(
                id=1,
                informe_id=informe.id,
                mensaje="No se detectaron observaciones mecánicas.",
                hay_hallazgos=False,
                estado="SIN_HALLAZGOS",
                cobertura={
                    "lentes": [
                        {"lente": "ajedrecista", "hallazgos": 0},
                        {"lente": "matematico", "hallazgos": 0},
                    ]
                },
            )
            job = models.AnalysisJob(
                id=1,
                informe_id=informe.id,
                usuario_id=usuario.id,
                estado="finalizado",
                resultado={
                    "_version_analisis": "2026.09-cierre",
                    "_metricas": {"duracion_total_ms": 1250},
                },
            )
            db.add_all([usuario, area, informe, devolucion, job])
            db.commit()

            app = FastAPI()
            app.include_router(router_informes.router)
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)

            with TestClient(app) as client:
                respuesta = client.get("/informes/1/comprobante-controles.pdf")

            assert respuesta.status_code == 200
            assert respuesta.headers["content-type"] == "application/pdf"
            assert "comprobante-controles-1-2026-09.pdf" in respuesta.headers["content-disposition"]
            assert respuesta.content.startswith(b"%PDF")

            lector = PdfReader(BytesIO(respuesta.content))
            assert len(lector.pages) == 1
            texto = " ".join(" ".join(p.extract_text() for p in lector.pages).split())
            assert "Lo no evaluado no equivale a un control superado." in texto
            assert "La presencia o ausencia de señales no demuestra" in texto
            assert "Comprobante de controles automáticos aplicados" in texto
            assert "SIN OBSERVACIONES MECÁNICAS" in texto
            assert "Ajedrecista" in texto
            assert "Matemático" in texto
            assert "La interpretación de los resultados y cualquier decisión institucional permanecen bajo responsabilidad humana" in texto

            evento = db.query(models.ActivityEvent).one()
            assert evento.accion == "comprobante_controles_descargado"
            assert evento.informe_id == informe.id
            assert evento.usuario_id == usuario.id
            assert evento.metadata_evento["version_analisis"] == "2026.09-cierre"
    finally:
        engine.dispose()
        deregister(JSONB)
