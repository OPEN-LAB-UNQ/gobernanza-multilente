"""Indicador de valor real con casos reales: sólo cifras agregadas, sin personas ni informes identificables.

A · Precisión vivida: de las señales que quien hizo el informe respondió como «error real» o «dato correcto»,
    cuántas eran error real. Por prioridad (registrada al responder; en respuestas anteriores, recalculada) y
    siempre con la cantidad («3 de 8»). Los «no sé todavía» no entran en el cociente y se informan aparte. Con
    menos de 10 respondidas, «insuficiente».
Tiempo hasta la respuesta: días entre la carga del informe y la primera respuesta a cada señal (mediana).
B · Informes salvados: pregunta de cierre («¿Corregiste algo del informe antes de entregarlo?») y errores que la
    herramienta no señaló.
Cobertura: casos de prioridad alta con alguna respuesta, sobre los casos de prioridad alta emitidos. Por debajo del
70 % el resultado es «sin medición», no 0 %.

Quedan afuera los informes marcados «es una prueba» al cargarlos y, salvo --incluir-admin, los que cargó la
administración (pruebas del gerente). Uso (en el servidor, con el .env cargado):
    python scripts/indicador_valor.py [--desde AAAA-MM-DD] [--hasta AAAA-MM-DD] [--incluir-admin] [salida.json]
"""
import datetime
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from exportar_respuestas_senal import prioridad_de, ultimas_respuestas  # noqa: E402

import models  # noqa: E402
from services import casos_revision  # noqa: E402

MINIMO_RESPONDIDAS = 10
COBERTURA_MINIMA = 0.7
ACCION_CIERRE = "cierre_informe_registrado"


def _clave(r):
    if r.hallazgo_id:
        return ("señal", r.hallazgo_id)
    if r.regla or r.celda:
        return ("copia", r.informe_id, r.lente, r.regla, r.hoja, r.celda)
    return ("fila", r.id)


def informes_medibles(db, desde=None, hasta=None, incluir_admin=False):
    """(ids incluidos, excluidos por prueba, excluidos por administración)."""
    q = db.query(models.Informe)
    if desde:
        q = q.filter(models.Informe.creado_en >= desde)
    if hasta:
        q = q.filter(models.Informe.creado_en < hasta + datetime.timedelta(days=1))
    admins = {u.id for u in db.query(models.Usuario).filter(models.Usuario.rol == "admin")}
    incluidos, pruebas, admin = {}, 0, 0
    for i in q:
        if (i.saneamiento or {}).get("es_prueba"):
            pruebas += 1
        elif not incluir_admin and i.usuario_id in admins:
            admin += 1
        else:
            incluidos[i.id] = i
    return incluidos, pruebas, admin


def precision(conteo):
    er, dc = conteo.get("error_real", 0), conteo.get("dato_correcto", 0)
    n = er + dc
    return {"error_real": er, "dato_correcto": dc, "no_se": conteo.get("no_se", 0), "n": n,
            "texto": f"{er} de {n}", "proporcion": round(er / n, 3) if n else None,
            "estado": "calculado" if n >= MINIMO_RESPONDIDAS else "insuficiente"}


def calcular(db, desde=None, hasta=None, incluir_admin=False):
    informes, n_pruebas, n_admin = informes_medibles(db, desde, hasta, incluir_admin)
    ultimas = [r for r in ultimas_respuestas(db) if r.informe_id in informes]

    # A · por prioridad y origen de la prioridad.
    por_prioridad, origenes = {}, Counter()
    for r in ultimas:
        h = db.get(models.Hallazgo, r.hallazgo_id) if r.hallazgo_id else None
        prioridad, origen = prioridad_de(r, h)
        por_prioridad.setdefault(prioridad or "sin_dato", Counter())[r.respuesta] += 1
        origenes[origen or "sin_dato"] += 1

    # Tiempo hasta la primera respuesta de cada señal.
    primera = {}
    for r in db.query(models.RespuestaSenal).filter(models.RespuestaSenal.informe_id.in_(list(informes) or [-1])):
        k = _clave(r)
        if r.creado_en and (k not in primera or r.creado_en < primera[k].creado_en):
            primera[k] = r
    dias = sorted((r.creado_en - informes[r.informe_id].creado_en).total_seconds() / 86400
                  for r in primera.values() if informes[r.informe_id].creado_en)

    # Cobertura: casos de prioridad alta con alguna respuesta vigente.
    respondidas = {r.hallazgo_id for r in ultimas if r.hallazgo_id}
    altas = altas_respondidas = 0
    for i in informes.values():
        if not i.devolucion or not i.hallazgos:
            continue
        for c in casos_revision.agrupar(i.hallazgos)["casos"]:
            if c["prioridad"] != "alta":
                continue
            altas += 1
            ids = {casos_revision.campo(x, "id") for x in [c["primary_finding"], *c["related_findings"]]}
            altas_respondidas += bool(ids & respondidas)
    cobertura = round(altas_respondidas / altas, 3) if altas else None

    # B · pregunta de cierre: vale la última respuesta de cada informe.
    cierres = {}
    for e in (db.query(models.ActivityEvent)
              .filter(models.ActivityEvent.accion == ACCION_CIERRE,
                      models.ActivityEvent.informe_id.in_(list(informes) or [-1]))
              .order_by(models.ActivityEvent.creado_en, models.ActivityEvent.id)):
        cierres[e.informe_id] = e.metadata_evento or {}
    corrigio = Counter(m.get("corrigio") for m in cierres.values())
    omisiones = [int(m["errores_no_senalados"]) for m in cierres.values() if m.get("errores_no_senalados") is not None]

    return {
        "periodo": {"desde": desde.isoformat() if desde else None, "hasta": hasta.isoformat() if hasta else None},
        "informes": {"incluidos": len(informes), "excluidos_por_prueba": n_pruebas,
                     "excluidos_administracion": n_admin},
        "indicador_a": {p: precision(c) for p, c in sorted(por_prioridad.items())},
        "prioridad_origen": dict(origenes),
        "tiempo_hasta_respuesta_dias": {"n": len(dias),
                                        "mediana": round(statistics.median(dias), 2) if dias else None},
        "cobertura_alta": {"casos_alta": altas, "con_respuesta": altas_respondidas, "proporcion": cobertura,
                           "medicion": "valida" if cobertura is not None and cobertura >= COBERTURA_MINIMA
                           else "sin medición"},
        "indicador_b": {"informes_con_cierre": len(cierres), "corrigio_si": corrigio.get("si", 0),
                        "corrigio_no": corrigio.get("no", 0), "todavia_no": corrigio.get("todavia_no", 0),
                        "informes_con_omisiones": sum(1 for x in omisiones if x > 0),
                        "errores_no_senalados": sum(omisiones)},
    }


def _fecha(argv, nombre):
    if nombre in argv:
        return datetime.datetime.strptime(argv[argv.index(nombre) + 1], "%Y-%m-%d")
    return None


if __name__ == "__main__":
    from database import SessionLocal

    args = sys.argv[1:]
    desde, hasta = _fecha(args, "--desde"), _fecha(args, "--hasta")
    salida = next((a for i, a in enumerate(args) if not a.startswith("--")
                   and (i == 0 or args[i - 1] not in ("--desde", "--hasta"))), None)
    with SessionLocal() as db:
        datos = calcular(db, desde, hasta, incluir_admin="--incluir-admin" in args)
    texto = json.dumps(datos, ensure_ascii=False, indent=1)
    if salida:
        Path(salida).write_text(texto, encoding="utf-8")
    print(texto)
