"""Casos de la décima medición (15/10/2026)."""

import json

from routers.carga_rapida import _cifras_revision
from services import carga_archivos, ocr_local
from services.controles_excel import series


def test_lineas_de_comentario_no_son_registros():
    contenido = ("# Estaciones meteorológicas por red\r\n# Unidad: estaciones\r\n"
                 "Red,2017,2018,2019\r\nSMN,242,246,231\r\nINTA,167,178,172\r\n"
                 "# Nota: desde 2018 la red INTA incorpora convenios\r\n"
                 "Universidades,124,131,141\r\nTotal,533,555,544\r\n").encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "e.csv")
    assert [f["Red"] for f in datos] == ["SMN", "INTA", "Universidades", "Total"]
    assert info["lineas_comentario"] == [1, 2, 6]
    assert any("líneas de comentario" in a for a in info["avisos"])


def test_csv_cortado_a_mitad_de_linea_se_declara():
    contenido = "Región;2021;2022;2023\nCentro;2609;2557;2556\nCuyo;2974;2986;2938\nNOA;3889;3".encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "v.csv")
    assert [f["Región"] for f in datos] == ["Centro", "Cuyo"]
    [p] = info["pendientes_lectura"]
    assert p["tipo"] == "no_leido" and p["donde"] == "fila 4" and "cortado" in p["motivo"]


def test_csv_completo_sin_salto_final_no_es_cortado():
    contenido = "Región;2021;2022\nCentro;2609;2557\nCuyo;2974;2986".encode("utf-8")
    datos, info = carga_archivos._leer_csv_con_lectura(contenido, "v.csv")
    assert len(datos) == 2 and not info.get("pendientes_lectura")


def _tabla(encabezado, filas, titulo=""):
    return {"titulo": titulo, "notas": [], "encabezado": encabezado, "filas": filas, "formato_numerico": "es",
            "cifras_pagina": {"filas": [], "todas": [], "palabras": []}}


def test_cuadro_que_sigue_en_la_pagina_siguiente_se_une():
    a = _tabla(["Provincia", "2024", "2025"], [["Buenos Aires", "87", "92"], ["Chaco", "346", "381"]], "Cuadro 3. Salas")
    b = _tabla(["Río Negro", "123", "131"], [["Salta", "312", "328"], ["Total", "868", "932"]])
    pages = [{"pagina": 1, "metodo": "texto_pdf", "tablas": [a]}, {"pagina": 2, "metodo": "texto_pdf", "tablas": [b]}]
    ocr_local._unir_continuaciones(pages)
    assert [f[0] for f in pages[0]["tablas"][0]["filas"]] == ["Buenos Aires", "Chaco", "Río Negro", "Salta", "Total"]
    assert pages[1]["tablas"] == [] and "continúa" in pages[1]["aviso_cifras"]


def test_encabezado_de_otra_pagina_no_se_une():
    a = _tabla(["Provincia", "2024", "2025"], [["Chaco", "346", "381"]])
    b = _tabla(["Región", "2024", "2025"], [["Norte", "12", "13"]])
    pages = [{"pagina": 1, "metodo": "texto_pdf", "tablas": [a]}, {"pagina": 2, "metodo": "texto_pdf", "tablas": [b]}]
    ocr_local._unir_continuaciones(pages)
    assert len(pages[1]["tablas"]) == 1


def _w(texto, x0, x1, top=100.0):
    return {"text": texto, "x0": x0, "x1": x1, "top": top}


def test_rotulos_de_dos_lineas_en_columnas_vecinas():
    arriba = [_w("Año", 10, 30), _w("Mendoza", 100, 150), _w("San", 180, 200), _w("Juan", 203, 230),
              _w("Santiago", 233, 290), _w("Catamarca", 330, 390)]
    abajo = [_w("del", 240, 258, 112), _w("Estero", 261, 300, 112)]
    rangos = [(10, 40), (100, 160), (180, 225), (238, 305), (330, 395)]
    nombres = carga_archivos._rotulos_de_columna_pdf([arriba, abajo], rangos)
    assert nombres == ["Año", "Mendoza", "San Juan", "Santiago del Estero", "Catamarca"]


class _Pagina:
    def __init__(self, palabras):
        self.palabras = palabras

    def extract_words(self, **_):
        return self.palabras


def test_rotulo_de_fila_en_dos_lineas_no_se_pierde():
    palabras = [_w("Tipo", 10, 40, 80), _w("2023", 300, 330, 80), _w("2024", 380, 410, 80), _w("2025", 460, 490, 80)]
    filas = [("Hospitales generales de agudos de", "28.460", "29.102", "28.303", 100),
             ("Centros de atención primaria", "12.183", "12.549", "12.013", 130),
             ("Unidades de pronta atención", "7.722", "8.303", "8.487", 150),
             ("Total", "48.365", "49.954", "48.803", 170)]
    for rotulo, *cifras, top in filas:
        x = 10
        for palabra in rotulo.split():
            palabras.append(_w(palabra, x, x + 8 * len(palabra), top))
            x += 8 * len(palabra) + 2
        for cifra, x0 in zip(cifras, (300, 380, 460)):
            palabras.append(_w(cifra, x0, x0 + 30, top))
    palabras += [_w("la", 10, 26, 112), _w("ciudad", 28, 76, 112)]
    grilla = carga_archivos._grilla_por_coordenadas_pdf(_Pagina(palabras))
    assert grilla[1][0] == "Hospitales generales de agudos de la ciudad"
    assert grilla[2][0] == "Centros de atención primaria"


def test_diez_veces_en_el_primer_periodo_no_requiere_conciliacion():
    periodos = list(range(2017, 2026))
    s = {"archivo": "a.xlsx", "hoja": "H", "cuadro": 1, "etiqueta": "Santiago del Estero", "nivel": 0, "periodos": periodos,
         "valores": [10530, 1092, 1109, 1053, 1141, 1208, 1198, 1201, 1190], "celdas": [f"{c}8" for c in "BCDEFGHIJ"],
         "periodos_validos": periodos, "unidad": None}
    [h] = [h for h in series.analizar(s) if h["evidencia"]["regla"] == "escala_extremo"]
    assert h["evidencia"]["celda"] == "B8" and not h["evidencia"]["requiere_conciliacion"]


def test_tabla_confirmada_contra_el_texto_del_pdf():
    cifras = {"filas": ["123", "127", "312", "311", "330", "331"], "todas": ["123", "127", "312", "311", "330", "331"],
              "palabras": ["provincia", "río", "negro", "salta", "san", "juan", "rodados", "maquinaria"]}
    csv = "﻿Río Negro;2024;2025\r\nSalta;312;311\r\nSan Juan;330;331\r\nRodado Msaquinaria;1;2\r\n".encode("utf-8")
    comp = _cifras_revision(json.dumps(cifras), [("x (revisado).csv", csv)])["cifras"]
    assert comp["faltan"] == 2 and comp["ejemplos_faltan"] == ["123", "127"]  # la fila tomada como encabezado
    assert comp["rotulos_distintos"] == ["Rodado Msaquinaria"]


def test_rotulo_que_desborda_sobre_una_columna_con_rotulo_propio_no_se_parte():
    arriba = [_w("Producción", 10, 90), _w("total", 93, 130), _w("de", 133, 150), _w("energía", 153, 210),
              _w("Exportaciones", 230, 320)]
    rangos = [(10, 120), (160, 320)]  # «de energía» desborda sobre la columna de «Exportaciones»
    nombres = carga_archivos._rotulos_de_columna_pdf([arriba], rangos)
    assert nombres == ["Producción total de energía", "Exportaciones"]


def test_rotulo_pegado_que_solo_roza_la_columna_vecina():
    arriba = [_w("Mendoza", 100, 150), _w("San", 180, 200), _w("Juan", 203, 230), _w("Santiago", 233, 290)]
    abajo = [_w("del", 262, 280, 112), _w("Estero", 283, 322, 112)]
    rangos = [(100, 160), (180, 235), (255, 330)]
    nombres = carga_archivos._rotulos_de_columna_pdf([arriba, abajo], rangos)
    assert nombres == ["Mendoza", "San Juan", "Santiago del Estero"]


def test_rotulos_pegados_en_una_sola_palabra_alineados_a_la_derecha():
    # Así llegan en el PDF: «San» «JuanSantiago» «del» «Estero», alineados a la derecha de sus columnas.
    arriba = [_w("Mendoza", 456, 490), _w("San", 524, 539), _w("JuanSantiago", 541, 589), _w("del", 591, 603),
              _w("Estero", 605, 630), _w("Catamarca", 659, 700)]
    rangos = [(465, 490), (535, 560), (605, 630), (680, 700)]
    nombres = carga_archivos._rotulos_de_columna_pdf([arriba], rangos)
    assert nombres == ["Mendoza", "San Juan", "Santiago del Estero", "Catamarca"]
