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
from routers import calibraciones, carga_rapida, certificaciones, informes
from services import analisis, calibracion
from tests.flujo_confirmado import cargar_confirmado, preparar_informe_fixture
from versiones import AUTOMATIC_PROTOCOL_VERSION, version_codigo, version_control


@pytest.fixture
def entorno():
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
        app.include_router(calibraciones.router)
        app.include_router(carga_rapida.router)
        app.include_router(informes.router)
        app.include_router(certificaciones.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
        with TestClient(app) as client:
            yield db, client
    engine.dispose()
    deregister(JSONB)


def payload():
    return {"dominio": "general", "version_protocolo": AUTOMATIC_PROTOCOL_VERSION,
            "version_codigo": version_codigo(), "control": "ajedrecista", "version_control": version_control("ajedrecista"),
            "bateria": "fixture-suma-2026", "tolerancia": 0.01, "categoria_incidencia": "cambio_motor",
            "desde": "2026-01-01T00:00:00", "hasta": "2099-01-01T00:00:00",
            "casos": [{"id": "suma-1", "tipo": "caso_calibracion", "referencia": "fixture:suma-1", "sha256": "a"*64,
                       "esperado": 12, "obtenido": 15}]}


def test_mismo_caso_en_una_corrida_no_es_ciego_y_calibracion():
    p = payload()
    p["casos"].append({**p["casos"][0], "id": "otro-id", "tipo": "caso_validacion_externa_ciega",
                       "grupo_fuente": "informe-original"})
    with pytest.raises(ValueError, match="mismo caso"):
        calibracion.CorridaCreate(**p)


def test_corrida_fallida_identifica_afectadas_sin_revocar(entorno):
    db, client = entorno
    i = models.Informe(area_id=1, usuario_id=1, periodo="2026-09", dominio="general", datos=[{"total": 12}], saneamiento={})
    preparar_informe_fixture(i)
    db.add(i)
    db.commit()
    analisis.ejecutar_analisis(db, i, [])
    e = db.query(models.EjecucionAnalisis).one()
    assert e.manifiesto["sha256_procesado"]
    assert e.manifiesto["ejecucion_id"] == e.id
    response = client.post("/calibraciones", json=payload())
    assert response.status_code == 200, response.text
    corrida_id = response.json()["id"]
    assert response.json()["estado"] == "fallida"
    afectados = client.get(f"/calibraciones/{corrida_id}/afectadas").json()
    assert afectados["potencialmente_afectadas"][0]["informe_id"] == i.id
    assert client.post(f"/calibraciones/{corrida_id}/marcar-reevaluacion").json()["sellos_modificados"] == 0
    db.refresh(e)
    assert e.requiere_reevaluacion
    assert db.query(models.SelloCertificacion).count() == 0
    diferente = payload()
    diferente["version_codigo"] = "b"*64
    otro = client.post("/calibraciones", json=diferente).json()["id"]
    assert client.get(f"/calibraciones/{otro}/afectadas").json()["potencialmente_afectadas"] == []


def test_ejecucion_critica_no_produce_hallazgos_ni_conformidad(entorno):
    db, _ = entorno
    i = models.Informe(area_id=1, usuario_id=1, periodo="2026-09", dominio="general",
                      datos=[{"credito_vigente": 10, "credito_devengado": 50}],
                      saneamiento={"contexto_validacion": {"campos_requeridos": ["unidad"]}})
    preparar_informe_fixture(i)
    db.add(i)
    db.commit()
    resultado = analisis.ejecutar_analisis(db, i, [])
    assert not resultado.hallazgos
    assert "No evaluable" in resultado.devolucion.mensaje
    assert all(c["estado"] == "no_evaluable" for c in resultado.devolucion.cobertura["lentes"])


def test_calibracion_no_puede_reutilizarse_como_ciega(entorno):
    _, client = entorno
    p = payload()
    assert client.post("/calibraciones", json=p).status_code == 200
    p["casos"][0]["tipo"] = "caso_validacion_externa_ciega"
    p["casos"][0]["grupo_fuente"] = "informe-original"
    assert client.post("/calibraciones", json=p).status_code == 422


def test_reserva_ciega_no_puede_ingresar_despues_al_banco_de_calibracion(entorno):
    _, client = entorno
    p = payload()
    p["casos"][0]["tipo"] = "caso_validacion_externa_ciega"
    p["casos"][0]["usado_para_calibracion"] = False
    p["casos"][0]["grupo_fuente"] = "informe-original"
    assert client.post("/calibraciones", json=p).status_code == 200
    p["casos"][0]["tipo"] = "caso_calibracion"
    assert client.post("/calibraciones", json=p).status_code == 422


def test_variantes_del_mismo_informe_no_cruzan_desarrollo_y_ciego(entorno):
    _, client = entorno
    p = payload()
    p["casos"][0]["grupo_fuente"] = "informe-original"
    assert client.post("/calibraciones", json=p).status_code == 200
    p["casos"][0].update(tipo="caso_validacion_externa_ciega", sha256="b" * 64)
    assert client.post("/calibraciones", json=p).status_code == 422


def test_experiencia_solo_cuenta_publicos_revisados_de_misma_estructura():
    perfil = {"institucion": "organismo_publico", "regimen": "publico", "tipo": "estadistica",
              "eje": "serie_columnas", "columnas": {"Año 2025": "periodo_serie", "Total": "cantidad"}, "unidad": None}
    unidad = {"confirmada": {**perfil, "roles": perfil["columnas"]}}
    base = {"sha256": "a" * 64, "grupo_fuente": "informe-a", "tipo": "caso_calibracion", "origen": "informe_publico",
            "perfil_cuadro": perfil, "revision_humana": {"resultado": "senal_justificada", "fundamento": "Cierre revisado", "fecha": "2026-10-22"}}
    otro = {**base, "sha256": "b" * 64, "origen": "sintetico"}
    ciego = {**base, "sha256": "c" * 64, "tipo": "caso_validacion_externa_ciega"}
    sin_revision = {**base, "sha256": "d" * 64, "revision_humana": None}
    distinto = {**base, "sha256": "e" * 64,
                "perfil_cuadro": {**perfil, "columnas": {"Año 2025": "periodo_serie", "Promedio": "cantidad"}}}
    variante = {**base, "sha256": "f" * 64}
    corridas = [SimpleNamespace(control="relaciones", casos=[base, variante, otro, ciego, sin_revision, distinto])]
    indice = calibracion.indice_experiencia(corridas)
    resumen = calibracion.experiencia_comparable(indice, unidad, "relaciones")
    assert resumen["casos_comparables"] == 1
    assert resumen["resultados"] == {"senal_justificada": 1}
    assert calibracion.experiencia_comparable(indice, unidad, "matematico")["casos_comparables"] == 0
    assert calibracion.firma_perfil({**perfil, "columnas": {"Año 2024": "periodo_serie", "Total": "cantidad"}}) == calibracion.firma_perfil(perfil)


def test_caso_revisado_exige_grupo_y_perfil():
    p = payload()["casos"][0]
    p["revision_humana"] = {"resultado": "senal_justificada", "fundamento": "La suma no cierra en el original",
                            "fecha": "2026-10-22"}
    p["origen"] = "informe_publico"
    with pytest.raises(ValueError, match="perfil"):
        calibracion.Caso(**p)
    p["perfil_cuadro"] = {"institucion": "organismo_publico", "regimen": "publico", "tipo": "estadistica",
                         "eje": "ninguno", "columnas": {"Total": "cantidad"}}
    with pytest.raises(ValueError, match="grupo_fuente"):
        calibracion.Caso(**p)
    p["grupo_fuente"] = "informe-original"
    assert calibracion.Caso(**p).revision_humana.resultado == "senal_justificada"


def test_informe_excel_publica_plan_ejecucion_y_cero_antecedentes(entorno, monkeypatch):
    from services import jobs

    db, client = entorno
    monkeypatch.setattr(jobs, "wake_worker", lambda: None)
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Datos"
    hoja.append(["Mes", "Total", "Parte A", "Parte B"])
    for mes in range(1, 7):
        hoja.append([f"2026-{mes:02d}", 30, 10, 20])
    buffer = io.BytesIO()
    libro.save(buffer)
    respuesta = cargar_confirmado(client, "/analisis-rapido", files={
        "archivos": ("cuadro.xlsx", buffer.getvalue(),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert respuesta.status_code == 200, respuesta.text
    informe = db.get(models.Informe, respuesta.json()["informe_id"])
    resultado = analisis.ejecutar_analisis(db, informe, [])
    bloque = resultado.devolucion.cobertura["excel"]["bloques"][0]
    assert bloque["trazabilidad_controles"]["cronista"]["estado"] == "ejecutado"
    assert bloque["trazabilidad_controles"]["matematico"]["estado"] == "no_aplicable"
    assert bloque["trazabilidad_controles"]["tabular"]["estado"] == "modulo_ejecutado"
    assert all(e["casos_comparables"] == 0 for e in bloque["experiencia_comparable"])


def test_tolerancia_recursiva_y_nan():
    assert calibracion.dentro_tolerancia({"x": [10]}, {"x": [10.001]}, .01)
    assert not calibracion.dentro_tolerancia(True, 1, 0)
    assert not calibracion.dentro_tolerancia(1, float("nan"), 0)


def test_carga_real_hash_reingreso_y_esquema_incompatible(entorno, monkeypatch):
    import hashlib

    from services import jobs
    db, client = entorno
    monkeypatch.setattr(jobs, "wake_worker", lambda: None)
    original = b"periodo,total\n2026-09,12\n"
    response = cargar_confirmado(client, "/analisis-rapido", files={"archivos": ("carga.csv", original, "text/csv")})
    assert response.status_code == 200, response.text
    i = db.get(models.Informe, response.json()["informe_id"])
    assert i.saneamiento["proveniencia"]["fuentes"][0]["sha256_bruto"] == hashlib.sha256(original).hexdigest()
    analisis.ejecutar_analisis(db, i, [])
    m = client.get(f"/informes/{i.id}/manifiesto").json()
    assert m["manifiesto"]["proveniencia"]["sha256_procesado"]
    assert db.query(models.EvaluacionCertificacion).count() == 0
    cambiado = b"periodo,importe\n2026-09,12\n"
    response = cargar_confirmado(client, "/analisis-rapido", files={"archivos": ("carga.csv", cambiado, "text/csv")}, data={"informe_anterior_id": str(i.id)})
    assert response.status_code == 200, response.text
    nuevo = db.get(models.Informe, response.json()["informe_id"])
    r = analisis.ejecutar_analisis(db, nuevo, [])
    assert r.devolucion.cobertura["condiciones_validez"]["cambio_esquema"]
    assert not r.devolucion.cobertura["condiciones_validez"]["puede_concluir"]
    assert nuevo.saneamiento["proveniencia"]["fuentes"][0]["version"] == 2


def test_evidencia_exploratoria_se_rechaza_por_api_y_no_crea_sello(entorno):
    db, client = entorno
    response = client.post("/certificaciones/resultados/1/evidencias", json={
        "tipo": "nota", "descripcion": "Pista de exploración", "metadata_evidencia": {"origen": {"hipotesis_id": 1}},
    })
    assert response.status_code == 422
    assert db.query(models.EvidenciaControl).count() == 0
    assert db.query(models.SelloCertificacion).count() == 0


def test_monitoreo_conserva_mas_de_veinte_cambios(entorno, monkeypatch):
    from routers import monitoreo
    db, _ = entorno
    proyecto = models.ProyectoIA(usuario_id=1, titulo="Caso de monitoreo")
    db.add(proyecto)
    db.flush()
    r = models.RegistroMonitoreo(proyecto_id=proyecto.id, usuario_id=1, tipo="indicador", titulo="Tiempo", contenido="Línea de base", estado="abierto")
    db.add(r)
    db.commit()
    monkeypatch.setattr(monitoreo.settings, "monitoreo_proyecto_id", proyecto.id)
    for numero in range(23):
        monitoreo.actualizar_estado_monitoreo(r.id, {"estado": "en_curso" if numero % 2 else "resuelto"}, db, db.get(models.Usuario, 1))
    db.refresh(r)
    assert len(r.metadata_evento["cambios_estado"]) == 23
    assert all(c["usuario_id"] == 1 and c["fecha"] for c in r.metadata_evento["cambios_estado"])
