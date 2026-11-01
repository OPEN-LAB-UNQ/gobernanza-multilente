"""Casos de la novena medición (15/10/2026)."""

from routers.carga_rapida import _celdas_marcadas_revision
from services import carga_archivos, cobertura_cifras
from services.perfilado import expandir_cientifica, numero_con_formato


def test_notacion_cientifica_es_una_cifra():
    assert expandir_cientifica("4.203222e+06") == "4203222"
    assert expandir_cientifica("1,5E-3") == "0.0015"
    assert expandir_cientifica("Acueducto 3e") is None
    assert numero_con_formato("4.203222e+06", "es") == 4203222
    assert cobertura_cifras.valores("4.203222e+06") >= {4203222.0}


def test_csv_en_notacion_cientifica_se_lee_entero():
    contenido = ("Acueducto,2017,2018,2019\r\n"
                 "Norte,4.203222e+06,4.357002e+06,4.472382e+06\r\n"
                 "Sur,359407,388178,369731\r\n"
                 "Total,4.562629e+06,4.745180e+06,4.842113e+06\r\n").encode("utf-8")
    datos, _ = carga_archivos._leer_csv_con_lectura(contenido, "a.csv")
    assert [f["2017"] for f in datos] == [4203222, 359407, 4562629]
    for f in datos:
        f["archivo_origen"] = "a.csv"
    [r] = cobertura_cifras.por_archivo([("a.csv", contenido)], datos)
    assert r["en_archivo"] == 9 and r["sin_incorporar"] == 0


def _palabra(texto, x0, x1):
    return {"text": texto, "x0": x0, "x1": x1, "top": 100.0}


def test_rotulos_pegados_en_el_pdf_se_separan_por_columna():
    fila = [_palabra("Año", 10, 30), _palabra("Rodilla", 100, 140), _palabra("Miembro", 180, 225),
            _palabra("inferiorMiembro", 228, 320), _palabra("superior", 323, 370), _palabra("Total", 420, 450)]
    rangos = [(10, 40), (100, 150), (180, 270), (285, 380), (420, 460)]
    nombres = carga_archivos._rotulos_de_columna_pdf([fila], rangos)
    assert nombres == ["Año", "Rodilla", "Miembro inferior", "Miembro superior", "Total"]


def test_rotulo_que_abarca_columnas_con_nivel_inferior_no_cambia():
    arriba = [_palabra("Ayuda", 100, 130), _palabra("directa", 133, 170)]
    abajo = [_palabra("Nación", 40, 80), _palabra("Provincias", 110, 160), _palabra("Total", 200, 230)]
    rangos = [(40, 90), (100, 170), (190, 240)]
    nombres = carga_archivos._rotulos_de_columna_pdf([arriba, abajo], rangos)
    assert nombres[1] == "Ayuda directa · Provincias"


def test_rotulo_repetido_renombrado_en_la_revision_se_declara():
    csv = "﻿Concepto;2023;2024;2024 · 2024\r\nNorte;10;11;12\r\nSur;20;21;22\r\n".encode("utf-8")
    marcas = _celdas_marcadas_revision([("x (revisado).csv", csv)])
    assert marcas["celdas_marcadas"] >= 1
    assert any("«2024»" in m for m in marcas["motivos_marcadas"])
