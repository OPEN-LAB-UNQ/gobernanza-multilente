"""Lecturas observadas automáticamente y resultados revisados por separado."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from core.auth import get_current_user, require_admin
from database import get_db
from services import actividad
from services import biblioteca_casos as bc
from services import interpretacion_previa as ip

router = APIRouter(prefix="/biblioteca-casos", tags=["biblioteca-casos"])


def salida(c):
    return {"id": c.id, "informe_id": c.informe_id, "estado": c.estado,
            "archivo": c.archivo, "hoja": c.hoja, "bloque": c.bloque, "control": c.control,
            "resultado": c.resultado, "fundamento": c.fundamento, "fuente_url": c.fuente_url,
            "fuente_sha256": c.fuente_sha256, "perfil_cuadro": c.perfil_cuadro,
            "evidencia": c.evidencia, "version_codigo": c.version_codigo,
            "propuesto_por_id": c.propuesto_por_id, "revisado_por_id": c.revisado_por_id,
            "creado_en": c.creado_en, "decidido_en": c.decidido_en}


@router.get("")
def listar(db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    pendientes = (db.query(models.CasoBiblioteca).filter_by(estado="pendiente")
                  .order_by(models.CasoBiblioteca.id.desc()).limit(100).all())
    return {"resumen": bc.resumen(db), "pendientes": [salida(c) for c in pendientes]}


@router.get("/informes/{informe_id}")
def informe_casos(informe_id: int, db: Session = Depends(get_db),
                  user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "Informe no encontrado")
    if user.rol != "admin" and (user.rol != "analista" or informe.usuario_id != user.id):
        raise HTTPException(403, "Sin permiso para revisar este informe")
    lectura = ip.exigir(informe)
    cobertura = ((informe.devolucion.cobertura or {}).get("excel") or {}) if informe.devolucion else {}
    cuadros = []
    for u in lectura["cuadros"]:
        b = next((b for b in cobertura.get("bloques") or [] if
                  (b.get("archivo"), b.get("hoja"), str(b.get("bloque"))) ==
                  (u["archivo"], u["hoja"], str(u["bloque"]))), None)
        if not b:
            continue
        controles = [k for k, v in (b.get("trazabilidad_controles") or {}).items()
                     if k in bc.CONTROLES and v.get("estado") == "ejecutado"]
        cuadros.append({"archivo": u["archivo"], "hoja": u["hoja"], "bloque": u["bloque"],
                        "perfil": u.get("confirmada"), "controles_ejecutados": controles})
    respuestas = {r.hallazgo_id: r for r in db.query(models.RespuestaSenal).filter_by(informe_id=informe_id)
                  .order_by(models.RespuestaSenal.id).all() if r.hallazgo_id}
    senales = [{"id": h.id, "lente": h.lente, "descripcion": h.descripcion[:350],
                "archivo": (h.evidencia or {}).get("archivo_origen") or (h.evidencia or {}).get("archivo"),
                "hoja": (h.evidencia or {}).get("hoja"), "bloque": (h.evidencia or {}).get("bloque_excel"),
                "celda": (h.evidencia or {}).get("celda"), "respuesta": respuestas[h.id].respuesta if h.id in respuestas else None}
               for h in informe.hallazgos]
    casos = [salida(c) for c in db.query(models.CasoBiblioteca).filter_by(informe_id=informe_id)
             .order_by(models.CasoBiblioteca.id.desc()).all()]
    return {"informe_id": informe_id, "cuadros": cuadros, "senales": senales, "casos": casos,
            "aviso": "La lectura confirmada ya orienta casos futuros sin otra aprobación. La revisión administrativa sólo acredita el resultado de una señal u omisión."}


@router.post("/informes/{informe_id}")
def proponer(informe_id: int, payload: bc.Propuesta, db: Session = Depends(get_db),
             user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "Informe no encontrado")
    if user.rol != "admin" and (user.rol != "analista" or informe.usuario_id != user.id):
        raise HTTPException(403, "Sin permiso para proponer un caso de este informe")
    if any(job.estado in {"pendiente", "procesando"} for job in informe.trabajos_analisis or []):
        raise HTTPException(409, "Esperá a que termine el análisis")
    try:
        caso = bc.proponer(db, informe, payload, user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    actividad.registrar(db, usuario=user, modulo="biblioteca_casos", accion="caso_propuesto",
                       resumen="Caso de informe público propuesto para revisión",
                       informe_id=informe_id, metadata={"caso_id": caso.id, "control": caso.control})
    db.commit()
    db.refresh(caso)
    return salida(caso)


@router.post("/{caso_id}/decision")
def decidir(caso_id: int, payload: bc.Decision, db: Session = Depends(get_db),
            user: models.Usuario = Depends(require_admin)):
    caso = db.get(models.CasoBiblioteca, caso_id)
    if not caso:
        raise HTTPException(404, "Caso no encontrado")
    try:
        bc.decidir(db, caso, payload, user.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    actividad.registrar(db, usuario=user, modulo="biblioteca_casos", accion="caso_revisado",
                       resumen="Caso de biblioteca aprobado" if payload.aprobar else "Caso de biblioteca rechazado",
                       informe_id=caso.informe_id, metadata={"caso_id": caso.id, "estado": caso.estado})
    db.commit()
    db.refresh(caso)
    return salida(caso)
