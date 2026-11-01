import hashlib
from types import SimpleNamespace

from services import certificaciones, guardrails, proveniencia, sanitizacion, validez


def informe(datos, contexto=None):
    return SimpleNamespace(id=17, datos=datos, hallazgos=[], saneamiento={"contexto_validacion": contexto or {}}, periodo="2026-09")


def test_condicion_critica_incompleta_no_se_da_por_verificada():
    i = informe([{"total": 1, "moneda": "ARS"}, {"total": 2}], {"condiciones_criticas": ["moneda"]})
    v = validez.evaluar(i)
    assert v["estado"] == "no_evaluable" and not v["puede_concluir"]
    assert any(c["condicion"] == "moneda" and c["categoria_incidencia"] == "condiciones_no_satisfechas" for c in v["condiciones_no_verificadas"])


def test_hash_bruto_y_procesado_con_transformaciones():
    bruto = b"total,dni\n100,12345678\n"
    saneados, reporte = sanitizacion.sanear([{"total": 100, "dni": "12345678"}])
    origen = proveniencia.registrar([("datos.csv", bruto)], saneados, reporte, 7, {"datos.csv": "text/csv"})
    assert origen["fuentes"][0]["sha256_bruto"] == hashlib.sha256(bruto).hexdigest()
    assert origen["sha256_procesado"] == proveniencia.huella([{"total": 100}])
    assert origen["fuentes"][0]["tamano_bytes"] == len(bruto)
    assert origen["transformaciones"][-1]["detalle"]["exclusiones"][0]["columna"] == "dni"
    assert "12345678" not in str(origen)


def test_evidencia_y_reingreso_conservan_vinculo_de_fuente():
    i = informe([{"total": 12}])
    i.saneamiento["proveniencia"] = proveniencia.registrar([("a.csv", b"total\n12")], i.datos, {}, 7)
    ev = proveniencia.evidencia_origen({}, i)
    fuente = i.saneamiento["proveniencia"]["fuentes"][0]
    assert ev["fuente_ids"] == [fuente["id"]]
    siguiente = proveniencia.registrar([("a.csv", b"total\n13")], [{"total": 13}], {}, 7, anterior=i)
    assert siguiente["fuentes"][0]["version"] == 2
    assert siguiente["fuentes"][0]["fuente_anterior_id"] == fuente["id"]


def test_multiples_fuentes_sin_localizador_declaran_ambiguedad():
    i = informe([{"total": 12}])
    i.saneamiento["proveniencia"] = proveniencia.registrar([("a.csv", b"a"), ("b.csv", b"b")], i.datos, {}, 7)
    assert proveniencia.evidencia_origen({}, i)["estado"] == "archivo_no_resuelto"
    assert len(proveniencia.evidencia_origen({"archivo": "a.csv"}, i)["fuente_ids"]) == 1


def test_condicion_critica_ausente_no_concluye_ni_sugiere_conformidad_b1():
    i = informe([{"total": 12}], {"condiciones_criticas": ["moneda"]})
    condiciones = validez.evaluar(i)
    assert condiciones["estado"] == "no_evaluable"
    assert condiciones["puede_concluir"] is False
    i.devolucion = SimpleNamespace(cobertura={"condiciones_validez": condiciones})
    assert certificaciones.estado_inicial_b1(SimpleNamespace(codigo="B1-01"), i) == "no_evaluable"


def test_condicion_fallida_y_esquema_incompatible_bloquean():
    i = informe([{"moneda": "ARS", "total": 12}, {"moneda": "USD", "total": 13}], {"condiciones_criticas": ["moneda"]})
    assert not validez.evaluar(i)["puede_concluir"]
    i = informe([{"importe": 12}])
    r = validez.evaluar(i, validez.esquema([{"total": 12}]))
    assert r["cambio_esquema"] and r["estado"] == "no_evaluable"


def test_guardrails_y_proveniencia_se_aplican_a_cada_hallazgo():
    hs = guardrails.normalizar_hallazgos([
        {"lente": "ajedrecista", "descripcion": "fraude", "evidencia": {}},
        {"lente": "rizoma", "descripcion": "asociación exploratoria", "evidencia": {}},
    ], informe([{"total": 12}]))
    assert all(h["limites"]["guardrails"]["aplicados"] for h in hs)
    assert hs[0]["limites"]["guardrails"]["cambios"]
    assert hs[1]["evidencia"]["naturaleza"] == "exploratoria"
    assert hs[0]["evidencia"]["proveniencia"]["estado"] == "origen_historico_no_registrado"


def test_cruce_documental_sin_unidades_no_se_declara_comparable():
    datos = [{"archivo_origen": "a.csv", "total": 10}, {"archivo_origen": "b.csv", "total": 20}]
    assert validez.condiciones_interdocumentales(datos)["estado"] == "no_evaluable"
    for fila in datos:
        fila.update(periodo="2026-09", entidad="A", moneda="ARS", unidad="pesos", escala="unidad")
    assert validez.condiciones_interdocumentales(datos)["estado"] == "evaluado"
    datos[1]["moneda"] = "USD"
    assert validez.condiciones_interdocumentales(datos)["estado"] == "no_evaluable"


def test_convergencia_no_modifica_naturaleza_ni_afirma_independencia():
    from copy import deepcopy

    from services.convergencia import detectar_convergencia
    hs = [{"id": 1, "lente": "rizoma", "evidencia": {"periodo": "2026-09", "naturaleza": "exploratoria"}},
          {"id": 2, "lente": "matematico", "evidencia": {"periodo": "2026-09"}}]
    antes = deepcopy(hs)
    grupos = detectar_convergencia(hs)
    assert grupos and not grupos[0]["produce_certeza"]
    assert not grupos[0]["independencia_verificada"]
    assert hs == antes
