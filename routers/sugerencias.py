"""Sugerencias de interfaz: identidad del servidor y lectura exclusiva de administración."""
import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from core.auth import get_current_user, require_admin
from database import get_db

router = APIRouter(prefix="/sugerencias", tags=["Sugerencias"])
PANTALLAS = {
    "inicio": "Inicio", "proyecto-ia": "Incubadora · Mi proyecto",
    "casos": "Casos de mis compañeros", "segunda-vuelta": "Actividad de votación",
    "conexiones": "Mapa de conexiones", "sintesis": "Tres síntesis",
    "analizar": "Multilente · Analizar", "informes": "Informes",
    "actividad": "Actividad", "validacion": "Validación", "guia": "Guía",
    "marco": "Marco", "aprendizaje": "Calibración del sistema", "detalle": "Detalle del informe",
}


class NuevaSugerencia(BaseModel):
    pantalla: str
    texto: str = Field(min_length=1, max_length=5000)
    solicitud_id: UUID

    @field_validator("pantalla")
    @classmethod
    def pantalla_conocida(cls, value):
        if value not in PANTALLAS:
            raise ValueError("Pantalla desconocida")
        return value

    @field_validator("texto")
    @classmethod
    def texto_no_vacio(cls, value):
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Escribí una sugerencia válida")
        return value


def serializar(row):
    return {"id": row.id, "usuario_id": row.usuario_id, "nombre": row.nombre,
            "pantalla": row.pantalla, "pantalla_nombre": PANTALLAS.get(row.pantalla, row.pantalla),
            "texto": row.texto, "creado_en": row.creado_en.isoformat() + "Z"}


@router.post("", status_code=201)
def crear(payload: NuevaSugerencia, user=Depends(get_current_user), db: Session = Depends(get_db)):
    token = str(payload.solicitud_id)
    existing = db.query(models.SugerenciaPantalla).filter_by(usuario_id=user.id, solicitud_id=token).first()
    if existing:
        if existing.pantalla != payload.pantalla or existing.texto != payload.texto:
            raise HTTPException(409, "Este envío ya fue registrado con otro contenido. Abrí una nueva sugerencia.")
        return serializar(existing)
    row = models.SugerenciaPantalla(usuario_id=user.id, nombre=user.nombre,
        pantalla=payload.pantalla, texto=payload.texto, solicitud_id=token)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(models.SugerenciaPantalla).filter_by(usuario_id=user.id, solicitud_id=token).first()
        if existing and existing.pantalla == payload.pantalla and existing.texto == payload.texto:
            return serializar(existing)
        raise HTTPException(409, "El envío no pudo registrarse. Revisá e intentá nuevamente.")
    db.refresh(row)
    return serializar(row)


def consulta(db, pantalla, usuario_id):
    q = db.query(models.SugerenciaPantalla)
    if pantalla:
        if pantalla not in PANTALLAS:
            raise HTTPException(422, "Pantalla desconocida")
        q = q.filter_by(pantalla=pantalla)
    if usuario_id is not None:
        q = q.filter_by(usuario_id=usuario_id)
    return q.order_by(models.SugerenciaPantalla.creado_en.desc(), models.SugerenciaPantalla.id.desc())


@router.get("")
def listar(pantalla: str = "", usuario_id: int = None, offset: int = Query(0, ge=0),
           limit: int = Query(50, ge=1, le=100), admin=Depends(require_admin), db: Session = Depends(get_db)):
    q = consulta(db, pantalla, usuario_id)
    personas = db.query(models.Usuario.id, models.Usuario.nombre).join(
        models.SugerenciaPantalla, models.SugerenciaPantalla.usuario_id == models.Usuario.id
    ).distinct().order_by(models.Usuario.nombre).all()
    return {"total": q.count(), "items": [serializar(x) for x in q.offset(offset).limit(limit)],
            "personas": [{"id": p.id, "nombre": p.nombre} for p in personas], "pantallas": PANTALLAS}


def celda_csv(value):
    value = str(value)
    # Evita ejecutar fórmulas al abrir sugerencias de texto libre en una planilla.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) or value.startswith(("\t", "\r", "\n")) else value


@router.get("/exportar")
def exportar(pantalla: str = "", usuario_id: int = None,
             admin=Depends(require_admin), db: Session = Depends(get_db)):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Fecha (UTC)", "Nombre", "Pantalla", "Sugerencia"])
    for row in consulta(db, pantalla, usuario_id).yield_per(500):
        writer.writerow([row.creado_en.isoformat() + "Z", celda_csv(row.nombre),
            PANTALLAS.get(row.pantalla, row.pantalla), celda_csv(row.texto)])
    return Response(content=("\ufeff" + output.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sugerencias-gobernanza.csv"', "Cache-Control": "no-store"})


class EditarSugerencia(BaseModel):
    texto: str = Field(min_length=1, max_length=5000)
    texto_anterior: str = Field(min_length=1, max_length=5000)

    @field_validator("texto")
    @classmethod
    def validar_texto(cls, value):
        return NuevaSugerencia.texto_no_vacio(value)


@router.get("/mias")
def propias(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
            user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = consulta(db, "", user.id)
    return {"total": q.count(), "items": [serializar(x) for x in q.offset(offset).limit(limit)]}


@router.patch("/{sugerencia_id}")
def editar(sugerencia_id: int, payload: EditarSugerencia,
           user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(models.SugerenciaPantalla).filter_by(id=sugerencia_id, usuario_id=user.id).with_for_update().first()
    if not row:
        raise HTTPException(404, "Sugerencia no encontrada")
    if row.texto == payload.texto:
        return serializar(row)
    if row.texto != payload.texto_anterior:
        raise HTTPException(409, "La sugerencia cambió en otra ventana. Conservá tu texto y recargá la lista antes de volver a guardar.")
    from services.actividad import registrar
    registrar(db, usuario=user, modulo="sugerencias", accion="sugerencia_corregida",
              resumen="Corrección de una sugerencia propia",
              metadata={"sugerencia_id": row.id, "antes": row.texto, "despues": payload.texto})
    row.texto = payload.texto
    db.commit()
    db.refresh(row)
    return serializar(row)
