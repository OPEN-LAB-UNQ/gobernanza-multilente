"""Casos de la undécima medición (15/10/2026)."""

from services import carga_archivos, cobertura_cifras
from services.perfilado import numero_con_formato
from services.sanitizacion import COLUMNA_SENSIBLE_RE


def test_circuito_no_es_un_cuit():
    assert not COLUMNA_SENSIBLE_RE.search("Circuito")
    assert not COLUMNA_SENSIBLE_RE.search("Visitas por circuito")
    for rotulo in ("CUIT", "cuit_proveedor", "Nro. CUIL", "DNI del agente", "dni", "CUITs"):
        assert COLUMNA_SENSIBLE_RE.search(rotulo), rotulo


def test_formula_de_texto_y_unidad_pegada():
    assert numero_con_formato('="159078"', "es") == 159078
    assert numero_con_formato("147.348 ha", "es") == 147348
    assert numero_con_formato("12,5 km", "es") == 12.5
    assert numero_con_formato("Ruta 5 km", "es") is None
    assert cobertura_cifras.valores('="159078"') >= {159078.0}
    assert cobertura_cifras.valores("147.348 ha") >= {147348.0}


def test_csv_con_cifras_como_formula_de_texto():
    contenido = ('Provincia;2023;2024\r\nBuenos Aires;="159078";="162231"\r\nCórdoba;="69620";="64857"\r\n'
                 'Total;="228698";="227088"\r\n').encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "o.csv")
    assert [f["2023"] for f in datos] == [159078, 69620, 228698]
    assert any("fórmula de texto" in a for a in info["avisos"])


def test_csv_con_la_unidad_pegada():
    contenido = ("Provincia;2023;2024\r\nBuenos Aires;147.348 ha;152.422 ha\r\nCórdoba;109.044 ha;116.387 ha\r\n"
                 "Total;256.392 ha;268.809 ha\r\n").encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "p.csv")
    assert [f["2024"] for f in datos] == [152422, 116387, 268809]
    assert any("«ha»" in a for a in info["avisos"])


def _w(texto, x0, x1, top, size=9.0):
    return {"text": texto, "x0": x0, "x1": x1, "top": top, "size": size}


def test_llamada_de_nota_en_superindice_no_se_pega_a_la_cifra():
    palabras = [_w("9.857", 100, 125, 110), _w("1", 125.3, 127.5, 108, 5.5), _w("10.361", 160, 190, 110),
                _w("Total", 10, 40, 130)]
    limpias = carga_archivos._sin_superindices_pdf(palabras)
    assert [w["text"] for w in limpias] == ["9.857", "10.361", "Total"]


def test_renglon_de_prosa_con_cifras_no_es_fila_del_cuadro():
    prosa = [_w(t, 10 + 40 * k, 45 + 40 * k, 50) for k, t in enumerate(
        "Durante 2025 las distribuidoras informaron 23.037 cortes de suministro de más de tres minutos 3,1 % más".split())]
    fila = [_w("Distribuidora", 10, 70, 80), _w("Norte", 72, 100, 80)] + [
        _w(v, 150 + 50 * k, 180 + 50 * k, 80) for k, v in enumerate(["7.557", "7.529", "7.826", "7.513"])]
    assert carga_archivos._es_prosa_pdf(prosa) and not carga_archivos._es_prosa_pdf(fila)
