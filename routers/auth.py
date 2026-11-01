"Login/logout y administracion basica de usuarios."
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

import models
import schemas
from core.auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    authenticate_user,
    get_current_user,
    hash_password,
    limpiar_login_fallidos,
    login_bloqueado,
    login_html,
    make_token,
    registrar_login_fallido,
    require_admin,
    revocar_sesiones,
    sesion_vigente,
    token_info,
    verify_password,
)
from database import get_db
from services import grupos

router = APIRouter()
API_ROLES = {"admin", "analista", "lector"}

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def limpiar_email_notificaciones(valor: str | None) -> str | None:
    email = str(valor or "").strip().lower()
    if not email:
        return None
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "correo de notificaciones inválido")
    return email


@router.get("/login", response_class=HTMLResponse)
def login_form():
    return HTMLResponse(login_html(), headers={"Cache-Control": "no-store"})


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "desconocida"
    try:
        form = await request.form()
    except Exception:
        # Formularios malformados (escáneres automáticos): no es un error del servidor.
        return HTMLResponse(login_html("No se pudo leer el formulario."), status_code=400, headers={"Cache-Control": "no-store"})
    email = str(form.get("email") or "").strip().lower()
    password = str(form.get("password") or "")
    # Freno por origen y también por cuenta: muchos orígenes distintos probando la misma
    # cuenta ya no esquivan el límite. Bloquea la cuenta 5 minutos, no la desactiva.
    cuenta = f"cuenta:{email}"
    if login_bloqueado(ip) or (email and login_bloqueado(cuenta)):
        return HTMLResponse(
            login_html("Demasiados intentos fallidos. Esperá unos minutos antes de volver a probar."),
            status_code=429,
            headers={"Cache-Control": "no-store"},
        )
    user = authenticate_user(db, email, password)
    if not user:
        registrar_login_fallido(ip)
        if email:
            registrar_login_fallido(cuenta)
        return HTMLResponse(login_html("Usuario o contraseña incorrectos"), status_code=401, headers={"Cache-Control": "no-store"})
    limpiar_login_fallidos(ip)
    limpiar_login_fallidos(cuenta)
    resp = RedirectResponse("/#/inicio", status_code=303)
    resp.set_cookie(COOKIE_NAME, make_token(user.id), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=True)
    return resp


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    # Salir invalida el token (no solo borra la cookie): una copia robada deja de valer.
    # Como el corte es por fecha de emisión, también cierra las otras sesiones de la cuenta.
    info = token_info(request.cookies.get(COOKIE_NAME))
    if info:
        user = db.get(models.Usuario, info[0])
        if user and sesion_vigente(user, info[1]):
            revocar_sesiones(user)
            db.commit()
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/api/me", response_model=schemas.UsuarioOut)
def me(user: models.Usuario = Depends(get_current_user)):
    return user


@router.patch("/api/me/notificaciones", response_model=schemas.UsuarioOut)
def actualizar_notificaciones(payload: schemas.UsuarioNotificacionesUpdate, user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    user.email_notificaciones = limpiar_email_notificaciones(payload.email_notificaciones)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/api/usuarios", response_model=list[schemas.UsuarioOut])
def listar_usuarios(_admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(models.Usuario).order_by(models.Usuario.email.asc()).all()


@router.post("/api/usuarios", response_model=schemas.UsuarioOut)
def crear_usuario(payload: schemas.UsuarioCreate, _admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(422, "email inválido")
    if payload.rol not in API_ROLES:
        raise HTTPException(422, "rol inválido")
    if len(payload.password) < 8:
        raise HTTPException(422, "la contraseña debe tener al menos 8 caracteres")
    if db.query(models.Usuario).filter(models.Usuario.email == email).first():
        raise HTTPException(409, "ya existe un usuario con ese email")
    user = models.Usuario(email=email, nombre=payload.nombre.strip() or email, password_hash=hash_password(payload.password), rol=payload.rol, activo=True,
                          grupo=grupos.normalizar(payload.grupo))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _registrar(db: Session, admin: models.Usuario, accion: str, resumen: str, usuario_id: int) -> None:
    from services import actividad as actividad_svc

    actividad_svc.registrar(db, usuario=admin, modulo="usuarios", accion=accion, resumen=resumen,
                            metadata={"usuario_afectado_id": usuario_id})


@router.patch("/api/usuarios/{usuario_id}", response_model=schemas.UsuarioOut)
def cambiar_estado_usuario(usuario_id: int, payload: schemas.UsuarioEstadoUpdate,
                           admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """Activa o desactiva un usuario. Desactivarlo cierra además todas sus sesiones."""
    user = db.get(models.Usuario, usuario_id)
    if not user:
        raise HTTPException(404, "usuario no encontrado")
    if user.id == admin.id and not payload.activo:
        raise HTTPException(409, "no podés desactivar tu propio usuario")
    user.activo = payload.activo
    if not payload.activo:
        revocar_sesiones(user)
    _registrar(db, admin, "usuario_activado" if payload.activo else "usuario_desactivado",
               "Usuario activado" if payload.activo else "Usuario desactivado y sus sesiones cerradas", user.id)
    db.commit()
    db.refresh(user)
    return user


@router.post("/api/usuarios/{usuario_id}/cerrar-sesiones", response_model=schemas.UsuarioOut)
def cerrar_sesiones_usuario(usuario_id: int, admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(models.Usuario, usuario_id)
    if not user:
        raise HTTPException(404, "usuario no encontrado")
    revocar_sesiones(user)
    _registrar(db, admin, "sesiones_cerradas", "Sesiones del usuario cerradas por administración", user.id)
    db.commit()
    db.refresh(user)
    return user


@router.post("/api/me/cerrar-sesiones")
def cerrar_mis_sesiones(user: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cierra la sesión en todos los dispositivos, incluido este."""
    revocar_sesiones(user)
    db.commit()
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.post("/api/me/password")
def cambiar_password(payload: schemas.CambioPassword, user: models.Usuario = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Cambia la contraseña y cierra las demás sesiones; esta sigue abierta con un token nuevo."""
    # Mismo freno que el login: con una cookie robada no se puede probar la contraseña sin límite.
    clave = f"cambio-password:{user.id}"
    if login_bloqueado(clave):
        raise HTTPException(429, "Demasiados intentos. Esperá unos minutos y volvé a probar.")
    if not verify_password(payload.actual, user.password_hash):
        registrar_login_fallido(clave)
        raise HTTPException(403, "la contraseña actual no es correcta")
    if len(payload.nueva) < 8:
        raise HTTPException(422, "la contraseña nueva debe tener al menos 8 caracteres")
    user.password_hash = hash_password(payload.nueva)
    revocar_sesiones(user)
    db.commit()
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE_NAME, make_token(user.id), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=True)
    return resp
