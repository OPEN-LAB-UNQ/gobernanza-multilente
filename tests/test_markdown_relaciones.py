"""Informe completo (20/10/2026): dos planillas de un instituto de estadística (cuentas internacionales) rompían el markdown con
KeyError 'total_declarado' porque una relación adicional de otra regla no trae total declarado."""

from services.reportes.markdown import _evidencia_markdown


def test_relacion_sin_total_declarado_no_rompe_el_informe():
    ev = {"regla": "pico_aislado", "puntaje_prioridad": 80, "conciliaciones": [
        {"regla": "cambio_escala_sostenido", "celdas_participantes": ["Cuadro 11!C9", "Cuadro 11!D9"]},
        {"regla": "otra", "celdas_participantes": None},
    ]}
    texto = "\n".join(_evidencia_markdown(ev))
    assert "Relación adicional (cambio escala sostenido)" in texto
    assert "Cuadro 11!C9" in texto
    assert "sin celdas identificadas" in texto


def test_conciliacion_con_total_declarado_se_sigue_mostrando_con_cifras():
    ev = {"regla": "x", "puntaje_prioridad": 80, "conciliaciones": [
        {"regla": "conciliacion_aritmetica", "celdas_participantes": ["H!B2"], "total_declarado": 10.0,
         "total_reconstruido": 9.0, "diferencia_absoluta": 1.0}]}
    texto = "\n".join(_evidencia_markdown(ev))
    assert "Conciliación adicional: declarado 10; reconstruido 9; diferencia 1" in texto
