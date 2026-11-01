"""Tests de regresion para services/reportes/markdown.py.

Cubren dos bugs reales detectados analizando archivos de prueba en vivo
(no se veian con una lectura superficial del codigo, solo corriendo un
analisis real de punta a punta):

1. _fundamento_regla_markdown pasaba identificadores tecnicos en snake_case
   (regla/fuente/estado, p.ej. "formula_fuera_de_patron") por el mismo
   pulido de tildes que la prosa, y el reemplazo por substring insertaba
   una tilde a mitad del slug ("fórmula_fuera_de_patron").
2. _resumen_hallazgo (la linea de "Devolucion ejecutiva") no revisaba
   evidencia['columna']/['columna_detalle'] antes de caer en el generico
   "la señal indicada", a diferencia de las otras dos funciones equivalentes
   del mismo archivo -- por eso Radiologo salia menos especifico que
   Ajedrecista/Orquesta para el mismo tipo de dato.
"""
from __future__ import annotations

import models
from services.reportes import markdown


def _hallazgo(**kwargs) -> models.Hallazgo:
    base = dict(
        id=1,
        informe_id=1,
        lente="ajedrecista",
        modo="formula",
        descripcion="descripcion de ejemplo",
        severidad="media",
        evidencia={},
        tipo_evidencia="FORMULA_EXCEL",
        incertidumbre="media",
        limites={},
    )
    base.update(kwargs)
    return models.Hallazgo(**base)


def test_fundamento_regla_no_tilda_el_slug_tecnico():
    h = _hallazgo(limites={
        "fundamento_regla": {
            "regla": "formula_fuera_de_patron",
            "fuente": "heuristica_por_encabezados_presupuestarios",
            "alcance": "mismo universo, corte y definiciones del reporte analizado; requiere validacion si no surge expresamente del archivo",
            "estado": "a_validar_con_area_responsable",
        }
    })
    texto = markdown._fundamento_regla_markdown(h)
    assert "regla: formula_fuera_de_patron" in texto
    assert "fuente: heuristica_por_encabezados_presupuestarios" in texto
    assert "fórmula_fuera_de_patron" not in texto
    assert "heurística_por_encabezados_presupuestarios" not in texto
    # el alcance si es prosa real y debe quedar tildado
    assert "validación" in texto


def test_estado_modelo_reporte_no_expone_error_interno():
    interpretacion = models.InterpretacionModelo(
        informe_id=1,
        modelo="renderix",
        contenido={},
        error="timed out connecting to host.internal:9999",
    )
    texto = markdown._estado_modelo_reporte(interpretacion)
    assert texto == "no respondió dentro del tiempo disponible"
    assert "host.internal" not in texto


def test_resumen_hallazgo_usa_columna_singular_antes_de_generico():
    h = _hallazgo(
        lente="radiologo",
        modo="semejanza",
        descripcion="En el período 2026-06, 'devengado' se ubica muy por fuera del rango comparable.",
        evidencia={"columna": "devengado"},
    )
    resumen = markdown._resumen_hallazgo(h)
    assert "devengado" in resumen.split(".")[0]
    assert "la señal indicada" not in resumen



def test_resumen_y_triangulacion_ejecutiva_no_truncan_con_puntos_suspensivos():
    descripcion = (
        "En la hoja 'Notas_estudiantes', G4 usa un promedio simple sobre C4:F4 "
        "en un contexto donde aparecen posibles ponderadores o denominadores "
        "(respuestas, volumen de casos, creditos, horas, pesos o carga horaria). "
        "La formula puede estar bien escrita, pero conviene justificar si corresponde "
        "promedio simple o ponderado."
    )
    h = _hallazgo(
        lente="matematico",
        modo="pertinencia_calculo",
        descripcion=descripcion,
        evidencia={"fila_detalle": "fila 4 (A: EST-013)"},
    )

    resumen = markdown._resumen_hallazgo(h)
    triangulacion = markdown._texto_triangulacion(
        "priorizado solo por claude: " + descripcion
    )

    assert "…" not in resumen
    assert "…" not in triangulacion
    assert "promedio simple o ponderado" in resumen
    assert "promedio simple o ponderado" in triangulacion


def test_criterio_severidad_explica_los_niveles_presentes():
    texto = markdown._criterio_severidad_markdown({"alta": 2, "media": 1, "baja": 0})
    assert "alta =" in texto
    assert "media =" in texto
    assert "baja =" not in texto



def test_conciliador_sin_evidencia_usa_referencia_inferida_en_resumen_y_pregunta():
    h = _hallazgo(
        lente="conciliador",
        modo="conciliacion",
        descripcion=(
            "Antes de escalar la señal, conviene conciliar el criterio de publicación: "
            "retrocesos en 2 serie(s) acumuladas. Puede indicar cambio de cobertura."
        ),
        evidencia={},
        pregunta_institucional=(
            "Indicar si la señal indicada se explica por carga, acumulación, "
            "reclasificación, corte de período, cobertura parcial o criterio de publicación."
        ),
    )

    resumen = markdown._resumen_hallazgo(h)
    pregunta = markdown._pregunta_sugerida(h)

    assert "Conciliador (media): retrocesos en dos series acumuladas" in resumen
    assert "la señal indicada" not in resumen
    assert "retrocesos en dos series acumuladas se explican" in pregunta
    assert "la señal indicada" not in pregunta


def test_reporte_html_declara_utf8_y_renderiza_markdown_basico():
    html = markdown.render_reporte_html("# Título con señales\n\nTexto con **énfasis** y crédito.\n\n- devengado supera crédito_vigente")

    assert '<meta charset="utf-8"' in html
    assert '<h1>Título con señales</h1>' in html
    assert '<strong>énfasis</strong>' in html
    assert '<li>devengado supera crédito_vigente</li>' in html
    assert '# Título' not in html


def test_reporte_pdf_genera_bytes_pdf():
    from io import BytesIO

    from pypdf import PdfReader

    data = markdown.render_reporte_pdf("# Título con señales\n\n- devengado supera crédito_vigente")
    reader = PdfReader(BytesIO(data))
    texto = reader.pages[0].extract_text()

    assert data.startswith(b"%PDF-1.4")
    assert b"/Type /Page" in data
    assert b"startxref" in data
    assert "Título con señales" in texto
    assert "devengado supera crédito_vigente" in texto


def test_reporte_empieza_con_lectura_rapida_en_tres_preguntas():
    area = models.Area(nombre="Área de prueba", codigo="TEST")
    informe = models.Informe(
        area=area,
        periodo="2026-09",
        dominio="general",
        datos=[{"total": 10}],
    )
    hallazgo = _hallazgo(
        descripcion="El total informado cambia de forma brusca respecto del período anterior.",
        pregunta_institucional="Documentar qué hecho explica el cambio del total.",
    )

    texto = markdown.render_reporte_markdown(
        informe,
        [hallazgo],
        incluir_triangulacion=False,
        incluir_devolucion=False,
    )

    assert "## 1. Lectura rápida" in texto
    assert "**Qué llamó la atención:** El total informado cambia" in texto
    assert "**Por qué merece revisión:**" in texto
    assert "**Qué revisar ahora:** Documentar qué hecho explica el cambio" in texto
    assert texto.index("## 1. Lectura rápida") < texto.index("### Resumen técnico")
    assert "## Cómo leer este reporte" in texto
    assert "punto de partida para evaluar, contrastar y mejorar" in texto
    assert "no es un diagnóstico cerrado" in texto


def test_reporte_separa_explicacion_simple_de_detalle_tecnico():
    area = models.Area(nombre="Área de prueba", codigo="TEST")
    informe = models.Informe(
        area=area,
        periodo="2026-09",
        dominio="general",
        datos=[{"total": 10}],
    )
    hallazgo = _hallazgo(
        lente="matematico",
        modo="consistencia_aritmetica_pdf",
        tipo_evidencia="CONSISTENCIA_ARITMETICA_PDF",
        evidencia={"fila_detalle": "página 2"},
        pregunta_institucional="Confirmar cómo se calculó el total informado.",
        limites={
            "fundamento_regla": {
                "regla": "control_textual_pdf",
                "fuente": "informe.pdf",
                "alcance": "requiere validación del área",
                "estado": "a_validar_con_area_responsable",
            }
        },
    )

    texto = markdown.render_reporte_markdown(
        informe,
        [hallazgo],
        incluir_triangulacion=False,
        incluir_devolucion=True,
    )
    lectura, anexo = texto.split("## Anexo técnico de señales", maxsplit=1)

    assert "## 4. Señales que conviene revisar" in lectura
    assert "**Qué se observó:**" in lectura
    assert "**Dónde mirar:** página 2" in lectura
    assert "Matemático revisa cálculos, fórmulas y relaciones numéricas" in lectura
    assert "CONSISTENCIA_ARITMETICA_PDF" not in lectura
    assert "control_textual_pdf" not in lectura
    assert "consistencia aritmética PDF" in anexo
    assert "control_textual_pdf" in anexo
    assert "## 6. Próximos pasos sugeridos" in texto
    assert "no condicionan la emisión automática del comprobante" in texto


def test_reporte_siempre_incluye_comprobante_automatico():
    area = models.Area(nombre="Área de prueba", codigo="TEST")
    informe = models.Informe(
        area=area,
        periodo="2026-09",
        dominio="general",
        datos=[{"total": 10}],
    )

    texto = markdown.render_reporte_markdown(
        informe,
        [],
        incluir_triangulacion=False,
        incluir_devolucion=False,
    )

    assert "## Comprobante de controles automáticos aplicados" in texto
    assert "**Resultado automático:** Controles ejecutados sin observaciones mecánicas" in texto
    assert "**Pregunta para empezar:** ¿Qué alcance tuvo la revisión y qué quedó fuera?" in texto
    assert "**Cómo interpretar este resultado:**" in texto
    assert "Lecturas que produjeron señales: ninguna." in texto
    assert "Primer foco sugerido: -" not in texto
    assert "registrar la cobertura y los controles no evaluables" in texto
    assert "su ejecución reproducible no reemplaza la interpretación ni la decisión humanas" in texto
    assert "no constituye una auditoría" in texto


def test_reporte_no_confunde_evaluacion_b1_historica_con_comprobante_automatico():
    from types import SimpleNamespace

    area = models.Area(nombre="Área de prueba", codigo="TEST")
    informe = SimpleNamespace(
        area=area,
        periodo="2026-09",
        dominio="general",
        datos=[{"total": 10}],
        saneamiento={},
        triangulacion=None,
        devolucion=None,
        interpretaciones=[],
    )
    control = SimpleNamespace(
        codigo="B1-04",
        nombre="Consistencia interna",
        descripcion="Busca contradicciones dentro del objeto.",
        lente="ajedrecista",
        criticidad="alta",
    )
    evidencia = SimpleNamespace(
        descripcion="Se verificaron las reglas declaradas.",
        referencia="hallazgos:4",
    )
    resultado = SimpleNamespace(
        control=control,
        aplica=True,
        estado="conforme",
        observacion=None,
        accion_requerida=None,
        reevaluado_en=None,
        evidencias=[evidencia],
    )
    sello = SimpleNamespace(
        estado="vigente",
        emitido_en=None,
        emitido_por=SimpleNamespace(nombre="Responsable humano"),
        resumen_alcance="Informe revisado bajo protocolo B-1.",
        identificador_publico="sello-publico",
        limitaciones=["No incluye contraste jurídico."],
    )
    informe.evaluaciones_certificacion = [
        SimpleNamespace(
            id=3,
            protocolo=SimpleNamespace(codigo="B-1", version="1.0", nombre="Gobernanza Multilente B-1"),
            estado="sellada",
            creado_en=None,
            reevaluado_en=None,
            hash_objeto="abc123",
            resultados=[resultado],
            sello=sello,
        )
    ]

    texto = markdown.render_reporte_markdown(
        informe,
        [],
        incluir_triangulacion=False,
        incluir_devolucion=False,
    )

    assert "## Comprobante de controles automáticos aplicados" in texto
    assert "su ejecución reproducible no reemplaza la interpretación ni la decisión humanas" in texto
    assert "B1-04 · Consistencia interna" not in texto
    assert "Responsable humano" not in texto


def test_comparacion_de_modelos_elimina_repeticiones_exactas():
    repetido = "La señal necesita contexto antes de decidir."
    assert markdown._textos_unicos([repetido, repetido, "Otra lectura."]) == [
        repetido,
        "Otra lectura.",
    ]


def test_reporte_explica_como_se_uso_la_orientacion_sin_cerrar_el_barrido():
    area = models.Area(nombre="Área de prueba", codigo="TEST")
    informe = models.Informe(
        area=area,
        periodo="2026-09",
        dominio="general",
        datos=[{"total": 10}],
        saneamiento={"orientacion_analisis": "Quiero comparar los cambios entre regiones."},
    )

    texto = markdown.render_reporte_markdown(
        informe,
        [],
        incluir_triangulacion=False,
        incluir_devolucion=False,
    )

    assert "Orientación declarada: Quiero comparar los cambios entre regiones." in texto
    assert "no limita el barrido abierto" in texto
