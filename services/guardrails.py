"""Guardrails institucionales para hallazgos de lectura multilente.

Esta capa no decide si un hallazgo es correcto. Ordena su forma antes de
persistirlo o mostrarlo: evidencia, incertidumbre, alcance, pregunta
institucional y limites de inferencia.
"""
from __future__ import annotations

import re
import warnings
from typing import Any

from enums import Lente, Severidad

ESTADO_CON_SENALES = "CON_SENALES_COMUNICABLES"
ESTADO_SIN_SENALES = "SIN_SENALES_COMUNICABLES"
ESTADO_COBERTURA_PARCIAL = "COBERTURA_PARCIAL"
ESTADO_PREGUNTA_NO_EVALUADA = "PREGUNTA_NO_EVALUADA"

LENTES = tuple(lente.value for lente in Lente)

REEMPLAZOS_INFERENCIA = (
    (r"\bfraudes?\b", "hallazgo a revisar"),
    (r"\birregularidad(?:es)?\b", "conclusion adversa"),
    (r"\bcorrupci[oó]n\b", "problema institucional a revisar"),
    (r"\bcorrupt[oa]s?\b", "a revisar"),
    (r"\bsospechos[oa]s?\b", "atipico"),
    (r"\bculpables?\b", "responsable de explicar"),
    (r"\bdelitos?\b", "hecho formal a revisar"),
    (r"\bilegalidad(?:es)?\b", "punto jurídico a validar por autoridad competente"),
    (r"\bdolo\b", "intencion no inferible desde datos agregados"),
    (r"\bsanci[oó]n(?:es)?\b", "decision institucional externa al sistema"),
    (r"\bviolaci[oó]n(?:es)?\b", "tension con regla a validar"),
)

REEMPLAZOS_POLITICOS = (
    (r"\bpartidos?\b", "actor institucional"),
    (r"\bcoaliciones?\b", "actor institucional"),
    (r"\balineamientos?\s+politic[oa]s?\b", "actor institucional"),
    (r"\bideolog[ií]as?\b", "orientacion no evaluada"),
    (r"\bpartidari[oa]s?\b", "institucional"),
    (r"\boficialismo\b", "actor institucional"),
    (r"\boposici[oó]n\b", "actor institucional"),
)

# Frases de vocabulario legitimo del dominio publico que no deben mutilarse
# por un match de palabra suelta (p.ej. "sancion" dentro de "sancion de la
# ley de presupuesto" es terminologia presupuestaria estandar, no una sancion
# institucional). Se protegen antes de aplicar los reemplazos de arriba y se
# restauran despues, intactas.
EXCEPCIONES_FRASE = (
    "partidos del Gran Buenos Aires",
    "partidos de Buenos Aires",
    "partidos de la provincia de Buenos Aires",
    "sancion de la ley",
    "sancion legislativa",
    "presupuesto sancionado",
    "credito sancionado",
    "monto sancionado",
    "ley de presupuesto sancionada",
    "partida sancionada",
)

TIPO_EVIDENCIA_POR_LENTE = {
    "conciliador": "ARTEFACTO_TECNICO",
    "ajedrecista": "REGLA_FORMAL_O_ARITMETICA",
    "cronista": "CAMBIO_TEMPORAL",
    "orquesta": "COHERENCIA_SISTEMICA",
    "radiologo": "COMPARACION_HISTORICA",
    "rizoma": "ASOCIACION_EXPLORATORIA",
    "matematico": "PERTINENCIA_METODOLOGICA",
}

TIPO_EVIDENCIA_POR_MODO = {
    "formula": "FORMULA_EXCEL",
    "formula_implicita": "PATRON_ARITMETICO_INFERIDO",
    "control_explicito": "CONTROL_EXPLICITO_DEL_ARCHIVO",
    "control_tabular": "REGLA_TABULAR_REPRODUCIBLE",
    "consistencia_aritmetica_pdf": "CONSISTENCIA_ARITMETICA_PDF",
    "pertinencia_calculo": "PERTINENCIA_METODOLOGICA",
    "exploratorio": "ASOCIACION_EXPLORATORIA",
    "conciliacion": "ARTEFACTO_TECNICO",
    "corte_temporal": "CAMBIO_TEMPORAL",
}

METODO_POR_LENTE = {
    "conciliador": "control de artefactos de carga, cobertura, acumulados o reclasificacion",
    "ajedrecista": "reglas estructurales, consistencia aritmética y restricciones formales",
    "cronista": "deteccion de quiebres temporales en series agregadas",
    "orquesta": "coherencia entre magnitudes agregadas relacionadas",
    "radiologo": "comparacion con antecedentes o historial comparable",
    "rizoma": "correlaciones exploratorias filtradas por relaciones obvias",
    "matematico": "revision de formulas, patrones de calculo y pertinencia metodologica",
}


def sanitizar_texto(texto: object) -> str:
    """Aplica lenguaje neutral por palabra, protegiendo antes las frases de
    EXCEPCIONES_FRASE (vocabulario legitimo del dominio) para que no las
    deforme un match de palabra suelta como "sancion" o "violacion"."""
    salida = str(texto or "")
    marcadores: dict[str, str] = {}
    for i, frase in enumerate(EXCEPCIONES_FRASE):
        patron_frase = re.compile(re.escape(frase), re.IGNORECASE)
        if patron_frase.search(salida):
            marcador = f"\x00EXC{i}\x00"
            salida = patron_frase.sub(marcador, salida)
            marcadores[marcador] = frase
    for patron, reemplazo in REEMPLAZOS_INFERENCIA + REEMPLAZOS_POLITICOS:
        salida = re.sub(patron, reemplazo, salida, flags=re.IGNORECASE)
    for marcador, frase in marcadores.items():
        salida = salida.replace(marcador, frase)
    return salida


def _detalle_notas_cobertura(evidencia: dict[str, Any]) -> str | None:
    notas = evidencia.get("notas_cobertura") or []
    if not notas:
        return None
    detalles = [str(item.get("detalle") or item) for item in notas[:2]]
    return "; ".join(detalles) if detalles else None


def _detalle(h: dict[str, Any]) -> str:
    evidencia = h.get("evidencia") or {}
    columnas = evidencia.get("columnas")
    if isinstance(columnas, list):
        columnas_txt = " / ".join(str(c) for c in columnas if c)
    else:
        columnas_txt = None
    # evidencia.regla es un identificador tecnico en snake_case (p.ej.
    # "conciliacion_tecnica_previa"): nunca debe usarse como frase de una
    # pregunta institucional -- si no hay nada mas legible, cae en el
    # generico "la señal indicada" en vez de exponer el slug interno.
    return (
        evidencia.get("fila_detalle")
        or evidencia.get("celda")
        or evidencia.get("serie")
        or columnas_txt
        or evidencia.get("columna_detalle")
        or evidencia.get("columna")
        or _detalle_notas_cobertura(evidencia)
        or "la señal indicada"
    )


def pregunta_institucional(h: dict[str, Any]) -> str:
    lente = str(h.get("lente") or "")
    modo = str(h.get("modo") or "")
    detalle = _detalle(h)
    evidencia = h.get("evidencia") or {}
    if evidencia.get("retrocesos_detalle"):
        cambios = "; ".join(f"{m['periodo_previo']} a {m['periodo']}: {m['valor_previo']} a {m['valor_actual']} (diferencia {m['diferencia']})" for m in evidencia["retrocesos_detalle"])
        return f"¿Qué ajuste, reversa o cambio de criterio explica el retroceso de {evidencia.get('columna')}: {cambios}?"
    if evidencia.get("formula_referencia"):
        return f"¿Corresponde mantener {evidencia.get('formula') or evidencia.get('valor')} en {evidencia.get('hoja')}!{evidencia.get('celda')}, o aplicar {evidencia['formula_referencia']} según el patrón de las celdas vecinas? Documentar el criterio autorizado."
    if modo == "primer_digito_no_conforme":
        return f"Indicar si la distribución atípica del primer dígito en {detalle} responde a cómo se agregaron o cargaron los datos, o si amerita revisar la fuente."
    preguntas = {
        "conciliador": f"Indicar si {detalle} se explica por carga, acumulación, reclasificación, corte de período, cobertura parcial o criterio de publicación.",
        "ajedrecista": f"Revisar y documentar qué regla, fórmula, total o restricción formal explica {detalle}.",
        "cronista": "Explicar qué ocurrió en el período bisagra y si responde a evento extraordinario, arrastre, carga tardía, cambio de criterio, estacionalidad, efecto de base de comparación o criterio metodológico documentado.",
        "orquesta": "Explicar qué relación institucional se esperaba entre las variables y qué contexto justifica la ruptura observada.",
        "radiologo": "Indicar si la semejanza o distancia frente a antecedentes comparables es esperable para el dominio o requiere revisión específica.",
        "rizoma": "Validar si la asociación detectada tiene explicación institucional o debe quedar solo como hipótesis en seguimiento.",
        "matematico": "Justificar si el método de cálculo corresponde al tipo de informe o si requiere ponderadores, denominadores o recálculo.",
    }
    return preguntas.get(lente, f"Explicar con evidencia documentada qué contexto justifica {detalle}.")


def _tipo_evidencia(h: dict[str, Any]) -> str:
    modo = str(h.get("modo") or "")
    lente = str(h.get("lente") or "")
    return h.get("tipo_evidencia") or TIPO_EVIDENCIA_POR_MODO.get(modo) or TIPO_EVIDENCIA_POR_LENTE.get(lente, "SENAL_MULTILENTE")


def _tipo_senal(h: dict[str, Any]) -> str:
    lente = str(h.get("lente") or "")
    modo = str(h.get("modo") or "")
    tipo_evidencia = str(h.get("tipo_evidencia") or "")
    if lente == "cronista" or tipo_evidencia == "CAMBIO_TEMPORAL":
        return "senal_temporal"
    if lente == "rizoma" or tipo_evidencia == "ASOCIACION_EXPLORATORIA":
        return "asociacion_exploratoria"
    if lente == "matematico" or modo in {"formula", "formula_implicita", "pertinencia_calculo"}:
        return "senal_metodologica"
    if lente == "conciliador":
        return "senal_trazabilidad"
    if lente == "ajedrecista":
        return "regla_formal_o_aritmetica"
    if lente == "orquesta":
        return "coherencia_sistemica"
    if lente == "radiologo":
        return "comparacion_historica"
    return "senal_institucional"


def _incertidumbre(h: dict[str, Any]) -> str:
    incertidumbre = h.get("incertidumbre")
    if isinstance(incertidumbre, str) and incertidumbre in {"baja", "media", "alta"}:
        return incertidumbre
    lente = str(h.get("lente") or "")
    modo = str(h.get("modo") or "")
    regla = (h.get("evidencia") or {}).get("regla")
    if lente == "rizoma":
        return "alta"
    if modo in {"formula", "formula_implicita", "consistencia_aritmetica_pdf", "control_explicito"}:
        return "media"
    if regla in {"partes_no_suman_total", "componentes_no_cierran_total", "complemento_porcentual_no_cierra"}:
        return "baja"
    return "media"


def _fundamento_regla(h: dict[str, Any]) -> dict[str, Any] | None:
    tipo = _tipo_evidencia(h)
    if tipo not in {
        "REGLA_FORMAL_O_ARITMETICA",
        "REGLA_TABULAR_REPRODUCIBLE",
        "FORMULA_EXCEL",
        "PATRON_ARITMETICO_INFERIDO",
        "CONTROL_EXPLICITO_DEL_ARCHIVO",
        "CONSISTENCIA_ARITMETICA_PDF",
    }:
        return None
    evidencia = h.get("evidencia") or {}
    regla = evidencia.get("regla") or evidencia.get("formula") or evidencia.get("control") or h.get("modo") or "regla o relacion a validar"
    fuente = evidencia.get("fuente_regla") or evidencia.get("fuente") or evidencia.get("hoja") or evidencia.get("archivo_origen") or "archivo cargado"
    alcance = evidencia.get("alcance_regla") or "mismo universo, corte y definiciones del reporte analizado; requiere validación si no surge expresamente del archivo"
    definiciones = evidencia.get("definiciones") or evidencia.get("columnas") or []
    return {
        "regla": regla,
        "fuente": fuente,
        "alcance": alcance,
        "definiciones": definiciones,
        "estado": "documentada_en_evidencia" if evidencia.get("fuente_regla") or evidencia.get("fuente") else "a_validar_con_area_responsable",
    }


def _limites_base(h: dict[str, Any], informe: Any | None = None) -> dict[str, Any]:
    limites = {
        "no_afirma_causalidad": True,
        "no_atribuye_intencion": True,
        "no_es_auditoria_forense": True,
        "no_es_sumario_administrativo": True,
        "no_sustituye_control_externo": True,
        "no_declara_legalidad": True,
        "no_evalua_politica": True,
        "alcance": "informacion agregada y reportes consolidados",
        "requiere_decision_humana": True,
    }
    fundamento = _fundamento_regla(h)
    if fundamento:
        limites["fundamento_regla"] = fundamento
    if h.get("lente") == "rizoma":
        limites["asociacion_exploratoria"] = "no debe leerse como causa ni como conclusion"
    saneamiento = getattr(informe, "saneamiento", None) or {}
    pdf_meta = saneamiento.get("pdf") if isinstance(saneamiento, dict) else None
    if isinstance(pdf_meta, dict) and pdf_meta:
        limites["pdf"] = {
            "paginas_analizadas": pdf_meta.get("paginas_analizadas"),
            "paginas_documento": pdf_meta.get("paginas_documento"),
            "limite_paginas_pdf": pdf_meta.get("limite_paginas_pdf"),
            "truncado_por_paginas": bool(pdf_meta.get("truncado_por_paginas")),
            "modos_extraccion": pdf_meta.get("modos_extraccion"),
        }
    return limites


def normalizar_hallazgo(hallazgo: dict[str, Any], informe: Any | None = None) -> dict[str, Any]:
    from services import proveniencia, validez
    h = dict(hallazgo)
    evidencia = dict(h.get("evidencia") or {})
    h["descripcion"] = sanitizar_texto(h.get("descripcion"))
    severidad_cruda = h.get("severidad")
    if severidad_cruda not in {s.value for s in Severidad}:
        if severidad_cruda is not None:
            warnings.warn(
                f"severidad desconocida {severidad_cruda!r} en hallazgo de lente "
                f"{h.get('lente')!r} -- se usa 'media' como default. Revisar si es un typo.",
                stacklevel=2,
            )
        severidad_cruda = Severidad.MEDIA.value
    h["severidad"] = severidad_cruda
    h["evidencia"] = evidencia
    h["tipo_evidencia"] = _tipo_evidencia(h)
    tipo_senal = _tipo_senal(h)
    evidencia["tipo_senal"] = tipo_senal
    h["alcance"] = h.get("alcance") or "agregado"
    if h.get("lente") not in {lente.value for lente in Lente}:
        warnings.warn(
            f"lente desconocida {h.get('lente')!r} -- no matchea ningun valor de enums.Lente. "
            "Revisar si es un typo (ej. 'matemático' en vez de 'matematico').",
            stacklevel=2,
        )
    h["metodo"] = h.get("metodo") or METODO_POR_LENTE.get(str(h.get("lente") or ""), "lectura multilente")
    h["incertidumbre"] = _incertidumbre(h)
    h["estado_validacion"] = h.get("estado_validacion") or "pendiente_decision_humana"
    h["pregunta_institucional"] = sanitizar_texto(h.get("pregunta_institucional") or pregunta_institucional(h))
    # «Qué pasó»: una frase llana armada con plantillas (services/reportes/lenguaje_llano), no por IA.
    from services.reportes.lenguaje_llano import resumen_llano
    h["resumen_llano"] = sanitizar_texto(h.get("resumen_llano") or resumen_llano(h))
    limites = _limites_base(h, informe)
    limites["tipo_senal"] = tipo_senal
    limites.update(h.get("limites") or {})
    # Un hallazgo de origen no puede desactivar las fronteras metodológicas.
    for clave, valor in _limites_base(h, informe).items():
        if clave.startswith("no_") or clave == "requiere_decision_humana":
            limites[clave] = valor
    if limites.get("contexto_tecnico"):
        # contexto_tecnico lo arma el conciliador citando nombres de columna
        # del archivo cargado por el usuario (services/lentes/conciliador.py) --
        # no pasaba por sanitizar_texto hasta ahora, a diferencia de descripcion
        # y pregunta_institucional. Mismo tratamiento que el resto del texto
        # institucional que puede llegar a la persona responsable.
        limites["contexto_tecnico"] = sanitizar_texto(limites["contexto_tecnico"])
    h["limites"] = limites
    cambios = []
    for campo in ("descripcion", "pregunta_institucional", "severidad", "incertidumbre", "estado_validacion"):
        if hallazgo.get(campo) != h.get(campo):
            cambios.append({"campo": campo, "accion": "normalizacion_o_reduccion", "original_sha256": proveniencia.huella(hallazgo.get(campo))})
    if (hallazgo.get("limites") or {}).get("contexto_tecnico") != limites.get("contexto_tecnico"):
        cambios.append({"campo": "contexto_tecnico", "accion": "lenguaje_neutral"})
    limites["guardrails"] = {"aplicados": True, "cambios": cambios,
                             "criterio": "Lenguaje sin atribución personal, jurídica, política o causal"}
    evidencia["naturaleza"] = validez.naturaleza(h)
    if informe is not None:
        evidencia["proveniencia"] = proveniencia.evidencia_origen(evidencia, informe)
    return h


def normalizar_hallazgos(hallazgos: list[dict[str, Any]], informe: Any | None = None) -> list[dict[str, Any]]:
    salida = [normalizar_hallazgo(h, informe) for h in hallazgos]
    if informe is not None:
        # Impacto sobre el total del cuadro, tabla derivada e identidades: los ejes de la prioridad.
        from services.reportes.celdas import anotar_todos

        anotar_todos(salida, informe)
    return salida


def _lentes_para_registro(informe: Any, por_lente: dict[str, int]) -> list[dict[str, Any]]:
    condiciones = getattr(informe, "_condiciones_lentes", None) or {}
    out = []
    for lente, cantidad in por_lente.items():
        c = condiciones.get(lente) or {}
        out.append({
            "lente": lente,
            "estado": c.get("estado") or ("con_senales" if cantidad else "sin_senales_comunicables"),
            "motivo": c.get("motivo"),
            "hallazgos": cantidad,
            **({"bloques_totales": c["bloques_totales"], "bloques_evaluados": c.get("bloques_evaluados", 0)}
               if c.get("bloques_totales") else {}),
        })
    return out


def contextualizacion_informe(informe: Any) -> dict[str, Any]:
    saneamiento = getattr(informe, "saneamiento", None) or {}
    opciones = saneamiento.get("opciones_tecnicas", {}) if isinstance(saneamiento, dict) else {}
    modo_uso = saneamiento.get("modo_uso_multilente") if isinstance(saneamiento, dict) else None
    pdf = saneamiento.get("pdf", {}) if isinstance(saneamiento, dict) else {}
    columnas_excluidas = saneamiento.get("columnas_excluidas", []) if isinstance(saneamiento, dict) else []
    return {
        "secuencia_operativa": [
            "carga_y_contextualizacion",
            "senal_analitica",
            "hallazgo_estructurado",
            "pregunta_institucional",
            "revision_y_triangulacion",
            "decision_humana",
            "enrutamiento_o_cierre",
            "registro",
        ],
        "controles": [
            {"nombre": "alcance agregado", "estado": "ok", "detalle": "microdatos y actores identificables quedan fuera del modo estandar"},
            {"nombre": "saneamiento de columnas", "estado": "aplicado" if columnas_excluidas else "sin exclusiones", "detalle": columnas_excluidas[:12]},
            {"nombre": "lectura PDF", "estado": "aplicado" if pdf else "no aplica", "detalle": pdf},
            {"nombre": "formulas Excel", "estado": "activado" if opciones.get("revisar_formulas_excel") else "opcional_no_activado", "detalle": "control tecnico separado de la lente Matematico"},
            {"nombre": "patrones implicitos", "estado": "activado" if opciones.get("inferir_patrones_calculo") else "opcional_no_activado", "detalle": "solo infiere relaciones repetidas; no reemplaza fuente formal"},
 {"nombre": "modo de uso", "estado": modo_uso or "revision_final", "detalle": "define si la lectura acompaña un informe en construcción o revisa una versión cerrada"},
        ],
    }


def cobertura_informe(informe: Any, hallazgos: list[dict[str, Any]]) -> dict[str, Any]:
    por_lente = {lente: 0 for lente in LENTES}
    for h in hallazgos:
        lente = h.get("lente")
        if lente in por_lente:
            por_lente[lente] += 1

    saneamiento = getattr(informe, "saneamiento", None) or {}
    controles_solicitados = (
        saneamiento.get("controles_solicitados", {})
        if isinstance(saneamiento, dict) else {}
    )
    estado_controles = controles_solicitados.get("estado") if isinstance(controles_solicitados, dict) else None
    if not estado_controles and isinstance(controles_solicitados, dict):
        from services.controles_solicitados import estado_controles as resumir_controles
        estado_controles = resumir_controles(controles_solicitados.get("controles", []))
    if estado_controles == "no_evaluable":
        estado_cobertura = ESTADO_PREGUNTA_NO_EVALUADA
    elif estado_controles == "parcialmente_evaluado":
        estado_cobertura = ESTADO_COBERTURA_PARCIAL
    else:
        estado_cobertura = ESTADO_CON_SENALES if hallazgos else ESTADO_SIN_SENALES
    from services.lentes.rizoma import evidencia_control_negativo
    evidencia_rizoma = evidencia_control_negativo(getattr(informe, "datos", None) or [])
    registro = None
    try:
        from services.reportes.registro import construir

        registro = construir(informe, hallazgos, cobertura={
            "lentes": _lentes_para_registro(informe, por_lente),
            "pdf": saneamiento.get("pdf", {}) if isinstance(saneamiento, dict) else {},
            "excel": getattr(informe, "_excel_ejecucion", None) or (saneamiento.get("excel") if isinstance(saneamiento, dict) else None) or {},
            "control_interdocumental": getattr(informe, "_condiciones_interdocumentales", None) or {},
        })
    except Exception:  # noqa: BLE001 — el registro no debe impedir guardar la cobertura
        registro = None
    return {
        "registro_revision": registro,
        "estado": estado_cobertura,
        "filas_analizadas": len(getattr(informe, "datos", None) or []),
        "lentes": [
            {
                "lente": lente,
                "estado": "con_senales" if cantidad else "sin_senales_comunicables",
                "hallazgos": cantidad,
            }
            for lente, cantidad in por_lente.items()
        ],
        "opciones_tecnicas": saneamiento.get("opciones_tecnicas", {}) if isinstance(saneamiento, dict) else {},
        "modo_uso_multilente": saneamiento.get("modo_uso_multilente", "revision_final") if isinstance(saneamiento, dict) else "revision_final",
        "normalizacion_series": saneamiento.get("normalizacion_series", {}) if isinstance(saneamiento, dict) else {},
        "pdf": saneamiento.get("pdf", {}) if isinstance(saneamiento, dict) else {},
        "columnas_excluidas": saneamiento.get("columnas_excluidas", []) if isinstance(saneamiento, dict) else [],
        "controles_negativos": {"rizoma": evidencia_rizoma} if evidencia_rizoma else {},
        "controles_solicitados": controles_solicitados,
        "contextualizacion": contextualizacion_informe(informe),
        "limites_globales": [
            "No garantiza ausencia de problemas: indica que no hubo señales comunicables con los métodos aplicados.",
            "Alcance agregado: no analiza personas ni actores individuales.",
            "No atribuye intención, responsabilidad, causalidad ni valoración política.",
            "No declara legalidad o ilegalidad; remite la interpretación jurídica a quien corresponda.",
            "No sustituye procedimientos formales, de control interno o de auditoría.",
        ],
    }
