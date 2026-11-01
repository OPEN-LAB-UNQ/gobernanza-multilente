"""Casos conocidos de materialidad, signo y evidencia mínima."""

import io
import json
import random
import sys
from pathlib import Path

from openpyxl import Workbook

from scripts.ensayo_relaciones import evaluar

VARIANTES = (
    "tres_periodos",
    "cuatro_periodos",
    "cinco_periodos",
    "dos_ausentes",
    "tres_ausentes",
    "diferencia_negativa",
    "total_negativo",
    "cancelacion",
    "redondeo_absoluto",
    "redondeo_relativo",
)


def construir(seed, variante, alterado):
    rng = random.Random(seed)
    base = rng.randint(1100, 1700)
    count = (
        3
        if variante == "tres_periodos"
        else 4
        if variante == "cuatro_periodos"
        else 5
        if variante == "cinco_periodos"
        else 6
    )
    w = Workbook()
    s = w.active
    s.title = "Cuadro"
    s.append(["Concepto"] + list(range(2018, 2018 + count)))
    a = [base + 11 * j for j in range(count)]
    b = [2 * x for x in a]
    if variante == "total_negativo":
        a = [-x for x in a]
        b = [-x for x in b]
    if variante == "cancelacion":
        b = [-x for x in a]
    if variante == "redondeo_absoluto":
        a = [0.1 + 0.01 * j for j in range(count)]
        b = [2 * x for x in a]
    total = [x + y for x, y in zip(a, b)]
    if variante == "redondeo_absoluto":
        total = [x + 0.02 for x in total]
    if variante == "redondeo_relativo":
        total[1] *= 1.0005
    s.append(["Componente A"] + a)
    s.append(["Componente B"] + b)
    s.append(["Total"] + total)
    if variante in ("dos_ausentes", "tres_ausentes"):
        n = 2 if variante == "dos_ausentes" else 3
        for col in range(2 + count - n, 2 + count):
            s.cell(2, col).value = None
    delta = -1000 if variante == "diferencia_negativa" else 1 if variante == "redondeo_absoluto" else 1000
    if alterado:
        s["C4"] = s["C4"].value + delta
    # Tres períodos no permiten corroborar la relación con las reglas actuales.
    esperado = alterado and variante not in ("tres_periodos", "tres_ausentes")
    # Componentes no nulos que se compensan sí aportan evidencia aritmética.
    diferencia = abs(s["C4"].value - (a[1] + b[1]))
    truth = {
        "hoja": "Cuadro",
        "celda": "C4",
        "alterado": esperado,
        "diferencia_esperada": diferencia,
        "mutacion_aplicada": alterado,
        "variante": variante,
    }
    out = io.BytesIO()
    w.save(out)
    return out.getvalue(), truth


def ejecutar(salida):
    out = Path(salida)
    out.mkdir(parents=True, exist_ok=False)
    casos = []
    for seed in (9413, 10211, 12007):
        for variante in VARIANTES:
            for alterado in (False, True):
                raw, truth = construir(seed, variante, alterado)
                r = evaluar(raw, truth)
                name = f"{seed}-{variante}-{int(alterado)}"
                casos.append({"caso": name, "espera_hallazgo": truth["alterado"], "errores": r["errores"]})
                if r["errores"]:
                    (out / (name + ".xlsx")).write_bytes(raw)
                    (out / (name + ".json")).write_text(
                        json.dumps({"verdad": truth, **r}, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
    resumen = {"casos": len(casos), "fallos": sum(bool(x["errores"]) for x in casos), "detalle": casos}
    (out / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False))
    return bool(resumen["fallos"])


if __name__ == "__main__":
    sys.exit(ejecutar(sys.argv[1]))
