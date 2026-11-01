"Notificaciones por correo: trabajos de analisis y consultas al docente de la Incubadora."
from __future__ import annotations

import datetime as dt
import smtplib
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from config import settings

ZONA_AR = ZoneInfo("America/Argentina/Buenos_Aires")


def smtp_configurado() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def _enviar(msg: EmailMessage) -> tuple[str, str | None]:
    """Envía un mensaje ya armado con el SMTP de settings. Nunca levanta: devuelve (estado, error)."""
    host = settings.smtp_host
    if not host or not settings.smtp_from:
        return "pendiente_configuracion", "SMTP no configurado"
    try:
        usa_ssl = bool(settings.smtp_ssl or int(settings.smtp_port) == 465)
        smtp_cm = (
            smtplib.SMTP_SSL(host, settings.smtp_port, timeout=20)
            if usa_ssl
            else smtplib.SMTP(host, settings.smtp_port, timeout=20)
        )
        with smtp_cm as smtp:
            if settings.smtp_tls and not usa_ssl:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return "enviada", None
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)


def enviar_analisis_finalizado(
    destinatario: str | None,
    informe_id: int,
    estado: str,
    error: str | None = None,
) -> tuple[str, str | None]:
    if not destinatario:
        return "omitida", "sin destinatario"
    if not smtp_configurado():
        return "pendiente_configuracion", "SMTP no configurado"

    url = f"{settings.public_base_url.rstrip('/')}/#/informe/{informe_id}"
    msg = EmailMessage()
    msg["Subject"] = "Gobernanza Multilente: análisis finalizado" if estado == "finalizado" else "Gobernanza Multilente: análisis con error"
    msg["From"] = settings.smtp_from
    msg["To"] = destinatario
    if estado == "finalizado":
        cuerpo = f"El análisis del informe #{informe_id} ya terminó.\n\nPodés verlo en:\n{url}\n"
    else:
        cuerpo = f"El análisis del informe #{informe_id} terminó con error.\n\nDetalle: {error or '-'}\n\nRevisalo en:\n{url}\n"
    msg.set_content(cuerpo)
    return _enviar(msg)


# --- Aviso al docente cuando un participante le escribe en el espacio docente de la Incubadora ---

def destinatarios_docente() -> list[str]:
    """Correos de DOCENTE_AVISO_EMAIL (separados por coma). El modelo no asigna docente por proyecto."""
    vistos: list[str] = []
    for correo in (settings.docente_aviso_email or "").split(","):
        correo = correo.strip()
        if correo and "@" in correo and not any(c in correo for c in "\r\n") and correo.lower() not in {v.lower() for v in vistos}:
            vistos.append(correo)
    return vistos


def nombre_proyecto(proyecto_id: int, titulo: str | None) -> str:
    """Título en una línea (los encabezados de correo no admiten saltos) o «proyecto #id» si no tiene."""
    texto = " ".join((titulo or "").split())
    if len(texto) > 120:
        texto = texto[:119].rstrip() + "…"
    return texto or f"proyecto #{proyecto_id}"


def url_proyecto_docente(proyecto_id: int) -> str:
    return f"{settings.public_base_url.rstrip('/')}/#/proyecto-ia/{proyecto_id}"


def fecha_local(valor: dt.datetime | None) -> str:
    """Las fechas de la base son UTC sin zona; el correo las muestra en hora de Argentina."""
    if not valor:
        return "-"
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=dt.timezone.utc)
    return valor.astimezone(ZONA_AR).strftime("%d/%m/%Y %H:%M")


def enviar_aviso_consulta_docente(
    destinatarios: list[str],
    proyecto_id: int,
    titulo: str | None,
    creado_en: dt.datetime | None,
) -> tuple[str, str | None]:
    """Avisa que hay una consulta nueva. A propósito NO lleva el texto de la consulta ni datos de quien la hizo:
    el correo sale de la aplicación; el contenido se lee adentro, con sesión de docente."""
    if not destinatarios:
        return "omitida", "sin destinatario (DOCENTE_AVISO_EMAIL vacío)"
    if not smtp_configurado():
        return "pendiente_configuracion", "SMTP no configurado"
    nombre = nombre_proyecto(proyecto_id, titulo)
    msg = EmailMessage()
    msg["Subject"] = f"Gobernanza · Nueva consulta en {nombre}"
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(
        "Hay una consulta nueva en el espacio docente de la Incubadora.\n\n"
        f"Proyecto: {nombre} (#{proyecto_id})\n"
        f"Fecha: {fecha_local(creado_en)} (hora de Argentina)\n\n"
        f"Abrila en:\n{url_proyecto_docente(proyecto_id)}\n\n"
        "El texto de la consulta y los datos de quien la envió se ven sólo dentro de la aplicación.\n"
    )
    return _enviar(msg)


def enviar_recordatorio_consultas(
    destinatarios: list[str],
    pendientes: list[dict],
    dias: int,
) -> tuple[str, str | None]:
    """Resumen diario: consultas sin respuesta hace más de `dias` días. Sólo proyecto, fecha y enlace."""
    if not destinatarios:
        return "omitida", "sin destinatario (DOCENTE_AVISO_EMAIL vacío)"
    if not pendientes:
        return "omitida", "sin consultas pendientes"
    if not smtp_configurado():
        return "pendiente_configuracion", "SMTP no configurado"
    msg = EmailMessage()
    n = len(pendientes)
    msg["Subject"] = f"Gobernanza · {n} consulta{'s' if n != 1 else ''} sin responder"
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(destinatarios)
    lineas = [
        f"- {nombre_proyecto(p['proyecto_id'], p.get('titulo'))} (#{p['proyecto_id']}) · "
        f"{fecha_local(p.get('creado_en'))} · hace {p['dias']} días\n  {url_proyecto_docente(p['proyecto_id'])}"
        for p in pendientes
    ]
    msg.set_content(
        f"Estas consultas del espacio docente de la Incubadora siguen sin respuesta hace más de {dias} días:\n\n"
        + "\n".join(lineas)
        + "\n\nEl texto de cada consulta se ve sólo dentro de la aplicación.\n"
    )
    return _enviar(msg)
