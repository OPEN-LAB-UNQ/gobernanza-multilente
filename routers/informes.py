from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session, defer, selectinload

import models
import schemas
from core.auth import get_current_user
from database import SessionLocal, get_db
from services import actividad as actividad_svc
from services import casos_revision, cuota_ia, proveniencia
from services import jobs as jobs_svc
from services import sanitizacion as sanitizacion_svc
from services.analisis import ejecutar_analisis, ejecutar_analisis_stream, modelos_consultados_publicos
from services.reportes.markdown import (
    render_comprobante_controles_markdown,
    render_reporte_html,
    render_reporte_markdown,
    render_reporte_pdf,
    slug,
)

router = APIRouter(prefix="/informes", tags=["informes"])
logger = logging.getLogger(__name__)

MODELOS_TRIANGULACION_VALIDOS = {"claude", "gpt", "gemini", "renderix", "deepseek", "llama"}




def _puede_ver(user: models.Usuario, informe: models.Informe) -> bool:
    return user.rol == "admin" or (informe.usuario_id is not None and informe.usuario_id == user.id)


def _puede_operar_informes(user: models.Usuario) -> bool:
    return user.rol in {"admin", "analista"}


def _rechazar_lector(user: models.Usuario, accion: str) -> None:
    if not _puede_operar_informes(user):
        raise HTTPException(403, f"el rol lector no puede {accion}")


def _puede_borrar_informe(user: models.Usuario, informe: models.Informe) -> bool:
    return user.rol == "admin" or (user.rol == "analista" and informe.usuario_id == user.id)


RESPUESTAS_SENAL = {
    "error_real": "Era un error real",
    "dato_correcto": "El dato estaba bien",
    "no_se": "No sé todavía",
}
MAX_COMENTARIO_RESPUESTA = 500


def _puede_responder(user: models.Usuario, informe: models.Informe) -> bool:
    # Sólo quien hizo el informe sabe qué resultó ser cada señal: nadie responde por otra persona. El rol lector
    # no escribe, como en la evaluación del piloto.
    return _puede_operar_informes(user) and informe.usuario_id is not None and informe.usuario_id == user.id


def _respuesta_publica(r: models.RespuestaSenal) -> dict:
    return {"respuesta": r.respuesta, "texto": RESPUESTAS_SENAL.get(r.respuesta, r.respuesta),
            "comentario": r.comentario, "creado_en": r.creado_en.isoformat() if r.creado_en else None}


def _hallazgos_con_respuesta(db: Session, informe: models.Informe, user: models.Usuario) -> list:
    ultimas = {}
    for r in (db.query(models.RespuestaSenal).filter_by(informe_id=informe.id)
              .order_by(models.RespuestaSenal.creado_en, models.RespuestaSenal.id)):
        ultimas[r.hallazgo_id] = r
    puede = _puede_responder(user, informe)
    out = []
    for h in informe.hallazgos:
        x = schemas.HallazgoOut.model_validate(h)
        x.respuesta = _respuesta_publica(ultimas[h.id]) if h.id in ultimas else None
        x.puede_responder = puede
        out.append(x)
    return out


def _version_motor(db: Session, informe: models.Informe) -> Optional[str]:
    """Versión del motor que produjo las señales vigentes: la del manifiesto o, si no hay, la del último trabajo."""
    m = ((informe.devolucion.cobertura or {}).get("manifiesto") or {}) if informe.devolucion else {}
    valor = m.get("version_motor")
    if not valor:
        job = jobs_svc.latest_job(db, informe.id)
        valor = job.version_analisis if job else None
    return str(valor)[:64] if valor else None


def _prioridad_caso(informe: models.Informe, hallazgo: models.Hallazgo) -> Optional[str]:
    """Prioridad del caso que integra la señal, como la ve la pantalla al responder; si la señal no integra un caso
    (contexto, nota), la de la señal. Se guarda con la respuesta: el código que la calcula puede cambiar."""
    try:
        for c in casos_revision.agrupar(informe.hallazgos)["casos"]:
            if any(casos_revision.campo(x, "id") == hallazgo.id for x in [c["primary_finding"], *c["related_findings"]]):
                return str(c["prioridad"])[:10]
        return str(casos_revision.prioridad(hallazgo))[:10]
    except Exception:  # noqa: BLE001 — la prioridad no puede impedir registrar la respuesta
        logger.exception("no se pudo calcular la prioridad de la señal %s", hallazgo.id)
        return None


# Pregunta de cierre por informe: si se corrigió algo antes de entregarlo y cuántos errores no señaló la herramienta.
# Va en activity_events (sin columnas nuevas): una fila por respuesta, vale la última.
CIERRE_CORRIGIO = {"si": "Sí", "no": "No", "todavia_no": "Todavía no"}
ACCION_CIERRE = "cierre_informe_registrado"
MAX_ERRORES_NO_SENALADOS = 1000


def _es_prueba(informe: models.Informe) -> bool:
    return bool((informe.saneamiento or {}).get("es_prueba"))


def _cierre_publico(evento: models.ActivityEvent) -> dict:
    m = evento.metadata_evento or {}
    return {"corrigio": m.get("corrigio"), "texto": CIERRE_CORRIGIO.get(m.get("corrigio"), m.get("corrigio")),
            "errores_no_senalados": m.get("errores_no_senalados"),
            "registrado_en": evento.creado_en.isoformat() if evento.creado_en else None}


def _cierre_informe(db: Session, informe: models.Informe, user: models.Usuario) -> dict:
    evento = (db.query(models.ActivityEvent)
              .filter(models.ActivityEvent.informe_id == informe.id, models.ActivityEvent.accion == ACCION_CIERRE)
              .order_by(models.ActivityEvent.creado_en.desc(), models.ActivityEvent.id.desc()).first())
    puede = _puede_responder(user, informe) and informe.devolucion is not None
    return {"puede_responder": puede, "es_prueba": _es_prueba(informe),
            "pendiente": puede and evento is None and not _es_prueba(informe),
            "respuesta": _cierre_publico(evento) if evento else None}


def _ultimo_job(informe: models.Informe):
    jobs = list(informe.trabajos_analisis or [])
    return jobs[0] if jobs else None

def _validar_modelos(modelos) -> list[str] | None:
    if not modelos:
        return None
    if not isinstance(modelos, list) or not all(isinstance(m, str) for m in modelos):
        raise HTTPException(422, "modelos debe ser una lista de strings")
    desconocidos = [m for m in modelos if m not in MODELOS_TRIANGULACION_VALIDOS]
    if desconocidos:
        raise HTTPException(
            422,
            f"modelos desconocidos: {', '.join(desconocidos)}; validos: {', '.join(sorted(MODELOS_TRIANGULACION_VALIDOS))}",
        )
    return modelos



@router.post("", response_model=schemas.InformeOut)
def crear_informe(payload: schemas.InformeCreate, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    _rechazar_lector(user, "crear informes")
    if not db.get(models.Area, payload.area_id):
        raise HTTPException(404, "área no encontrada")
    if not payload.datos:
        raise HTTPException(422, "el informe no puede tener datos vacíos")

    datos_saneados, reporte = sanitizacion_svc.sanear(payload.datos)
    anterior = db.get(models.Informe, payload.informe_anterior_id) if payload.informe_anterior_id else None
    if payload.informe_anterior_id and (not anterior or not _puede_ver(user, anterior)):
        raise HTTPException(404, "informe anterior no disponible")
    reporte["contexto_validacion"] = payload.contexto_validacion.model_dump()
    if anterior and not payload.contexto_validacion.esquema_esperado:
        from services.validez import esquema
        reporte["contexto_validacion"]["esquema_esperado"] = esquema(anterior.datos or [])
    reporte["proveniencia"] = proveniencia.registrar(
        [("carga-estructurada.json", json.dumps(payload.datos, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())],
        datos_saneados, reporte, user.id, {"carga-estructurada.json": "application/json"}, anterior,
    )
    reporte["proveniencia"]["representacion_origen"] = "JSON canónico del payload; no representa un archivo bruto recibido"
    if not datos_saneados or not datos_saneados[0]:
        raise HTTPException(
            422,
            "Todas las columnas cargadas identifican actores o documentos individuales "
            f"({', '.join(reporte['columnas_excluidas'])}). El sistema solo procesa información "
            "agregada: no hay ninguna columna de alcance agregado para analizar.",
        )

    reporte.setdefault("opciones_tecnicas", {})["ambito"] = payload.ambito
    reporte["ambito"] = payload.ambito
    reporte["origen_interpretacion"] = "datos_estructurados"
    informe = models.Informe(
        area_id=payload.area_id,
        periodo=payload.periodo,
        dominio=payload.dominio,
        modo=payload.modo,
        creado_por=user.email,  # la autoría sale de la sesión, nunca del pedido
        usuario_id=user.id,
        datos=datos_saneados,
        saneamiento=reporte,
    )
    db.add(informe)
    db.commit()
    db.refresh(informe)
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="informe_creado",
        resumen="Informe creado desde carga estructurada",
        informe_id=informe.id,
        metadata={"filas": len(datos_saneados), "dominio": informe.dominio, "periodo": informe.periodo},
    )
    db.commit()
    return informe


@router.post("/{informe_id}/interpretacion")
def interpretar_carga_estructurada(informe_id: int, payload: dict = Body(default_factory=dict),
                                  db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Misma barrera para la API de datos estructurados; archivos requieren reenviar originales."""
    from copy import deepcopy

    from services import interpretacion_previa as ip
    informe = db.get(models.Informe, informe_id)
    if not informe or informe.usuario_id != user.id:
        raise HTTPException(404, "informe no disponible")
    _rechazar_lector(user, "confirmar interpretaciones")
    meta = deepcopy(informe.saneamiento or {})
    base_meta = deepcopy(meta)
    if meta.get("origen_interpretacion") != "datos_estructurados":
        raise HTTPException(409, "Esta carga requiere reenviar los archivos originales en la pantalla de carga.")
    if informe.devolucion:
        raise HTTPException(409, "Esta corrida ya terminó; creá una carga nueva para otra interpretación.")
    accion = payload.get("accion", "preparar")
    if accion not in {"preparar", "detallada", "confirmar"}:
        raise HTTPException(422, "Acción de interpretación desconocida")
    previa = meta.get(ip.CAMPO)
    if previa and previa.get("estado") == "confirmada":
        raise HTTPException(409, "La interpretación ya se confirmó.")
    if previa and previa.get("estado") == "interpretando":
        raise HTTPException(409, "La lectura previa sigue en curso. Esperá su propuesta antes de modificarla.")
    if accion != "preparar" and (not previa or payload.get("revision") != previa.get("revision")):
        raise HTTPException(409, "Falta una interpretación vigente para confirmar o releer.")
    originales = [("datos-estructurados.json", json.dumps(informe.datos, ensure_ascii=False, sort_keys=True, default=str).encode())]
    opciones = {"periodo": informe.periodo, "contexto_validacion": meta.get("contexto_validacion"),
                "opciones_tecnicas": meta.get("opciones_tecnicas")}
    if accion == "confirmar":
        nueva = ip.confirmar(previa, usuario_id=user.id, revision=payload.get("revision"), leidos=originales,
                             datos=informe.datos, opciones=opciones, correcciones=payload.get("correcciones"))
    else:
        cuota_ia.verificar_analisis(db, user)
        cuota_ia.reservar_interpretacion(db, user, detallada=accion == "detallada", informe_id=informe.id)
        nueva = ip.lectura_pendiente(informe.datos, originales, opciones, user.id, anterior=previa)
    meta[ip.CAMPO] = nueva
    campos = {models.Informe.saneamiento: meta}
    if accion == "confirmar":
        dominios = {ip.dominio(u) for u in nueva["cuadros"]}
        campos[models.Informe.dominio] = next(iter(dominios)) if len(dominios) == 1 else "general"
    n = db.query(models.Informe).filter(models.Informe.id == informe.id, models.Informe.saneamiento == base_meta).update(
        campos, synchronize_session=False)
    if n != 1:
        db.rollback()
        raise HTTPException(409, "La interpretación cambió en otra solicitud.")
    if accion != "confirmar":
        db.refresh(informe)
        job = jobs_svc.enqueue_interpretacion(db, informe, user, opciones, detallada=accion == "detallada")
        return {"informe_id": informe.id, "estado": nueva["estado"], "interpretacion": ip.publico(nueva),
                "job": schemas.AnalysisJobOut.model_validate(job)}
    db.commit()
    return {"informe_id": informe.id, "estado": nueva["estado"], "interpretacion": ip.publico(nueva)}


ORDEN_SEVERIDAD = {"alta": 3, "media": 2, "baja": 1}


@router.get("", response_model=list[schemas.InformeResumenOut])
def listar_informes(area_id: Optional[int] = None, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    # La lista solo muestra una fila por informe: no traer datos, saneamiento, evidencia ni el
    # resultado de cada análisis (decenas de MB con libros grandes; la lista tardaba 3 s).
    q = db.query(models.Informe).options(
        defer(models.Informe.datos), defer(models.Informe.saneamiento),
        selectinload(models.Informe.hallazgos).load_only(models.Hallazgo.id, models.Hallazgo.informe_id, models.Hallazgo.severidad),
        selectinload(models.Informe.devolucion).load_only(models.Devolucion.id, models.Devolucion.informe_id, models.Devolucion.estado)
        .selectinload(models.Devolucion.decision),
        selectinload(models.Informe.trabajos_analisis).load_only(
            models.AnalysisJob.id, models.AnalysisJob.informe_id, models.AnalysisJob.estado, models.AnalysisJob.creado_en),
    )
    if area_id is not None:
        q = q.filter(models.Informe.area_id == area_id)
    if user.rol != "admin":
        q = q.filter(models.Informe.usuario_id == user.id)
    informes = q.order_by(models.Informe.creado_en.desc()).all()
    # Proyectar sólo el nombre y el conteo público, sin cargar los JSON completos.
    resumenes = {i: (archivos or [], casos, lectura) for i, archivos, casos, lectura in db.query(
        models.Informe.id, models.Informe.saneamiento["archivos_origen"],
        models.Devolucion.cobertura["revision"]["casos_revision"],
        models.Informe.saneamiento["interpretacion_previa"]["estado"],
    ).outerjoin(models.Devolucion, models.Devolucion.informe_id == models.Informe.id).filter(
        models.Informe.id.in_([informe.id for informe in informes]))} if informes else {}
    # Qué revisión fue cada uno, sin leer el saneamiento: lo registra el evento de la carga.
    rapidas = {i for (i,) in db.query(models.ActivityEvent.informe_id).filter(
        models.ActivityEvent.accion == "analisis_rapido_encolado",
        models.ActivityEvent.informe_id.in_([informe.id for informe in informes]),
        models.ActivityEvent.metadata_evento["modo_revision"].as_string() == "rapida")} if informes else set()
    # «Es una prueba» y pregunta de cierre, también sin leer el saneamiento: salen de los eventos de cada informe.
    pruebas, cerrados = set(), set()
    if informes:
        for informe_id, accion, meta in db.query(
                models.ActivityEvent.informe_id, models.ActivityEvent.accion, models.ActivityEvent.metadata_evento).filter(
                models.ActivityEvent.accion.in_(["analisis_rapido_encolado", ACCION_CIERRE]),
                models.ActivityEvent.informe_id.in_([informe.id for informe in informes])):
            if accion == ACCION_CIERRE:
                cerrados.add(informe_id)
            elif (meta or {}).get("es_prueba") is True:
                pruebas.add(informe_id)
    responde = _puede_operar_informes(user)

    resultado = []
    for informe in informes:
        severidad_max = None
        for h in informe.hallazgos:
            if severidad_max is None or ORDEN_SEVERIDAD.get(h.severidad, 0) > ORDEN_SEVERIDAD.get(severidad_max, 0):
                severidad_max = h.severidad
        decision = informe.devolucion.decision if informe.devolucion else None
        job = _ultimo_job(informe)
        resultado.append(schemas.InformeResumenOut(
            id=informe.id,
            area_id=informe.area_id,
            periodo=informe.periodo,
            dominio=informe.dominio,
            modo=informe.modo,
            creado_en=informe.creado_en,
            usuario_id=informe.usuario_id,
            creado_por=informe.creado_por,
            n_hallazgos=len(informe.hallazgos),
            n_casos=resumenes.get(informe.id, ([], None))[1],
            archivos_origen=resumenes.get(informe.id, ([], None))[0],
            interpretacion_estado=resumenes.get(informe.id, ([], None, None))[2],
            severidad_max=severidad_max,
            estado_devolucion=informe.devolucion.estado if informe.devolucion else None,
            decision_tomada=decision is not None,
            tipo_decision=decision.tipo_decision if decision else None,
            analysis_job_id=job.id if job else None,
            analysis_status=job.estado if job else ("finalizado" if informe.devolucion else None),
            modo_revision="rapida" if informe.id in rapidas else "profunda",
            es_prueba=informe.id in pruebas,
            cierre_pendiente=bool(responde and informe.usuario_id == user.id and informe.devolucion is not None
                                  and informe.id not in cerrados and informe.id not in pruebas),
        ))
    return resultado


@router.delete("/{informe_id}")
def borrar_informe(informe_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_borrar_informe(user, informe):
        raise HTTPException(403, "sin permiso para borrar este informe")
    # Borrar un informe en pleno análisis detuvo la cola el 08/10 (informe 310): se espera a que
    # termine. Los que todavía esperan turno sí se pueden borrar.
    if any(job.estado == "procesando" for job in (informe.trabajos_analisis or [])):
        raise HTTPException(409, "Este informe se está analizando ahora. Esperá a que termine (unos minutos) y después podés borrarlo.")
    # Un sello emitido se verifica públicamente contra este informe: borrarlo lo dejaría
    # sin respaldo («nada se borra»). Rige también para la administración.
    con_sello = (
        db.query(models.EvaluacionCertificacion)
        .filter(models.EvaluacionCertificacion.informe_id == informe.id)
        .filter(models.EvaluacionCertificacion.sello.has())
        .first()
    )
    if con_sello:
        raise HTTPException(409, "este informe tiene un sello emitido y no se puede borrar: el sello dejaría de verificarse")

    for ejecucion in db.query(models.EjecucionAnalisis).filter(models.EjecucionAnalisis.informe_id == informe.id):
        db.delete(ejecucion)
    for hipotesis in db.query(models.HipotesisExploratoria).filter(models.HipotesisExploratoria.informe_id == informe.id):
        db.delete(hipotesis)

    for job in list(informe.trabajos_analisis or []):
        db.delete(job)
    for evento in list(informe.learning_events or []):
        evento.informe_id = None
        db.add(evento)
    for evento_actividad in db.query(models.ActivityEvent).filter(models.ActivityEvent.informe_id == informe.id):
        evento_actividad.informe_id = None
        db.add(evento_actividad)
    for evaluacion in db.query(models.EvaluacionCertificacion).filter(
        models.EvaluacionCertificacion.informe_id == informe.id
    ):
        if evaluacion.sello:
            db.delete(evaluacion.sello)
        db.delete(evaluacion)
    for respuesta in db.query(models.RespuestaSenal).filter(models.RespuestaSenal.informe_id == informe.id):
        db.delete(respuesta)
    for hallazgo in list(informe.hallazgos or []):
        db.delete(hallazgo)
    for interpretacion in list(informe.interpretaciones or []):
        db.delete(interpretacion)
    if informe.triangulacion:
        db.delete(informe.triangulacion)
    if informe.devolucion:
        decision = informe.devolucion.decision
        if decision:
            for documento in list(decision.documentos or []):
                db.delete(documento)
            db.delete(decision)
        db.delete(informe.devolucion)
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="informe_borrado",
        resumen="Informe borrado por usuario autorizado",
        informe_id=None,
        metadata={
            "informe_id_borrado": getattr(informe, "id", informe_id),
            "periodo": getattr(informe, "periodo", None),
            "dominio": getattr(informe, "dominio", None),
        },
    )
    db.delete(informe)
    db.commit()
    return {"ok": True}


@router.get("/{informe_id}", response_model=schemas.InformeOut)
def obtener_informe(informe_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para ver este informe")
    from services import lector_mapa
    salida = schemas.InformeOut.model_validate(informe)
    salida.saneamiento = lector_mapa.saneamiento_publico(informe.saneamiento, _puede_responder(user, informe))
    return salida


@router.get("/{informe_id}/detalle", response_model=schemas.InformeDetalleOut)
def obtener_detalle(informe_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para ver este informe")
    tri = informe.triangulacion
    job = jobs_svc.latest_job(db, informe.id)
    evaluacion_evento = (
        db.query(models.ActivityEvent)
        .filter(
            models.ActivityEvent.informe_id == informe.id,
            models.ActivityEvent.modulo == "multilente",
            models.ActivityEvent.accion == "evaluacion_piloto_registrada",
        )
        .order_by(models.ActivityEvent.creado_en.desc(), models.ActivityEvent.id.desc())
        .first()
    )
    from services import lector_mapa
    from services.semantica_excel import presentar_cobertura
    devolucion = schemas.DevolucionOut.model_validate(informe.devolucion) if informe.devolucion else None
    if devolucion:
        devolucion.cobertura = presentar_cobertura(devolucion.cobertura)
    return schemas.InformeDetalleOut(
        revision=casos_revision.agrupar(informe.hallazgos),
        id=informe.id,
        area_id=informe.area_id,
        periodo=informe.periodo,
        dominio=informe.dominio,
        modo=informe.modo,
        creado_en=informe.creado_en,
        n_filas=len(informe.datos or []),
        saneamiento=lector_mapa.saneamiento_publico(informe.saneamiento, _puede_responder(user, informe)),
        hallazgos=_hallazgos_con_respuesta(db, informe, user),
        coincidencias=tri.coincidencias if tri else [],
        divergencias=tri.divergencias if tri else [],
        hallazgos_singulares=tri.hallazgos_singulares if tri else [],
        modelos_consultados=modelos_consultados_publicos(list(informe.interpretaciones or []),
            manifiesto=(informe.devolucion.cobertura or {}).get("manifiesto") if informe.devolucion else None),
        convergencia_multilente=tri.convergencia_multilente if tri else [],
        devolucion=devolucion,
        decision=schemas.DecisionOut.model_validate(informe.devolucion.decision)
        if informe.devolucion and informe.devolucion.decision else None,
        job=schemas.AnalysisJobOut.model_validate(job) if job else None,
        evaluacion_piloto={
            **dict(evaluacion_evento.metadata_evento or {}),
            "registrado_en": evaluacion_evento.creado_en.isoformat(),
        } if evaluacion_evento else None,
        cierre_informe=_cierre_informe(db, informe, user),
    )


@router.post("/{informe_id}/evaluacion-piloto")
def registrar_evaluacion_piloto(
    informe_id: int,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para evaluar este informe")
    _rechazar_lector(user, "registrar evaluaciones del piloto")
    resultado = str(payload.get("resultado") or "").strip().lower()
    validos = {"util", "parcial", "falso_positivo", "omision"}
    if resultado not in validos:
        raise HTTPException(422, "resultado de evaluación inválido")
    comentario = str(payload.get("comentario") or "").strip()
    if len(comentario) > 1500:
        raise HTTPException(422, "el comentario supera 1500 caracteres")
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="evaluacion_piloto_registrada",
        resumen="Evaluación humana del resultado del piloto",
        informe_id=informe.id,
        metadata={
            "resultado": resultado,
            "comentario": comentario,
            "version_analisis": jobs_svc.latest_job(db, informe.id).version_analisis
            if jobs_svc.latest_job(db, informe.id) else None,
        },
    )
    db.commit()
    return {"ok": True, "resultado": resultado}


@router.get("/{informe_id}/manifiesto")
def obtener_manifiesto(informe_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe or not _puede_ver(user, informe):
        raise HTTPException(404, "informe no disponible")
    cobertura = (informe.devolucion.cobertura or {}) if informe.devolucion else {}
    manifiesto = cobertura.get("manifiesto") or {}
    ejecucion = db.get(models.EjecucionAnalisis, manifiesto["ejecucion_id"]) if manifiesto.get("ejecucion_id") else None
    return {"informe_id": informe.id, "manifiesto": cobertura.get("manifiesto"),
            "estado": "registrado" if cobertura.get("manifiesto") else "sin_manifiesto_historico",
            "proveniencia": (informe.saneamiento or {}).get("proveniencia"),
            "requiere_reevaluacion": bool(ejecucion and ejecucion.requiere_reevaluacion),
            "incidencias": ejecucion.incidencias if ejecucion else []}


@router.post("/{informe_id}/reporte")
def descargar_reporte_seleccionado(
    informe_id: int,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para ver este informe")
    if not informe.devolucion:
        raise HTTPException(409, "el informe todavía no fue analizado")

    seleccion = payload.get("hallazgo_ids")
    if seleccion is None:
        hallazgos = list(informe.hallazgos)
    else:
        try:
            seleccion_ids = {int(x) for x in seleccion}
        except (TypeError, ValueError):
            raise HTTPException(422, "hallazgo_ids debe ser una lista de IDs")
        ids_validos = {h.id for h in informe.hallazgos}
        desconocidos = seleccion_ids - ids_validos
        if desconocidos:
            raise HTTPException(422, f"hallazgos no pertenecen al informe: {sorted(desconocidos)}")
        hallazgos = [h for h in informe.hallazgos if h.id in seleccion_ids]

    prioridad = {"alta": 0, "media": 1, "baja": 2}
    hallazgos = sorted(hallazgos, key=lambda h: (prioridad.get(h.severidad, 9), h.lente, h.id))
    pieza = str(payload.get("pieza") or "completo").lower()
    if pieza not in {"ejecutivo", "anexo", "completo"}:
        raise HTTPException(422, "pieza debe ser ejecutivo, anexo o completo")
    contenido = render_reporte_markdown(
        informe,
        hallazgos,
        bool(payload.get("incluir_triangulacion", True)),
        bool(payload.get("incluir_devolucion", True)),
        bool(payload.get("incluir_detalle_modelos", False)),
        pieza=pieza,
    )
    formato = str(payload.get("formato") or "markdown").lower()
    if formato == "pdf":
        actividad_svc.registrar(
            db,
            usuario=user,
            modulo="multilente",
            accion="reporte_descargado",
            resumen="Reporte descargado en PDF",
            informe_id=informe.id,
            metadata={"formato": "pdf", "hallazgos_incluidos": len(hallazgos)},
        )
        db.commit()
        filename = f"reporte-{pieza}-{informe.id}-{slug(informe.periodo)}.pdf"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=render_reporte_pdf(contenido), media_type="application/pdf", headers=headers)
    if formato == "html":
        actividad_svc.registrar(
            db,
            usuario=user,
            modulo="multilente",
            accion="reporte_descargado",
            resumen="Reporte descargado en HTML",
            informe_id=informe.id,
            metadata={"formato": "html", "hallazgos_incluidos": len(hallazgos)},
        )
        db.commit()
        filename = f"reporte-{pieza}-{informe.id}-{slug(informe.periodo)}.html"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=render_reporte_html(contenido), media_type="text/html; charset=utf-8", headers=headers)

    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="reporte_descargado",
        resumen="Reporte descargado en Markdown",
        informe_id=informe.id,
        metadata={"formato": "markdown", "hallazgos_incluidos": len(hallazgos)},
    )
    db.commit()
    filename = f"reporte-{pieza}-{informe.id}-{slug(informe.periodo)}.md"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    # BOM UTF-8 para visores de Windows/Word que no respetan siempre el charset
    # de la respuesta al abrir el archivo descargado fuera del navegador.
    return Response(content="\ufeff" + contenido, media_type="text/markdown; charset=utf-8", headers=headers)


@router.get("/{informe_id}/informe-revision.pdf")
def descargar_informe_revision(informe_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    respuesta = descargar_reporte_seleccionado(informe_id, {"formato": "pdf", "pieza": "ejecutivo"}, db, user)
    respuesta.headers["Content-Disposition"] = f'attachment; filename="informe-revision-{informe_id}.pdf"'
    return respuesta


@router.get("/{informe_id}/comprobante-controles.pdf")
def descargar_comprobante_controles(
    informe_id: int,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para ver este informe")
    if not informe.devolucion:
        raise HTTPException(409, "el informe todavía no fue analizado")
    job = jobs_svc.latest_job(db, informe.id)
    contenido = render_comprobante_controles_markdown(informe, job)
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="comprobante_controles_descargado",
        resumen="Comprobante de controles automáticos aplicados descargado",
        informe_id=informe.id,
        metadata={"formato": "pdf", "version_analisis": job.version_analisis if job else None},
    )
    db.commit()
    filename = f"comprobante-controles-{informe.id}-{slug(informe.periodo)}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=render_reporte_pdf(contenido), media_type="application/pdf", headers=headers)

@router.post("/{informe_id}/analizar", response_model=schemas.AnalisisOut)
def analizar_informe(
    informe_id: int, payload: dict = Body(default_factory=dict), db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)
):
    """Corre el flujo completo: lentes disponibles -> triangulación entre modelos
    -> devolución al responsable de decisión. No dispara nada hacia otras unidades todavía.
    payload opcional: {"modelos": ["gpt", "gemini", ...]} para elegir con cuáles de los
    modelos disponibles triangular; si se omite o viene vacío, corre el perfil recomendado."""
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para analizar este informe")
    _rechazar_lector(user, "analizar informes")
    from services.interpretacion_previa import exigir
    exigir(informe)
    if informe.devolucion:
        raise HTTPException(409, "este informe ya fue analizado; ver /informes/{id}")
    cuota_ia.verificar_analisis(db, user)
    modelos = _validar_modelos(payload.get("modelos"))
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="analisis_solicitado",
        resumen="Analisis multilente solicitado",
        informe_id=informe.id,
        metadata={"modelos": modelos or []},
    )
    db.commit()
    return ejecutar_analisis(db, informe, modelos)


@router.post("/{informe_id}/analizar/stream")
def analizar_informe_stream(
    informe_id: int, payload: dict = Body(default_factory=dict), db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)
):
    """Misma corrida que /analizar, pero como Server-Sent Events: un evento
    por lente a medida que termina, uno por cada modelo de IA que responde
    (en el orden en que van llegando, no en el que se lanzaron), uno de
    convergencia/cobertura, y un evento final con el mismo payload que
    devuelve la version no-streaming. Pensado para mostrar progreso en vivo
    en vez de una espera ciega."""
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso para analizar este informe")
    _rechazar_lector(user, "analizar informes")
    from services.interpretacion_previa import exigir
    exigir(informe)
    if informe.devolucion:
        raise HTTPException(409, "este informe ya fue analizado; ver /informes/{id}")
    cuota_ia.verificar_analisis(db, user)
    modelos = _validar_modelos(payload.get("modelos"))
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="analisis_stream_solicitado",
        resumen="Analisis multilente en vivo solicitado",
        informe_id=informe.id,
        metadata={"modelos": modelos or []},
    )
    db.commit()

    def generador():
        # Sesion propia, independiente del ciclo de vida de Depends(get_db):
        # StreamingResponse itera el generador despues de que la funcion de
        # ruta "termina", y no queremos depender de cuando FastAPI cierra la
        # sesion inyectada.
        db_stream = SessionLocal()
        try:
            informe_stream = db_stream.get(models.Informe, informe_id)
            for evento in ejecutar_analisis_stream(db_stream, informe_stream, modelos):
                yield f"data: {json.dumps(jsonable_encoder(evento))}\n\n"
        except Exception:  # noqa: BLE001
            db_stream.rollback()
            logger.exception("falló el análisis en vivo del informe %s", informe_id)
            detalle = "No se pudo completar el análisis. Tu informe está guardado; podés reintentar."
            yield f"data: {json.dumps({'tipo': 'error', 'detalle': detalle})}\n\n"
        finally:
            db_stream.close()

    return StreamingResponse(
        generador(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{informe_id}/comparacion")
def comparacion_corridas(informe_id: int, base_id: Optional[int] = None, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    informe=db.get(models.Informe,informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "sin permiso")
    cobertura=(informe.devolucion.cobertura or {}) if informe.devolucion else {}
    if base_id is None:
        return cobertura.get(
            "comparacion_corridas", {"estado": "sin_base", "motivo": "Corrida histórica sin comparación registrada"}
        )
    base=db.get(models.Informe,base_id)
    if not base:
        raise HTTPException(404, "informe base no encontrado")
    if not _puede_ver(user, base):
        raise HTTPException(403, "sin permiso para ver la base")

    def manifiesto(i):
        m=dict((i.devolucion.cobertura or {}).get('manifiesto',{})) if i.devolucion else {}
        m.update(informe_id=i.id, snapshot_senales=m.get('snapshot_senales',casos_revision.snapshot(i.hallazgos,prioridad_historica=True)),opciones_tecnicas=(i.saneamiento or {}).get('opciones_tecnicas'))
        return m
    return casos_revision.comparar(manifiesto(base),manifiesto(informe))


@router.get("/{informe_id}/datos-analizados")
def consultar_datos_analizados(informe_id: int, q: str = Query("", max_length=200),
                              offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                              descargar: bool = False, db: Session = Depends(get_db),
                              user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "informe no disponible")
    datos = informe.datos or []
    aviso = ("Datos procesados y saneados conservados por Gobernanza. No es el archivo original "
             "ni representa todas sus hojas o contenidos. El número de registro no es la fila del Excel.")
    fuentes = [f.get("nombre_original", "Nombre no registrado") for f in
               (informe.saneamiento or {}).get("proveniencia", {}).get("fuentes", [])]
    if descargar:
        payload = {"informe_id": informe_id, "aviso": aviso, "fuentes": fuentes, "datos": datos}
        return Response(json.dumps(jsonable_encoder(payload), ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="datos-analizados-{informe_id}.json"',
                                 "Cache-Control": "no-store"})
    columnas = list(dict.fromkeys(k for fila in datos if isinstance(fila, dict) for k in fila))
    needle = q.strip().casefold()
    filas = [{"registro": i + 1, "valores": fila} for i, fila in enumerate(datos)
             if not needle or needle in json.dumps(fila, ensure_ascii=False).casefold()]
    payload = {"informe_id": informe_id, "aviso": aviso, "fuentes": fuentes,
               "columnas": columnas, "total": len(datos), "coincidencias": len(filas),
               "offset": offset, "items": filas[offset:offset + limit]}
    return Response(json.dumps(jsonable_encoder(payload), ensure_ascii=False), media_type="application/json",
                    headers={"Cache-Control": "no-store"})


@router.post("/{informe_id}/hallazgos/{hallazgo_id}/respuesta")
def responder_senal(informe_id: int, hallazgo_id: int, payload: dict = Body(...), db: Session = Depends(get_db),
                    user: models.Usuario = Depends(get_current_user)):
    """Qué resultó ser la señal: error real, dato correcto o no sabe. Una fila nueva por respuesta (vale la última)."""
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_responder(user, informe):
        raise HTTPException(403, "sólo quien hizo el informe (con rol de analista) puede responder qué resultó ser cada señal")
    if any(job.estado in jobs_svc.ESTADOS_ABIERTOS for job in (informe.trabajos_analisis or [])):
        raise HTTPException(409, "el informe se está analizando: esperá a que termine para responder")
    hallazgo = db.query(models.Hallazgo).filter_by(id=hallazgo_id, informe_id=informe_id).first()
    if not hallazgo:
        raise HTTPException(404, "observación no encontrada en este informe")
    respuesta = str((payload or {}).get("respuesta") or "").strip()
    if respuesta not in RESPUESTAS_SENAL:
        raise HTTPException(422, "respuesta inválida: error_real, dato_correcto o no_se")
    comentario = " ".join(str((payload or {}).get("comentario") or "").split())
    if len(comentario) > MAX_COMENTARIO_RESPUESTA:
        raise HTTPException(422, f"el comentario admite hasta {MAX_COMENTARIO_RESPUESTA} caracteres")
    e = hallazgo.evidencia or {}
    r = models.RespuestaSenal(hallazgo_id=hallazgo.id, informe_id=informe.id, usuario_id=user.id,
                              respuesta=respuesta, comentario=comentario or None, lente=hallazgo.lente,
                              regla=str(e.get("regla"))[:80] if e.get("regla") else None,
                              hoja=str(e.get("hoja"))[:200] if e.get("hoja") else None,
                              celda=str(e.get("celda"))[:40] if e.get("celda") else None,
                              prioridad=_prioridad_caso(informe, hallazgo), version_motor=_version_motor(db, informe))
    db.add(r)
    # La señal que generó el motor no se modifica: su estado se deriva de la última respuesta.
    db.commit()
    db.refresh(r)
    return {"hallazgo_id": hallazgo.id, "respuesta": _respuesta_publica(r),
            "aviso": "Tu respuesta queda registrada con fecha. Sirve para medir la herramienta, no para evaluarte."}


@router.post("/{informe_id}/cierre")
def responder_cierre(informe_id: int, payload: dict = Body(...), db: Session = Depends(get_db),
                     user: models.Usuario = Depends(get_current_user)):
    """Pregunta de cierre: «¿Corregiste algo del informe antes de entregarlo?» y «¿Encontraste errores que la
    herramienta no señaló?». Un evento por respuesta (vale el último); mide la herramienta, no a la persona."""
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_responder(user, informe):
        raise HTTPException(403, "sólo quien hizo el informe (con rol de analista) puede responder la pregunta de cierre")
    if not informe.devolucion:
        raise HTTPException(409, "el informe todavía no fue analizado")
    if any(job.estado in jobs_svc.ESTADOS_ABIERTOS for job in (informe.trabajos_analisis or [])):
        raise HTTPException(409, "el informe se está analizando: esperá a que termine para responder")
    corrigio = str((payload or {}).get("corrigio") or "").strip()
    if corrigio not in CIERRE_CORRIGIO:
        raise HTTPException(422, "corrigio inválido: si, no o todavia_no")
    crudo = (payload or {}).get("errores_no_senalados")
    errores = None
    if crudo not in (None, ""):
        if isinstance(crudo, bool) or not (isinstance(crudo, int) or (isinstance(crudo, str) and crudo.strip().isdigit())):
            raise HTTPException(422, "errores_no_senalados tiene que ser una cantidad entera (0 o más)")
        errores = int(crudo)
        if not 0 <= errores <= MAX_ERRORES_NO_SENALADOS:
            raise HTTPException(422, f"errores_no_senalados va de 0 a {MAX_ERRORES_NO_SENALADOS}")
    evento = actividad_svc.registrar(
        db, usuario=user, modulo="multilente", accion=ACCION_CIERRE,
        resumen="Pregunta de cierre del informe respondida", informe_id=informe.id,
        metadata={"corrigio": corrigio, "errores_no_senalados": errores,
                  "version_motor": _version_motor(db, informe), "es_prueba": _es_prueba(informe)})
    db.commit()
    db.refresh(evento)
    return {"cierre": _cierre_publico(evento),
            "aviso": "Tu respuesta queda registrada con fecha. Sirve para medir la herramienta, no para evaluarte."}


@router.post("/{informe_id}/lector/{pregunta_id}")
def confirmar_lectura(informe_id: int, pregunta_id: str, payload: dict = Body(...), db: Session = Depends(get_db),
                      user: models.Usuario = Depends(get_current_user)):
    """Respuesta a una pregunta del lector del cuadro («¿la fila 16 es el total de las filas 17 a 33?»)."""
    from services import lector_mapa

    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_responder(user, informe):
        raise HTTPException(403, "sólo quien hizo el informe (con rol de analista) puede confirmar cómo se leyó el cuadro")
    if any(job.estado in jobs_svc.ESTADOS_ABIERTOS for job in (informe.trabajos_analisis or [])):
        raise HTTPException(409, "el informe se está analizando: esperá a que termine para responder")
    confirma = (payload or {}).get("confirma")
    if not isinstance(confirma, bool):
        raise HTTPException(422, "confirma tiene que ser verdadero o falso")
    try:
        informe.saneamiento, pregunta = lector_mapa.confirmar(informe.saneamiento or {}, pregunta_id, confirma, user.id)
    except KeyError:
        raise HTTPException(404, "pregunta no encontrada en este informe")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    db.add(informe)
    db.commit()
    return {"pregunta": pregunta,
            "aviso": "Respuesta registrada. Se aplica al volver a analizar el informe."}


@router.get("/{informe_id}/hallazgos/{hallazgo_id}/evidencia")
def consultar_evidencia_origen(informe_id: int, hallazgo_id: int, db: Session = Depends(get_db),
                              user: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver(user, informe):
        raise HTTPException(403, "informe no disponible")
    hallazgo = db.query(models.Hallazgo).filter_by(id=hallazgo_id, informe_id=informe_id).first()
    if not hallazgo:
        raise HTTPException(404, "observación no encontrada en este informe")
    payload = {"informe_id": informe_id, "hallazgo_id": hallazgo_id,
               "descripcion": hallazgo.descripcion, "evidencia": hallazgo.evidencia or {},
               "aviso": "Evidencia conservada al ejecutar el control. No es una vista del archivo original. "
                        "Las ubicaciones ausentes no se reconstruyen a partir de los registros procesados."}
    return Response(json.dumps(jsonable_encoder(payload), ensure_ascii=False), media_type="application/json",
                    headers={"Cache-Control": "no-store"})
