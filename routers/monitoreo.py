"""Gobernanza Monitoreo: seguimiento de la implementacion real de un proyecto de Incubadora.

Multilente lee datos ya producidos e Incubadora acompana el diseno de una
implementacion; Monitoreo cubre el tramo siguiente, cuando el proyecto ya
opera: registra avances, riesgos, decisiones humanas, indicadores y
aprendizajes sobre la operacion real, con la misma disciplina de estado
explicito y trazabilidad que ya rige en routers/aprendizajes_incubadora.py.
No mide desempeno de personas ni compara proyectos entre si.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from config import settings
from core.auth import get_current_user
from database import get_db
from routers.aprendizajes import _redactar_aprendizaje
from services import actividad as actividad_svc
from services import plural

router = APIRouter(prefix="/api/monitoreo", tags=["monitoreo"])

TIPOS_REGISTRO = {
    "avance": "Avance",
    "riesgo": "Riesgo",
    "decision": "Decision",
    "indicador": "Indicador",
    "aprendizaje": "Aprendizaje",
}

ESTADOS_REGISTRO = {"abierto", "en_curso", "resuelto", "descartado"}


def _texto_seguro(valor: object, max_chars: int) -> str:
    texto = _redactar_aprendizaje(str(valor or "").strip())
    return texto[:max_chars].strip()


def _proyecto_o_404(db: Session, proyecto_id: int) -> models.ProyectoIA:
    proyecto = db.get(models.ProyectoIA, proyecto_id)
    if not proyecto:
        raise HTTPException(404, "proyecto no encontrado")
    return proyecto


def _exigir_acceso(proyecto: models.ProyectoIA, usuario: models.Usuario) -> None:
    if usuario.rol != "admin" and proyecto.usuario_id != usuario.id:
        raise HTTPException(403, "no tenes acceso a este proyecto")


def _habilitado(proyecto: models.ProyectoIA) -> bool:
    return settings.monitoreo_proyecto_id is not None and proyecto.id == settings.monitoreo_proyecto_id


def _exigir_piloto(proyecto: models.ProyectoIA) -> None:
    if not _habilitado(proyecto):
        raise HTTPException(403, "Monitoreo está habilitado únicamente para el proyecto ganador del piloto. Este proyecto permanece en cartera; su historial es de solo lectura.")


def _registro_out(registro: models.RegistroMonitoreo) -> dict[str, Any]:
    return {
        "id": registro.id,
        "proyecto_id": registro.proyecto_id,
        "usuario_id": registro.usuario_id,
        "tipo": registro.tipo,
        "titulo": registro.titulo,
        "contenido": _redactar_aprendizaje(registro.contenido),
        "estado": registro.estado,
        "valor_indicador": registro.valor_indicador,
        "metadata": registro.metadata_evento or {},
        "creado_en": registro.creado_en.isoformat() if registro.creado_en else None,
    }


def _metricas_registros(registros: list[models.RegistroMonitoreo]) -> dict[str, Any]:
    por_tipo: dict[str, int] = {}
    por_estado: dict[str, int] = {}
    for registro in registros:
        por_tipo[registro.tipo] = por_tipo.get(registro.tipo, 0) + 1
        por_estado[registro.estado] = por_estado.get(registro.estado, 0) + 1
    abiertos = por_estado.get("abierto", 0) + por_estado.get("en_curso", 0)
    cerrados = por_estado.get("resuelto", 0) + por_estado.get("descartado", 0)
    if not registros:
        lectura = "Todavía no hay seguimiento registrado. Agregá el primer avance, riesgo, indicador o decisión cuando el proyecto empiece a operar."
    elif abiertos:
        lectura = (f"Hay {plural.contar(abiertos, 'registro')} que todavía "
                   f"{'requiere' if abiertos == 1 else 'requieren'} seguimiento. "
                   "Los cambios de estado quedan asociados a la persona que los realiza.")
    else:
        lectura = "Todos los registros tienen cierre explícito. El seguimiento está al día y puede retomarse cuando aparezca un nuevo avance o riesgo."
    return {"total_registros": len(registros), "por_tipo": por_tipo, "por_estado": por_estado,
            "abiertos": abiertos, "cerrados": cerrados, "lectura": lectura}


@router.get("/proyecto/{proyecto_id}")
def listar_monitoreo(
    proyecto_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    proyecto = _proyecto_o_404(db, proyecto_id)
    _exigir_acceso(proyecto, usuario)
    registros = (
        db.query(models.RegistroMonitoreo)
        .filter(models.RegistroMonitoreo.proyecto_id == proyecto_id)
        .order_by(models.RegistroMonitoreo.creado_en.desc(), models.RegistroMonitoreo.id.desc())
        .all()
    )
    return {
        "proyecto_id": proyecto_id,
        "proyecto_titulo": proyecto.titulo or "Proyecto",
        "habilitado": _habilitado(proyecto),
        "alcance": "Piloto habilitado: seguimiento del proyecto ganador." if _habilitado(proyecto) else "En cartera; Monitoreo no habilitado en esta etapa. Los registros anteriores se conservan como historial de solo lectura.",
        "registros": [_registro_out(r) for r in registros],
        "metricas": _metricas_registros(registros),
    }


@router.post("/proyecto/{proyecto_id}")
def registrar_monitoreo(
    proyecto_id: int,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    proyecto = _proyecto_o_404(db, proyecto_id)
    _exigir_acceso(proyecto, usuario)
    _exigir_piloto(proyecto)

    tipo = str(payload.get("tipo") or "").strip()
    if tipo not in TIPOS_REGISTRO:
        raise HTTPException(422, "tipo de registro invalido")

    estado = str(payload.get("estado") or "abierto").strip()
    if estado not in ESTADOS_REGISTRO:
        raise HTTPException(422, "estado de registro invalido")

    titulo = _texto_seguro(payload.get("titulo"), 160)
    contenido = _texto_seguro(payload.get("contenido"), 1800)
    if not titulo or not contenido:
        raise HTTPException(422, "titulo y contenido son obligatorios")

    valor_indicador = None
    if tipo == "indicador" and payload.get("valor_indicador") is not None:
        try:
            valor_indicador = float(payload["valor_indicador"])
        except (TypeError, ValueError):
            raise HTTPException(422, "valor_indicador invalido")

    registro = models.RegistroMonitoreo(
        proyecto_id=proyecto_id,
        usuario_id=usuario.id,
        tipo=tipo,
        titulo=titulo,
        contenido=contenido,
        estado=estado,
        valor_indicador=valor_indicador,
        metadata_evento={"tipo_label": TIPOS_REGISTRO[tipo]},
    )
    db.add(registro)
    actividad_svc.registrar(
        db,
        usuario=usuario,
        modulo="monitoreo",
        accion="registro_monitoreo_creado",
        resumen=f"Registro de monitoreo ({tipo}) creado",
        proyecto_id=proyecto_id,
        metadata={"tipo": tipo, "estado": estado},
    )
    db.commit()
    return listar_monitoreo(proyecto_id, db, usuario)


@router.patch("/registros/{registro_id}")
def actualizar_estado_monitoreo(
    registro_id: int,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    estado = str(payload.get("estado") or "").strip()
    if estado not in ESTADOS_REGISTRO:
        raise HTTPException(422, "estado de registro invalido")
    registro = db.get(models.RegistroMonitoreo, registro_id)
    if not registro:
        raise HTTPException(404, "registro no encontrado")
    proyecto = _proyecto_o_404(db, registro.proyecto_id)
    _exigir_acceso(proyecto, usuario)
    _exigir_piloto(proyecto)
    anterior = registro.estado
    registro.estado = estado
    metadata = dict(registro.metadata_evento or {})
    cambios = list(metadata.get("cambios_estado") or [])
    cambios.append({
        "de": anterior,
        "a": estado,
        "usuario_id": usuario.id,
        "fecha": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    metadata["cambios_estado"] = cambios
    registro.metadata_evento = metadata
    db.add(registro)
    actividad_svc.registrar(
        db,
        usuario=usuario,
        modulo="monitoreo",
        accion="estado_monitoreo_actualizado",
        resumen="Estado de seguimiento actualizado por una persona autorizada",
        proyecto_id=registro.proyecto_id,
        metadata={"registro_id": registro.id, "de": anterior, "a": estado},
    )
    db.commit()
    db.refresh(registro)
    return _registro_out(registro)
