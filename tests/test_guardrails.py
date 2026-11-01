"""Tests de guardrails (lenguaje y estructura de hallazgos) y sanitizacion."""
from __future__ import annotations

from services import guardrails, sanitizacion, triangulacion


class DummyInforme:
    datos = [{"periodo": "2026-01", "valor": 100}]
    saneamiento = {
        "opciones_tecnicas": {"revisar_formulas_excel": False},
        "columnas_excluidas": ["proveedor"],
    }



def test_guardrails_lenguaje_y_estructura():
    hallazgo = guardrails.normalizar_hallazgo({
        "lente": "rizoma",
        "modo": "exploratorio",
        "descripcion": "fraude sospechoso de partido por correlacion",
        "severidad": "alta",
        "evidencia": {"columnas": ["a", "b"]},
    })
    texto = hallazgo["descripcion"].lower()
    assert "fraude" not in texto
    assert "sospech" not in texto
    assert "partido" not in texto
    assert hallazgo["tipo_evidencia"] == "ASOCIACION_EXPLORATORIA"
    assert hallazgo["incertidumbre"] == "alta"
    assert hallazgo["limites"]["no_afirma_causalidad"] is True


def test_guardrails_protege_vocabulario_legitimo_del_dominio():
    """"sancion"/"violacion" en su forma acusatoria se siguen neutralizando,
    pero frases de vocabulario presupuestario estandar no se deforman."""
    texto = guardrails.sanitizar_texto(
        "El credito vigente difiere del monto sancionado por la ley de "
        "presupuesto sancionada, y ademas hubo una sancion disciplinaria "
        "por violacion del reglamento."
    )
    assert "ley de presupuesto sancionada" in texto
    assert "monto sancionado" in texto
    assert "sancion disciplinaria" not in texto
    assert "violacion del reglamento" not in texto

    texto_desvio = triangulacion.sanitizar_lenguaje(
        "El valor se aleja 3,5 desvios estandar del banco historico, lo cual "
        "resulta sospechoso."
    )
    assert "desvios estandar" in texto_desvio
    assert "sospechoso" not in texto_desvio


def test_cobertura_sin_senales():
    cobertura = guardrails.cobertura_informe(DummyInforme(), [])
    assert cobertura["estado"] == guardrails.ESTADO_SIN_SENALES
    assert len(cobertura["lentes"]) == 7
    assert cobertura["columnas_excluidas"] == ["proveedor"]


def test_sanitizacion_agregada():
    datos = [{"proveedor": "ACME", "factura": "F-1", "programa": "A", "monto_total": 10}]
    saneados, reporte = sanitizacion.sanear(datos)
    assert "proveedor" not in saneados[0]
    assert "factura" not in saneados[0]
    assert saneados[0]["programa"] == "A"
    assert reporte["columnas_excluidas"]


def test_sanitizacion_no_redacta_codigos_ni_montos_como_dni():
    """Regresion: un codigo de programa o un monto de 7-8 digitos en una
    columna agregada no debe confundirse con un DNI sin etiqueta."""
    datos = [{"programa": "Programa 1234567", "observaciones": "credito vigente 3500000 pesos"}]
    saneados, reporte = sanitizacion.sanear(datos)
    assert saneados[0]["programa"] == "Programa 1234567"
    assert saneados[0]["observaciones"] == "credito vigente 3500000 pesos"
    assert reporte["valores_redactados"] == 0


def test_sanitizacion_redacta_cuit_con_guiones_sin_necesitar_etiqueta():
    datos = [{"observaciones": "contacto registrado 20-12345678-9"}]
    saneados, reporte = sanitizacion.sanear(datos)
    assert "[CUIT_REDACTADO]" in saneados[0]["observaciones"]
    assert reporte["valores_redactados"] == 1
    assert reporte["redacciones_por_columna"] == {"observaciones": 1}


def test_sanitizacion_redacta_dni_y_cuit_solo_cuando_estan_etiquetados():
    datos = [{"observaciones": "DNI 30123456 - CUIT 20123456789"}]
    saneados, reporte = sanitizacion.sanear(datos)
    texto = saneados[0]["observaciones"]
    assert "[DNI_REDACTADO]" in texto
    assert "[CUIT_REDACTADO]" in texto
    assert reporte["redacciones_por_columna"] == {"observaciones": 1}


def test_pregunta_institucional_no_filtra_slug_tecnico_como_detalle():
    """Regresion: cuando un hallazgo (p.ej. el general del Conciliador) no
    trae fila_detalle/celda/serie/columnas/columna_detalle/columna ni notas
    de cobertura, _detalle() no debe caer en evidencia['regla'] -- ese es un
    identificador tecnico en snake_case (p.ej. "conciliacion_tecnica_previa")
    que no es una frase legible. Tiene que caer en el generico "la señal
    indicada". Bug real detectado analizando incorrecto-acumulado-retrocede.xlsx:
    salia "Indicar si conciliacion_tecnica_previa se explica por carga...".
    """
    hallazgo = guardrails.normalizar_hallazgo({
        "lente": "conciliador",
        "modo": "conciliacion",
        "descripcion": "contexto tecnico de ejemplo",
        "severidad": "media",
        "evidencia": {"regla": "conciliacion_tecnica_previa"},
    })
    pregunta = hallazgo["pregunta_institucional"]
    assert "conciliacion_tecnica_previa" not in pregunta
    assert "la señal indicada" in pregunta
