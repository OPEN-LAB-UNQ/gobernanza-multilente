"""Registro liviano de actividad pedagogica y operativa.

La bitacora guarda hechos y metadatos, no duplica contenidos completos de
chats o informes. Sirve para reconstruir recorridos y medir aprendizaje sin
sumar carga al participante.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

import models


def registrar(
    db: Session,
    *,
    usuario: models.Usuario | None = None,
    modulo: str,
    accion: str,
    resumen: str | None = None,
    informe_id: int | None = None,
    proyecto_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> models.ActivityEvent:
    evento = models.ActivityEvent(
        usuario_id=usuario.id if usuario else None,
        informe_id=informe_id,
        proyecto_id=proyecto_id,
        modulo=modulo[:40],
        accion=accion[:80],
        resumen=(resumen or "")[:300] or None,
        metadata_evento=metadata or {},
    )
    db.add(evento)
    return evento
