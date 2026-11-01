"""Relaciones aritmeticas entre columnas identificadas por nombre."""
from __future__ import annotations

import re
from typing import Any

from services.calculos.excel_utils import (
    MAX_HALLAZGOS,
    _norm_label,
)
from services.calculos.formulas import (
    _evaluar_patron,
    _hallazgo_implicito,
)


def _buscar_por_nombre(ws, rows: list[dict[str, Any]], patron: str) -> dict[str, Any] | None:
    rx = re.compile(patron)
    for row in rows:
        if rx.search(_norm_label(ws, row["row"])):
            return row
    return None


def _analizar_relaciones_por_nombre(ws, rows: list[dict[str, Any]]) -> list[dict]:
    hallazgos: list[dict] = []
    sheet = ws.title
    reglas = [
        (
            r"superavit.*deficit operativo",
            r"total ingresos operativos",
            r"total egresos operativos",
            "{target} = {a} - {b}",
            lambda a, b: {c: a["values"][c] - b["values"][c] for c in set(a["values"]) & set(b["values"])}
        ),
        (
            r"saldo.*deficit financiero",
            r"total ingresos financieros",
            r"total egresos financieros",
            "{target} = {a} - {b}",
            lambda a, b: {c: a["values"][c] - b["values"][c] for c in set(a["values"]) & set(b["values"])}
        ),
        (
            r"saldo.*deficit del periodo",
            r"superavit.*deficit operativo",
            r"saldo.*deficit financiero",
            "{target} = {a} + {b}",
            lambda a, b: {c: a["values"][c] + b["values"][c] for c in set(a["values"]) & set(b["values"])}
        ),
        (
            r"caja final",
            r"saldo inicial",
            r"saldo.*deficit del periodo",
            "{target} = {a} + {b}",
            lambda a, b: {c: a["values"][c] + b["values"][c] for c in set(a["values"]) & set(b["values"])}
        ),
    ]
    for target_pat, a_pat, b_pat, template, calc in reglas:
        target = _buscar_por_nombre(ws, rows, target_pat)
        a = _buscar_por_nombre(ws, rows, a_pat)
        b = _buscar_por_nombre(ws, rows, b_pat)
        if not target or not a or not b:
            continue
        target["ws"] = ws
        esperado = calc(a, b)
        ok, fallas = _evaluar_patron(target, esperado)
        total = ok + len(fallas)
        if not fallas or total < 4 or ok < max(4, int(total * 0.7)):
            continue
        col, actual, exp = fallas[0]
        regla = template.format(target=target["label"], a=a["label"], b=b["label"])
        hallazgos.append(_hallazgo_implicito(sheet, target, col, actual, exp, regla, [a["label"], b["label"]]))
        if len(hallazgos) >= MAX_HALLAZGOS:
            return hallazgos
    return hallazgos
