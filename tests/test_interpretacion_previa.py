"""Contrato del flujo solicitado: interpretar, confirmar y recién entonces controlar."""
import io
import json
from types import SimpleNamespace

import openpyxl
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles, deregister
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from core.auth import get_current_user
from database import get_db
from routers import carga_rapida, informes
from services import interpretacion_previa as ip
from services import jobs, lector_mapa
from tests.flujo_confirmado import terminar_lectura

# La rápida es la opción por defecto y no tiene interpretación previa: estas pruebas son de la profunda.
PROFUNDA = {"modo_revision": "profunda"}


def lector(proveedor, prompt):
    material = json.loads(prompt.split("\nDATOS\n", 1)[1].rsplit("\nFIN", 1)[0])
    cols = material["columnas"]
    tipo = "pagos" if any("pago" in v.lower() for v in cols.values()) else "presupuesto"
    return dict(institucion="universidad", regimen="publico", tipo=tipo, eje="serie_filas", descripcion="Presupuesto de una universidad",
                roles={k: "fecha_operacion" if "fecha" in v.lower() else "periodo_serie" if "mes" in v.lower()
                       else "importe" if any(x in v.lower() for x in ("importe", "credito", "devengado", "pagado")) else "categoria"
                       for k, v in cols.items()}, fuentes=list(cols)[:3], relaciones=[]), "modelo-prueba"


def caso(n=6):
    datos = [{"Mes": "2026-01", "credito_vigente": 100, "devengado": 80} for _ in range(n)]
    reporte = {"archivos_origen": ["a.csv"]}
    leidos = [("a.csv", b"original exacto")]
    r = ip.interpretar(datos, reporte, leidos, {}, 1, fn=lector, proveedoras=["gpt", "gemini", "deepseek"])
    return datos, reporte, leidos, r


@pytest.mark.parametrize("v", [2021, 1900.0, "(1.234)", "1.234 (p)", "$ 1.500", "12,5 %", "año 2021", "1.2e5"])
def test_ninguna_cifra_del_documento_llega_al_modelo(v):
    assert not any(c.isdigit() for c in ip.ciego(v))


def test_dos_proveedores_distintos_y_fuentes_reales():
    datos, reporte, leidos, r = caso()
    assert r["cuadros"][0]["propuesta"]["tipo"] == "presupuesto"
    repetido = ip.interpretar(datos, reporte, leidos, {}, 1, fn=lector, proveedoras=["gpt", "gpt"])
    assert repetido["cuadros"][0]["propuesta"]["tipo"] == "desconocido"
    def invalido(p, prompt):
        v, m = lector(p, prompt)
        v["fuentes"] = ["ZZ999"]
        return v, m
    malo = ip.interpretar(datos, reporte, leidos, {}, 1, fn=invalido, proveedoras=["gpt", "gemini"])
    assert malo["cuadros"][0]["propuesta"]["tipo"] == "desconocido"
    assert all(r["error"] for r in malo["cuadros"][0]["lecturas"].values())


def test_respuesta_invalida_se_reintenta_y_explica_si_sigue_invalida():
    datos, reporte, leidos, _ = caso()
    llamados = []

    def lectura(proveedor, prompt):
        llamados.append((proveedor, prompt))
        respuesta, modelo = lector(proveedor, prompt)
        if proveedor == "gpt" and "CORRECCIÓN DE ESQUEMA" not in prompt:
            respuesta["fuentes"] = ["ZZ999"]
        if proveedor == "deepseek":
            respuesta["fuentes"] = ["ZZ999"]
        return respuesta, modelo

    registro = ip.interpretar(datos, reporte, leidos, {}, 1, fn=lectura,
                              proveedoras=["gpt", "gemini", "deepseek"])
    visibles = ip.publico(registro)["cuadros"][0]
    assert visibles["lecturas_validas"] == 2
    assert visibles["estado_lectoras"]["gpt"] == {"error": None, "reintento_esquema": True}
    assert "referencias inexistentes" in visibles["estado_lectoras"]["deepseek"]["error"]
    assert len(llamados) == 5


def test_relectura_amplia_material_y_no_confirma():
    datos, reporte, leidos, r = caso(400)
    vistos = []
    def captura(p, prompt):
        vistos.append(prompt)
        return lector(p, prompt)
    nuevo = ip.interpretar(datos, reporte, leidos, {}, 1, detallada=True, anterior=r,
                           fn=captura, proveedoras=["gpt", "gemini"])
    assert len(vistos) == 2
    assert nuevo["cuadros"][0]["cobertura"]["filas_presentadas"] > r["cuadros"][0]["cobertura"]["filas_presentadas"]
    assert nuevo["revision"] == 2 and nuevo["estado"] == "pendiente_confirmacion"
    assert "confirmacion" not in nuevo and len(nuevo["historial"]) == 1


def test_titulo_en_notas_es_fuente_valida_y_columnas_no_se_confunden_con_celdas():
    datos, reporte, leidos, _ = caso()
    reporte["grillas_lectura"] = [{"archivo": "a.csv", "hoja": "Datos", "celdas": {
        "A1": "Presupuesto de la Universidad Nacional de Prueba", "A3": "Mes", "B3": "credito_vigente"}}]
    reporte["excel"] = {"bloques": [{"archivo": "a.csv", "hoja": "Datos", "bloque": 1,
        "inicio": 0, "fin": len(datos), "filas": list(range(4, 10)), "encabezados": [3],
        "columnas": {"Mes": "A", "credito_vigente": "B", "devengado": "C"}}]}
    def con_titulo(p, prompt):
        material = json.loads(prompt.split("\nDATOS\n", 1)[1].rsplit("\nFIN", 1)[0])
        assert "A1" not in material["celdas"]
        assert any(n["celda"] == "A1" for n in material["notas"])
        assert all(c.startswith("col_") for c in material["columnas"])
        r, m = lector(p, prompt)
        r["fuentes"] = ["A1"]
        return r, m
    r = ip.interpretar(datos, reporte, leidos, {}, 1, fn=con_titulo, proveedoras=["gpt", "deepseek"])
    assert r["cuadros"][0]["propuesta"]["tipo"] == "presupuesto"
    assert all(not r.get("error") for r in r["cuadros"][0]["lecturas"].values())


def test_muchas_fuentes_reales_se_acotan_y_una_fuente_inventada_se_descarta_y_se_cuenta():
    cols = {f"col_{i}": f"importe_{i}" for i in range(12)}
    r = dict(institucion="desconocida", regimen="no_determinado", tipo="estadistica", eje="ninguno",
        roles={k: "importe" for k in cols}, fuentes=list(cols), relaciones=[])
    valido = ip._validar(r, cols, set(cols))
    assert len(valido["fuentes"]) == 8 and valido["fuentes_recortadas"] == 4
    r["fuentes"].append("ZZ999")
    con_una_inventada = ip._validar(r, cols, set(cols))
    assert "ZZ999" not in con_una_inventada["fuentes"] and con_una_inventada["fuentes_descartadas"] == 1
    r["fuentes"] = ["ZZ999", "YY1"]
    with pytest.raises(ValueError, match="referencias inexistentes"):
        ip._validar(r, cols, set(cols))


def test_confirmacion_invalida_si_cambia_archivo_usuario_opciones_o_revision():
    datos, _, leidos, r = caso()
    args = dict(usuario_id=1, revision=1, leidos=leidos, datos=datos, opciones={})
    for cambio in ({"usuario_id": 2}, {"revision": 2}, {"leidos": [("a.csv", b"alterado")]}, {"opciones": {"alcance": "otro"}}, {"datos": []}):
        with pytest.raises(HTTPException):
            ip.confirmar(r, **(args | cambio))
    confirmado = ip.confirmar(r, **args)
    informe = SimpleNamespace(datos=datos, saneamiento={ip.CAMPO: confirmado})
    assert ip.exigir(informe)["estado"] == "confirmada"
    confirmado["cuadros"][0]["plan"]["matematico"] = True
    with pytest.raises(HTTPException):
        ip.exigir(informe)


def test_mismos_datos_otro_significado_cambia_controles_y_conserva_propuesta():
    datos, _, leidos, r = caso()
    u = r["cuadros"][0]
    cambio = {u["id"]: {"tipo": "pagos", "eje": "operaciones", "roles": {"Mes": "fecha_operacion", "credito_vigente": "importe", "devengado": "importe"}}}
    args = dict(usuario_id=1, revision=1, leidos=leidos, datos=datos, opciones={})
    a, b = ip.confirmar(r, **args), ip.confirmar(r, correcciones=cambio, **args)
    assert a["cuadros"][0]["plan"]["cronista"] and not a["cuadros"][0]["plan"]["matematico"]
    assert not b["cuadros"][0]["plan"]["cronista"] and b["cuadros"][0]["plan"]["matematico"]
    assert b["cuadros"][0]["propuesta"]["tipo"] == "presupuesto"
    assert b["cuadros"][0]["origen"] == "correccion_humana"


def test_traza_distingue_control_ejecutado_de_seleccionado():
    confirmado = {"tipo": "pagos", "institucion": "organismo_publico", "regimen": "publico",
                  "eje": "operaciones", "roles": {"Fecha": "fecha_operacion", "Importe": "importe"}}
    unidad = {"plan": ip.plan(confirmado)}
    traza = ip.trazabilidad_controles(unidad, {"matematico": {"estado": "evaluado"},
                                             "ajedrecista": {"estado": "no_evaluable", "motivo": "Sin importes comparables"}},
                                      modulo_tabular=True, opciones={"revisar_formulas_excel": False})
    assert traza["matematico"]["estado"] == "ejecutado"
    assert traza["ajedrecista"]["estado"] == "no_evaluable"
    assert traza["cronista"]["estado"] == "no_aplicable"
    assert traza["tabular"]["estado"] == "modulo_ejecutado"
    assert traza["relaciones"]["estado"] == "sin_traza_de_ejecucion"
    assert traza["formulas"]["estado"] == "no_solicitado"


def test_fecha_de_pago_no_apaga_benford_y_serie_si(monkeypatch):
    from services.lentes import matematico
    datos = [{"fecha": "2026-01-01", "importe": i * 1000 + 1} for i in range(100)]
    llamadas = []
    monkeypatch.setattr(matematico, "_benford_columna", lambda ds, col: llamadas.append(col))
    matematico.analizar(datos, roles={"fecha": "fecha_operacion", "importe": "importe"})
    assert llamadas == ["importe"]
    llamadas.clear()
    matematico.analizar(datos, roles={"fecha": "periodo_serie", "importe": "importe"})
    assert not llamadas


def test_contexto_confirmado_gobierna_reglas_presupuestarias_sobre_los_mismos_datos():
    import datetime

    from services.lentes import _ejecutar_unidad
    datos = [{"periodo": f"2026-{m:02d}", "credito_vigente": 100, "devengado": 180} for m in range(1, 7)]
    def correr(tipo):
        interpretada = dict(tipo=tipo, institucion="universidad", regimen="publico", eje="serie_filas",
                            roles={"periodo": "periodo_serie", "credito_vigente": "importe", "devengado": "importe"})
        u = {"confirmada": interpretada, "plan": ip.plan(interpretada)}
        informe = SimpleNamespace(id=None, area_id=1, periodo="2026-06", creado_en=datetime.datetime.now(),
                                  dominio=ip.dominio(u), datos=datos, saneamiento={"interpretacion_unidad": u})
        return next(hs for lente, hs in _ejecutar_unidad(None, informe, previos=[]) if lente == "_crudos_finales")
    assert any(h["evidencia"].get("regla") == "devengado_supera_vigente" for h in correr("presupuesto"))
    assert not any(h["evidencia"].get("regla") == "devengado_supera_vigente" for h in correr("estadistica"))


def test_un_libro_mixto_no_desactiva_benford_en_otra_hoja(monkeypatch):
    import datetime

    from services import lentes
    pagos = [{"fecha": f"2026-01-{d % 28 + 1:02d}", "importe": d * 1280 + 100} for d in range(60)]
    serie = [{"periodo": f"2026-{m:02d}", "importe": m * 100} for m in range(1, 13)]
    cuadros = []
    bloques = []
    for i, (hoja, tipo, eje, roles, inicio, fin) in enumerate([
        ("Pagos", "pagos", "operaciones", {"fecha": "fecha_operacion", "importe": "importe"}, 0, 60),
        ("Serie", "estadistica", "serie_filas", {"periodo": "periodo_serie", "importe": "importe"}, 60, 72),
    ], 1):
        c = dict(tipo=tipo, institucion="universidad", regimen="publico", eje=eje, roles=roles)
        cuadros.append(dict(archivo="mixto.xlsx", hoja=hoja, bloque=i, confirmada=c, plan=ip.plan(c)))
        bloques.append(dict(archivo="mixto.xlsx", hoja=hoja, bloque=i, inicio=inicio, fin=fin, filas=[], columnas={}))
    informe = SimpleNamespace(id=None, area_id=1, periodo="2026-12", creado_en=datetime.datetime.now(), dominio="general",
                              datos=pagos + serie, saneamiento={"excel": {"bloques": bloques}, ip.CAMPO: {"cuadros": cuadros}})
    llamadas = []
    monkeypatch.setattr(lentes.matematico, "analizar", lambda datos, **kw: llamadas.append((datos, kw)) or [])
    list(lentes.ejecutar_lentes_stream(None, informe))
    assert len(llamadas) == 1 and llamadas[0][0] == pagos
    assert llamadas[0][1]["roles"]["fecha"] == "fecha_operacion"


def test_una_universidad_privada_no_se_convierte_en_presupuesto_publico():
    c = dict(tipo="presupuesto", institucion="universidad", regimen="privado", eje="ninguno", roles={})
    assert not ip.plan(c)["radiologo"]
    assert ip.dominio({"confirmada": c}) == "general"


@pytest.fixture
def entorno(monkeypatch):
    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(engine)
    monkeypatch.setattr(lector_mapa, "llamar", lector)
    monkeypatch.setattr(lector_mapa, "lectoras_habilitadas", lambda: ["gpt", "gemini", "deepseek"])
    monkeypatch.setattr(jobs, "wake_worker", lambda: None)
    with Session(engine) as db:
        for i in (1, 2):
            db.add(models.Usuario(id=i, email=f"persona{i}@example.test", nombre="Persona", password_hash="x", rol="analista"))
        db.commit()
        app = FastAPI()
        app.include_router(carga_rapida.router, prefix="/api")
        app.include_router(informes.router, prefix="/api")
        quien = {"id": 1}
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: db.get(models.Usuario, quien["id"])
        with TestClient(app) as client:
            yield client, db, quien
    engine.dispose()
    deregister(JSONB)


def archivo():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Presupuesto"
    ws.append(["Mes", "credito_vigente", "devengado", "pagado"])
    for i in range(1, 7):
        ws.append([f"2026-{i:02d}", 1000, 800 if i != 4 else 1800, 700])
    salida = io.BytesIO()
    wb.save(salida)
    return [("archivos", ("Universidad.xlsx", salida.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]


def test_ningun_control_antes_de_confirmar_y_replay_rechazado(entorno, monkeypatch):
    from services import controles_excel, formula_integridad, pdf_controles
    client, db, quien = entorno
    eventos = []
    original = controles_excel.analizar
    def control(*args, **kw):
        assert ip.actual()["estado"] == "confirmada"
        eventos.append("tabular")
        return original(*args, **kw)
    monkeypatch.setattr(controles_excel, "analizar", control)
    for modulo, nombre in ((formula_integridad, "analizar_archivos"), (formula_integridad, "analizar_matematico_archivos"), (pdf_controles, "analizar"), (pdf_controles, "analizar_coherencia_visual")):
        def registrar(*args, **kw):
            assert ip.actual()["estado"] == "confirmada"
            eventos.append("otro")
            return []
        monkeypatch.setattr(modulo, nombre, registrar)
    f = archivo()
    opciones = {"notificar": "false", "revisar_formulas_excel": "true", "modo_revision": "profunda"}
    primera = client.post("/api/analisis-rapido", data=opciones, files=f)
    assert primera.status_code == 200, primera.text
    p = primera.json()
    assert p["estado"] == "interpretando" and not eventos
    assert db.query(models.AnalysisJob).one().resultado["fase"] == "interpretacion"
    p = terminar_lectura(client, p)
    assert p["estado"] == "pendiente_confirmacion" and not eventos
    assert client.post(f"/api/informes/{p['informe_id']}/analizar").status_code == 409
    assert client.post(f"/api/informes/{p['informe_id']}/analizar/stream").status_code == 409
    confirmacion = opciones | {"interpretacion_accion": "confirmar", "interpretacion_id": p["informe_id"], "interpretacion_revision": 1}
    quien["id"] = 2
    assert client.post("/api/analisis-rapido", data=confirmacion, files=f).status_code == 404
    quien["id"] = 1
    segunda = client.post("/api/analisis-rapido", data=confirmacion, files=f)
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["job"]["estado"] == "pendiente" and eventos
    assert db.query(models.AnalysisJob).count() == 2  # lectura finalizada y análisis pendiente
    antes = list(eventos)
    assert client.post("/api/analisis-rapido", data=confirmacion, files=f).status_code == 409
    assert eventos == antes


def test_relectura_endpoint_invalida_revision_anterior(entorno):
    client, db, _ = entorno
    f = archivo()
    p = terminar_lectura(client, client.post("/api/analisis-rapido", data=PROFUNDA, files=f).json())
    siguiente = {**PROFUNDA, "interpretacion_accion": "detallada", "interpretacion_id": p["informe_id"], "interpretacion_revision": 1}
    respuesta = client.post("/api/analisis-rapido", data=siguiente, files=f)
    assert respuesta.status_code == 200, respuesta.text
    nueva = terminar_lectura(client, respuesta.json())
    assert nueva["interpretacion"]["revision"] == 2
    siguiente["interpretacion_accion"] = "confirmar"
    assert client.post("/api/analisis-rapido", data=siguiente, files=f).status_code == 409
    assert all(j.resultado["fase"] == "interpretacion" for j in db.query(models.AnalysisJob).all())


def test_carga_json_tambien_exige_interpretacion_y_confirmacion(entorno):
    client, db, _ = entorno
    db.add(models.Area(id=1, nombre="Area", codigo="A"))
    db.commit()
    r = client.post("/api/informes", json={"area_id": 1, "periodo": "2026-01",
        "datos": [{"Mes": "Enero", "credito_vigente": 1000, "devengado": 500}]})
    assert r.status_code in {200, 201}, r.text
    ident = r.json()["id"]
    assert client.post(f"/api/informes/{ident}/analizar").status_code == 409
    p = client.post(f"/api/informes/{ident}/interpretacion", json={"accion": "preparar"})
    assert p.status_code == 200, p.text
    assert p.json()["estado"] == "interpretando"
    assert client.post(f"/api/informes/{ident}/interpretacion", json={"accion": "confirmar", "revision": 1}).status_code == 409
    propuesta = terminar_lectura(client, p.json())
    assert propuesta["estado"] == "pendiente_confirmacion"
    confirmacion = client.post(f"/api/informes/{ident}/interpretacion", json={"accion": "confirmar", "revision": 1})
    assert confirmacion.status_code == 200, confirmacion.text
    db.expire_all()
    assert ip.exigir(db.get(models.Informe, ident))["estado"] == "confirmada"


def test_conversion_interna_no_cambia_huella_original_ni_impide_confirmar(entorno, monkeypatch):
    import hashlib
    import zipfile

    from services import carga_archivos
    client, db, _ = entorno
    conversiones = []
    def convertir(bruto):
        copia = io.BytesIO(bruto)
        with zipfile.ZipFile(copia, "a") as z:
            z.comment = f"conversion {len(conversiones)}".encode()
        conversiones.append(copia.getvalue())
        return conversiones[-1]
    monkeypatch.setattr(carga_archivos, "libro_transicional", convertir)
    f = archivo()
    p = terminar_lectura(client, client.post("/api/analisis-rapido", data=PROFUNDA, files=f).json())
    r = client.post("/api/analisis-rapido", files=f, data={**PROFUNDA, "interpretacion_accion": "confirmar",
        "interpretacion_id": p["informe_id"], "interpretacion_revision": 1})
    assert r.status_code == 200, r.text
    db.expire_all()
    meta = db.get(models.Informe, p["informe_id"]).saneamiento
    esperado = hashlib.sha256(f[0][1][1]).hexdigest()
    assert meta["proveniencia"]["fuentes"][0]["sha256_bruto"] == esperado
    assert meta[ip.CAMPO]["archivos"][0]["sha256"] == esperado
    assert conversiones[0] != conversiones[1]


def test_worker_recupera_lectura_interrumpida_sin_ejecutar_controles(entorno, monkeypatch):
    client, db, _ = entorno
    p = client.post("/api/analisis-rapido", data=PROFUNDA, files=archivo()).json()
    ident = p["informe_id"]
    trabajo = db.query(models.AnalysisJob).one()
    trabajo.estado = "procesando"
    db.commit()
    monkeypatch.setattr(jobs, "SessionLocal", lambda: Session(db.get_bind()))
    def prohibido(*args, **kw):
        raise AssertionError("El worker de lectura no puede analizar")
    monkeypatch.setattr(jobs, "ejecutar_analisis_stream", prohibido)
    jobs.recover_processing_jobs()
    assert jobs._process_one()
    db.expire_all()
    assert db.get(models.Informe, ident).saneamiento[ip.CAMPO]["estado"] == "pendiente_confirmacion"
    assert db.query(models.AnalysisJob).one().resultado["_metricas"]["controles_ejecutados"] == 0
    assert db.query(models.AnalysisJob).one().estado == "finalizado"
