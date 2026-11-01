"""Catálogo v2 reproducible. Conserva todos los originales anteriores.

Clona los XLSX existentes y ajusta XML/cachés explícitos sin recalcular con una
aplicación externa. No usa datos de usuarios. Todos los ejemplos son sintéticos.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "static/samples"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
N = {"s": NS}


def clonar(origen, nombre, cambios=None, formula=None, hoja=None, nota=""):
    with ZipFile(SAMPLES / origen) as z:
        entradas = {i.filename: z.read(i.filename) for i in z.infolist()}
    xml = ET.fromstring(entradas["xl/worksheets/sheet1.xml"])
    for c in xml.findall(".//s:c", N):
        ref = c.get("r")
        if ref not in (cambios or {}) and ref not in (formula or {}):
            continue
        valor = cambios[ref] if ref in (cambios or {}) else None
        for child in list(c):
            c.remove(child)
        c.attrib.pop("t", None)
        if ref in (formula or {}):
            ET.SubElement(c, "{" + NS + "}f").text = formula[ref].lstrip("=")
            if isinstance(valor, str):
                c.set("t", "str")
            ET.SubElement(c, "{" + NS + "}v").text = str(valor)
        elif isinstance(valor, str):
            c.set("t", "inlineStr")
            ET.SubElement(ET.SubElement(c, "{" + NS + "}is"), "{" + NS + "}t").text = valor
        else:
            ET.SubElement(c, "{" + NS + "}v").text = str(valor)
    entradas["xl/worksheets/sheet1.xml"] = ET.tostring(xml)
    if hoja:
        wb = ET.fromstring(entradas["xl/workbook.xml"])
        wb.find("s:sheets/s:sheet", N).set("name", hoja)
        entradas["xl/workbook.xml"] = ET.tostring(wb)
    guia = ET.Element("{" + NS + "}worksheet")
    data = ET.SubElement(guia, "{" + NS + "}sheetData")
    for i, par in enumerate(
        [
            ("Campo", "Valor"),
            ("Archivo", nombre),
            ("Origen", "Datos sintéticos para demostración; no son datos de personas ni validación empírica."),
            ("Nota", nota),
        ],
        1,
    ):
        row = ET.SubElement(data, "{" + NS + "}row", r=str(i))
        for col, valor in zip("AB", par):
            c = ET.SubElement(row, "{" + NS + "}c", r=f"{col}{i}", t="inlineStr")
            ET.SubElement(ET.SubElement(c, "{" + NS + "}is"), "{" + NS + "}t").text = valor
    entradas["xl/worksheets/sheet2.xml"] = ET.tostring(guia)
    with ZipFile(SAMPLES / nombre, "w", ZIP_DEFLATED) as z:
        for path, contenido in entradas.items():
            info = ZipInfo(path, date_time=(2026, 9, 18, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            z.writestr(info, contenido)


def main():
    manifest = json.loads((SAMPLES / "manifest.json").read_text())
    # Permite repetir la generación conservando siempre las fuentes originales.
    por_caso = {}
    for item in manifest:
        por_caso.setdefault(item["orden"], {})[item["columna"]] = item
    bases = {
        1: ("incorrecto-pagado-mayor-devengado.xlsx", {"E4": 480}),
        4: ("incorrecto-acumulado-retrocede.xlsx", {"C5": 400, "D5": 365}),
        5: ("incorrecto-formulas-notas.xlsx", {"G4": 7, "H3": "REGULAR"}),
        6: (
            "incorrecto-avance-fisico-financiero.xlsx",
            {"D4": 57, "D5": 81, "D6": 94, "E4": 115, "E5": 163, "E6": 190},
        ),
        8: (
            "incorrecto-correlacion-espuria.xlsx",
            dict(zip(["D" + str(i) for i in range(2, 10)], [500, 420, 610, 390, 550, 480, 530, 600])),
        ),
    }
    for caso, (base, buenos) in bases.items():
        for lado in ("bueno", "malo"):
            nombre = f"caso-{caso}-v2-" + ("sin-senal" if lado == "bueno" else "con-senal") + ".xlsx"
            cambios = dict(buenos) if lado == "bueno" else {}
            formulas = {}
            hoja = None
            if caso == 5:
                hoja = "Grupos_sinteticos"
                cambios.update(A1="grupo_sintetico", **{f"A{i}": f"GRUPO-{i - 1:03}" for i in range(2, 6)})
                if lado == "bueno":
                    formulas = {
                        "G4": "C4*0.15+D4*0.15+E4*0.2+F4*0.5",
                        "H3": 'IF(AND(G3>=7,B3>=0.75),"PROMOCIONA",IF(AND(G3>=4,B3>=0.6),"REGULAR","LIBRE"))',
                    }
            nota = "Par controlado: misma base y solo cambios necesarios para ilustrar el control. Una señal requiere contexto; no es prueba de error."
            if caso == 5:
                nota += " Las puntuaciones y asistencia representan promedios de grupos sintéticos; la condición es una etiqueta simulada para probar fórmulas, no una decisión sobre estudiantes. En G4 ambos métodos dan 7; en H3 el patrón da REGULAR."
            if caso == 8:
                nota += (
                    " Asociación lineal débil bajo el umbral, sin afirmar ausencia de relación."
                    if lado == "bueno"
                    else " Asociación exploratoria fuerte; no prueba causalidad ni que la relación sea espuria."
                )
            clonar(base, nombre, cambios, formulas, hoja, nota)
            item = por_caso[caso][lado]
            item["archivo"] = "/samples/" + nombre
            item["descripcion"] = nota
    for item in manifest:
        if item["orden"] in (4, 6, 7, 8):
            item["estado"] = "sin_senal" if item["columna"] == "bueno" else "con_senal"
        if item["orden"] == 4 and item["columna"] == "bueno":
            item["nombre"] = "Acumulados sin retrocesos"
        if item["orden"] == 5:
            item["tema"] = "Fórmulas sobre datos de grupos sintéticos"
        if item["orden"] == 7:
            item["caso"] = "7. Evolución dentro del archivo"
            nota = " No prueba Radiólogo: no se aportan preinformes. Importes mensuales, no acumulados."
            if nota not in item["descripcion"]:
                item["descripcion"] += nota
        if item["orden"] == 8:
            item["tema"] = "Asociación lineal: pregunta exploratoria, no error"
            item["nombre"] = (
                "Asociación bajo el umbral" if item["columna"] == "bueno" else "Asociación fuerte para explorar"
            )
    (SAMPLES / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
