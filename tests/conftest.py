"""Fixtures y helpers compartidos por la suite de tests."""
from __future__ import annotations

import os
import smtplib
import socket

import pytest

# La suite funciona en una instalación limpia y no hereda acceso a producción: la base de pruebas se fija
# siempre, aunque el entorno traiga la de producción (por ejemplo, después de cargar el .env con `set -a`).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-only-not-a-production-secret")
os.environ.setdefault("GOBERNANZA_PASSWORD", "test-only")
# El lector del cuadro consulta modelos de IA: en las pruebas va apagado aunque el .env de la carpeta lo active
# (una variable de entorno tiene prioridad sobre el .env). Las pruebas del lector lo activan ellas mismas.
os.environ["LECTOR_IA"] = "apagado"

# Correo: la suite NUNCA manda correos reales (25/10/2026: corrida en /home/gobernanza, con el .env de producción,
# mandó 4 avisos «Nueva consulta en Caso» al docente). Dos capas, además de este vaciado del entorno (una variable
# de entorno tiene prioridad sobre el .env, así que `settings` arranca sin SMTP ni destinatarios):
#   1) `_sin_correos_reales` (autouse, toda la sesión) vacía SMTP y destinatarios en `settings` y reemplaza
#      smtplib.SMTP y SMTP_SSL por un falso que registra el intento y falla sin conectar;
#   2) cualquier conexión de socket a un puerto de correo falla (por si algo importó la clase SMTP antes).
# Las pruebas que verifican el envío ponen su propio SMTP falso y sus datos con monkeypatch, encima de esto.
_VARIABLES_CORREO = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "DOCENTE_AVISO_EMAIL", "ALERTAS_EMAIL")
for _variable in _VARIABLES_CORREO:
    os.environ[_variable] = ""
PUERTOS_CORREO = {25, 465, 587, 2525}
INTENTOS_SMTP: list[tuple] = []


class _SMTPBloqueado:
    """Registra el intento y falla como un servidor que rechaza la conexión. Nunca abre un socket."""

    def __init__(self, host="", port=0, *args, **kwargs):
        INTENTOS_SMTP.append(("smtp", host, port))
        raise ConnectionRefusedError(f"pruebas: SMTP bloqueado ({host}:{port}); no se mandan correos reales")


_crear_conexion_original = socket.create_connection


def _crear_conexion_vigilada(address, *args, **kwargs):
    try:
        puerto = int(address[1])
    except (TypeError, ValueError, IndexError):
        puerto = None
    if puerto in PUERTOS_CORREO:
        INTENTOS_SMTP.append(("socket", address[0], puerto))
        raise ConnectionRefusedError(f"pruebas: conexión a un puerto de correo bloqueada ({address[0]}:{puerto})")
    return _crear_conexion_original(address, *args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def _sin_correos_reales():
    from config import settings

    with pytest.MonkeyPatch.context() as mp:
        for campo in ("smtp_host", "smtp_user", "smtp_password", "smtp_from"):
            mp.setattr(settings, campo, None)
        mp.setattr(settings, "docente_aviso_email", "")
        mp.setattr(settings, "alertas_email", "")
        mp.setattr(smtplib, "SMTP", _SMTPBloqueado)
        mp.setattr(smtplib, "SMTP_SSL", _SMTPBloqueado)
        mp.setattr(socket, "create_connection", _crear_conexion_vigilada)
        yield


@pytest.fixture
def intentos_smtp():
    """Devuelve una función con los intentos de correo real que la suite bloqueó desde que empezó la prueba."""
    inicio = len(INTENTOS_SMTP)
    return lambda: list(INTENTOS_SMTP[inicio:])


def _presupuesto_largo(devengado_pct=0.93, salto_area=None, salto_periodo=None, salto_factor=2.6):
    """4 areas x 6 meses, formato largo (periodo/area/credito_*). Con
    salto_area+salto_periodo se introduce una anomalia deliberada en esa
    celda para poder afirmar que las lentes la detectan."""
    areas = ["Salud", "Educacion", "Infraestructura", "Desarrollo Social"]
    meses = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    base = {"Salud": 1_000_000, "Educacion": 1_800_000, "Infraestructura": 900_000, "Desarrollo Social": 650_000}
    filas = []
    for area in areas:
        credito = base[area]
        for i, periodo in enumerate(meses):
            vigente = credito * (1 + 0.02 * i)
            devengado = vigente * devengado_pct
            if area == salto_area and periodo == salto_periodo:
                devengado = vigente * salto_factor
            filas.append({
                "area": area,
                "periodo": periodo,
                "credito_vigente": round(vigente, 2),
                "credito_devengado": round(devengado, 2),
                "credito_pagado": round(devengado * 0.97, 2),
            })
    return filas
