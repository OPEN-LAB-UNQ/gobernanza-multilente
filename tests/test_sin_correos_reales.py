"""La suite nunca manda correos reales (25/10/2026).

Una corrida de la batería en /home/gobernanza, con el .env de producción (SMTP y DOCENTE_AVISO_EMAIL), mandó
cuatro avisos reales «Gobernanza · Nueva consulta en Caso». tests/conftest.py vacía el SMTP y los destinatarios
y bloquea toda conexión de correo; estas pruebas lo fijan, aun con un SMTP «real» configurado a propósito.
"""
import smtplib
import socket

from config import Settings, settings
from services import notificaciones


def test_la_suite_arranca_sin_smtp_ni_destinatarios():
    assert not settings.smtp_host and not settings.smtp_from
    assert not settings.docente_aviso_email and not settings.alertas_email
    # Aunque la carpeta tenga un .env con SMTP, el entorno de la suite lo vacía (el entorno manda sobre el .env).
    nuevo = Settings()
    assert not nuevo.smtp_host and not nuevo.smtp_from and not nuevo.docente_aviso_email


def test_con_smtp_real_configurado_el_aviso_no_abre_ninguna_conexion(monkeypatch, intentos_smtp):
    for variable, valor in {"SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "587", "SMTP_USER": "cuenta@gmail.com",
                            "SMTP_PASSWORD": "no-es-una-clave", "SMTP_FROM": "cuenta@gmail.com",
                            "DOCENTE_AVISO_EMAIL": "docente@example.org"}.items():
        monkeypatch.setenv(variable, valor)
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "cuenta@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", "no-es-una-clave")
    monkeypatch.setattr(settings, "smtp_from", "cuenta@gmail.com")
    monkeypatch.setattr(settings, "docente_aviso_email", "docente@example.org")
    conexiones = []

    def conectar(self, direccion):
        conexiones.append(direccion)
        raise ConnectionRefusedError("prueba: ningún socket hacia afuera")

    monkeypatch.setattr(socket.socket, "connect", conectar)

    estado, error = notificaciones.enviar_aviso_consulta_docente(
        notificaciones.destinatarios_docente(), 31, "Caso", None)
    assert estado == "error" and "bloqueado" in (error or "")
    assert intentos_smtp() == [("smtp", "smtp.gmail.com", 587)]
    assert conexiones == []

    # Por SSL tampoco, y tampoco por un socket directo a un puerto de correo.
    monkeypatch.setattr(settings, "smtp_port", 465)
    estado, _ = notificaciones.enviar_aviso_consulta_docente(["docente@example.org"], 31, "Caso", None)
    assert estado == "error"
    try:
        socket.create_connection(("smtp.gmail.com", 587), timeout=1)
        raise AssertionError("la conexión a un puerto de correo tenía que fallar")
    except ConnectionRefusedError:
        pass
    assert [i[0] for i in intentos_smtp()] == ["smtp", "smtp", "socket"] and conexiones == []
    assert smtplib.SMTP.__name__ == "_SMTPBloqueado" and smtplib.SMTP_SSL.__name__ == "_SMTPBloqueado"
