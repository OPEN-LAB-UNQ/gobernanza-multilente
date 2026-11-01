"""Aprendizajes curados: lectura y registro de entradas en APRENDIZAJES.md.

Redacta secretos (API keys, tokens, la contraseña de la app) antes de
exponer el contenido, porque el archivo puede citar configuracion tecnica
al documentar un ajuste.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, TypedDict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

import models
from core.auth import APP_PASSWORD, get_current_user
from database import get_db
from routers.proyectos_ia import USUARIOS_EXCLUIDOS_METRICAS
from services import grupos

router = APIRouter(prefix="/api")

BASE_DIR = Path(__file__).parent.parent
APRENDIZAJES_PATH = BASE_DIR / "APRENDIZAJES.md"

_SECRET_VALUE_RE = re.compile(
    r"(?im)\b(api[_-]?key|token|secret|password|clave|credential|bearer)\b(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")

TIPOS_APRENDIZAJE = {
    "falso_positivo": "Falso positivo",
    "regla_validada": "Regla validada",
    "regla_descartada": "Regla descartada",
    "ajuste_umbral": "Ajuste de umbral",
    "criterio_metodologico": "Criterio metodológico",
}

ESTADOS_APRENDIZAJE = {"propuesto", "validado", "implementado", "descartado"}


class Subseccion(TypedDict):
    titulo: str
    parrafos: list[str]
    items: list[str]


class EntradaAprendizaje(TypedDict):
    titulo: str
    fecha: str | None
    parrafos: list[str]
    items: list[str]
    subsecciones: list[Subseccion]


def _redactar_aprendizaje(texto: str) -> str:
    texto = _SECRET_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redactado>", texto)
    texto = _BEARER_RE.sub("Bearer <redactado>", texto)
    if APP_PASSWORD and len(APP_PASSWORD) >= 8:
        texto = texto.replace(APP_PASSWORD, "<redactado>")
    return texto


def _parsear_aprendizajes(texto: str) -> tuple[list[str], list[EntradaAprendizaje]]:
    entradas: list[EntradaAprendizaje] = []
    intro: list[str] = []
    actual: EntradaAprendizaje | None = None

    def agregar_actual() -> None:
        if actual is not None:
            entradas.append(actual)

    for linea_original in texto.splitlines():
        linea = linea_original.rstrip()
        limpia = linea.strip()
        if linea.startswith("## "):
            agregar_actual()
            titulo = linea[3:].strip()
            fecha = None
            match = re.match(r"(\d{4}-\d{2}-\d{2})\s*[-–]\s*(.+)", titulo)
            if match:
                fecha = match.group(1)
                titulo = match.group(2).strip()
            actual = {"titulo": titulo, "fecha": fecha, "parrafos": [], "items": [], "subsecciones": []}
            continue

        if actual is None:
            if limpia and not limpia.startswith("#"):
                intro.append(limpia)
            continue

        if linea.startswith("### "):
            actual["subsecciones"].append({"titulo": linea[4:].strip(), "parrafos": [], "items": []})
            continue

        if not limpia or limpia == "---":
            continue

        destino: Subseccion | EntradaAprendizaje = actual["subsecciones"][-1] if actual["subsecciones"] else actual
        if limpia.startswith("- "):
            destino["items"].append(limpia[2:].strip())
        elif re.match(r"^\d+\.\s+", limpia):
            destino["items"].append(re.sub(r"^\d+\.\s+", "", limpia).strip())
        elif not limpia.startswith("#"):
            destino["parrafos"].append(limpia)

    agregar_actual()
    return intro, entradas



def _ids_hallazgos(valor: object) -> list[int]:
    if isinstance(valor, (str, int)):
        valor = [valor]
    if not isinstance(valor, list):
        return []
    ids: list[int] = []
    for item in valor[:50]:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def _lente_afectada(db: Session, hallazgo_ids: list[int], valor: object) -> str | None:
    manual = str(valor or "").strip().lower()
    if manual:
        return manual[:30]
    if not hallazgo_ids:
        return None
    lentes = [
        str(row[0])
        for row in db.query(models.Hallazgo.lente)
        .filter(models.Hallazgo.id.in_(hallazgo_ids))
        .distinct()
        .all()
        if row[0]
    ]
    if len(lentes) == 1:
        return lentes[0]
    if len(lentes) > 1:
        return "multilente"
    return None


def _metricas_eventos(eventos: list[models.LearningEvent]) -> dict[str, Any]:
    por_tipo: dict[str, int] = {}
    por_estado: dict[str, int] = {}
    por_lente: dict[str, int] = {}
    for evento in eventos:
        por_tipo[evento.tipo] = por_tipo.get(evento.tipo, 0) + 1
        por_estado[evento.estado] = por_estado.get(evento.estado, 0) + 1
        lente = evento.lente_afectada or "sin_lente"
        por_lente[lente] = por_lente.get(lente, 0) + 1
    return {
        "total_eventos": len(eventos),
        "por_tipo": por_tipo,
        "por_estado": por_estado,
        "por_lente": por_lente,
    }


def _texto_proyecto(proyecto: models.ProyectoIA) -> str:
    return " ".join([
        proyecto.titulo or "",
        proyecto.organismo_area or "",
        proyecto.situacion or "",
        proyecto.entrega_final or "",
    ]).lower()


def _tema_proyecto(texto: str) -> str:
    reglas = [
        (("gedo", "document", "expediente", "tramite", "archivo", "mesa"), "Gestión documental"),
        (("ciudadano", "consulta", "soporte", "notificacion", "capacitación", "capacitacion", "hospital"), "Atención y soporte"),
        (("presupuesto", "gasto", "ejecucion", "ejecución", "credito", "crédito", "subsidio"), "Presupuesto y control"),
        (("dictamen", "jurid", "norma", "resolucion", "resolución", "acto administrativo"), "Jurídico/normativo"),
        (("riesgo", "seguridad", "ciber", "control", "integridad"), "Riesgos y control"),
        (("reporte", "tablero", "indicador", "datos", "analisis", "análisis"), "Datos e indicadores"),
    ]
    for claves, etiqueta in reglas:
        if any(clave in texto for clave in claves):
            return etiqueta
    return "Otros / por definir"


def _contiene(texto: str, claves: tuple[str, ...]) -> bool:
    return any(clave in texto for clave in claves)


def _metricas_proyectos_ia(db: Session, usuario: models.Usuario | None = None) -> dict[str, Any]:
    vacio: dict[str, Any] = {
        "total_proyectos": 0,
        "con_contexto": 0,
        "con_chat_ia": 0,
        "con_entrega": 0,
        "temas": {},
        "brechas": {
            "problema_como_herramienta": 0,
            "sin_evidencia": 0,
            "sin_indicador": 0,
            "gestion_documental": 0,
        },
    }
    try:
        consulta = (
            db.query(models.ProyectoIA)
            .options(selectinload(models.ProyectoIA.mensajes), selectinload(models.ProyectoIA.usuario))
            .join(models.Usuario, models.Usuario.id == models.ProyectoIA.usuario_id)
            .filter(models.Usuario.rol != "admin")
            .filter(~models.Usuario.email.in_(USUARIOS_EXCLUIDOS_METRICAS))
        )
        if not grupos.ve_todo(usuario):  # sólo los proyectos del grupo de quien consulta (0.10.62)
            consulta = consulta.filter(grupos.filtro(models.Usuario.grupo, grupos.de(usuario)))
        proyectos = consulta.all()
    except AttributeError:
        return vacio
    visibles = [
        p for p in proyectos
        if p.titulo or p.organismo_area or p.situacion or p.entrega_final
        or any(m.remitente not in {"ia", "docente"} for m in (p.mensajes or []))
    ]
    temas: dict[str, int] = {}
    brechas = {
        "problema_como_herramienta": 0,
        "sin_evidencia": 0,
        "sin_indicador": 0,
        "gestion_documental": 0,
    }
    con_contexto = 0
    con_chat_ia = 0
    con_entrega = 0
    for proyecto in visibles:
        texto = _texto_proyecto(proyecto)
        tema = _tema_proyecto(texto)
        temas[tema] = temas.get(tema, 0) + 1
        if proyecto.titulo or proyecto.organismo_area or proyecto.situacion:
            con_contexto += 1
        if proyecto.entrega_final:
            con_entrega += 1
        if any(m.remitente == "participante" for m in (proyecto.mensajes or [])):
            con_chat_ia += 1
        if _contiene(texto, ("asistente", "chatbot", "automatiz", "ia para", "inteligente")):
            brechas["problema_como_herramienta"] += 1
        if not _contiene(texto, ("demora", "error", "reclamo", "duplic", "trazabilidad", "pendiente", "tiempo", "volumen", "riesgo", "criterio", "datos")):
            brechas["sin_evidencia"] += 1
        if not _contiene(texto, ("indicador", "medir", "tiempo", "cantidad", "porcentaje", "tasa", "plazo", "frecuencia", "antes", "despues", "después")):
            brechas["sin_indicador"] += 1
        if tema == "Gestión documental":
            brechas["gestion_documental"] += 1
    return {
        "total_proyectos": len(visibles),
        "con_contexto": con_contexto,
        "con_chat_ia": con_chat_ia,
        "con_entrega": con_entrega,
        "temas": dict(sorted(temas.items(), key=lambda item: (-item[1], item[0]))),
        "brechas": brechas,
    }




def _puede_registrar_aprendizaje(usuario: models.Usuario) -> bool:
    return usuario.rol in {"admin", "analista"}


def _puede_aprobar_aprendizaje(usuario: models.Usuario) -> bool:
    return usuario.rol == "admin"


def _validar_permiso_estado(usuario: models.Usuario, estado: str) -> None:
    if not _puede_registrar_aprendizaje(usuario):
        raise HTTPException(403, "tu rol no puede registrar aprendizajes")
    if estado != "propuesto" and not _puede_aprobar_aprendizaje(usuario):
        raise HTTPException(403, "solo un admin puede validar, implementar o descartar aprendizajes")


def _evento_out(evento: models.LearningEvent) -> dict[str, Any]:
    return {
        "id": evento.id,
        "tipo": evento.tipo,
        "titulo": evento.titulo,
        "contenido": _redactar_aprendizaje(evento.contenido),
        "estado": evento.estado,
        "lente_afectada": evento.lente_afectada,
        "informe_id": evento.informe_id,
        "hallazgo_ids": evento.hallazgo_ids or [],
        "usuario_id": evento.usuario_id,
        "metadata": evento.metadata_evento or {},
        "creado_en": evento.creado_en.isoformat() if evento.creado_en else None,
    }

def _texto_seguro_aprendizaje(valor: object, max_chars: int = 1800) -> str:
    texto = _redactar_aprendizaje(str(valor or "").strip())
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto[:max_chars].strip()


def _sin_referencias(texto: str) -> str:
    """Para quien no administra: el criterio aprendido sí, a qué informe y hallazgos remite no."""
    return re.sub(r"Informe: [^;\n]*; Hallazgos: [^;\n]*; ", "", texto)


@router.get("/aprendizaje")
def aprendizaje(db: Session = Depends(get_db), usuario: models.Usuario = Depends(get_current_user)):
    texto = ""
    actualizado = None
    intro: list[str] = []
    entradas: list[EntradaAprendizaje] = []
    if APRENDIZAJES_PATH.exists():
        texto = _redactar_aprendizaje(APRENDIZAJES_PATH.read_text(encoding="utf-8"))
        if usuario.rol != "admin":
            texto = _sin_referencias(texto)
        intro, entradas = _parsear_aprendizajes(texto)
        stat = APRENDIZAJES_PATH.stat()
        actualizado = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat().replace("+00:00", "Z")
    eventos = db.query(models.LearningEvent).order_by(models.LearningEvent.creado_en.desc(), models.LearningEvent.id.desc()).limit(200).all()
    return {
        "fuente": APRENDIZAJES_PATH.name,
        "actualizado": actualizado,
        "markdown": texto,
        "intro": intro,
        "total": len(entradas),
        "entries": entradas,
        # Las métricas son agregadas; el detalle de cada evento (usuario, informe, contenido)
        # sólo lo ve un admin, y cada participante ve los propios.
        "eventos": [_evento_out(evento) for evento in eventos
                    if usuario.rol == "admin" or evento.usuario_id == usuario.id],
        "metricas": _metricas_eventos(eventos),
        "proyecto_ia": _metricas_proyectos_ia(db, usuario),
    }


@router.post("/aprendizaje")
def registrar_aprendizaje(
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    tipo = str(payload.get("tipo") or "criterio_metodologico").strip()
    if tipo not in TIPOS_APRENDIZAJE:
        raise HTTPException(422, "tipo de aprendizaje inválido")

    estado = str(payload.get("estado") or "propuesto").strip()
    if estado not in ESTADOS_APRENDIZAJE:
        raise HTTPException(422, "estado de aprendizaje inválido")
    _validar_permiso_estado(usuario, estado)

    # Una sola línea en el título y ningún encabezado markdown en el contenido: así nadie
    # puede fabricar dentro de APRENDIZAJES.md una entrada «validada» que no lo es.
    titulo = " ".join(_texto_seguro_aprendizaje(payload.get("titulo"), 160).split())
    contenido = "\n".join(
        linea.lstrip("#").lstrip() if linea.lstrip().startswith("#") else linea
        for linea in _texto_seguro_aprendizaje(payload.get("contenido"), 1800).splitlines()
    )
    contenido = "\n".join(
        ("» " + linea) if linea.strip().lower().startswith(("tipo:", "estado:")) else linea
        for linea in contenido.splitlines()
    )
    if not titulo or not contenido:
        raise HTTPException(422, "titulo y contenido son obligatorios")

    informe_id = payload.get("informe_id")
    try:
        informe_id_int = int(informe_id) if informe_id else None
    except (TypeError, ValueError):
        raise HTTPException(422, "informe_id inválido")
    hallazgo_ids = _ids_hallazgos(payload.get("hallazgo_ids"))
    hallazgo_txt = ", ".join(str(x) for x in hallazgo_ids[:12]) or "-"
    lente_afectada = _lente_afectada(db, hallazgo_ids, payload.get("lente_afectada"))
    evento = models.LearningEvent(
        informe_id=informe_id_int,
        usuario_id=usuario.id,
        tipo=tipo,
        titulo=titulo,
        contenido=contenido,
        estado=estado,
        lente_afectada=lente_afectada,
        hallazgo_ids=hallazgo_ids,
        metadata_evento={
            "fuente": "detalle_informe",
            "tipo_label": TIPOS_APRENDIZAJE[tipo],
        },
    )
    db.add(evento)
    db.commit()

    fecha = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    bloque = [
        "",
        f"## {fecha} - {titulo}",
        "",
        f"Tipo: {TIPOS_APRENDIZAJE[tipo]}. Estado: {estado}. Informe: {informe_id_int or '-'}; Hallazgos: {hallazgo_txt}; Lente: {lente_afectada or '-'}.",
        "",
        contenido,
        "",
    ]
    APRENDIZAJES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with APRENDIZAJES_PATH.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(bloque))
    return aprendizaje(db, usuario)



@router.patch("/aprendizaje/eventos/{evento_id}")
def actualizar_estado_aprendizaje(
    evento_id: int,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    if not _puede_aprobar_aprendizaje(usuario):
        raise HTTPException(403, "solo un admin puede cambiar el estado de aprendizajes")
    estado = str(payload.get("estado") or "").strip()
    if estado not in ESTADOS_APRENDIZAJE:
        raise HTTPException(422, "estado de aprendizaje inválido")
    evento = db.get(models.LearningEvent, evento_id)
    if not evento:
        raise HTTPException(404, "aprendizaje no encontrado")
    anterior = evento.estado
    evento.estado = estado
    metadata = dict(evento.metadata_evento or {})
    cambios = list(metadata.get("cambios_estado") or [])
    cambios.append({
        "de": anterior,
        "a": estado,
        "usuario_id": usuario.id,
        "fecha": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    metadata["cambios_estado"] = cambios[-20:]
    evento.metadata_evento = metadata
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return _evento_out(evento)
