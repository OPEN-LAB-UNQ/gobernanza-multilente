"""Topes de Incubadora para textos largos (consulta de una participante, 05/10/2026).

Una propuesta corregida no entraba en «Guardar contexto» (8.000 caracteres) ni en la consulta al docente
(12.000): ahora ambos admiten 30.000, como la entrega. Al asistente se le envía el contexto acotado.
"""
import schemas
from routers import proyectos_ia


def test_contexto_admite_lo_mismo_que_la_entrega():
    assert proyectos_ia.MAX_SITUACION_CHARS == proyectos_ia.MAX_ENTREGA_CHARS == 30000


def test_consulta_al_docente_admite_una_propuesta_completa():
    largo = "a" * 25000
    assert schemas.ProyectoIADocenteMensajeCreate(mensaje=largo).mensaje == largo
    assert proyectos_ia.MAX_MENSAJE_DOCENTE_CHARS == 30000


def test_chat_con_el_asistente_conserva_su_tope():
    assert proyectos_ia.MAX_MENSAJE_CHARS == 12000
    try:
        schemas.ProyectoIAMensajeCreate(mensaje="a" * 12001)
    except Exception:  # noqa: BLE001 - pydantic ValidationError
        pass
    else:
        raise AssertionError("el chat con el asistente debería seguir limitado a 12.000 caracteres")


def test_el_asistente_recibe_el_contexto_acotado():
    assert proyectos_ia.MAX_SITUACION_PARA_IA < proyectos_ia.MAX_SITUACION_CHARS


def test_la_interfaz_usa_los_mismos_topes_que_el_servidor():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    assert f"const MAX_SITUACION_CHARS = {proyectos_ia.MAX_SITUACION_CHARS};" in js
    assert f"const MAX_MENSAJE_CHARS = {proyectos_ia.MAX_MENSAJE_CHARS};" in js
    assert f"const MAX_ENTREGA_CHARS = {proyectos_ia.MAX_ENTREGA_CHARS};" in js
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="proyecto-situacion-contador"' in html and 'id="proyecto-mensaje-contador"' in html
