"""Preparación explícita del nuevo recorrido en regresiones del motor.

Se simulan sólo respuestas externas. Carga, validación, confirmación, selección,
controles y persistencia son reales. No sustituye exigir() ni confirma en producción.
Las pruebas de la barrera usan TestClient directamente, sin este ayudante.
"""
import json
import re
import types
from unittest.mock import patch

import models
from database import get_db
from services import interpretacion_previa as ip
from services import jobs, lector_mapa


def respuesta_fixture(proveedor, prompt):
    material = json.loads(prompt.split("\nDATOS\n", 1)[1].rsplit("\nFIN", 1)[0])
    cols = material["columnas"]
    texto = " ".join(cols.values()).lower()
    tipo = "presupuesto" if re.search(r"credito|crédito|devengad|presupuest", texto) else "servicios" if "consulta" in texto else "pagos" if re.search(r"pago|factura", texto) else "estadistica"
    periodo = bool(re.search(r"per[ií]odo|mes|año|anio|trimestre|bimestre", texto))
    eje = "serie_filas" if periodo else "serie_columnas" if len(material.get("formato_periodo_encabezados", {})) >= 2 else "operaciones" if tipo == "pagos" else "ninguno"
    roles = {}
    for k, c in cols.items():
        t = c.lower()
        roles[k] = "periodo_serie" if re.search(r"per[ií]odo|mes|año|anio", t) else "fecha_operacion" if "fecha" in t else "porcentaje" if re.search(r"%|porcent|ponder|tasa", t) else "identificador" if re.search(r"c[oó]digo|^id$", t) else "importe" if re.search(r"importe|credito|crédito|devengad|pagad|monto|gasto|ingreso", t) else "cantidad"
    return dict(institucion="organismo_publico", regimen="publico", tipo=tipo, eje=eje,
                descripcion="Interpretación simulada para el caso de regresión", roles=roles, fuentes=list(cols)[:3], relaciones=[]), "proveedor-simulado"


def cargar_confirmado(client, ruta, *, data=None, files=None, **kw):
    opciones = dict(data or {})
    # Este recorrido es el de la revisión profunda; la rápida (por defecto) no tiene interpretación que confirmar.
    opciones.setdefault("modo_revision", "profunda")
    with patch.object(lector_mapa, "llamar", respuesta_fixture), patch.object(lector_mapa, "lectoras_habilitadas", lambda: ["gpt", "gemini", "deepseek"]):
        inicial = client.post(ruta, data=opciones, files=files, **kw)
        if inicial.status_code == 200:
            propuesta = terminar_lectura(client, inicial.json(), ruta)
    if inicial.status_code != 200:
        return inicial
    assert propuesta["estado"] == "pendiente_confirmacion", propuesta
    assert "job" not in propuesta
    cambios = {}
    if opciones.get("ambito") == "organizacion":
        cambios = {u["id"]: {"regimen": "privado", "institucion": "organizacion"} for u in propuesta["interpretacion"]["cuadros"]}
    return client.post(ruta, data={**opciones, "interpretacion_accion": "confirmar", "interpretacion_id": propuesta["informe_id"],
                                   "interpretacion_correcciones": json.dumps(cambios),
                                   "interpretacion_revision": propuesta["interpretacion"]["revision"]}, files=files, **kw)


def terminar_lectura(client, propuesta, ruta="/api/analisis-rapido"):
    """Consume la etapa persistida con el procesador real, sin arrancar hilos en la suite."""
    assert propuesta["estado"] == "interpretando", propuesta
    dependencia = client.app.dependency_overrides[get_db]()
    db = next(dependencia) if isinstance(dependencia, types.GeneratorType) else dependencia
    try:
        job = db.get(models.AnalysisJob, propuesta["job"]["id"])
        jobs.procesar_interpretacion(db, job)
    finally:
        if isinstance(dependencia, types.GeneratorType):
            dependencia.close()
    prefijo = "/api" if ruta.startswith("/api/") else ""
    respuesta = client.get(f"{prefijo}/interpretacion-previa/{propuesta['informe_id']}")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def preparar_informe_fixture(informe):
    """Para regresiones que construyen un informe en memoria, antes de invocar el motor."""
    meta = dict(informe.saneamiento or {})
    original = [("datos-fixture.json", json.dumps(informe.datos, sort_keys=True).encode())]
    r = ip.interpretar(informe.datos, meta, original, {}, informe.usuario_id,
                      fn=respuesta_fixture, proveedoras=["gpt", "gemini", "deepseek"])
    meta[ip.CAMPO] = ip.confirmar(r, usuario_id=informe.usuario_id, revision=1, leidos=original, datos=informe.datos, opciones={})
    informe.saneamiento = meta
