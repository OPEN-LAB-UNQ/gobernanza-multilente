"""Casos de la revisión independiente del 28/09/2026 sobre los cambios del día."""
import contextvars

import pytest

from services import ambito, perfilado
from services.lentes import ajedrecista
from services.sanitizacion import columna_sensible, redactar_texto_libre, sanear


@pytest.mark.parametrize("nombre,valores", [
    ("Proveedores nuevos", ["Juan Pérez"]),
    ("Área responsable", ["Lic. Juan Pérez"]),
    ("Clientes activos", ["ACME SA"]),
    ("Pagos a proveedores", ["Juan"]),
    ("Expedientes activos", ["EX-2024-12345678-APN"]),
    ("Facturas emitidas", ["A-0001-00001234"]),
    ("Clientes", [30712345678, 20123456789]),
    ("Beneficiarios", ["12.345.678", "23.456.789"]),
    ("Personas", ["20123456789"]),
    ("Proveedores", [30123456, 40555666]),
    ("Nombre del proyecto", ["Juan Pérez"]),
    ("Clientes activos", None),
])
def test_el_rotulo_solo_no_alcanza_para_conservar_datos_de_actores(nombre, valores):
    assert columna_sensible(nombre, valores)


def test_sanear_excluye_nombres_aunque_el_rotulo_suene_agregado():
    datos, reporte = sanear([{"Proveedores nuevos": "Juan Pérez", "Monto": 100}])
    assert datos == [{"Monto": 100}] and reporte["columnas_excluidas"] == ["Proveedores nuevos"]


@pytest.mark.parametrize("texto", [
    "Partida 11-001-0001", "Prog 16-001-2024", "Cuenta 511-0001-2024", "SAF 325-1234-5678",
    "Resolución 1234-5678-2024", "Comparar 2023-2024-2025",
])
def test_codigos_con_guiones_no_se_toman_por_telefonos(texto):
    assert redactar_texto_libre(texto) == texto


def test_sector_publico_conserva_los_negativos_aunque_varias_filas_de_gasto_los_compartan():
    datos = [{"Inciso": "Gastos en personal", "Devengado": -900}, {"Inciso": "Gastos de funcionamiento", "Devengado": -100},
             {"Inciso": "Bienes de uso", "Devengado": -50}, {"Inciso": "Transferencias", "Devengado": 300}]
    testigo = ambito.declarar(ambito.PUBLICO)
    try:
        negativos = [h for h in ajedrecista.imposibilidad(datos)
                     if h["evidencia"].get("regla") == "valor_negativo_en_magnitud_no_negativa"]
    finally:
        ambito.restaurar(testigo)
    assert negativos and negativos[0]["evidencia"]["filas"] == [0, 1, 2]


def _par(columnas):
    datos = [{**dict(zip(columnas, [1000, 950, -50, 0.95])), "Rubro": "Costo de ventas"}] * 2
    return ajedrecista._columnas_presupuesto_real(perfilado.perfilar(datos))


@pytest.mark.parametrize("columnas,esperado", [
    (["Presupuesto", "Real", "Actual vs presupuesto"], ("Presupuesto", "Real")),
    (["Presupuesto", "Real", "Cumplimiento presupuesto"], ("Presupuesto", "Real")),
    (["Real 2023", "Presupuesto 2024", "Real 2024"], ("Presupuesto 2024", "Real 2024")),
    (["Presupuesto", "Actualización", "Real"], ("Presupuesto", "Real")),
    (["Real 2023", "Presupuesto 2024"], (None, None)),
])
def test_presupuesto_y_real_se_eligen_comparables(columnas, esperado):
    assert _par(columnas) == esperado


def test_real_por_debajo_del_presupuesto_no_se_marca_por_una_columna_de_comparacion():
    datos = [{"Rubro": "Costo de ventas", "Presupuesto": 1000, "Real": 950, "Actual vs presupuesto": -50},
             {"Rubro": "Gastos de administración", "Presupuesto": 500, "Real": 480, "Actual vs presupuesto": -20}]
    testigo = ambito.declarar(ambito.ORGANIZACION)
    try:
        reglas = {h["evidencia"].get("regla") for h in ajedrecista.imposibilidad(datos)}
    finally:
        ambito.restaurar(testigo)
    assert "gasto_real_supera_presupuesto" not in reglas


def test_el_contexto_se_redeclara_en_cada_paso_del_streaming():
    from services.analisis import _en_contexto

    def lentes():
        for _ in range(3):
            yield ambito.actual()

    flujo = _en_contexto(lentes(), lambda: ambito.declarar(ambito.ORGANIZACION))
    # Cada paso en una copia nueva del contexto, como hace StreamingResponse.
    vistos = [contextvars.copy_context().run(next, flujo) for _ in range(3)]
    assert vistos == [ambito.ORGANIZACION] * 3


# Segunda revisión independiente (28/09/2026, noche).

@pytest.mark.parametrize("valores", [["1.500.000", "2.300.000"], [1500000, 2300000, 1750000], [30500000000.0, 12000000000.0]])
def test_montos_bajo_rotulo_de_importe_se_conservan(valores):
    assert not columna_sensible("Deuda con proveedores", valores)


def test_un_cuit_valido_se_excluye_aun_bajo_rotulo_de_importe():
    assert columna_sensible("Deuda con proveedores", [20123456786])


@pytest.mark.parametrize("columnas,esperado", [
    (["Presupuesto_2023", "Real_2023"], ("Presupuesto_2023", "Real_2023")),
    (["presupuesto", "gasto_real"], ("presupuesto", "gasto_real")),
    (["Presupuesto", "Realizado", "Real"], ("Presupuesto", "Real")),
])
def test_real_con_guion_bajo_se_reconoce(columnas, esperado):
    assert _par(columnas) == esperado


def test_un_xlsx_renombrado_a_xls_tambien_se_valida(monkeypatch):
    import io
    import zipfile

    from services import carga_archivos
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"0" * (6 * 1024 * 1024))
    monkeypatch.setattr(carga_archivos, "MAX_XLSX_DESCOMPRIMIDO", 5 * 1024 * 1024)
    with pytest.raises(carga_archivos.ArchivoNoSoportado, match="al abrirse"):
        carga_archivos.parse_archivos_con_cobertura([("libro.xls", buf.getvalue())])
