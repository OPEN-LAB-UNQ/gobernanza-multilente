"""Evidencia por hallazgo: aislamiento entre informes y ausencia explícita de coordenadas."""

import models
from routers import informes

pytest_plugins = ["tests.test_ejemplos_zip"]


def preparar(flujo):
    client, factory, actual = flujo
    client.app.include_router(informes.router, prefix="/api")
    with factory() as db:
        db.add(models.Area(id=1, nombre="Prueba", codigo="TEST"))
        for i in (1, 2):
            db.add(models.Informe(id=i, area_id=1, usuario_id=i, periodo="2026", datos=[{"valor": 99}]))
        db.flush()
        db.add(
            models.Hallazgo(
                id=1,
                informe_id=1,
                lente="conciliador",
                descripcion="Total discordante",
                evidencia={
                    "archivo_origen": "área.xlsx",
                    "hoja": "Buenos Aires",
                    "celda": "K37",
                    "bloque_excel": 2,
                    "valor_observado": 0,
                    "total_reconstruido": None,
                    "celdas_participantes": ["Buenos Aires!K37", "Otra hoja!K38"],
                },
            )
        )
        db.add(models.Hallazgo(id=2, informe_id=2, lente="cronista", descripcion="Ajeno", evidencia={"celda": "A1"}))
        db.add(models.Hallazgo(id=3, informe_id=1, lente="cronista", descripcion="Antiguo", evidencia=None))
        db.commit()
    return client, actual


def test_conserva_ubicaciones_valores_y_no_inventa_coordenadas(flujo):
    client, _ = preparar(flujo)
    r = client.get("/api/informes/1/hallazgos/1/evidencia")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    e = r.json()["evidencia"]
    assert e["archivo_origen"] == "área.xlsx" and e["celda"] == "K37"
    assert e["valor_observado"] == 0 and e["total_reconstruido"] is None
    assert e["celdas_participantes"] == ["Buenos Aires!K37", "Otra hoja!K38"]
    assert client.get("/api/informes/1/hallazgos/3/evidencia").json()["evidencia"] == {}


def test_prohibe_cruce_de_ids_y_usuario_ajeno(flujo):
    client, actual = preparar(flujo)
    assert client.get("/api/informes/1/hallazgos/2/evidencia").status_code == 404
    actual["id"] = 2
    assert client.get("/api/informes/1/hallazgos/1/evidencia").status_code == 403
    actual["id"] = 4
    assert client.get("/api/informes/1/hallazgos/1/evidencia").status_code == 200
    assert client.get("/api/informes/999/hallazgos/1/evidencia").status_code == 404
    assert client.get("/api/informes/1/hallazgos/999/evidencia").status_code == 404
