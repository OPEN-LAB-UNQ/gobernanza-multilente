"Cola secuencial de analisis persistida en PostgreSQL."
from __future__ import annotations

import datetime as dt
import logging
import threading

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

import models
from database import SessionLocal
from services import plural
from services.analisis import ejecutar_analisis_stream
from services.notificaciones import enviar_analisis_finalizado
from versiones import ANALYSIS_VERSION

logger = logging.getLogger("gobernanza.jobs")

_event = threading.Event()
_lock = threading.Lock()
_worker: threading.Thread | None = None
_stop = False
ESTADOS_ABIERTOS = {"pendiente", "procesando"}
LECTURA_CANCELADA = "Lectura cancelada a pedido. No se ejecutaron controles; podés volver a cargar el archivo."


def error_interno(job_id: int) -> str:
    """Lo que ve quien cargó cuando el análisis falla: sin el texto de la excepción, con el número para buscarlo."""
    return (f"El análisis se detuvo por un error interno y no produjo una conclusión (trabajo {job_id}). "
            "Volvé a intentarlo; si se repite, avisá citando ese número de trabajo.")


class LecturaCancelada(Exception):
    """Quien pidió la lectura la canceló: no se piden más lecturas a los modelos ni se ejecutan controles."""
NOMBRES_ETAPA_LENTE = {
    "ajedrecista": "Coherencia interna",
    "matematico": "Cálculos y métodos",
    "cronista": "Evolución temporal",
    "orquesta": "Coherencia documental",
    "radiologo": "Antecedentes comparables",
    "rizoma": "Conexiones exploratorias",
    "conciliador": "Contexto técnico",
}


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _evento(
    paso: int,
    etapa: str,
    mensaje: str,
    *,
    estado: str = "completado",
    detalle: str | None = None,
) -> dict:
    return {
        "paso": paso,
        "etapa": etapa,
        "estado": estado,
        "mensaje": mensaje,
        "detalle": detalle,
        "registrado_en": _now().isoformat(),
    }


def _evento_analisis(evento: dict, paso: int) -> dict | None:
    tipo = evento.get("tipo")
    if tipo == "lente":
        lente = str(evento.get("lente") or "")
        cantidad = int(evento.get("cantidad") or 0)
        nombre = NOMBRES_ETAPA_LENTE.get(lente, str(evento.get("nombre") or lente))
        from services.reporte_ejecutivo import senales

        contexto = min(int(evento.get("contexto") or 0), cantidad)
        partes = []
        if cantidad - contexto:
            partes.append(f"{senales(cantidad - contexto)} para revisar")
        if contexto:
            separadas = "separada" if contexto == 1 else "separadas"
            partes.append(f"{plural.contar(contexto, 'variación', 'variaciones')} {separadas} como contexto, no como error")
        detalle = ("; ".join(partes) + ".") if partes else "Sin señales para revisar."
        condiciones = evento.get("condiciones") or {}
        if condiciones.get("estado") == "no_aplicable":
            # No corresponde a este tipo de archivo: es información, no un problema.
            return _evento(paso, "controles", f"{nombre}: no corresponde a este archivo.",
                           estado="informativo", detalle=condiciones.get("motivo"))
        if condiciones.get("estado") == "no_evaluable":
            return _evento(paso, "controles", f"{nombre}: no se pudo evaluar.",
                           estado="advertencia", detalle=condiciones.get("motivo"))
        return _evento(paso, "controles", f"{nombre}: control terminado.", detalle=detalle)
    if tipo == "modelo":
        nombre = str(evento.get("modelo") or "modelo").upper()
        # Dos tareas distintas: leer las señales (ok) y explorar el libro, que sólo existe
        # cuando el informe trae contexto semántico (exploracion_completada no es None).
        from services.reporte_ejecutivo import _estado_exploracion

        exploracion = evento.get("exploracion_completada")
        if evento.get("lectura_senales") == "no_solicitada":
            completa = exploracion is True
            return _evento(paso, "exploracion",
                           f"{nombre}: {'completó la exploración del libro' if completa else 'la exploración del libro quedó incompleta'}.",
                           estado="completado" if completa else "advertencia",
                           detalle="No había señales para leer.")
        causa = ""
        if exploracion is False:
            causa = _estado_exploracion({"evaluada": False, "motivos": evento.get("motivos_exploracion") or []})
            causa = causa.replace("no completada: ", "", 1)
            causa = f"{causa[:1].upper()}{causa[1:]}."
            # Sin un motivo concreto, «No se completó.» repetía el título del evento.
            if causa.rstrip(".").strip().lower() in {"", "no se completó", "no completada"}:
                causa = ""
        if evento.get("ok"):
            if exploracion is False and causa.lower().startswith("completada parcialmente"):
                detalle = causa.split(": ", 1)[-1]
                # El tope de consultas es una decisión de diseño: se informa, no se advierte.
                por_limite = "límite de consultas" in detalle
                return _evento(paso, "exploracion", f"{nombre}: leyó las señales; la exploración del libro quedó parcial.",
                               estado="informativo" if por_limite else "advertencia",
                               detalle=f"{detalle[:1].upper()}{detalle[1:]} No afecta a los controles automáticos.")
            if exploracion is False:
                # Las señales se leyeron: la exploración del libro es una capa adicional, se informa.
                return _evento(paso, "exploracion", f"{nombre}: leyó las señales; la exploración del libro quedó parcial.",
                               estado="informativo", detalle=f"{causa} No afecta a los controles automáticos.".strip())
            if exploracion:
                return _evento(paso, "exploracion", f"{nombre}: leyó las señales y completó la exploración del libro.")
            return _evento(paso, "exploracion", f"{nombre}: lectura de las señales recibida.")
        error = str(evento.get("error") or "Proveedor no disponible.")
        if exploracion is False:
            return _evento(paso, "exploracion", f"{nombre}: no pudo leer las señales ni completar la exploración del libro.",
                           estado="advertencia", detalle=f"{causa} No afecta a los controles automáticos.".strip())
        return _evento(paso, "exploracion", f"{nombre}: no pudo completar la lectura.", estado="advertencia", detalle=error)
    if tipo == "control_solicitado":
        estado_control = str(evento.get("estado") or "")
        return _evento(
            paso,
            "controles",
            f"{evento.get('nombre')}: {estado_control.replace('_', ' ')}.",
            estado="advertencia" if estado_control == "no_evaluable" else "completado",
            detalle=str(evento.get("detalle") or ""),
        )
    if tipo == "lector_inicio":
        return _evento(paso, "controles", "Comprobando las relaciones de la interpretación confirmada…", estado="informativo",
                       detalle="Las reglas usan los valores reales y las propuestas de la lectura previa; esta etapa no vuelve a consultar a los modelos.")
    if tipo == "lector_error":
        return _evento(paso, "controles", "No se pudo completar la comprobación de las relaciones leídas.", estado="advertencia",
                       detalle="Los demás controles continúan. Esta comprobación queda pendiente y se declara en el informe.")
    if tipo == "lector":
        senales_ = int(evento.get("senales") or 0)
        preguntas_ = int(evento.get("preguntas") or 0)
        resumen = evento.get("resumen") or {}
        estado = resumen.get("estado")
        if estado == "no_completada":
            return _evento(paso, "controles", "No se pudo completar la lectura del cuadro con IA.", estado="advertencia",
                           detalle="No hubo suficientes respuestas para contrastar la lectura. Los demás controles continúan.")
        titulo = ("Se leyó el cuadro y se verificaron las relaciones que debería cumplir."
                  if evento.get("modo") == "activo" else
                  "Se leyó el cuadro en modo de observación: lo que encontró no entra en el informe.")
        if estado == "parcial":
            titulo = "La lectura del cuadro con IA quedó parcial. Consultá qué se pudo leer en el detalle."
        elif resumen and not resumen.get("relaciones_acordadas"):
            titulo = "Lectura del cuadro recibida: no hubo relaciones acordadas para comprobar."
        return _evento(paso, "controles", titulo,
                       estado="advertencia" if estado == "parcial" else "completado",
                       detalle=f"{plural.contar(senales_, 'señal', 'señales')} por relaciones leídas; "
                               f"{plural.contar(preguntas_, 'pregunta', 'preguntas')} para confirmar la lectura.")
    if tipo == "convergencia":
        return _evento(
            paso,
            "contraste",
            "Se contrastaron las señales entre las miradas.",
            detalle=f"{plural.contar(int(evento.get('grupos') or 0), 'grupo relacionado', 'grupos relacionados')}.",
        )
    if tipo == "cobertura":
        cobertura = evento.get("cobertura") or {}
        filas = cobertura.get("filas_analizadas")
        return _evento(
            paso,
            "cobertura",
            "Se registró qué se revisó y qué quedó fuera.",
            detalle=f"{plural.contar(filas, 'fila agregada analizada', 'filas agregadas analizadas')}." if filas is not None else None,
        )
    if tipo == "error":
        return _evento(
            paso,
            "error",
            "El análisis se interrumpió.",
            estado="error",
            detalle=str(evento.get("detalle") or "Error sin detalle."),
        )
    return None


def _actualizar_traza(
    job_id: int,
    *,
    evento: dict | None = None,
    metricas: dict | None = None,
    analisis: object | None = None,
) -> None:
    """Persiste progreso en una sesión separada del análisis principal.

    De este modo la interfaz puede consultar eventos reales mientras las
    reglas siguen dentro de su propia transacción.
    """
    db_progreso = SessionLocal()
    try:
        job_progreso = db_progreso.get(models.AnalysisJob, job_id)
        if not job_progreso:
            return
        sobre = dict(job_progreso.resultado or {})
        progreso = list(sobre.get("_progreso") or [])
        if evento:
            progreso.append(evento)
        sobre["_progreso"] = progreso[-80:]
        sobre["_version_analisis"] = ANALYSIS_VERSION
        sobre["_metricas"] = {**dict(sobre.get("_metricas") or {}), **(metricas or {})}
        if analisis is not None:
            sobre["analisis"] = jsonable_encoder(analisis)
        job_progreso.resultado = sobre
        db_progreso.commit()
    finally:
        db_progreso.close()


def latest_job(db: Session, informe_id: int) -> models.AnalysisJob | None:
    return db.query(models.AnalysisJob).filter(models.AnalysisJob.informe_id == informe_id).order_by(models.AnalysisJob.creado_en.desc(), models.AnalysisJob.id.desc()).first()


def enqueue_analysis(db: Session, informe: models.Informe, usuario: models.Usuario | None, modelos: list[str] | None, notify_email: str | None = None, modo_revision: str | None = None) -> models.AnalysisJob:
    from services.interpretacion_previa import exigir
    exigir(informe)
    if informe.devolucion:
        job = latest_job(db, informe.id)
        if job:
            return job
        job = models.AnalysisJob(informe_id=informe.id, usuario_id=usuario.id if usuario else informe.usuario_id, estado="finalizado", modelos=modelos or [], notify_email=notify_email, finalizado_en=_now())
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    abierto = db.query(models.AnalysisJob).filter(models.AnalysisJob.informe_id == informe.id, models.AnalysisJob.estado.in_(ESTADOS_ABIERTOS)).order_by(models.AnalysisJob.creado_en.desc()).first()
    if abierto:
        return abierto
    job = models.AnalysisJob(
        informe_id=informe.id,
        usuario_id=usuario.id if usuario else informe.usuario_id,
        estado="pendiente",
        modelos=modelos or [],
        notify_email=notify_email,
        resultado={
            # La revisión rápida no usa IA: el cupo diario de análisis con IA no la cuenta.
            **({"modo_revision": modo_revision} if modo_revision else {}),
            "_version_analisis": ANALYSIS_VERSION,
            "_metricas": {"filas": len(informe.datos or []), "modelos_solicitados": 0 if modo_revision == "rapida" else len(modelos) if modelos else 1},
            "_progreso": [
                _evento(
                    1,
                    "carga",
                    "Archivo recibido y puesto en cola.",
                    detalle=f"{plural.contar(len(informe.datos or []), 'registro agregado', 'registros agregados')}; no se muestran datos individuales.",
                )
            ],
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    wake_worker()
    return job


def enqueue_interpretacion(db, informe, usuario, opciones, *, detallada=False):
    """Lectura persistida antes de los controles; no requiere conservar archivos originales."""
    from services import interpretacion_previa as ip
    r = informe.saneamiento[ip.CAMPO]
    job = models.AnalysisJob(informe_id=informe.id, usuario_id=usuario.id, estado="pendiente", modelos=[],
        resultado={"fase": "interpretacion", "revision": r["revision"], "opciones": opciones, "detallada": detallada,
                   "_progreso": [_evento(1, "interpretacion", "Lectura previa en cola; no se ejecutaron controles.")],
                   "_metricas": {"fase": "interpretacion"}, "_version_analisis": ANALYSIS_VERSION})
    db.add(job)
    db.commit()
    db.refresh(job)
    wake_worker()
    return job


def procesar_interpretacion(db, job):
    """Etapa recuperable de lectura: publica una propuesta, nunca un análisis."""
    from copy import deepcopy

    from services import interpretacion_previa as ip
    informe = db.get(models.Informe, job.informe_id)
    if not informe:
        raise RuntimeError("El informe ya no está disponible")
    base = deepcopy(informe.saneamiento or {})
    r = base.get(ip.CAMPO) or {}
    config_lectura = dict(job.resultado or {})
    if r.get("estado") != "interpretando" or r.get("revision") != config_lectura.get("revision"):
        raise RuntimeError("La interpretación cambió; esta tarea ya no corresponde a la revisión actual")
    if r.get("datos_huella") != ip.huella(informe.datos) or r.get("opciones_huella") != ip.huella(config_lectura.get("opciones")):
        raise RuntimeError("Los datos o las opciones cambiaron antes de la interpretación")
    job.estado = "procesando"
    job.iniciado_en = job.iniciado_en or _now()
    db.commit()
    from services import biblioteca_casos
    casos = biblioteca_casos.observados(db, job.usuario_id)
    casos.extend(db.query(models.CasoBiblioteca).filter_by(estado="aprobado").all())
    def avance(leidos, total, hoja):
        # Avance visible mientras se lee; el informe se actualiza al final, con su control de concurrencia.
        # Cada avance revisa si la lectura se canceló: así se dejan de pedir lecturas a los modelos.
        db.refresh(job)
        if (job.resultado or {}).get("cancelada"):
            raise LecturaCancelada()
        job.resultado = dict(job.resultado or {}, avance_lectura={"leidos": leidos, "total": total, "hoja": hoja})
        db.commit()
    lectura = ip.interpretar(informe.datos, base, None, config_lectura["opciones"], job.usuario_id,
        detallada=config_lectura.get("detallada", False), anterior=r.get("anterior"),
        archivos_preparados=r["archivos"], casos_revisados=casos, avance=avance)
    if lectura["revision"] != r["revision"]:
        raise RuntimeError("La revisión de la lectura no coincide con la solicitud")
    db.refresh(job)
    if (job.resultado or {}).get("cancelada"):
        raise LecturaCancelada()
    nueva = dict(base, **{ip.CAMPO: lectura})
    n = db.query(models.Informe).filter(models.Informe.id == informe.id, models.Informe.saneamiento == base).update(
        {models.Informe.saneamiento: nueva}, synchronize_session=False)
    if n != 1:
        raise RuntimeError("El informe cambió durante la lectura; no se reemplazó su interpretación")
    job.estado = "finalizado"
    job.finalizado_en = _now()
    job.resultado = {**config_lectura, "_progreso": [*config_lectura.get("_progreso", []),
        _evento(2, "interpretacion", "Interpretación lista para confirmar. No se ejecutaron controles.")],
        "_metricas": {"fase": "interpretacion", "cuadros": len(lectura["cuadros"]), "controles_ejecutados": 0}}
    db.commit()


def wake_worker() -> None:
    ensure_worker_started()
    _event.set()


def ensure_worker_started() -> None:
    global _worker
    with _lock:
        if _worker and _worker.is_alive():
            return
        _worker = threading.Thread(target=_worker_loop, name="gobernanza-analysis-worker", daemon=True)
        _worker.start()


def _claim_next(db: Session) -> models.AnalysisJob | None:
    job = db.query(models.AnalysisJob).filter(models.AnalysisJob.estado == "pendiente").order_by(models.AnalysisJob.creado_en.asc(), models.AnalysisJob.id.asc()).with_for_update(skip_locked=True).first()
    if not job:
        return None
    job.estado = "procesando"
    job.iniciado_en = _now()
    db.commit()
    db.refresh(job)
    return job


def _process_one() -> bool:
    db = SessionLocal()
    job = None
    job_id = None
    try:
        job = _claim_next(db)
        if not job:
            return False
        # El número del trabajo se guarda ya: si el informe se borra durante el análisis, el
        # objeto queda inaccesible y el manejo del error no puede leerlo.
        job_id = job.id
        informe = db.get(models.Informe, job.informe_id)
        if not informe:
            job.estado = "error"
            job.error = "informe no encontrado"
            job.finalizado_en = _now()
            db.commit()
            return True
        if informe.devolucion:
            job.estado = "finalizado"
            job.finalizado_en = _now()
            db.commit()
            return True
        if (job.resultado or {}).get("fase") == "interpretacion":
            procesar_interpretacion(db, job)
            return True
        inicio = _now()
        _actualizar_traza(
            job.id,
            evento=_evento(
                2,
                "lectura",
                "Estructura leída; comienza la revisión.",
                # El período de la carga es la fecha de carga si no se declaró: no presentarlo como el de los datos.
                detalle=(f"Dominio {informe.dominio}; "
                         + (f"período {informe.periodo}; " if (informe.saneamiento or {}).get("periodo_declarado") else "período no declarado; ")
                         + f"{plural.contar(len(informe.datos or []), 'registro')}."),
            ),
        )
        resultado = None
        paso = 3
        lentes_ejecutadas = 0
        modelos_respondieron = 0
        for evento_analisis in ejecutar_analisis_stream(db, informe, job.modelos or None):
            if evento_analisis.get("tipo") == "final":
                resultado = evento_analisis.get("resultado")
                continue
            if evento_analisis.get("tipo") == "lente" and (evento_analisis.get("condiciones") or {}).get("estado", "evaluado") == "evaluado":
                lentes_ejecutadas += 1
            if evento_analisis.get("tipo") == "modelo" and evento_analisis.get("ok"):
                modelos_respondieron += 1
            progreso = _evento_analisis(evento_analisis, paso)
            if progreso:
                _actualizar_traza(job.id, evento=progreso)
                paso += 1
        if resultado is None:
            raise RuntimeError("el análisis no produjo resultado final")
        finalizado = _now()
        duracion = max(0.0, (finalizado - inicio).total_seconds())
        hallazgos = len(getattr(resultado, "hallazgos", []) or [])
        _actualizar_traza(
            job.id,
            evento=_evento(
                paso,
                "resultado",
                "Análisis terminado; la evidencia quedó lista para revisión humana.",
                detalle=f"{plural.contar(hallazgos, 'hallazgo')}. La herramienta no tomó ninguna decisión.",
            ),
            metricas={
                "duracion_segundos": round(duracion, 3),
                "lentes_ejecutadas": lentes_ejecutadas,
                "modelos_respondieron": modelos_respondieron,
                "hallazgos": hallazgos,
            },
            analisis=resultado,
        )
        job.estado = "finalizado"
        job.finalizado_en = finalizado
        estado_mail, error_mail = enviar_analisis_finalizado(job.notify_email, informe.id, "finalizado")
        job.notificacion_estado = estado_mail
        job.notificacion_error = error_mail
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        if isinstance(exc, LecturaCancelada):
            return True  # ya quedó registrada como cancelada: no es un error ni se avisa por correo
        if job_id is not None:
            job = db.get(models.AnalysisJob, job_id)
            if not job:
                # El informe (y su trabajo) se borró durante el análisis: no hay nada que registrar.
                logger.warning("el trabajo %s se borró durante el análisis: %s", job_id, exc.__class__.__name__)
            if job:
                job.estado = "error"
                logger.error("fallo el analisis del informe %s (trabajo %s): %s", job.informe_id, job.id, exc, exc_info=True)
                # La excepción y su traceback quedan sólo en el registro del servidor: a la pantalla y al correo va un
                # mensaje fijo con el número de trabajo, que permite encontrarlo en el registro (auditoría, 28/10/2026).
                error_publico = ("La lectura previa no se completó; no se ejecutaron controles. Volvé a preparar la carga."
                    if (job.resultado or {}).get("fase") == "interpretacion" else error_interno(job.id))
                job.error = error_publico
                job.finalizado_en = _now()
                _actualizar_traza(
                    job.id,
                    evento=_evento(
                        99,
                        "error",
                        "El análisis terminó con un error y no produjo una conclusión.",
                        estado="error",
                        detalle=error_publico,
                    ),
                )
                estado_mail, error_mail = enviar_analisis_finalizado(job.notify_email, job.informe_id, "error", error_publico)
                job.notificacion_estado = estado_mail
                job.notificacion_error = error_mail
                db.commit()
        return True
    finally:
        db.close()


def _worker_loop() -> None:
    while not _stop:
        try:
            hizo = _process_one()
        except Exception:  # noqa: BLE001 - un trabajo con problemas no puede detener la cola
            logger.exception("falla inesperada al procesar un trabajo; la cola sigue")
            hizo = True
        if not hizo:
            _event.wait(8)
            _event.clear()


def recover_processing_jobs() -> None:
    db = SessionLocal()
    try:
        db.query(models.AnalysisJob).filter(models.AnalysisJob.estado == "procesando").update({models.AnalysisJob.estado: "pendiente", models.AnalysisJob.iniciado_en: None}, synchronize_session=False)
        db.commit()
    finally:
        db.close()
