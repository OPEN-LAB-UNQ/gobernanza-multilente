"""Regresión sobre los documentos visibles en "Documentos para probar".

Cada fila del manifest define un ejemplo bueno o malo. El test comprueba que
los buenos no produzcan señales comunicables y que los malos produzcan al
menos una señal, usando las mismas opciones técnicas de la UI.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, cast

import pytest

import models
from routers.carga_rapida import _aplicar_alcance_series, _inferir_dominio
from services import carga_archivos, formula_integridad, guardrails, pdf_controles
from services import sanitizacion as sanitizacion_svc
from services.lentes import ejecutar_lentes

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "static" / "samples"


def _sample_items() -> list[dict]:
    manifest = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    return sorted(manifest, key=lambda item: (item["orden"], item["columna"]))


def _hallazgos_sample(item: dict) -> list[dict]:
    path = ROOT / "static" / item["archivo"].lstrip("/")
    contenido = path.read_bytes()
    leidos = [(path.name, contenido)]
    opciones = item.get("opciones") or {}

    datos = carga_archivos.parse_archivos(leidos)
    datos, normalizacion_series = _aplicar_alcance_series(
        datos,
        str(opciones.get("alcance_series") or "auto"),
    )

    formula_hallazgos = (
        formula_integridad.analizar_archivos(
            leidos,
            detectar_formulas=bool(opciones.get("revisar_formulas_excel")),
            inferir_patrones=bool(opciones.get("inferir_patrones_calculo")),
        )
        if opciones.get("revisar_formulas_excel") or opciones.get("inferir_patrones_calculo")
        else []
    )
    matematico_hallazgos = (
        formula_integridad.analizar_matematico_archivos(leidos)
        if opciones.get("revisar_metodo_calculo")
        else []
    )
    matematico_hallazgos.extend(pdf_controles.analizar(datos))

    datos_saneados, reporte = sanitizacion_svc.sanear(datos)
    reporte["normalizacion_series"] = normalizacion_series
    if formula_hallazgos:
        reporte["formula_hallazgos"] = formula_hallazgos
    if matematico_hallazgos:
        reporte["matematico_hallazgos"] = matematico_hallazgos

    area = models.Area(id=1, nombre="General", codigo="GENERAL")
    informe = models.Informe(
        id=1,
        area_id=1,
        area=area,
        periodo="2026-08",
        dominio=_inferir_dominio(datos_saneados, str(opciones.get("dominio") or "auto")),
        modo="intraarea",
        datos=datos_saneados,
        saneamiento=reporte,
        creado_en=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    return guardrails.normalizar_hallazgos(ejecutar_lentes(cast(Any, _DBSinPrevios()), informe), informe)


class _QueryVacia:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _DBSinPrevios:
    def query(self, _model):
        return _QueryVacia()


@pytest.mark.parametrize("item", _sample_items(), ids=lambda item: item["nombre"])
def test_documento_de_ejemplo_detecta_lo_esperado(item: dict):
    hallazgos = _hallazgos_sample(item)

    assert item["estado"] in {"correcto", "incorrecto", "sin_senal", "con_senal"}
    if item["columna"] == "bueno":
        assert hallazgos == []
    else:
        assert hallazgos, f"{item['nombre']} debería producir al menos una señal"
