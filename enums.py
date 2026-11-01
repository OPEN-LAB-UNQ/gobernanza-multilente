"""Vocabulario cerrado de lentes y severidades.

Son (str, Enum): comparan y hashean igual que el string plano ("ajedrecista"
== Lente.AJEDRECISTA), asi que se pueden usar como drop-in donde antes habia
literales sueltos -- sin forzar una reescritura de las 7 lentes ni de
guardrails. El valor real esta acá para no repetir "matematico"/"matemático"
a mano en cada lugar y para poder validar en un solo punto (ver
services.guardrails.normalizar_hallazgo) cuando algo no matchea ninguno.
"""
from __future__ import annotations

from enum import Enum


class Lente(str, Enum):
    CONCILIADOR = "conciliador"
    AJEDRECISTA = "ajedrecista"
    CRONISTA = "cronista"
    ORQUESTA = "orquesta"
    RADIOLOGO = "radiologo"
    RIZOMA = "rizoma"
    MATEMATICO = "matematico"


class Severidad(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
