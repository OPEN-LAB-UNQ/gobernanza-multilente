"""«1 señales» o «1 casos» hacen dudar del resto del informe: el plural se decide en un solo lugar."""
import re

from services import devolucion, lectura_temporal, plural
from services.plural import contar, senales


def test_concordancia_basica():
    assert contar(1, "señal", "señales") == "1 señal"
    assert contar(2, "señal", "señales") == "2 señales"
    assert contar(0, "señal", "señales") == "0 señales"
    assert contar(1, "caso") == "1 caso"
    assert contar(3, "caso") == "3 casos"
    assert contar(1, "hoja") == "1 hoja"


def test_senales_distingue_ninguna_de_una():
    assert senales(0) == "sin señales"
    assert senales(1) == "1 señal"
    assert senales(4) == "4 señales"


def test_reporte_ejecutivo_usa_el_mismo_criterio():
    from services.reporte_ejecutivo import senales as senales_ejecutivo

    assert senales_ejecutivo is plural.senales


class _Hallazgo:
    def __init__(self, periodo, hoja):
        self.lente = "cronista"
        self.modo = "control"
        self.descripcion = "Variación anual a contextualizar."
        self.evidencia = {"naturaleza": "contexto", "periodo": periodo, "hoja": hoja,
                          "bloque_excel": 1, "serie": "Total", "requiere_contexto_anual": True,
                          "ratio_vs_movimiento_tipico": 3, "regla": "variacion_anual"}


def test_una_sola_variacion_anual_no_se_anuncia_en_plural():
    resumen = lectura_temporal.resumen([_Hallazgo("2020", "Hoja 1")])
    assert resumen["cantidad"] == 1 and resumen["hojas"] == 1
    texto = "\n".join(lectura_temporal.lineas_markdown([_Hallazgo("2020", "Hoja 1")]))
    assert "1 señal temporal anual en 1 hoja" in texto
    assert "2020: 1 señal" in texto
    assert "1 señales" not in texto and "1 hojas" not in texto


def test_la_devolucion_no_anuncia_una_senal_en_plural():
    hallazgo = {"lente": "cronista", "modo": "control", "descripcion": "Variación anual a contextualizar.",
                "evidencia": {"naturaleza": "contexto", "periodo": "2020", "hoja": "Hoja 1",
                              "requiere_contexto_anual": True, "ratio_vs_movimiento_tipico": 3}}
    mensaje, _ = devolucion.armar_mensaje([hallazgo], {})
    assert "1 señal anual para contextualizar" in mensaje
    assert not re.search(r"\b1 (señales|casos|hojas|observaciones)\b", mensaje)


def test_el_contexto_agrupado_de_un_solo_periodo_concuerda():
    from services import prioridad_controles

    hallazgo = {"lente": "cronista", "modo": "control", "descripcion": "Variación 2005.",
                "evidencia": {"naturaleza": "contexto", "periodo": "2005", "hoja": "Córdoba",
                              "requiere_contexto_anual": True, "ratio_vs_movimiento_tipico": 3}}
    salida = prioridad_controles.consolidar_contexto([hallazgo])
    agrupado = [h for h in salida if (h.get("evidencia") or {}).get("regla") == "contexto_compartido_periodo"]
    assert agrupado, "el contexto anual debería agruparse por período"
    assert "1 variación anual en 1 hoja" in agrupado[0]["descripcion"]


def test_un_reporte_ejecutivo_con_una_sola_senal_no_escribe_ningun_plural_de_uno():
    """La prueba que faltaba: recorre el reporte completo y falla ante «1 <plural>»."""
    from types import SimpleNamespace

    from services import reporte_ejecutivo

    hallazgo = SimpleNamespace(
        id=1, lente="matematico", modo="control", severidad="alta",
        descripcion="El total de la fila no coincide con la suma de sus rubros.",
        pregunta_institucional="¿Cuál de los dos valores corresponde?",
        evidencia={"naturaleza": "control", "hoja": "Córdoba", "celda": "F12", "regla": "total_de_fila_no_cierra"},
    )
    informe = SimpleNamespace(id=7, datos=[{"rubro": "Total", "monto": 10}], saneamiento={},
                              devolucion=SimpleNamespace(cobertura={"excel": {"hojas": ["Córdoba"], "bloques": [1]}}))
    texto = "\n".join(str(x) for x in reporte_ejecutivo.lineas(informe, [hallazgo]))
    assert "1 caso de revisión" in texto
    assert "1 señal de control" in texto
    assert "1 registro incorporado; 1 hoja; 1 cuadro" in texto
    assert not re.search(r"\b1 (señales|casos|hojas|observaciones|grupos|variaciones)\b", texto)
