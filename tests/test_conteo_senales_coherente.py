"""Las cifras de señales de la página 1 y del anexo («Controles ejecutados») son coherentes.

Caso real: informe 306 (libro de gasto), página 1 «76 señales de control» y anexo 6 + 59 + 16 = 81. No
faltaban señales: el anexo cuenta 16 resúmenes de contexto temporal y la página 1 cuenta las
11 variaciones anuales que integran un caso. El informe explicita ambas definiciones.
"""
from services.reporte_ejecutivo import agrupar, nota_conteo_senales


def _h(i, regla, lente="ajedrecista", **ev):
    return {"id": i, "lente": lente, "modo": "control_tabular", "severidad": "media", "descripcion": regla,
            "evidencia": {"regla": regla, "hoja": "H", "celda": f"B{i}", "naturaleza": "control", **ev}}


def _hallazgos():
    control = [_h(1, "total_columna_no_cierra", diferencia=5), _h(2, "valor_fuera_de_escala_columna")]
    contexto = [_h(10 + k, "contexto_compartido_periodo", lente="cronista", naturaleza="contexto",
                   detalle_contexto=[{"hoja": "H", "celda": f"C{k}{j}", "periodo": 2000 + j, "regla": "variacion_anual"}
                                     for j in range(3)]) for k in range(2)]
    return control + contexto


def test_cifras_de_portada_y_anexo_cuadran():
    hs = _hallazgos()
    r = agrupar(hs)
    # Anexo: cada hallazgo cuenta uno (señales directas + resúmenes de contexto).
    assert r["senales_control_directas"] + r["resumenes_contexto"] == len(hs)
    # Página 1: señales directas + variaciones anuales que integran un caso.
    assert r["senales_control"] == r["senales_control_directas"] + r["variaciones_en_casos"]


def test_el_informe_explica_las_dos_definiciones():
    r = agrupar(_hallazgos())
    nota = nota_conteo_senales(r)
    assert f"{r['senales_control']} señales de control" in nota
    assert f"{r['resumenes_contexto']} resúmenes de contexto" in nota
    assert nota_conteo_senales(agrupar(_hallazgos()[:2])) == ""
