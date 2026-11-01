from __future__ import annotations

import datetime
import html
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

import models
import schemas
from core.auth import get_current_user, require_admin
from database import get_db
from services import actividad as actividad_svc
from services import certificaciones as certificaciones_svc
from services import plural, sanitizacion

router = APIRouter(prefix="/certificaciones", tags=["certificaciones"])
verification_router = APIRouter(tags=["verificacion-sellos"])


@router.get("/lentes")
def listar_matriz_lentes(db: Session = Depends(get_db), _user: models.Usuario = Depends(get_current_user)):
    """Matriz canónica usada por interfaz, anexos y revisión institucional."""
    protocolo = db.query(models.VersionProtocolo).filter(
        models.VersionProtocolo.codigo == "B-1", models.VersionProtocolo.activo.is_(True)
    ).order_by(models.VersionProtocolo.id.desc()).first()
    return certificaciones_svc.matriz_versionada(protocolo) if protocolo else []


def _puede_ver_objeto(user: models.Usuario, objeto) -> bool:
    propietario_id = getattr(objeto, "usuario_id", None)
    return bool(user.rol == "admin" or (propietario_id is not None and propietario_id == user.id))


def _cargar_evaluacion(db: Session, evaluacion_id: int) -> models.EvaluacionCertificacion:
    evaluacion = (
        db.query(models.EvaluacionCertificacion)
        .options(
            selectinload(models.EvaluacionCertificacion.protocolo).selectinload(models.VersionProtocolo.controles),
            selectinload(models.EvaluacionCertificacion.resultados).selectinload(models.ResultadoControl.control),
            selectinload(models.EvaluacionCertificacion.resultados).selectinload(models.ResultadoControl.evidencias),
            selectinload(models.EvaluacionCertificacion.resultados).selectinload(models.ResultadoControl.historial),
            selectinload(models.EvaluacionCertificacion.sello),
        )
        .filter(models.EvaluacionCertificacion.id == evaluacion_id)
        .first()
    )
    if not evaluacion:
        raise HTTPException(404, "evaluación no encontrada")
    return evaluacion


def _objeto_y_hash(evaluacion: models.EvaluacionCertificacion):
    if evaluacion.informe_id:
        if not evaluacion.informe:
            raise HTTPException(409, "el informe evaluado ya no está disponible")
        _, huella = certificaciones_svc.snapshot_informe(evaluacion.informe)
        return evaluacion.informe, huella
    if not evaluacion.proyecto:
        raise HTTPException(409, "el proyecto evaluado ya no está disponible")
    _, huella = certificaciones_svc.snapshot_proyecto(evaluacion.proyecto)
    return evaluacion.proyecto, huella


def _crear_evaluacion(
    db: Session,
    user: models.Usuario,
    protocolo: models.VersionProtocolo,
    *,
    informe: models.Informe | None = None,
    proyecto: models.ProyectoIA | None = None,
) -> models.EvaluacionCertificacion:
    if informe:
        snapshot, huella = certificaciones_svc.snapshot_informe(informe)
        snapshot["ejecucion_automatica"] = (informe.devolucion.cobertura or {}).get("manifiesto") if informe.devolucion else None
        filtro = models.EvaluacionCertificacion.informe_id == informe.id
    elif proyecto:
        snapshot, huella = certificaciones_svc.snapshot_proyecto(proyecto)
        filtro = models.EvaluacionCertificacion.proyecto_id == proyecto.id
    else:
        raise HTTPException(422, "falta objeto para evaluar")

    anterior = (
        db.query(models.EvaluacionCertificacion)
        .filter(filtro, models.EvaluacionCertificacion.protocolo_id == protocolo.id)
        .order_by(models.EvaluacionCertificacion.creado_en.desc(), models.EvaluacionCertificacion.id.desc())
        .first()
    )
    if anterior and anterior.hash_objeto == huella and anterior.estado != "reemplazada":
        return _cargar_evaluacion(db, anterior.id)
    if anterior and anterior.estado == "sellada":
        anterior.estado = "reemplazada"
        if anterior.sello and anterior.sello.estado == "vigente":
            anterior.sello.estado = "reemplazado"

    evaluacion = models.EvaluacionCertificacion(
        protocolo_id=protocolo.id,
        informe_id=informe.id if informe else None,
        proyecto_id=proyecto.id if proyecto else None,
        creado_por_id=user.id,
        estado="en_revision",
        hash_objeto=huella,
        snapshot_objeto=snapshot,
        manifiesto_modelos=certificaciones_svc.construir_manifiesto_modelos(informe),
    )
    db.add(evaluacion)
    db.flush()
    for control in protocolo.controles:
        estado = certificaciones_svc.estado_inicial_b1(control, informe) if informe else "no_evaluable"
        resultado = models.ResultadoControl(
            evaluacion_id=evaluacion.id,
            control_id=control.id,
            estado=estado,
            revisado_por_id=None,  # Iniciar B-1 no constituye revisar sus controles.
        )
        db.add(resultado)
        db.flush()
        if informe:
            evidencia = certificaciones_svc.evidencia_inicial_b1(control, informe)
            if evidencia:
                db.add(
                    models.EvidenciaControl(
                        resultado_id=resultado.id,
                        agregado_por_id=user.id,
                        **evidencia,
                    )
                )
    db.flush()
    db.refresh(evaluacion)
    evaluacion.estado = certificaciones_svc.estado_evaluacion(evaluacion)
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="certificaciones",
        accion="evaluacion_creada",
        resumen=f"Evaluación {protocolo.codigo} iniciada",
        informe_id=informe.id if informe else None,
        proyecto_id=proyecto.id if proyecto else None,
        metadata={"evaluacion_id": evaluacion.id, "protocolo": protocolo.codigo, "version": protocolo.version},
    )
    db.commit()
    return _cargar_evaluacion(db, evaluacion.id)


@router.get("/protocolos", response_model=list[schemas.VersionProtocoloOut])
def listar_protocolos(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return (
        db.query(models.VersionProtocolo)
        .options(selectinload(models.VersionProtocolo.controles))
        .filter(models.VersionProtocolo.activo.is_(True))
        .order_by(models.VersionProtocolo.codigo, models.VersionProtocolo.version)
        .all()
    )


@router.post("/informes/{informe_id}/evaluacion", response_model=schemas.EvaluacionCertificacionOut)
def iniciar_b1(
    informe_id: int,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver_objeto(user, informe) or user.rol == "lector":
        raise HTTPException(403, "sin permiso para iniciar la evaluación")
    if not informe.devolucion:
        raise HTTPException(409, "el informe debe completar primero el análisis multilente")
    protocolo = (
        db.query(models.VersionProtocolo)
        .options(selectinload(models.VersionProtocolo.controles))
        .filter(
            models.VersionProtocolo.codigo == "B-1",
            models.VersionProtocolo.tipo_objeto == "informe",
            models.VersionProtocolo.activo.is_(True),
        )
        .order_by(models.VersionProtocolo.id.desc())
        .first()
    )
    if not protocolo:
        raise HTTPException(503, "no hay una versión activa del protocolo B-1")
    return _crear_evaluacion(db, user, protocolo, informe=informe)


@router.post("/proyectos/{proyecto_id}/evaluacion", response_model=schemas.EvaluacionCertificacionOut)
def iniciar_r1(
    proyecto_id: int,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    proyecto = db.get(models.ProyectoIA, proyecto_id)
    if not proyecto:
        raise HTTPException(404, "proyecto no encontrado")
    if not _puede_ver_objeto(user, proyecto) or user.rol == "lector":
        raise HTTPException(403, "sin permiso para iniciar la evaluación")
    # R-1 es un protocolo institucional opcional: lo inicia el equipo docente cuando un proyecto
    # lo amerita. Iniciado por participantes quedaba abierto sin que nadie lo revisara (03/10/2026).
    if user.rol != "admin":
        raise HTTPException(403, "R-1 lo inicia el equipo docente cuando un proyecto lo amerita; no hace falta para entregar.")
    protocolo = (
        db.query(models.VersionProtocolo)
        .options(selectinload(models.VersionProtocolo.controles))
        .filter(
            models.VersionProtocolo.codigo == "R-1",
            models.VersionProtocolo.tipo_objeto == "proyecto_ia",
            models.VersionProtocolo.activo.is_(True),
        )
        .order_by(models.VersionProtocolo.id.desc())
        .first()
    )
    if not protocolo:
        raise HTTPException(503, "no hay una versión activa del protocolo R-1")
    return _crear_evaluacion(db, user, protocolo, proyecto=proyecto)


@router.get("/informes/{informe_id}/evaluacion", response_model=Optional[schemas.EvaluacionCertificacionOut])
def ultima_evaluacion_b1(
    informe_id: int,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver_objeto(user, informe):
        raise HTTPException(403, "sin permiso para ver esta evaluación")
    evaluacion = (
        db.query(models.EvaluacionCertificacion)
        .filter(models.EvaluacionCertificacion.informe_id == informe_id)
        .order_by(models.EvaluacionCertificacion.creado_en.desc(), models.EvaluacionCertificacion.id.desc())
        .first()
    )
    return _cargar_evaluacion(db, evaluacion.id) if evaluacion else None


@router.get("/proyectos/{proyecto_id}/evaluacion", response_model=Optional[schemas.EvaluacionCertificacionOut])
def ultima_evaluacion_r1(
    proyecto_id: int,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    proyecto = db.get(models.ProyectoIA, proyecto_id)
    if not proyecto:
        raise HTTPException(404, "proyecto no encontrado")
    if not _puede_ver_objeto(user, proyecto):
        raise HTTPException(403, "sin permiso para ver esta evaluación")
    evaluacion = (
        db.query(models.EvaluacionCertificacion)
        .filter(models.EvaluacionCertificacion.proyecto_id == proyecto_id)
        .order_by(models.EvaluacionCertificacion.creado_en.desc(), models.EvaluacionCertificacion.id.desc())
        .first()
    )
    return _cargar_evaluacion(db, evaluacion.id) if evaluacion else None


@router.get("/evaluaciones/{evaluacion_id}", response_model=schemas.EvaluacionCertificacionOut)
def obtener_evaluacion(
    evaluacion_id: int,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    evaluacion = _cargar_evaluacion(db, evaluacion_id)
    objeto, _ = _objeto_y_hash(evaluacion)
    if not _puede_ver_objeto(user, objeto):
        raise HTTPException(403, "sin permiso para ver esta evaluación")
    return evaluacion


@router.get("/evaluaciones/{evaluacion_id}/reporte")
def reporte_evaluacion(
    evaluacion_id: int,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    """Lectura única de la evaluación: matriz de la versión institucional B-1
    (once controles en v1.2; las evaluaciones históricas conservan su versión)
    más los siete anexos autónomos por lente, "Para concluir se requiere",
    alcance/exclusiones y cumplimiento de la política de modelos. La misma
    función alimenta la exportación markdown -- evita que API y reporte
    exportable diverjan."""
    evaluacion = _cargar_evaluacion(db, evaluacion_id)
    objeto, huella_actual = _objeto_y_hash(evaluacion)
    if not _puede_ver_objeto(user, objeto):
        raise HTTPException(403, "sin permiso para ver esta evaluación")
    return certificaciones_svc.construir_reporte_evaluacion(evaluacion, huella_actual)


@router.get("/metricas")
def metricas_certificacion(
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(require_admin),
):
    """Lectura agregada micro, meso y macro; nunca compara personas."""
    evaluaciones = (
        db.query(models.EvaluacionCertificacion)
        .options(
            selectinload(models.EvaluacionCertificacion.protocolo),
            selectinload(models.EvaluacionCertificacion.resultados).selectinload(models.ResultadoControl.control),
            selectinload(models.EvaluacionCertificacion.sello),
        )
        .all()
    )
    protocolos_activos = db.query(models.VersionProtocolo).filter(models.VersionProtocolo.activo.is_(True)).all()
    por_protocolo: dict[str, dict] = {
        protocolo.codigo: {
            "protocolo": protocolo.codigo,
            "nombre": protocolo.nombre,
            "evaluaciones": 0,
            "en_revision": 0,
            "con_observaciones": 0,
            "listas_para_emision": 0,
            "selladas": 0,
            "sellos_vigentes": 0,
        }
        for protocolo in protocolos_activos
    }
    por_control: dict[str, dict] = {}
    reevaluados = 0
    for evaluacion in evaluaciones:
        codigo = evaluacion.protocolo.codigo
        agregado = por_protocolo[codigo]
        agregado["evaluaciones"] += 1
        clave_estado = {
            "lista_para_emision": "listas_para_emision",
            "sellada": "selladas",
        }.get(evaluacion.estado, evaluacion.estado)
        if clave_estado in agregado:
            agregado[clave_estado] += 1
        if evaluacion.sello and evaluacion.sello.estado == "vigente":
            agregado["sellos_vigentes"] += 1
        if evaluacion.reevaluado_en:
            reevaluados += 1
        for resultado in evaluacion.resultados:
            clave = resultado.control.codigo
            control = por_control.setdefault(
                clave,
                {
                    "codigo": clave,
                    "nombre": resultado.control.nombre,
                    "protocolo": codigo,
                    "conforme": 0,
                    "observado": 0,
                    "no_evaluable": 0,
                    "no_aplicable": 0,
                    "evidencias": 0,
                },
            )
            if not resultado.aplica:
                control["no_aplicable"] += 1
            else:
                control[resultado.estado] += 1
            control["evidencias"] += len(resultado.evidencias)

    protocolos = sorted(por_protocolo.values(), key=lambda item: item["protocolo"])
    controles = sorted(
        por_control.values(),
        key=lambda item: (-item["observado"], -item["no_evaluable"], item["codigo"]),
    )
    sellos_vigentes = sum(item["sellos_vigentes"] for item in protocolos)
    return {
        "micro": {
            "evaluaciones": len(evaluaciones),
            "reevaluaciones": reevaluados,
            "sellos_vigentes": sellos_vigentes,
            "evidencias": sum(item["evidencias"] for item in controles),
        },
        "meso": {
            "controles": controles,
            "observaciones_recurrentes": [item for item in controles if item["observado"]][:8],
            "faltantes_recurrentes": [item for item in controles if item["no_evaluable"]][:8],
        },
        "macro": {
            "protocolos": protocolos,
            "lectura": (
                "Todavía no hay evaluaciones reales suficientes para inferir patrones institucionales."
                if len(evaluaciones) < 5
                else "Los patrones agregados pueden orientar mejoras de proceso; no modifican protocolos automáticamente."
            ),
        },
    }


@router.put("/resultados/{resultado_id}", response_model=schemas.EvaluacionCertificacionOut)
def actualizar_resultado(
    resultado_id: int,
    payload: schemas.ResultadoControlUpdate,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(require_admin),
):
    resultado = db.get(models.ResultadoControl, resultado_id)
    if not resultado:
        raise HTTPException(404, "resultado de control no encontrado")
    if resultado.evaluacion.estado in {"sellada", "reemplazada"}:
        raise HTTPException(409, "una evaluación emitida es inmutable; inicie una nueva versión")
    if not payload.aplica and resultado.control.obligatorio:
        raise HTTPException(422, "un control obligatorio no puede marcarse como no aplicable")
    if not payload.aplica and not (payload.justificacion_aplicabilidad or "").strip():
        raise HTTPException(422, "un control no aplicable requiere justificación")
    if payload.estado == "observado" and not (payload.observacion or "").strip():
        raise HTTPException(422, "un control observado requiere una observación")
    anterior = {
        "aplica": resultado.aplica,
        "justificacion_aplicabilidad": resultado.justificacion_aplicabilidad,
        "estado": resultado.estado,
        "observacion": resultado.observacion,
        "accion_requerida": resultado.accion_requerida,
    }
    nuevo = {
        "aplica": payload.aplica,
        "justificacion_aplicabilidad": payload.justificacion_aplicabilidad,
        "estado": payload.estado,
        "observacion": payload.observacion,
        "accion_requerida": payload.accion_requerida,
    }
    db.add(models.HistorialResultadoControl(
        resultado_id=resultado.id, modificado_por_id=user.id,
        estado_anterior=anterior, estado_nuevo=nuevo,
    ))
    resultado.aplica = payload.aplica
    resultado.justificacion_aplicabilidad = payload.justificacion_aplicabilidad
    resultado.estado = payload.estado
    resultado.observacion = payload.observacion
    resultado.accion_requerida = payload.accion_requerida
    resultado.revisado_por_id = user.id
    resultado.reevaluado_en = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    resultado.evaluacion.reevaluado_en = resultado.reevaluado_en
    db.flush()
    resultado.evaluacion.estado = certificaciones_svc.estado_evaluacion(resultado.evaluacion)
    db.commit()
    return _cargar_evaluacion(db, resultado.evaluacion_id)


@router.put("/evaluaciones/{evaluacion_id}/conclusion-r1", response_model=schemas.EvaluacionCertificacionOut)
def registrar_conclusion_r1(
    evaluacion_id: int,
    payload: schemas.ConclusionR1Update,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(require_admin),
):
    evaluacion = _cargar_evaluacion(db, evaluacion_id)
    if evaluacion.protocolo.codigo != "R-1":
        raise HTTPException(422, "esta conclusión solo corresponde al protocolo R-1")
    if evaluacion.estado in {"sellada", "reemplazada"}:
        raise HTTPException(409, "una evaluación emitida es inmutable")
    evaluacion.conclusion_r1 = payload.conclusion
    evaluacion.fundamento_conclusion_r1 = payload.fundamento.strip()
    evaluacion.reevaluado_en = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    db.flush()
    evaluacion.estado = certificaciones_svc.estado_evaluacion(evaluacion)
    actividad_svc.registrar(
        db, usuario=user, modulo="certificaciones", accion="conclusion_r1_registrada",
        resumen="Conclusión humana R-1 registrada", proyecto_id=evaluacion.proyecto_id,
        metadata={"evaluacion_id": evaluacion.id, "conclusion": evaluacion.conclusion_r1},
    )
    db.commit()
    return _cargar_evaluacion(db, evaluacion.id)


@router.get("/evaluaciones/{evaluacion_id}/anexos/{lente}")
def obtener_anexo_lente(
    evaluacion_id: int,
    lente: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    evaluacion = _cargar_evaluacion(db, evaluacion_id)
    objeto, _ = _objeto_y_hash(evaluacion)
    if not _puede_ver_objeto(user, objeto):
        raise HTTPException(403, "sin permiso para ver esta evaluación")
    anexo = next((item for item in certificaciones_svc.anexos_lentes(evaluacion) if item["lente"] == lente), None)
    if not anexo:
        raise HTTPException(404, "anexo de lente no encontrado")
    if "text/html" not in request.headers.get("accept", ""):
        return anexo
    preguntas = "".join(f"<li>{html.escape(str(item))}</li>" for item in anexo["preguntas"])
    evidencias = "".join(f"<li>{html.escape(str(item))}</li>" for item in anexo["evidencia_utilizada"]) or "<li>Sin evidencia registrada.</li>"
    hallazgos = "".join(f"<li>{html.escape(str(item))}</li>" for item in anexo["hallazgos"]) or "<li>Sin hallazgos.</li>"
    faltantes = "".join(f"<li>{html.escape(str(item))}</li>" for item in anexo["informacion_faltante"]) or "<li>Ninguno registrado.</li>"
    pagina = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Anexo {html.escape(anexo['nombre'])}</title><style>body{{font-family:Inter,Arial;background:#f4f7fa;color:#172033;padding:30px}}main{{max-width:850px;margin:auto;background:#fff;padding:32px;border-radius:14px}}h1{{color:#1f4d78}}.estado{{display:inline-block;padding:7px 12px;background:#eef4f8;border-radius:20px}}li{{margin:7px 0}}</style></head><body><main><p>Protocolo {html.escape(evaluacion.protocolo.codigo)} v{html.escape(evaluacion.protocolo.version)}</p><h1>Anexo · {html.escape(anexo['nombre'])}</h1><p class='estado'>{html.escape(anexo['estado'])}</p><h2>Qué se quiso verificar</h2><p>{html.escape(anexo['pregunta_central'])}</p><h2>Preguntas canónicas</h2><ul>{preguntas}</ul><h2>Evidencia utilizada</h2><ul>{evidencias}</ul><h2>Hallazgos</h2><ul>{hallazgos}</ul><h2>Información faltante</h2><ul>{faltantes}</ul><h2>Acciones requeridas</h2><p>{html.escape('; '.join(anexo['accion_requerida']) or 'Ninguna pendiente.')}</p><h2>Límites</h2><p>{html.escape('; '.join(anexo['limites']))}</p></main></body></html>"""
    return HTMLResponse(pagina)


@router.post("/resultados/{resultado_id}/evidencias", response_model=schemas.EvaluacionCertificacionOut)
def agregar_evidencia(
    resultado_id: int,
    payload: schemas.EvidenciaControlCreate,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    if certificaciones_svc.es_evidencia_exploratoria(payload):
        raise HTTPException(422, "Las hipótesis exploratorias no pueden alimentar evidencia B-1 ni R-1")
    resultado = db.get(models.ResultadoControl, resultado_id)
    if not resultado:
        raise HTTPException(404, "resultado de control no encontrado")
    evaluacion = resultado.evaluacion
    objeto, _ = _objeto_y_hash(evaluacion)
    if not _puede_ver_objeto(user, objeto) or user.rol == "lector":
        raise HTTPException(403, "sin permiso para aportar evidencia")
    if evaluacion.estado in {"sellada", "reemplazada"}:
        raise HTTPException(409, "una evaluación emitida es inmutable; inicie una nueva versión")
    db.add(
        models.EvidenciaControl(
            resultado_id=resultado.id,
            tipo=payload.tipo,
            descripcion=payload.descripcion,
            referencia=payload.referencia,
            metadata_evidencia={**(payload.metadata_evidencia or {}), "proveniencia_aporte": {
                "tipo": "aporte_manual", "usuario_id": user.id, "evaluacion_id": evaluacion.id,
                "archivo_origen_verificado": False,
                "limite": "Referencia aportada por el responsable; no implica verificación automática del archivo citado.",
            }},
            agregado_por_id=user.id,
        )
    )
    db.flush()
    evaluacion.estado = certificaciones_svc.estado_evaluacion(evaluacion)
    db.commit()
    return _cargar_evaluacion(db, evaluacion.id)


@router.post("/evaluaciones/{evaluacion_id}/emitir", response_model=schemas.SelloCertificacionOut)
def emitir_sello(
    evaluacion_id: int,
    payload: schemas.EmisionSelloCreate,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(require_admin),
):
    evaluacion = _cargar_evaluacion(db, evaluacion_id)
    _, huella_actual = _objeto_y_hash(evaluacion)
    if evaluacion.sello:
        raise HTTPException(409, "esta evaluación ya tiene un sello emitido")
    motivos = certificaciones_svc.motivos_bloqueo(evaluacion, huella_actual)
    motivos.extend(certificaciones_svc.motivos_separacion_emisor(evaluacion, user.id))
    if motivos:
        raise HTTPException(409, {"mensaje": "la evaluación no está lista para emisión", "motivos": motivos})
    sello = models.SelloCertificacion(
        evaluacion_id=evaluacion.id,
        identificador_publico=str(uuid.uuid4()),
        estado="vigente",
        hash_objeto=evaluacion.hash_objeto,
        resumen_alcance=payload.alcance_del_analisis,
        limitaciones=certificaciones_svc.exclusiones_completas(
            evaluacion.protocolo.codigo, payload.excluidos_del_analisis
        ),
        emitido_por_id=user.id,
    )
    evaluacion.estado = "sellada"
    db.add(sello)
    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="certificaciones",
        accion="sello_emitido",
        resumen=f"Sello {evaluacion.protocolo.codigo} emitido",
        informe_id=evaluacion.informe_id,
        proyecto_id=evaluacion.proyecto_id,
        metadata={"evaluacion_id": evaluacion.id, "identificador_publico": sello.identificador_publico},
    )
    db.commit()
    db.refresh(sello)
    return sello


@router.post("/sellos/{sello_id}/revocar", response_model=schemas.SelloCertificacionOut)
def revocar_sello(
    sello_id: int,
    payload: schemas.RevocacionSelloCreate,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(require_admin),
):
    sello = db.get(models.SelloCertificacion, sello_id)
    if not sello:
        raise HTTPException(404, "sello no encontrado")
    if sello.estado == "revocado":
        return sello
    sello.estado = "revocado"
    sello.revocado_en = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    sello.motivo_revocacion = payload.motivo
    sello.revocado_por_id = user.id
    actividad_svc.registrar(
        db, usuario=user, modulo="certificaciones", accion="sello_revocado",
        resumen=f"Sello {sello.evaluacion.protocolo.codigo} revocado",
        informe_id=sello.evaluacion.informe_id, proyecto_id=sello.evaluacion.proyecto_id,
        metadata={"evaluacion_id": sello.evaluacion_id, "identificador_publico": sello.identificador_publico, "motivo": payload.motivo},
    )
    db.commit()
    db.refresh(sello)
    return sello


@verification_router.get("/verificar-sello/{identificador_publico}")
def verificar_sello(
    identificador_publico: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    sello = (
        db.query(models.SelloCertificacion)
        .options(
            selectinload(models.SelloCertificacion.evaluacion)
            .selectinload(models.EvaluacionCertificacion.protocolo),
            selectinload(models.SelloCertificacion.evaluacion)
            .selectinload(models.EvaluacionCertificacion.resultados)
            .selectinload(models.ResultadoControl.control),
            selectinload(models.SelloCertificacion.evaluacion)
            .selectinload(models.EvaluacionCertificacion.resultados)
            .selectinload(models.ResultadoControl.historial),
            selectinload(models.SelloCertificacion.emitido_por),
            selectinload(models.SelloCertificacion.revocado_por),
        )
        .filter(models.SelloCertificacion.identificador_publico == identificador_publico)
        .first()
    )
    if not sello:
        raise HTTPException(404, "sello no encontrado")
    evaluacion = sello.evaluacion
    resultados = evaluacion.resultados
    objeto_id = evaluacion.informe_id if evaluacion.informe_id is not None else evaluacion.proyecto_id
    if objeto_id is None:
        raise HTTPException(409, "el sello no tiene un objeto asociado")
    responsables_revision = certificaciones_svc.responsables_que_revisaron(evaluacion)
    revision_emision_separadas = any(
        responsable_id != sello.emitido_por_id for responsable_id in responsables_revision
    )
    sanear = sanitizacion.redactar_texto_libre
    salida = schemas.VerificacionSelloOut(
        identificador_publico=sello.identificador_publico,
        estado=sello.estado,
        protocolo=evaluacion.protocolo.codigo,
        version=evaluacion.protocolo.version,
        tipo_objeto=evaluacion.protocolo.tipo_objeto,
        objeto_id=objeto_id,
        hash_objeto=sello.hash_objeto,
        alcance_del_analisis=sanear(sello.resumen_alcance),
        analisis_excluidos=[sanear(item) for item in sello.limitaciones],
        resumen_alcance=sanear(sello.resumen_alcance),
        limitaciones=[sanear(item) for item in sello.limitaciones],
        emitido_en=sello.emitido_en,
        emitido_por=sello.emitido_por.nombre,
        responsables_revision=len(responsables_revision),
        ultima_revision_en=certificaciones_svc.ultima_revision(evaluacion),
        revision_emision_separadas=revision_emision_separadas,
        revocado_por=sello.revocado_por.nombre if sello.revocado_por else None,
        revocado_en=sello.revocado_en,
        motivo_revocacion=sanear(sello.motivo_revocacion or "") or None,
        estado_evaluacion_visible=certificaciones_svc.estado_visible(evaluacion.estado),
        controles_conformes=sum(1 for r in resultados if r.aplica and r.estado == "conforme"),
        controles_no_aplicables=sum(1 for r in resultados if not r.aplica),
        controles_totales=len(resultados),
        lentes=certificaciones_svc.anexos_lentes_publicos(evaluacion),
        model_policy_cumplida=not certificaciones_svc.motivos_incumplimiento_model_policy(
            evaluacion.protocolo, evaluacion.manifiesto_modelos or []
        ),
        conclusion_r1=evaluacion.conclusion_r1,
        fundamento_conclusion_r1=sanear(evaluacion.fundamento_conclusion_r1 or "") or None,
        declaracion=certificaciones_svc.DECLARACION_SELLO,
    )
    cache_headers = {"Cache-Control": "public, max-age=60, must-revalidate"}
    if "text/html" not in request.headers.get("accept", ""):
        response.headers.update(cache_headers)
        return salida
    color = "#176b47" if sello.estado == "vigente" else "#9a3412"
    excluidos = "".join(f"<li>{html.escape(item)}</li>" for item in salida.analisis_excluidos)
    revocacion = ""
    if sello.estado == "revocado":
        revocacion = (
            f"<section class='warning'><h2>Constancia revocada</h2><p>{html.escape(salida.motivo_revocacion or '')}</p>"
            f"<p>Responsable: {html.escape(salida.revocado_por or 'no registrado')}</p></section>"
        )
    lentes = "".join(
        "<article><h3>" + html.escape(str(lente.get("nombre", ""))) + "</h3>"
        "<p><strong>Estado:</strong> " + html.escape(str(lente.get("estado", ""))) + "</p>"
        "<p>" + html.escape(str(lente.get("pregunta_central", ""))) + "</p></article>"
        for lente in salida.lentes
    )
    conclusion = ""
    if salida.protocolo == "R-1":
        conclusion = (
            "<h2>Conclusión humana</h2><p><strong>" + html.escape(salida.conclusion_r1 or "No registrada")
            + "</strong></p><p>" + html.escape(salida.fundamento_conclusion_r1 or "") + "</p>"
        )
    pagina = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Verificación {html.escape(salida.protocolo)}</title><style>
    body{{font-family:Inter,Arial,sans-serif;background:#f3f6f8;color:#172033;margin:0;padding:32px}}main{{max-width:860px;margin:auto;background:white;padding:34px;border-radius:16px;box-shadow:0 18px 50px #17203318}}.seal{{border:3px solid {color};padding:20px;border-radius:14px}}.mark{{font-size:44px;font-weight:800;color:{color}}}h1{{margin:.2em 0}}code{{overflow-wrap:anywhere}}dt{{font-weight:700;margin-top:12px}}dd{{margin:3px 0}}.warning{{background:#fff1e8;border-left:5px solid #9a3412;padding:12px 18px;margin:18px 0}}blockquote{{border-left:4px solid #b58b32;margin:22px 0;padding:10px 18px;background:#fffbeb}}.lenses{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.lenses article{{border:1px solid #d9e0e5;border-radius:10px;padding:12px}}.lenses h3{{margin:0 0 6px}}</style></head>
    <body><main><div class='seal'><div class='mark'>{html.escape(salida.protocolo)}</div><h1>Constancia {html.escape(salida.estado)}</h1><p>{html.escape(salida.estado_evaluacion_visible)}</p></div>{revocacion}
    <dl><dt>Protocolo</dt><dd>{html.escape(salida.protocolo)} v{html.escape(salida.version)}</dd><dt>Objeto</dt><dd>{html.escape(salida.tipo_objeto)} #{salida.objeto_id}</dd><dt>Identificador público</dt><dd><code>{html.escape(salida.identificador_publico)}</code></dd><dt>Huella SHA-256</dt><dd><code>{html.escape(salida.hash_objeto)}</code></dd><dt>Fecha de emisión</dt><dd>{salida.emitido_en.strftime('%Y-%m-%d %H:%M UTC')}</dd><dt>Responsable de emisión</dt><dd>{html.escape(salida.emitido_por)}</dd><dt>Intervención humana</dt><dd>Revisado por {plural.contar(salida.responsables_revision, 'responsable')}. {'Revisión y emisión a cargo de personas distintas, conforme al protocolo.' if salida.revision_emision_separadas else 'No consta separación entre revisión y emisión.'}</dd><dt>Última revisión</dt><dd>{salida.ultima_revision_en.strftime('%Y-%m-%d %H:%M UTC') if salida.ultima_revision_en else 'No registrada'}</dd><dt>Alcance</dt><dd>{html.escape(salida.alcance_del_analisis)}</dd></dl>
    <h2>Controles</h2><p>{salida.controles_conformes} conformes · {salida.controles_no_aplicables} no aplicables · {salida.controles_totales} totales.</p>{conclusion}<h2>Revisión por lentes</h2><div class='lenses'>{lentes}</div><h2>Análisis excluidos</h2><ul>{excluidos}</ul><blockquote>{html.escape(salida.declaracion)}</blockquote></main></body></html>"""
    return HTMLResponse(pagina, headers=cache_headers)
