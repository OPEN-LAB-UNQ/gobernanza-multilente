"""Compatibilidad dimensional y alineación de períodos, desde Excel."""

import io
import json
import math
import random
import sys
from pathlib import Path

from openpyxl import Workbook

from scripts.ensayo_relaciones import evaluar as evaluar_base

VARIANTES = ("homogeneas", "porcentaje", "escala_distinta", "periodos_inversos", "bloques_separados")


def construir(seed, variante, alterado):
    base = random.Random(seed).randint(1100, 1700)
    years = list(range(2018, 2024))
    if variante == "periodos_inversos":
        years.reverse()
    w = Workbook()
    s = w.active
    s.title = "Cuadro"
    s.append(["En millones de pesos"])
    s.append(["Concepto"] + years)
    label = (
        "En porcentaje"
        if variante == "porcentaje"
        else "En miles de pesos"
        if variante == "escala_distinta"
        else "Componente B"
    )
    s.append(["Componente A"] + [base + 11 * (y - 2018) for y in years])
    s.append([label] + [2 * (base + 11 * (y - 2018)) for y in years])
    s.append(["Total"] + [3 * (base + 11 * (y - 2018)) for y in years])
    target = "C5"
    if variante == "bloques_separados":
        # Total repetido en otro bloque con años en orden contrario.
        s.append([])
        s.append(["En millones de pesos"])
        s.append(["Concepto"] + list(reversed(years)))
        s.append(["Total"] + [3 * (base + 11 * (y - 2018)) for y in reversed(years)])
        target = "F9"  # 2019, también C5 en el primer bloque.
    if alterado:
        s[target] = s[target].value + 1000
    truth = {
        "hoja": "Cuadro",
        "celda": target,
        "alterado": alterado and variante not in ("porcentaje", "escala_distinta"),
        "diferencia_esperada": 1000,
    }
    out = io.BytesIO()
    w.save(out)
    return out.getvalue(), truth


def evaluar(raw, truth):
    resultado = evaluar_base(raw, truth)
    evs = [e for h in resultado["hallazgos"] for e in [h["evidencia"], *h["evidencia"].get("conciliaciones", [])]]
    if truth["celda"] == "F9" and truth["alterado"]:
        # Una comparación no identifica cuál lado es incorrecto: exigir ambos.
        validas = [
            e
            for e in evs
            if e.get("regla") == "conciliacion_aritmetica"
            and set(e.get("celdas_participantes", [])) == {"Cuadro!C5", "Cuadro!F9"}
            and e.get("periodo") == 2019
            and math.isclose(e.get("diferencia_absoluta", -1), 1000)
        ]
        resultado["errores"] = [] if validas else ["Comparación entre bloques sin evidencia exacta"]
    if any(e.get("regla") in ("anios_no_crecientes", "discontinuidad_anual", "anio_duplicado") for e in evs):
        resultado["errores"].append("Falsa alarma sobre encabezado temporal válido")
    return resultado


def ejecutar(salida):
    out = Path(salida)
    out.mkdir(parents=True, exist_ok=False)
    casos = []
    for seed in (13711, 15217, 17401):
        for variante in VARIANTES:
            for alterado in (False, True):
                raw, truth = construir(seed, variante, alterado)
                r = evaluar(raw, truth)
                name = f"{seed}-{variante}-{int(alterado)}"
                casos.append({"caso": name, "errores": r["errores"]})
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
