"""0.10.63: la tutora de la Incubadora no deja preguntas cortadas, no repite pendientes ya respondidos y la revisión
con citas prefiere los aportes más recientes.

Caso real (30/10/2026): un participante de una comisión del grupo original recibió ítems como «2. Por ejemplo,» sin pregunta,
la tutora tomó una sigla por el nombre de un fenómeno climático y, después de que él respondió punto por punto, le
volvió a listar los mismos pendientes; la revisión citó, para el problema, su frase más antigua. Los textos de abajo
son de prueba, no los suyos.
"""
import pytest

from routers import proyectos_ia as r
from services import memoria_incubadora as memoria
from tests.test_memoria_incubadora_049 import proyecto

CIERRE = "\n\nCon estas respuestas avanzamos."


@pytest.mark.parametrize("texto,esperado", [
    # Negrita alrededor de la pregunta descartada: no queda «2. ****».
    ("1. **¿Qué proceso querés mejorar?**\n2. **¿Quiénes se ven afectados?** Por ejemplo, familias en zonas inundables." + CIERRE,
     "1. **¿Qué proceso querés mejorar?**" + CIERRE),
    # Etiqueta pegada a la pregunta: no queda «2. **Usuarios:** Por ejemplo, …».
    ("1. **Proceso:** ¿Qué proceso querés mejorar?\n2. **Usuarios:** ¿Quiénes se ven afectados? Por ejemplo, familias." + CIERRE,
     "1. **Proceso:** ¿Qué proceso querés mejorar?" + CIERRE),
    # El ejemplo en líneas con sangría era del ítem descartado: no se pega al anterior.
    ("1. ¿Qué problema genera el fenómeno?\n2. ¿Quiénes se ven afectados?\n   Por ejemplo,\n   familias, escuelas." + CIERRE,
     "1. ¿Qué problema genera el fenómeno?" + CIERRE),
    # En prosa, el ejemplo de la pregunta descartada se va con ella.
    ("Entiendo el foco. ¿Qué proceso querés mejorar? ¿Quiénes se ven afectados? Por ejemplo, familias en zonas "
     "inundables, salud pública, defensa civil, etc. Con eso avanzamos.",
     "Entiendo el foco. ¿Qué proceso querés mejorar? Con eso avanzamos."),
    # Lo que ya funcionaba sigue igual.
    ("Te pregunto:\n\n1. ¿Qué proceso querés mejorar? Por ejemplo, ¿la prevención o la respuesta?\n2. ¿Quiénes se ven "
     "afectados? Por ejemplo, familias en zonas inundables." + CIERRE,
     "Te pregunto:\n\n1. ¿Qué proceso querés mejorar?" + CIERRE),
])
def test_el_filtro_de_preguntas_no_deja_frases_cortadas(texto, esperado):
    salida = r._limitar_preguntas(texto, 1)
    assert salida == esperado
    assert "****" not in salida and r._HUECO not in salida


def test_un_ejemplo_de_una_pregunta_que_queda_no_se_toca():
    texto = "¿Quiénes se ven afectados? Por ejemplo, familias en zonas inundables. Con eso avanzamos."
    assert r._limitar_preguntas(texto, 1) == texto


def test_la_tutora_no_repite_pendientes_ni_supone_siglas():
    assert "Tampoco repitas un pendiente con las mismas palabras" in r.SYSTEM_PROMPT
    assert "preguntá qué es antes de suponerlo" in r.SYSTEM_PROMPT


def test_en_el_borrador_reconoce_lo_ya_respondido_de_cada_faltante():
    p = proyecto([("participante", "Tenemos datos registrados en una planilla que usamos para el análisis.")])
    contexto = r._contexto_progreso_para_ia(p, "Generá un borrador con toda la información que ya aporté.")
    assert "BORRADOR" in contexto and "Para cada faltante que el participante ya abordó" in contexto
    pendientes = r._contexto_progreso_para_ia(p, "Mostrame qué falta para cerrar mi propuesta.")
    assert "PENDIENTES" in pendientes and "Para cada faltante que el participante ya abordó" in pendientes


def test_una_respuesta_en_varios_puntos_se_incorpora_punto_por_punto():
    p = proyecto([("participante", "Tenemos datos registrados en una planilla que usamos para el análisis.")])
    respuesta = "#1 Falta de recursos y coordinación. #2 Usuario técnico: el área de obras. #3 Proyectos con más de 30 años."
    assert "RESPUESTA EN VARIOS PUNTOS" in r._contexto_progreso_para_ia(p, respuesta)
    assert "RESPUESTA EN VARIOS PUNTOS" not in r._contexto_progreso_para_ia(p, "Siguiente paso")
    assert r._responde_varios_puntos("1. Uno.\n2. Dos.") and not r._responde_varios_puntos("Tenemos 2 planillas.")


def test_la_revision_sabe_cual_aporte_es_mas_reciente():
    p = proyecto([("participante", "La demora se debe a la proximidad del fenómeno."),
                  ("participante", "La demora promedio es de entre 4 y 10 años y afecta a proyectos de más de 30 años.")])
    mem = memoria.fuentes_participante(p)
    aportes = [f for clave, f in mem["fuentes"].items() if clave.startswith("aporte_")]
    assert [(f["orden"], f["total"]) for f in aportes] == [(1, 2), (2, 2)]
    textos = [m["content"] for m in memoria.mensajes_fuentes(mem)]
    assert any("aporte 1 de 2, del más antiguo al más reciente" in t for t in textos)
    assert any("aporte 2 de 2, del más antiguo al más reciente" in t for t in textos)
    assert "citá el más reciente y completo" in memoria.REVISION_INSTRUCCIONES
