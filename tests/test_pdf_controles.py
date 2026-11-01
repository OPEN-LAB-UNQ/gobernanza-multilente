"""Tests de services.pdf_controles."""
from __future__ import annotations

from services import pdf_controles


def test_pdf_controles_composicion():
    datos = [
        {"extraccion_pdf": "tabla", "Indicador": "Pobreza en personas", "Valor alterado": "50.0"},
        {"extraccion_pdf": "tabla", "Indicador": "Indigencia en personas", "Valor alterado": "20.0"},
        {"extraccion_pdf": "tabla", "Indicador": "Pobres no indigentes", "Valor alterado": "25.0"},
        {"extraccion_pdf": "tabla", "Indicador": "No pobres", "Valor alterado": "50.0"},
    ]
    hallazgos = pdf_controles.analizar(datos)
    assert hallazgos
    assert hallazgos[0]["modo"] == "consistencia_aritmetica_pdf"


def test_fila_detalle_usa_posicion_en_tabla_no_indice_global():
    """Regresion: un informe combina varios archivos (ej. 2 PDF + 2 Excel) en
    un solo dataset antes de analizarlo. El "fila N" de un hallazgo de PDF
    no puede ser la posicion de esa fila en ese dataset combinado -- eso no
    se corresponde con ningun renglon contable dentro de la pagina citada y
    confunde a quien intenta ubicar el hallazgo en el documento original.
    Debe usar fila_tabla_pdf (la posicion real dentro de la tabla de esa
    pagina) cuando esta disponible."""
    datos = [
        {"extraccion_pdf": "tabla", "Concepto": "Total 2024", "Valor": "100", "pagina_pdf": 2, "tabla_pdf": 1, "fila_tabla_pdf": 3},
        {"extraccion_pdf": "tabla", "Concepto": "Total 2025", "Valor": "no coincide con el cierre anterior", "pagina_pdf": 4, "tabla_pdf": 1, "fila_tabla_pdf": 2},
    ]
    hallazgos = pdf_controles.analizar(datos)
    textuales = [h for h in hallazgos if h["evidencia"].get("regla") == "control_textual_pdf"]
    assert textuales
    detalle = textuales[0]["evidencia"]["fila_detalle"]
    assert "fila 2" in detalle
    assert "fila 16" not in detalle
    assert "página 4" in detalle


def test_texto_no_muestra_indice_combinado_como_fila():
    fila = {"extraccion_pdf": "texto_por_pagina", "pagina": 4, "pagina_pdf_impresa": 3,
            "texto": "El total no coincide con la suma de sus componentes."}
    hallazgos = pdf_controles.analizar([{"otro_archivo": "sin datos"}] * 59 + [fila])
    detalle = hallazgos[0]["evidencia"]["fila_detalle"]
    assert "fila 60" not in detalle
    assert "página 4 del archivo PDF" in detalle
    assert "numeración impresa: 3" in detalle


def test_definicion_de_diferencia_no_es_inconsistencia():
    datos = [{"extraccion_pdf": "texto_por_pagina", "pagina": 4,
              "texto": "De existir deficit operativo, entendido como la diferencia entre el ingreso operativo y el gasto operativo, se consolida sumado al gasto de capital."}]
    assert pdf_controles.analizar(datos) == []


def test_cita_contiene_disparador_aunque_este_al_final():
    texto = "Introduccion metodologica. " * 100 + "El total no coincide con el valor informado."
    h = pdf_controles.analizar([{"extraccion_pdf": "texto_por_pagina", "pagina": 2, "texto": texto}])[0]
    assert "no coincide" in h["evidencia"]["texto_control"]
    assert len(h["evidencia"]["texto_control"]) < 500


def test_no_se_atribuye_al_pdf_un_control_de_otro_archivo():
    datos = [{"extraccion_pdf": "texto_por_pagina", "pagina": 1, "texto": "Metodologia general"},
             {"archivo_origen": "otro.xlsx", "nota": "No coincide el cierre"}]
    assert pdf_controles.analizar(datos) == []


def test_numero_impreso_no_se_infiere_restandole_uno_a_la_pagina():
    from services.carga_archivos import _pagina_impresa_pdf
    assert _pagina_impresa_pdf("Organismo\n3\nMetodologia de consolidacion", 13) == 3
    assert _pagina_impresa_pdf("Portada sin numero", 13) is None
    assert _pagina_impresa_pdf("2\nTabla\n3", 13) is None


def test_renaf_no_confunde_descripcion_de_inconsistencias_con_error_aritmetico():
    datos = [
        {
            "extraccion_pdf": "texto_por_pagina",
            "pagina": 1,
            "texto": (
                "Herramientas de Inteligencia Artificial para realizar un triaje previo, "
                "detectar inconsistencias y priorizar casos, manteniendo la validacion y "
                "decision final bajo responsabilidad humana."
            ),
        },
        {
            "extraccion_pdf": "texto_por_pagina",
            "pagina": 2,
            "texto": (
                "El triaje permite clasificar casos segun indicadores de consistencia o "
                "posibles inconsistencias para decidir cuales requieren revision tecnica."
            ),
        },
        {
            "extraccion_pdf": "texto_por_pagina",
            "pagina": 4,
            "texto": (
                "Analisis geoespacial y deteccion de inconsistencias. Motor de reglas y "
                "clasificacion de alertas. Revision y validacion del agente tecnico."
            ),
        },
    ]

    assert pdf_controles.analizar(datos) == []


def test_control_textual_conserva_errores_aritmeticos_explicitos():
    datos = [{
        "extraccion_pdf": "texto_por_pagina",
        "pagina": 3,
        "texto": "La revision detecto un error de calculo en el total informado.",
    }]

    hallazgos = pdf_controles.analizar(datos)
    assert len(hallazgos) == 1
    assert hallazgos[0]["evidencia"]["regla"] == "control_textual_pdf"
