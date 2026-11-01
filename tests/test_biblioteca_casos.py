"""La biblioteca incorpora sólo cuadros ejecutados, públicos y aprobados por una persona."""
import io
from types import SimpleNamespace

import openpyxl
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
from routers import biblioteca_casos, carga_rapida, informes
from services import analisis
from services import biblioteca_casos as bc
from services import interpretacion_previa as ip
from tests.flujo_confirmado import cargar_confirmado, respuesta_fixture


@pytest.fixture
def entorno(monkeypatch):
    from services import jobs

    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(models.Usuario(id=1, email="admin@test", nombre="Admin", password_hash="x", rol="admin"))
        db.add(models.Area(id=1, nombre="Area", codigo="A"))
        db.commit()
        app = FastAPI()
        app.include_router(biblioteca_casos.router)
        app.include_router(carga_rapida.router)
        app.include_router(informes.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
        monkeypatch.setattr(jobs, "wake_worker", lambda: None)
        with TestClient(app) as client:
            yield db, client
    engine.dispose()
    deregister(JSONB)


def cargar(db, client, *, variar=False):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Datos"
    hoja.append(["Mes", "Total", "Parte A", "Parte B"])
    for mes in range(1, 7):
        hoja.append([f"2026-{mes:02d}", 30 + int(variar), 10 + int(variar), 20])
    buf = io.BytesIO()
    libro.save(buf)
    r = cargar_confirmado(client, "/analisis-rapido", files={"archivos": (
        "cuadro.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    informe = db.get(models.Informe, r.json()["informe_id"])
    resultado = analisis.ejecutar_analisis(db, informe, [])
    for job in informe.trabajos_analisis or []:
        if job.estado in {"pendiente", "procesando"}:
            job.estado = "finalizado"
    db.commit()
    bloque = resultado.devolucion.cobertura["excel"]["bloques"][0]
    return informe, bloque


def propuesta(bloque, *, fuente="https://datos.unlp.edu.ar/series/cuadro.xlsx"):
    return {"archivo": bloque["archivo"], "hoja": bloque["hoja"], "bloque": bloque["bloque"],
            "control": "ajedrecista", "resultado": "sin_senal_revisado",
            "fundamento": "Revisé las seis filas del original y la suma de sus partes cierra.",
            "localizador": "Datos!B2:D7", "fuente_url": fuente}


def test_propuesta_aprobacion_y_antecedente_sin_autocontarse(entorno):
    db, client = entorno
    informe, bloque = cargar(db, client)
    assert bloque["trazabilidad_controles"]["ajedrecista"]["estado"] == "ejecutado"
    unidad = (informe.saneamiento or {})[ip.CAMPO]["cuadros"][0]
    assert bc.resumen(db)["observados"] == 1
    sin_revision = bc.experiencia(bc.indice(db), unidad, "ajedrecista")
    assert sin_revision["casos_comparables"] == 1
    assert sin_revision["revisados_por_persona"] == 0
    assert sin_revision["resultados"] == {}
    assert bc.antecedentes_interpretacion(bc.observados(db, informe.usuario_id), unidad["columnas"])["orientacion"]
    assert bc.antecedentes_interpretacion(bc.observados(db, informe.usuario_id), unidad["columnas"],
                                          bc.observados(db, informe.usuario_id)[0].fuente_sha256)["orientacion"] is None
    db.add(models.Usuario(id=2, email="otra@test", nombre="Otra", password_hash="x", rol="analista"))
    db.commit()
    assert bc.observados(db, 2) == []
    assert bc.indice(db, 2) == {}
    p = propuesta(bloque)
    assert client.post(f"/biblioteca-casos/informes/{informe.id}", json={**p, "fuente_url": "http://127.0.0.1/file.xlsx"}).status_code == 422
    assert client.post(f"/biblioteca-casos/informes/{informe.id}", json={**p, "control": "matematico"}).status_code == 422
    r = client.post(f"/biblioteca-casos/informes/{informe.id}", json=p)
    assert r.status_code == 200, r.text
    caso_id = r.json()["id"]
    assert r.json()["estado"] == "pendiente"
    assert client.get("/biblioteca-casos").json()["resumen"]["aprobados"] == 0
    aprobado = client.post(f"/biblioteca-casos/{caso_id}/decision", json={"aprobar": True,
        "fundamento": "Comparé las filas indicadas con la publicación enlazada y confirmo la revisión."})
    assert aprobado.status_code == 200, aprobado.text
    assert client.get("/biblioteca-casos").json()["resumen"]["aprobados"] == 1
    index = bc.indice(db)
    assert bc.experiencia(index, unidad, "ajedrecista")["casos_comparables"] == 1
    assert bc.experiencia(bc.indice(db, 2), unidad, "ajedrecista")["revisados_por_persona"] == 1
    assert bc.experiencia(index, unidad, "ajedrecista", aprobado.json()["fuente_sha256"])["casos_comparables"] == 0
    otro, segundo_bloque = cargar(db, client, variar=True)
    assert otro.id != informe.id
    respaldo = next(e for e in segundo_bloque["experiencia_comparable"] if e["control"] == "ajedrecista")
    assert respaldo["casos_comparables"] == 1
    assert respaldo["revisados_por_persona"] == 1
    assert respaldo["resultados"] == {"sin_senal_revisado": 1}
    assert client.post(f"/biblioteca-casos/{caso_id}/decision", json={"aprobar": True,
        "fundamento": "No debe poder sobrescribirse una decisión ya registrada."}).status_code == 409


def test_dos_casos_independientes_orientan_sin_copiar_numeros():
    perfil = {"institucion": "universidad", "regimen": "publico", "tipo": "presupuesto", "eje": "serie_filas",
              "columnas": {"Año 2025": "periodo_serie", "Total": "importe", "Crédito vigente": "importe"}}
    casos = [SimpleNamespace(fuente_sha256=x * 64, grupo_fuente=x * 64, perfil_cuadro=perfil)
             for x in ("a", "b")]
    nombres = list(perfil["columnas"])
    assert bc.antecedentes_interpretacion(casos[:1], nombres)["orientacion"]["tipo"] == "presupuesto"
    assert bc.antecedentes_interpretacion(casos, nombres)["orientacion"]["tipo"] == "presupuesto"
    assert bc.antecedentes_interpretacion(casos, nombres, "a" * 64)["orientacion"]["tipo"] == "presupuesto"
    assert bc.antecedentes_interpretacion(casos[:1], nombres, "a" * 64)["orientacion"] is None
    prompts = []
    def fn(proveedor, prompt):
        prompts.append(prompt)
        return respuesta_fixture(proveedor, prompt)
    datos = [{"Año 2026": "2026", "Total": 10, "Crédito vigente": 10}]
    reporte = {"archivos_origen": ["nuevo.xlsx"]}
    r = ip.interpretar(datos, reporte, [("nuevo.xlsx", b"nuevo")], {}, 1,
                       casos_revisados=casos, fn=fn, proveedoras=["gpt", "gemini", "deepseek"])
    assert r["cuadros"][0]["antecedentes_biblioteca"] == {"casos_similares": 2, "orientacion_utilizada": True}
    assert all("LECTURAS CONFIRMADAS ANTERIORES" in p and '"tipo": "presupuesto"' in p for p in prompts)
    assert all("2025" not in p and "2026" not in p for p in prompts)


def test_institucion_desconocida_no_descarta_tipo_y_roles_confirmados():
    perfil = {"institucion": "desconocida", "regimen": "desconocido", "tipo": "estadistica",
              "eje": "serie_filas", "columnas": {"Mes": "periodo_serie", "Total": "cantidad", "Parte": "cantidad"}}
    caso = SimpleNamespace(fuente_sha256="a" * 64, grupo_fuente="a" * 64, perfil_cuadro=perfil)
    orientacion = bc.antecedentes_interpretacion([caso], list(perfil["columnas"]))["orientacion"]
    assert orientacion["tipo"] == "estadistica"
    assert orientacion["institucion"] == "desconocida"


def test_resultados_senal_exigen_respuesta_del_autor(entorno):
    db, client = entorno
    informe, bloque = cargar(db, client)
    p = {**propuesta(bloque), "resultado": "senal_justificada", "hallazgo_id": 999}
    assert client.post(f"/biblioteca-casos/informes/{informe.id}", json=p).status_code == 422
    assert db.query(models.CasoBiblioteca).count() == 0
