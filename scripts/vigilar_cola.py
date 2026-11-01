#!/usr/bin/env python3
"""Vigila la cola de análisis y la destraba sola (cron cada 2 minutos).

El 08/10/2026 la cola quedó detenida 18 minutos en una presentación: el hilo que analiza
murió y nadie lo notó. Este control no depende de conocer la causa:
- Un informe espera turno hace más de ESPERA_MAX y ninguno se está analizando: el hilo
  no está trabajando; se reinicia el servicio (al arrancar, retoma la cola).
- Un análisis lleva más de ANALISIS_MAX (lo normal es ~7 minutos): se marca como error
  para que no se reintente en bucle y se reinicia el servicio.
Cada intervención queda en var/vigilar_cola.log.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ESPERA_MAX = dt.timedelta(minutes=3)
ANALISIS_MAX = dt.timedelta(minutes=25)
LOG = RAIZ / "var" / "vigilar_cola.log"


def decidir(trabajos, ahora):
    """Qué hacer con la cola. trabajos: (id, estado, creado_en, iniciado_en). Sin efectos."""
    procesando = [t for t in trabajos if t[1] == "procesando"]
    pendientes = [t for t in trabajos if t[1] == "pendiente"]
    colgados = [t[0] for t in procesando if t[3] is not None and ahora - t[3] > ANALISIS_MAX]
    if colgados:
        return "reiniciar", colgados, f"análisis de más de {int(ANALISIS_MAX.total_seconds() // 60)} minutos: {colgados}"
    if pendientes and not procesando and min(ahora - t[2] for t in pendientes) > ESPERA_MAX:
        return "reiniciar", [], f"{len(pendientes)} en espera y ninguno en análisis"
    return "nada", [], ""


def main() -> int:
    import models
    from database import SessionLocal

    db = SessionLocal()
    try:
        ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        trabajos = [(j.id, j.estado, j.creado_en, j.iniciado_en)
                    for j in db.query(models.AnalysisJob).filter(models.AnalysisJob.estado.in_(("pendiente", "procesando")))]
        accion, colgados, motivo = decidir(trabajos, ahora)
        if accion == "nada":
            return 0
        for job_id in colgados:
            job = db.get(models.AnalysisJob, job_id)
            job.estado = "error"
            job.error = "El análisis superó el tiempo máximo y se detuvo; podés volver a cargar el archivo."
            job.finalizado_en = ahora
        db.commit()
    finally:
        db.close()
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} reinicio: {motivo}\n")
    subprocess.run(["systemctl", "restart", "gobernanza"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
