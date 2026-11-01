"""Exporta las respuestas a «¿qué resultó ser esta señal?» para medir la herramienta con casos reales.

Sin datos de la persona (ni usuario ni correo). El informe va con un seudónimo distinto en cada exportación (no
se puede cruzar con la base para saber de quién es). El comentario es texto libre: puede nombrar algo del área, así
que el archivo es de uso interno para medir y no se publica. Los informes marcados «es una prueba» al cargarlos
quedan afuera (con --incluir-pruebas entran, marcados). La prioridad es la registrada al responder; las respuestas
anteriores a ese registro llevan la recalculada con el código vigente y lo dicen en «prioridad_origen».
Uso (en el servidor, con el .env cargado): python scripts/exportar_respuestas_senal.py salida.json [--incluir-pruebas]
"""
import hashlib
import json
import secrets
import sys

sys.path.insert(0, ".")

import models  # noqa: E402
from services import casos_revision  # noqa: E402


def ultimas_respuestas(db):
    """La última respuesta a cada señal; si la señal se regeneró al reanalizar, la identifica su copia."""
    ultimas = {}
    for r in db.query(models.RespuestaSenal).order_by(models.RespuestaSenal.creado_en, models.RespuestaSenal.id):
        if r.hallazgo_id:
            clave = ("señal", r.hallazgo_id)
        elif r.regla or r.celda:
            clave = ("copia", r.informe_id, r.lente, r.regla, r.hoja, r.celda)
        else:
            clave = ("fila", r.id)  # sin ubicación: no se junta con otras
        ultimas[clave] = r
    return list(ultimas.values())


def informes_de_prueba(db, ids):
    """Informes marcados «es una prueba» al cargarlos (saneamiento.es_prueba)."""
    if not ids:
        return set()
    return {i.id for i in db.query(models.Informe).filter(models.Informe.id.in_(list(ids)))
            if (i.saneamiento or {}).get("es_prueba")}


def prioridad_de(r, h):
    """(prioridad, origen): la registrada al responder o, en respuestas anteriores, la recalculada hoy."""
    if r.prioridad:
        return r.prioridad, "registrada"
    if h is not None:
        return casos_revision.prioridad(h), "recalculada"
    return None, None


def exportar(db, incluir_pruebas=False):
    ultimas = ultimas_respuestas(db)
    pruebas = informes_de_prueba(db, {r.informe_id for r in ultimas})
    sal = secrets.token_hex(16)
    out = []
    for r in sorted(ultimas, key=lambda x: (x.informe_id, x.id)):
        if r.informe_id in pruebas and not incluir_pruebas:
            continue
        h = db.get(models.Hallazgo, r.hallazgo_id) if r.hallazgo_id else None
        prioridad, origen = prioridad_de(r, h)
        fila = dict(informe=hashlib.sha256(f"{sal}:{r.informe_id}".encode()).hexdigest()[:12],
                    vigente=h is not None, lente=r.lente, regla=r.regla, prioridad=prioridad,
                    prioridad_origen=origen, version_motor=r.version_motor, hoja=r.hoja,
                    celda=r.celda, respuesta=r.respuesta, comentario=r.comentario,
                    fecha=r.creado_en.isoformat() if r.creado_en else None)
        if incluir_pruebas:
            fila["es_prueba"] = r.informe_id in pruebas
        out.append(fila)
    return out


if __name__ == "__main__":
    from database import SessionLocal

    with SessionLocal() as db:
        datos = exportar(db, incluir_pruebas="--incluir-pruebas" in sys.argv[2:])
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print(len(datos), "respuestas exportadas")
