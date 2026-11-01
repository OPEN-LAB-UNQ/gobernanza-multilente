"""El prompt de la tutora: voseo, y una versión para organizaciones que no se rompe en silencio."""
import re

from routers import proyectos_ia


def test_cada_reemplazo_de_organizaciones_encuentra_su_texto():
    for viejo, _ in proyectos_ia._PROMPT_ORGANIZACION:
        assert proyectos_ia.SYSTEM_PROMPT.count(viejo) == 1, viejo


def test_el_prompt_de_organizaciones_no_habla_de_administracion_publica(monkeypatch):
    monkeypatch.setattr(proyectos_ia.settings, "incubadora_ambito", "organizacion")
    texto = proyectos_ia.system_prompt_incubadora()
    assert "administración pública" not in texto and "empleados públicos" not in texto
    assert "en organizaciones" in texto


def test_imperativos_en_voseo():
    # Los imperativos sin tilde se leían como tuteo («Usa», «Trabaja», «Propone», «Hace»).
    for tuteo in ("Usa un tono", "Trabaja siempre", "Propone, cuando", "Hace como maximo", "Enfoca la conversacion", "Distingui siempre"):
        assert tuteo not in proyectos_ia.SYSTEM_PROMPT
    assert re.search(r"\bUsá un tono\b", proyectos_ia.SYSTEM_PROMPT)
    # Preguntas de afinado (tutoría del 10/10): opcionales, nunca un criterio nuevo.
    assert "no se copia en un fin de semana" in proyectos_ia.SYSTEM_PROMPT and "contra qué casos" in proyectos_ia.SYSTEM_PROMPT
    assert "podés sumar como OPCIONAL, de a una y sin convertirlas en requisito" in proyectos_ia.SYSTEM_PROMPT


def test_predevoluciones_guardadas_no_muestran_la_herramienta_personal_de_notas():
    from types import SimpleNamespace
    m = SimpleNamespace(id=1, proyecto_id=1, usuario_id=1, remitente="predevolucion_ia", creado_en=None,
                        contenido="Esta pre-devolución fue realizada íntegramente por inteligencia artificial, "
                                  "tomando como referencia las notas de Obsidian de Maximiliano Pérez.")
    salida = proyectos_ia._mensaje_out(m)["contenido"]
    assert "Obsidian" not in salida and "notas de orientación del docente responsable" in salida
