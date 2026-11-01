"""Panel técnico autenticado de calibraciones, incidencias y posibles reevaluaciones."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from core.auth import require_admin
from database import get_db
from enums import Lente
from services import actividad, calibracion
from versiones import APP_VERSION, AUTOMATIC_PROTOCOL_VERSION, version_codigo, version_control

router = APIRouter(prefix="/calibraciones", tags=["calibraciones"])


def salida(c):
    return {campo.name: getattr(c, campo.name) for campo in models.CalibrationRun.__table__.columns}


@router.get("")
def listar(db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    return {"version_aplicacion": APP_VERSION, "version_codigo": version_codigo(),
            "version_protocolo": AUTOMATIC_PROTOCOL_VERSION,
            "controles": {lente.value: version_control(lente.value) for lente in Lente},
            "corridas": [salida(c) for c in db.query(models.CalibrationRun).order_by(models.CalibrationRun.id.desc()).limit(200)],
            "validacion_externa": "No se presume realizada; revisar origen y tipo de los casos registrados"}


@router.post("")
def registrar(payload: calibracion.CorridaCreate, db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    try:
        corrida = calibracion.registrar(db, payload, user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    actividad.registrar(db, usuario=user, modulo="calibracion", accion="corrida_registrada",
                        resumen="Contraste de calibración registrado", metadata={"corrida_id": corrida.id, "estado": corrida.estado})
    db.commit()
    return salida(corrida)


@router.get("/{corrida_id}/afectadas")
def afectadas(corrida_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    corrida = db.get(models.CalibrationRun, corrida_id)
    if not corrida:
        raise HTTPException(404, "corrida no encontrada")
    filas = []
    for e in calibracion.potencialmente_afectadas(db, corrida):
        evaluaciones = db.query(models.EvaluacionCertificacion).filter(models.EvaluacionCertificacion.informe_id == e.informe_id).all()
        filas.append({"ejecucion_id": e.id, "informe_id": e.informe_id, "fecha": e.creado_en,
                      "evaluaciones_ids": [ev.id for ev in evaluaciones], "requiere_reevaluacion": e.requiere_reevaluacion})
    return {"potencialmente_afectadas": filas, "limite": "Análisis anteriores sin versiones registradas no pueden descartarse con esta búsqueda"}


@router.post("/{corrida_id}/marcar-reevaluacion")
def marcar(corrida_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    corrida = db.get(models.CalibrationRun, corrida_id)
    if not corrida:
        raise HTTPException(404, "corrida no encontrada")
    if corrida.estado != "fallida":
        raise HTTPException(409, "la corrida no registra un fallo")
    ejecuciones = calibracion.potencialmente_afectadas(db, corrida)
    for e in ejecuciones:
        e.requiere_reevaluacion = True
        if not any(i.get("corrida_id") == corrida.id for i in e.incidencias or []):
            e.incidencias = [*(e.incidencias or []), {"corrida_id": corrida.id, "responsable_id": user.id,
                             "fecha": models.now().isoformat(), "categoria": corrida.categoria_incidencia}]
    actividad.registrar(db, usuario=user, modulo="calibracion", accion="reevaluacion_solicitada",
                        resumen="Reevaluación técnica solicitada", metadata={"corrida_id": corrida.id, "ejecuciones": [e.id for e in ejecuciones]})
    db.commit()
    return {"marcadas": len(ejecuciones), "sellos_modificados": 0}
