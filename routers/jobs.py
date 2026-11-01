from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from core.auth import get_current_user
from database import get_db
from routers.carga_rapida import _limpiar_email_notificaciones
from routers.informes import _rechazar_lector, _validar_modelos
from services import cuota_ia
from services import jobs as jobs_svc

router = APIRouter(prefix="/jobs", tags=["jobs"])


def puede_ver(user: models.Usuario, informe: models.Informe) -> bool:
    return user.rol == "admin" or informe.usuario_id == user.id


@router.get("/{job_id}", response_model=schemas.AnalysisJobOut)
def obtener_job(job_id: int, user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(models.AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "trabajo no encontrado")
    if not puede_ver(user, job.informe):
        raise HTTPException(403, "sin permiso para ver este trabajo")
    return job


@router.post("/informes/{informe_id}/analizar", response_model=schemas.EnqueueAnalisisOut)
def encolar_informe(informe_id: int, payload: Optional[dict] = None, user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para analizar este informe")
    _rechazar_lector(user, "analizar informes")
    cuota_ia.verificar_encolado(db, user, informe)
    modelos = _validar_modelos((payload or {}).get("modelos"))
    # Mismo criterio que la carga: sólo una dirección con formato válido.
    notify_email = _limpiar_email_notificaciones((payload or {}).get("notify_email")) or user.email_notificaciones
    job = jobs_svc.enqueue_analysis(db, informe, user, modelos, notify_email=notify_email)
    return {"informe_id": informe.id, "job": job}
