"""Tests de la lente Matematico."""
from __future__ import annotations

import io

from openpyxl import Workbook

from services import formula_integridad
from services.lentes import matematico


def test_matematico_benford_detecta_distribucion_artificial():
    """Serie angosta y artificial (todos los valores entre 480 y 520):
    concentra el primer digito en 4 y 5, lejos de lo esperado por Benford.
    Debe comunicarse como hipotesis exploratoria (severidad baja,
    incertidumbre alta), nunca como conclusion."""
    import random

    random.seed(7)
    datos = [{"monto": random.uniform(480, 520)} for _ in range(200)]
    hallazgos = matematico.analizar(datos)
    benford = [h for h in hallazgos if h["evidencia"].get("regla") == "primer_digito_no_conforme_benford"]
    assert benford
    assert benford[0]["severidad"] == "baja"
    assert benford[0]["incertidumbre"] == "alta"
    assert benford[0]["evidencia"]["n"] == 200


def test_matematico_benford_no_falso_positivo_con_distribucion_natural():
    """Calibracion: una serie generada con amplitud de magnitud natural
    (log-uniforme entre 1 y 10 millones, como se generan los datasets de
    referencia en la literatura de Benford) no deberia dispararse."""
    import random

    random.seed(7)
    datos = [{"monto": 10 ** random.uniform(0, 7)} for _ in range(400)]
    hallazgos = matematico.analizar(datos)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "primer_digito_no_conforme_benford"]


def test_matematico_benford_no_corre_con_pocos_datos():
    """Calibracion/alcance: por debajo de BENFORD_MIN_N (50) no debe
    activarse aunque la distribucion sea muy artificial -- no hay evidencia
    suficiente para una lectura estadistica, ni exploratoria."""
    import random

    random.seed(7)
    datos = [{"monto": random.uniform(480, 520)} for _ in range(30)]
    hallazgos = matematico.analizar(datos)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "primer_digito_no_conforme_benford"]


def test_matematico_benford_ignora_columnas_periodo():
    import random

    random.seed(7)
    datos = [{"2025*": random.uniform(480, 520)} for _ in range(200)]
    hallazgos = matematico.analizar(datos)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "primer_digito_no_conforme_benford"]


def _workbook_bytes(filas, con_ponderador_en_texto: bool) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Notas" if con_ponderador_en_texto else "Resumen"
    encabezado = ["Materia", "Creditos", "Nota 1", "Nota 2", "Promedio"] if con_ponderador_en_texto else ["Item", "Enero", "Febrero", "Promedio"]
    ws.append(encabezado)
    for i in range(2, 2 + filas):
        if con_ponderador_en_texto:
            ws.cell(i, 1, f"Materia {i}")
            ws.cell(i, 2, i)
            ws.cell(i, 3, 7)
            ws.cell(i, 4, 9)
            ws.cell(i, 5, f"=PROMEDIO(C{i}:D{i})")
        else:
            ws.cell(i, 1, f"Item {i}")
            ws.cell(i, 2, 100 + i)
            ws.cell(i, 3, 90 + i)
            ws.cell(i, 4, f"=PROMEDIO(B{i}:C{i})")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def test_matematico_sin_falsos_positivos_sin_mencion_de_ponderadores():
    """Calibracion: la regla solo se activa si la hoja menciona creditos,
    horas, pesos u otro ponderador posible en el texto. Sin esa mencion,
    un promedio simple no deberia comunicarse."""
    contenido = _workbook_bytes(4, con_ponderador_en_texto=False)
    hallazgos = formula_integridad.analizar_matematico_archivo("resumen.xlsx", contenido)
    assert hallazgos == []


def test_matematico_detecta_cambio_criterio_ponderado_sin_formula():
    from openpyxl import Workbook
    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append([
        "periodo", "materia",
        "promedio_trabajos", "peso_trabajos",
        "promedio_parcial", "peso_parcial",
        "promedio_final", "peso_final",
        "promedio_informado", "criterio_declarado",
    ])
    ws.append(["2026-03", "Matematica", 8.0, 0.2, 7.0, 0.3, 6.0, 0.5, 6.7, "Promedio ponderado 20/30/50"])
    ws.append(["2026-04", "Lengua", 9.0, 0.2, 7.0, 0.3, 5.0, 0.5, 7.0, "Promedio ponderado 20/30/50"])
    wb.save(buf)
    hallazgos = formula_integridad.analizar_matematico_archivo("notas.xlsx", buf.getvalue())
    assert any(h["evidencia"]["regla"] == "promedio_informado_simple_con_ponderadores" for h in hallazgos)


def test_matematico_no_marca_si_informado_respeta_ponderado():
    from openpyxl import Workbook
    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append([
        "periodo", "materia",
        "promedio_trabajos", "peso_trabajos",
        "promedio_parcial", "peso_parcial",
        "promedio_final", "peso_final",
        "promedio_informado", "criterio_declarado",
    ])
    ws.append(["2026-03", "Matematica", 8.0, 0.2, 7.0, 0.3, 6.0, 0.5, 6.7, "Promedio ponderado 20/30/50"])
    ws.append(["2026-04", "Lengua", 9.0, 0.2, 7.0, 0.3, 5.0, 0.5, 6.8, "Promedio ponderado 20/30/50"])
    wb.save(buf)
    hallazgos = formula_integridad.analizar_matematico_archivo("notas.xlsx", buf.getvalue())
    assert not any(h["evidencia"].get("regla") == "promedio_informado_simple_con_ponderadores" for h in hallazgos)


def test_matematico_no_se_autoreferencia_como_componente_de_si_mismo():
    """Bug real encontrado en revision: una columna target (p.ej. 'Promedio
    Final') no debe colarse como componente de ningun promedio ponderado --
    "final"/"oficial" son ambiguos por nombre (examen final vs. promedio
    final), asi que la desambiguacion es estructural: solo es componente si
    tiene una columna de peso propia emparejada."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["periodo", "promedio_trabajos", "peso_trabajos", "promedio_parcial", "peso_parcial", "promedio_final"])
    ws.append(["2026-03", 8.0, 0.2, 7.0, 0.8, 7.5])
    ws.append(["2026-04", 9.0, 0.2, 5.0, 0.8, 5.5])
    componentes = formula_integridad._mapear_componentes_ponderados(ws)
    assert not any(c["valor_nombre"] == "promedio_final" for c in componentes)


def test_matematico_promedio_simple():
    wb = Workbook()
    ws = wb.active
    ws.title = "Notas"
    ws.append(["Materia", "Creditos", "Nota 1", "Nota 2", "Promedio"])
    for i in range(2, 6):
        ws.cell(i, 1, f"Materia {i}")
        ws.cell(i, 2, i)
        ws.cell(i, 3, 7)
        ws.cell(i, 4, 9)
        ws.cell(i, 5, f"=PROMEDIO(C{i}:D{i})")
    buf = io.BytesIO()
    wb.save(buf)
    hallazgos = formula_integridad.analizar_matematico_archivo("notas.xlsx", buf.getvalue())
    assert hallazgos
    assert hallazgos[0]["modo"] == "pertinencia_calculo"


def test_benford_no_se_aplica_a_columnas_de_codigos():
    """Caso real: posición arancelaria (NCM) y país de origen (Porg) del archivo de importaciones.

    Son códigos: enteros encerrados en una misma escala. El primer dígito describe el nomenclador,
    no el registro de una cantidad, y la prueba no dice nada sobre los datos.
    """
    import random

    random.seed(11)
    ncm = [8123456, 84512300, 87032310, 30490000, 85171200]
    paises = [200, 203, 218, 504, 505, 600, 310]
    datos = [{"NCM": random.choice(ncm), "Porg": random.choice(paises)} for _ in range(300)]
    hallazgos = matematico.analizar(datos)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "primer_digito_no_conforme_benford"]


def test_benford_sigue_corriendo_sobre_importes_enteros_de_varias_escalas():
    """Un importe en unidades enteras que va de decenas a millones sí es una cantidad."""
    import random

    random.seed(11)
    datos = [{"monto": int(10 ** random.uniform(1, 6))} for _ in range(400)]
    matematico.analizar(datos)  # no debe quedar excluido por ser entero
    assert not matematico._es_nomenclador([float(f["monto"]) for f in datos])
