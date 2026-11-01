"""Datos consultables: contenido conservado, páginas, exportación y autorización real."""

import models
from routers import informes

pytest_plugins = ["tests.test_ejemplos_zip"]


def preparar(flujo):
    client, factory, actual = flujo
    client.app.include_router(informes.router, prefix="/api")
    with factory() as db:
        db.add(models.Area(id=1, nombre="Prueba", codigo="TEST"))
        db.add(
            models.Informe(
                id=1,
                area_id=1,
                usuario_id=1,
                periodo="2026",
                datos=[{"valor": i} for i in range(51)] + [{"tardía": "<img src=x onerror=alert(1)>", "valor": -2}],
                saneamiento={"proveniencia": {"fuentes": [{"nombre_original": "prueba.xlsx"}]}},
            )
        )
        db.commit()
    return client, actual


def test_paginas_columnas_tardias_busqueda_y_exportacion_completa(flujo):
    client, _ = preparar(flujo)
    url = "/api/informes/1/datos-analizados"
    r = client.get(url)
    assert r.headers["cache-control"] == "no-store"
    data = r.json()
    assert data["total"] == 52 and len(data["items"]) == 50
    assert data["columnas"] == ["valor", "tardía"]
    assert client.get(url + "?offset=50").json()["items"][0]["registro"] == 51
    result = client.get(url, params={"q": "IMG"}).json()
    assert result["coincidencias"] == 1 and result["items"][0]["registro"] == 52
    export = client.get(url + "?descargar=true&q=inexistente").json()
    assert len(export["datos"]) == 52 and export["datos"][-1]["valor"] == -2
    assert "No es el archivo original" in export["aviso"]
    assert export["fuentes"] == ["prueba.xlsx"]


def test_permiso_ajeno_admin_limites_e_informe_ausente(flujo):
    client, actual = preparar(flujo)
    actual["id"] = 2
    for suffix in ("", "?descargar=true"):
        assert client.get("/api/informes/1/datos-analizados" + suffix).status_code == 403
    actual["id"] = 4
    assert client.get("/api/informes/1/datos-analizados").status_code == 200
    assert client.get("/api/informes/999/datos-analizados").status_code == 404
    for query in ("limit=101", "offset=-1", "q=" + "a" * 201):
        assert client.get("/api/informes/1/datos-analizados?" + query).status_code == 422
