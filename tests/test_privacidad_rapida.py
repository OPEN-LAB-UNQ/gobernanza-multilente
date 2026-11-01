"""Revisión rápida y privacidad: los datos del informe no salen del servidor.

La única salida de la rápida es el aviso por correo (número del informe y enlace). Lo que dicen las páginas
públicas tiene que coincidir con eso.
"""

import socket
from pathlib import Path

import pytest

import models
from config import settings
from routers import ejemplos
from services import analisis, cuota_ia, jobs, lector_mapa, notificaciones, triangulacion
from tests.test_ejemplos_zip import CATALOGO, flujo  # noqa: F401 — fixture compartida

STATIC = Path(__file__).resolve().parents[1] / "static"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def sin_red(flujo, monkeypatch):  # noqa: F811
    """Toda salida externa falla: lectoras, triangulación, exploración y cualquier conexión de red.
    El correo se reemplaza por un SMTP falso que guarda lo que se habría enviado."""
    llamadas = []

    def prohibido(nombre):
        def f(*a, **kw):
            llamadas.append(nombre)
            raise AssertionError(f"la revisión rápida intentó una salida externa: {nombre}")
        return f

    monkeypatch.setattr(lector_mapa, "llamar", prohibido("lector_mapa.llamar"))
    monkeypatch.setattr(analisis.triangulacion_svc, "interpretar_con_modelos_stream", prohibido("triangulacion.stream"))
    monkeypatch.setattr(triangulacion, "interpretar_con_modelos", prohibido("triangulacion.interpretar"))
    for nombre in ("claude", "gpt", "gemini", "deepseek", "renderix", "llama"):
        monkeypatch.setattr(triangulacion, f"_interpretar_{nombre}", prohibido(f"triangulacion.{nombre}"))
    monkeypatch.setattr(cuota_ia, "verificar_analisis", prohibido("cuota_ia"))
    # Cualquier socket hacia afuera (httpx, openai, google, smtplib) falla. TestClient y SQLite no usan red.
    monkeypatch.setattr(socket.socket, "connect", prohibido("socket.connect"))
    monkeypatch.setattr(socket, "create_connection", prohibido("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", prohibido("socket.getaddrinfo"))

    enviados = []

    class SMTPFalso:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            enviados.append(msg)

    monkeypatch.setattr(notificaciones.smtplib, "SMTP", SMTPFalso)
    monkeypatch.setattr(notificaciones.smtplib, "SMTP_SSL", SMTPFalso)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from", "avisos@example.test")
    monkeypatch.setattr(jobs, "enviar_analisis_finalizado", notificaciones.enviar_analisis_finalizado)
    return flujo, llamadas, enviados


def test_rapida_termina_sin_ninguna_salida_externa_y_el_correo_no_lleva_datos(sin_red):
    (client, factory, _), llamadas, enviados = sin_red
    item = next(d for d in CATALOGO if d["orden"] == 1 and d["columna"] == "malo")
    path = ejemplos.SAMPLES / Path(item["archivo"]).name
    data = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in item["opciones"].items()}
    data.update(periodo="2026-09", modo_revision="rapida", notificar="true", notify_email="persona@example.test")
    r = client.post("/api/analisis-rapido", data=data, files={"archivos": (path.name, path.read_bytes(), XLSX)})
    assert r.status_code == 200, r.text
    while jobs._process_one():
        pass
    assert llamadas == []
    with factory() as db:
        trabajo = db.query(models.AnalysisJob).one()
        assert trabajo.estado == "finalizado" and trabajo.modelos == []
        assert trabajo.notificacion_estado == "enviada"
        informe = db.get(models.Informe, r.json()["informe_id"])
        assert informe.hallazgos  # el análisis terminó y encontró la señal del ejemplo
        assert informe.devolucion.cobertura["interpretacion_ia"]["etapa"]["estado"] == "no_solicitada"
        assert not db.query(models.InterpretacionModelo).count()
        descripciones = [h.descripcion for h in informe.hallazgos]
    # La única salida: un aviso con el número del informe y el enlace; ni el archivo ni sus datos.
    assert len(enviados) == 1
    cuerpo = enviados[0].get_content()
    assert f"#{informe.id}" in cuerpo and f"/#/informe/{informe.id}" in cuerpo
    assert path.name not in cuerpo and path.stem not in cuerpo and path.name not in enviados[0]["Subject"]
    assert all(d[:40] not in cuerpo for d in descripciones)
    assert len(cuerpo.splitlines()) <= 5


def test_paginas_dicen_que_sale_en_cada_revision():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    presentacion = (STATIC / "presentacion.html").read_text(encoding="utf-8")
    ficha = (STATIC / "detalle-body.html").read_text(encoding="utf-8")
    charla = (STATIC / "multilente-body.html").read_text(encoding="utf-8")
    assert ("Tus datos no salen del servidor: no se envía nada a proveedores de IA. Sólo sale el aviso por correo "
            "de que terminó, con el número del informe y un enlace.") in index
    assert ("Se envían a las lectoras de IA los rótulos y la estructura de cada cuadro, sin las cifras; "
            "la lectura de las señales recibe los hallazgos con sus valores.") in index
    for texto in (presentacion, ficha, charla):
        assert "La seguridad mira todo el recorrido de los datos" in texto
        assert "sirve para informes reservados, de uso interno; datos de personas no se cargan en ninguna de las dos" in texto
    for texto in (presentacion, ficha):
        assert "Sólo sale el aviso por correo de que terminó, con el número del informe y un enlace" in texto
        assert "la lectura de las señales recibe los hallazgos con sus valores" in texto
    assert "(si el análisis falla, un aviso con el número de trabajo, sin el detalle técnico del error)" in ficha
    assert "<tr><th>Qué sale del servidor</th><td>Nada hacia proveedores de IA;" in ficha
    # La triangulación por defecto y el lector son de la profunda: la ficha no los atribuye a todo análisis.
    assert "En la revisión profunda, si hay hallazgos y no se elige un perfil" in ficha
    assert "En la revisión profunda, el <a href=\"#lector-del-cuadro\">lector del cuadro</a> añade" in ficha
    # Nada promete que la profunda no envía datos ni que la rápida no manda ningún correo.
    for texto in (index, presentacion, ficha, charla):
        assert "no sale nada del servidor" not in texto and "ningún dato sale del servidor" not in texto
