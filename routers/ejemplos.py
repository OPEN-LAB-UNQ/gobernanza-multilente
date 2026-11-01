"""Descarga conjunta de ejemplos del catálogo y sus reportes reales ya analizados."""
from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from core.auth import get_current_user
from database import get_db
from routers.informes import _puede_ver, descargar_reporte_seleccionado
from services import jobs, proveniencia

router = APIRouter(prefix="/ejemplos", tags=["ejemplos"])
SAMPLES = Path(__file__).resolve().parents[1] / "static" / "samples"
PUBLIC_SAMPLES = SAMPLES.parent / "public-samples"


class ParInformes(BaseModel):
    sin_senal: int = Field(..., gt=0, strict=True)
    con_senal: int = Field(..., gt=0, strict=True)


def _archivos_caso(caso: int):
    catalogo = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    par = [item for item in catalogo if item.get("orden") == caso]
    if len(par) != 2 or {item.get("columna") for item in par} != {"bueno", "malo"}:
        raise HTTPException(404, "par de ejemplos no disponible")
    result = {}
    for item in par:
        ruta = str(item["archivo"])
        nombre = ruta.removeprefix("/samples/")
        path = SAMPLES / nombre
        if (not ruta.startswith("/samples/") or Path(nombre).name != nombre
                or path.resolve().parent != SAMPLES.resolve() or not path.is_file()):
            raise HTTPException(409, "archivo de ejemplo no disponible")
        result[item["columna"]] = (path.name, path.read_bytes())
    return result


@router.get("/publicos")
def catalogo_publico():
    """Sólo expone metadatos de los ejemplos sintéticos, nunca informes privados."""
    catalogo = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    casos = []
    for orden in sorted({item["orden"] for item in catalogo}):
        par = {item["columna"]: item for item in catalogo if item["orden"] == orden}
        if set(par) != {"bueno", "malo"} or not (PUBLIC_SAMPLES / f"caso-{orden}.zip").is_file():
            continue
        casos.append({
            "orden": orden,
            "titulo": par["bueno"]["caso"],
            "tema": par["bueno"]["tema"],
            "sin_senal": {"nombre": par["bueno"]["nombre"], "descripcion": par["bueno"]["descripcion"]},
            "con_senal": {"nombre": par["malo"]["nombre"], "descripcion": par["malo"]["descripcion"]},
        })
    return {"casos": casos, "modo": "resultados_precalculados", "nuevas_cargas_requieren_clave": True}


def _zip_publico(caso: int) -> bytes:
    # Nunca acepta ids de informes, rutas ni nombres aportados por el cliente.
    if caso not in range(1, 9):
        raise HTTPException(404, "caso público no disponible")
    path = PUBLIC_SAMPLES / f"caso-{caso}.zip"
    if not path.is_file():
        raise HTTPException(404, "caso público no disponible")
    return path.read_bytes()


@router.get("/publicos/{caso}/zip")
def descargar_caso_publico(caso: int):
    return Response(
        content=_zip_publico(caso), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="ejemplos-caso-{caso}.zip"', "Cache-Control": "no-store"},
    )


@router.get("/publicos/{caso}/{lado}.{formato}")
def archivo_caso_publico(caso: int, lado: str, formato: str):
    if lado not in {"sin", "con"} or formato not in {"pdf", "xlsx"}:
        raise HTTPException(404, "archivo público no disponible")
    numero = {("sin", "xlsx"): "01", ("sin", "pdf"): "02", ("con", "xlsx"): "03", ("con", "pdf"): "04"}[(lado, formato)]
    extension = "original" if formato == "xlsx" else "reporte"
    etiqueta = "sin-senal-esperada" if lado == "sin" else "con-senal-esperada"
    nombre = f"{numero}-{extension}-{etiqueta}.{formato}"
    with ZipFile(BytesIO(_zip_publico(caso))) as z:
        try:
            contenido = z.read(nombre)
        except KeyError as exc:
            raise HTTPException(404, "archivo público no disponible") from exc
    tipo = "application/pdf" if formato == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    disposicion = "inline" if formato == "pdf" else "attachment"
    return Response(
        content=contenido, media_type=tipo,
        headers={"Content-Disposition": f'{disposicion}; filename="{nombre}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{caso}/zip")
def descargar_par(
    caso: int,
    payload: ParInformes,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(get_current_user),
):
    if user.rol not in {"admin", "analista"}:
        raise HTTPException(403, "este recorrido requiere rol admin o analista")
    if payload.sin_senal == payload.con_senal:
        raise HTTPException(422, "se necesitan dos informes diferentes")
    archivos = _archivos_caso(caso)
    verificados = []
    for lado, informe_id, etiqueta in [
        ("bueno", payload.sin_senal, "sin-senal-esperada"),
        ("malo", payload.con_senal, "con-senal-esperada"),
    ]:
        informe = db.get(models.Informe, informe_id)
        if not informe or not _puede_ver(user, informe):
            raise HTTPException(404, "informe no disponible")
        trabajo = jobs.latest_job(db, informe.id)
        if not trabajo or trabajo.estado != "finalizado" or not informe.devolucion:
            raise HTTPException(409, "ambos análisis deben terminar correctamente antes de descargar")
        nombre, contenido = archivos[lado]
        origen = (informe.saneamiento or {}).get("proveniencia") or {}
        fuentes = origen.get("fuentes") or []
        if (len(fuentes) != 1 or fuentes[0].get("nombre_original") != nombre
                or fuentes[0].get("sha256_bruto") != hashlib.sha256(contenido).hexdigest()
                or origen.get("sha256_procesado") != proveniencia.huella(informe.datos or [])):
            raise HTTPException(409, "el informe no corresponde al original de este ejemplo; ejecutá nuevamente el par")
        verificados.append((informe, nombre, contenido, etiqueta))

    # Valida el par completo antes de generar cualquiera de las descargas.
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archivo_zip:
        for index, (informe, nombre, contenido, etiqueta) in enumerate(verificados):
            base = index * 2 + 1
            archivo_zip.writestr(f"{base:02}-original-{etiqueta}{Path(nombre).suffix}", contenido)
            reporte = descargar_reporte_seleccionado(
                informe.id, {"formato": "pdf"}, db=db, user=user,
            )
            archivo_zip.writestr(f"{base + 1:02}-reporte-{etiqueta}.pdf", reporte.body)
    return Response(
        content=buffer.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="ejemplos-caso-{caso}.zip"',
                 "Cache-Control": "no-store"},
    )
