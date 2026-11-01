"""0.10.61: ajustes de una auditoría externa de sólo lectura (28/10/2026).

El contador público separa lo cargado de lo revisado; las alertas dicen de dónde viene cada error; /api/health
comprueba la base y la cola; un análisis fallido no muestra el texto de la excepción; un archivo que supera el tope
se rechaza sin leerlo entero; el sondeo dice lo que no puede distinguir y las páginas públicas, qué datos se cargan.
"""
import datetime as dt
import importlib.util
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile

import models
from routers import sistema
from services import jobs, sondeo, uso_publico

RAIZ = Path(__file__).resolve().parents[1]
STATIC = RAIZ / "static"
_spec = importlib.util.spec_from_file_location("alerta_errores_0161", RAIZ / "scripts" / "alerta_errores.py")
alerta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alerta)

# El registro del 27/10/2026: el proveedor reinició el servidor y la migración del arranque encontró la base
# todavía levantándose. El aviso llegó como «fallaron análisis en segundo plano».
ARRANQUE_27_10 = """\
Oct 27 11:14:31 vps alembic[1176]: Traceback (most recent call last):
Oct 27 11:14:31 vps alembic[1176]:   File "/home/gobernanza/venv/lib64/python3.9/site-packages/sqlalchemy/engine/base.py", line 145, in __init__
Oct 27 11:14:31 vps alembic[1176]:     self._dbapi_connection = engine.raw_connection()
Oct 27 11:14:31 vps alembic[1176]: psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed: FATAL:  the database system is starting up
Oct 27 11:14:31 vps alembic[1176]:
Oct 27 11:14:31 vps alembic[1176]: The above exception was the direct cause of the following exception:
Oct 27 11:14:31 vps alembic[1176]:
Oct 27 11:14:31 vps alembic[1176]: Traceback (most recent call last):
Oct 27 11:14:31 vps alembic[1176]:   File "/home/gobernanza/venv/bin/alembic", line 8, in <module>
Oct 27 11:14:31 vps alembic[1176]: sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "localhost" (::1), port 5432 failed: FATAL:  the database system is starting up
Oct 27 11:14:31 vps systemd[1]: gobernanza.service: Failed with result 'exit-code'.
Oct 27 11:14:38 vps systemd[1]: Started Gobernanza - lectura multilente para decision institucional.
Oct 27 11:14:43 vps uvicorn[1992]: INFO:     Application startup complete.
"""


def _traceback(proceso, archivo, error, antes=""):
    lineas = [antes] if antes else []
    lineas += ["Traceback (most recent call last):", f'  File "{archivo}", line 10, in f', "    x()", error]
    return "".join(f"Oct 28 10:00:00 vps {proceso}[10]: {linea}\n" for linea in lineas)


def _sqlite(request):
    @compiles(JSONB, "sqlite")
    def _json_sqlite(element, compiler, **kw):
        return "JSON"

    request.addfinalizer(lambda: deregister(JSONB))
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    request.addfinalizer(engine.dispose)
    return engine


# --- Contador público ---

def test_el_contador_separa_cargados_revisados_y_sin_senales(request):
    with Session(_sqlite(request)) as db:
        db.add_all([models.Usuario(id=1, email="b@t", nombre="B", password_hash="x", rol="analista"),
                    models.Area(id=1, nombre="Area", codigo="A")])
        for i in (1, 2, 3):
            db.add(models.Informe(id=i, area_id=1, usuario_id=1, periodo="2026", dominio="general", datos=[], saneamiento={}))
        db.add(models.Devolucion(informe_id=1, mensaje="sin señales", hay_hallazgos=False))
        db.add(models.Devolucion(informe_id=2, mensaje="con señales", hay_hallazgos=True))
        db.add(models.Hallazgo(informe_id=2, lente="ajedrecista", severidad="alta", descripcion="no cierra"))
        # El 3 espera la confirmación de la lectura previa: está cargado, pero nadie lo revisó todavía.
        db.add(models.Hallazgo(informe_id=3, lente="ajedrecista", severidad="alta", descripcion="sin devolución"))
        db.commit()
        uso = uso_publico.calcular(db)
    assert uso["informes"] == 3 and uso["informes_con_devolucion"] == 2
    assert uso["informes_sin_senales"] == 1 and uso["observaciones"] == 1


# --- Alertas por origen ---

def test_el_arranque_del_27_10_se_avisa_como_arranque_y_no_como_analisis_fallido():
    assert alerta._extraer_fallos_worker(ARRANQUE_27_10) == []
    por_origen = alerta._clasificar(ARRANQUE_27_10)
    assert list(por_origen) == ["arranque"]
    falla, volvio = por_origen["arranque"]
    assert falla.startswith("Oct 27 11:14:31 alembic: sqlalchemy.exc.OperationalError")
    assert falla.endswith("the database system is starting up")
    assert volvio == "Volvió a arrancar: Oct 27 11:14:43."


def test_main_manda_un_solo_aviso_con_el_asunto_del_arranque(tmp_path, monkeypatch):
    enviados = []
    monkeypatch.setattr(alerta, "VAR_DIR", tmp_path)
    monkeypatch.setattr(alerta, "ESTADO_PATH", tmp_path / "ultimo")
    monkeypatch.setattr(alerta, "CAIDA_PATH", tmp_path / "caido")
    monkeypatch.setattr(alerta, "_journal_entre", lambda d, h: ARRANQUE_27_10)
    monkeypatch.setattr(alerta, "_enviar_alerta", lambda lineas, asunto=None, intro=None: enviados.append(asunto))
    monkeypatch.setattr(alerta, "_servicio_activo", lambda: True)
    monkeypatch.setattr(alerta, "_horas_desde_ultimo_backup", lambda ahora: 1.0)
    alerta.main()
    assert enviados == ["Gobernanza: el servicio falló al arrancar"]


def test_un_arranque_que_no_vuelve_lo_dice():
    texto = ARRANQUE_27_10.split("Oct 27 11:14:43")[0]
    assert alerta._clasificar(texto)["arranque"][-1] == "No se vio que volviera a arrancar en esta ventana."


def test_el_traceback_de_un_analisis_fallido_no_se_avisa_dos_veces():
    texto = _traceback("uvicorn", "/home/gobernanza/services/analisis.py", "RuntimeError: boom",
                       antes="ERROR:services.jobs:fallo el analisis del informe 12 (trabajo 40): boom")
    assert len(alerta._extraer_fallos_worker(texto)) == 1
    assert alerta._clasificar(texto) == {}


def test_un_analisis_con_un_error_de_varias_lineas_tampoco_se_avisa_dos_veces():
    # Las excepciones de SQLAlchemy agregan «[SQL: …]» y «(Background on this error at …)» al mensaje.
    antes = "".join(f"Oct 28 10:00:00 vps uvicorn[10]: {linea}\n" for linea in (
        "fallo el analisis del informe 12 (trabajo 40): (psycopg2.OperationalError) server closed the connection",
        "[SQL: SELECT 1]", "(Background on this error at: https://sqlalche.me/e/20/e3q8)"))
    texto = antes + _traceback("uvicorn", "/home/gobernanza/services/analisis.py",
                               "sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) server closed the connection")
    assert len(alerta._extraer_fallos_worker(texto)) == 1
    assert alerta._clasificar(texto) == {}


def test_volvio_se_mira_despues_del_ultimo_arranque_fallido():
    otra_falla = ARRANQUE_27_10.split("Oct 27 11:14:31 vps systemd")[0].replace("11:14:31", "11:20:05")
    assert alerta._clasificar(ARRANQUE_27_10 + otra_falla)["arranque"][-1] == \
        "No se vio que volviera a arrancar en esta ventana."


def test_un_traceback_cortado_no_se_traga_al_siguiente():
    cortado = "".join(f"Oct 28 10:00:00 vps uvicorn[10]: {linea}\n" for linea in (
        "fallo el analisis del informe 12 (trabajo 40): boom", "Traceback (most recent call last):",
        '  File "/home/gobernanza/services/analisis.py", line 10, in f',
        'INFO:     127.0.0.1:5000 - "GET /api/health HTTP/1.1" 200 OK'))
    otro = _traceback("uvicorn", "/home/gobernanza/routers/informes.py", "KeyError: 'celda'")
    assert alerta._clasificar(cortado + otro) == {"otro": ["Oct 28 10:00:00 uvicorn: KeyError: 'celda'"]}
    sin_linea_de_registro = cortado.rsplit("Oct 28", 1)[0]
    assert alerta._clasificar(sin_linea_de_registro + otro) == {"otro": ["Oct 28 10:00:00 uvicorn: KeyError: 'celda'"]}


def test_el_traceback_de_un_500_no_se_avisa_dos_veces_y_uno_irreconocible_se_avisa_igual():
    http = _traceback("uvicorn", "/home/gobernanza/routers/informes.py", "KeyError: 'x'",
                      antes="ERROR:    Exception in ASGI application")
    assert alerta._clasificar(http) == {}
    assert alerta._clasificar("sep 29 uvicorn: Traceback (most recent call last):\n") == {
        "otro": ["sep 29 uvicorn: Traceback (most recent call last):"]}


def test_un_error_de_base_envuelto_en_otra_excepcion_es_de_base():
    texto = (_traceback("uvicorn", "/home/gobernanza/routers/informes.py", "sqlalchemy.exc.OperationalError: server closed")
             + "Oct 28 10:00:00 vps uvicorn[10]: The above exception was the direct cause of the following exception:\n"
             + _traceback("uvicorn", "/home/gobernanza/routers/informes.py", "RuntimeError: no se pudo guardar"))
    assert alerta._clasificar(texto) == {"base": ["Oct 28 10:00:00 uvicorn: RuntimeError: no se pudo guardar"]}


def test_base_proveedor_y_otros_se_separan():
    base = _traceback("uvicorn", "/home/gobernanza/routers/informes.py",
                      "sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) server closed the connection")
    proveedor = _traceback("uvicorn", "/home/gobernanza/venv/lib64/python3.9/site-packages/httpx/_client.py",
                           "httpx.ReadTimeout: timed out")
    otro = _traceback("uvicorn", "/home/gobernanza/routers/informes.py", "KeyError: 'celda'")
    por_origen = alerta._clasificar(base + proveedor + otro)
    assert sorted(por_origen) == ["base", "otro", "proveedor"]
    assert por_origen["proveedor"] == ["Oct 28 10:00:00 uvicorn: httpx.ReadTimeout: timed out"]
    assert por_origen["otro"] == ["Oct 28 10:00:00 uvicorn: KeyError: 'celda'"]
    assert set(alerta.ORIGENES) == {"arranque", "base", "proveedor", "otro"}


# --- /api/health ---

def _salud(monkeypatch, trabajos):
    def consulta():
        if isinstance(trabajos, Exception):
            raise trabajos
        return trabajos
    monkeypatch.setattr(sistema, "_trabajos_en_cola", consulta)
    app = FastAPI()
    app.include_router(sistema.router)
    return TestClient(app).get("/api/health")


def test_health_dice_503_si_la_base_no_responde(monkeypatch):
    r = _salud(monkeypatch, RuntimeError("sin base"))
    assert r.status_code == 503 and r.json() == {"status": "error", "base": "sin respuesta"}


def test_health_ok_y_cola_trabada(monkeypatch):
    r = _salud(monkeypatch, [])
    assert r.status_code == 200 and r.json() == {"status": "ok", "base": "ok", "cola": "ok"}
    hace_diez = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(minutes=10)
    r = _salud(monkeypatch, [(7, "pendiente", hace_diez, None)])
    assert r.status_code == 200 and r.json() == {"status": "degradado", "base": "ok", "cola": "trabada"}


def test_health_consulta_la_cola_en_la_base(monkeypatch, request):
    factory = sessionmaker(bind=_sqlite(request))
    monkeypatch.setattr(sistema, "SessionLocal", factory)
    with factory() as db:
        db.add_all([models.Usuario(id=1, email="b@t", nombre="B", password_hash="x", rol="analista"),
                    models.Area(id=1, nombre="Area", codigo="A")])
        db.add(models.Informe(id=1, area_id=1, usuario_id=1, periodo="2026", dominio="general", datos=[], saneamiento={}))
        db.add(models.AnalysisJob(id=5, informe_id=1, usuario_id=1, estado="pendiente", modelos=[]))
        db.add(models.AnalysisJob(id=6, informe_id=1, usuario_id=1, estado="finalizado", modelos=[]))
        db.commit()
    assert [t[:2] for t in sistema._trabajos_en_cola()] == [(5, "pendiente")]


# --- Error de análisis ---

def test_un_analisis_fallido_no_muestra_ni_manda_el_texto_de_la_excepcion(monkeypatch, request):
    factory = sessionmaker(bind=_sqlite(request))
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    correos = []
    monkeypatch.setattr(jobs, "enviar_analisis_finalizado", lambda *a, **k: correos.append(a) or ("enviada", None))
    with factory() as db:
        db.add(models.Usuario(id=1, email="a@test", nombre="A", password_hash="x", rol="analista"))
        db.add(models.Area(id=1, nombre="Área de prueba", codigo="prueba"))
        db.add(models.Informe(id=1, usuario_id=1, area_id=1, periodo="2026-10", dominio="general",
                              modo="intraarea", datos=[{"x": 1}], saneamiento={}))
        db.add(models.AnalysisJob(id=3, informe_id=1, usuario_id=1, estado="pendiente", modelos=[],
                                  notify_email="a@test"))
        db.commit()

    def analisis_que_falla(db, informe, modelos):
        raise TypeError("'modelos_consultados' is an invalid keyword argument for Triangulacion")
        yield

    monkeypatch.setattr(jobs, "ejecutar_analisis_stream", analisis_que_falla)
    assert jobs._process_one() is True
    with factory() as db:
        job = db.get(models.AnalysisJob, 3)
        assert job.estado == "error" and job.error == jobs.error_interno(3)
    assert "trabajo 3" in job.error and "modelos_consultados" not in job.error
    assert correos == [("a@test", 1, "error", jobs.error_interno(3))]


# --- Tope de carga ---

def _cargar(monkeypatch, request, tamano, tope=10):
    from core.auth import get_current_user
    from database import get_db
    from routers import carga_rapida

    lecturas = []
    leer = UploadFile.read

    async def leer_contando(self, size=-1):
        lecturas.append(size)
        return await leer(self, size)

    monkeypatch.setattr(UploadFile, "read", leer_contando)
    monkeypatch.setattr(carga_rapida, "MAX_BYTES_POR_ARCHIVO", tope)
    monkeypatch.setattr(jobs, "wake_worker", lambda: None)
    with Session(_sqlite(request)) as db:
        db.add(models.Usuario(id=1, email="a@test", nombre="A", password_hash="x", rol="analista"))
        db.commit()
        app = FastAPI()
        app.include_router(carga_rapida.router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, 1)
        r = TestClient(app).post("/api/analisis-rapido", data={"notificar": "false"},
                                 files=[("archivos", ("a.csv", b"x" * tamano, "text/csv"))])
    return r, lecturas


def test_un_archivo_mas_grande_que_el_tope_se_rechaza_sin_leerlo(monkeypatch, request):
    r, lecturas = _cargar(monkeypatch, request, 11)
    assert r.status_code == 422 and "'a.csv' supera el máximo permitido" in r.json()["detail"]
    assert lecturas == []


def test_un_archivo_dentro_del_tope_se_lee_con_limite(monkeypatch, request):
    _, lecturas = _cargar(monkeypatch, request, 10)
    assert lecturas and lecturas[0] == 11 and -1 not in lecturas


# --- Sondeo y textos públicos ---

def test_el_sondeo_dice_que_no_puede_distinguir_la_forma_del_cuadro_de_un_error_repetido():
    def h(hoja, celda):
        ev = {"regla": "signo_aislado", "hoja": hoja, "archivo_origen": "a.xlsx", "celda": celda}
        return {"lente": "ajedrecista", "severidad": "alta", "descripcion": "señal", "evidencia": ev}

    en_una_hoja = sondeo.aplicar([h("Cuadro 1", c) for c in ("B5", "D9", "F14")], lambda x: True)
    en_hojas = sondeo.aplicar([h(f"Cuadro {i}", "B5") for i in (1, 2, 3)], lambda x: True)
    assert "no se puede distinguir sin mirarlo" in en_una_hoja[0]["motivo"]
    assert en_hojas[0]["motivo"].endswith(sondeo.REPETIDO_EN_HOJAS)
    for abst in en_una_hoja + en_hojas:
        assert "no un error" not in abst["motivo"] and "es más probable" not in abst["motivo"]


def test_las_paginas_dicen_que_datos_se_cargan_y_que_la_devolucion_es_un_borrador():
    presentacion = (STATIC / "presentacion.html").read_text(encoding="utf-8")
    ficha = (STATIC / "detalle-body.html").read_text(encoding="utf-8")
    assert "Está pensada para datos agregados: no se cargan datos de personas." in presentacion
    assert "ese filtro no las encuentra todas" in presentacion
    assert "La devolución automática llega antes de ese paso: es un borrador para quien la recibe." in presentacion
    assert "No se cargan datos personales;" in presentacion
    for viejo in ("nunca con información de personas", "pasa por cuatro verbos humanos antes de salir",
                  "sirve para informes sensibles", "No se cargan datos personales ni sensibles", "Lo que marca vale la pena"):
        assert viejo not in presentacion and viejo not in ficha
    assert "No es una tasa de acierto" in presentacion and "no es una tasa de acierto" in ficha
    assert "como el sondeo no puede distinguirlos, esa parte se declara" in ficha
