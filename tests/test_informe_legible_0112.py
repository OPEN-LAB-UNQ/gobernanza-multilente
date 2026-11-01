"""0.10.12: el informe se lee sin identificadores internos y la interpretación previa se resume por tipo."""
from services import interpretacion_previa as ip
from services.reportes import lenguaje_llano


def _cuadro(n, hoja, origen="ia_confirmada", tipo="presupuesto"):
    return {"archivo": "libro.xlsx", "hoja": hoja, "bloque": n, "origen": origen, "plan": {"ajedrecista": True, "radiologo": True},
            "confirmada": {"tipo": tipo, "institucion": "organismo_publico", "regimen": "publico", "eje": "serie_columnas",
                           "roles": {"Rubro": "categoria", "2017": "importe"}}}


def test_resumen_agrupa_por_tipo_y_dice_que_no_hay_excepciones():
    registro = {"estado": "confirmada", "cuadros": [_cuadro(n, f"H{n % 3}") for n in range(1, 8)]}
    texto = "\n".join(ip.resumen(registro))
    assert texto.startswith("Interpretación previa confirmada: 7 cuadros en 3 hojas.")
    assert "- 7 cuadros: presupuesto · organismo público · régimen público · períodos en columnas." in texto
    assert "Sin excepciones" in texto
    assert "organismo_publico" not in texto and "ia_confirmada" not in texto


def test_resumen_nombra_los_cuadros_corregidos_o_sin_clasificar():
    registro = {"estado": "confirmada", "cuadros": [_cuadro(1, "A"), _cuadro(2, "B", "correccion_humana", "estadistica"),
                                                    _cuadro(3, "C", "sin_clasificar", "desconocido")]}
    texto = "\n".join(ip.resumen(registro))
    assert "- 1 cuadro: estadística · organismo público" in texto
    assert "B · cuadro 2 (corregida por una persona)" in texto and "C · cuadro 3 (sin clasificar)" in texto
    assert "Sin excepciones" not in texto


def test_detalle_por_cuadro_sin_identificadores_internos():
    texto = "\n".join(ip.lineas({"estado": "confirmada", "cuadros": [_cuadro(1, "A")]}))
    for crudo in ("ia_confirmada", "organismo_publico", "régimen publico", "radiologo", "matematico", "serie columnas"):
        assert crudo not in texto, crudo
    assert "institución: organismo público" in texto and "períodos en columnas" in texto


def test_salto_de_escala_final_tiene_su_frase_con_los_numeros():
    frase = lenguaje_llano.resumen_llano({"lente": "ajedrecista", "evidencia": {
        "regla": "salto_escala_final", "indicador": "Ayuda directa", "periodo": 2017, "valor_anterior": 759.3017,
        "valor_observado": 0.16043, "valor_posterior": 0.19361, "factor_escala": 4732.88}})
    assert "cae de 759,30 a 0,16 y sigue en 0,19" in frase
    assert "4.733 veces por debajo" in frase


def test_frase_generica_guardada_se_vuelve_a_armar():
    h = {"lente": "ajedrecista", "resumen_llano": lenguaje_llano.GENERICA_POR_LENTE["ajedrecista"],
         "evidencia": {"regla": "salto_escala_final", "indicador": "Ayuda directa", "periodo": 2017,
                       "valor_anterior": 759.3, "valor_observado": 0.16}}
    assert "cae de 759,30 a 0,16" in lenguaje_llano.resumen_de(h)
    h["resumen_llano"] = "Frase propia guardada."
    assert lenguaje_llano.resumen_de(h) == "Frase propia guardada."


def test_salto_anual_se_dice_en_veces():
    frase = lenguaje_llano.resumen_llano({"lente": "cronista", "evidencia": {
        "regla": "corte_temporal", "serie": "Ciencia_y_técnica", "valor_previo": 13.88, "periodo_previo": 2014,
        "valor_actual": 84.76, "periodo": 2015, "ratio_vs_movimiento_tipico": 139.1}})
    assert "se multiplica por 6,1, un salto mucho mayor que los habituales de la serie" in frase
    assert "movimiento habitual" not in frase
