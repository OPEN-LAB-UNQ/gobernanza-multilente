"""Meses ausentes no son vecinos; los límites conservan el cuadro de origen."""
from types import SimpleNamespace

from services import interpretacion_previa as ip
from services.lentes import rizoma
from services.reportes import markdown, registro


def test_diferencias_no_saltan_un_mes_sin_datos():
    datos = [dict(periodo=f"2024-{i:02d}", temperatura=i*3, visitantes=i*8) for i in range(1,8)]
    datos[3]["visitantes"] = None
    resultado = rizoma._estadistica_par(datos,"temperatura","visitantes")
    assert resultado["n_observaciones"] == 6
    assert resultado["datos_faltantes"] == 1
    assert resultado["n_primeras_diferencias"] == 4
    assert resultado["correlacion_primeras_diferencias"] is None  # incrementos constantes
    datos[3]["visitantes"] = 32
    assert rizoma._estadistica_par(datos,"temperatura","visitantes")["n_primeras_diferencias"] == 6


def test_cuadros_pendientes_se_distinguen_y_no_inventan_un_numero():
    saneamiento = {ip.CAMPO: {"revision": 1, "cuadros": [
        {"archivo":"x.xlsx","hoja":"Datos","bloque":n,"plan":{"relaciones":False}}
        for n in (1,2)]}}
    mapa = ip.verificar_relaciones(saneamiento)["estado"]
    assert [x["bloque"] for x in mapa["sin_leer"]] == [1,2]
    informe = SimpleNamespace(datos=[],saneamiento={"mapa_lectura":mapa},hallazgos=[],devolucion=None,periodo="2026-10")
    pendientes = registro.construir(informe)["pendientes"]
    assert any("cuadro 1" in p["donde"] for p in pendientes)
    assert any("cuadro 2" in p["donde"] for p in pendientes)
    texto = markdown._con_lector_cuadro("# Informe\n",informe)
    assert "cuadro 1" in texto and "cuadro 2" in texto
    assert "confirmada.." not in texto
    for x in mapa["sin_leer"]:
        x.pop("bloque")
    assert "cuadro None" not in markdown._con_lector_cuadro("# Informe\n",informe)


def test_etiqueta_temporal_no_afirma_frecuencia_anual():
    assert ip.etiqueta("serie_filas") == "períodos en filas"
    assert ip.etiqueta("serie_columnas") == "períodos en columnas"
