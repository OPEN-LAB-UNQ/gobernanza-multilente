"""Ámbito del informe: organismo público u organización.

Se elige al cargar y queda en `saneamiento["opciones_tecnicas"]["ambito"]`. El valor por
defecto es "publico": todo informe anterior, y toda carga que no lo indique, se lee como
hasta ahora. Con "organizacion" (empresa, pyme, cooperativa, ONG, universidad) cambian las
reglas que sólo tienen sentido en el presupuesto público y el vocabulario de la lectura.

Se declara al empezar cada análisis, siempre, con el mismo patrón que
`perfilado.declarar_identificadores`, para que ninguna corrida herede el ámbito de otra.
"""
from __future__ import annotations

import contextvars
from typing import Any

PUBLICO = "publico"
ORGANIZACION = "organizacion"
AMBITOS = {PUBLICO, ORGANIZACION}

_AMBITO: contextvars.ContextVar[str] = contextvars.ContextVar("ambito_informe", default=PUBLICO)


def normalizar(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    return texto if texto in AMBITOS else PUBLICO


def de_informe(informe: Any) -> str:
    saneamiento = getattr(informe, "saneamiento", None) or {}
    if not isinstance(saneamiento, dict):
        return PUBLICO
    opciones = saneamiento.get("opciones_tecnicas")
    opciones = opciones if isinstance(opciones, dict) else {}
    return normalizar(opciones.get("ambito") or saneamiento.get("ambito"))


def declarar(valor: Any) -> object:
    return _AMBITO.set(normalizar(valor))


def restaurar(testigo) -> None:
    _AMBITO.reset(testigo)


def actual() -> str:
    return _AMBITO.get()


def es_organizacion() -> bool:
    return _AMBITO.get() == ORGANIZACION


INSTRUCCION_ORGANIZACION = (
    "Ámbito: organización no estatal (empresa, cooperativa, ONG o universidad). Usá su vocabulario "
    "(presupuesto, real, diferencia, ingresos, egresos, resultado, indicadores) y no el del presupuesto público: "
    "no hables de crédito vigente, devengado, organismo, jurisdicción ni gobierno. Quien decide es la "
    "dirección, el consejo o la gerencia. En un ingreso, superar lo presupuestado es favorable."
)
