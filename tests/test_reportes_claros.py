from types import SimpleNamespace

import pytest

from services.reporte_ejecutivo import corto
from services.reportes import markdown as m


@pytest.mark.parametrize(
    "estado,parcial,esperado",
    [
        ("no_evaluable", False, "sin evaluar"),
        ("informado", True, "parcialmente"),
        ("conforme", False, "fueron ejecutados"),
    ],
)
def test_estado_consulta_primero_aunque_haya_senales(estado, parcial, esperado):
    control = {
        "nombre": "Suma mensual",
        "estado": estado,
        "cobertura_parcial": parcial,
        "resultado": "Resultado preciso",
    }
    informe = SimpleNamespace(
        saneamiento={"orientacion_analisis": "Verificar suma", "controles_solicitados": {"controles": [control]}},
        devolucion=None,
    )
    salida = m._encabezar_consulta("# Reporte\n## Cómo leer\nDetalle", informe, [object()])
    assert salida.index(esperado) < salida.index("## Cómo leer")
    assert "Resultado preciso" in salida and "1 señal para revisar" in salida


def test_pregunta_sin_control_no_se_presenta_como_resuelta():
    informe = SimpleNamespace(saneamiento={"orientacion_analisis": "Revisar los plazos"}, devolucion=None)
    salida = m._encabezar_consulta("# Reporte\nDetalle", informe, [])
    assert "No hay una evaluación específica registrada" in salida


def test_resumen_no_corta_evidencia_ni_conclusion():
    frase = "Importaciones y exportaciones se mueven juntas: " + "Se debe contrastar con la fuente. " * 20
    assert corto(frase).endswith("Se debe contrastar con la fuente.")
    assert "Importaciones y exportaciones" in corto(frase)


def test_rizoma_no_inventa_contexto_comercial(monkeypatch):
    from services.lentes import rizoma

    monkeypatch.setattr(
        rizoma, "evaluar_relaciones", lambda datos: [{"columnas": ["Serie A", "Serie B"], "coeficiente_pearson": 0.99}]
    )
    h = rizoma.analizar([{}] * rizoma.CORRELACION_MIN_N)[0]
    texto = str(h)
    assert "turismo" not in texto and "promociones" not in texto and "puntos de venta" not in texto
    assert "metodología" in texto


def test_sin_series_por_periodo_el_reporte_dice_que_filas_entraron():
    """No medir la cobertura de series no autoriza a callar cuánto del archivo se incorporó."""
    resumen = [
        "Excel: 1 de 2 hojas con datos incorporados.",
        "archivo.xlsx · Avances: 5 filas incorporadas, 1 cuadros.",
        "archivo.xlsx · Guia: 0 filas incorporadas, 0 cuadros. Sin filas cuantitativas.",
    ]
    informe = SimpleNamespace(
        saneamiento={},
        devolucion=SimpleNamespace(cobertura={"excel": {"lectura": {}}, "excel_resumen": resumen}),
    )
    salida = m._lineas_lectura_reporte(informe)
    assert any("1 de 2 hojas con datos incorporados" in x for x in salida)
    assert any("5 filas incorporadas" in x for x in salida)
    assert not any("0 %" in x for x in salida)


def test_con_series_por_periodo_no_se_repite_el_detalle_de_hojas():
    informe = SimpleNamespace(
        saneamiento={},
        devolucion=SimpleNamespace(
            cobertura={
                "excel": {"lectura": {"series_leidas": 8, "series_aparentes": 8, "estado": "completa", "archivos": []}},
                "excel_resumen": ["Excel: 1 de 1 hojas con datos incorporados."],
            }
        ),
    )
    salida = m._lineas_lectura_reporte(informe)
    assert any("8 de las 8 series" in x for x in salida)
    assert not any("hojas con datos incorporados" in x for x in salida)


def test_pregunta_no_evaluada_es_la_primera_linea_del_reporte():
    """Si la consulta no pudo evaluarse, eso es el resultado: no puede quedar en la sección 2."""
    informe = SimpleNamespace(
        saneamiento={"orientacion_analisis": "Verificar que CIF = FOB + flete + seguro"},
        devolucion=SimpleNamespace(cobertura={"estado": "PREGUNTA_NO_EVALUADA", "lentes": []}),
    )
    salida = m._encabezar_consulta("# Reporte de apoyo\n## Cómo leer\nDetalle", informe, [object()] * 5)
    assert "no pudo evaluarse con la estructura disponible" in salida
    assert salida.index("no pudo evaluarse") < salida.index("## Cómo leer")
    assert "no responden la consulta" in salida


def test_consulta_evaluada_no_se_declara_sin_evaluar():
    informe = SimpleNamespace(
        saneamiento={"orientacion_analisis": "Verificar suma", "controles_solicitados": {"controles": [
            {"nombre": "Suma", "estado": "conforme", "resultado": "Cierra en todos los períodos"}]}},
        devolucion=SimpleNamespace(cobertura={"estado": "CON_SENALES_COMUNICABLES", "lentes": []}),
    )
    salida = m._encabezar_consulta("# Reporte\n## Cómo leer\nDetalle", informe, [object()])
    assert "no pudo evaluarse" not in salida and "fueron ejecutados" in salida


def test_el_resumen_no_muestra_los_nombres_internos_de_las_lentes():
    """«rizoma» o «cronista» no le dicen nada a quien lee: van sus nombres de pantalla."""
    from services import reporte_ejecutivo as r

    assert r._lente_legible("rizoma") == "Conexiones exploratorias"
    assert r._lente_legible("cronista") == "Evolución temporal"
    assert r._lente_legible("matematico") == "Cálculos y métodos"
    assert r._lente_legible(None) == "—"
    assert r._regla_legible({"regla": "corte_temporal"}, "cronista") == "corte temporal"
    assert r._regla_legible({}, "rizoma") == "Conexiones exploratorias"


def test_los_conteos_se_escriben_como_los_lee_una_persona():
    """«1 señal(es)» y «0 registros de señales; .» son restos de plantilla, no lenguaje."""
    from services.reporte_ejecutivo import senales

    assert senales(0) == "sin señales"
    assert senales(1) == "1 señal"
    assert senales(4) == "4 señales"


def test_el_indice_del_anexo_pone_la_huella_al_final_y_rotulada():
    """La huella sirve para comparar corridas: se conserva, pero no encabeza la línea."""
    from services.reporte_ejecutivo import anexo_contexto

    hallazgo = {
        "id": 1, "lente": "rizoma", "modo": "exploratorio", "severidad": "media",
        "descripcion": "Dos series se mueven juntas.", "evidencia": {"naturaleza": "exploratoria"},
        "pregunta_institucional": "",
    }
    lineas = anexo_contexto([SimpleNamespace(**hallazgo)])
    indice = [x for x in lineas if x.startswith("- ")]
    assert indice and not indice[0].startswith("- caso-")
    assert "Conexiones exploratorias" in indice[0]
    assert "Referencia técnica: caso-" in indice[0]
    assert "None!None" not in indice[0] and "1 señal." in indice[0]
