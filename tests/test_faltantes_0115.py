"""0.10.15: faltantes del lector en una línea y motivo de validez cuando no se ejecutan los controles."""
from types import SimpleNamespace

from services.reportes import registro


def _informe(saneamiento, cobertura):
    return SimpleNamespace(saneamiento=saneamiento, devolucion=SimpleNamespace(cobertura=cobertura), datos=[], hallazgos=[],
                           id=1, periodo="2026-10", creado_en=None)


def test_tramos_sin_respuesta_del_lector_en_una_sola_linea():
    hojas = [{"archivo": "a.xlsx", "hoja": f"H{k % 5}", "filas": [],
              "mapas": {"gpt": {}, "deepseek": {}, "gemini": {"error": "El proveedor no completó la lectura"}}}
             for k in range(12)]
    reg = registro.construir(_informe({"mapa_lectura": {"hojas": hojas}}, {}))
    lector = [p for p in reg["pendientes"] if str(p["donde"]).startswith("lector del cuadro")]
    assert len(lector) == 1
    assert lector[0]["donde"] == "lector del cuadro en 12 tramos de 5 hojas («H0», «H1», «H2», «H3» y otras)"
    assert "gemini: El proveedor no completó la lectura" in lector[0]["motivo"]
    assert "filas []" not in str(reg["pendientes"])


def test_un_solo_tramo_conserva_sus_filas():
    hojas = [{"archivo": "a.xlsx", "hoja": "H", "filas": [4, 9], "mapas": {"gpt": {"error": "x"}, "gemini": {}}}]
    reg = registro.construir(_informe({"mapa_lectura": {"hojas": hojas}}, {}))
    assert any(p["donde"] == "lector del cuadro, hoja «H», filas [4, 9]" for p in reg["pendientes"])


def test_controles_sin_ejecutar_dicen_el_motivo_de_validez():
    cobertura = {"lentes": [{"lente": "ajedrecista", "estado": "no_evaluable", "ejecutado": False}],
                 "condiciones_validez": {"cambio_esquema": True, "puede_concluir": False,
                                         "condiciones_fallidas": [{"motivo": "Cambio de esquema detectado"}]}}
    controles = registro._controles(cobertura, [])
    assert controles[0]["motivo"] == "condiciones de validez no cumplidas: cambio de esquema detectado respecto del informe anterior"
    assert registro.motivo_validez({}) is None
