"""Suprimir preguntas no deja restos vacíos ni borra contenido legítimo de la respuesta."""
from routers.proyectos_ia import _limitar_preguntas, _pide_borrador


def test_no_deja_vinetas_vacias_ni_introduccion_huerfana():
    texto = ("Para armar la propuesta necesito tres indicadores. Por ejemplo:\n"
             "- ¿Cuántas discrepancias?\n- ¿Qué tiempo?\n- ¿Qué porcentaje?\n\nAsí integro esa información.")
    assert _limitar_preguntas(texto, 0) == "Para armar la propuesta necesito tres indicadores.\n\nAsí integro esa información."


def test_para_avanzar_sin_pregunta_desaparece():
    assert _limitar_preguntas("El pendiente es el flujo.\n\nPara avanzar:\n¿Quién aprueba cada etapa?", 0) == "El pendiente es el flujo."
    assert _limitar_preguntas("Pendiente: indicadores.\n\nPara avanzar: ¿Qué medirías? Por ejemplo, discrepancias.", 0) == (
        "Pendiente: indicadores.")  # 0.10.63: el ejemplo de una pregunta descartada se va con ella


def test_conserva_la_pregunta_permitida_y_su_introduccion():
    salida = _limitar_preguntas("Pendiente: datos. Por ejemplo:\n- ¿Qué fuente?\n- ¿Quién la carga?", 1)
    assert salida == "Pendiente: datos. Por ejemplo:\n- ¿Qué fuente?"


def test_no_toca_respuestas_sin_preguntas_suprimidas():
    for texto in (
        "Queda así:\n\n1. Problema: demora\n2. Datos: planillas\n  - detalle",
        "Problema:\n\nEl área demora en consolidar.",
        "Indicadores:\n\n| Indicador | Meta |\n|---|---|",
        "Sección 3. Supervisión humana:\n\nRevisa la jefatura.",
        "El costo es 3.5% del total:\n\n- insumos",
    ):
        assert _limitar_preguntas(texto, 0) == texto


def test_titulo_de_seccion_se_conserva_aunque_se_quite_una_pregunta_en_otro_lado():
    texto = "Problema:\n\nEl área demora. ¿Cuántos días?\n\nDatos:\n\nPlanillas."
    assert _limitar_preguntas(texto, 0) == "Problema:\n\nEl área demora.\n\nDatos:\n\nPlanillas."


def test_pedidos_de_borrador():
    for pedido in ("quiero la propuesta completa desarrollada", "Generá un borrador con toda la información que ya aporté.",
                   "generame un borrador", "hacé un borrador", "genera el borrador", "continuá el borrador"):
        assert _pide_borrador(pedido), pedido
    for pedido in ("Siguiente paso.", "no quiero una propuesta completa todavía", "¿qué es la propuesta desarrollada?"):
        assert not _pide_borrador(pedido), pedido
