import models
from routers.monitoreo import _metricas_registros


def _registro(estado: str) -> models.RegistroMonitoreo:
    return models.RegistroMonitoreo(
        proyecto_id=1,
        usuario_id=1,
        tipo="avance",
        titulo="Avance",
        contenido="Contenido",
        estado=estado,
    )


def test_metricas_monitoreo_hacen_visible_lo_pendiente_y_el_cierre():
    pendientes = _metricas_registros([_registro("abierto"), _registro("resuelto")])
    assert pendientes["abiertos"] == 1
    assert pendientes["cerrados"] == 1
    assert "1 registro que todavía requiere seguimiento" in pendientes["lectura"]

    dos = _metricas_registros([_registro("abierto"), _registro("abierto"), _registro("resuelto")])
    assert "2 registros que todavía requieren seguimiento" in dos["lectura"]

    cerrado = _metricas_registros([_registro("resuelto"), _registro("descartado")])
    assert cerrado["abiertos"] == 0
    assert "cierre explícito" in cerrado["lectura"]
