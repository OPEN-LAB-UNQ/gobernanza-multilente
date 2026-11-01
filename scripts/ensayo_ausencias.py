"""Ausencias, ceros, encabezados ambiguos y fórmulas sin caché."""

import io
import json
import random
import sys
from pathlib import Path

from openpyxl import Workbook

from services import carga_archivos, controles_excel, excel_cobertura, formula_integridad, sanitizacion

VARIANTES = ("vacio_interior", "vacio_extremo", "cero", "texto", "formula", "formula_desplazada", "anio_duplicado")


def construir(seed, variante, alterado):
    base = random.Random(seed).randint(1100, 1700)
    w = Workbook()
    s = w.active
    s.title = "Cuadro"
    s.append(["Concepto"] + list(range(2018, 2024)))
    for label, m in [("Salud", 1), ("Educación", 2), ("Total", 3)]:
        s.append([label] + [(base + j * 11) * m for j in range(6)])
    required = []
    forbidden = []
    if alterado:
        if variante == "vacio_interior":
            s["D2"] = None
            required = [("vacio_interior", "D2")]
        if variante == "vacio_extremo":
            s["B2"] = None
            forbidden = [("vacio_interior", "B2"), ("conciliacion_aritmetica", "B4")]
        if variante == "cero":
            s["D2"] = 0
            required = [("conciliacion_aritmetica", "D4")]
            forbidden = [("vacio_interior", "D2"), ("cambio_tipo", "D2")]
        if variante == "texto":
            s["D2"] = "s/d"
            required = [("cambio_tipo", "D2")]
            forbidden = [("conciliacion_aritmetica", "D4")]
        if variante in ("formula", "formula_desplazada"):
            for col in "BCDEFG":
                s[f"{col}4"] = f"=SUM({col}2:{col}3)"
            forbidden = [("vacio_interior", f"{col}4") for col in "BCDEFG"]
            if variante == "formula_desplazada":
                s["D4"] = "=SUM(C2:C3)"
                required = [("formula_fuera_de_patron", "D4")]
        if variante == "anio_duplicado":
            s["D1"] = 2019
            s["D4"] = s["D4"].value + 1000
            required = [("anio_duplicado", "D1")]
            forbidden = [("conciliacion_aritmetica", "C4"), ("conciliacion_aritmetica", "D4")]
    out = io.BytesIO()
    w.save(out)
    return out.getvalue(), {"required": required, "forbidden": forbidden, "alterado": alterado, "variante": variante}


def evaluar(raw, truth):
    archivos = [("sintetico.xlsx", raw)]
    d, cv = carga_archivos.parse_archivos_con_cobertura(archivos)
    d, r, _ = excel_cobertura.preparar(d, cv, lambda x: (x, {}), sanitizacion.sanear)
    hs = controles_excel.analizar(archivos, d, r["excel"]) + formula_integridad.analizar_archivo("sintetico.xlsx", raw)
    evs = [e for h in hs for e in [h["evidencia"], *h["evidencia"].get("conciliaciones", [])]]
    present = {(e.get("regla"), e.get("celda")) for e in evs if e.get("hoja") == "Cuadro"}
    errores = [f"Falta {x}" for x in truth["required"] if tuple(x) not in present]
    errores += [f"Falsa alarma {x}" for x in truth["forbidden"] if tuple(x) in present]
    if not truth["alterado"] and hs:
        errores.append("Hallazgos en control correcto")
    if truth["variante"] == "formula" and hs:
        errores.append("Hallazgos en fórmulas coherentes sin caché")
    return {"errores": errores, "hallazgos": hs}


def ejecutar(salida):
    out = Path(salida)
    out.mkdir(parents=True, exist_ok=False)
    casos = []
    for seed in (19001, 21317, 23143):
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
