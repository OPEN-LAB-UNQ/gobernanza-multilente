"""La pared entre la capa exploratoria y el protocolo B-1/R-1.

La capa exploratoria (services/exploratorio.py) produce hipotesis no
validadas. Estas pruebas verifican que esa salida nunca alimente controles,
nunca produzca anexos ni se incorpore automáticamente a evidencia o emisión.
No comprueban la veracidad semántica de texto libre copiado por una persona.

La capa exploratoria está implementada. Estas pruebas protegen su separación
de las evaluaciones institucionales ante cambios futuros.
"""
from __future__ import annotations

import ast
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

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

HIPOTESIS_TEXTO = "hipotesis exploratoria de prueba: correlacion inesperada entre X e Y"
MODELO_EXPLORADOR = "gpt-4.1-mini-explorador-de-prueba"


def _engine_sqlite():
    @compiles(JSONB, "sqlite")
    def _json_sqlite(element, compiler, **kw):  # noqa: ANN001
        return "JSON"

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    tablas = [
        models.Usuario.__table__, models.Area.__table__, models.Informe.__table__,
        models.Devolucion.__table__, models.DecisionDirector.__table__, models.Hallazgo.__table__,
        models.InterpretacionModelo.__table__, models.HipotesisExploratoria.__table__,
        models.ProyectoIA.__table__, models.ActivityEvent.__table__,
        models.VersionProtocolo.__table__, models.DefinicionControl.__table__,
        models.EvaluacionCertificacion.__table__, models.ResultadoControl.__table__,
        models.EvidenciaControl.__table__, models.HistorialResultadoControl.__table__,
        models.SelloCertificacion.__table__,
    ]
    models.Base.metadata.create_all(engine, tables=tablas)
    return engine


def _control(codigo, lente=None):
    return SimpleNamespace(codigo=codigo, nombre=codigo, lente=lente)


def _resultado(codigo, lente=None, estado="conforme", aplica=True):
    return SimpleNamespace(
        control=_control(codigo, lente),
        estado=estado,
        aplica=aplica,
        justificacion_aplicabilidad=None,
        evidencias=[SimpleNamespace(descripcion=f"evidencia {codigo}")],
        observacion=None,
        accion_requerida=None,
        reevaluado_en=None,
    )


def _evaluacion_b1(**overrides):
    resultados = [
        _resultado("B1-04", "ajedrecista"),
        _resultado("B1-05", "cronista"),
        _resultado("B1-06", "matematico"),
        _resultado("B1-07", "orquesta"),
    ]
    base = dict(
        protocolo=SimpleNamespace(
            codigo="B-1", version="1.1", nombre="Gobernanza Multilente B-1",
            tipo_objeto="informe", model_policy={},
        ),
        informe=SimpleNamespace(hallazgos=[]),
        resultados=resultados,
        manifiesto_modelos=[],
        hash_objeto="hash-actual",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# 1. Ninguna hipotesis exploratoria aparece en la salida de los anexos.


def test_hipotesis_exploratoria_no_aparece_en_anexos_lentes():
    engine = _engine_sqlite()
    try:
        with Session(engine) as db:
            area = models.Area(id=1, nombre="Prueba", codigo="PRUEBA")
            db.add(area)
            db.flush()
            informe = models.Informe(
                id=1, area_id=area.id, periodo="2026-09", dominio="general",
                modo="intraarea", datos=[{"total": 10}], saneamiento={},
            )
            db.add(informe)
            db.flush()
            db.add(models.HipotesisExploratoria(
                informe_id=informe.id,
                tipo_pista="preguntas_no_formuladas",
                texto_hipotesis=HIPOTESIS_TEXTO,
                modelo=MODELO_EXPLORADOR,
                version_modelo="v-prueba",
                estado="HIPOTESIS_NO_VALIDADA",
            ))
            db.commit()
            db.refresh(informe)

            evaluacion = _evaluacion_b1(informe=informe)
            anexos = certificaciones.anexos_lentes(evaluacion)
            anexos_publicos = certificaciones.anexos_lentes_publicos(evaluacion)
    finally:
        engine.dispose()
        deregister(JSONB)

    serializado = json.dumps(anexos, default=str) + json.dumps(anexos_publicos, default=str)
    assert HIPOTESIS_TEXTO not in serializado
    assert MODELO_EXPLORADOR not in serializado
    assert "HIPOTESIS_NO_VALIDADA" not in serializado


# 2. El estado y la evidencia inicial de B-1 no dependen de lo que dijo el explorador.


def test_estado_y_evidencia_inicial_b1_no_dependen_del_explorador():
    engine = _engine_sqlite()
    try:
        with Session(engine) as db:
            area = models.Area(id=1, nombre="Prueba", codigo="PRUEBA")
            db.add(area)
            db.flush()
            informe = models.Informe(
                id=1, area_id=area.id, periodo="2026-09", dominio="general",
                modo="intraarea", datos=[{"total": 10}], saneamiento={},
            )
            db.add(informe)
            db.flush()
            db.add(models.Devolucion(
                informe_id=informe.id, mensaje="ok", hay_hallazgos=False,
                estado="ENVIADA", cobertura={"lentes": [{"lente": "ajedrecista"}]},
            ))
            db.commit()
            db.refresh(informe)

            control = SimpleNamespace(codigo="B1-04")
            estados_sin = {
                codigo: certificaciones.estado_inicial_b1(SimpleNamespace(codigo=codigo), informe)
                for codigo in ("B1-01", "B1-02", "B1-03", "B1-04", "B1-08", "B1-09", "B1-10")
            }
            evidencia_sin = certificaciones.evidencia_inicial_b1(control, informe)

            db.add(models.HipotesisExploratoria(
                informe_id=informe.id,
                tipo_pista="correlaciones_no_declaradas",
                texto_hipotesis=HIPOTESIS_TEXTO,
                modelo=MODELO_EXPLORADOR,
                version_modelo="v-prueba",
                estado="HIPOTESIS_NO_VALIDADA",
            ))
            db.commit()
            db.refresh(informe)

            estados_con = {
                codigo: certificaciones.estado_inicial_b1(SimpleNamespace(codigo=codigo), informe)
                for codigo in ("B1-01", "B1-02", "B1-03", "B1-04", "B1-08", "B1-09", "B1-10")
            }
            evidencia_con = certificaciones.evidencia_inicial_b1(control, informe)
    finally:
        engine.dispose()
        deregister(JSONB)

    assert estados_sin == estados_con
    assert evidencia_sin == evidencia_con


# 3. El manifiesto de modelos no incluye los modelos usados por el explorador.


def test_manifiesto_modelos_no_incluye_modelos_del_explorador():
    engine = _engine_sqlite()
    try:
        with Session(engine) as db:
            area = models.Area(id=1, nombre="Prueba", codigo="PRUEBA")
            db.add(area)
            db.flush()
            informe = models.Informe(
                id=1, area_id=area.id, periodo="2026-09", dominio="general",
                modo="intraarea", datos=[{"total": 10}], saneamiento={},
            )
            db.add(informe)
            db.flush()
            db.add(models.InterpretacionModelo(
                informe_id=informe.id, modelo="claude", contenido={}, error=None,
            ))
            db.add(models.HipotesisExploratoria(
                informe_id=informe.id,
                tipo_pista="preguntas_no_formuladas",
                texto_hipotesis=HIPOTESIS_TEXTO,
                modelo=MODELO_EXPLORADOR,
                version_modelo="v-prueba",
                estado="HIPOTESIS_NO_VALIDADA",
            ))
            db.commit()
            db.refresh(informe)

            manifiesto = certificaciones.construir_manifiesto_modelos(informe)
    finally:
        engine.dispose()
        deregister(JSONB)

    modelos = {item["modelo"] for item in manifiesto}
    assert MODELO_EXPLORADOR not in modelos
    assert modelos == {"claude"}


# 4. El payload publico de la constancia no contiene ninguna hipotesis exploratoria.


def test_payload_publico_de_constancia_no_contiene_hipotesis_exploratorias():
    @compiles(JSONB, "sqlite")
    def _json_sqlite(element, compiler, **kw):  # noqa: ANN001
        return "JSON"

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    tablas = [
        models.Usuario.__table__, models.Area.__table__, models.Informe.__table__,
        models.HipotesisExploratoria.__table__,
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
            db.add(models.HipotesisExploratoria(
                id=99,
                informe_id=informe.id,
                tipo_pista="preguntas_no_formuladas",
                texto_hipotesis=HIPOTESIS_TEXTO,
                modelo=MODELO_EXPLORADOR,
                version_modelo="v-prueba",
                estado="HIPOTESIS_NO_VALIDADA",
            ))
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
            db.add(models.EvidenciaControl(
                resultado_id=resultado.id, tipo="nota",
                descripcion="evidencia de control", agregado_por_id=admin_a.id,
            ))
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
                client.post("/certificaciones/evaluaciones/1/emitir", json=payload)
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
    finally:
        engine.dispose()
        deregister(JSONB)

    assert HIPOTESIS_TEXTO not in cuerpo
    assert MODELO_EXPLORADOR not in cuerpo
    assert "99" not in json.dumps(publica.json().get("lentes"))
    assert "hipotesis" not in cuerpo.lower()
    assert "HIPOTESIS_NO_VALIDADA" not in cuerpo


# 5. Prueba estructural: ni services/certificaciones.py ni routers/certificaciones.py
#    importan el modulo del explorador. Se resuelve leyendo los imports del
#    archivo, no por convencion.


def _nombres_importados(path: Path) -> set[str]:
    arbol = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module:
                nombres.add(nodo.module)
            nombres.update(alias.name for alias in nodo.names)
    return nombres


def test_certificaciones_no_importa_el_modulo_exploratorio():
    raiz = Path(__file__).resolve().parent.parent
    for archivo in (raiz / "services" / "certificaciones.py", raiz / "routers" / "certificaciones.py"):
        importados = _nombres_importados(archivo)
        ofensores = {
            nombre for nombre in importados
            if nombre == "exploratorio" or nombre.endswith(".exploratorio")
            or nombre == "routers.exploratorio" or nombre == "services.exploratorio"
        }
        assert not ofensores, f"{archivo} importa el modulo exploratorio: {ofensores}"
