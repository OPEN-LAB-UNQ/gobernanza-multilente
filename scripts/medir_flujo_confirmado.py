#!/usr/bin/env python3
"""Campaña aislada del flujo HTTP real; la confirmación es simulada y queda declarada.

No mide la calidad de una decisión humana. Nunca confirma cuadros desconocidos
ni responde automáticamente las preguntas aritméticas posteriores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path


def clasificacion_confirmable(propuesta, esperado=None):
    cuadros = (propuesta.get("interpretacion") or {}).get("cuadros") or []
    return bool(cuadros) and all(u.get("lecturas_validas", 0) >= 2
        and u.get("propuesta", {}).get("tipo") not in {None, "desconocido", "otro"}
        and (esperado is None or u["propuesta"]["tipo"] == esperado) for u in cuadros)


def senal_en_celda(hallazgos, hoja, celda):
    if not celda:
        return None
    for h in hallazgos:
        e = h.get("evidencia") or {}
        if e.get("hoja") == hoja and e.get("celda") == celda:
            return True
        if f"{hoja}!{celda}" in (e.get("ubicaciones_excel") or []):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--casos", required=True, type=Path)
    parser.add_argument("--salida", required=True, type=Path)
    parser.add_argument("--version-codigo", required=True)
    parser.add_argument("--limite-segundos", type=int, default=7 * 3600)
    parser.add_argument("--max-llamadas", type=int, default=1500)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy.engine import make_url
    # Rechazo antes de importar la aplicación o conectar una base.
    base = make_url(os.environ.get("DATABASE_URL", "sqlite://")).database or ""
    if not base.startswith("gobernanza_medicion_"):
        raise SystemExit("La campaña exige una base aislada con prefijo gobernanza_medicion_")
    from versiones import ANALYSIS_VERSION, APP_VERSION, version_codigo
    if version_codigo() != args.version_codigo:
        raise SystemExit("La huella no coincide con la versión publicada fijada para esta campaña")
    args.salida.mkdir(parents=True, exist_ok=False)
    casos = json.loads(args.casos.read_text(encoding="utf-8"))
    import models
    from database import SessionLocal, engine
    models.Base.metadata.create_all(engine)
    from fastapi.encoders import jsonable_encoder
    from fastapi.testclient import TestClient

    from config import settings
    from core.auth import COOKIE_NAME, make_token
    from main import app
    from services import lector_mapa, triangulacion
    inicio = time.monotonic()
    parar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: parar.set())
    signal.signal(signal.SIGINT, lambda *_: parar.set())
    cerrojo = threading.RLock()
    cache = {}
    contadores = {"llamadas": 0, "errores_proveedor": 0, "aciertos_cache": 0, "por_proveedor": {}}
    resultados = []
    modelos_configurados = {k: getattr(settings, v) for k, v in
        {"gpt": "openai_model", "gemini": "gemini_model", "deepseek": "deepseek_model"}.items()}

    def guardar(nombre, obj):
        p = args.salida / nombre
        temporal = p.with_suffix(p.suffix + ".tmp")
        with cerrojo:
            temporal.write_text(json.dumps(jsonable_encoder(obj), ensure_ascii=False, indent=2), encoding="utf-8")
            temporal.replace(p)

    def agotado():
        return parar.is_set() or time.monotonic() - inicio >= args.limite_segundos

    def reservar(proveedor):
        with cerrojo:
            if agotado() or contadores["llamadas"] >= args.max_llamadas:
                raise RuntimeError("Límite de campaña alcanzado")
            contadores["llamadas"] += 1
            contadores["por_proveedor"][proveedor] = contadores["por_proveedor"].get(proveedor, 0) + 1
            guardar("llamadas.json", contadores)

    llamar_real = lector_mapa.llamar
    def lectura(proveedor, prompt):
        clave = hashlib.sha256(json.dumps([args.version_codigo, proveedor, modelos_configurados[proveedor], prompt]).encode()).hexdigest()
        with cerrojo:
            if clave in cache:
                contadores["aciertos_cache"] += 1
                guardar("llamadas.json", contadores)
                return cache[clave]
        reservar(proveedor)
        try:
            resultado = llamar_real(proveedor, prompt)
        except Exception:
            with cerrojo:
                contadores["errores_proveedor"] += 1
                guardar("llamadas.json", contadores)
            raise
        with cerrojo:
            cache[clave] = resultado
        return resultado
    lector_mapa.llamar = lectura  # Instrumenta el proveedor real; no sustituye sus respuestas.
    comentarios_reales = triangulacion._interpretar_gpt
    def comentarios(*a, **kw):
        reservar("gpt_comentarios")
        return comentarios_reales(*a, **kw)
    triangulacion._interpretar_gpt = comentarios

    def esperar(client, ident, fase):
        fin = time.monotonic() + 1800
        while time.monotonic() < fin and not agotado():
            if fase == "lectura":
                r = client.get(f"/api/interpretacion-previa/{ident}")
                r.raise_for_status()
                if r.json()["estado"] != "interpretando":
                    return r.json()
            else:
                with SessionLocal() as db:
                    j = db.get(models.AnalysisJob, ident)
                    if j.estado in {"finalizado", "error"}:
                        return {"estado": j.estado, "resultado": j.resultado}
            parar.wait(1)
        raise TimeoutError("Campaña o archivo sin completar dentro del plazo")

    guardar("protocolo.json", {"app": APP_VERSION, "motor": ANALYSIS_VERSION, "codigo": args.version_codigo,
        "modelos": modelos_configurados, "casos_planificados": len(casos), "max_llamadas": args.max_llamadas,
        "limite_segundos": args.limite_segundos, "confirmacion": "simulada sólo con clasificación conocida y dos lecturas válidas",
        "limites": ["No valida la intervención humana ni la precisión de la clasificación sin etiquetas independientes.",
                    "Señales en archivos oficiales requieren revisión: no se cuentan automáticamente como falsas alarmas.",
                    "Una coincidencia de celda es detección localizada, no prueba de explicación causal correcta.",
                    "La caché comparte únicamente respuestas a pedidos ciegos idénticos dentro de esta corrida."]})
    with TestClient(app, base_url="https://testserver") as client:
        with SessionLocal() as db:
            usuario = db.query(models.Usuario).filter_by(email=settings.admin_email).one()
            client.cookies.set(COOKIE_NAME, make_token(usuario.id))
        for numero, caso in enumerate(casos):
            if agotado() or contadores["llamadas"] >= args.max_llamadas:
                break
            resultado = {"caso": caso, "estado": "en_curso", "confirmacion_simulada": False}
            resultados.append(resultado)
            guardar("resultados.json", resultados)
            try:
                resultado["fase"] = "carga"
                ruta = Path(caso["ruta"])
                bruto = ruta.read_bytes()
                resultado["sha256"] = hashlib.sha256(bruto).hexdigest()
                if caso.get("sha256") and caso["sha256"] != resultado["sha256"]:
                    raise ValueError("Cambió el archivo del corpus fijado")
                archivos = [("archivos", (caso.get("archivo") or ruta.name, bruto))]
                opciones = {"notificar": "false", "modelos": "gpt", "revisar_formulas_excel": "true"}
                r = client.post("/api/analisis-rapido", files=archivos, data=opciones)
                if r.status_code == 422 and str(r.json().get("detail", "")).startswith("SIN_ANALISIS_NUMERICO:"):
                    resultado["estado"] = "sin_analisis_numerico"
                    resultado["motivo"] = r.json()["detail"]
                    continue
                r.raise_for_status()
                ident = r.json()["informe_id"]
                resultado["informe_id"] = ident
                resultado["fase"] = "lectura_ia"
                propuesta = esperar(client, ident, "lectura")
                guardar(f"{numero:04d}-propuesta.json", propuesta)
                if propuesta.get("estado") != "pendiente_confirmacion":
                    raise RuntimeError("La lectura previa terminó con error")
                if not clasificacion_confirmable(propuesta, caso.get("tipo_esperado")):
                    resultado["estado"] = "requiere_revision_humana"
                    continue
                resultado["fase"] = "confirmacion"
                r = client.post("/api/analisis-rapido", files=archivos, data={**opciones,
                    "interpretacion_accion": "confirmar", "interpretacion_id": ident,
                    "interpretacion_revision": propuesta["interpretacion"]["revision"]})
                r.raise_for_status()
                resultado["confirmacion_simulada"] = True
                resultado["fase"] = "analisis"
                job = esperar(client, r.json()["job"]["id"], "analisis")
                if job["estado"] != "finalizado":
                    raise RuntimeError("El trabajo de análisis terminó con error")
                with SessionLocal() as db:
                    informe = db.get(models.Informe, ident)
                    resultado["filas"] = len(informe.datos)
                    resultado["hallazgos"] = [{"lente": h.lente, "severidad": h.severidad,
                        "descripcion": h.descripcion, "evidencia": h.evidencia} for h in informe.hallazgos]
                    resultado["cobertura"] = informe.devolucion.cobertura
                    resultado["interpretacion"] = lector_mapa.saneamiento_publico(informe.saneamiento).get("interpretacion_previa")
                resultado["deteccion_celda"] = senal_en_celda(resultado["hallazgos"], caso.get("hoja"), caso.get("celda"))
                resultado["fase"] = "reportes"
                for pieza in ("completo", "anexo"):
                    r = client.post(f"/api/informes/{ident}/reporte", json={"formato": "pdf", "pieza": pieza})
                    r.raise_for_status()
                    if not r.content.startswith(b"%PDF"):
                        raise RuntimeError("El reporte no es un PDF")
                    (args.salida / f"{numero:04d}-{pieza}.pdf").write_bytes(r.content)
                resultado["estado"] = "completado"
            except TimeoutError:
                resultado["estado"] = "incompleto_por_plazo"
                parar.set()
            except Exception as exc:
                resultado.update(estado="fallo", clase_error=type(exc).__name__)
                if hasattr(exc, "response") and getattr(exc, "response") is not None:
                    resultado["estado_http"] = exc.response.status_code
                    # Sólo detalles de nuestra API; nunca excepciones de proveedores o DSN.
                    if exc.response.status_code in {400, 404, 409, 422}:
                        resultado["detalle_http"] = str(exc.response.json().get("detail", ""))[:300]
            finally:
                guardar("resultados.json", resultados)
                print(numero + 1, len(casos), resultado["estado"], flush=True)
    guardar("resumen.json", {"planificados": len(casos), "iniciados": len(resultados),
        "completados": sum(r["estado"] == "completado" for r in resultados),
        "pendientes_humanos": sum(r["estado"] == "requiere_revision_humana" for r in resultados),
        "sin_analisis_numerico": sum(r["estado"] == "sin_analisis_numerico" for r in resultados),
        "fallos": sum(r["estado"] == "fallo" for r in resultados),
        "incompleta": len(resultados) != len(casos) or any(r["estado"] == "incompleto_por_plazo" for r in resultados),
        "llamadas": contadores, "duracion_segundos": round(time.monotonic() - inicio)})


if __name__ == "__main__":
    main()
