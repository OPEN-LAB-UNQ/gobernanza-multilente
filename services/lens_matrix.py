"""Matriz canónica de preguntas y límites de las siete lentes.

La interfaz, los anexos y las respuestas de API deben leer esta misma matriz
para que el método comunicado coincida con el comportamiento esperado.
"""
from __future__ import annotations

from typing import Any

LENS_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "id": "ajedrecista",
        "nombre": "Ajedrecista",
        "rol": "Coherencia lógica y estructural",
        "pregunta_central": "¿La estructura interna del informe es posible y coherente?",
        "preguntas": [
            "¿Los totales coinciden con sus componentes?",
            "¿Las relaciones de orden y las restricciones declaradas se cumplen?",
            "¿Hay valores incompatibles con la naturaleza del dato?",
            "¿Las series acumuladas respetan la lógica de una acumulación?",
            "¿La tensión puede explicarse por una excepción o regla documentada?",
        ],
        "evidencia_minima": ["valores comparados", "regla o restricción aplicable", "ubicación reproducible"],
        "criterios": {
            "conforme": "Las relaciones estructurales aplicables se cumplen o tienen una excepción documentada.",
            "observado": "Existe una relación imposible o tensionada que necesita explicación o corrección.",
            "no_evaluable": "No hay datos, componentes o regla suficiente para comprobar la relación.",
        },
        "limites": ["No evalúa la pertinencia estadística del método.", "No certifica verdad externa."],
        "salida_vacia": "No encontró imposibilidades lógicas ni relaciones estructurales prioritarias para revisar.",
    },
    {
        "id": "matematico",
        "nombre": "Matemático",
        "rol": "Cálculo y pertinencia metodológica",
        "pregunta_central": "¿El cálculo y el método cuantitativo son adecuados para responder la pregunta del informe?",
        "preguntas": [
            "¿La fórmula reproduce el resultado informado?",
            "¿El denominador, universo y período base son los correctos?",
            "¿Corresponde promedio simple o ponderado?",
            "¿Pesos, unidades, escalas, porcentajes y redondeos están bien aplicados?",
            "¿Las variaciones y tendencias internas están correctamente calculadas?",
            "¿La técnica estadística es válida para la cantidad y el tipo de datos?",
            "¿Benford es aplicable y se comunica sólo como señal exploratoria?",
        ],
        "evidencia_minima": ["fórmula o plan de cálculo", "datos de entrada", "resultado reproducido", "supuestos metodológicos"],
        "criterios": {
            "conforme": "El cálculo es reproducible y el método corresponde al universo, unidades y finalidad declarados.",
            "observado": "El resultado no se reproduce o el método, denominador, ponderación o técnica requiere justificación.",
            "no_evaluable": "Faltan fórmula, datos de entrada, denominador o información metodológica.",
        },
        "limites": ["No interpreta por sí solo la causa temporal.", "Una señal estadística no demuestra irregularidad ni causalidad."],
        "salida_vacia": "No detectó cálculos irreproducibles ni métodos cuantitativos que requieran revisión.",
    },
    {
        "id": "cronista",
        "nombre": "Cronista",
        "rol": "Historia y comparabilidad temporal",
        "pregunta_central": "¿Qué cambió a lo largo del tiempo, desde cuándo y con qué explicación documentada?",
        "preguntas": [
            "¿Los períodos son realmente comparables?",
            "¿En qué período aparece el quiebre o cambio de régimen?",
            "¿Cambió la definición, metodología, cobertura o forma de carga?",
            "¿Puede influir estacionalidad, efecto de base, acumulación o carga tardía?",
            "¿Existe un evento extraordinario documentado que explique el cambio?",
        ],
        "evidencia_minima": ["serie ordenada", "período bisagra", "criterios de comparabilidad", "documentación del cambio"],
        "criterios": {
            "conforme": "La serie es comparable y los cambios relevantes tienen contexto temporal suficiente.",
            "observado": "Existe un quiebre relevante sin explicación documentada o con comparabilidad dudosa.",
            "no_evaluable": "No hay suficientes períodos o no puede construirse una serie comparable.",
        },
        "limites": ["No predice el futuro.", "No atribuye causas sin documentación."],
        "salida_vacia": "No detectó quiebres temporales comunicables con la información disponible.",
    },
    {
        "id": "orquesta",
        "nombre": "Orquesta",
        "rol": "Coherencia interdocumental y sistémica",
        "pregunta_central": "¿Los documentos y magnitudes que describen el mismo objeto son coherentes entre sí?",
        "preguntas": [
            "¿Los archivos corresponden a la misma entidad, período, moneda, escala y criterio?",
            "¿Los saldos compartidos coinciden entre documentos?",
            "¿El efectivo final concilia entre flujo de caja y estado patrimonial?",
            "¿El resultado del ejercicio se refleja de manera compatible en el patrimonio?",
            "¿Las magnitudes operativas, físicas y financieras evolucionan de forma explicable?",
            "¿Una diferencia responde a rezago, cobertura o criterio documentado?",
        ],
        "evidencia_minima": ["archivos de origen", "conceptos homologados", "período y unidad", "valores cruzados"],
        "criterios": {
            "conforme": "Las relaciones interdocumentales aplicables concilian o tienen diferencias documentadas.",
            "observado": "Dos documentos o magnitudes relacionadas presentan una diferencia sin conciliación suficiente.",
            "no_evaluable": "Faltan archivos relacionados, conceptos homologables o metadatos de comparabilidad.",
        },
        "limites": ["No sustituye una auditoría contable.", "No presume causalidad entre magnitudes relacionadas."],
        "salida_vacia": "No detectó rupturas interdocumentales o sistémicas con evidencia suficiente.",
    },
    {
        "id": "radiologo",
        "nombre": "Radiólogo",
        "rol": "Comparación con preinformes y antecedentes",
        "pregunta_central": "¿En qué se parece o se diferencia este informe de antecedentes realmente comparables?",
        "preguntas": [
            "¿Qué preinformes son comparables por entidad, dominio, período, escala y método?",
            "¿El valor actual está dentro del rango histórico comparable?",
            "¿El desvío es aislado o generalizado?",
            "¿La diferencia apareció antes en condiciones semejantes?",
            "¿Existe una explicación documentada para el alejamiento?",
        ],
        "evidencia_minima": ["preinformes identificados", "criterios de comparabilidad", "rango histórico", "distancia observada"],
        "criterios": {
            "conforme": "El caso se mantiene dentro del rango comparable o el desvío tiene explicación documentada.",
            "observado": "El caso se aparta materialmente de antecedentes comparables sin explicación suficiente.",
            "no_evaluable": "No existe un banco suficiente de preinformes comparables.",
        },
        "limites": ["No usa el historial interno del mismo archivo como sustituto de preinformes.", "Un caso atípico no demuestra error."],
        "salida_vacia": "No encontró diferencias históricas señalables o falta un banco comparable suficiente.",
    },
    {
        "id": "rizoma",
        "nombre": "Rizoma",
        "rol": "Conexiones no previstas",
        "pregunta_central": "¿Aparece una conexión inesperada que merezca formular una nueva pregunta?",
        "preguntas": [
            "¿Qué variables, áreas o categorías se mueven juntas sin relación predefinida?",
            "¿La asociación se mantiene en distintos períodos o grupos?",
            "¿Puede explicarse por escala, agregación, denominador común o relación derivada?",
            "¿Existe un mecanismo institucional plausible?",
            "¿Qué nueva evidencia permitiría confirmar o descartar la hipótesis?",
        ],
        "evidencia_minima": ["variables vinculadas", "fuerza y estabilidad de la asociación", "filtros de relaciones obvias"],
        "criterios": {
            "conforme": "No aparece una asociación inesperada suficientemente estable para comunicar.",
            "observado": "Existe una conexión no prevista que justifica una hipótesis y evidencia adicional.",
            "no_evaluable": "No hay volumen, variación o diversidad suficiente para explorar asociaciones.",
        },
        "limites": ["Correlación no implica causalidad.", "Toda salida conserva incertidumbre alta hasta validación externa."],
        "salida_vacia": "No detectó asociaciones exploratorias con evidencia suficiente para comunicar.",
    },
    {
        "id": "conciliador",
        "nombre": "Conciliador",
        "rol": "Contexto transversal y reducción de falsos positivos",
        "pregunta_central": "¿Existe una explicación documentada que permita cerrar o modular la señal?",
        "preguntas": [
            "¿La señal puede explicarse por carga, acumulación o reclasificación?",
            "¿Hay cambio de unidad, cobertura parcial o corte de período?",
            "¿Existe una excepción autorizada o criterio de publicación documentado?",
            "¿Qué fuente o responsable puede confirmar la explicación?",
            "¿Corresponde cerrar, seguir, pedir información o escalar?",
        ],
        "evidencia_minima": ["señal de origen", "explicación propuesta", "fuente o responsable", "decisión humana"],
        "criterios": {
            "conforme": "La explicación está documentada y permite cerrar o modular la señal.",
            "observado": "La explicación es parcial o la señal continúa abierta.",
            "no_evaluable": "Falta contexto o no se identificó una fuente responsable para validarlo.",
        },
        "limites": ["No elimina señales sin evidencia.", "No reemplaza la decisión del responsable institucional."],
        "salida_vacia": "No encontró contexto técnico suficiente para modular las señales existentes.",
    },
)

LENS_BY_ID = {item["id"]: item for item in LENS_MATRIX}

B1_CONTROL_LENSES: dict[str, tuple[str, ...]] = {
    "B1-04": ("ajedrecista",),
    "B1-05": ("cronista",),
    "B1-06": ("matematico",),
    "B1-07": ("orquesta", "radiologo", "rizoma"),
    "B1-08": ("conciliador",),
}


def lens_profiles_for_control(control_code: str, declared_lens: str | None = None) -> list[dict[str, Any]]:
    ids = B1_CONTROL_LENSES.get(control_code, (declared_lens,) if declared_lens else ())
    return [LENS_BY_ID[lens_id] for lens_id in ids if lens_id in LENS_BY_ID]
