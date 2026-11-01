from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from core.auth import get_current_user
from database import get_db
from services import actividad as actividad_svc
from services import enrutamiento as enrutamiento_svc

router = APIRouter(tags=["decisiones"])

TIPOS_DECISION = {"pedir_contexto", "seguimiento", "cerrar", "escalar_formalmente", "sin_escalamiento"}


def _puede_decidir(user: models.Usuario, informe: models.Informe) -> bool:
    if user.rol == "lector":
        return False
    return bool(user.rol == "admin" or (informe.usuario_id is not None and informe.usuario_id == user.id))


@router.post("/devoluciones/{devolucion_id}/decision", response_model=schemas.DecisionOut)
def decidir(devolucion_id: int, payload: schemas.DecisionCreate, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Registra SIEMPRE la decisión del responsable -- escale o no escale -- para
    que quede trazabilidad de lo que el sistema detectó y de lo que el
    responsable humano decidió hacer con esa información."""
    devolucion = db.get(models.Devolucion, devolucion_id)
    if not devolucion:
        raise HTTPException(404, "devolución no encontrada")
    if devolucion.decision:
        raise HTTPException(409, "esta devolución ya tiene una decisión registrada")

    informe = devolucion.informe
    if not _puede_decidir(user, informe):
        raise HTTPException(403, "sin permiso para decidir sobre esta devolución")

    tipo_decision = payload.tipo_decision or ("escalar_formalmente" if payload.escalar else "sin_escalamiento")
    if tipo_decision not in TIPOS_DECISION:
        raise HTTPException(422, "tipo_decision inválido")
    escalar = bool(payload.escalar or tipo_decision == "escalar_formalmente")

    try:
        seleccion_ids = list(dict.fromkeys(int(x) for x in (payload.hallazgo_ids or [])))
    except (TypeError, ValueError):
        raise HTTPException(422, "hallazgo_ids debe ser una lista de IDs")
    ids_validos = {h.id for h in informe.hallazgos}
    desconocidos = sorted(set(seleccion_ids) - ids_validos)
    if desconocidos:
        raise HTTPException(422, f"hallazgos no pertenecen al informe: {desconocidos}")

    hallazgos_seleccionados = [
        h for h in informe.hallazgos
        if not seleccion_ids or h.id in seleccion_ids
    ]
    hallazgo_ids_guardados = seleccion_ids or [h.id for h in hallazgos_seleccionados]

    decision = models.DecisionDirector(
        devolucion_id=devolucion.id,
        escalar=escalar,
        tipo_decision=tipo_decision,
        pregunta_institucional=payload.pregunta_institucional,
        hallazgo_ids=hallazgo_ids_guardados,
        comentario=payload.comentario,
        decidido_por=user.email,  # la autoría sale de la sesión, nunca del pedido
    )
    db.add(decision)
    db.flush()

    if escalar:
        hallazgos = hallazgos_seleccionados
        if not hallazgos:
            raise HTTPException(422, "no hay hallazgos seleccionados para escalar")
        if payload.areas_destino_ids:
            areas_destino = db.query(models.Area).filter(models.Area.id.in_(payload.areas_destino_ids)).all()
            if len(areas_destino) != len(set(payload.areas_destino_ids)):
                raise HTTPException(404, "una o más áreas destino no existen")
        else:
            areas_destino = [informe.area]

        documentos = enrutamiento_svc.generar_documentos(
            informe, hallazgos, areas_destino, payload.comentario, user.email
        )
        for doc in documentos:
            db.add(models.DocumentoEnrutamiento(decision_id=decision.id, **doc))

    actividad_svc.registrar(
        db,
        usuario=user,
        modulo="multilente",
        accion="decision_humana_registrada",
        resumen="Decision humana registrada sobre una devolucion",
        informe_id=getattr(informe, "id", None),
        metadata={"tipo_decision": tipo_decision, "escalar": escalar, "hallazgos": len(hallazgo_ids_guardados)},
    )
    db.commit()
    db.refresh(decision)
    return decision
