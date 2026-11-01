"""Tope diario de uso de IA por usuario.

Cada análisis consulta a los proveedores de triangulación y cada mensaje de la Incubadora a un
modelo: sin un tope, una sola cuenta podía generar un costo alto. Los valores se fijan en
`.env` y son holgados: en la cohorte de septiembre de 2026 el máximo diario fue 6 análisis y 77
mensajes por persona. La administración queda exenta. Se cuenta sobre las últimas 24 horas con
lo que ya registra la base; no hace falta una tabla nueva.
"""
from __future__ import annotations

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

import models
from config import settings


def _desde() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(hours=24)


def _turno(db: Session, usuario: models.Usuario) -> None:
    """Serializa los pedidos de un mismo usuario hasta el próximo commit.

    Sin esto, varios pedidos simultáneos contaban lo ya registrado, pasaban todos el
    control y recién después se registraban. El bloqueo es por usuario y de transacción
    (se libera solo en el commit o rollback); en SQLite, que usan los tests, no hace falta.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:clave)"), {"clave": 7_310_000 + int(usuario.id)})


def _rechazar(limite: int, que: str) -> None:
    raise HTTPException(
        429,
        f"Llegaste al tope de {limite} {que} en 24 horas. Podés seguir más tarde; si necesitás más, "
        "escribile a la administración del curso.",
    )


def verificar_analisis(db: Session, usuario: models.Usuario) -> None:
    limite = int(settings.limite_analisis_ia_dia or 0)
    if not limite or usuario.rol == "admin":
        return
    _turno(db, usuario)
    desde = _desde()
    # Jobs que llamaron (o van a llamar) a la IA: no cuentan los fallidos, que se pueden
    # reintentar, ni los que solo reabren una devolución ya hecha (nunca se iniciaron), ni las
    # revisiones rápidas, que no usan IA.
    en_cola = (
        db.query(models.AnalysisJob)
        .filter(models.AnalysisJob.usuario_id == usuario.id, models.AnalysisJob.creado_en >= desde,
                models.AnalysisJob.estado != "error",
                or_(models.AnalysisJob.resultado["fase"].as_string().is_(None),
                    models.AnalysisJob.resultado["fase"].as_string() != "interpretacion"),
                or_(models.AnalysisJob.resultado["modo_revision"].as_string().is_(None),
                    models.AnalysisJob.resultado["modo_revision"].as_string() != "rapida"),
                ~((models.AnalysisJob.estado == "finalizado") & models.AnalysisJob.iniciado_en.is_(None)))
        .count()
    )
    # Análisis directos (/informes/{id}/analizar y su versión en vivo): no crean job.
    directos = (
        db.query(models.ActivityEvent)
        .filter(models.ActivityEvent.usuario_id == usuario.id, models.ActivityEvent.creado_en >= desde,
                models.ActivityEvent.accion.in_(("analisis_solicitado", "analisis_stream_solicitado")))
        .count()
    )
    if en_cola + directos >= limite:
        _rechazar(limite, "análisis con IA")


def reservar_interpretacion(db: Session, usuario: models.Usuario, *, detallada=False, informe_id=None):
    """Las propuestas y relecturas también consumen IA, aunque no terminen en análisis."""
    from services import actividad
    limite = int(settings.limite_analisis_ia_dia or 0)
    if limite and usuario.rol != "admin":
        _turno(db, usuario)
        usadas = db.query(models.ActivityEvent).filter(models.ActivityEvent.usuario_id == usuario.id,
            models.ActivityEvent.creado_en >= _desde(), models.ActivityEvent.accion == "interpretacion_solicitada").count()
        if usadas >= limite:
            _rechazar(limite, "lecturas previas con IA")
    actividad.registrar(db, usuario=usuario, modulo="multilente", accion="interpretacion_solicitada",
        resumen="Relectura detallada" if detallada else "Interpretación previa a controles", informe_id=informe_id,
        metadata={"detallada": bool(detallada)})
    db.commit()  # cuenta también una llamada fallida; libera el turno antes de la red


def verificar_encolado(db: Session, usuario: models.Usuario, informe: models.Informe) -> None:
    """Tope al encolar: reabrir un análisis hecho o en curso no llama a la IA ni gasta cupo."""
    if informe.devolucion:
        return
    en_curso = (
        db.query(models.AnalysisJob.id)
        .filter(models.AnalysisJob.informe_id == informe.id, models.AnalysisJob.estado.in_(("pendiente", "procesando")))
        .first()
    )
    if not en_curso:
        verificar_analisis(db, usuario)


def verificar_incubadora(db: Session, usuario: models.Usuario) -> None:
    limite = int(settings.limite_mensajes_incubadora_dia or 0)
    if not limite or usuario.rol == "admin":
        return
    _turno(db, usuario)
    usados = (
        db.query(models.MensajeProyectoIA)
        .filter(models.MensajeProyectoIA.usuario_id == usuario.id,
                models.MensajeProyectoIA.remitente == "participante",
                models.MensajeProyectoIA.creado_en >= _desde())
        .count()
    )
    if usados >= limite:
        _rechazar(limite, "mensajes a la IA de la Incubadora")


def verificar_exploracion(db: Session, usuario: models.Usuario) -> None:
    limite = int(settings.limite_analisis_ia_dia or 0)
    if not limite or usuario.rol == "admin":
        return
    _turno(db, usuario)
    # Cada pedido llama a la IA aunque repita informe: se cuentan pedidos de quien explora.
    usados = (
        db.query(models.ActivityEvent)
        .filter(models.ActivityEvent.usuario_id == usuario.id, models.ActivityEvent.creado_en >= _desde(),
                models.ActivityEvent.accion == "exploracion_generada")
        .count()
    )
    if usados >= limite:
        _rechazar(limite, "exploraciones con IA")
