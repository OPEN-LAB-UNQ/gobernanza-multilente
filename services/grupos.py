"""Grupos de cursada (0.10.62): cada participante ve los proyectos y la votación de su propio grupo.

Una cuenta sin grupo pertenece al grupo por defecto (las comisiones originales). La cuenta administradora ve todos.
"""
from __future__ import annotations

from typing import Optional


def normalizar(valor: Optional[str]) -> Optional[str]:
    """Vacío o sólo espacios es el grupo por defecto (None)."""
    return (valor or "").strip() or None


def de(usuario) -> Optional[str]:
    return normalizar(getattr(usuario, "grupo", None))


def ve_todo(usuario) -> bool:
    """Sin usuario (llamadas internas) o con la cuenta administradora no se filtra por grupo."""
    return usuario is None or getattr(usuario, "rol", None) == "admin"


def filtro(columna, grupo: Optional[str]):
    """Condición SQL «del mismo grupo»: sin grupo coincide con NULL, no con todos."""
    grupo = normalizar(grupo)
    return columna.is_(None) if grupo is None else columna == grupo
