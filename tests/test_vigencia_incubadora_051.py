"""Rectificaciones posteriores y aportes incluidos dentro de pedidos de ayuda."""
import json
from types import SimpleNamespace

import pytest

from services import memoria_incubadora as m
from tests.test_memoria_incubadora_049 import proyecto, revision
from tests.test_pertinencia_incubadora_050 import cliente_falso

# Referencias humanas para llamadas reales fuera de la suite sin credenciales.
CASOS_VIGENCIA = [
    {"nombre": "retira_disponibilidad", "criterio": "datos", "mensajes": [
        "Tenemos fechas y montos disponibles.", "Corrijo: sólo tenemos identificadores. No tenemos fechas ni montos disponibles."],
     "citar": 1, "esperado": False},
    {"nombre": "confirmacion_nueva", "criterio": "datos", "mensajes": [
        "No tenemos fechas disponibles.", "Actualizo: ahora sí tenemos fechas disponibles en una planilla pública."],
     "citar": 2, "esperado": True},
    {"nombre": "negacion_antigua_superada", "criterio": "datos", "mensajes": [
        "No tenemos fechas disponibles.", "Actualizo: ahora sí tenemos fechas disponibles en una planilla pública."],
     "citar": 1, "esperado": False},
    {"nombre": "otra_variable_no_invalida", "criterio": "datos", "mensajes": [
        "Tenemos fechas de ingreso disponibles.", "Corrijo: no tenemos los montos, pero sí las fechas de ingreso."],
     "citar": 1, "esperado": True},
    {"nombre": "historia_no_es_presente", "criterio": "evidencia", "mensajes": [
        "En 2024 registramos 40 expedientes con demoras de más de 60 días.", "Actualizo: en 2026 ya no hay expedientes demorados."],
     "citar": 1, "esperado": True},
    {"nombre": "retira_certeza", "criterio": "datos", "mensajes": [
        "Confirmo que tenemos acceso a los montos.", "No estoy seguro de tener acceso a los montos; retiro lo dicho sobre su disponibilidad."],
     "citar": 1, "esperado": False},
    {"nombre": "rectifica_registro_historico", "criterio": "evidencia", "mensajes": [
        "En marzo contamos 12 pagos duplicados.", "Rectifico el registro de marzo: esos 12 pagos no estaban duplicados, el listado era incorrecto."],
     "citar": 1, "esperado": False},
    {"nombre": "periodos_distintos", "criterio": "evidencia", "mensajes": [
        "En marzo contamos 12 pagos duplicados.", "Actualizo: en abril no encontramos ningún pago duplicado."],
     "citar": 1, "esperado": True},
    {"nombre": "permiso_actualizado_no_es_historia", "criterio": "datos", "mensajes": [
        "El área no autoriza exportar los registros.", "Actualizo: el área autorizó exportar los registros anonimizados."],
     "citar": 1, "esperado": False},
    {"nombre": "permiso_nuevo_se_conserva", "criterio": "datos", "mensajes": [
        "El área no autoriza exportar los registros.", "Actualizo: el área autorizó exportar los registros anonimizados."],
     "citar": 2, "esperado": True},
]


def material(caso):
    p = proyecto([("participante", t) for t in caso["mensajes"]])
    fuente = f"aporte_{caso['citar']}"
    texto = caso["mensajes"][caso["citar"] - 1]
    contenido = json.dumps({"criterios": [
        {"clave": c, "citas": [{"fuente": fuente, "cita": texto}] if c == caso["criterio"] else [], "pendiente": ""}
        for c in m.CRITERIOS]}, ensure_ascii=False)
    return contenido, m.fuentes_participante(p)


@pytest.mark.parametrize("prefijo", ["Resumí esto: ", "Revisá este aporte: ", "Evaluá el caso: "])
def test_pedido_introductorio_conserva_datos_y_negaciones(prefijo):
    aporte = "Tenemos fechas de ingreso confirmadas; no tenemos montos."
    assert m.contenido_aportado(prefijo + aporte) == aporte
    fuentes = m.fuentes_participante(proyecto([("participante", prefijo + aporte)]))["fuentes"]
    assert fuentes["aporte_1"]["texto"] == aporte


def test_una_lista_de_criterios_sigue_sin_ser_dato():
    assert not m.contenido_aportado("Revisá estos diez criterios: problema, datos, flujo y supervisión.")


@pytest.mark.parametrize("aclaracion", ["En realidad sólo tenemos identificadores.",
    "Ya no tenemos acceso a esa base.", "Ahora sí tenemos los datos.", "No estoy seguro de tener permiso."])
def test_rectificaciones_se_priorizan_en_la_memoria(aclaracion):
    memoria = m.fuentes_participante(proyecto([("participante", aclaracion)]))
    assert memoria["fuentes"]["aporte_1"]["aclaracion"]


def test_verificador_recibe_rectificacion_y_orden_sin_conclusiones_anteriores():
    contenido, memoria = material(CASOS_VIGENCIA[0])
    recibido = {}
    def crear(**kwargs):
        recibido.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "evaluaciones": [{"id": "datos:0", "motivo": "Disponibilidad retirada después.",
                              "pertinente": True, "rectificada": True}]})), finish_reason="stop")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))
    veredicto = m.comprobar_pertinencia(client, "modelo", contenido, memoria)
    payload = json.loads(recibido["messages"][1]["content"])
    assert payload["aclaraciones"][0]["orden_fuente"] > payload["citas"][0]["orden_fuente"]
    assert payload["citas"][0]["aclaraciones_posteriores"] == ["aporte_2"]
    assert "No tenemos fechas ni montos" in payload["aclaraciones"][0]["texto"]
    assert "pendiente" not in recibido["messages"][1]["content"]
    salida = m.render_revision(contenido, memoria, {}, veredicto)
    assert "Tenemos fechas y montos disponibles" not in salida
    assert "contexto actual" in salida


def test_aclaracion_anterior_no_se_presenta_como_posterior():
    contenido, memoria = material(CASOS_VIGENCIA[1])
    candidata = m.candidatas_pertinencia(contenido, memoria)[0]
    assert candidata["fuente"] == "aporte_2"
    assert candidata["orden_fuente"] == list(memoria["fuentes"]).index("aporte_2")


def test_aclaracion_archivada_no_llega_al_verificador():
    p = proyecto([("participante", "Tenemos fechas disponibles."),
                  ("archivado_participante", "Corrijo: no tenemos nada."),
                  ("ia", "Corrijo: no hay fechas.")])
    memoria = m.fuentes_participante(p)
    assert all(not f["aclaracion"] for f in memoria["fuentes"].values())
    texto = revision([{"fuente": "aporte_1", "cita": "Tenemos fechas disponibles."}])
    assert len(m.candidatas_pertinencia(texto, memoria)) == 1


@pytest.mark.parametrize("rectificada", [None, "false", 0])
def test_veredicto_sin_vigencia_booleana_no_se_publica(rectificada):
    contenido, memoria = material(CASOS_VIGENCIA[0])
    salida = json.dumps({"evaluaciones": [{"id": "datos:0", "motivo": "Disponible.",
                                         "pertinente": True, "rectificada": rectificada}]})
    with pytest.raises(ValueError):
        m.comprobar_pertinencia(cliente_falso(salida), "modelo", contenido, memoria)


def test_la_ultima_aclaracion_no_puede_invalidarse_a_si_misma():
    caso = {"criterio": "datos", "mensajes": ["Tenemos fechas disponibles.",
            "Corrijo: no tenemos fechas disponibles."], "citar": 2}
    contenido, memoria = material(caso)
    recibido = {}
    def crear(**kwargs):
        recibido.update(kwargs)
        # Reproduce la clasificación errónea observada con el proveedor real.
        return cliente_falso(json.dumps({"evaluaciones": [{"id": "datos:0", "motivo": "Dato retirado.",
            "pertinente": True, "rectificada": True}]})).chat.completions.create(**kwargs)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))
    veredicto = m.comprobar_pertinencia(client, "modelo", contenido, memoria)
    assert veredicto == {"datos:0": True}
    payload = json.loads(recibido["messages"][1]["content"])
    assert payload["aclaraciones"] == []
    assert payload["citas"][0]["aclaraciones_posteriores"] == []
    assert "no tenemos fechas" in m.render_revision(contenido, memoria, {}, veredicto)


def test_verificador_razonador_no_envia_parametros_incompatibles():
    contenido, memoria = material(CASOS_VIGENCIA[0])
    recibido = {}
    def crear(**kwargs):
        recibido.update(kwargs)
        return cliente_falso(json.dumps({"evaluaciones": [{"id": "datos:0", "motivo": "Retirada.",
            "pertinente": True, "rectificada": True}]})).chat.completions.create(**kwargs)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))
    assert not m.comprobar_pertinencia(client, "gpt-5.4-mini", contenido, memoria)["datos:0"]
    assert "temperature" not in recibido and "max_tokens" not in recibido
    assert recibido["reasoning_effort"] == "low" and recibido["max_completion_tokens"] > 0
