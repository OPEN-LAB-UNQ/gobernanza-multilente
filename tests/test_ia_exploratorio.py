"""6. Capa exploratoria: nombres, significación, redondeo, totales, relaciones derivadas,
contexto estructurado, preguntas genéricas, corridas y silencios."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from services import exploratorio

# Informe 264 (t1): rubros x años, fila Total y columna Código.
RUBROS_264 = [
    {"Código": 1100, "Rubro": "Personal", "2019": 1200.0, "2020": 1500.0, "2021": 2100.0, "2022": 3300.0, "2023": 5900.0},
    {"Código": 1200, "Rubro": "Servicios no personales", "2019": 400.0, "2020": 470.0, "2021": 610.0, "2022": 900.0, "2023": 1650.0},
    {"Código": 1210, "Rubro": "Servicios no personales (SNP) - mantenimiento", "2019": 80.0, "2020": 95.0, "2021": 120.0, "2022": 175.0, "2023": 320.0},
    {"Código": 1300, "Rubro": "Bienes de consumo", "2019": 150.0, "2020": 170.0, "2021": 230.0, "2022": 330.0, "2023": 600.0},
    {"Código": 1500, "Rubro": "Transferencias corrientes", "2019": 250.0, "2020": 340.0, "2021": 0.452, "2022": 620.0, "2023": 1100.0},
    {"Código": 1600, "Rubro": "Transferencias de capital", "2019": 90.0, "2020": 60.0, "2021": 30.0, "2022": 140.0, "2023": 260.0},
    {"Código": 9999, "Rubro": "Total", "2019": 2170.0, "2020": 2635.0, "2021": 3090.452, "2022": 5465.0, "2023": 9830.0},
]

# Informe 265 (t2): pendientes = consultas - resueltas (salvo dos filas).
CONSULTAS_265 = [
    {"area": a, "periodo": f"2026-0{m}", "consultas": c, "resueltas": r, "pendientes": c - r + (11 if (a, m) == ("Salud", 2) else 0), "codigo_area": 300 + i}
    for i, a in enumerate(["Atención ciudadana", "Salud", "Educación", "Obras"])
    for m, (c, r) in enumerate([(465, 395), (377, 320), (502, 426), (410, 351), (450, 380), (390, 333)], start=1)
]


def test_pista_b_excluye_total_codigos_y_pares_de_anios_264():
    analisis = exploratorio.analizar_correlaciones(SimpleNamespace(datos=RUBROS_264))
    assert analisis["pares"] == []
    assert analisis["filas_total_excluidas"] == 1
    assert analisis["excluidos"]["periodos_de_una_serie"] > 0
    hipotesis, avisos = exploratorio.generar_pista_b_con_avisos(SimpleNamespace(datos=RUBROS_264))
    assert hipotesis == [] and avisos and "No se generaron hipótesis" in avisos[0]


def test_pista_b_excluye_relaciones_aritmeticas_derivadas_265():
    pares = exploratorio.calcular_correlaciones(SimpleNamespace(datos=CONSULTAS_265))
    nombres = {frozenset((p["columna_a"], p["columna_b"])) for p in pares}
    assert not nombres & {frozenset(("consultas", "pendientes")), frozenset(("resueltas", "pendientes")), frozenset(("consultas", "resueltas"))}


def test_pista_b_no_muestra_0999_por_redondeo():
    datos = [{"a": float(i), "b": i * 2.0 + (0.25 if i % 2 else -0.25)} for i in range(1, 9)]
    r = exploratorio._pearson([d["a"] for d in datos], [d["b"] for d in datos])
    assert r < 0.999 and round(r, 3) == 0.999  # antes pasaba el filtro y se mostraba como 0.999
    assert exploratorio.calcular_correlaciones(SimpleNamespace(datos=datos)) == []


def _par_redactado(monkeypatch, texto):
    datos = [{"poblacion": p, "matricula": m} for p, m in [(10, 3), (12, 5), (15, 4), (18, 7), (20, 6), (25, 9), (27, 8), (30, 12)]]
    monkeypatch.setattr(exploratorio, "_redactar_correlacion_con_modelo",
                        lambda par: {"modelo": "gpt", "version": "v", "texto": texto.format(**par), "error": None})
    return exploratorio.generar_pista_b_con_avisos(SimpleNamespace(datos=datos))


def test_redaccion_que_pierde_nombres_o_afirma_significacion_usa_plantilla(monkeypatch):
    hipotesis, avisos = _par_redactado(monkeypatch, "Se observó una correlación estadísticamente significativa de {r} entre la variable A y la variable B.")
    assert hipotesis[0]["modelo"] == "plantilla_determinista"
    texto = hipotesis[0]["texto_hipotesis"]
    assert "'poblacion'" in texto and "'matricula'" in texto and "sin prueba de significación" in texto
    assert "significativa" not in texto
    assert any("variable A/B" in a and "significación" in a for a in avisos)


def test_redaccion_valida_conserva_nombres_y_aclara_muestra_chica(monkeypatch):
    hipotesis, avisos = _par_redactado(monkeypatch, "'poblacion' y 'matricula' se mueven juntas (r = {r}, {n} observaciones); una correlación no implica causalidad.")
    assert hipotesis[0]["modelo"] == "gpt" and "Muestra chica" in hipotesis[0]["texto_hipotesis"]
    assert avisos == []


def test_pista_a_recibe_estructura_y_descarta_preguntas_genericas(monkeypatch):
    informe = SimpleNamespace(periodo="2021-2023", dominio="educacion", datos=[{"Nivel": "Inicial", "2021": 50}],
                              saneamiento={"contexto_semantico": {"elementos": [
                                  {"hoja": "Salta", "rol": "nombre_hoja", "texto": "Salta"},
                                  {"hoja": "Salta", "rol": "titulo_subtitulo_nota", "texto": "Matrícula escolar por nivel — Provincia de Corrientes"},
                                  {"hoja": "Salta", "rol": "unidad", "texto": "En alumnos"},
                                  {"hoja": "Salta", "rol": "fuente", "texto": "Fuente: instituto de estadística"}]}})
    contexto = exploratorio._contexto_informe(informe)
    assert contexto["estructura"][0]["titulos"] == ["Matrícula escolar por nivel — Provincia de Corrientes"]
    assert contexto["estructura"][0]["unidades"] == ["En alumnos"] and contexto["estructura"][0]["fuentes"] == ["Fuente: instituto de estadística"]
    respuesta = "\n".join([
        "¿Cómo se ha comunicado internamente el informe para facilitar su comprensión?",
        "¿Existe retroalimentación de los usuarios finales del informe?",
        "¿Por qué la hoja Salta lleva un título referido a Corrientes?",
        "¿El nivel Inicial se mide en alumnos en todas las provincias?",
    ])
    monkeypatch.setattr(exploratorio, "_llamar_modelo_pista_a", lambda ctx: {"modelo": "gpt", "version": "v", "texto": respuesta, "error": None})
    hipotesis, error, avisos = exploratorio.generar_pista_a_con_avisos(informe)
    assert error is None
    assert [h["texto_hipotesis"] for h in hipotesis] == [
        "¿Por qué la hoja Salta lleva un título referido a Corrientes?",
        "¿El nivel Inicial se mide en alumnos en todas las provincias?",
    ]
    assert any("2 preguntas descartadas por genéricas" in a for a in avisos)


def test_dos_corridas_se_agrupan_por_separado():
    t0 = dt.datetime(2026, 10, 3, 17, 56, 50)
    filas = [SimpleNamespace(id=i, creado_en=t0 + dt.timedelta(microseconds=i)) for i in range(1, 6)]
    filas += [SimpleNamespace(id=10 + i, creado_en=t0 + dt.timedelta(minutes=12, microseconds=i)) for i in range(1, 6)]
    corridas = exploratorio.agrupar_corridas(filas)
    assert [c["cantidad"] for c in corridas] == [5, 5]
    assert corridas[0]["corrida"] == 2 and {h.id for h in corridas[0]["hipotesis"]} == {11, 12, 13, 14, 15}
