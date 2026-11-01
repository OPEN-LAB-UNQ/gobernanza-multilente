"""Calibración de relaciones: mismo control, estructuras y magnitudes distintas."""

import io
import json
import math
import random
import sys
from pathlib import Path

from openpyxl import Workbook

from services import carga_archivos, controles_excel, excel_cobertura, sanitizacion

VARIANTES = (
    "subtotal_antes_intermedio",
    "subtotales_despues",
    "componente_negativo",
    "redondeo",
    "periodo_omitido",
    "cuatro_periodos",
    "escala_pequena",
)


def construir(seed, variante, alterado):
    rng = random.Random(seed)
    base = rng.randint(1100, 1700)
    w = Workbook()
    s = w.active
    s.title = "Cuadro"
    periodos = [2018, 2019, 2020, 2021, 2022, 2023]
    if variante == "periodo_omitido":
        periodos.remove(2020)
    if variante == "cuatro_periodos":
        periodos = periodos[:4]
    s.append(["Concepto"] + periodos)
    rows = [("Atención", 1), ("Prevención", 2), ("Total", 3)]
    target = 4
    if variante == "subtotal_antes_intermedio":
        rows = [
            ("Subtotal Salud", 3),
            ("Atención", 1),
            ("Prevención", 2),
            ("Subtotal Educación", 7),
            ("Primaria", 3),
            ("Secundaria", 4),
        ]
        target = 5
    if variante == "subtotales_despues":
        rows = [
            ("Atención", 1),
            ("Prevención", 2),
            ("Subtotal Salud", 3),
            ("Primaria", 3),
            ("Secundaria", 4),
            ("Subtotal Educación", 7),
            ("Total", 10),
        ]
        target = 7
    if variante == "componente_negativo":
        rows = [("Altas", 3), ("Bajas", -1), ("Total", 2)]
    for nombre, mul in rows:
        s.append(
            [nombre]
            + [(base + j * 11) * mul * (0.0001 if variante == "escala_pequena" else 1) for j in range(len(periodos))]
        )
    if variante == "redondeo":
        for cell in s[target][1:]:
            cell.value += 0.02
    targetcell = s.cell(target, 3)
    delta = 1 if variante == "escala_pequena" else 1000
    if alterado:
        targetcell.value += delta
    truth = {
        "hoja": "Cuadro",
        "celda": targetcell.coordinate,
        "delta": delta,
        "diferencia_esperada": delta + (0.02 if variante == "redondeo" else 0),
        "alterado": alterado,
    }
    out = io.BytesIO()
    w.save(out)
    return out.getvalue(), truth


def evaluar(raw, truth):
    archivos = [("sintetico.xlsx", raw)]
    d, cv = carga_archivos.parse_archivos_con_cobertura(archivos)
    d, r, _ = excel_cobertura.preparar(d, cv, lambda x: (x, {}), sanitizacion.sanear)
    hs = controles_excel.analizar(archivos, d, r["excel"])
    evs = [ev for h in hs for ev in [h["evidencia"], *h["evidencia"].get("conciliaciones", [])]]
    conc = [ev for ev in evs if ev.get("regla") == "conciliacion_aritmetica"]
    errores = []
    if not truth["alterado"] and conc:
        errores.append("Falsa alarma de conciliación")
    if truth["alterado"] and not any(
        ev.get("celda") == truth["celda"]
        and ev.get("hoja") == truth["hoja"]
        and math.isclose(ev.get("diferencia_absoluta", -1), truth["diferencia_esperada"], rel_tol=1e-8, abs_tol=1e-8)
        for ev in conc
    ):
        errores.append("Conciliación sembrada no detectada en su celda")
    return {"errores": errores, "hallazgos": hs}


def ejecutar(salida):
    out = Path(salida)
    out.mkdir(exist_ok=False)
    casos = []
    for seed in (871, 1917, 3301):
        for variante in VARIANTES:
            for alterado in (False, True):
                raw, truth = construir(seed, variante, alterado)
                try:
                    r = evaluar(raw, truth)
                except Exception as exc:
                    r = {"errores": [type(exc).__name__ + ": " + str(exc)]}
                nombre = f"{seed}-{variante}-{int(alterado)}"
                casos.append({"caso": nombre, "errores": r["errores"]})
                if r["errores"]:
                    (out / (nombre + ".xlsx")).write_bytes(raw)
                    (out / (nombre + ".json")).write_text(
                        json.dumps({"verdad": truth, **r}, ensure_ascii=False, indent=2)
                    )
    resumen = {"casos": len(casos), "fallos": sum(bool(x["errores"]) for x in casos), "detalle": casos}
    (out / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(json.dumps(resumen, ensure_ascii=False))
    return bool(resumen["fallos"])


if __name__ == "__main__":
    sys.exit(ejecutar(sys.argv[1]))
