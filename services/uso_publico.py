"""Conteos agregados de uso real que muestra la presentación pública.

Excluyen la cuenta administradora y no contienen datos personales. Se calculan al
mostrar la página, con una caché breve, para que la franja «Uso registrado» no quede
atrasada entre publicaciones. `scripts/actualizar_evidencia_publica.py` guarda además
una foto en `static/public-evidence.json`, que se usa si la base no responde.
"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import time

logger = logging.getLogger(__name__)

CACHE_SEGUNDOS = 300
# Argentina no tiene horario de verano: UTC-3 todo el año.
HORA_ARGENTINA = dt.timezone(dt.timedelta(hours=-3))

# Un informe cargado cuenta como revisado cuando tiene devolución: los que esperan la confirmación de la lectura previa,
# o cuyo análisis no terminó, no entran entre los revisados ni entre los «sin señales» (auditoría del 28/10/2026).
CON_DEVOLUCION = "exists (select 1 from devoluciones d where d.informe_id=i.id)"

CONSULTAS = {
    "informes": "select count(*) from informes i join usuarios u on u.id=i.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos",
    "informes_con_devolucion": "select count(*) from informes i join usuarios u on u.id=i.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos and " + CON_DEVOLUCION,
    "participantes": "select count(distinct i.usuario_id) from informes i join usuarios u on u.id=i.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos",
    "observaciones": "select count(*) from hallazgos h join informes i on i.id=h.informe_id join usuarios u on u.id=i.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos and " + CON_DEVOLUCION,
    "informes_sin_senales": "select count(*) from informes i join usuarios u on u.id=i.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos and not exists (select 1 from hallazgos h where h.informe_id=i.id) and " + CON_DEVOLUCION,
    "proyectos": "select count(*) from proyectos_ia p join usuarios u on u.id=p.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos",
    "proyectos_entregados": "select count(*) from proyectos_ia p join usuarios u on u.id=p.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos and p.estado in ('entregado','revisado')",
}

_cache: dict = {"hasta": 0.0, "valor": None}
_lock = threading.Lock()


def _fecha_local(valor: dt.datetime | str | None) -> str:
    if not valor:
        return ""
    if isinstance(valor, str):  # SQLite devuelve el texto; Postgres, un datetime.
        valor = dt.datetime.fromisoformat(valor)
    return valor.replace(tzinfo=dt.timezone.utc).astimezone(HORA_ARGENTINA).strftime("%d/%m/%Y")


def calcular(db) -> dict:
    """Conteos en este momento. Las fechas de la base están en UTC sin zona."""
    from sqlalchemy import bindparam, text

    from config import settings

    # Sin cuentas de prueba: la misma exclusión que las métricas internas. Un conjunto vacío
    # no se puede pasar a «not in», así que se usa un valor que ningún correo tiene.
    excluidos = sorted({c.strip().lower() for c in settings.usuarios_excluidos_metricas.split(",") if c.strip()}) or [""]

    def consulta(sql: str):
        return text(sql).bindparams(bindparam("excluidos", value=excluidos, expanding=True))

    uso = {clave: int(db.execute(consulta(sql)).scalar() or 0) for clave, sql in CONSULTAS.items()}
    desde, hasta = db.execute(consulta(
        "select min(i.creado_en), max(i.creado_en) from informes i join usuarios u on u.id=i.usuario_id where u.rol<>'admin' and lower(u.email) not in :excluidos"
    )).one()
    uso["desde"] = _fecha_local(desde)
    uso["hasta"] = _fecha_local(hasta)
    uso["fecha"] = dt.datetime.now(HORA_ARGENTINA).strftime("%d/%m/%Y")
    return uso


def vigente(respaldo: dict | None = None) -> dict:
    """Conteos con caché de CACHE_SEGUNDOS; si la base falla, la última foto guardada."""
    ahora = time.monotonic()
    with _lock:
        if _cache["valor"] is not None and ahora < _cache["hasta"]:
            return _cache["valor"]
    try:
        from database import SessionLocal

        with SessionLocal() as db:
            valor = calcular(db)
    except Exception:  # noqa: BLE001 — la página pública no puede caerse por un conteo.
        logger.exception("no se pudieron calcular los datos de uso; se muestra la última foto")
        # Un minuto sin reintentar: si la base no responde, no se la consulta en cada visita.
        with _lock:
            _cache.update(valor=respaldo or {}, hasta=ahora + 60)
        return respaldo or {}
    with _lock:
        _cache.update(valor=valor, hasta=ahora + CACHE_SEGUNDOS)
    return valor
