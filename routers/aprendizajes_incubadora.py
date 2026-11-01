"""Aprendizaje curado propio de Gobernanza Incubadora.

Aplica a la etapa de desarrollo de implementaciones la misma disciplina que
routers/aprendizajes.py ya aplica a la calibracion de las lentes de Multilente:
un error o tema que se repite en la practica no queda como observacion suelta
del rizoma, sino que un docente puede cristalizarlo como criterio versionado,
sujeto a validacion humana y reversible. Redacta secretos antes de exponer el
contenido, igual que el modulo de aprendizajes de Multilente.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from core.auth import get_current_user, require_admin
from database import get_db
from routers.aprendizajes import EntradaAprendizaje, _parsear_aprendizajes, _redactar_aprendizaje
from routers.proyectos_ia import TEMAS_RIZOMA, _proyectos_visibles, _tema_presente, _texto_caso
from services import actividad as actividad_svc
from services import grupos

router = APIRouter(prefix="/api/incubadora", tags=["aprendizajes-incubadora"])

BASE_DIR = Path(__file__).parent.parent
APRENDIZAJES_PATH = BASE_DIR / "APRENDIZAJES_INCUBADORA.md"

TIPOS_APRENDIZAJE = {
    "error_recurrente": "Error recurrente",
    "brecha_formativa": "Brecha formativa",
    "criterio_validado": "Criterio validado",
    "criterio_descartado": "Criterio descartado",
    "ajuste_consigna": "Ajuste de consigna o tutor IA",
}

ESTADOS_APRENDIZAJE = {"propuesto", "validado", "implementado", "descartado"}


def _texto_seguro(valor: object, max_chars: int) -> str:
    texto = _redactar_aprendizaje(str(valor or "").strip())
    return texto[:max_chars].strip()


def _evento_out(evento: models.AprendizajeIncubadora) -> dict[str, Any]:
    return {
        "id": evento.id,
        "tipo": evento.tipo,
        "titulo": evento.titulo,
        "contenido": _redactar_aprendizaje(evento.contenido),
        "estado": evento.estado,
        "tema": evento.tema,
        "proyecto_id": evento.proyecto_id,
        "usuario_id": evento.usuario_id,
        "metadata": evento.metadata_evento or {},
        "creado_en": evento.creado_en.isoformat() if evento.creado_en else None,
    }


def _metricas_eventos(eventos: list[models.AprendizajeIncubadora]) -> dict[str, Any]:
    por_tipo: dict[str, int] = {}
    por_estado: dict[str, int] = {}
    por_tema: dict[str, int] = {}
    for evento in eventos:
        por_tipo[evento.tipo] = por_tipo.get(evento.tipo, 0) + 1
        por_estado[evento.estado] = por_estado.get(evento.estado, 0) + 1
        tema = evento.tema or "sin_tema"
        por_tema[tema] = por_tema.get(tema, 0) + 1
    return {"total_eventos": len(eventos), "por_tipo": por_tipo, "por_estado": por_estado, "por_tema": por_tema}


def _cruces_rizoma(db: Session, usuario: models.Usuario | None = None) -> list[dict[str, Any]]:
    """Cuenta cuantos proyectos activos del grupo de quien consulta tocan cada tema del rizoma, sin exponer casos."""
    proyectos = _proyectos_visibles(db, usuario=usuario)
    cruces = []
    for tema in TEMAS_RIZOMA:
        cantidad = sum(1 for p in proyectos if _tema_presente(_texto_caso(p), tema["claves"]))
        if cantidad:
            cruces.append({"nombre": tema["nombre"], "cantidad": cantidad})
    cruces.sort(key=lambda item: item["cantidad"], reverse=True)
    return cruces


def _grupos_de_eventos(db: Session, eventos: list[models.AprendizajeIncubadora]) -> dict[int, str | None]:
    """Grupo de cada evento (0.10.62): el del dueño del proyecto si lo tiene; si no, el de quien lo registró."""
    proyectos = {e.proyecto_id for e in eventos if e.proyecto_id}
    usuarios = {e.usuario_id for e in eventos if e.usuario_id}
    por_proyecto = dict(
        db.query(models.ProyectoIA.id, models.Usuario.grupo)
        .join(models.Usuario, models.Usuario.id == models.ProyectoIA.usuario_id)
        .filter(models.ProyectoIA.id.in_(proyectos))
    ) if proyectos else {}
    por_usuario = dict(db.query(models.Usuario.id, models.Usuario.grupo).filter(models.Usuario.id.in_(usuarios))) if usuarios else {}
    return {e.id: grupos.normalizar(por_proyecto[e.proyecto_id] if e.proyecto_id in por_proyecto else por_usuario.get(e.usuario_id))
            for e in eventos}


def _validar_tema(valor: object) -> str | None:
    tema = str(valor or "").strip()
    if not tema:
        return None
    nombres_validos = {t["nombre"] for t in TEMAS_RIZOMA}
    return tema if tema in nombres_validos else tema[:60]


@router.get("/aprendizaje")
def aprendizaje_incubadora(db: Session = Depends(get_db), usuario: models.Usuario = Depends(get_current_user)):
    texto = ""
    actualizado = None
    intro: list[str] = []
    entradas: list[EntradaAprendizaje] = []
    if APRENDIZAJES_PATH.exists():
        texto = _redactar_aprendizaje(APRENDIZAJES_PATH.read_text(encoding="utf-8"))
        intro, entradas = _parsear_aprendizajes(texto)
        stat = APRENDIZAJES_PATH.stat()
        actualizado = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat().replace("+00:00", "Z")
    eventos = (
        db.query(models.AprendizajeIncubadora)
        .order_by(models.AprendizajeIncubadora.creado_en.desc(), models.AprendizajeIncubadora.id.desc())
        .limit(200)
        .all()
    )
    if grupos.ve_todo(usuario):
        del_grupo = eventos
    else:  # las métricas cuentan sólo eventos del grupo de quien consulta (0.10.62)
        grupo_evento = _grupos_de_eventos(db, eventos)
        del_grupo = [e for e in eventos if grupo_evento[e.id] == grupos.de(usuario)]
    return {
        "fuente": APRENDIZAJES_PATH.name,
        "actualizado": actualizado,
        "markdown": texto,
        "intro": intro,
        "total": len(entradas),
        "entries": entradas,
        # Las notas docentes nombran proyectos y personas: completas solo para la administración;
        # cada participante ve las que se refieren a su propio trabajo.
        "eventos": [_evento_out(evento) for evento in eventos
                    if usuario.rol == "admin" or evento.usuario_id == usuario.id],
        "metricas": _metricas_eventos(del_grupo),
        "rizoma": _cruces_rizoma(db, usuario),
    }


@router.post("/aprendizaje")
def registrar_aprendizaje_incubadora(
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(require_admin),
    usuario: models.Usuario = Depends(get_current_user),
):
    tipo = str(payload.get("tipo") or "error_recurrente").strip()
    if tipo not in TIPOS_APRENDIZAJE:
        raise HTTPException(422, "tipo de aprendizaje invalido")

    estado = str(payload.get("estado") or "propuesto").strip()
    if estado not in ESTADOS_APRENDIZAJE:
        raise HTTPException(422, "estado de aprendizaje invalido")

    titulo = _texto_seguro(payload.get("titulo"), 160)
    contenido = _texto_seguro(payload.get("contenido"), 1800)
    if not titulo or not contenido:
        raise HTTPException(422, "titulo y contenido son obligatorios")

    proyecto_id = payload.get("proyecto_id")
    try:
        proyecto_id_int = int(proyecto_id) if proyecto_id else None
    except (TypeError, ValueError):
        raise HTTPException(422, "proyecto_id invalido")

    tema = _validar_tema(payload.get("tema"))

    evento = models.AprendizajeIncubadora(
        proyecto_id=proyecto_id_int,
        usuario_id=usuario.id,
        tipo=tipo,
        titulo=titulo,
        contenido=contenido,
        estado=estado,
        tema=tema,
        metadata_evento={"fuente": "revision_docente", "tipo_label": TIPOS_APRENDIZAJE[tipo]},
    )
    db.add(evento)
    actividad_svc.registrar(
        db,
        usuario=usuario,
        modulo="incubadora",
        accion="aprendizaje_curado_registrado",
        resumen="Aprendizaje curado de Incubadora registrado",
        proyecto_id=proyecto_id_int,
        metadata={"tipo": tipo, "estado": estado, "tema": tema},
    )
    db.commit()

    fecha = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    bloque = [
        "",
        f"## {fecha} - {titulo}",
        "",
        f"Tipo: {TIPOS_APRENDIZAJE[tipo]}. Estado: {estado}. Proyecto: {proyecto_id_int or '-'}; Tema: {tema or '-'}.",
        "",
        contenido,
        "",
    ]
    APRENDIZAJES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with APRENDIZAJES_PATH.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(bloque))
    return aprendizaje_incubadora(db)


@router.patch("/aprendizaje/eventos/{evento_id}")
def actualizar_estado_aprendizaje_incubadora(
    evento_id: int,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(require_admin),
):
    estado = str(payload.get("estado") or "").strip()
    if estado not in ESTADOS_APRENDIZAJE:
        raise HTTPException(422, "estado de aprendizaje invalido")
    evento = db.get(models.AprendizajeIncubadora, evento_id)
    if not evento:
        raise HTTPException(404, "aprendizaje no encontrado")
    anterior = evento.estado
    evento.estado = estado
    metadata = dict(evento.metadata_evento or {})
    cambios = list(metadata.get("cambios_estado") or [])
    cambios.append({
        "de": anterior,
        "a": estado,
        "usuario_id": admin.id,
        "fecha": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    metadata["cambios_estado"] = cambios[-20:]
    evento.metadata_evento = metadata
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return _evento_out(evento)
