"""Ámbito del informe: organismo público (por defecto) u organización."""
import io
from types import SimpleNamespace as NS

import pytest
from openpyxl import Workbook

from routers.carga_rapida import _inferir_dominio
from services import ambito
from services.lentes import ajedrecista
from tests.flujo_confirmado import cargar_confirmado

COOP = [
    ("Ingresos por servicios de agua", 90, 95, 104, 98),
    ("Ingresos por energía", 60, 62, 66, 61),
    ("Cuotas sociales", 4, 4, 4.3, 4.3),
    ("Remuneraciones", -40, -44, -45, -43),
    ("Compra de energía", -45, -48, -52, -50),
    ("Mantenimiento de redes", -12, -12, -9, -8),
    ("Gastos administrativos", -8, -8.5, -8.4, -8.4),
]


def _coop():
    return [{"Rubro": r, "Presupuesto original": o, "Presupuesto vigente": v, "Ejecutado": e, "Pagado": p}
            for r, o, v, e, p in COOP]


def _reglas(hallazgos):
    return {h["evidencia"].get("regla") for h in hallazgos}


@pytest.fixture
def en_ambito():
    testigos = []

    def declarar(valor):
        testigos.append(ambito.declarar(valor))
    yield declarar
    for testigo in reversed(testigos):
        ambito.restaurar(testigo)


def test_por_defecto_es_publico_y_valores_invalidos_vuelven_a_publico():
    assert ambito.actual() == ambito.PUBLICO
    assert ambito.normalizar("cualquiera") == ambito.PUBLICO
    assert ambito.de_informe(NS(saneamiento={})) == ambito.PUBLICO
    assert ambito.de_informe(NS(saneamiento={"opciones_tecnicas": {"ambito": "organizacion"}})) == ambito.ORGANIZACION


def test_organizacion_no_hereda_reglas_del_presupuesto_publico(en_ambito):
    en_ambito(ambito.ORGANIZACION)
    reglas = _reglas(ajedrecista.imposibilidad(_coop()))
    assert not reglas & {"devengado_supera_vigente", "pagado_supera_devengado", "pagado_supera_vigente"}
    assert "valor_negativo_en_magnitud_no_negativa" not in reglas


def test_organizacion_marca_el_gasto_que_supera_lo_presupuestado_y_no_el_ingreso(en_ambito):
    en_ambito(ambito.ORGANIZACION)
    desvio = next(h for h in ajedrecista.imposibilidad(_coop()) if h["evidencia"]["regla"] == "gasto_real_supera_presupuesto")
    assert desvio["evidencia"]["columna_presupuesto"] == "Presupuesto vigente"
    assert desvio["evidencia"]["columna_real"] == "Ejecutado"
    marcadas = {m["rubro"] for m in desvio["evidencia"]["muestras"]}
    assert marcadas == {"Remuneraciones", "Compra de energía"}
    texto = desvio["descripcion"] + desvio["pregunta_institucional"]
    assert "devengado" not in texto.lower() and "crédito" not in texto.lower()


def test_publico_conserva_las_reglas_presupuestarias(en_ambito):
    en_ambito(ambito.PUBLICO)
    datos = [{"Programa": "A", "Crédito vigente": 100, "Devengado": 120, "Pagado": 90},
             {"Programa": "B", "Crédito vigente": 100, "Devengado": 80, "Pagado": 70}]
    reglas = _reglas(ajedrecista.imposibilidad(datos))
    assert "devengado_supera_vigente" in reglas and "gasto_real_supera_presupuesto" not in reglas


def test_dominio_presupuestario_no_se_infiere_en_una_organizacion():
    datos = [{"Rubro": "x", "Presupuesto vigente": 1, "Pagado": 1}]
    assert _inferir_dominio(datos, "auto", ambito.PUBLICO) == "presupuestario"
    assert _inferir_dominio(datos, "auto", ambito.ORGANIZACION) == "general"
    assert _inferir_dominio(datos, "presupuestario", ambito.ORGANIZACION) == "presupuestario"


def test_la_lectura_con_ia_recibe_el_vocabulario_de_organizacion():
    from services import triangulacion
    base = {"dominio": "general", "periodo": "2025", "orientacion_analisis": ""}
    org = triangulacion._prompt_usuario({**base, "ambito": "organizacion"}, [])
    pub = triangulacion._prompt_usuario({**base, "ambito": "publico"}, [])
    assert ambito.INSTRUCCION_ORGANIZACION in org and ambito.INSTRUCCION_ORGANIZACION not in pub


def _xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append(["Rubro", "Presupuesto original", "Presupuesto vigente", "Ejecutado", "Pagado"])
    for fila in COOP:
        ws.append(list(fila))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_carga_guarda_el_ambito_y_rechaza_valores_desconocidos():
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
                archivo = [("archivos", ("coop.xlsx", _xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
                assert cargar_confirmado(client, "/api/analisis-rapido", data={"ambito": "otro"}, files=archivo).status_code == 422
                resp = cargar_confirmado(client, "/api/analisis-rapido", data={"ambito": "organizacion"}, files=archivo)
                assert resp.status_code == 200, resp.text
                informe = db.get(models.Informe, resp.json()["informe_id"])
                assert informe.saneamiento["opciones_tecnicas"]["ambito"] == "organizacion"
                assert informe.dominio == "general"
            finally:
                jobs.wake_worker = original
    finally:
        engine.dispose()
        deregister(JSONB)


def test_la_pantalla_de_carga_pregunta_el_ambito_y_lo_envia():
    from pathlib import Path
    static = Path(__file__).resolve().parent.parent / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert 'id="opt-ambito"' in html and "¿De quién es el informe?" in html
    assert '<option value="publico" selected>Organismo público</option>' in html
    assert 'formData.append("ambito", optAmbito?.value || "publico")' in js


def test_los_totales_no_cuentan_como_un_egreso_mas(en_ambito):
    en_ambito(ambito.ORGANIZACION)
    datos = [{"Rubro": "Ventas", "Presupuesto": 100, "Real": 120},
             {"Rubro": "Costo de mercadería", "Presupuesto": 50, "Real": 60},
             {"Rubro": "Gastos de administración", "Presupuesto": 20, "Real": 20},
             {"Rubro": "Total egresos", "Presupuesto": 70, "Real": 95}]
    desvio = next(h for h in ajedrecista.imposibilidad(datos) if h["evidencia"]["regla"] == "gasto_real_supera_presupuesto")
    assert [m["rubro"] for m in desvio["evidencia"]["muestras"]] == ["Costo de mercadería"]


def test_el_conciliador_no_usa_etapas_publicas_en_una_organizacion(en_ambito):
    from services.lentes import conciliador
    datos = [{"Inciso": "1", "Crédito vigente": 100, "Devengado": 130}]
    en_ambito(ambito.PUBLICO)
    assert conciliador._nombre_columnas_presupuesto(datos)
    en_ambito(ambito.ORGANIZACION)
    assert conciliador._nombre_columnas_presupuesto(datos) == {}


def test_el_reporte_no_habla_como_si_toda_organizacion_fuera_un_organismo():
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent / "services"
    textos = (raiz / "reportes" / "markdown.py").read_text(encoding="utf-8") + (raiz / "lentes" / "conciliador.py").read_text(encoding="utf-8")
    for frase in ("no sustituye la decisión institucional", "conveniencia institucional",
                  "políticamente neutral", "actualización presupuestaria posterior"):
        assert frase not in textos, frase


def test_la_carga_por_api_acepta_el_ambito():
    import pydantic

    import schemas
    base = {"area_id": 1, "periodo": "2026", "datos": [{"total": 1}]}
    assert schemas.InformeCreate(**base).ambito == "publico"
    assert schemas.InformeCreate(**base, ambito="organizacion").ambito == "organizacion"
    try:
        schemas.InformeCreate(**base, ambito="otro")
        raise AssertionError("debía rechazarse")
    except pydantic.ValidationError:
        pass
