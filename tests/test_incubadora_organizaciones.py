"""La Incubadora se adapta a una cohorte de organizaciones sin cambiar la del sector público."""
from pathlib import Path

from config import settings
from routers import proyectos_ia


def test_cohorte_publica_conserva_el_prompt(monkeypatch):
    monkeypatch.setattr(settings, "incubadora_ambito", "publico")
    assert proyectos_ia.system_prompt_incubadora() == proyectos_ia.SYSTEM_PROMPT


def test_cohorte_de_organizaciones_cambia_el_rol_y_no_prohibe_hablar_de_proveedores(monkeypatch):
    monkeypatch.setattr(settings, "incubadora_ambito", "organizacion")
    texto = proyectos_ia.system_prompt_incubadora()
    assert "empleados publicos" not in texto and "administracion publica" not in texto
    assert "compras publicas, proveedores, contratistas" not in texto
    assert "organizaciones (empresas, pymes, cooperativas, ONG y universidades)" in texto
    assert "datos agregados o ficticios" in texto
    # Cada reemplazo tiene que encontrar su texto: si el prompt cambia, este test lo avisa.
    for viejo, _ in proyectos_ia._PROMPT_ORGANIZACION:
        assert viejo in proyectos_ia.SYSTEM_PROMPT, viejo[:60]


def test_la_pantalla_habla_a_organismos_y_organizaciones():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text(encoding="utf-8")
    assert "Organismo, organización o área" in html and "Organismo o área</label>" not in html
    assert "Transformá una necesidad de tu organismo u organización" in html


def test_conexiones_permite_enfocar_un_proyecto():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(encoding="utf-8")
    assert "state.conexionFoco" in js and "Todos los proyectos (mapa general)" in js
    assert "El proyecto elegido va primero en cada tema" in js
