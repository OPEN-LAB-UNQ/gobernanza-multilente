"""Regresiones de pertinencia, consignas del botón y pedidos de síntesis."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import models
from routers import proyectos_ia as r
from services import memoria_incubadora as m
from tests.test_memoria_incubadora_049 import proyecto, revision

# Etiquetas manuales para contrastar el verificador con el proveedor real fuera de CI.
CASOS_PERTINENCIA = [
    ("evidencia", "Queremos reducir las demoras en los expedientes.", False),
    ("evidencia", "En julio registramos 34 expedientes con más de 60 días de demora.", True),
    ("evidencia", "Sólo tengo el identificador del proyecto; no confirmé fechas ni montos.", False),
    ("datos", "Sólo tengo el identificador del proyecto; no confirmé fechas ni montos.", True),
    ("datos", "Tenemos fechas y montos en una planilla pública.", True),
    ("indicador", "El objetivo es reducir demoras en las obras.", False),
    ("indicador", "Mediremos la mediana de días entre ingreso y resolución de cada expediente.", True),
    ("indicador", "Queremos mejorar la eficiencia y el impacto.", False),
    ("flujo", "Queremos IA para generar reportes.", False),
    ("flujo", "Hoy la oficina recibe la solicitud, verifica la documentación y la remite a firma.", True),
    ("rol_ia", "La IA redactará un resumen de cada expediente.", True),
    ("supervision", "Revisá estos diez criterios y decime qué falta.", False),
    ("supervision", "La directora verificará cada alerta antes de tomar una decisión.", True),
    ("usuarios", "Actores: Ministerio, Congreso, municipios y proveedores.", False),
    ("usuarios", "Los analistas de la oficina usarán el panel cada mañana.", True),
    ("riesgos", "Todavía tengo que completar riesgos, indicadores y supervisión.", False),
    ("riesgos", "Una alerta incorrecta podría retrasar el pago a un proveedor.", True),
    ("proximo_paso", "sobre ia para generar reportes", False),
    ("proximo_paso", "La próxima semana la oficina seleccionará diez expedientes para el piloto.", True),
    ("problema", "Queremos reducir demoras en obras hídricas preventivas.", True),
    ("problema", "Reducir demoras de ejecución.", True),
]


def cliente_falso(contenido):
    def crear(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido), finish_reason="stop")])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))


def test_el_prompt_real_del_boton_no_suma_criterios_ni_fuentes():
    app = (Path(__file__).parents[1] / "static/app.js").read_text(encoding="utf-8")
    bloque = app.split("function promptPruebaClaridadProyecto()", 1)[1].split("async function probarClaridadProblema", 1)[0]
    lineas = re.findall(r'^\s*(".*")\s*,?\s*$', bloque, re.M)
    prompt = "\n".join(json.loads(x) for x in lineas)
    assert "estos diez criterios" in prompt and "El contador" in prompt
    p = proyecto([("participante", "Sólo tengo el identificador del proyecto.")])
    antes = r._checkpoint_propuesta(p)["completos"]
    p.mensajes.append(models.MensajeProyectoIA(id=2, remitente="participante", contenido=prompt))
    assert r._checkpoint_propuesta(p)["completos"] == antes
    assert "aporte_2" not in m.fuentes_participante(p)["fuentes"]


@pytest.mark.parametrize("pedido", ["Resumí qué entendiste.", "Resumí el problema sin agregar datos.",
                                   "¿Qué entendiste?", "Podés resumir el caso?", "Solo dame un resumen."])
def test_sintesis_no_abre_preguntas(pedido):
    p = proyecto([("participante", "Me refiero al fenómeno climático El Niño.")])
    assert r._pide_sintesis(pedido)
    salida = r._respuesta_sin_insistencia("El caso trata sobre El Niño.\nPara seguir:\n1. ¿Quién lo supervisa?\n2. ¿Qué datos tenés?", p, pedido)
    assert salida == "El caso trata sobre El Niño."


@pytest.mark.parametrize("pedido", ["La IA debe resumir expedientes.", "No quiero un resumen.",
                                   "Resumí y haceme dos preguntas.", "Generá un borrador."])
def test_una_mencion_o_un_pedido_mixto_no_se_toma_como_solo_sintesis(pedido):
    assert not r._pide_sintesis(pedido)


def test_cita_literal_pero_no_pertinente_no_se_muestra_como_sustento():
    memoria = m.fuentes_participante(proyecto([("participante", "Queremos reducir demoras.")]))
    texto = revision([{"fuente": "aporte_1", "cita": "Queremos reducir demoras."}])
    assert "Queremos reducir demoras" not in m.render_revision(texto, memoria, {}, {"datos:0": False})
    assert "no sustenta el criterio con el contexto actual" in m.render_revision(texto, memoria, {}, {"datos:0": False})


def test_pertinencia_no_borra_la_negacion_de_un_dato():
    memoria = m.fuentes_participante(proyecto([("participante", "No tenemos montos disponibles.")]))
    texto = revision([{"fuente": "aporte_1", "cita": "tenemos montos disponibles"}])
    candidatos = m.candidatas_pertinencia(texto, memoria)
    assert candidatos[0]["texto"] == "No tenemos montos disponibles."
    salida = m.render_revision(texto, memoria, {}, {"datos:0": True})
    assert "No tenemos montos disponibles" in salida


def test_la_cita_no_toma_evidencia_de_la_oracion_siguiente():
    fuente = "Queremos reducir demoras. En julio registramos 34 expedientes atrasados."
    assert m._cita_en_contexto("Queremos reducir demoras.", fuente) == "Queremos reducir demoras."
    assert m._cita_en_contexto("reducir demoras", fuente) == "Queremos reducir demoras."


def test_mayuscula_editorial_se_resuelve_con_texto_original_sin_cambiar_palabras():
    fuente = "La IA resume y la directora verificará cada resumen."
    assert m._cita_en_contexto("La directora verificará cada resumen.", fuente) == fuente
    assert m._cita_en_contexto("La directora aprobará cada resumen.", fuente) is None
    assert m._cita_en_contexto("TENEMOS MONTOS", "No tenemos montos.") == "No tenemos montos."


@pytest.mark.parametrize("salida", ['{"evaluaciones": []}', '{"evaluaciones": [{"id": "otro", "pertinente": true}]}',
                                    '{"evaluaciones": [{"id": "datos:0", "pertinente": "true"}]}', 'no es json'])
def test_verificacion_invalida_no_se_acepta(salida):
    memoria = m.fuentes_participante(proyecto([("participante", "Tengo fechas disponibles.")]))
    texto = revision([{"fuente": "aporte_1", "cita": "Tengo fechas disponibles."}])
    with pytest.raises(ValueError):
        m.comprobar_pertinencia(cliente_falso(salida), "modelo", texto, memoria)


def test_sin_citas_literales_no_se_llama_de_nuevo_al_proveedor():
    assert m.comprobar_pertinencia(None, "modelo", revision(), m.fuentes_participante(proyecto([]))) == {}


def test_falla_del_verificador_no_publica_revision_no_comprobada(monkeypatch):
    import sys

    p = proyecto([("participante", "Tengo fechas disponibles.")])
    client = cliente_falso(revision([{"fuente": "aporte_1", "cita": "Tengo fechas disponibles."}]))
    monkeypatch.setattr(r.settings, "openai_api_key", "test-only")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kw: client))
    def fallar(*args):
        raise TimeoutError("verificación no disponible")
    monkeypatch.setattr(m, "comprobar_pertinencia", fallar)
    class DB:
        def query(self, *a): return self
        def filter(self, *a): return self
        def order_by(self, *a): return self
        def limit(self, *a): return self
        def all(self): return list(reversed(p.mensajes))
    with pytest.raises(r.HTTPException) as error:
        r._respuesta_ia(DB(), p, "Revisá estos diez criterios")
    assert error.value.status_code == 503
