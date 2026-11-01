"""Corte 0.8.0: identidad propia en todas las superficies y regresiones que antes vivían dentro de otras pruebas."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user, login_html
from database import get_db
from routers import proyectos_ia
from services.reportes import markdown as reportes
from versiones import ANALYSIS_VERSION, API_VERSION, APP_VERSION, DOCUMENT_VERSION

STATIC = Path(__file__).resolve().parents[1] / "static"
FRASE = "Una segunda lectura antes de decidir"


def test_versiones_del_corte_082_conservan_documento_y_contrato():
    assert APP_VERSION == "0.10.64"  # nuevo corte: Python 3.12 y dependencias sin avisos de seguridad (motor sin cambios)
    assert DOCUMENT_VERSION == "9.3"  # numeración de la serie en Zenodo, independiente de la aplicación
    assert ANALYSIS_VERSION == "multilente-0.10.61" and API_VERSION == "0.4.3"


def test_acceso_y_aplicacion_se_presentan_como_producto_no_como_curso():
    acceso = login_html()
    assert "<h1>Gobernanza Multilente</h1>" in acceso and FRASE in acceso
    assert "algo que se puede comprobar" in acceso
    assert "método del curso" not in acceso and "Curso de IA aplicada" not in acceso
    app = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "<h1>Gobernanza Multilente</h1>" in app and FRASE in app
    assert "De los principios de gobernanza a algo que se puede comprobar." in app and "paraguas del curso" not in app


def test_una_sola_familia_de_color_en_aplicacion_y_reportes():
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "--azul-500: #b01c2e;" in css and "#1f4d78" not in css
    fuente = Path(reportes.__file__).read_text(encoding="utf-8")
    assert 'navy = colors.HexColor("#B01C2E")' in fuente and "#2F70E8" not in fuente


def test_reportes_pdf_se_generan_y_llevan_la_firma_en_el_pie():
    fuente = Path(reportes.__file__).read_text(encoding="utf-8")
    assert f'" · {FRASE}"' in fuente
    pdf = reportes.render_reporte_pdf("# Reporte de prueba\n\nTexto de control.")
    assert pdf.startswith(b"%PDF") and len(pdf) > 1500


def test_entregado_exige_entrega_final_o_aportes_propios(monkeypatch):
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    monkeypatch.setattr(proyectos_ia, "_registrar_aprendizajes_auto", lambda *a, **k: None)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(models.Usuario(id=1, email="p@example.test", nombre="P", password_hash="x", rol="analista"))
    db.add(models.ProyectoIA(id=1, usuario_id=1, titulo="Caso", estado="en_proceso"))
    db.commit()
    app = FastAPI()
    app.include_router(proyectos_ia.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
    client = TestClient(app)
    vacio = client.patch("/proyectos-ia/mio", json={"estado": "entregado", "entrega_final": ""})
    assert vacio.status_code == 422 and db.get(models.ProyectoIA, 1).estado == "en_proceso"
    db.add(models.MensajeProyectoIA(proyecto_id=1, remitente="participante", contenido="Mi propuesta conversada"))
    db.commit()
    db.expire_all()
    assert client.patch("/proyectos-ia/mio", json={"estado": "entregado", "entrega_final": ""}).status_code == 200


def test_predevolucion_muestra_fecha_y_avisa_si_quedo_desactualizada():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    pre = js.split("function renderPredevolucionIA", 1)[1].split("\n}\n", 1)[0]
    assert "fmtFecha(pre.creado_en)" in pre and "puede no reflejar la versión actual" in pre
