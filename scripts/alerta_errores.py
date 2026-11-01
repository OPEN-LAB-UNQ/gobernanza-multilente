#!/usr/bin/env python3
"""Alerta por email cuando gobernanza.service devuelve errores 500, falla un análisis
en segundo plano, aparece un traceback (avisado según su origen) o el servicio deja de estar activo.

Pensado para correr via cron cada 10-15 min. Guarda en VAR_DIR la marca de
tiempo del ultimo chequeo para no reenviar los mismos errores dos veces.
No reemplaza revisar journalctl a mano: solo evita que un bug de produccion
pase horas sin que nadie se entere (fue lo que paso el 2026-09-06 con el
bug de modo_uso_multilente).
"""
from __future__ import annotations

import re
import smtplib
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import models  # noqa: E402
from config import settings  # noqa: E402
from database import SessionLocal  # noqa: E402
from services.notificaciones import smtp_configurado  # noqa: E402

SERVICIO = "gobernanza.service"
VAR_DIR = RAIZ / "var"
ESTADO_PATH = VAR_DIR / "alerta_errores_ultimo_chequeo"
PATRON_500 = re.compile(r'"\w+ \S+ HTTP/\d\.\d" 500\b')
# Un análisis que falla en el worker no produce un 500: deja este registro, con el informe y el trabajo.
PATRON_WORKER = re.compile(r"fallo el analisis del informe")
# Los demás tracebacks se avisan según su origen. Antes cualquiera contaba como análisis fallido: el 27/10/2026 un
# arranque con la base todavía levantándose llegó como «fallaron análisis en segundo plano».
PATRON_TRACEBACK = re.compile(r"Traceback \(most recent call last\)")
# Línea de journalctl: «Oct 27 11:14:31 host proceso[pid]: mensaje» (el mensaje puede venir vacío).
_LINEA = re.compile(r"^(?P<cuando>\w+ +\d+ [\d:]+) \S+ (?P<proceso>[^\s\[:]+)(?:\[\d+\])?:(?: (?P<mensaje>.*))?$")
_ENCADENADA = ("During handling of the above exception", "The above exception was the direct cause")
# Lo que el proceso escribe antes de un traceback que ya tiene su propio aviso: el análisis fallido (con su número de
# trabajo) y el 500 (uvicorn escribe «Exception in ASGI application» y el 500 queda en el registro de accesos).
_YA_AVISADO = (("analisis", PATRON_WORKER), ("http", re.compile(r"Exception in ASGI application")))
_NIVEL = re.compile(r"^(INFO|WARNING|ERROR|DEBUG|CRITICAL):")
_BASE = re.compile(r"OperationalError|InterfaceError|database system is starting up|connection to server|could not connect")
_PROVEEDOR = re.compile(r"site-packages/(httpx|httpcore|openai|anthropic|google|vertexai)/"
                        r"|\b(httpx|httpcore|openai|anthropic|google\.[\w.]+)\.\w*(Error|Exception|Timeout)")
ORIGENES = {
    "arranque": ("Gobernanza: el servicio falló al arrancar",
                 "El servicio no pudo arrancar (migraciones o primera conexión con la base):"),
    "base": ("Gobernanza: errores de conexión con la base", "Errores de conexión con la base de datos:"),
    "proveedor": ("Gobernanza: errores de proveedores de IA", "Errores en llamadas a proveedores de IA:"),
    "otro": ("Gobernanza: errores en el servicio",
             "Errores con traceback que no son de un análisis, del arranque, de la base ni de un proveedor:"),
}
CAIDA_PATH = VAR_DIR / "alerta_servicio_caido"
# El backup diario corre a la madrugada: más de 26 h sin un dump nuevo es que falló.
BACKUP_DIR = RAIZ / "backups" / "db"
BACKUP_PATRON = "gobernanza-*.dump"
BACKUP_MAX_HORAS = 26
BACKUP_ALERTA_PATH = VAR_DIR / "alerta_backup_viejo"
FMT = "%Y-%m-%d %H:%M:%S"


def _ultimo_chequeo(ahora: datetime) -> str:
    if ESTADO_PATH.exists():
        return ESTADO_PATH.read_text().strip()
    return "-15min"


def _journal_entre(desde: str, hasta: str) -> str:
    cmd = ["journalctl", "-u", SERVICIO, "--no-pager", "-S", desde, "-U", hasta]
    resultado = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return resultado.stdout


def _extraer_500(texto: str) -> list[str]:
    return [linea.strip() for linea in texto.splitlines() if PATRON_500.search(linea)]


def _extraer_fallos_worker(texto: str) -> list[str]:
    return [linea.strip() for linea in texto.splitlines() if PATRON_WORKER.search(linea)]


def _tracebacks(texto: str) -> list[dict]:
    """Cada traceback del registro: hora, proceso, sus excepciones y si ya tiene su propio aviso."""
    bloques: list[dict] = []
    abiertos: dict[str, dict] = {}  # proceso → bloque que todavía no llegó a la línea de la excepción
    cerrados: dict[str, dict] = {}  # proceso → último bloque cerrado, por si sigue una excepción encadenada
    encadenadas: set[str] = set()
    avisado: dict[str, str] = {}  # proceso → aviso propio que corresponde a su próximo traceback
    for n, cruda in enumerate(texto.splitlines()):
        m = _LINEA.match(cruda)
        if not m:
            continue
        proceso, mensaje = m["proceso"], m["mensaje"] or ""
        if PATRON_TRACEBACK.search(mensaje):
            if proceso in encadenadas and proceso not in abiertos:
                # «The above exception…»: es la misma falla y vale la última excepción.
                encadenadas.discard(proceso)
                abiertos[proceso] = cerrados[proceso]
                continue
            # Si había uno abierto, quedó cortado (por la ventana o por journald) y no se traga a este.
            abiertos.pop(proceso, None)
            bloque = dict(cuando=m["cuando"], proceso=proceso, errores=[], lineas=[], linea=n,
                          avisado=avisado.pop(proceso, ""))
            bloques.append(bloque)
            abiertos[proceso] = bloque
            continue
        bloque = abiertos.get(proceso)
        if bloque is not None and _NIVEL.match(mensaje):
            del abiertos[proceso]  # una línea de registro corriente: el traceback quedó cortado
            bloque = None
        if bloque is None:
            if mensaje.startswith(_ENCADENADA) and proceso in cerrados:
                encadenadas.add(proceso)
            elif mensaje.strip():
                encadenadas.discard(proceso)
            # La marca vale hasta el próximo traceback: el mensaje de la excepción puede ocupar varias líneas.
            for origen, patron in _YA_AVISADO:
                if patron.search(mensaje):
                    avisado[proceso] = origen
            continue
        bloque["lineas"].append(mensaje)
        if mensaje and not mensaje[0].isspace():
            bloque["errores"].append(mensaje.strip())  # la primera línea sin sangría es la excepción
            cerrados[proceso] = abiertos.pop(proceso)
    return bloques


def _origen(bloque: dict) -> str:
    if bloque["avisado"]:
        return bloque["avisado"]
    if bloque["proceso"] == "alembic":
        return "arranque"
    if any(_BASE.search(error) for error in bloque["errores"]):  # también si otra excepción la envuelve
        return "base"
    if _PROVEEDOR.search("\n".join(bloque["lineas"])):
        return "proveedor"
    return "otro"


def _clasificar(texto: str) -> dict[str, list[str]]:
    """Tracebacks agrupados por origen, una línea cada uno, sin los que ya tienen aviso (análisis fallido o 500)."""
    por_origen: dict[str, list[str]] = {}
    arranques = []
    for bloque in _tracebacks(texto):
        origen = _origen(bloque)
        if origen in ("analisis", "http"):
            continue
        if origen == "arranque":
            arranques.append(bloque["linea"])
        error = bloque["errores"][-1] if bloque["errores"] else "(traceback cortado, sin la línea del error)"
        por_origen.setdefault(origen, []).append(f"{bloque['cuando']} {bloque['proceso']}: {error}"[:600])
    # Un traceback en una línea con otro formato no se pierde: se avisa tal cual, como antes.
    sueltos = [linea.strip()[:600] for linea in texto.splitlines()
               if PATRON_TRACEBACK.search(linea) and not _LINEA.match(linea)]
    if sueltos:
        por_origen.setdefault("otro", []).extend(sueltos)
    if arranques:
        # Importa si volvió después del último arranque fallido, no de uno anterior.
        volvio = [m["cuando"] for n, m in enumerate(map(_LINEA.match, texto.splitlines()))
                  if m and n > max(arranques) and "Application startup complete" in (m["mensaje"] or "")]
        por_origen["arranque"].append(f"Volvió a arrancar: {volvio[-1]}." if volvio
                                      else "No se vio que volviera a arrancar en esta ventana.")
    return por_origen


def _horas_desde_ultimo_backup(ahora: datetime, carpeta: Path = BACKUP_DIR) -> float | None:
    """Antigüedad del dump más nuevo, o None si no hay ninguno."""
    dumps = list(carpeta.glob(BACKUP_PATRON)) if carpeta.exists() else []
    if not dumps:
        return None
    ultimo = max(d.stat().st_mtime for d in dumps)
    return (ahora.timestamp() - ultimo) / 3600


def _servicio_activo() -> bool:
    resultado = subprocess.run(["systemctl", "is-active", SERVICIO], capture_output=True, text=True, check=False)
    return resultado.stdout.strip() == "active"


def _email_admin() -> str | None:
    """Destinatario fijo (ALERTAS_EMAIL en .env) o el primer admin con correo de avisos."""
    if settings.alertas_email:
        return settings.alertas_email
    db = SessionLocal()
    try:
        admin = (
            db.query(models.Usuario)
            .filter(models.Usuario.rol == "admin", models.Usuario.email_notificaciones.isnot(None))
            .order_by(models.Usuario.id)
            .first()
        )
        return admin.email_notificaciones if admin else None
    except Exception:  # noqa: BLE001 — si la base está caída, igual hay que poder avisar.
        return None
    finally:
        db.close()


def _enviar_alerta(lineas: list[str], asunto: str | None = None, intro: str | None = None) -> None:
    destinatario = _email_admin()
    smtp_host = settings.smtp_host
    if not destinatario or not smtp_host or not smtp_configurado():
        print("SMTP no configurado o sin admin_email; no se pudo enviar la alerta", file=sys.stderr)
        return
    msg = EmailMessage()
    msg["Subject"] = asunto or f"Gobernanza: {len(lineas)} error(es) 500 detectado(s)"
    msg["From"] = settings.smtp_from
    msg["To"] = destinatario
    cuerpo = (
        (intro or "Se detectaron los siguientes errores 500 en gobernanza.service:") + "\n\n"
        + "\n".join(lineas[:30])
    )
    if len(lineas) > 30:
        cuerpo += f"\n\n... y {len(lineas) - 30} mas. Revisar journalctl -u gobernanza para el detalle completo."
    msg.set_content(cuerpo)

    usa_ssl = bool(settings.smtp_ssl or int(settings.smtp_port) == 465)
    smtp_cm = (
        smtplib.SMTP_SSL(smtp_host, settings.smtp_port, timeout=20)
        if usa_ssl
        else smtplib.SMTP(smtp_host, settings.smtp_port, timeout=20)
    )
    with smtp_cm as smtp:
        if settings.smtp_tls and not usa_ssl:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


def main() -> None:
    ahora = datetime.now()
    hasta = ahora.strftime(FMT)
    desde = _ultimo_chequeo(ahora)
    texto = _journal_entre(desde, hasta)
    lineas = _extraer_500(texto)
    if lineas:
        print(f"{len(lineas)} error(es) 500 detectado(s), enviando alerta")
        _enviar_alerta(lineas)
    else:
        print("sin errores 500 en esta ventana")
    fallos = _extraer_fallos_worker(texto)
    if fallos:
        print(f"{len(fallos)} fallo(s) de análisis en segundo plano, enviando alerta")
        _enviar_alerta(fallos, "Gobernanza: fallaron análisis en segundo plano",
                       "Estos análisis terminaron con error en el worker (no generan un 500):")
    for origen, lineas in _clasificar(texto).items():
        print(f"{len(lineas)} línea(s) de origen {origen}, enviando alerta")
        _enviar_alerta(lineas, *ORIGENES[origen])
    VAR_DIR.mkdir(exist_ok=True)
    # Caída del servicio: una alerta al caer y otra al volver, no una cada 10 minutos.
    activo = _servicio_activo()
    if not activo and not CAIDA_PATH.exists():
        print("el servicio no está activo, enviando alerta")
        _enviar_alerta([f"{SERVICIO} no está activo ({hasta})."], "Gobernanza: el servicio no está activo",
                       "Revisar con: systemctl status gobernanza y journalctl -u gobernanza.")
        CAIDA_PATH.write_text(hasta)
    elif activo and CAIDA_PATH.exists():
        _enviar_alerta([f"{SERVICIO} volvió a estar activo ({hasta})."], "Gobernanza: el servicio volvió",
                       f"Había dejado de estar activo el {CAIDA_PATH.read_text().strip()}.")
        CAIDA_PATH.unlink()
    # Backup viejo: una alerta por episodio, igual que la caída del servicio.
    horas = _horas_desde_ultimo_backup(ahora)
    viejo = horas is None or horas > BACKUP_MAX_HORAS
    if viejo and not BACKUP_ALERTA_PATH.exists():
        detalle = "no hay ningún dump" if horas is None else f"el último dump tiene {horas:.0f} horas"
        print(f"backup viejo: {detalle}, enviando alerta")
        _enviar_alerta([f"{BACKUP_DIR}: {detalle} ({hasta})."], "Gobernanza: el backup diario no se hizo",
                       "Revisar con: systemctl status gobernanza-backup y journalctl -u gobernanza-backup.")
        BACKUP_ALERTA_PATH.write_text(hasta)
    elif not viejo and BACKUP_ALERTA_PATH.exists():
        BACKUP_ALERTA_PATH.unlink()
    ESTADO_PATH.write_text(hasta)


if __name__ == "__main__":
    main()
