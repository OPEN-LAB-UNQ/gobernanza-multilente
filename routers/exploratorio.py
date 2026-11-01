"""Router propio de la capa exploratoria.

Deliberadamente separado de routers/certificaciones.py: la capa exploratoria
tiene su propia pantalla (ver static/exploratorio.html), no aparece como
pestaña ni como bloque del reporte multilente, y no la toca ningun endpoint
de certificacion. Acceso restringido a usuarios habilitados, como el resto
de la carga -- nada de esto es visible en la pagina publica de verificacion.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from core.auth import get_current_user
from database import get_db
from services import actividad as actividad_svc
from services import cuota_ia, exploratorio

router = APIRouter(prefix="/exploratorio", tags=["exploratorio"])


def _puede_ver_informe(user: models.Usuario, informe: models.Informe) -> bool:
    return bool(user.rol == "admin" or (informe.usuario_id is not None and informe.usuario_id == user.id))


def _informe_habilitado(informe_id: int, db: Session, usuario: models.Usuario) -> models.Informe:
    if usuario.rol == "lector":
        raise HTTPException(403, "el rol lector no accede a la capa exploratoria")
    informe = db.get(models.Informe, informe_id)
    if not informe:
        raise HTTPException(404, "informe no encontrado")
    if not _puede_ver_informe(usuario, informe):
        raise HTTPException(403, "sin permiso para ver este informe")
    return informe


def _hipotesis_publica(h: models.HipotesisExploratoria, corrida: int | None = None) -> dict:
    salida = {
        "id": h.id,
        "tipo_pista": h.tipo_pista,
        "texto_hipotesis": h.texto_hipotesis,
        "modelo": h.modelo,
        "version_modelo": h.version_modelo,
        "estado": h.estado,
        "creado_en": h.creado_en,
    }
    if corrida is not None:
        salida["corrida"] = corrida
    return salida


@router.get("/informes/{informe_id}")
def listar_hipotesis(
    informe_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    informe = _informe_habilitado(informe_id, db, usuario)
    hipotesis = exploratorio.listar_hipotesis(db, informe.id)
    corridas = exploratorio.agrupar_corridas(hipotesis)
    numero = {h.id: c["corrida"] for c in corridas for h in c["hipotesis"]}
    return {
        "rotulo_experimental": exploratorio.ROTULO_EXPERIMENTAL,
        "informe_id": informe.id,
        "hipotesis": [_hipotesis_publica(h, numero.get(h.id)) for h in hipotesis],
        # Cada corrida por separado: dos generaciones no se mezclan en una lista.
        "corridas": [
            {"corrida": c["corrida"], "creado_en": c["creado_en"], "cantidad": c["cantidad"],
             "hipotesis": [_hipotesis_publica(h, c["corrida"]) for h in c["hipotesis"]]}
            for c in corridas
        ],
    }


@router.post("/informes/{informe_id}/generar")
def generar_hipotesis(
    informe_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    informe = _informe_habilitado(informe_id, db, usuario)
    cuota_ia.verificar_exploracion(db, usuario)
    # Se registra antes de llamar a la IA: cuenta para el tope aunque la llamada falle.
    evento = actividad_svc.registrar(
        db, usuario=usuario, modulo="multilente", accion="exploracion_generada",
        resumen="Exploración con IA solicitada", informe_id=informe.id, metadata={},
    )
    db.commit()
    resultado = exploratorio.generar_para_informe_detallado(db, informe)
    guardadas, errores, avisos = resultado["guardadas"], resultado["errores"], resultado["avisos"]
    evento.metadata_evento = {"hipotesis": len(guardadas), "errores": len(errores), "avisos": len(avisos)}
    db.commit()
    return {
        "rotulo_experimental": exploratorio.ROTULO_EXPERIMENTAL,
        "informe_id": informe.id,
        # Sólo esta corrida; las anteriores se consultan agrupadas en el GET.
        "hipotesis": [_hipotesis_publica(h) for h in guardadas],
        "errores": errores,
        "avisos": avisos,
    }
