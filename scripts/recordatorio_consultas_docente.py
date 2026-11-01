#!/usr/bin/env python3
"""Recordatorio diario al docente: consultas de la Incubadora sin respuesta hace más de 2 días.

Sólo lee la base. Manda a DOCENTE_AVISO_EMAIL un resumen con proyecto, fecha y enlace (sin el texto de la
consulta ni datos de quien la hizo), como mucho una vez por día (marca en var/). Pensado para cron, p. ej.:
  0 9 * * * cd /home/gobernanza && ./venv/bin/python3 scripts/recordatorio_consultas_docente.py >> var/recordatorio_consultas.log 2>&1
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from database import SessionLocal  # noqa: E402
from services import aviso_docente, notificaciones  # noqa: E402

DIAS = 2
MARCA = RAIZ / "var" / "recordatorio_consultas_ultimo_envio"


def main(marca: Path = MARCA) -> str:
    hoy = dt.date.today().isoformat()
    if marca.exists() and marca.read_text().strip() == hoy:
        print("el recordatorio de hoy ya salió")
        return "ya_enviado"
    with SessionLocal() as db:
        pendientes = aviso_docente.consultas_sin_respuesta(db, mas_de_dias=DIAS)
        db.rollback()
    estado, error = notificaciones.enviar_recordatorio_consultas(notificaciones.destinatarios_docente(), pendientes, DIAS)
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M} pendientes={len(pendientes)} estado={estado} {error or ''}".rstrip())
    if estado == "enviada":
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text(hoy)
    return estado


if __name__ == "__main__":
    main()
