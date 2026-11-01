"""Recorrido HTTP de separación entre revisión, emisión y verificación pública."""
from __future__ import annotations

import datetime as dt

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
from routers import certificaciones as router_certificaciones
from services import certificaciones


def test_emision_con_dos_administradores_y_verificacion_publica_saneada():
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    tablas = [
        models.Usuario.__table__, models.Area.__table__, models.Informe.__table__,
        models.ProyectoIA.__table__, models.ActivityEvent.__table__,
        models.VersionProtocolo.__table__, models.DefinicionControl.__table__,
        models.EvaluacionCertificacion.__table__, models.ResultadoControl.__table__,
        models.EvidenciaControl.__table__, models.HistorialResultadoControl.__table__,
        models.SelloCertificacion.__table__,
    ]
    models.Base.metadata.create_all(engine, tables=tablas)
    try:
        with Session(engine) as db:
            admin_a = models.Usuario(
                id=1, email="admin-a@example.test", nombre="Admin A",
                password_hash="unused", rol="admin",
            )
            admin_b = models.Usuario(
                id=2, email="admin-b@example.test", nombre="Admin B",
                password_hash="unused", rol="admin",
            )
            area = models.Area(id=1, nombre="Prueba", codigo="PRUEBA")
            db.add_all([admin_a, admin_b, area])
            db.flush()
            informe = models.Informe(
                id=1, area_id=area.id, usuario_id=admin_a.id, periodo="2026-09",
                dominio="general", modo="intraarea", datos=[{"total": 10}], saneamiento={},
            )
            protocolo = models.VersionProtocolo(
                id=1, codigo="B-1", version="1.1", nombre="B-1",
                tipo_objeto="informe", descripcion="Prueba", activo=True,
                model_policy={"modelos_minimos_con_respuesta": 0}, matriz_lentes=[],
            )
            db.add_all([informe, protocolo])
            db.flush()
            control = models.DefinicionControl(
                id=1, protocolo_id=protocolo.id, codigo="B1-04", nombre="Coherencia",
                descripcion="Control", lente="ajedrecista", obligatorio=True,
                criticidad="alta", orden=1,
            )
            db.add(control)
            db.flush()
            snapshot, huella = certificaciones.snapshot_informe(informe)
            evaluacion = models.EvaluacionCertificacion(
                id=1, protocolo_id=protocolo.id, informe_id=informe.id,
                creado_por_id=admin_a.id, estado="lista_para_emision",
                hash_objeto=huella, snapshot_objeto=snapshot, manifiesto_modelos=[],
                reevaluado_en=dt.datetime(2026, 9, 14, 12, 0),
            )
            db.add(evaluacion)
            db.flush()
            resultado = models.ResultadoControl(
                id=1, evaluacion_id=evaluacion.id, control_id=control.id,
                aplica=True, estado="conforme", revisado_por_id=admin_a.id,
                reevaluado_en=dt.datetime(2026, 9, 14, 12, 0),
            )
            db.add(resultado)
            db.flush()
            db.add_all([
                models.EvidenciaControl(
                    resultado_id=resultado.id, tipo="nota",
                    descripcion="CUIT 30-12345678-9, DNI 12345678 y persona@example.org",
                    agregado_por_id=admin_a.id,
                ),
                models.HistorialResultadoControl(
                    resultado_id=resultado.id, modificado_por_id=admin_a.id,
                    estado_anterior={"estado": "no_evaluable"},
                    estado_nuevo={"estado": "conforme"},
                    creado_en=dt.datetime(2026, 9, 14, 12, 0),
                ),
            ])
            db.commit()

            app = FastAPI()
            app.include_router(router_certificaciones.router)
            app.include_router(router_certificaciones.verification_router)
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
            with TestClient(app) as client:
                payload = {
                    "alcance_del_analisis": "Control de consistencia del informe agregado.",
                    "excluidos_del_analisis": [],
                }
                bloqueada = client.post("/certificaciones/evaluaciones/1/emitir", json=payload)
                assert bloqueada.status_code == 409
                assert "segundo responsable" in bloqueada.text

                app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 2)
                emitida = client.post("/certificaciones/evaluaciones/1/emitir", json=payload)
                assert emitida.status_code == 200
                identificador = emitida.json()["identificador_publico"]

                publica = client.get(
                    f"/verificar-sello/{identificador}",
                    headers={"Accept": "application/json"},
                )
                assert publica.status_code == 200
                cuerpo = publica.text
                assert publica.json()["estado"] == "vigente"
                assert publica.json()["revision_emision_separadas"] is True
                assert publica.json()["responsables_revision"] == 1
                assert "30-12345678-9" not in cuerpo
                assert "12345678" not in cuerpo
                assert "persona@example.org" not in cuerpo
                assert "evidencia_utilizada" not in cuerpo
                assert publica.headers["cache-control"] == "public, max-age=60, must-revalidate"

                pagina = client.get(
                    f"/verificar-sello/{identificador}", headers={"Accept": "text/html"}
                )
                assert pagina.status_code == 200
                assert "personas distintas" in pagina.text
    finally:
        engine.dispose()
        deregister(JSONB)
