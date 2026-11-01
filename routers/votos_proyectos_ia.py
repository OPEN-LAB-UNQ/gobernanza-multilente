"""Votacion justificada entre proyectos de la incubadora."""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from core.auth import get_current_user, require_admin
from database import get_db
from services import actividad as actividad_svc
from services import grupos, votacion

router = APIRouter(prefix="/proyectos-ia", tags=["proyectos-ia-votos"])

ALCANCE_VOTACION = votacion.ALCANCE


class ProyectoIAVotoCreate(BaseModel):
    actividad_id: Optional[int] = None
    proyecto_id: int
    justificacion: str = Field(min_length=40, max_length=1200)


class ProyectoIAVotoSegundaVueltaCreate(ProyectoIAVotoCreate):
    pass


def _voto_out(voto: models.VotoProyectoIA) -> dict[str, Any]:
    return {
        "id": voto.id,
        "proyecto_id": voto.proyecto_id,
        "usuario_id": voto.usuario_id,
        "justificacion": voto.justificacion,
        "creado_en": voto.creado_en.isoformat() if voto.creado_en else None,
        "actualizado_en": voto.actualizado_en.isoformat() if voto.actualizado_en else None,
    }


def _voto_segunda_out(voto: models.VotoSegundaVuelta) -> dict[str, Any]:
    return {
        "id": voto.id,
        "actividad_id": voto.actividad_id,
        "justificacion": voto.justificacion,
        "proyecto_id": voto.proyecto_id,
        "usuario_id": voto.usuario_id,
        "creado_en": voto.creado_en.isoformat() if voto.creado_en else None,
        "actualizado_en": voto.actualizado_en.isoformat() if voto.actualizado_en else None,
    }


def _resultados_primera_vuelta(db: Session, actividad=None) -> list[dict[str, Any]]:
    actividad = actividad or votacion.activa(db)
    # Sólo los del grupo de la votación, aunque alguna cuenta haya cambiado de grupo después de armarla (0.10.62).
    proyectos = db.query(models.ProyectoIA).join(models.Usuario, models.Usuario.id == models.ProyectoIA.usuario_id).filter(
        models.ProyectoIA.id.in_(actividad.proyectos_ids),
        models.ProyectoIA.titulo.isnot(None),
        grupos.filtro(models.Usuario.grupo, actividad.grupo),
    ).all()
    conteo: dict[int, int] = {}
    for voto in db.query(models.VotoProyectoIA).filter(models.VotoProyectoIA.actividad_id == actividad.id).all():
        conteo[voto.proyecto_id] = conteo.get(voto.proyecto_id, 0) + 1
    resultados = [
        {
            "proyecto_id": proyecto.id,
            "titulo": proyecto.titulo,
            "organismo_area": proyecto.organismo_area,
            "votos": int(conteo.get(proyecto.id, 0)),
        }
        for proyecto in proyectos
    ]
    return sorted(resultados, key=lambda item: (-item["votos"], item["proyecto_id"]))


def _del_grupo(db: Session, proyecto: models.ProyectoIA, actividad) -> bool:
    """El proyecto es del grupo de la votación (su dueño pudo cambiar de grupo después de armarla)."""
    dueno = db.get(models.Usuario, proyecto.usuario_id)
    return grupos.normalizar(getattr(dueno, "grupo", None)) == grupos.normalizar(actividad.grupo)


@router.post("/votos")
def votar_proyecto_ia(
    payload: ProyectoIAVotoCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actividad = votacion.activa(db, bloquear=True, usuario=usuario)
    if payload.actividad_id is not None and payload.actividad_id != actividad.id:
        raise HTTPException(409, "La actividad cambió; actualice la pantalla")
    if not votacion.abierta(actividad, 1):
        raise HTTPException(
            status_code=409,
            detail="La primera vuelta esta cerrada. Ya esta disponible la segunda vuelta.",
        )
    if payload.proyecto_id not in actividad.proyectos_ids:
        raise HTTPException(404, "Proyecto fuera de esta actividad")
    proyecto = db.get(models.ProyectoIA, payload.proyecto_id)
    if not proyecto or not (proyecto.titulo or proyecto.organismo_area or proyecto.situacion):
        raise HTTPException(status_code=404, detail="proyecto no encontrado")
    if not _del_grupo(db, proyecto, actividad):
        raise HTTPException(404, "Proyecto fuera de esta actividad")
    if proyecto.usuario_id == usuario.id:
        raise HTTPException(status_code=400, detail="No podes votar tu propio proyecto.")
    justificacion = " ".join(payload.justificacion.split()).strip()
    if len(justificacion) < 40:
        raise HTTPException(status_code=400, detail="La justificacion debe tener al menos 40 caracteres.")

    voto = (
        db.query(models.VotoProyectoIA)
        .filter(models.VotoProyectoIA.usuario_id == usuario.id, models.VotoProyectoIA.actividad_id == actividad.id)
        .first()
    )
    accion = "voto_proyecto_ia_actualizado" if voto else "voto_proyecto_ia_emitido"
    proyecto_anterior = voto.proyecto_id if voto else None
    justificacion_anterior = voto.justificacion if voto else None
    if voto:
        voto.proyecto_id = proyecto.id
        voto.justificacion = justificacion
        voto.actualizado_en = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    else:
        voto = models.VotoProyectoIA(
            actividad_id=actividad.id,
            proyecto_id=proyecto.id,
            usuario_id=usuario.id,
            justificacion=justificacion,
        )
        db.add(voto)
    actividad_svc.registrar(
        db,
        usuario=usuario,
        modulo="incubadora",
        accion=accion,
        resumen="Voto justificado registrado",
        proyecto_id=proyecto.id,
        metadata={
            "actividad_id": actividad.id,
            "proyecto_anterior_id": proyecto_anterior,
            "justificacion_caracteres": len(justificacion),
            "justificacion": justificacion,
            "justificacion_anterior": justificacion_anterior,
        },
    )
    db.commit()
    db.refresh(voto)
    return _voto_out(voto)


@router.get("/votos/historial")
def historial_votos_proyectos_ia(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consulta = db.query(models.ActivityEvent).filter(
        models.ActivityEvent.accion.in_(["voto_proyecto_ia_emitido", "voto_proyecto_ia_actualizado"])
    )
    if usuario.rol != "admin":
        consulta = consulta.filter(models.ActivityEvent.usuario_id == usuario.id)
    return [
        {"id": e.id, "usuario_id": e.usuario_id, "proyecto_id": e.proyecto_id,
         "creado_en": e.creado_en.isoformat(), "detalle": e.metadata_evento}
        for e in consulta.order_by(models.ActivityEvent.creado_en.desc(), models.ActivityEvent.id.desc()).all()
    ]


@router.get("/votos/estado")
def estado_votos_proyectos_ia(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actividad = votacion.activa_del_grupo(db, usuario)
    if actividad is None:
        return {"mi_voto": None, "votos_por_proyecto": {}, "cerrada": True,
                "actividad_id": None, "actividad": None, "alcance": ALCANCE_VOTACION}
    votos = db.query(models.VotoProyectoIA).filter(
        models.VotoProyectoIA.usuario_id == usuario.id, models.VotoProyectoIA.actividad_id == actividad.id
    ).all()
    recibidos = db.query(models.VotoProyectoIA).filter(models.VotoProyectoIA.actividad_id == actividad.id).all()
    por_proyecto: dict[int, int] = {}
    for voto in recibidos:
        por_proyecto[voto.proyecto_id] = por_proyecto.get(voto.proyecto_id, 0) + 1
    propio = votos[0] if votos else None
    return {
        "mi_voto": _voto_out(propio) if propio else None,
        "votos_por_proyecto": por_proyecto,
        "cerrada": not votacion.abierta(actividad, 1),
        "actividad_id": actividad.id, "alcance": ALCANCE_VOTACION,
        "actividad": votacion.salida(actividad),
    }


@router.get("/votos/resultados")
def resultados_votos_proyectos_ia(
    _admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _resultados_primera_vuelta(db)


@router.get("/votos/segunda-vuelta/estado")
def estado_segunda_vuelta(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actividad = votacion.activa(db, usuario=usuario)
    resultados_primera = _resultados_primera_vuelta(db, actividad)
    por_id = {item["proyecto_id"]: item for item in resultados_primera}
    finalistas = [por_id[proyecto_id] for proyecto_id in actividad.finalistas if proyecto_id in por_id]
    conteo_segunda = {proyecto_id: 0 for proyecto_id in actividad.finalistas}
    for voto in db.query(models.VotoSegundaVuelta).filter(models.VotoSegundaVuelta.actividad_id == actividad.id).all():
        if voto.proyecto_id in conteo_segunda:
            conteo_segunda[voto.proyecto_id] += 1
    propio = db.query(models.VotoSegundaVuelta).filter(
        models.VotoSegundaVuelta.usuario_id == usuario.id, models.VotoSegundaVuelta.actividad_id == actividad.id
    ).first()
    return {
        "actividad": votacion.salida(actividad),
        "primera_vuelta": resultados_primera,
        "finalistas": finalistas,
        "segunda_vuelta": {
            "cerrada": not votacion.abierta(actividad, 2),
            "mi_voto": _voto_segunda_out(propio) if propio else None,
            "votos_por_proyecto": conteo_segunda,
            "votos_total": sum(conteo_segunda.values()),
        },
    }


@router.post("/votos/segunda-vuelta")
def votar_segunda_vuelta(
    payload: ProyectoIAVotoSegundaVueltaCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actividad = votacion.activa(db, bloquear=True, usuario=usuario)
    if payload.actividad_id is not None and payload.actividad_id != actividad.id:
        raise HTTPException(409, "La actividad cambió; actualice la pantalla")
    if not votacion.abierta(actividad, 2):
        raise HTTPException(
            status_code=409,
            detail="La segunda vuelta esta cerrada. Los resultados finales ya estan disponibles.",
        )
    if payload.proyecto_id not in actividad.finalistas:
        raise HTTPException(status_code=400, detail="Solo se puede votar por uno de los dos proyectos finalistas.")
    proyecto = db.get(models.ProyectoIA, payload.proyecto_id)
    if not proyecto or not _del_grupo(db, proyecto, actividad):
        raise HTTPException(status_code=404, detail="Proyecto finalista no encontrado.")

    justificacion = " ".join(payload.justificacion.split())
    if len(justificacion) < 40:
        raise HTTPException(422, "La justificación debe tener al menos 40 caracteres")
    voto = db.query(models.VotoSegundaVuelta).filter(
        models.VotoSegundaVuelta.usuario_id == usuario.id, models.VotoSegundaVuelta.actividad_id == actividad.id
    ).first()
    proyecto_anterior = voto.proyecto_id if voto else None
    accion = "voto_segunda_vuelta_actualizado" if voto else "voto_segunda_vuelta_emitido"
    if voto:
        voto.proyecto_id = proyecto.id
        voto.actualizado_en = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    else:
        voto = models.VotoSegundaVuelta(proyecto_id=proyecto.id, usuario_id=usuario.id, actividad_id=actividad.id)
        db.add(voto)
    voto.justificacion = justificacion
    actividad_svc.registrar(
        db,
        usuario=usuario,
        modulo="incubadora",
        accion=accion,
        resumen="Voto de segunda vuelta registrado",
        proyecto_id=proyecto.id,
        metadata={"proyecto_anterior_id": proyecto_anterior, "ronda": 2, "actividad_id": actividad.id, "justificacion": justificacion},
    )
    db.commit()
    db.refresh(voto)
    return _voto_segunda_out(voto)


@router.get("/votos/actividades")
def actividades(db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    return [votacion.salida(a) for a in db.query(models.ActividadVotacion).order_by(models.ActividadVotacion.id.desc())]


def _guardar_actividad(db, user, payload, actividad=None):
    if db.query(models.ActividadVotacion).filter(models.ActividadVotacion.cohorte == payload.cohorte,
            models.ActividadVotacion.id != (actividad.id if actividad else -1)).first():
        raise HTTPException(409, "La cohorte ya existe")
    ids = {p.id for p in db.query(models.ProyectoIA).filter(models.ProyectoIA.id.in_(payload.proyectos_ids))}
    if ids != set(payload.proyectos_ids):
        raise HTTPException(422, "Hay proyectos inexistentes")
    # Una votación es de un solo grupo: sus proyectos no pueden ser de otro (0.10.62).
    duenos = (db.query(models.ProyectoIA.id, models.Usuario.grupo)
              .join(models.Usuario, models.Usuario.id == models.ProyectoIA.usuario_id)
              .filter(models.ProyectoIA.id.in_(payload.proyectos_ids)))
    ajenos = sorted(pid for pid, grupo in duenos if grupos.normalizar(grupo) != payload.grupo)
    if ajenos:
        raise HTTPException(422, f"Hay proyectos de otro grupo: {ajenos}")
    if actividad:
        if actividad.proyectos_ids != payload.proyectos_ids and db.query(models.VotoProyectoIA).filter(models.VotoProyectoIA.actividad_id == actividad.id).first():
            raise HTTPException(409, "No se pueden cambiar los proyectos de una actividad que ya recibió votos")
        if actividad.finalistas != payload.finalistas and db.query(models.VotoSegundaVuelta).filter(models.VotoSegundaVuelta.actividad_id == actividad.id).first():
            raise HTTPException(409, "No se pueden cambiar finalistas después de recibir votos")
    anterior = votacion.salida(actividad) if actividad else None
    if payload.activa:
        # Activar una votación apaga sólo la activa de su mismo grupo.
        db.query(models.ActividadVotacion).filter(
            models.ActividadVotacion.activa.is_(True), grupos.filtro(models.ActividadVotacion.grupo, payload.grupo)
        ).update({models.ActividadVotacion.activa: False})
        db.flush()
    if actividad is None:
        actividad = models.ActividadVotacion()
        db.add(actividad)
    for clave, valor in payload.model_dump().items():
        setattr(actividad, clave, valor)
    actividad.actualizado_por_id = user.id
    db.flush()
    from fastapi.encoders import jsonable_encoder
    actividad_svc.registrar(db, usuario=user, modulo="votacion", accion="actividad_configurada",
        resumen="Configuración pedagógica de votación actualizada", metadata=jsonable_encoder({"antes": anterior, "despues": votacion.salida(actividad)}))
    db.commit()
    return votacion.salida(actividad)


@router.post("/votos/actividades")
def crear_actividad(payload: votacion.Configuracion, db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    return _guardar_actividad(db, user, payload)


@router.put("/votos/actividades/{actividad_id}")
def configurar_actividad(actividad_id: int, payload: votacion.Configuracion, db: Session = Depends(get_db), user: models.Usuario = Depends(require_admin)):
    actividad = db.query(models.ActividadVotacion).filter(models.ActividadVotacion.id == actividad_id).with_for_update().first()
    if not actividad:
        raise HTTPException(404, "Actividad no encontrada")
    return _guardar_actividad(db, user, payload, actividad)
