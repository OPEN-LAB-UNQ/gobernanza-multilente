"""La detección textual no sustituye las decisiones ni la evidencia del participante."""
from types import SimpleNamespace

import pytest

import models
from routers import proyectos_ia as r
from tests.test_memoria_incubadora_049 import proyecto


@pytest.mark.parametrize('cierre', ['.', '?', '!'])
def test_puntuacion_editorial_conserva_la_oracion_original_y_su_limite(cierre):
    fuente = 'La IA redactará un resumen de cada expediente y la directora verificará cada resumen antes de autorizarlo.'
    cita = 'La IA redactará un resumen de cada expediente' + cierre
    assert r.memoria_tutora._cita_en_contexto(cita, fuente) == fuente
    assert r.memoria_tutora._cita_en_contexto('tenemos montos' + cierre, 'No tenemos montos ni fechas.') == 'No tenemos montos ni fechas.'


def test_puntuacion_no_permite_cambiar_palabras_o_cortar_dentro_de_ellas():
    contexto = r.memoria_tutora._cita_en_contexto
    assert contexto('Tenemos monto.', 'Tenemos montos disponibles.') is None
    assert contexto('Tenemos fechas.', 'Tenemos montos disponibles.') is None


def con_datos():
    return proyecto([('participante', 'Tenemos datos registrados en una planilla que usamos para el análisis.')])


def test_deteccion_automatica_no_se_presenta_a_la_ia_como_cierre_humano():
    p = con_datos()
    estado = r._estado_acompanamiento(p)
    assert 'Datos e insumos' in estado['con_texto_detectado']
    assert not estado['cerrados_por_participante']
    contexto = r._contexto_progreso_para_ia(p, 'Siguiente paso')
    assert 'CERRADOS POR EL PARTICIPANTE: ninguno' in contexto
    assert 'DETECCIÓN ORIENTATIVA' in contexto
    assert 'COMPLETO (no volver a preguntar)' not in contexto
    assert 'rectificaciones' in contexto


def test_posponer_prevalece_aunque_haya_coincidencias_de_texto():
    p = con_datos()
    assert next(c for c in r._checkpoint_propuesta(p)['criterios'] if c['clave'] == 'datos')['ok']
    p.mensajes.append(models.MensajeProyectoIA(id=2, remitente='control', contenido='criterio:datos:pospuesto'))
    datos = next(c for c in r._checkpoint_propuesta(p)['criterios'] if c['clave'] == 'datos')
    assert datos['pospuesto'] and not datos['ok'] and datos['evidencia']
    estado = r._estado_acompanamiento(p)
    assert 'datos' in [c['clave'] for c in estado['pospuestos']]
    assert 'Datos e insumos' not in estado['con_texto_detectado']


def test_cierre_y_reapertura_distinguen_decision_de_deteccion():
    p = con_datos()
    p.mensajes.append(models.MensajeProyectoIA(id=2, remitente='control', contenido='criterio:datos:cerrado'))
    assert 'Datos e insumos' in r._estado_acompanamiento(p)['cerrados_por_participante']
    p.mensajes.append(models.MensajeProyectoIA(id=3, remitente='control', contenido='criterio:datos:abierto'))
    estado = r._estado_acompanamiento(p)
    assert not estado['cerrados_por_participante']
    assert 'Datos e insumos' in estado['con_texto_detectado']


def test_prompt_no_reintroduce_fragmentos_clasificados_como_aportes_nuevos(monkeypatch):
    import sys
    p = con_datos()
    recibido = {}
    def crear(**kwargs):
        recibido.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Síntesis del caso.'), finish_reason='stop')])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))
    monkeypatch.setattr(r.settings, 'openai_api_key', 'test-only')
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(OpenAI=lambda **kw: client))
    class DB:
        def query(self, *args): return self
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def limit(self, *args): return self
        def all(self): return list(reversed(p.mensajes))
    r._respuesta_ia(DB(), p, 'Resumí el caso')
    textos = [m['content'] for m in recibido['messages']]
    assert not any('Fragmentos ya aportados' in t for t in textos)
    assert any('Fuente aporte_1' in t and p.mensajes[0].contenido in t for t in textos)
