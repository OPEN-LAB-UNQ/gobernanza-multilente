"""Aviso por correo al docente cuando un participante escribe en el espacio docente de la Incubadora.

Corre después de responder la carga (BackgroundTasks) con su propia sesión: si el SMTP falla o tarda, la
consulta ya quedó guardada. Cada aviso deja un evento en la bitácora con el id del mensaje; si ya hay uno
«enviada» para ese mensaje no se vuelve a mandar (una consulta = un aviso).
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy.orm import Session

import models
from services import actividad as actividad_svc
from services import notificaciones

log = logging.getLogger(__name__)

ACCION_AVISO = "aviso_docente_consulta"
REMITENTE_CONSULTA = "consulta_docente"
REMITENTE_DOCENTE = "docente"


def _aviso_ya_enviado(db: Session, proyecto_id: int, mensaje_id: int) -> bool:
    eventos = db.query(models.ActivityEvent).filter(
        models.ActivityEvent.proyecto_id == proyecto_id,
        models.ActivityEvent.accion == ACCION_AVISO,
    ).all()
    return any((e.metadata_evento or {}).get("mensaje_id") == mensaje_id
               and (e.metadata_evento or {}).get("estado") == "enviada" for e in eventos)


def avisar_consulta_docente(bind: Any, mensaje_id: int) -> str:
    """Tarea en segundo plano. Nunca levanta: devuelve el estado y lo deja registrado."""
    try:
        with Session(bind=bind) as db:
            mensaje = db.get(models.MensajeProyectoIA, mensaje_id)
            if not mensaje or mensaje.remitente != REMITENTE_CONSULTA:
                return "omitida"
            proyecto = db.get(models.ProyectoIA, mensaje.proyecto_id)
            if _aviso_ya_enviado(db, mensaje.proyecto_id, mensaje_id):
                return "duplicado"
            estado, error = notificaciones.enviar_aviso_consulta_docente(
                notificaciones.destinatarios_docente(), mensaje.proyecto_id,
                proyecto.titulo if proyecto else None, mensaje.creado_en,
            )
            if estado != "enviada":
                log.warning("aviso al docente por la consulta %s: %s (%s)", mensaje_id, estado, error)
            actividad_svc.registrar(
                db, usuario=None, modulo="incubadora", accion=ACCION_AVISO,
                resumen="Aviso por correo al docente de una consulta nueva",
                proyecto_id=mensaje.proyecto_id,
                metadata={"mensaje_id": mensaje_id, "estado": estado, "error": (error or "")[:200] or None},
            )
            db.commit()
            return estado
    except Exception:  # noqa: BLE001 — el aviso nunca debe afectar la consulta ya guardada.
        log.exception("no se pudo procesar el aviso al docente de la consulta %s", mensaje_id)
        return "error"


def consultas_sin_respuesta(db: Session, ahora: dt.datetime | None = None, mas_de_dias: int = -1) -> list[dict]:
    """Consultas posteriores a la última respuesta docente de cada proyecto (misma regla que
    `_consulta_docente_pendiente`), con más de `mas_de_dias` días de antigüedad. Sin texto ni datos personales."""
    ahora = ahora or models.now()
    salida = []
    for proyecto in db.query(models.ProyectoIA).all():
        canal = sorted(
            (m for m in (proyecto.mensajes or []) if m.remitente in {REMITENTE_CONSULTA, REMITENTE_DOCENTE}),
            key=lambda m: (m.creado_en or dt.datetime.min, m.id or 0),
        )
        ultima_respuesta = max((i for i, m in enumerate(canal) if m.remitente == REMITENTE_DOCENTE), default=-1)
        for m in canal[ultima_respuesta + 1:]:
            dias = (ahora - m.creado_en).days if m.creado_en else 0
            if dias > mas_de_dias:
                salida.append({"mensaje_id": m.id, "proyecto_id": proyecto.id, "titulo": proyecto.titulo,
                               "creado_en": m.creado_en, "dias": dias})
    return sorted(salida, key=lambda p: (p["creado_en"] or dt.datetime.min, p["mensaje_id"]))
