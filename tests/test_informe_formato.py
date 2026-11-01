"""Formato numérico es-AR centralizado; los identificadores nunca se reescriben."""
from types import SimpleNamespace

from services.reportes.formato import normalizar_numeros, numero
from services.reportes.markdown import _pulir_redaccion, render_reporte_markdown


def test_un_solo_formato_numerico_en_el_texto():
    texto = ("Gasto por objeto!F5 · Bienes de uso · 2023: 2.11356e+10 → 1.9662e+11; sube de 21,135,555,929 a "
             "196,619,506,542 y el total es 192.828.843.503,00 (4.76% de la mayor; 6.01 veces).")
    salida = normalizar_numeros(texto, {"valor_observado": 196619506542, "previo": 21135555929})
    assert "e+" not in salida and "21,135" not in salida
    assert "21.135.555.929" in salida and "196.619.506.542" in salida and "192.828.843.503,00" in salida
    assert "4,76%" in salida and "6,01 veces" in salida
    assert salida.startswith("Gasto por objeto!F5 · Bienes de uso · 2023:")
    # Sin el valor exacto: se escribe con los dígitos disponibles, sin inventar precisión.
    assert normalizar_numeros("1.9662e+11") == "≈196.620.000.000"
    assert numero(1234567.891) == "1.234.567,89" and numero(10) == "10"


def test_identificadores_intactos():
    texto = ("E06_formulas_sin_cache.xlsx · Cuadro 1 (2024)!D6 · motor multilente-0.8.74 · v0.8.74 · "
             "hash 86669ceac74a36172438a62549e6 · credito_vigente_2023 · 2026-10-03")
    assert normalizar_numeros(texto) == texto
    pulido = _pulir_redaccion("La formula de E06_formulas_sin_cache.xlsx y la columna formula_total; la explicacion.")
    assert "E06_formulas_sin_cache.xlsx" in pulido and "formula_total" in pulido
    assert pulido.startswith("La fórmula") and "explicación" in pulido


def test_el_informe_descargable_sale_en_es_ar():
    informe = SimpleNamespace(id=9, datos=[], saneamiento={"archivos_origen": ["E06_formulas_sin_cache.xlsx"]},
                              devolucion=SimpleNamespace(cobertura={}), periodo=None, creado_en=None)
    h = dict(id=1, lente="ajedrecista", modo="control_tabular", severidad="alta", pregunta_institucional="?",
             descripcion="Gasto!E10 · Total · 2022: Total declarado 1.92829e+11; reconstruido 1.83647e+11; diferencia 9.18233e+09 (4.76% de la mayor magnitud).",
             evidencia=dict(regla="conciliacion_aritmetica", hoja="Gasto", celda="E10", periodo=2022,
                            archivo_origen="E06_formulas_sin_cache.xlsx", total_declarado=192828843503.0,
                            reconstruido=183646517622.0, diferencia_absoluta=9182325881.0, puntaje_prioridad=55))
    md = render_reporte_markdown(informe, [SimpleNamespace(tipo_evidencia=None, **h)], False, True, pieza="ejecutivo")
    assert "e+" not in md and "192.828.843.503" in md and "4,76%" in md
    assert "E06_formulas_sin_cache.xlsx" in md and "fórmulas_sin_cache" not in md
