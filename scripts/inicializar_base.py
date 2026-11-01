"""Prepara la base de datos de una instalación nueva o existente.

La primera migración de Alembic («baseline») se generó sobre una base que ya
existía: modifica tablas en lugar de crearlas. Por eso `alembic upgrade head`
falla en una base vacía. Este script resuelve los dos casos:

- base vacía: crea el esquema completo desde los modelos, carga las
  definiciones de los protocolos B-1 y R-1 (sql/datos_referencia_protocolos.json,
  que las migraciones cargan en una base existente) y marca la última migración
  (`alembic stamp head`);
- base existente: aplica las migraciones pendientes (`alembic upgrade head`).

Uso, desde la raíz del proyecto y con el .env configurado:

    venv/bin/python scripts/inicializar_base.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

import models  # noqa: E402,F401 -- registra todos los modelos en Base.metadata
from alembic import command  # noqa: E402
from database import Base, engine  # noqa: E402

DATOS_REFERENCIA = RAIZ / "sql" / "datos_referencia_protocolos.json"
TABLAS_REFERENCIA = ("versiones_protocolo", "definiciones_control")


def cargar_datos_referencia() -> dict[str, int]:
    datos = json.loads(DATOS_REFERENCIA.read_text(encoding="utf-8"))
    cargadas = {}
    with engine.begin() as conn:
        for tabla in TABLAS_REFERENCIA:
            filas = datos[tabla]
            conn.execute(Base.metadata.tables[tabla].insert(), filas)
            conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), (SELECT MAX(id) FROM {tabla}))"))
            cargadas[tabla] = len(filas)
    return cargadas


def main() -> int:
    alembic_cfg = Config(str(RAIZ / "alembic.ini"))
    tablas = set(inspect(engine).get_table_names()) - {"alembic_version"}
    if not tablas:
        Base.metadata.create_all(engine)
        cargadas = cargar_datos_referencia()
        command.stamp(alembic_cfg, "head")
        print(f"Base vacía: se crearon {len(Base.metadata.tables)} tablas, se cargaron "
              f"{cargadas['versiones_protocolo']} versiones de protocolo y {cargadas['definiciones_control']} "
              "controles, y se marcó la última migración.")
    else:
        command.upgrade(alembic_cfg, "head")
        print(f"Base existente ({len(tablas)} tablas): migraciones aplicadas hasta la última.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
