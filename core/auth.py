"Autenticacion por usuarios con cookie firmada."
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import re
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
from config import settings
from database import SessionLocal, get_db

APP_PASSWORD = settings.gobernanza_password
COOKIE_NAME = "gobernanza_auth"
COOKIE_MAX_AGE = 60 * 60 * 12
SECRET = settings.secret_key
PBKDF2_ITERATIONS = 260_000


def _sign(payload: str) -> str:
    return hmac.new(SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        metodo, iteraciones, salt, digest = stored.split("$", 3)
        if metodo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iteraciones)).hex()
        return hmac.compare_digest(calc, digest)
    except Exception:
        return False


def make_token(user_id: int) -> str:
    # En milisegundos: un token y un cierre de sesiones del mismo segundo no quedan empatados.
    issued = str(int(time.time() * 1000))
    payload = f"{user_id}.{issued}"
    return f"{payload}.{_sign(payload)}"


def token_info(token: Optional[str]) -> tuple[int, int] | None:
    """(usuario, emitido en milisegundos) de un token con firma válida y no vencido."""
    if not token or token.count(".") != 2:
        return None
    user_id_s, issued_s, sig = token.split(".", 2)
    payload = f"{user_id_s}.{issued_s}"
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        issued = int(issued_s)
        user_id = int(user_id_s)
    except ValueError:
        return None
    if issued < 10**11:  # tokens emitidos antes del 29/09/2026, en segundos
        issued *= 1000
    if (time.time() - issued / 1000) > COOKIE_MAX_AGE:
        return None
    return user_id, issued


def token_user_id(token: Optional[str]) -> int | None:
    info = token_info(token)
    return info[0] if info else None


def sesion_vigente(user, issued: int) -> bool:
    """El usuario está activo y el token se emitió después del último cierre de sesiones."""
    if not user or not user.activo:
        return False
    desde = getattr(user, "sesiones_desde", None)
    if desde is None:
        return True
    return issued >= int(desde.replace(tzinfo=_dt.timezone.utc).timestamp() * 1000)


def revocar_sesiones(user) -> None:
    """Invalida todas las sesiones abiertas del usuario (las nuevas siguen valiendo)."""
    user.sesiones_desde = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


def valid_token(token: Optional[str]) -> bool:
    return token_user_id(token) is not None


def active_token(token: Optional[str]) -> bool:
    """Valida firma, vencimiento y vigencia actual del usuario."""
    info = token_info(token)
    if info is None:
        return False
    db = SessionLocal()
    try:
        return sesion_vigente(db.get(models.Usuario, info[0]), info[1])
    finally:
        db.close()


# Limite basico de intentos de login por IP -- proceso unico (un solo worker
# uvicorn), asi que el estado en memoria alcanza sin necesitar Redis ni tabla
# aparte. No es proteccion de nivel produccion contra IPs rotativas, pero
# frena fuerza bruta trivial contra un mismo origen.
_login_intentos_fallidos: dict[str, list[float]] = {}
LOGIN_MAX_INTENTOS = 8
LOGIN_VENTANA_SEGUNDOS = 300  # 5 minutos


def login_bloqueado(ip: str) -> bool:
    ahora = time.time()
    intentos = [t for t in _login_intentos_fallidos.get(ip, []) if ahora - t < LOGIN_VENTANA_SEGUNDOS]
    _login_intentos_fallidos[ip] = intentos
    return len(intentos) >= LOGIN_MAX_INTENTOS


def registrar_login_fallido(ip: str) -> None:
    ahora = time.time()
    intentos = [t for t in _login_intentos_fallidos.get(ip, []) if ahora - t < LOGIN_VENTANA_SEGUNDOS]
    intentos.append(ahora)
    _login_intentos_fallidos[ip] = intentos


def limpiar_login_fallidos(ip: str) -> None:
    _login_intentos_fallidos.pop(ip, None)


def seed_initial_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(models.Usuario).first():
            return
        password = settings.admin_password or APP_PASSWORD
        admin = models.Usuario(
            email=settings.admin_email.lower(),
            nombre=settings.admin_name,
            password_hash=hash_password(password),
            rol="admin",
            activo=True,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()


def authenticate_user(db: Session, email: str, password: str) -> models.Usuario | None:
    if not email:
        return None
    user = db.query(models.Usuario).filter(
        models.Usuario.activo.is_(True),
        models.Usuario.email == email.lower(),
    ).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def current_user_from_request(request: Request, db: Session) -> models.Usuario | None:
    info = token_info(request.cookies.get(COOKIE_NAME))
    if info is None:
        return None
    user = db.get(models.Usuario, info[0])
    return user if sesion_vigente(user, info[1]) else None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    user = current_user_from_request(request, db)
    if not user:
        raise HTTPException(401, "no autenticado")
    return user


def require_admin(user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    if user.rol != "admin":
        raise HTTPException(403, "requiere rol admin")
    return user


def login_html(error: str = "") -> str:
    error_html = f'<div class="error">{error}</div>' if error else ""
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Gobernanza Multilente · acceso</title>
  <style>
    @font-face {{ font-family: "Gobernanza Inter"; src: url("/fonts/inter-variable-v4.woff2") format("woff2"); font-style: normal; font-weight: 100 900; font-display: swap; }}
    :root {{ color-scheme: light; font-family: "Gobernanza Inter", Inter, Arial, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      overflow: hidden;
      background:
        radial-gradient(circle at 20% 18%, rgba(48, 106, 166, .10), transparent 28%),
        radial-gradient(circle at 82% 76%, rgba(192, 137, 44, .13), transparent 26%),
        linear-gradient(135deg, #faf7f7 0%, #f6efef 100%);
      color: #2e292a;
    }}
    body::before,
    body::after {{
      content: "";
      position: fixed;
      width: 520px;
      height: 520px;
      border-radius: 50%;
      border: 1px solid rgba(176, 28, 46, .14);
      pointer-events: none;
    }}
    body::before {{ left: -160px; top: -190px; box-shadow: 90px 80px 0 -34px rgba(192, 137, 44, .10); }}
    body::after {{ right: -170px; bottom: -210px; box-shadow: -110px -70px 0 -40px rgba(176, 28, 46, .10); }}
    .lens-field {{
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .9;
    }}
    .ring {{
      position: absolute;
      border-radius: 50%;
      border: 1.5px solid rgba(176, 28, 46, .18);
    }}
    .ring.gold {{ border-color: rgba(192, 137, 44, .28); }}
    .ring.one {{ width: 170px; height: 170px; left: 13%; top: 27%; }}
    .ring.two {{ width: 116px; height: 116px; left: calc(13% + 86px); top: calc(27% + 24px); }}
    .ring.three {{ width: 210px; height: 210px; right: 16%; top: 20%; }}
    .ring.four {{ width: 132px; height: 132px; right: calc(16% + 104px); top: calc(20% + 48px); }}
    main {{
      position: relative;
      width: min(92vw, 478px);
      background: rgba(255, 255, 255, .92);
      border: 1px solid rgba(217, 224, 231, .95);
      border-radius: 16px;
      padding: 34px 34px 30px;
      box-shadow: 0 28px 80px rgba(22, 32, 51, .16);
      backdrop-filter: blur(8px);
    }}
    .brand-row {{ display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }}
    .brand-mark {{
      width: 48px;
      height: 48px;
      display: grid;
      place-items: center;
      border-radius: 14px;
      background: linear-gradient(160deg, #234f79 0%, #b01c2e 60%, #1b4468 100%);
      box-shadow:
        inset 0 1px 0 rgba(255,255,255,.16),
        inset 0 0 0 1px rgba(255,255,255,.12),
        0 12px 28px rgba(176, 28, 46,.24);
    }}
    h1 {{ margin: 0 0 5px; font-size: 25px; line-height: 1.15; letter-spacing: 0; }}
    p {{ margin: 0; color: #5b6675; line-height: 1.45; }}
    .intro {{ margin-bottom: 22px; }}
    label {{ display: block; font-size: 13px; font-weight: 800; margin: 14px 0 8px; }}
    input {{
      width: 100%;
      height: 46px;
      border: 1px solid #cdbfc1;
      border-radius: 10px;
      padding: 0 13px;
      font-size: 16px;
      background: #fbf8f8;
      color: #2e292a;
      outline: none;
      transition: border-color .16s ease, box-shadow .16s ease, background .16s ease;
    }}
    input:focus {{
      background: white;
      border-color: #b01c2e;
      box-shadow: 0 0 0 4px rgba(176, 28, 46, .13);
    }}
    button {{
      width: 100%;
      margin-top: 18px;
      height: 48px;
      border: 0;
      border-radius: 10px;
      background: #b01c2e;
      color: white;
      font-weight: 800;
      cursor: pointer;
      box-shadow: 0 10px 24px rgba(176, 28, 46, .22);
    }}
    button:hover {{ background: #183f63; }}
    .error {{ margin-bottom: 14px; padding: 10px 12px; border-radius: 8px; background: #fff0f0; color: #9b1c1c; font-size: 13px; }}
    .hint {{ margin-top: 12px; font-size: 12px; color: #62595b; }}
    .access-note {{
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid #ece3e4;
      color: #62595b;
      font-size: 12px;
      line-height: 1.45;
    }}
    .learn-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      min-height: 42px;
      margin-top: 14px;
      border: 1px solid #dccfd1;
      border-radius: 9px;
      color: #b01c2e;
      background: #fbf8f8;
      font-size: 14px;
      font-weight: 800;
      text-decoration: none;
    }}
    .learn-link:hover {{ background: #f6efef; border-color: #9cabb9; }}
    .learn-link:focus-visible {{ outline: 3px solid rgba(176, 28, 46, .18); outline-offset: 2px; }}
    .privacidad-link {{ margin: 14px 0 0; text-align: center; font-size: 12px; }}
    .privacidad-link a {{ color: #62595b; }}
    @media (max-width: 640px) {{
      body {{ overflow: auto; padding: 22px 0; }}
      main {{ padding: 26px 22px 24px; }}
      .ring.one, .ring.two, .ring.three, .ring.four {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="lens-field" aria-hidden="true">
    <span class="ring one"></span>
    <span class="ring two gold"></span>
    <span class="ring three gold"></span>
    <span class="ring four"></span>
  </div>
  <main>
    <div class="brand-row">
      <div class="brand-mark">
        <svg viewBox="0 0 40 40" width="30" height="30" aria-hidden="true">
          <defs>
            <radialGradient id="lensLoginA" cx="35%" cy="30%" r="75%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity=".18"/>
              <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
            </radialGradient>
            <radialGradient id="lensLoginB" cx="35%" cy="30%" r="75%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity=".3"/>
              <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
            </radialGradient>
            <radialGradient id="lensLoginGold" cx="35%" cy="30%" r="75%">
              <stop offset="0%" stop-color="#c0892c" stop-opacity=".22"/>
              <stop offset="100%" stop-color="#c0892c" stop-opacity="0"/>
            </radialGradient>
            <filter id="lensLoginShadow" x="-50%" y="-50%" width="200%" height="200%">
              <feDropShadow dx="0" dy=".4" stdDeviation=".4" flood-color="#0b1f33" flood-opacity=".18"/>
            </filter>
          </defs>
          <circle cx="15.5" cy="16" r="9" fill="url(#lensLoginA)" stroke="rgba(255,255,255,0.48)" stroke-width="1.6" filter="url(#lensLoginShadow)"/>
          <circle cx="24.5" cy="16" r="9" fill="url(#lensLoginB)" stroke="rgba(255,255,255,0.9)" stroke-width="1.6" filter="url(#lensLoginShadow)"/>
          <circle cx="20" cy="24" r="9" fill="url(#lensLoginGold)" stroke="#c0892c" stroke-width="1.8" filter="url(#lensLoginShadow)"/>
        </svg>
      </div>
      <div>
        <h1>Gobernanza Multilente</h1>
        <p>Una segunda lectura antes de decidir</p>
      </div>
    </div>
    <p class="intro">Lleva los principios de gobernanza a algo que se puede comprobar. Ingresá para revisar informes o continuar tu proyecto.</p>
    {error_html}
    <form method="post" action="/login">
      <label for="email">Usuario</label>
      <input id="email" name="email" type="text" autocomplete="username" autofocus />
      <label for="password">Contraseña</label>
      <input id="password" name="password" type="password" autocomplete="current-password" />
      <button type="submit">Entrar</button>
    </form>
    <div class="access-note"><strong>¿Venís de la cursada?</strong><br>Adentro vas a encontrar Multilente, la Incubadora, Conexiones y el seguimiento de proyectos.</div>
    <a class="learn-link" href="/presentacion">Conocer Gobernanza Multilente</a>
    <p class="privacidad-link"><a href="/privacidad">Privacidad, cookies y aviso legal</a></p>
    <a class="learn-link" href="/probar.html">Probar informes predefinidos sin clave</a>
  </main>
</body>
</html>"""


METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def origen_confiable(headers) -> bool:
    """Un pedido que modifica datos sólo se acepta desde la propia app.

    La cookie es samesite=lax, pero los otros sitios *.entornodepruebas.com.ar del mismo
    servidor cuentan como «mismo sitio» y el navegador se la manda: sin este control podían
    disparar acciones con la sesión de quien los visita (CSRF entre subdominios). Los
    navegadores siempre envían Origin en un POST/PATCH/DELETE; los clientes sin navegador
    (tests, scripts del servidor) no lo envían y no corren con la cookie de nadie.
    """
    origen = (headers.get("origin") or "").rstrip("/")
    if origen:
        if origen == settings.public_base_url.rstrip("/"):
            return True
        return bool(re.fullmatch(r"https?://(?:127\.0\.0\.1|localhost)(?::\d+)?", origen))
    sitio = (headers.get("sec-fetch-site") or "").lower()
    return sitio in {"", "same-origin", "none"}


async def require_password_middleware(request, call_next):
    from fastapi.responses import JSONResponse, RedirectResponse

    path = request.url.path
    if request.method not in METODOS_SEGUROS and not origen_confiable(request.headers):
        return JSONResponse({"detail": "origen no permitido"}, status_code=403)
    public_paths = {
        "/login",
        "/logout",
        "/api/health",
        "/favicon.ico",
        "/robots.txt",
        "/sitemap.xml",
        "/presentacion",
        "/detalle",
        "/multilente",
        "/privacidad",
        "/probar.html",
        "/probar.js",
        "/errores.js",
        "/api/ejemplos/publicos",
        "/presentacion-nav.js",
        "/presentacion-theme.js",
        "/presentacion-faq.js",
        "/presentacion-video.js",
        "/charla-filminas.js",
        "/hero-revision-institucional.png",
        "/hero-revision-institucional-sin-bandera.jpg",
        "/fonts/inter-variable-v4.woff2",
        "/fonts/Inter-OFL.txt",
    }
    ejemplo_publico = re.fullmatch(r"/api/ejemplos/publicos/[1-8]/(?:zip|(?:sin|con)\.(?:pdf|xlsx))", path)
    if path in public_paths or ejemplo_publico or path.startswith("/verificar-sello/"):
        return await call_next(request)
    if active_token(request.cookies.get(COOKIE_NAME)):
        return await call_next(request)
    if path.startswith("/api"):
        return JSONResponse({"detail": "no autenticado"}, status_code=401)
    return RedirectResponse("/login", status_code=303)
