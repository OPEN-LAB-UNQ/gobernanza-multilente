"""Familias adicionales permanentes; pares correctos/alterados con verdad conocida."""

import pytest

from scripts.ensayo_formatos import VARIANTES, comprobar, construir
from services.controles_excel.conciliacion import analizar, relaciones_cuadro
from tests.flujo_confirmado import cargar_confirmado


@pytest.mark.parametrize("semilla", (731, 1193, 2053))
@pytest.mark.parametrize("variante", VARIANTES)
@pytest.mark.parametrize("alterado", (False, True))
def test_formatos_adicionales(semilla, variante, alterado):
    raw, truth = construir(semilla, variante, alterado)
    resultado = comprobar(raw, truth, variante)
    assert not resultado["errores"], resultado


def serie(etiqueta, fila, valores, nivel=0):
    return {
        "etiqueta": etiqueta,
        "archivo": "sintetico.xlsx",
        "hoja": "Cuadro",
        "cuadro": 1,
        "nivel": nivel,
        "valores": valores,
        "periodos": list(range(2018, 2024)),
        "celdas": [f"{c}{fila}" for c in "BCDEFG"],
    }


def test_total_inicial_no_suma_niveles_ni_cruza_otro_total():
    filas = [
        serie("Total", 2, [30] * 6),
        serie("Salud", 3, [10] * 6),
        serie("Detalle salud", 4, [10] * 6, 1),
        serie("Educación", 5, [20] * 6),
        serie("Subtotal siguiente", 6, [80] * 6),
        serie("Otro universo", 7, [80] * 6),
    ]
    candidato = next(x for x in relaciones_cuadro(filas) if x[2] == "total_precede_componentes")
    assert [x["etiqueta"] for x in candidato[1]] == ["Salud", "Educación"]


def test_nombre_total_no_basta_sin_corroboracion_en_otros_periodos():
    filas = [serie("Total", 2, [99] * 6), serie("Salud", 3, [10] * 6), serie("Educación", 4, [20] * 6)]
    assert analizar(filas) == []


pytest_plugins = ["tests.test_ejemplos_zip"]


@pytest.mark.parametrize("alterado", (False, True))
def test_total_primero_recorrido_carga_cola_y_resultado(flujo, alterado):
    import models
    from services import jobs

    client, factory, _ = flujo
    raw, truth = construir(731, "total_primero", alterado)
    r = cargar_confirmado(client, "/api/analisis-rapido",
        data={"periodo": "2026", "dominio": "general", "notificar": "false"},
        files={
            "archivos": ("total_antes.xlsx", raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        },
    )
    assert r.status_code == 200, r.text
    assert jobs._process_one()
    with factory() as db:
        informe = db.get(models.Informe, r.json()["informe_id"])
        eventos = [ev for h in informe.hallazgos for ev in [h.evidencia, *h.evidencia.get("conciliaciones", [])]]
        conciliaciones = [e for e in eventos if e.get("regla") == "conciliacion_aritmetica" and e.get("celda") == "D2"]
        assert bool(conciliaciones) == alterado
        if alterado:
            assert conciliaciones[0]["diferencia_absoluta"] == 1000
            assert conciliaciones[0]["origen_relacion"] == "total_precede_componentes"
