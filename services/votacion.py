"""Configuración de la actividad pedagógica; no importa módulos de evaluación."""
import datetime as dt
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

import models
from services import grupos

ALCANCE = "Preferencias de una actividad pedagógica. No mide calidad, esfuerzo ni aptitud; no modifica R-1, la evaluación docente, sellos ni Monitoreo."


class Configuracion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cohorte: str = Field(min_length=3, max_length=160)
    grupo: Optional[str] = Field(default=None, max_length=60)  # grupo de cursada; vacío es el grupo por defecto
    activa: bool = False
    primera_vuelta_abierta: bool = False
    segunda_vuelta_abierta: bool = False
    fecha_apertura_1: Optional[dt.datetime] = None
    fecha_cierre_1: Optional[dt.datetime] = None
    fecha_apertura_2: Optional[dt.datetime] = None
    fecha_cierre_2: Optional[dt.datetime] = None
    proyectos_ids: list[int] = Field(min_length=1, max_length=500)
    finalistas: list[int] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def coherencia(self):
        self.grupo = grupos.normalizar(self.grupo)
        if self.primera_vuelta_abierta and self.segunda_vuelta_abierta:
            raise ValueError("Abrir una etapa por vez")
        if self.segunda_vuelta_abierta and len(self.finalistas) < 2:
            raise ValueError("Elegir al menos dos finalistas")
        if not set(self.finalistas) <= set(self.proyectos_ids) or len(set(self.proyectos_ids)) != len(self.proyectos_ids) or len(set(self.finalistas)) != len(self.finalistas):
            raise ValueError("Proyectos o finalistas inconsistentes")
        for etapa in (1, 2):
            for campo in (f"fecha_apertura_{etapa}", f"fecha_cierre_{etapa}"):
                valor = getattr(self, campo)
                if valor and valor.tzinfo:
                    setattr(self, campo, valor.astimezone(dt.timezone.utc).replace(tzinfo=None))
            inicio, fin = getattr(self, f"fecha_apertura_{etapa}"), getattr(self, f"fecha_cierre_{etapa}")
            if inicio and fin and inicio >= fin:
                raise ValueError("Fechas de apertura/cierre incompatibles")
        return self


def activa_del_grupo(db, usuario=None, bloquear=False):
    """La actividad activa del grupo de quien consulta (0.10.62), o None. La administración ve la primera activa."""
    q = db.query(models.ActividadVotacion).filter(models.ActividadVotacion.activa.is_(True))
    if not grupos.ve_todo(usuario):
        q = q.filter(grupos.filtro(models.ActividadVotacion.grupo, grupos.de(usuario)))
    q = q.order_by(models.ActividadVotacion.id.desc())
    if bloquear:
        q = q.with_for_update()
    return q.first()


def activa(db, bloquear=False, usuario=None):
    actividad = activa_del_grupo(db, usuario, bloquear)
    if not actividad:
        raise HTTPException(409, "No hay actividad de votación activa")
    return actividad


def abierta(actividad, etapa):
    flag = actividad.primera_vuelta_abierta if etapa == 1 else actividad.segunda_vuelta_abierta
    inicio, fin = getattr(actividad, f"fecha_apertura_{etapa}"), getattr(actividad, f"fecha_cierre_{etapa}")
    ahora = models.now()
    return bool(actividad.activa and flag and (inicio is None or ahora >= inicio) and (fin is None or ahora < fin))


def salida(a):
    return {**{c.name: getattr(a, c.name) for c in models.ActividadVotacion.__table__.columns}, "alcance": ALCANCE}
