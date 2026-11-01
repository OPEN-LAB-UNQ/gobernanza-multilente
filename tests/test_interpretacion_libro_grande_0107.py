"""Interpretación previa de un libro grande (Gasto Público Social, 27 hojas y 172 cuadros, 22/10/2026).

Antes se leía un cuadro por vez y sin avance visible: una hora de «Interpretando el archivo…». Ahora se leen
varios cuadros a la vez, un cuadro idéntico en otra hoja (una por provincia) reutiliza la lectura y el trabajo
informa cuántos cuadros lleva.
"""
import json
import threading
import time

from services import interpretacion_previa as ip

PROVINCIAS = ["Buenos Aires", "Córdoba", "Mendoza", "Tucumán"]


def _libro(hojas, columnas=("Indicador", "Gasto", "Personas")):
    datos, bloques, grillas = [], [], []
    for n, hoja in enumerate(hojas):
        inicio = len(datos)
        for k in range(3):
            datos.append({columnas[0]: f"Programa {k}", columnas[1]: 100 + k, columnas[2]: 7 + k})
        letras = {c: "ABC"[i] for i, c in enumerate(columnas)}
        bloques.append({"archivo": "libro.xlsx", "hoja": hoja, "bloque": 1, "inicio": inicio, "fin": len(datos),
                        "filas": [4, 5, 6], "columnas": letras, "encabezados": [3]})
        celdas = {"A1": f"Gasto público social dirigido a la niñez. {hoja}", "A3": columnas[0], "B3": columnas[1],
                  "C3": columnas[2], "A4": "Programa", "A5": "Programa", "A6": "Programa"}
        grillas.append({"archivo": "libro.xlsx", "hoja": hoja, "celdas": celdas})
    return datos, {"excel": {"bloques": bloques}, "grillas_lectura": grillas}


def _lector(llamadas, demora=0.0):
    cerrojo = threading.Lock()

    def fn(proveedor, prompt):
        material = json.loads(prompt.split("\nDATOS\n", 1)[1].rsplit("\nFIN", 1)[0])
        with cerrojo:
            llamadas.append((proveedor, material["hoja"]))
        time.sleep(demora)
        cols = list(material["columnas"])
        return dict(institucion="organismo_publico", regimen="publico", tipo="estadistica", eje="ninguno",
                    descripcion=f"Gasto social de {material['hoja']}", fuentes=cols[:1], relaciones=[],
                    roles={c: "categoria" if i == 0 else "importe" for i, c in enumerate(cols)}), "modelo-prueba"
    return fn


def test_cuadros_identicos_en_hojas_distintas_se_leen_una_vez():
    datos, reporte = _libro(PROVINCIAS)
    llamadas = []
    r = ip.interpretar(datos, reporte, [("libro.xlsx", b"x")], {}, 1, fn=_lector(llamadas), proveedoras=["gpt", "gemini"])
    assert len(llamadas) == 2  # una lectura por proveedora, no cuatro
    cuadros = r["cuadros"]
    assert [c["hoja"] for c in cuadros] == PROVINCIAS
    assert "lectura_compartida" not in cuadros[0]
    assert all(c["lectura_compartida"] == {"hoja": "Buenos Aires", "bloque": 1} for c in cuadros[1:])
    # La descripción nombra la hoja de cada cuadro, no la del cuadro leído.
    assert cuadros[1]["propuesta"]["descripcion"] == "Gasto social de Córdoba"
    assert all(c["propuesta"]["tipo"] == "estadistica" for c in cuadros)


def test_cuadros_con_otros_rotulos_se_leen_por_separado():
    a_datos, a = _libro(["Buenos Aires"])
    b_datos, b = _libro(["Córdoba"], columnas=("Indicador", "Gasto", "Beneficiarios"))
    for blq in b["excel"]["bloques"]:
        blq["inicio"] += len(a_datos)
        blq["fin"] += len(a_datos)
    reporte = {"excel": {"bloques": a["excel"]["bloques"] + b["excel"]["bloques"]},
               "grillas_lectura": a["grillas_lectura"] + b["grillas_lectura"]}
    llamadas = []
    r = ip.interpretar(a_datos + b_datos, reporte, [("libro.xlsx", b"x")], {}, 1, fn=_lector(llamadas), proveedoras=["gpt"])
    assert len(llamadas) == 2 and not any("lectura_compartida" in c for c in r["cuadros"])


def test_avance_informa_cada_cuadro_leido():
    datos, reporte = _libro(PROVINCIAS)
    pasos = []
    ip.interpretar(datos, reporte, [("libro.xlsx", b"x")], {}, 1, fn=_lector([]), proveedoras=["gpt"],
                   avance=lambda leidos, total, hoja: pasos.append((leidos, total)))
    assert pasos[0] == (0, 4) and pasos[-1] == (4, 4)


def test_los_cuadros_distintos_se_leen_a_la_vez():
    # Seis cuadros con otra columna cada uno: ninguno reutiliza la lectura de otro.
    datos, bloques, grillas = [], [], []
    for medida in ("Gasto", "Monto", "Importe", "Erogación", "Inversión", "Transferencia"):
        d, r = _libro([f"Hoja {medida}"], columnas=("Indicador", medida, "Personas"))
        for blq in r["excel"]["bloques"]:
            blq["inicio"] += len(datos)
            blq["fin"] += len(datos)
        datos += d
        bloques += r["excel"]["bloques"]
        grillas += r["grillas_lectura"]
    reporte = {"excel": {"bloques": bloques}, "grillas_lectura": grillas}
    llamadas = []
    inicio = time.monotonic()
    ip.interpretar(datos, reporte, [("libro.xlsx", b"x")], {}, 1, fn=_lector(llamadas, demora=0.2), proveedoras=["gpt"])
    assert len(llamadas) == 6
    assert time.monotonic() - inicio < 6 * 0.2 * 0.75  # de a CUADROS_EN_PARALELO, no uno por vez
