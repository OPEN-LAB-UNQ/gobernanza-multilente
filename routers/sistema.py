"""Endpoints de diagnostico, estado de modelos, actividad y health check."""
from __future__ import annotations

import datetime as dt
import logging
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session, defer, load_only

import models
from config import settings
from core.auth import require_admin
from database import SessionLocal, get_db
from routers.proyectos_ia import _conteos_interacciones, _diagnostico_proyecto

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/modelos/status")
def modelos_status():
    estado = {
        "openai": {
            "configurada": bool(settings.openai_api_key),
            "modelo": settings.openai_model,
        },
        "anthropic": {
            "configurada": bool(settings.anthropic_api_key),
            "modelo": settings.anthropic_model,
        },
        "gemini": {
            "configurada": bool(settings.gemini_api_key or settings.google_genai_use_enterprise),
            "modelo": settings.gemini_model,
        },
        "deepseek": {
            "configurada": bool(settings.deepseek_api_key),
            "modelo": settings.deepseek_model,
            "base_url": settings.deepseek_base_url,
        },
        "renderix": {
            "configurada": bool(settings.renderix_api_key),
            "modelo": settings.renderix_model,
            "base_url": settings.renderix_base_url,
        },
        "llama": {
            "configurada": bool(settings.ollama_base_url),
            "modelo": settings.ollama_model,
            "base_url": settings.ollama_base_url,
            "requiere_api_key": bool(settings.ollama_api_key),
        },
        "nota": "Configuración y habilitación administrativa; no constituye una prueba de disponibilidad en tiempo real.",
    }
    for proveedor, modelo in {"openai": "gpt", "anthropic": "claude", "gemini": "gemini",
                             "deepseek": "deepseek", "renderix": "renderix", "llama": "llama"}.items():
        item = estado[proveedor]
        suspendido = not settings.modelo_habilitado(modelo)
        item["habilitada"] = item["configurada"] and not suspendido
        item["motivo"] = "Temporalmente fuera de servicio" if suspendido else ("Sin configurar" if not item["configurada"] else None)
    return estado


def _iso(valor: dt.datetime | None) -> str | None:
    return valor.isoformat() if valor else None


@router.get("/actividad")
def actividad_admin(
    _admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    desde_24h = ahora - dt.timedelta(hours=24)

    usuarios = db.query(models.Usuario).all()
    # Solo conteos y metadatos: sin datos, saneamiento, evidencia ni resultados (decenas de MB).
    informes = db.query(models.Informe).options(defer(models.Informe.datos), defer(models.Informe.saneamiento)).all()
    hallazgos = db.query(models.Hallazgo).options(load_only(models.Hallazgo.id, models.Hallazgo.informe_id)).all()
    jobs = db.query(models.AnalysisJob).options(defer(models.AnalysisJob.resultado)).all()
    decisiones = db.query(models.DecisionDirector).all()
    aprendizajes = db.query(models.LearningEvent).all()
    eventos_actividad = db.query(models.ActivityEvent).all()
    proyectos_ia = db.query(models.ProyectoIA).all()
    mensajes_proyecto_ia = db.query(models.MensajeProyectoIA).all()

    eventos_por_modulo = Counter(evento.modulo for evento in eventos_actividad)
    eventos_por_accion = Counter(evento.accion for evento in eventos_actividad)
    eventos_24h = [evento for evento in eventos_actividad if evento.creado_en is not None and evento.creado_en >= desde_24h]
    evaluaciones_piloto = [
        evento for evento in eventos_actividad
        if evento.modulo == "multilente" and evento.accion == "evaluacion_piloto_registrada"
    ]
    evaluaciones_piloto_por_resultado = Counter(
        str((evento.metadata_evento or {}).get("resultado") or "sin_clasificar")
        for evento in evaluaciones_piloto
    )
    jobs_por_estado = Counter(job.estado for job in jobs)
    modelos_usados: Counter[str] = Counter()
    for job in jobs:
        for modelo in job.modelos or []:
            modelos_usados[str(modelo)] += 1

    usuarios_por_id = {u.id: u for u in usuarios}
    por_usuario: dict[int | None, dict[str, Any]] = {}

    def fila_usuario(usuario_id: int | None) -> dict[str, Any]:
        if usuario_id not in por_usuario:
            usuario = usuarios_por_id.get(usuario_id) if usuario_id is not None else None
            por_usuario[usuario_id] = {
                "usuario_id": usuario_id,
                "email": usuario.email if usuario else "sin_usuario",
                "nombre": usuario.nombre if usuario else "Sin usuario",
                "rol": usuario.rol if usuario else "-",
                "informes": 0,
                "hallazgos": 0,
                "decisiones": 0,
                "proyecto_ia": False,
                "proyecto_estado": None,
                "proyecto_etapa": "Sin iniciar",
                "proyecto_contexto": False,
                "proyecto_mensajes_participante": 0,
                "proyecto_consultas_docente": 0,
                "proyecto_entrega": False,
                "ultimo_informe": None,
                "ultimo_proyecto_ia": None,
            }
        return por_usuario[usuario_id]

    informe_usuario: dict[int, int | None] = {}
    for informe in informes:
        informe_usuario[informe.id] = informe.usuario_id
        fila = fila_usuario(informe.usuario_id)
        fila["informes"] += 1
        if fila["ultimo_informe"] is None or informe.creado_en > fila["ultimo_informe"]:
            fila["ultimo_informe"] = informe.creado_en

    for hallazgo in hallazgos:
        fila_usuario(informe_usuario.get(hallazgo.informe_id))["hallazgos"] += 1

    for decision in decisiones:
        informe_decision = decision.devolucion.informe if decision.devolucion else None
        fila_usuario(informe_decision.usuario_id if informe_decision else None)["decisiones"] += 1

    mensajes_por_proyecto: dict[int, Counter[str]] = {}
    ultimo_mensaje_por_proyecto: dict[int, dt.datetime] = {}
    for mensaje in mensajes_proyecto_ia:
        mensajes_por_proyecto.setdefault(mensaje.proyecto_id, Counter())[mensaje.remitente] += 1
        if (
            mensaje.creado_en is not None
            and mensaje.creado_en > ultimo_mensaje_por_proyecto.get(mensaje.proyecto_id, dt.datetime.min)
        ):
            ultimo_mensaje_por_proyecto[mensaje.proyecto_id] = mensaje.creado_en

    def proyecto_tiene_contexto(proyecto: models.ProyectoIA) -> bool:
        return any([proyecto.titulo, proyecto.organismo_area, proyecto.situacion])

    def etapa_proyecto(proyecto: models.ProyectoIA, conteos: Counter[str]) -> str:
        if proyecto.estado == 'revisado':
            return 'Revisado'
        if proyecto.estado == 'entregado' or bool(proyecto.entrega_final):
            return 'Entregado'
        if conteos.get('docente', 0):
            return 'Intervención docente'
        if conteos.get('consulta_docente', 0):
            return 'Consulta docente'
        if conteos.get('participante', 0):
            return 'Conversación con IA'
        if proyecto_tiene_contexto(proyecto):
            return 'Contexto definido'
        return 'Sin iniciar'

    progreso_proyectos_ia = []
    for proyecto in proyectos_ia:
        conteos = mensajes_por_proyecto.get(proyecto.id, Counter())
        ultimo_movimiento = max(
            proyecto.actualizado_en or dt.datetime.min,
            ultimo_mensaje_por_proyecto.get(proyecto.id, dt.datetime.min),
        )
        fila = fila_usuario(proyecto.usuario_id)
        fila["proyecto_ia"] = True
        fila["proyecto_estado"] = proyecto.estado
        fila["proyecto_etapa"] = etapa_proyecto(proyecto, conteos)
        fila["proyecto_contexto"] = proyecto_tiene_contexto(proyecto)
        conteos_norm = _conteos_interacciones(list(proyecto.mensajes or []))
        diagnostico = _diagnostico_proyecto(proyecto)
        fila["proyecto_mensajes_participante"] = conteos_norm["mensajes_participante"]
        fila["proyecto_consultas_docente"] = conteos_norm["interacciones_docente"]
        fila["proyecto_entrega"] = bool(proyecto.entrega_final)
        fila["ultimo_proyecto_ia"] = ultimo_movimiento if ultimo_movimiento != dt.datetime.min else None

        usuario = usuarios_por_id.get(proyecto.usuario_id)
        if usuario and usuario.rol != 'admin':
            progreso_proyectos_ia.append(
                {
                    'proyecto_id': proyecto.id,
                    'usuario_id': usuario.id,
                    'email': usuario.email,
                    'nombre': usuario.nombre,
                    'rol': usuario.rol,
                    'estado': proyecto.estado,
                    'etapa': fila["proyecto_etapa"],
                    'contexto': fila["proyecto_contexto"],
                    'mensajes_participante': fila["proyecto_mensajes_participante"],
                    'mensajes_chat_ia': conteos_norm["mensajes_chat_ia"],
                    'mensajes_ia': conteos_norm["mensajes_ia"],
                    'consultas_docente': conteos_norm["consultas_docente"],
                    'respuestas_docente': conteos_norm["respuestas_docente"],
                    'interacciones_docente': fila["proyecto_consultas_docente"],
                    'entrega': fila["proyecto_entrega"],
                    'revisado': proyecto.estado == 'revisado',
                    'diagnostico': diagnostico,
                    'ultimo_movimiento': _iso(fila["ultimo_proyecto_ia"]),
                }
            )

    progreso_proyectos_ia.sort(key=lambda item: item['ultimo_movimiento'] or '', reverse=True)

    usuarios_actividad = sorted(
        por_usuario.values(),
        key=lambda item: (
            item["informes"],
            int(item["proyecto_ia"]),
            item["hallazgos"],
            item["ultimo_informe"] or item["ultimo_proyecto_ia"] or dt.datetime.min,
        ),
        reverse=True,
    )
    for item in usuarios_actividad:
        item["ultimo_informe"] = _iso(item["ultimo_informe"])
        item["ultimo_proyecto_ia"] = _iso(item["ultimo_proyecto_ia"])

    ultimos_informes = sorted(informes, key=lambda x: x.creado_en, reverse=True)[:12]
    ultimos_jobs = sorted(jobs, key=lambda x: x.creado_en, reverse=True)[:12]
    ultima_carga = ultimos_informes[0].creado_en if ultimos_informes else None
    ultimas_decisiones = sorted(decisiones, key=lambda x: x.decidido_en, reverse=True)
    ultima_decision = ultimas_decisiones[0].decidido_en if ultimas_decisiones else None
    usuarios_con_informes = {informe.usuario_id for informe in informes if informe.usuario_id is not None}
    usuarios_con_proyecto_ia = {proyecto.usuario_id for proyecto in proyectos_ia if proyecto.usuario_id is not None}
    usuarios_con_informes_24h = {
        informe.usuario_id
        for informe in informes
        if informe.usuario_id is not None and informe.creado_en is not None and informe.creado_en >= desde_24h
    }

    return {
        "generado_en": _iso(ahora),
        "resumen_operativo": {
            "ultima_carga": _iso(ultima_carga),
            "ultima_decision": _iso(ultima_decision),
            "usuarios_con_informes": len(usuarios_con_informes),
            "usuarios_con_proyecto_ia": len(usuarios_con_proyecto_ia),
            "usuarios_con_informes_24h": len(usuarios_con_informes_24h),
            "jobs_pendientes": jobs_por_estado.get("pendiente", 0),
            "jobs_procesando": jobs_por_estado.get("procesando", 0),
            "jobs_error": jobs_por_estado.get("error", 0),
        },
        "metricas": {
            "usuarios_total": len(usuarios),
            "usuarios_activos": sum(1 for u in usuarios if u.activo),
            "admins": sum(1 for u in usuarios if u.rol == "admin"),
            "analistas": sum(1 for u in usuarios if u.rol == "analista"),
            "lectores": sum(1 for u in usuarios if u.rol == "lector"),
            "informes_total": len(informes),
            "informes_24h": sum(1 for i in informes if i.creado_en is not None and i.creado_en >= desde_24h),
            "jobs_total": len(jobs),
            "jobs_finalizados": jobs_por_estado.get("finalizado", 0),
            "jobs_error": jobs_por_estado.get("error", 0),
            "hallazgos_total": len(hallazgos),
            "decisiones_total": len(decisiones),
            "aprendizajes_total": len(aprendizajes),
            "proyectos_ia_total": len(proyectos_ia),
            "usuarios_con_proyecto_ia": len(usuarios_con_proyecto_ia),
            "proyectos_ia_entregados": sum(1 for p in proyectos_ia if p.estado == 'entregado' or bool(p.entrega_final)),
            "proyectos_ia_revisados": sum(1 for p in proyectos_ia if p.estado == 'revisado'),
            "mensajes_proyecto_ia_total": len(mensajes_proyecto_ia),
            "mensajes_participante_proyecto_ia": sum(
                1 for m in mensajes_proyecto_ia if m.remitente in {'participante', 'consulta_docente'}
            ),
            "mensajes_chat_ia_proyecto_ia": sum(1 for m in mensajes_proyecto_ia if m.remitente == 'participante'),
            "respuestas_ia_proyecto_ia": sum(1 for m in mensajes_proyecto_ia if m.remitente == 'ia'),
            "consultas_docente_total": sum(
                1 for m in mensajes_proyecto_ia if m.remitente in {'consulta_docente', 'docente'}
            ),
            "proyectos_necesitan_segunda_vuelta": sum(
                1 for p in proyectos_ia
                if usuarios_por_id.get(p.usuario_id) and usuarios_por_id[p.usuario_id].rol != 'admin'
                and _diagnostico_proyecto(p)["necesita_segunda_vuelta"]
            ),
            "eventos_actividad_total": len(eventos_actividad),
            "eventos_actividad_24h": len(eventos_24h),
            "evaluaciones_piloto_total": len(evaluaciones_piloto),
            "evaluaciones_piloto_utiles": evaluaciones_piloto_por_resultado.get("util", 0),
            "evaluaciones_piloto_parciales": evaluaciones_piloto_por_resultado.get("parcial", 0),
            "evaluaciones_piloto_falsos_positivos": evaluaciones_piloto_por_resultado.get("falso_positivo", 0),
            "evaluaciones_piloto_omisiones": evaluaciones_piloto_por_resultado.get("omision", 0),
        },
        "evaluaciones_piloto": {
            "total": len(evaluaciones_piloto),
            "por_resultado": dict(evaluaciones_piloto_por_resultado),
        },
        "eventos_actividad": {
            "total": len(eventos_actividad),
            "ultimas_24h": len(eventos_24h),
            "por_modulo": dict(eventos_por_modulo),
            "por_accion": dict(eventos_por_accion.most_common(20)),
            "recientes": [
                {
                    "id": evento.id,
                    "usuario_id": evento.usuario_id,
                    "modulo": evento.modulo,
                    "accion": evento.accion,
                    "resumen": evento.resumen,
                    "informe_id": evento.informe_id,
                    "proyecto_id": evento.proyecto_id,
                    "metadata": evento.metadata_evento or {},
                    "creado_en": _iso(evento.creado_en),
                }
                for evento in sorted(eventos_actividad, key=lambda e: e.creado_en or dt.datetime.min, reverse=True)[:40]
            ],
        },
        "jobs_por_estado": dict(jobs_por_estado),
        "modelos_usados": dict(modelos_usados),
        "usuarios": usuarios_actividad[:30],
        "progreso_proyectos_ia": progreso_proyectos_ia,
        "ultimos_informes": [
            {
                "id": informe.id,
                "periodo": informe.periodo,
                "dominio": informe.dominio,
                "creado_por": informe.creado_por,
                "usuario_id": informe.usuario_id,
                "creado_en": _iso(informe.creado_en),
                "hallazgos": len(informe.hallazgos or []),
                "decision": bool(informe.devolucion and informe.devolucion.decision),
            }
            for informe in ultimos_informes
        ],
        "ultimos_jobs": [
            {
                "id": job.id,
                "informe_id": job.informe_id,
                "usuario_id": job.usuario_id,
                "estado": job.estado,
                "modelos": job.modelos or [],
                "creado_en": _iso(job.creado_en),
                "finalizado_en": _iso(job.finalizado_en),
                "error": bool(job.error),
            }
            for job in ultimos_jobs
        ],
    }


@router.get("/health")
def health(response: Response):
    """Estado para monitoreo, sin datos: si la base responde y si la cola de análisis está trabada.

    503 si la base no responde; «degradado» con la cola como la que destraba scripts/vigilar_cola.py.
    """
    from scripts.vigilar_cola import decidir  # los mismos umbrales que la vigilancia que reinicia el servicio

    try:
        trabajos = _trabajos_en_cola()
    except Exception as exc:  # noqa: BLE001 — el chequeo tiene que responder aunque la base no lo haga.
        logger.warning("health: la base no responde (%s)", exc.__class__.__name__)
        response.status_code = 503
        return {"status": "error", "base": "sin respuesta"}
    trabada = decidir(trabajos, dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))[0] == "reiniciar"
    return {"status": "degradado" if trabada else "ok", "base": "ok", "cola": "trabada" if trabada else "ok"}


def _trabajos_en_cola() -> list[tuple]:
    """(id, estado, creado_en, iniciado_en) de los trabajos pendientes o en análisis."""
    with SessionLocal() as db:
        j = models.AnalysisJob
        return [tuple(fila) for fila in db.query(j.id, j.estado, j.creado_en, j.iniciado_en)
                .filter(j.estado.in_(("pendiente", "procesando")))]
