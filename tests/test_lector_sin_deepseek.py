"""0.10.60: el lector del cuadro y la interpretación previa leen con GPT y Gemini; DeepSeek sólo si se agrega a mano.

DeepSeek trata los datos en China, sin decisión de adecuación de la Comisión Europea. El lector deja de enviarle los
cuadros por defecto; LECTOR_LECTORAS=gpt,gemini,deepseek lo vuelve a sumar y entonces vale lo que acuerden dos de tres.
"""
from pathlib import Path

import pytest

from config import Settings, settings
from services import interpretacion_previa as ip
from services import lector_mapa as lm

STATIC = Path(__file__).resolve().parents[1] / "static"


def test_por_defecto_leen_gpt_y_gemini():
    assert lm.LECTORAS_POR_DEFECTO == ("gpt", "gemini")
    assert Settings.model_fields["lector_lectoras"].default == ",".join(lm.LECTORAS_POR_DEFECTO)


@pytest.mark.parametrize("elegidas,suspendidos,esperadas", [
    ("gpt,gemini", "", ["gpt", "gemini"]),
    ("", "", ["gpt", "gemini"]),
    (",", "", ["gpt", "gemini"]),
    ("claude", "", ["gpt", "gemini"]),
    ("openai,google", "", ["gpt", "gemini"]),
    ("gpt,gemini,deepseek", "", ["gpt", "gemini", "deepseek"]),
    (" DeepSeek , GPT,gemini ", "", ["gpt", "gemini", "deepseek"]),
    ("gpt,gemini,deepseek", "gemini", ["gpt", "deepseek"]),
    ("gpt,gemini", "claude", ["gpt", "gemini"]),
    ("gpt,claude,llama", "", ["gpt"]),
])
def test_deepseek_solo_si_se_agrega_a_mano(monkeypatch, elegidas, suspendidos, esperadas):
    monkeypatch.setattr(settings, "lector_lectoras", elegidas)
    monkeypatch.setattr(settings, "modelos_suspendidos", suspendidos)
    assert lm.lectoras_habilitadas() == esperadas


def test_una_lectora_suspendida_se_declara_en_cada_cuadro(monkeypatch):
    # Con dos lectoras, suspender una deja a los cuadros sin acuerdo: la pantalla tiene que decir por qué.
    monkeypatch.setattr(settings, "lector_lectoras", "gpt,gemini")
    monkeypatch.setattr(settings, "modelos_suspendidos", "gemini")
    assert lm.lectoras_suspendidas() == ["gemini"]
    consultadas = []

    def lector(proveedor, prompt):
        consultadas.append(proveedor)
        return dict(institucion="universidad", regimen="publico", tipo="desconocido", eje="serie_filas",
                    descripcion="Presupuesto", roles={}, fuentes=[], relaciones=[]), "modelo-prueba"

    datos = [{"Mes": "2026-01", "credito_vigente": 100, "devengado": 80} for _ in range(6)]
    registro = ip.interpretar(datos, {"archivos_origen": ["a.csv"]}, [("a.csv", b"x")], {}, 1, fn=lector)
    assert consultadas and set(consultadas) == {"gpt"}
    cuadro = ip.publico(registro)["cuadros"][0]
    assert cuadro["estado_lectoras"]["gemini"]["error"] == lm.NO_CONSULTADA
    assert cuadro["lecturas_validas"] == 1 and cuadro["propuesta"]["tipo"] == "desconocido"


def test_una_cita_inexistente_se_descarta_sin_perder_el_voto():
    cols = {"col_0": "Mes", "col_1": "Total"}
    r = dict(institucion="desconocida", regimen="no_determinado", tipo="estadistica", eje="serie_filas",
             roles={"col_0": "periodo_serie", "col_1": "importe"}, fuentes=["col_1", "B15", "C"], relaciones=[])
    valido = ip._validar(r, cols, set(cols) | {"A3"})
    assert valido["fuentes"] == ["col_1"] and valido["fuentes_descartadas"] == 2
    r["fuentes"] = ["B15"]
    with pytest.raises(ValueError, match="referencias inexistentes"):
        ip._validar(r, cols, set(cols))


def test_el_lector_sin_lectoras_explicitas_no_consulta_a_deepseek(monkeypatch):
    monkeypatch.setattr(settings, "lector_lectoras", "gpt,gemini")
    monkeypatch.setattr(settings, "modelos_suspendidos", "")
    consultadas = []

    def proveedor(nombre, prompt):
        consultadas.append(nombre)
        return {"relaciones": [dict(tipo="filas", destino=15, expresion="3+4", columnas=["B"])]}, nombre

    san = {"grillas_lectura": [dict(archivo="a.xlsx", hoja="H", celdas={"B3": 10., "B4": 20., "B15": 99.})]}
    lectura = lm.analizar(san, proveedor, None, "activo")
    assert sorted(consultadas) == ["gemini", "gpt"]
    hoja = lectura["estado"]["hojas"][0]
    assert set(hoja["mapas"]) == {"gpt", "gemini"}
    # Con dos lectoras, la relación se comprueba porque la proponen las dos.
    assert len(hoja["grupos"]) == 1


def test_la_interpretacion_previa_sin_proveedoras_explicitas_no_consulta_a_deepseek(monkeypatch):
    monkeypatch.setattr(settings, "lector_lectoras", "gpt,gemini")
    monkeypatch.setattr(settings, "modelos_suspendidos", "")
    consultadas = []

    def lector(proveedor, prompt):
        consultadas.append(proveedor)
        return dict(institucion="universidad", regimen="publico", tipo="presupuesto", eje="serie_filas",
                    descripcion="Presupuesto", roles={}, fuentes=[], relaciones=[]), "modelo-prueba"

    datos = [{"Mes": "2026-01", "credito_vigente": 100, "devengado": 80} for _ in range(6)]
    ip.interpretar(datos, {"archivos_origen": ["a.csv"]}, [("a.csv", b"x")], {}, 1, fn=lector)
    assert consultadas and set(consultadas) == {"gpt", "gemini"}


def test_el_pedido_exige_proponer_las_relaciones_que_sostienen_los_rotulos():
    pedido = " ".join(ip.PEDIDO.split())
    assert pedido.startswith("Tu respuesta tiene dos partes: la clasificación del cuadro y sus relaciones.")
    assert "Proponé todas las que los rótulos sostengan; [] sólo si no permiten deducir ninguna." in pedido
    assert "No completes por adivinación. Una propuesta no es un hallazgo" in pedido


def test_las_paginas_publicas_dicen_que_el_lector_no_envia_a_deepseek():
    privacidad = (STATIC / "privacidad-body.html").read_text(encoding="utf-8")
    assert "el lector del cuadro envía a OpenAI y Gemini" in privacidad
    assert "desde la versión 0.10.60 ya no los envía a DeepSeek" in privacidad
    assert "DeepSeek, que en este despliegue interviene sólo si se elige en la triangulación" in privacidad
    textos = {n: (STATIC / n).read_text(encoding="utf-8") for n in
              ("detalle-body.html", "index.html", "multilente-body.html", "presentacion.html", "privacidad-body.html")}
    for nombre, html in textos.items():
        for viejo in ("OpenAI, Gemini y DeepSeek", "Google Gemini y DeepSeek cuando", "Tres proveedores", "tres proveedores",
                      "propuestas de tres modelos", "tres lectoras y tu confirmación", "Tres modelos leen"):
            assert viejo not in html, (nombre, viejo)
    assert "las de Gemini y DeepSeek, 4" in textos["detalle-body.html"]
