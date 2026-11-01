from copy import deepcopy

import pytest

from services import casos_revision as c
from services import triangulacion as t
from tests.flujo_confirmado import cargar_confirmado


def h(regla, celda, **ev):
    return dict(
        lente="ajedrecista",
        modo="control_tabular",
        descripcion=celda,
        severidad="alta",
        evidencia=dict(
            naturaleza="control",
            archivo_origen="a.xlsx",
            hoja="H",
            celda=celda,
            regla=regla,
            periodo=2019,
            puntaje_prioridad=100,
            **ev,
        ),
    )


def test_duplicado_y_efecto_adyacente_conservan_ambas_senales():
    a = h("anio_duplicado", "U5")
    b = h("discontinuidad_anual", "V5")
    b["evidencia"]["periodo"] = 2021
    antes = deepcopy([a, b])
    r = c.agrupar([a, b])
    assert r["senales_control"] == 2 and r["casos_revision"] == 1
    assert r["casos"][0]["primary_finding"]["evidencia"]["celda"] == "U5"
    assert r["casos"][0]["related_findings"][0]["evidencia"]["celda"] == "V5"
    assert [a, b] == antes
    b["evidencia"]["hoja"] = "Otra"
    assert c.agrupar([a, b])["casos_revision"] == 2


def test_conciliaciones_relacionadas_exigen_misma_diferencia_y_periodo():
    a = h(
        "conciliacion_aritmetica",
        "K23",
        celdas_participantes=["H!K23", "H!K17", "H!K18"],
        diferencia_absoluta=100,
        diferencia_porcentual=25,
    )
    b = h(
        "conciliacion_aritmetica",
        "K6",
        celdas_participantes=["H!K6", "H!K23"],
        diferencia_absoluta=100,
        diferencia_porcentual=25,
    )
    assert c.agrupar([a, b])["casos_revision"] == 1
    b["evidencia"]["diferencia_absoluta"] = 200
    assert c.agrupar([a, b])["casos_revision"] == 2


def test_prioridad_no_cambia_deteccion_y_contexto_no_compite():
    a = h("pico_aislado", "G6", factor_escala=6)
    assert c.prioridad(a) == "media" and a["severidad"] == "alta"
    a["evidencia"]["factor_escala"] = 10
    assert c.prioridad(a) == "alta"
    a["evidencia"]["naturaleza"] = "contexto"
    assert c.prioridad(a) == "contexto"


def test_contexto_agrupa_por_hoja_cuadro_y_anio():
    ds = []
    for hoja, cuadro in [("H", 1), ("H", 2), ("I", 1)]:
        x = h("corte_temporal", "G6")
        x.update(lente="cronista")
        x["evidencia"].update(hoja=hoja, bloque_excel=cuadro, naturaleza="contexto", requiere_contexto_anual=True)
        ds.append(x)
    previo = {"lente": "cronista", "evidencia": {"requiere_contexto_anual": True, "detalle_contexto": ds}}
    r = c.agrupar([previo])
    assert len(r["contexto"]) == 3 and r["senales_contexto"] == 3 and r["casos_revision"] == 0


def test_delta_conserva_identidad_y_atribuye_solo_lo_demostrable():
    a = h("pico_aislado", "G6", factor_escala=6)
    b = deepcopy(a)
    b["evidencia"]["factor_escala"] = 10
    meta = {
        "informe_id": 1,
        "version_codigo": "abc",
        "version_motor": "v1",
        "proveniencia": {"fuentes": [{"sha256_bruto": "123"}]},
    }
    base = {**meta, "snapshot_senales": c.snapshot([a, h("cambio_tipo", "B8")])}
    actual = {**meta, "version_codigo": "def", "snapshot_senales": c.snapshot([b, h("vacio_interior", "C9")])}
    r = c.comparar(base, actual)
    assert r["conteos"] == dict(persistentes=1, nuevos=1, desaparecidos=1, cambiaron_prioridad=1, cambiaron_evidencia=1)
    assert r["mismo_excel"] and r["mismo_motor"] and not r["mismo_codigo"]  # misma versión de reglas, otra huella


VALIDO = dict(prioritarios=[0], lectura="Revisar el dato.", explicaciones_alternativas=[], confianza="baja")


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("prioritarios", [0.5]),
        ("prioritarios", [-1]),
        ("prioritarios", [True]),
        ("explicaciones_alternativas", [{}]),
        ("extra", 1),
    ],
)
def test_esquema_estricto(campo, valor):
    with pytest.raises(ValueError):
        t._validar_interpretacion({**VALIDO, campo: valor})


def test_un_reintento_y_aislamiento_de_hallazgos():
    llamadas = []
    datos = [h("cambio_tipo", "G6")]
    antes = deepcopy(datos)

    def proveedor(ctx, hs):
        llamadas.append(ctx)
        hs.clear()
        return {
            "modelo": "gpt",
            "contenido": ({**VALIDO, "prioritarios": [10]} if len(llamadas) == 1 else VALIDO),
            "error": None,
        }

    it = t._interpretar_validado(proveedor, {}, datos)
    assert it["contenido"] == VALIDO and it["intentos"] == 2 and llamadas[-1]["_reparar_formato"]
    assert datos == antes and it["errores_formato"]


def test_error_persistente_no_se_inventa_una_respuesta():
    it = t._interpretar_validado(
        lambda *_: {"modelo": "gpt", "contenido": {"lectura": "mal"}}, {}, [h("cambio_tipo", "C2")]
    )
    assert it["contenido"] is None and it["intentos"] == 2 and len(it["errores_formato"]) == 2


pytest_plugins = ["tests.test_ejemplos_zip"]


def test_dos_corridas_guardan_delta_y_restringen_acceso(flujo):
    import models
    from routers import informes
    from scripts.ensayo_controles import bytes_libro, libro
    from services import jobs

    client, factory, actual = flujo
    client.app.include_router(informes.router, prefix="/api")
    w, mp = libro(55)
    ids = []
    for alterado in (False, True):
        if alterado:
            w.active[mp["celdas"][0][5]] = None
        response = cargar_confirmado(client, "/api/analisis-rapido",
            data={"periodo": "2026-09", "dominio": "general", "notificar": "false"},
            files={
                "archivos": (
                    "misma_fuente.xlsx",
                    bytes_libro(w),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert response.status_code == 200, response.text
        ids.append(response.json()["informe_id"])
        assert jobs._process_one()
    with factory() as db:
        i = db.get(models.Informe, ids[-1])
        d = i.devolucion.cobertura["comparacion_corridas"]
        assert d["estado"] == "comparado" and d["base"]["informe_id"] == ids[0]
        assert d["conteos"]["nuevos"] >= 1 and not d["mismo_excel"] and d["mismo_motor"]
        assert i.devolucion.cobertura["manifiesto"]["snapshot_senales"]
    detalle = client.get(f"/api/informes/{ids[-1]}/detalle")
    assert detalle.status_code == 200 and detalle.json()["revision"]["casos_revision"] >= 1
    comp = client.get(f"/api/informes/{ids[-1]}/comparacion?base_id={ids[0]}")
    assert comp.status_code == 200 and comp.json()["estado"] == "comparado"
    actual["id"] = 2
    assert client.get(f"/api/informes/{ids[-1]}/comparacion?base_id={ids[0]}").status_code == 403


def test_renombrar_una_fuente_no_convierte_todo_en_senales_nuevas():
    a = h("cambio_tipo", "C3")
    b = deepcopy(a)
    b["evidencia"]["archivo_origen"] = "a_corregido.xlsx"
    r = c.comparar({"snapshot_senales": c.snapshot([a])}, {"snapshot_senales": c.snapshot([b])})
    assert r["conteos"]["persistentes"] == 1 and not r["conteos"]["nuevos"]
    assert not r["conteos"]["cambiaron_evidencia"]


def test_snapshot_de_una_fuente_no_depende_de_senales_sin_archivo():
    from types import SimpleNamespace as N

    import services.casos_revision as c
    con = N(lente='ajedrecista', modo='control_tabular', severidad='alta', descripcion='x', evidencia={'archivo_origen': 'a.xlsx', 'hoja': 'H', 'celda': 'B2', 'regla': 'r'})
    sin = N(lente='cronista', modo='corte_temporal', severidad='media', descripcion='y', evidencia={'hoja': 'H', 'celda': 'C3', 'regla': 's'})
    # Con o sin una señal sin archivo anotado, la señal de a.xlsx conserva la misma identidad.
    k1 = {x['key'] for x in c.snapshot([con])}
    k2 = {x['key'] for x in c.snapshot([con, sin])}
    assert k1 <= k2
