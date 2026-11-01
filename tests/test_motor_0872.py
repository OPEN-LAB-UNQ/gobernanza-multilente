"""multilente-0.8.72: notas de cobertura saneadas, cambio de escala entre ediciones,
sobreejecución en ambos ámbitos y transferencias entre rubros en cuadros cortos."""

import pytest

from services import ambito
from services.controles_excel import ediciones
from services.lentes import ajedrecista, conciliador

# 1. Notas de cobertura con datos personales ------------------------------------------

def test_nota_de_observaciones_no_se_copia_literal():
    datos = [
        {"Rubro": "Salud", "Monto": 10, "Observaciones": "Relevamiento desde 2019; consultar a Juan Pérez tel 11-4555-1234"},
        {"Rubro": "Obras", "Monto": 20, "Observaciones": ""},
    ]
    pistas = [p for p in conciliador._pistas_cobertura(datos) if p["tipo"] == "valor"]
    assert pistas and pistas[0]["detalle"] == "nota de cobertura en la fila 1"
    assert "Pérez" not in str(pistas) and "4555" not in str(pistas)


def test_nota_en_columna_de_persona_no_se_copia_literal():
    datos = [{"Rubro": "Salud", "Agente": "Carga parcial informada por María Gómez"}]
    pistas = [p for p in conciliador._pistas_cobertura(datos) if p["tipo"] == "valor"]
    assert pistas and pistas[0]["detalle"] == "nota de cobertura en la fila 1"


def test_nota_en_otra_columna_se_copia_saneada():
    datos = [{"Rubro": "Salud", "Fuente": "Dato preliminar, consultas a datos@ministerio.gob.ar o DNI 20123456"}]
    pistas = [p for p in conciliador._pistas_cobertura(datos) if p["tipo"] == "valor"]
    assert pistas
    detalle = pistas[0]["detalle"]
    assert "Dato preliminar" in detalle
    assert "[EMAIL_REDACTADO]" in detalle and "[DNI_REDACTADO]" in detalle
    assert "@" not in detalle and "20123456" not in detalle


def test_evidencia_del_conciliador_no_lleva_la_nota():
    datos = [
        {"Rubro": "Salud", "A": 1.0, "B": 2.0, "C": 3.0, "Notas": "Cobertura parcial, ver con Juan Pérez"},
        {"Rubro": "Obras", "A": 1.0, "B": 2.0, "C": 3.0, "Notas": ""},
    ]
    general = conciliador.analizar(datos)["hallazgo_general"]
    assert general and "Pérez" not in str(general)


# 2. Cambio de escala entre ediciones --------------------------------------------------

ANIOS_ANT = list(range(2016, 2023))
ANIOS_NUE = list(range(2016, 2024))
SALUD = [100.0, 130.0, 170.0, 220.0, 290.0, 380.0, 450.0]
EDUC = [500.0, 640.0, 820.0, 1050.0, 1350.0, 1700.0, 2100.0]
OBRAS = [300.0, 310.0, 330.0, 360.0, 420.0, 480.0, 520.0]


def _serie(archivo, etiqueta, fila, periodos, valores, cuadro=1):
    return {
        "archivo": archivo, "hoja": "Cuadro", "cuadro": cuadro, "etiqueta": etiqueta, "fila": fila,
        "nivel": 0, "periodos": periodos, "valores": valores,
        "celdas": [f"{chr(66 + i)}{fila}" for i in range(len(periodos))],
    }


def _ediciones(salud_nueva, educ_nueva=None, anios_ant=ANIOS_ANT, anios_nue=ANIOS_NUE):
    n = len(anios_ant)
    ant = [
        _serie("ed_2022.xlsx", "Salud", 2, anios_ant, SALUD[:n]),
        _serie("ed_2022.xlsx", "Educación", 3, anios_ant, EDUC[:n]),
        _serie("ed_2022.xlsx", "Obras", 4, anios_ant, OBRAS[:n]),
    ]
    nue = [
        _serie("ed_2023.xlsx", "Salud", 2, anios_nue, salud_nueva),
        _serie("ed_2023.xlsx", "Educación", 3, anios_nue, educ_nueva or EDUC[:n] + [2500.0]),
        _serie("ed_2023.xlsx", "Obras", 4, anios_nue, OBRAS[:n] + [560.0]),
    ]
    return ediciones.analizar(ant + nue)


def _regla(hs, regla):
    return [h for h in hs if h["evidencia"]["regla"] == regla]


@pytest.mark.parametrize("factor", [0.001, 1000.0, 0.01, 10.0])
def test_fila_en_otra_escala_se_rotula_cambio_de_escala(factor):
    hs = _ediciones([v * factor for v in SALUD] + [500.0 * factor])
    escala = _regla(hs, "cambio_de_escala_entre_ediciones")
    assert len(escala) == 1
    ev = escala[0]["evidencia"]
    assert ev["indicador"] == "Salud" and ev["factor_escala"] == factor
    assert ev["puntaje_prioridad"] > 100 and escala[0]["severidad"] == "alta"
    assert "Cambio de escala" in escala[0]["descripcion"]
    assert not _regla(hs, "serie_revisada_entre_ediciones")


def test_filas_con_formula_que_cambian_por_arrastre_no_ocultan_el_cambio_de_escala():
    # «Resto» se calcula con fórmula a partir de Salud: cambia con ella, pero no es un cambio propio.
    n = len(ANIOS_ANT)
    resto_ant = [e - s for e, s in zip(EDUC, SALUD)]
    salud_nueva = [v / 1000 for v in SALUD] + [0.5]
    resto_nuevo = [e - s for e, s in zip(EDUC + [2500.0], salud_nueva)]
    ant = [
        _serie("ed_2022.xlsx", "Salud", 2, ANIOS_ANT, SALUD[:n]),
        _serie("ed_2022.xlsx", "Educación", 3, ANIOS_ANT, EDUC[:n]),
        _serie("ed_2022.xlsx", "Resto", 4, ANIOS_ANT, resto_ant[:n]),
    ]
    resto = _serie("ed_2023.xlsx", "Resto", 4, ANIOS_NUE, resto_nuevo)
    resto["formulas"] = [True] * len(ANIOS_NUE)
    nue = [
        _serie("ed_2023.xlsx", "Salud", 2, ANIOS_NUE, salud_nueva),
        _serie("ed_2023.xlsx", "Educación", 3, ANIOS_NUE, EDUC[:n] + [2500.0]),
        resto,
    ]
    escala = _regla(ediciones.analizar(ant + nue), "cambio_de_escala_entre_ediciones")
    assert [h["evidencia"]["indicador"] for h in escala] == ["Salud"]


def test_cambio_de_escala_con_tres_anios_comunes():
    anios_ant, anios_nue = [2019, 2020, 2021, 2022], [2019, 2020, 2021, 2022, 2023]
    hs = _ediciones([v / 1000 for v in SALUD[:4]] + [0.5], anios_ant=anios_ant, anios_nue=anios_nue,
                    educ_nueva=EDUC[:4] + [2500.0])
    assert len(_regla(hs, "cambio_de_escala_entre_ediciones")) == 1


def test_escala_con_ruido_mayor_a_1_por_ciento_no_es_cambio_de_escala():
    salud = [v / 1000 * (1.03 if i % 2 else 0.97) for i, v in enumerate(SALUD)] + [0.5]
    hs = _ediciones(salud)
    assert not _regla(hs, "cambio_de_escala_entre_ediciones")
    assert _regla(hs, "serie_revisada_entre_ediciones")


def test_cuadro_reexpresado_completo_sigue_siendo_revision():
    hs = _ediciones([v * 1000 for v in SALUD] + [5e5], educ_nueva=[v * 1.1 for v in EDUC] + [2500.0])
    assert not _regla(hs, "cambio_de_escala_entre_ediciones")
    assert _regla(hs, "serie_revisada_entre_ediciones")


def test_revision_que_no_es_potencia_de_10_no_cambia():
    hs = _ediciones([v * 1.1 for v in SALUD] + [500.0])
    assert not _regla(hs, "cambio_de_escala_entre_ediciones")
    assert _regla(hs, "serie_revisada_entre_ediciones")[0]["evidencia"]["puntaje_prioridad"] == 75


# 3. Presupuesto contra ejecutado en ambos ámbitos -------------------------------------

def _tabla(real="Ejecutado", presupuesto="Presupuesto"):
    return [
        {"Programa": "Salud", presupuesto: 1000.0, real: 1250.0},
        {"Programa": "Obras", presupuesto: 2000.0, real: 2100.0},
        {"Programa": "Educación", presupuesto: 500.0, real: 480.0},
        {"Programa": "Ventas de servicios", presupuesto: 100.0, real: 300.0},
        {"Programa": "Total", presupuesto: 3600.0, real: 4130.0},
    ]


def _imposibilidad(datos, amb):
    testigo = ambito.declarar(amb)
    try:
        return ajedrecista.imposibilidad(datos)
    finally:
        ambito.restaurar(testigo)


def _sobre(hs):
    return [h for h in hs if h["evidencia"]["regla"] == "gasto_real_supera_presupuesto"]


@pytest.mark.parametrize("real", ["Ejecutado", "Real"])
@pytest.mark.parametrize("presupuesto", ["Presupuesto", "Presupuestado"])
def test_sobreejecucion_fuerte_en_organizacion(real, presupuesto):
    hs = _sobre(_imposibilidad(_tabla(real, presupuesto), "organizacion"))
    assert len(hs) == 1
    ev = hs[0]["evidencia"]
    # Salud (+25 %) sí; Obras (+5 %) no llega al 10 %; ni ingresos ni el total.
    assert ev["filas"] == [0]
    assert ev["muestras"][0]["rubro"] == "Salud"
    assert "egreso" not in ev["muestras"][0]


def test_sobreejecucion_con_columna_real_en_publico():
    hs = _sobre(_imposibilidad(_tabla("Real"), "publico"))
    assert len(hs) == 1 and hs[0]["evidencia"]["filas"] == [0]


def test_publico_con_ejecutado_no_duplica_devengado_supera_vigente():
    hs = _imposibilidad(_tabla("Ejecutado"), "publico")
    assert not _sobre(hs)
    assert [h for h in hs if h["evidencia"]["regla"] == "devengado_supera_vigente"]


def test_columnas_sin_rotulo_explicito_mantienen_la_regla_de_egresos():
    datos = [
        {"Rubro": "Salud", "Plan": 1000.0, "Actual": 1500.0},
        {"Rubro": "Gastos de personal", "Plan": 1000.0, "Actual": 1010.0},
    ]
    hs = _sobre(_imposibilidad(datos, "organizacion"))
    assert len(hs) == 1 and hs[0]["evidencia"]["filas"] == [1]
    assert "de egreso" in hs[0]["descripcion"]
    assert not _sobre(_imposibilidad(datos, "publico"))


# 4. Transferencias entre rubros en cuadros cortos -------------------------------------

from services.controles_excel import compensados  # noqa: E402

ANIOS_CORTOS = [2019, 2020, 2021, 2022]
RUBROS_CORTOS = {
    "Salud": [1000.0, 1450.0, 2200.0, 3300.0],
    "Educación": [2000.0, 2950.0, 4400.0, 6500.0],
    "Obras": [800.0, 1180.0, 1750.0, 2650.0],
    "Vivienda": [500.0, 740.0, 1100.0, 1640.0],
}


def _cuadro_corto(rubros):
    filas = [_serie("corto.xlsx", nombre, 2 + k, ANIOS_CORTOS, list(vs)) for k, (nombre, vs) in enumerate(rubros.items())]
    total = [sum(vs[i] for vs in rubros.values()) for i in range(len(ANIOS_CORTOS))]
    filas.append(_serie("corto.xlsx", "Total", 2 + len(rubros), ANIOS_CORTOS, total))
    return filas


def _compensados(hs):
    return [h for h in hs if h["evidencia"]["regla"] == "movimiento_compensado"]


def test_transferencia_en_cuadro_de_cuatro_anios_se_detecta():
    rubros = {k: list(v) for k, v in RUBROS_CORTOS.items()}
    movido = 0.6 * rubros["Obras"][1]
    rubros["Obras"][1] -= movido
    rubros["Educación"][1] += movido
    hs = _compensados(compensados.analizar(_cuadro_corto(rubros)))
    assert len(hs) == 1
    celdas = " ".join(hs[0]["evidencia"]["celdas_participantes"])
    assert "C3" in celdas and "C4" in celdas  # Educación y Obras en 2020


def test_cuadro_corto_sin_transferencia_no_se_marca():
    assert not _compensados(compensados.analizar(_cuadro_corto(RUBROS_CORTOS)))


def test_cuadro_corto_con_participaciones_ruidosas_no_se_marca():
    # Rubros que cambian mucho de participación todos los años: un movimiento parecido es habitual.
    rubros = {
        "Salud": [1000.0, 1900.0, 1700.0, 3900.0],
        "Educación": [2000.0, 2300.0, 5200.0, 5200.0],
        "Obras": [800.0, 1500.0, 1200.0, 3100.0],
        "Vivienda": [500.0, 400.0, 1300.0, 900.0],
    }
    rubros["Obras"][1] -= 300.0
    rubros["Educación"][1] += 300.0
    assert not _compensados(compensados.analizar(_cuadro_corto(rubros)))
