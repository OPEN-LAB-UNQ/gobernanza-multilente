from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from core.auth import require_admin
from database import get_db

router = APIRouter(prefix="/areas", tags=["areas"])


@router.post("", response_model=schemas.AreaOut)
def crear_area(
    payload: schemas.AreaCreate,
    _admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(models.Area).filter(models.Area.codigo == payload.codigo).first():
        raise HTTPException(409, "ya existe un área con ese código")
    area = models.Area(**payload.model_dump())
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


@router.get("", response_model=list[schemas.AreaOut])
def listar_areas(db: Session = Depends(get_db)):
    return db.query(models.Area).order_by(models.Area.nombre).all()
