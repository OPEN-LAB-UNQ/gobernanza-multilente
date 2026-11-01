"""0.10.16: modo básico (por defecto) y avanzado; frase llana también para las variaciones anuales que son casos."""
from pathlib import Path

from services.casos_revision import agrupar

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_interruptor_y_reglas_del_modo_basico():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'id="modo-avanzado"' in html
    for marcado in ('id="detalle-completo" class="detalle-completo solo-avanzado"', 'class="advanced-options solo-avanzado"',
                    'class="notify-panel solo-avanzado"', 'class="disclaimer solo-avanzado"'):
        assert marcado in html, marcado
    assert "body.modo-basico .solo-avanzado { display: none !important; }" in css
    assert 'const MODO_CLAVE = "gobernanza-modo";' in js and 'item.seccion === "acerca"' in js


def test_variacion_anual_que_es_caso_trae_su_frase_llana():
    corte = {"regla": "corte_temporal", "serie": "Ciencia_y_técnica", "valor_previo": 13.88, "periodo_previo": 2014,
             "valor_actual": 84.76, "periodo": 2015, "ratio_vs_movimiento_tipico": 139.1, "hoja": "Formosa"}
    resumen = {"id": 1, "lente": "cronista", "severidad": "media", "descripcion": "contexto",
               "evidencia": {"naturaleza": "contexto", "regla": "contexto_compartido_periodo", "periodo": 2015,
                             "detalle_contexto": [{"id": 2, "lente": "cronista", "severidad": "alta",
                                                   "descripcion": "[Formosa · cuadro 63] La serie...", "evidencia": corte}]}}
    r = agrupar([resumen])
    anuales = [c["primary_finding"] for c in r["casos"]] + [x for g in r["contexto"] for x in g.get("referencias", [])]
    frases = [h.get("resumen_llano") for h in anuales if (h.get("evidencia") or {}).get("regla") == "corte_temporal"]
    assert frases and all(f and f.startswith("«Ciencia y técnica» pasa de 13,88") for f in frases)
