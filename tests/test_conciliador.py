"""Tests de el Conciliador."""
from __future__ import annotations

from conftest import _presupuesto_largo

from services import guardrails
from services.lentes import ajedrecista, aplicar_conciliador, conciliador, cronista


def test_conciliador_no_pierde_advertencia_de_modulacion_sin_match():
    """Si una modulacion (pistas tecnicas) matchea un hallazgo pero la otra
    (hallazgos presupuestarios) no encuentra nada para emparejar, la
    advertencia general del conciliador debe seguir apareciendo -- antes un
    solo booleano global apagaba el aviso de la que fallo con que la otra
    hubiera tenido exito."""
    crudos = [{"lente": "ajedrecista", "modo": "otro", "descripcion": "x", "severidad": "alta", "evidencia": {"filas": [5]}}]
    resultado_conciliador = {
        "modulaciones": [
            {"filas": {5}, "hallazgo_presupuestario": False, "contexto_tecnico": "ctx"},
            {"filas": set(), "hallazgo_presupuestario": True, "contexto_tecnico": "ctx"},
        ],
        "hallazgo_general": {"modo": "conciliacion", "descripcion": "advertencia general", "severidad": "baja", "evidencia": {}},
    }
    crudos_originales_snapshot = [dict(h) for h in crudos]
    resultado = aplicar_conciliador(crudos, resultado_conciliador)
    assert resultado[0]["limites"]["contexto_tecnico"] == "ctx"
    assert resultado[0]["severidad"] == "media"
    assert any(h.get("lente") == "conciliador" for h in resultado), (
        "se perdio la advertencia general de la modulacion presupuestaria que no encontro match"
    )
    assert crudos == crudos_originales_snapshot, (
        "aplicar_conciliador no debe mutar los dicts de entrada -- debe devolver una lista nueva"
    )


def test_conciliador_modula_en_vez_de_duplicar():
    """Caso end-to-end: el conciliador encuentra un artefacto tecnico (ratio
    ejecucion/credito extremo) que explica el hallazgo del ajedrecista.
    Debe bajarle la severidad y adjuntar contexto, sin agregar un hallazgo
    'conciliador' separado."""
    datos = _presupuesto_largo(salto_area="Infraestructura", salto_periodo="2026-05", salto_factor=2.6)

    crudos = [{**h, "lente": "ajedrecista"} for h in ajedrecista.analizar(datos, None)]
    crudos += [{**h, "lente": "cronista"} for h in cronista.analizar(datos)]

    severidad_previa = next(h["severidad"] for h in crudos if h["lente"] == "ajedrecista" and h["modo"] == "restriccion_formal_a_validar")
    assert severidad_previa == "alta"

    resultado = conciliador.analizar(datos, crudos)
    crudos = aplicar_conciliador(crudos, resultado)

    ajedrecista_h = next(h for h in crudos if h["lente"] == "ajedrecista" and h["modo"] == "restriccion_formal_a_validar")
    assert ajedrecista_h["severidad"] == "media"
    assert "contexto_tecnico" in ajedrecista_h["limites"]

    cronista_h = next(h for h in crudos if h["lente"] == "cronista")
    assert cronista_h["severidad"] == "alta"
    assert "contexto_tecnico" not in cronista_h.get("limites", {})

    assert not any(h["lente"] == "conciliador" for h in crudos)


def test_conciliador_cae_a_advertencia_propia_sin_hallazgo_para_emparejar():
    """Si el conciliador detecta un artefacto (reversa mensual) pero no hay
    ningun hallazgo sustantivo cuyas filas se solapen, debe seguir emitiendo
    su propia advertencia -- el comportamiento anterior a la modulacion."""
    datos = [
        {"periodo": "2026-01", "credito_vigente": 100, "devengado_mensual": 10},
        {"periodo": "2026-02", "credito_vigente": 100, "devengado_mensual": -5},
        {"periodo": "2026-03", "credito_vigente": 100, "devengado_mensual": 8},
    ]
    crudos: list[dict] = []
    resultado = conciliador.analizar(datos, crudos)
    crudos = aplicar_conciliador(crudos, resultado)

    assert len(crudos) == 1
    assert crudos[0]["lente"] == "conciliador"
    assert crudos[0]["modo"] == "conciliacion"


def test_contexto_tecnico_del_conciliador_tambien_se_sanitiza():
    """limites.contexto_tecnico viajaba sin pasar por sanitizar_texto -- si el
    conciliador cita un nombre de columna del archivo del usuario con lenguaje
    acusatorio, ahora se neutraliza igual que descripcion/pregunta_institucional,
    y sigue protegiendo el vocabulario legitimo del dominio."""
    hallazgo = guardrails.normalizar_hallazgo({
        "lente": "ajedrecista",
        "modo": "imposibilidad",
        "descripcion": "El devengado supera al credito vigente.",
        "severidad": "alta",
        "evidencia": {"filas": [1, 2]},
        "limites": {
            "contexto_tecnico": (
                "Antes de escalar conviene revisar si hubo una sancion disciplinaria "
                "en el area, aunque la sancion de la ley de presupuesto no cambio."
            )
        },
    })
    contexto = hallazgo["limites"]["contexto_tecnico"]
    assert "sancion disciplinaria" not in contexto
    assert "sancion de la ley de presupuesto" in contexto




def test_conciliador_lee_notas_de_corte_en_celdas():
    datos = [
        {"periodo": "2026-01", "nota": "serie normal", "monto": 10, "cantidad": 2, "otro": 5},
        {"periodo": "2026-02", "nota": "corte temporal de carga parcial al cierre provisorio", "monto": 20, "cantidad": 3, "otro": 6},
        {"periodo": "2026-03", "nota": "serie normal", "monto": 30, "cantidad": 4, "otro": 7},
    ]
    resultado = conciliador.analizar(datos, [])
    assert resultado["hallazgo_general"]
    notas = resultado["hallazgo_general"]["evidencia"]["notas_cobertura"]
    assert any(n["tipo"] == "valor" and n["fila"] == 1 for n in notas)
    assert "corte temporal" in resultado["hallazgo_general"]["descripcion"]
