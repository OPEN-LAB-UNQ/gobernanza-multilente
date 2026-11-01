"""Las opciones de fórmulas dicen qué corre siempre y qué suma cada casilla (12/10/2026)."""

from pathlib import Path

INDEX = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def _bloque_formulas() -> str:
    inicio = INDEX.index('<div class="technical-options"')
    return INDEX[inicio:INDEX.index("</div>", inicio)]


def test_aclara_que_lentes_y_control_basico_corren_siempre():
    bloque = _bloque_formulas()
    assert "Revisiones extra de fórmulas" in bloque
    assert "corren siempre" in bloque
    assert "control básico de fórmulas" in bloque


def test_la_casilla_de_ponderaciones_no_se_presenta_como_la_lente_matematico():
    # La lente Matemático corre en todo análisis; la casilla sólo suma el control de
    # promedios simples cuando el archivo trae ponderadores.
    assert "Activar lente Matemático" not in INDEX
    assert "Promedios que no ponderan" in _bloque_formulas()


def test_las_tres_casillas_conservan_sus_ids():
    bloque = _bloque_formulas()
    for ident in ("opt-formulas-excel", "opt-patrones-calculo", "opt-metodo-calculo"):
        assert f'id="{ident}"' in bloque


def test_promedios_que_no_ponderan_viene_tildada():
    # Banco s7011 (12/10/2026): sin efecto en planillas sin ponderadores (164/174, 0 falsas alarmas).
    assert 'id="opt-metodo-calculo" checked' in _bloque_formulas()
    assert 'id="opt-formulas-excel" />' in _bloque_formulas()
