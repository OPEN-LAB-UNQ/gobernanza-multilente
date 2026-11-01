"""Tests del mensaje de devolucion cuando no hay hallazgos comunicables."""
from __future__ import annotations

import ast
from pathlib import Path

from services import devolucion
from services.analisis import _mensaje_sin_hallazgos, estado_interpretacion_publico


class DummyInformeSinPdf:
    datos = [{"periodo": "2026-01", "valor": 100}]
    saneamiento: dict[str, object] = {}


class DummyInformeOrientado:
    datos = [{"periodo": "2026-01", "valor": 100}]
    saneamiento = {"orientacion_analisis": "Quiero entender si cambió la demanda."}


def test_mensaje_sin_hallazgos_detalla_que_reviso_cada_lente():
    """Regresion: una alumna reporto que, sin senales, el reporte no decia
    nada sobre que criterios se aplicaron para descartarlas. El mensaje debe
    listar, lente por lente, que busco cada una."""
    mensaje = _mensaje_sin_hallazgos(DummyInformeSinPdf())
    assert "Conciliador" in mensaje
    assert "Ajedrecista" in mensaje
    assert "Cronista" in mensaje
    assert "Orquesta" in mensaje
    assert "Radiólogo" in mensaje
    assert "Rizoma" in mensaje
    assert "Matemático" in mensaje
    assert "no se encontraron señales comunicables con los controles ejecutados" in mensaje


def test_mensaje_sin_hallazgos_no_finge_responder_la_orientacion():
    mensaje = _mensaje_sin_hallazgos(DummyInformeOrientado())
    assert "Orientación declarada: Quiero entender si cambió la demanda." in mensaje
    assert "no encontró señales comunicables que respondan directamente" in mensaje
    assert "no la confirma ni la descarta" in mensaje


def test_devolucion_con_senales_muestra_orientacion_y_preserva_barrido_abierto():
    mensaje, hay_hallazgos = devolucion.armar_mensaje(
        [{
            "lente": "cronista",
            "descripcion": "La serie cambia entre dos períodos.",
            "severidad": "media",
            "pregunta_institucional": "¿Qué contexto explica el cambio?",
        }],
        {"coincidencias": [], "divergencias": [], "hallazgos_singulares": []},
        DummyInformeOrientado(),
    )
    assert hay_hallazgos is True
    assert "Orientación propuesta por la persona" in mensaje
    assert "Quiero entender si cambió la demanda." in mensaje
    assert "no limita el barrido abierto" in mensaje


def test_estado_modelo_publico_distingue_respuesta_timeout_y_formato_sin_filtrar_error():
    assert estado_interpretacion_publico("gpt", {"lectura": "ok"}, None)["estado"] == "respondio"
    timeout = estado_interpretacion_publico("renderix", {}, "timed out connecting to internal host")
    assert timeout == {
        "modelo": "renderix",
        "estado": "sin_respuesta",
        "detalle": "No respondió dentro del tiempo disponible.",
    }
    formato = estado_interpretacion_publico("deepseek", {}, "la respuesta no contiene un objeto JSON")
    assert formato["detalle"] == "Respondió, pero no entregó un formato utilizable."
    assert "internal host" not in timeout["detalle"]


def test_modelos_consultados_pertenece_al_resultado_y_no_al_modelo_triangulacion():
    arbol = ast.parse(Path("services/analisis.py").read_text(encoding="utf-8"))
    keywords: dict[str, set[str]] = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        if isinstance(nodo.func, ast.Attribute):
            nombre = nodo.func.attr
        elif isinstance(nodo.func, ast.Name):
            nombre = nodo.func.id
        else:
            continue
        if nombre in {"Triangulacion", "AnalisisOut"}:
            keywords.setdefault(nombre, set()).update(k.arg for k in nodo.keywords if k.arg)
    assert "modelos_consultados" not in keywords["Triangulacion"]
    assert "modelos_consultados" in keywords["AnalisisOut"]


def test_las_lentes_que_no_corrieron_no_figuran_como_revisadas():
    from services.analisis import _barrido_por_lente
    texto = _barrido_por_lente({"radiologo": {"estado": "no_aplicable", "motivo": "Fuera del dominio presupuestario calibrado"}})
    revisadas, no_revisadas = texto.split("Qué no se revisó en este archivo:")
    assert "Radiólogo" not in revisadas
    assert "Radiólogo: Fuera del dominio presupuestario calibrado." in no_revisadas
