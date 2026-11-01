"""Planillas habituales de organizaciones (pyme, cooperativa, ONG): carga, filtro y signos.

Casos reproducidos en la revisión del 28/09/2026: un presupuesto vs real con título
no cargaba, el filtro borraba totales como «Clientes activos», los egresos en
negativo se marcaban como imposibles y una tasa se usaba como categoría.
"""
import io

import pytest
from openpyxl import Workbook

from services import ambito, carga_archivos, perfilado
from services.lentes import ajedrecista, cronista
from services.sanitizacion import columna_sensible, sanear


@pytest.fixture
def organizacion():
    testigo = ambito.declarar(ambito.ORGANIZACION)
    yield
    ambito.restaurar(testigo)


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    for fila in filas:
        ws.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_presupuesto_vs_real_con_titulo_encuentra_el_encabezado():
    contenido = _xlsx([
        ["Pyme Ejemplo S.R.L. — Presupuesto vs real 2025"],
        [],
        ["Concepto", "Presupuesto", "Real", "Desvío"],
        ["Ventas", 1000, 1100, 100],
        ["Costo de ventas", 600, 650, 50],
        ["Gastos de administración", 200, 210, 10],
        ["Gastos comerciales", 100, 90, -10],
    ])
    assert carga_archivos._detectar_filas_encabezado(contenido) == [2]


@pytest.mark.parametrize("nombre", [
    "Clientes activos", "Cantidad de beneficiarios", "Beneficiarios atendidos", "Proveedores activos",
    "Deuda con proveedores", "Cuentas por cobrar clientes", "Facturas emitidas", "Facturación",
    "Nombre del indicador",
])
def test_totales_sobre_actores_no_se_borran(nombre):
    valores = ["NPS", "Ventas"] if nombre == "Nombre del indicador" else [120, 1350.5]
    assert not columna_sensible(nombre, valores)


@pytest.mark.parametrize("nombre", ["Cliente", "Proveedor", "Razón social", "Nombre y apellido", "dni_beneficiario"])
def test_actores_individuales_se_siguen_borrando(nombre):
    assert columna_sensible(nombre)


def test_plural_numerico_se_conserva_y_plural_con_nombres_no():
    datos, reporte = sanear([{"mes": "ene", "Beneficiarios": 1200, "Proveedores": "ACME SA"},
                             {"mes": "feb", "Beneficiarios": 1350, "Proveedores": "Otra SRL"}])
    assert reporte["columnas_excluidas"] == ["Proveedores"]
    assert datos[0]["Beneficiarios"] == 1200


def test_facturacion_y_clientes_activos_son_cifras_no_identificadores():
    assert perfilado.inferir_rol("Facturación", [100, 200]) == "importe"
    assert perfilado.inferir_rol("Clientes activos", [10, 12]) != "identificador"
    assert perfilado.inferir_rol("Proveedor", ["ACME", "XYZ"]) == "identificador"


def _negativos(hallazgos):
    return [h for h in hallazgos if h["evidencia"].get("regla") == "valor_negativo_en_magnitud_no_negativa"]


def test_egresos_en_negativo_por_convencion_no_son_imposibles(organizacion):
    datos = [
        {"Concepto": "Ventas", "Total": 1000},
        {"Concepto": "Costo de ventas", "Total": -600},
        {"Concepto": "Sueldos y cargas sociales", "Total": -200},
        {"Concepto": "Gastos de administración", "Total": -100},
        {"Concepto": "Resultado", "Total": 100},
    ]
    assert _negativos(ajedrecista.imposibilidad(datos)) == []


def test_un_signo_invertido_en_un_egreso_sigue_detectandose(organizacion):
    datos = [
        {"Concepto": "Ventas", "Total": 1000},
        {"Concepto": "Costo de ventas", "Total": 600},
        {"Concepto": "Sueldos y cargas sociales", "Total": -200},
        {"Concepto": "Gastos de administración", "Total": 100},
    ]
    assert _negativos(ajedrecista.imposibilidad(datos))


def test_ingreso_negativo_se_sigue_detectando_aunque_los_egresos_sean_negativos(organizacion):
    datos = [
        {"Concepto": "Ventas", "Total": -1000},
        {"Concepto": "Costo de ventas", "Total": -600},
        {"Concepto": "Gastos de administración", "Total": -100},
    ]
    negativos = _negativos(ajedrecista.imposibilidad(datos))
    assert negativos and negativos[0]["evidencia"]["filas"] == [0]


def test_una_tasa_no_se_usa_como_categoria_de_series():
    meses = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01", "2024-06-01"]
    datos = [{"Mes": m, "Ventas": 100 + i, "Rotación de personal %": [3, 3.3][i % 2]} for i, m in enumerate(meses)]
    assert cronista._dimension_formato_largo(datos, "Mes", ["Ventas"]) is None


def test_salto_de_sueldos_en_junio_se_lee_como_aguinaldo():
    valores = [(f"2025-{m:02d}", (2025, m), v) for m, v in
               [(1, 100), (2, 101), (3, 100), (4, 102), (5, 101), (6, 150)]]
    hallazgo = cronista._analizar_serie({"etiqueta": "Sueldos y cargas sociales", "valores": valores, "orientacion": "fila"})
    assert hallazgo["severidad"] == "media"
    assert "aguinaldo" in hallazgo["descripcion"]
