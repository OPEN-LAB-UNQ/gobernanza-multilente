"""Un Excel con celdas de fecha (series mensuales) se carga sin error al guardar: JSONB no acepta datetime.

Caso real: las tablas del IDB Group Data Wall 2026 (hoja F4.12, meses como fechas) daban error 500.
"""
import datetime
import io

import openpyxl

from routers.carga_rapida import _fechas_a_texto
from tests.flujo_confirmado import cargar_confirmado


def test_fechas_a_texto_convierte_anidado():
    datos = [{"Mes": datetime.datetime(2022, 6, 1), "Valor": 3.5, "Hora": datetime.time(10, 30)},
             {"meta": {"corte": datetime.date(2024, 1, 31), "lista": [datetime.datetime(2024, 1, 1, 12, 0)]}}]
    salida = _fechas_a_texto(datos)
    assert salida[0] == {"Mes": "2022-06-01", "Valor": 3.5, "Hora": "10:30:00"}
    assert salida[1]["meta"] == {"corte": "2024-01-31", "lista": ["2024-01-01T12:00:00"]}


def _xlsx_con_fechas() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mes", "Empleo", "Desempleo"])
    for i, (e, d) in enumerate([(100, 7.1), (101, 7.0), (102, 6.9), (104, 6.8), (103, 6.9), (105, 6.7)]):
        ws.append([datetime.datetime(2022, 6 + i, 1), e, d])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_analisis_rapido_guarda_un_excel_con_fechas():
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
    from routers import carga_rapida
    from services import jobs

    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    try:
        models.Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(models.Usuario(id=1, email="a@test", nombre="A", password_hash="x", rol="analista"))
            db.commit()
            app = FastAPI()
            app.include_router(carga_rapida.router, prefix="/api")
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
            original = jobs.wake_worker
            jobs.wake_worker = lambda: None
            try:
                client = TestClient(app)
                archivo = [("archivos", ("serie-mensual.xlsx", _xlsx_con_fechas(),
                                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
                resp = cargar_confirmado(client, "/api/analisis-rapido", data={"notificar": "false"}, files=archivo)
                assert resp.status_code == 200, resp.text
                informe = db.get(models.Informe, resp.json()["informe_id"])
                meses = [str(fila.get("Mes")) for fila in informe.datos]
                assert "2022-06-01" in meses
            finally:
                jobs.wake_worker = original
    finally:
        engine.dispose()
        deregister(JSONB)
