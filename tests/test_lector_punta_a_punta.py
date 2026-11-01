"""Lector del cuadro de punta a punta: carga de un Excel, análisis en la cola y señal guardada en el informe
(lectoras simuladas: no hay llamadas a modelos)."""
from io import BytesIO

from openpyxl import Workbook

import models
from config import settings
from services import jobs, lector_mapa
from tests.flujo_confirmado import respuesta_fixture, terminar_lectura

pytest_plugins = ["tests.test_ejemplos_zip"]

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre"]
NETO = {"tipo": "columnas", "destino": "D", "expresion": "B - C", "filas": [3, 14], "fundamento": "neto = altas - bajas"}


def _libro():
    w = Workbook()
    s = w.active
    s.title = "Altas"
    s["A1"] = "Cuadro 1. Altas y bajas mensuales 2019"
    for j, t in enumerate(["Mes", "Altas", "Bajas", "Neto"], 1):
        s.cell(2, j, t)
    for i, mes in enumerate(MESES):
        altas, bajas = 1000 + 37 * i, 400 + 11 * i
        s.append([mes, altas, bajas, altas - bajas])
    s["D9"] = s["D9"].value * 10
    b = BytesIO()
    w.save(b)
    return b.getvalue()


def _cargar(client):
    opciones = {"periodo": "2026-09", "dominio": "general", "notificar": "false", "modo_revision": "profunda"}
    archivos = {"archivos": ("altas.xlsx", _libro(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/api/analisis-rapido", data=opciones, files=archivos)
    assert r.status_code == 200, r.text
    p = terminar_lectura(client, r.json())
    assert p["estado"] == "pendiente_confirmacion" and "job" not in p
    r = client.post("/api/analisis-rapido", data={**opciones, "interpretacion_accion": "confirmar",
        "interpretacion_id": p["informe_id"], "interpretacion_revision": p["interpretacion"]["revision"]}, files=archivos)
    assert r.status_code == 200, r.text
    return r.json()["informe_id"]


def test_activo_la_senal_del_lector_llega_al_informe(flujo, monkeypatch):
    client, factory, _ = flujo
    monkeypatch.setattr(settings, "lector_ia", "activo")
    llamadas = []

    def falsa(lectora, prompt):
        llamadas.append(lectora)
        assert "D9" in prompt and "6550" not in prompt  # a ciegas
        respuesta, _ = respuesta_fixture(lectora, prompt)
        return {**respuesta, "relaciones": [NETO]}, f"modelo-{lectora}"

    monkeypatch.setattr(lector_mapa, "llamar", falsa)
    monkeypatch.setattr(lector_mapa, "lectoras_habilitadas", lambda: ["gpt", "gemini", "deepseek"])
    informe_id = _cargar(client)
    assert jobs._process_one()
    with factory() as db:
        i = db.get(models.Informe, informe_id)
        assert i.saneamiento["grillas_lectura"][0]["hoja"] == "Altas"
        mapa = i.saneamiento["mapa_lectura"]
        assert mapa["modo"] == "activo" and mapa["senales"] == 1 and sorted(set(llamadas)) == ["deepseek", "gemini", "gpt"]
        del_lector = [h for h in i.hallazgos if (h.evidencia or {}).get("regla") == "relacion_leida_no_cierra"]
        assert [(h.evidencia["hoja"], h.evidencia["celda"], h.severidad) for h in del_lector] == [("Altas", "D9", "alta")]


def test_interruptor_del_lector_antiguo_no_omite_interpretacion_previa(flujo, monkeypatch):
    client, factory, _ = flujo
    monkeypatch.setattr(settings, "lector_ia", "apagado")

    llamadas = []
    def leer(lectora, prompt):
        llamadas.append(lectora)
        return respuesta_fixture(lectora, prompt)
    monkeypatch.setattr(lector_mapa, "llamar", leer)
    monkeypatch.setattr(lector_mapa, "lectoras_habilitadas", lambda: ["gpt", "gemini", "deepseek"])
    informe_id = _cargar(client)
    assert len(llamadas) == 3
    assert jobs._process_one()
    assert len(llamadas) == 3  # las cuentas no vuelven a interpretar después de confirmar
    with factory() as db:
        i = db.get(models.Informe, informe_id)
        assert i.saneamiento["interpretacion_previa"]["estado"] == "confirmada"
        assert i.saneamiento["mapa_lectura"]["senales"] == 0
        assert not [h for h in i.hallazgos if (h.evidencia or {}).get("regla") == "relacion_leida_no_cierra"]


def test_si_los_modelos_fallan_el_analisis_termina_igual(flujo, monkeypatch):
    client, factory, _ = flujo
    monkeypatch.setattr(settings, "lector_ia", "activo")

    def caida(lectora, prompt):
        raise RuntimeError("proveedor caído")

    monkeypatch.setattr(lector_mapa, "llamar", caida)
    monkeypatch.setattr(lector_mapa, "lectoras_habilitadas", lambda: ["gpt", "gemini", "deepseek"])
    informe_id = _cargar(client)
    assert jobs._process_one()
    with factory() as db:
        i = db.get(models.Informe, informe_id)
        assert i.devolucion is not None
        previa = i.saneamiento["interpretacion_previa"]
        errores = previa["cuadros"][0]["lecturas"]
        assert all(m["error"] for m in errores.values())
        assert not i.hallazgos
        # Desde 0.10.28 las cuentas no dependen de la IA: con las tres lectoras caidas, los controles corren igual.
        assert i.devolucion.cobertura["condiciones_validez"]["puede_concluir"]
