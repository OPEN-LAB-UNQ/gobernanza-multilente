"""Revisión de lectura de PDF e imágenes con las cuentas y permisos existentes.

Los PDF y las imágenes no se analizan directo: acá la persona ve el original al lado de la tabla
leída, corrige y confirma; recién después la tabla se envía a /api/analisis-rapido como CSV.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from core.auth import get_current_user
from services import ocr_local

router = APIRouter(prefix="/ocr", tags=["Lectura OCR"])


def permiso(user=Depends(get_current_user)):
    if user.rol not in ("admin", "analista"):
        raise HTTPException(403, "La lectura OCR requiere rol admin o analista.")
    return user


@router.get("", response_class=HTMLResponse)
def pagina(user=Depends(permiso)):
    return (Path(__file__).resolve().parents[1] / "static/ocr.html").read_text(encoding="utf-8")


@router.post("/leer")
async def leer(archivo: UploadFile = File(...), paginas: Optional[str] = Form(None), user=Depends(permiso)):
    try:
        elegidas = [p for p in (paginas or "").replace(";", ",").split(",") if p.strip()] or None
        contenido = await archivo.read(ocr_local.MAX_BYTES + 1)
        return await run_in_threadpool(ocr_local.extraer, archivo.filename or "", contenido, elegidas)
    except ocr_local.OCRNoDisponible as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(
            422, "No se pudo abrir el archivo. Comprobá que sea una imagen o PDF válido y sin contraseña."
        )
    finally:
        await archivo.close()
