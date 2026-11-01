"""Renderizado del reporte ejecutivo en markdown de un informe analizado.

Toda esta logica vivia antes en routers/informes.py: el router solo debe
recibir, validar, llamar al servicio y devolver -- el detalle de como se
arma el markdown (evidencia, contexto de cobertura/PDF/series, triangulacion,
convergencia) queda acá.
"""
from __future__ import annotations

import datetime
import html
import io
import os
import re
from collections.abc import Sequence

import models
from services import certificaciones as certificaciones_svc
from services import guardrails, lectura_temporal, perfilado, plural
from services.lentes import rizoma as rizoma_svc
from services.reportes import lenguaje_llano

ALCANCE_REVISION = (
    "La presencia o ausencia de señales no demuestra que el informe sea verdadero ni que esté libre de errores. "
    "El resultado se limita a los datos disponibles, los controles ejecutados y las condiciones de esta revisión. "
    "Lo no evaluado no equivale a un control superado."
)

def _pulir_redaccion(texto: object) -> str:
    """Pulido liviano de frases generadas para el reporte descargable."""
    salida = str(texto or "")
    reemplazos = {
        "credito_vigente": "crédito vigente",
        "ejecutado_acumulado": "ejecutado acumulado",
        "pagado_acumulado": "pagado acumulado",
        "retrocesos en 2 serie(s) acumuladas": "retrocesos en dos series acumuladas",
        "1 paso(s)": "un período",
        " que regla": " qué regla",
        "formula": "fórmula",
        "restriccion": "restricción",
        "explicacion": "explicación",
        "deberia": "debería",
        "ampliacion": "ampliación",
        "compensacion": "compensación",
        "imputacion": "imputación",
        "automatico": "automático",
        "validacion": "validación",
        "juridico": "jurídico",
        "aritmetica": "aritmética",
        "heuristica": "heurística",
        "priorizacion": "priorización",
        "senales": "señales",
        "metodos": "métodos",
        "intencion": "intención",
        "valoracion": "valoración",
        "interpretacion": "interpretación",
        "politica": "política",
        "juridica": "jurídica",
        "organos": "órganos",
    }
    from services.reportes.formato import proteger

    def pulir(segmento: str) -> str:
        for viejo, nuevo in reemplazos.items():
            segmento = segmento.replace(viejo, nuevo)
        return segmento

    # Los slugs de columna conocidos se traducen; un archivo, una celda o un identificador, nunca.
    for slug_conocido in ("credito_vigente", "ejecutado_acumulado", "pagado_acumulado"):
        salida = re.sub(rf"(?<![\w.]){slug_conocido}(?![\w.])", reemplazos[slug_conocido], salida)
    return proteger(salida, pulir)


def _md(texto: object) -> str:
    """Normaliza texto para un reporte Markdown simple y legible."""
    if texto is None:
        return "-"
    return _pulir_redaccion(str(texto).replace("\r\n", "\n").replace("\r", "\n").strip()) or "-"


def _orientacion_informe(informe: models.Informe) -> str:
    saneamiento = informe.saneamiento or {}
    if not isinstance(saneamiento, dict):
        return ""
    opciones = saneamiento.get("opciones_tecnicas")
    opciones = opciones if isinstance(opciones, dict) else {}
    valor = saneamiento.get("orientacion_analisis") or opciones.get("orientacion_analisis")
    return str(valor or "").strip()


def _controles_solicitados_informe(informe: models.Informe) -> list[dict]:
    saneamiento = informe.saneamiento or {}
    if not isinstance(saneamiento, dict):
        return []
    bloque = saneamiento.get("controles_solicitados")
    if not isinstance(bloque, dict):
        return []
    return [item for item in (bloque.get("controles") or []) if isinstance(item, dict)]


def _estado_modelo_reporte(interpretacion: models.InterpretacionModelo, manifiesto=None) -> str:
    registro = next((m for m in (manifiesto or {}).get("modelos", []) if m.get("proveedor") == interpretacion.modelo), {})
    if ((registro.get("estado_tareas") or {}).get("lectura_senales") or {}).get("estado") == "no_solicitada":
        return "sin señales para interpretar; la exploración del libro se informa por separado"
    contenido = interpretacion.contenido if isinstance(interpretacion.contenido, dict) else {}
    if contenido.get("lectura"):
        return "leyó las señales y su lectura fue incorporada"
    error = str(interpretacion.error or "").lower()
    if contenido:
        # Sólo exploró el libro: la lectura de señales no se completó.
        motivo = str(interpretacion.error or "").strip()
        return "no completó la lectura de señales" + (f" ({motivo})" if motivo else "") + "; sólo aportó exploración del libro"
    if "timeout" in error or "timed out" in error:
        return "no respondió dentro del tiempo disponible"
    if "json" in error or "objeto" in error or "formato" in error:
        return "respondió, pero no entregó un formato utilizable"
    if "no configurad" in error:
        return "no estaba disponible en este entorno"
    return "no pudo completar la lectura"


def slug(texto: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", texto.strip().lower()).strip("-")
    return base[:80] or "informe"


NOMBRE_LENTE = {
    "ajedrecista": "Ajedrecista",
    "conciliador": "Conciliador",
    "cronista": "Cronista",
    "orquesta": "Orquesta",
    "radiologo": "Radiólogo",
    "rizoma": "Rizoma",
    "matematico": "Matemático",
}


def _nombre_lente(lente: object) -> str:
    texto = str(lente or "-")
    return NOMBRE_LENTE.get(texto, texto.title())


DESCRIPCION_LENTE = {
    "ajedrecista": "busca combinaciones imposibles o datos fuera de lugar",
    "conciliador": "revisa si una señal puede explicarse por carga, publicación o agregación",
    "cronista": "observa cambios bruscos o quiebres a lo largo del tiempo",
    "orquesta": "compara si las magnitudes del informe son coherentes entre sí",
    "radiologo": "contrasta el caso con antecedentes que resultan comparables",
    "rizoma": "encuentra asociaciones que sirven para abrir preguntas, no para afirmar causas",
    "matematico": "revisa cálculos, fórmulas y relaciones numéricas",
}


def _descripcion_lente(lente: object) -> str:
    texto = str(lente or "-")
    return DESCRIPCION_LENTE.get(texto, "aporta una lectura complementaria del informe")


def _detalle_comprobante_controles_markdown(
    informe: models.Informe,
    job: models.AnalysisJob | None = None,
) -> str:
    """Comprobante automático del procedimiento ejecutado.

    No expresa aprobación humana ni reutiliza el lenguaje del sello B-1. Su
    objeto es demostrar qué controles automáticos corrieron, con qué versión
    y sobre qué huella, distinguiendo resultados mecánicos de señales
    exploratorias.
    """
    _, huella = certificaciones_svc.snapshot_informe(informe)
    fecha = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")
    cobertura = dict(getattr(getattr(informe, "devolucion", None), "cobertura", None) or {})
    controles = list(cobertura.get("lentes") or [])
    hallazgos = list(getattr(informe, "hallazgos", None) or [])
    exploratorios = [
        h for h in hallazgos
        if h.lente == "rizoma" or h.tipo_evidencia == "ASOCIACION_EXPLORATORIA" or h.modo == "exploratorio" or (h.evidencia or {}).get("naturaleza") == "exploratoria"
    ]
    temporales_anuales = [h for h in hallazgos if lectura_temporal.anual(h)]
    mecanicos = [h for h in hallazgos if h not in exploratorios and h not in temporales_anuales]
    version = getattr(job, "version_analisis", None) or "análisis histórico"
    metricas = dict(getattr(job, "metricas", None) or {})
    estado = "CONTROLES EJECUTADOS CON OBSERVACIONES" if mecanicos else "CONTROLES EJECUTADOS SIN OBSERVACIONES MECÁNICAS"
    lectura_excel = ((cobertura.get("excel") or (informe.saneamiento or {}).get("excel") or {}) or {}).get("lectura") or {}
    from services.controles_excel.lectura import porcentaje, resumen_pdf
    lectura_pdf = resumen_pdf((informe.saneamiento or {}).get("pdf") or {})
    if lectura_pdf.get("estado") == "insuficiente" and not lectura_excel:
        estado = "COBERTURA DE LECTURA INSUFICIENTE · EL PDF NO APORTÓ SERIES REVISABLES"
    elif lectura_pdf.get("estado") == "parcial" and not lectura_excel:
        estado += " · LECTURA PARCIAL DEL PDF"
    if lectura_excel.get("estado") == "insuficiente":
        estado = f"COBERTURA DE LECTURA INSUFICIENTE · {porcentaje(lectura_excel)} % DEL ARCHIVO"
    elif lectura_excel.get("estado") == "parcial":
        estado += f" · LECTURA PARCIAL DEL ARCHIVO ({porcentaje(lectura_excel)} %)"
    if (cobertura.get("condiciones_validez") or {}).get("puede_concluir") is False:
        estado = "NO EVALUABLE · SE REQUIERE INFORMACIÓN ADICIONAL"
    if temporales_anuales:
        estado += f" · {len(temporales_anuales)} GRUPOS TEMPORALES PARA CONTEXTUALIZAR"
    if exploratorios:
        etiqueta_exploratoria = "SEÑAL EXPLORATORIA" if len(exploratorios) == 1 else "SEÑALES EXPLORATORIAS"
        estado += f" · {len(exploratorios)} {etiqueta_exploratoria}"

    lineas = [
        "# Comprobante de controles automáticos aplicados",
        "",
        f"**Estado:** {estado}",
        "",
    ]
    from services.controles_excel.lectura import lineas as lineas_lectura
    from services.controles_excel.lectura import lineas_pdf
    texto_lectura = lineas_lectura(lectura_excel) + lineas_pdf(lectura_pdf)
    if texto_lectura:
        lineas.extend(["## Qué se pudo leer", ""])
        lineas.extend(f"- {_pulir_redaccion(x)}" for x in texto_lectura)
        lineas.append("")
    lineas += [
        "## Identificación",
        "",
        f"- **Informe:** #{informe.id}",
        f"- **Área:** {_md(getattr(getattr(informe, 'area', None), 'nombre', None))}",
        f"- **Período:** {_md(informe.periodo)}",
        f"- **Dominio:** {_md(informe.dominio)}",
        f"- **Fecha de generación:** {fecha}",
        f"- **Versión del motor:** {_md(version)}",
        f"- **Huella SHA-256 del objeto revisado:** `{huella}`",
        "",
        "## Controles automáticos aplicados",
        "",
    ]
    if controles:
        for control in controles:
            if control.get("estado") in {"no_evaluable", "no_aplicable"}:
                continue
            lente = str(control.get("lente") or "-")
            cantidad = int(control.get("hallazgos") or 0)
            resultado = "sin observaciones" if cantidad == 0 else "1 observación" if cantidad == 1 else f"{cantidad} observaciones"
            if lente == "cronista" and temporales_anuales:
                resultado = (f"{plural.contar(len(temporales_anuales), 'grupo anual', 'grupos anuales')} para contextualizar; "
                             f"{plural.contar(cantidad - len(temporales_anuales), 'señal temporal', 'señales temporales')} de otra cadencia")
            if control.get("estado") in {"no_evaluable", "no_aplicable"}:
                resultado = control["estado"].replace("_", " ")
                if control.get("motivo"):
                    resultado += f" ({_md(control['motivo'])})"
            lineas.append(f"- **{_nombre_lente(lente)}:** {resultado}.")
    else:
        lineas.append("- El informe fue analizado antes de incorporar el detalle persistente por control.")

    lineas.extend(_lineas_priorizadas(hallazgos))
    lineas.extend(["", "## Resultado mecánico", ""])
    if mecanicos:
        mapa_casos = _casos_por_senal(hallazgos)
        for hallazgo in sorted(mecanicos, key=_clave_politica):
            nivel, _, _ = _prioridad_y_ejes(hallazgo, mapa_casos)
            lineas.append(
                f"- **{_nombre_lente(hallazgo.lente)} · {str(nivel).upper()}:** "
                f"{_md(lenguaje_llano.resumen_de(hallazgo))} {_md(hallazgo.descripcion)}"
            )
            if (hallazgo.evidencia or {}).get('puntaje_prioridad') is not None:
                lineas.extend('  - '+x for x in _evidencia_markdown(hallazgo.evidencia))
    else:
        lineas.append("- No se registraron observaciones mecánicas con los controles ejecutados.")

    if temporales_anuales:
        lineas.extend(lectura_temporal.lineas_markdown(hallazgos))
        lineas.extend(["", "## Detalle de variaciones anuales para contextualizar", ""])
        for hallazgo in sorted(temporales_anuales, key=lectura_temporal.intensidad, reverse=True):
            lineas.append(f"- **Cronista · CONTEXTO ANUAL:** {_md(hallazgo.descripcion)}")
            lineas.extend('  - ' + x for x in _evidencia_markdown(hallazgo.evidencia or {}))
    lineas.extend(["", "## Señales exploratorias separadas", ""])
    if exploratorios:
        for hallazgo in exploratorios:
            lineas.append(f"- {_md(hallazgo.descripcion)}")
        lineas.append("- Estas señales abren preguntas; no modifican por sí solas el resultado mecánico.")
    else:
        lineas.append("- No se registraron señales exploratorias comunicables.")

    lineas.extend(["", "## Trazabilidad técnica", ""])
    lineas.extend([
        f"- **Registros agregados analizados:** {cobertura.get('filas_analizadas', metricas.get('filas', len(informe.datos or [])))}",
        f"- **Miradas ejecutadas:** {metricas.get('lentes_ejecutadas', len(controles) or '-')}",
        f"- **Duración registrada:** {metricas.get('duracion_segundos', '-')} segundos",
        f"- **Modelos exploratorios que respondieron:** {metricas.get('modelos_respondieron', '-')} ",
    ])
    from services.excel_cobertura import resumen_lineas
    excel_lineas = resumen_lineas(cobertura.get("excel") or (informe.saneamiento or {}).get("excel"))
    if excel_lineas:
        lineas.extend(["", "## Cobertura del Excel", ""])
        lineas.extend(f"- {_md(x)}" for x in excel_lineas)
    excluidas = cobertura.get("columnas_excluidas") or []
    if excluidas:
        lineas.append(f"- **Columnas excluidas antes del análisis:** {', '.join(_md(item) for item in excluidas)}")
    limites = cobertura.get("limites_globales") or []
    if limites:
        lineas.extend(["", "## Límites informados", ""])
        lineas.extend(f"- {_pulir_redaccion(item)}" for item in limites)

    manifiesto = cobertura.get("manifiesto") or {}
    if manifiesto:
        condiciones = manifiesto.get("condiciones") or {}
        lineas.extend(["", "## Condiciones y origen", "",
            f"- **Aplicación / protocolo automático:** {_md(manifiesto.get('version_aplicacion'))} / {_md(manifiesto.get('version_protocolo'))}",
            f"- **Fecha de ejecución:** {_md(manifiesto.get('fecha'))}",
            f"- **Código ejecutado (SHA-256):** `{_md(manifiesto.get('version_codigo'))}`",
            f"- **Objeto procesado (SHA-256):** `{_md(manifiesto.get('sha256_procesado'))}`",
        ])
        for fuente in (manifiesto.get("proveniencia") or {}).get("fuentes", []):
            lineas.append(f"- **Origen:** {_md(fuente['nombre_original'])}, versión {fuente['version']}, SHA-256 `{fuente['sha256_bruto']}`.")
        for clave, etiqueta in (("condiciones_no_verificadas", "No verificada"), ("condiciones_fallidas", "Fallida")):
            for condicion in condiciones.get(clave, []):
                lineas.append(f"- **{etiqueta}:** {_md(condicion['condicion'])} — {_md(condicion.get('motivo'))}.")
        lineas.append(f"- **Detalle técnico autenticado:** /api/informes/{informe.id}/manifiesto")
        lineas.append("- Este documento es un comprobante automático. La evaluación institucional B-1 es opcional, exige revisión humana y tiene una constancia propia.")

    lineas.extend([
        "",
        "## Declaración",
        "",
        ALCANCE_REVISION,
        "",
        "> Este comprobante acredita que el archivo identificado fue procesado por los controles automáticos indicados. No certifica la veracidad de la información, no constituye una auditoría ni sustituye la decisión de la persona responsable.",
        "",
        "El comprobante se genera automáticamente al finalizar los controles. Los controles determinísticos pueden reproducirse con las mismas entradas, reglas, versión y condiciones, sin recalcular manualmente cada operación. La interpretación de los resultados y cualquier decisión institucional permanecen bajo responsabilidad humana.",
        "",
    ])
    return "\n".join(lineas)


def _anexo_controles_automaticos(informe: models.Informe) -> list[str]:
    """Resumen breve del procedimiento automático para el reporte principal."""
    cobertura = dict(getattr(getattr(informe, "devolucion", None), "cobertura", None) or {})
    controles = list(cobertura.get("lentes") or [])
    hallazgos = list(getattr(informe, "hallazgos", None) or [])
    exploratorios = [
        h for h in hallazgos
        if h.lente == "rizoma" or h.tipo_evidencia == "ASOCIACION_EXPLORATORIA" or h.modo == "exploratorio" or (h.evidencia or {}).get("naturaleza") == "exploratoria"
    ]
    temporales_anuales = [h for h in hallazgos if lectura_temporal.anual(h)]
    mecanicos = [h for h in hallazgos if h not in exploratorios and h not in temporales_anuales]
    estado = (
        "Controles ejecutados con observaciones mecánicas"
        if mecanicos else "Controles ejecutados sin observaciones mecánicas"
    )
    if (cobertura.get("condiciones_validez") or {}).get("puede_concluir") is False:
        estado = "No evaluable: condiciones indispensables pendientes"
    if temporales_anuales:
        estado += f"; {len(temporales_anuales)} grupos anuales para contextualizar, informadas aparte"
    if exploratorios:
        estado += f"; {len(exploratorios)} señal{'es' if len(exploratorios) != 1 else ''} exploratoria{'s' if len(exploratorios) != 1 else ''} informada{'s' if len(exploratorios) != 1 else ''} aparte"
    lineas = [
        "## Comprobante de controles automáticos aplicados",
        "",
        f"- **Resultado automático:** {estado}.",
        "- **Emisión:** automática al finalizar los controles; su ejecución reproducible no reemplaza la interpretación ni la decisión humanas.",
    ]
    if controles:
        lineas.append("- **Controles aplicados:**")
        for control in controles:
            lente = str(control.get("lente") or "-")
            cantidad = int(control.get("hallazgos") or 0)
            resultado = "sin observaciones" if cantidad == 0 else "1 observación" if cantidad == 1 else f"{cantidad} observaciones"
            if lente == "cronista" and temporales_anuales:
                resultado = (f"{plural.contar(len(temporales_anuales), 'grupo anual', 'grupos anuales')} para contextualizar; "
                             f"{plural.contar(cantidad - len(temporales_anuales), 'señal temporal', 'señales temporales')} de otra cadencia")
            if control.get("estado") in {"no_evaluable", "no_aplicable"}:
                resultado = control["estado"].replace("_", " ")
                if control.get("motivo"):
                    resultado += f" ({_md(control['motivo'])})"
            lineas.append(f"  - {_nombre_lente(lente)}: {resultado}.")
    else:
        lineas.append("- **Detalle por control:** no disponible para este análisis histórico.")
    if exploratorios:
        lineas.append(
            f"- **Señales exploratorias separadas:** {len(exploratorios)}. "
            "Abren preguntas y no modifican por sí solas el resultado mecánico."
        )
    lineas.extend([
        "- **Alcance:** acredita qué controles automáticos se aplicaron y qué resultado registraron.",
        "- **Interpretación:** " + ALCANCE_REVISION,
        "- **Límite:** no certifica la veracidad de los datos, no constituye una auditoría y no sustituye la decisión de quien es responsable.",
        "",
    ])
    return lineas


NOMBRE_MODO = {
    "formula": "fórmula",
    "formula_implicita": "fórmula implícita",
    "conciliacion": "conciliación",
    "pertinencia_calculo": "pertinencia de cálculo",
    "exploratorio": "exploratorio",
    "priorizacion": "priorización",
    "restriccion_formal_a_validar": "restricción formal a validar",
    "consistencia_aritmetica_pdf": "consistencia aritmética PDF",
    "coherencia_interna_pdf": "coherencia interna del PDF",
    "restriccion formal a validar": "restricción formal a validar",
    "primer_digito_no_conforme": "primer dígito no conforme (Benford)",
    "coherencia": "coherencia",
    "coherencia_empleo_agregada": "coherencia de empleo agregada",
    "coherencia_fisico_financiera": "coherencia físico-financiera",
    "coherencia_operativa": "coherencia operativa",
    "control_explicito": "control explícito",
    "corte_temporal": "corte temporal",
    "corte_temporal_conjunto": "corte temporal conjunto",
    "imposibilidad": "imposibilidad",
    "semejanza": "semejanza",
}


def _nombre_modo(modo: object) -> str:
    texto = str(modo or "-")
    return NOMBRE_MODO.get(texto, texto.replace("_", " "))


def _proporcion(valor: object, referencia: object) -> str:
    """Con fila de referencia la comparación es una proporción; sin ella, el valor propio."""
    from services.controles_excel.comun import es_numero, es_porcentaje

    try:
        return es_porcentaje(float(valor)) if referencia else es_numero(float(valor))
    except (TypeError, ValueError):
        return str(valor)


def _decimal_es(valor: object) -> str:
    try:
        return f"{float(valor):.1f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(valor)


def _estado_barrido_legible(estado: object, hay_hallazgos: bool) -> str:
    nombres = {
        "CON_SENALES_COMUNICABLES": "Se encontraron señales para revisar",
        "SIN_SENALES_COMUNICABLES": "No se encontraron señales relevantes",
        "SIN_HALLAZGOS": "No se encontraron señales relevantes",
        "COBERTURA_PARCIAL": "La revisión general tiene cobertura parcial; consultar el resultado de cada control solicitado",
        "PREGUNTA_NO_EVALUADA": "La pregunta declarada no pudo evaluarse con la estructura disponible",
    }
    texto = str(estado or "").strip()
    if texto in nombres:
        return nombres[texto]
    if texto:
        return texto.replace("_", " ").capitalize()
    return "Se encontraron señales para revisar" if hay_hallazgos else "No se encontraron señales relevantes"


def _prioridad_legible(severidad: object) -> str:
    return {
        "alta": "Alta",
        "media": "Media",
        "baja": "Baja",
    }.get(str(severidad or "").lower(), _md(severidad).capitalize())


def _es_contexto_o_nota(h) -> bool:
    from services.casos_revision import es_contexto, es_nota

    return es_nota(h) or es_contexto(h) or lectura_temporal.anual(h)


def _clave_politica(h) -> tuple:
    """Orden por la misma política que el informe ejecutivo (rareza, impacto, evidencia)."""
    from services.casos_revision import ejes, es_nota

    ev = getattr(h, "evidencia", None) if not isinstance(h, dict) else h.get("evidencia")
    ev = ev or {}
    grupo = 2 if es_nota(h) else 1 if _es_contexto_o_nota(h) else 0
    return (grupo, 0 if grupo else -ejes(h)["puntaje"], str(ev.get("hoja", "")), str(ev.get("celda", "")),
            str(getattr(h, "id", "") if not isinstance(h, dict) else h.get("id", "")))


def _portada_politica(hallazgos) -> list:
    return [h for h in sorted(hallazgos, key=_clave_politica) if not _es_contexto_o_nota(h)][:20]


def _casos_por_senal(hallazgos) -> dict:
    """Cada señal con su caso: la prioridad que se muestra es la del caso, igual que en el ejecutivo."""
    from services.casos_revision import agrupar, identidad

    mapa = {}
    for n, c in enumerate(agrupar(hallazgos)["casos"], 1):
        for x in [c["primary_finding"], *c["related_findings"]]:
            mapa.setdefault(identidad(x), (n, c, x is c["primary_finding"]))
    return mapa


def _prioridad_y_ejes(h, mapa) -> tuple[str, str, str]:
    from services.casos_revision import ejes, identidad, prioridad, texto_ejes

    caso = mapa.get(identidad(h))
    if caso:
        n, c, principal = caso
        if principal:
            return c["prioridad"], texto_ejes(c["ejes"]), f"caso {n}"
        return c["prioridad"], texto_ejes(ejes(h)) + f" Agrupada con el caso {n} por causa común.", f"caso {n}"
    return prioridad(h), texto_ejes(ejes(h)), ""


def _lineas_priorizadas(hallazgos) -> list[str]:
    seleccion = _portada_politica(hallazgos)
    if not any(((getattr(h, "evidencia", None) if not isinstance(h, dict) else h.get("evidencia")) or {}).get("puntaje_prioridad") is not None for h in seleccion):
        return []
    mapa = _casos_por_senal(hallazgos)
    lineas = [
        "## Hallazgos de control priorizados",
        "",
        "Hasta 20 resultados, con la misma política de prioridad que el informe ejecutivo: rareza, impacto sobre el total "
        "del cuadro y evidencia. La severidad original de cada control queda en el anexo y no es la prioridad.",
        "",
    ]
    for i, h in enumerate(seleccion, 1):
        nivel, texto, caso = _prioridad_y_ejes(h, mapa)
        descripcion = h.get("descripcion", "") if isinstance(h, dict) else h.descripcion
        lineas.append(f"{i}. **{str(nivel).upper()}{' · ' + caso if caso else ''}:** {descripcion}")
        lineas.append(f"   - {texto}")
    return lineas + ["", "El resto de los controles y el contexto temporal se conservan en el detalle.", ""]


def _ubicacion_excel_legible(valor: object) -> str:
    """Un rango cuyo inicio y fin son la misma celda se muestra una sola vez."""
    return re.sub(r"(!([A-Z]+\d+)):\2\b", r"\1", str(valor))


def _evidencia_markdown(evidencia: dict | None) -> list[str]:
    if not evidencia:
        return []
    partes: list[str] = []
    if evidencia.get('puntaje_prioridad') is not None:
        if 'valor_observado' in evidencia:
            partes.append(f"Valor observado: {evidencia['valor_observado']!r}")
        for clave, etiqueta in [
            ('bloque_excel','Cuadro'), ('indicador','Indicador'), ('regla','Regla'),
            ('puntaje_prioridad','Puntaje de prioridad'), ('valor_anterior','Valor anterior'),
            ('valor_posterior','Valor posterior'), ('razon_anterior','Razón respecto del anterior'),
            ('razon_posterior','Razón respecto del posterior'), ('interpolacion','Interpolación entre vecinos'),
            ('desviacion_interpolacion','Desviación respecto de la interpolación'),
            ('desviacion_robusta_mad','Desviación robusta (MAD)'), ('mediana_serie','Mediana de la serie'),
            ('mad_serie','MAD de la serie'), ('diferencia_logaritmica','Diferencia logarítmica'),
            ('factor_escala','Factor de escala local'), ('total_declarado','Total declarado'),
            ('total_reconstruido','Total reconstruido'), ('diferencia_absoluta','Diferencia absoluta'),
            ('diferencia_porcentual','Diferencia porcentual'), ('tolerancia_absoluta','Tolerancia absoluta'),
            ('tolerancia_relativa','Tolerancia relativa'), ('accion_revision','Acción de revisión')]:
            if evidencia.get(clave) is not None:
                partes.append(f"{etiqueta}: {_md(evidencia[clave])}")
        if evidencia.get('celdas_participantes'):
            partes.append('Celdas participantes: '+ '; '.join(_md(c) for c in evidencia['celdas_participantes']))
        for relacion in evidencia.get('conciliaciones',[]):
            celdas = '; '.join(_md(c) for c in relacion.get('celdas_participantes') or [])
            if relacion.get('regla') == 'identidad_entre_cuadros':
                partes.append(f"Misma serie en otra apertura: {_decimal_es(relacion['valor_otra_apertura'])} en {_md(relacion['celda_otra_apertura'])} ({relacion['periodos_coincidentes']} de {relacion['periodos_comparables']} períodos coinciden)")
            elif relacion.get('regla') == 'cambio_entre_ediciones':
                partes.append(f"Edición anterior ({_md(relacion['archivo_edicion_anterior'])}): el mismo dato valía {_decimal_es(relacion['valor_edicion_anterior'])}; el resto de la serie no cambió")
            elif relacion.get('regla') == 'movimiento_compensado':
                partes.append(f"Movimiento compensado: un rubro sube {relacion['desvio_sube']:,.1f} y otro baja {abs(relacion['desvio_baja']):,.1f} en el mismo período; celdas: {celdas}")
            elif relacion.get('regla') == 'poblacion_implicita':
                vecinos = ', '.join(f"{v:,.0f}" for v in relacion.get('poblacion_vecinos', []))
                partes.append(f"Coherencia con el valor por persona: población implícita {relacion['poblacion_implicita']:,.0f} frente a {vecinos} en los períodos vecinos; celdas: {celdas}")
            elif relacion.get('regla') == 'serie_de_otro_rubro_entre_ediciones':
                partes.append(f"Edición anterior ({_md(relacion['archivo_edicion_anterior'])}): esta serie es la que allí figuraba en «{relacion['serie_de_origen']}»; celdas: {celdas}")
            elif relacion.get('regla') == 'series_intercambiadas_entre_ediciones':
                partes.append(f"Edición anterior ({_md(relacion['archivo_edicion_anterior'])}): esta fila y «{relacion['serie_intercambiada']}» tienen cada una la serie de la otra; celdas: {celdas}")
            elif relacion.get('regla') == 'escala_entre_hojas':
                partes.append(f"Comparación con las demás hojas: el rubro vale {_proporcion(relacion['proporcion_hoja'], relacion['serie_referencia'])} acá y {_proporcion(relacion['proporcion_resto'], relacion['serie_referencia'])} en las otras {relacion['hojas_comparadas']}; celdas: {celdas}")
            elif relacion.get('regla') == 'rubros_intercambiados':
                partes.append(f"Comparación con las demás hojas: «{relacion['serie_intercambiada']}» tiene el valor de este rubro y viceversa ({_proporcion(relacion['proporcion_hoja'], relacion['serie_referencia'])} y {_proporcion(relacion['proporcion_hoja_intercambiada'], relacion['serie_referencia'])} contra {_proporcion(relacion['proporcion_resto'], relacion['serie_referencia'])} y {_proporcion(relacion['proporcion_resto_intercambiada'], relacion['serie_referencia'])}); celdas: {celdas}")
            elif all(isinstance(relacion.get(k), (int, float)) for k in ('total_declarado', 'total_reconstruido', 'diferencia_absoluta')):
                partes.append(f"Conciliación adicional: declarado {relacion['total_declarado']:g}; reconstruido {relacion['total_reconstruido']:g}; diferencia {relacion['diferencia_absoluta']:g}; celdas: {celdas}")
            else:
                # Relación de otra regla sin total declarado: se nombra y se dan sus celdas, sin inventar cifras.
                from services.sondeo import nombre_control
                partes.append(f"Relación adicional ({_md(nombre_control(relacion.get('regla')))}): celdas: {celdas or 'sin celdas identificadas'}")
    if evidencia.get("ubicaciones_excel"):
        partes.append("Ubicación en Excel: " + "; ".join(_ubicacion_excel_legible(x) for x in evidencia["ubicaciones_excel"]))
    for clave, etiqueta in [
        ("formula", "Fórmula observada"), ("valor", "Valor fijo observado"),
        ("formula_referencia", "Fórmula del patrón vecino trasladada a esta celda"),
        ("origen_formula_referencia", "Celda de referencia del patrón"),
        ("resultado_actual_recalculado", "Resultado observado recalculado"),
        ("resultado_patron_recalculado", "Resultado al aplicar el patrón vecino"),
        ("limite_recalculo", "Límite del recálculo"),
        ("formula_ratio", "Cociente analizado"),
        ("ratio_historico_mediano", "Mediana histórica del cociente"),
        ("ratio_actual", "Cociente actual"),
        ("desvio_relativo_pct", "Desvío relativo absoluto del cociente (%)"),
        ("criterio_seleccion", "Criterio de selección"),
        ("movimiento_tipico", "Movimiento típico de referencia"),
        ("metodo_movimiento_tipico", "Método de referencia"),
        ("cambios_referencia", "Cambios absolutos usados como referencia"),
        ("umbral_ratio", "Umbral salto / movimiento típico"),
    ]:
        if evidencia.get(clave) is not None:
            valor = evidencia[clave]
            if clave in ("formula", "formula_referencia") and str(valor).startswith("="):
                # Funciones en castellano para leer; la fórmula tal como figura en el archivo, al lado.
                traducida = lenguaje_llano.traducir_formula(valor)
                valor = traducida if traducida == valor else f"{traducida} (en el archivo: {valor})"
            partes.append(f"{etiqueta}: {valor}")
    for clave, etiqueta in [("valores_previos", "Valores previos"), ("valores_actuales", "Valores actuales"), ("entradas_recalculo", "Valores utilizados en el recálculo")]:
        if evidencia.get(clave):
            partes.append(etiqueta + ": " + "; ".join(f"{k} = {v}" for k, v in evidencia[clave].items()))
    for m in evidencia.get("retrocesos_detalle", []):
        partes.append(f"{m['periodo_previo']} a {m['periodo']}: {m['valor_previo']} → {m['valor_actual']}; diferencia {m['diferencia']}; variación {m['variacion_pct']} %")
    for m in evidencia.get("detalle_series", []):
        partes.append(f"Serie {m.get('serie')}: {m.get('valor_previo')} → {m.get('valor_actual')}; cambio {m.get('delta')}; referencia {m.get('movimiento_tipico')}; método: {m.get('metodo_movimiento_tipico')}; cambios de referencia: {m.get('cambios_referencia')}; umbral: {m.get('umbral_ratio')}")
    cierre = evidencia.get("cierre_serie") or {}
    if cierre:
        partes.append(f"Cierre de la serie ({cierre['periodo']}): avance financiero {cierre['financiero']}; físico {cierre['fisico']}" + (f"; brecha {cierre['brecha_pp']} puntos porcentuales" if cierre.get('brecha_pp') is not None else "") + ". Describe la evolución completa; no es otra alerta independiente.")
    if evidencia.get("hoja"):
        partes.append(f"Hoja: {evidencia['hoja']}")
    if evidencia.get("celda"):
        partes.append(f"Celda: {evidencia['celda']}")
    if evidencia.get("fila_detalle"):
        partes.append(f"Ubicación: {evidencia['fila_detalle']}")
    if evidencia.get("texto_control"):
        partes.append(f"Pasaje a revisar: {evidencia['texto_control']}")
    if evidencia.get("periodo_previo") or evidencia.get("periodo"):
        previo = evidencia.get("periodo_previo") or "-"
        periodo = evidencia.get("periodo") or "-"
        partes.append(f"Período: {previo} -> {periodo}")
    columnas = evidencia.get("columnas")
    if not columnas:
        columnas = [
            evidencia.get("columna"),
            evidencia.get("columna_mayor"),
            evidencia.get("columna_menor"),
            evidencia.get("columna_total"),
            *(evidencia.get("columnas_componentes") or []),
        ]
    columnas = [c for c in columnas if c] if isinstance(columnas, list) else []
    if columnas:
        partes.append(f"Columnas: {' / '.join(_md(c) for c in columnas)}")
    if evidencia.get("serie"):
        partes.append(f"Serie: {evidencia['serie']}")
    if evidencia.get("metodo"):
        partes.append(f"Método: {evidencia['metodo']}")
    if evidencia.get("valor_actual_texto") is not None and evidencia.get("valor_actual_tabla") is not None:
        periodo_actual = " ".join(
            str(v) for v in (evidencia.get("mes"), evidencia.get("anio_actual")) if v is not None
        )
        partes.append(
            f"Contraste{f' ({periodo_actual})' if periodo_actual else ''}: "
            f"texto destacado {_decimal_es(evidencia['valor_actual_texto'])} % / "
            f"tabla {_decimal_es(evidencia['valor_actual_tabla'])} %"
        )
    if evidencia.get("valor_previo_texto") is not None and evidencia.get("valor_previo_tabla") is not None:
        periodo_previo = " ".join(
            str(v) for v in (evidencia.get("mes"), evidencia.get("anio_previo")) if v is not None
        )
        partes.append(
            f"Contraste{f' ({periodo_previo})' if periodo_previo else ''}: "
            f"texto destacado {_decimal_es(evidencia['valor_previo_texto'])} % / "
            f"tabla {_decimal_es(evidencia['valor_previo_tabla'])} %"
        )
    if evidencia.get("coeficiente_pearson") is not None:
        partes.append(f"Coeficiente de Pearson: {evidencia['coeficiente_pearson']}")
    if evidencia.get("n_observaciones") is not None:
        partes.append(f"Observaciones: n = {evidencia['n_observaciones']}")
    if evidencia.get("periodo_desde") or evidencia.get("periodo_hasta"):
        partes.append(f"Período observado: {evidencia.get('periodo_desde') or '-'} a {evidencia.get('periodo_hasta') or '-'}")
    if evidencia.get("datos_faltantes") is not None:
        partes.append(f"Datos faltantes en el par: {evidencia['datos_faltantes']}")
    if evidencia.get("umbral_seleccion_abs") is not None:
        partes.append(f"Umbral de comunicación: |r| ≥ {evidencia['umbral_seleccion_abs']}")
    if evidencia.get("correlacion_primeras_diferencias") is not None:
        partes.append(
            f"Primeras diferencias: r = {evidencia['correlacion_primeras_diferencias']} "
            f"con n = {evidencia.get('n_primeras_diferencias')} variaciones"
        )
    if evidencia.get("limitacion_muestra"):
        partes.append(f"Limitación: {evidencia['limitacion_muestra']}")
    comprobaciones = evidencia.get("comprobaciones_sugeridas") or []
    if comprobaciones:
        partes.append("Comprobaciones sugeridas: " + "; ".join(str(item).strip().rstrip(".") for item in comprobaciones) + ".")
    notas_cobertura = evidencia.get("notas_cobertura") or []
    if notas_cobertura:
        detalles = [str(item.get("detalle") or item) for item in notas_cobertura[:4]]
        partes.append("Notas de cobertura: " + "; ".join(detalles))
    muestra = evidencia.get("muestra") or {}
    if muestra.get("fila_detalle"):
        partes.append(f"Muestra: {muestra['fila_detalle']}")
    filas = evidencia.get("filas_detalle") or []
    if filas:
        partes.append("Filas: " + "; ".join(str(f) for f in filas[:6]))
    muestras_violacion = evidencia.get("muestras_violacion") or []
    for item in muestras_violacion[:6]:
        partes.append(
            f"{item.get('ubicacion', 'Registro')}: {item.get('valor_mayor')} > {item.get('valor_menor')}; "
            f"diferencia {item.get('diferencia_absoluta')} "
            f"({item.get('exceso_sobre_menor_pct')}% sobre el límite comparado)"
        )
    if muestra.get("resueltas") is not None and muestra.get("pendientes") is not None:
        partes.append(
            f"Cierre: {muestra.get('resueltas')} resueltas + {muestra.get('pendientes')} pendientes = "
            f"{muestra.get('calculado')}, frente a {muestra.get('declarado')} consultas; "
            f"diferencia {muestra.get('diferencia_absoluta')} ({muestra.get('diferencia_pct_consultas')}%)"
        )
    return partes


def _detalle_notas_cobertura(evidencia: dict) -> str | None:
    notas = evidencia.get("notas_cobertura") or []
    if not notas:
        return None
    detalles = [str(item.get("detalle") or item) for item in notas[:2]]
    return "; ".join(detalles) if detalles else None


def _fundamento_regla_markdown(h: models.Hallazgo) -> str | None:
    limites = h.limites or {}
    fundamento = limites.get("fundamento_regla") if isinstance(limites, dict) else None
    if isinstance(fundamento, str):
        return _md(fundamento)  # informes históricos del lector y controles solicitados
    if not isinstance(fundamento, dict):
        return None
    # regla/fuente/estado son identificadores tecnicos en snake_case (p.ej.
    # "formula_fuera_de_patron"): no deben pasar por _pulir_redaccion, que
    # inserta tildes de prosa dentro del slug y lo deja mixto e ilegible.
    # alcance si es prosa real y se beneficia del pulido.
    regla = str(fundamento.get("regla") or "-")
    fuente = str(fundamento.get("fuente") or "-")
    alcance = _md(fundamento.get("alcance"))
    estado = str(fundamento.get("estado") or "-")
    return f"regla: {regla}; fuente: {fuente}; alcance: {alcance}; estado: {estado}"


def _contexto_tecnico_markdown(h: models.Hallazgo) -> str | None:
    limites = h.limites or {}
    contexto = limites.get("contexto_tecnico") if isinstance(limites, dict) else None
    if not contexto:
        return None
    return _texto_corto(contexto, 360)

def _normalizacion_series(informe: models.Informe) -> dict:
    saneamiento = informe.saneamiento or {}
    meta = saneamiento.get("normalizacion_series") or {}
    return meta if isinstance(meta, dict) else {}


def _titulo_alcance_series(valor: object) -> str:
    return {
        "auto": "automático",
        "nivel_general": "solo nivel general",
        "principales": "principales aperturas",
        "todas": "todas las aperturas",
    }.get(str(valor or ""), str(valor or "no especificado"))


def _hay_hallazgo_nivel_general(hallazgos: list[models.Hallazgo]) -> bool:
    for h in hallazgos:
        evidencia = h.evidencia or {}
        textos: list[str] = []
        for clave in ("serie", "series", "series_compactas"):
            valor = evidencia.get(clave)
            if isinstance(valor, list):
                textos.extend(str(x) for x in valor if x)
            elif valor:
                textos.append(str(valor))
        for texto in textos:
            norm = texto.lower().replace(" ", "_")
            if "nivel_general" in norm or "total_general" in norm or norm.startswith("ng_"):
                return True
    return False


def _contexto_pdf_markdown(informe: models.Informe) -> list[str]:
    meta = (informe.saneamiento or {}).get("pdf") or {}
    if not isinstance(meta, dict) or not meta.get("cantidad_archivos"):
        return []
    total = meta.get("paginas_documento") or "-"
    analizadas = meta.get("paginas_analizadas") or "-"
    limite = meta.get("limite_paginas_pdf") or "-"
    archivos = meta.get("cantidad_archivos") or "-"
    nombres_modo = {
        "texto_por_pagina": "texto por página",
        "tabla": "tablas detectadas",
    }
    modos = ", ".join(
        nombres_modo.get(str(m), str(m).replace("_", " "))
        for m in (meta.get("modos_extraccion") or [])
        if m
    ) or "no especificado"
    etiqueta_archivos = "archivo" if archivos == 1 else "archivos"
    lineas = [
        f"- Documento PDF: {archivos} {etiqueta_archivos}; se analizaron {analizadas} de {total} páginas; forma de lectura: {modos}; límite máximo: {limite} páginas.",
    ]
    if meta.get("truncado_por_paginas"):
        lineas.append("- Alcance PDF: el documento fue recortado por límite de páginas; el reporte no debe leerse como revisión completa del PDF.")
    return lineas


def _contexto_series_markdown(informe: models.Informe, hallazgos: list[models.Hallazgo]) -> list[str]:
    meta = _normalizacion_series(informe)
    if meta.get("formato") != "largo":
        return []
    periodo = _md(meta.get("columna_periodo") or "período")
    dimension = _md(meta.get("columna_dimension") or "apertura")
    columnas_valor = meta.get("columnas_valor") or []
    valor_txt = " / ".join(str(c) for c in columnas_valor[:4]) if isinstance(columnas_valor, list) else _md(columnas_valor)
    solicitado = _titulo_alcance_series(meta.get("alcance_solicitado"))
    aplicado = _titulo_alcance_series(meta.get("alcance_aplicado") or meta.get("alcance_solicitado"))
    filas = f"{meta.get('filas_analizadas', '-')} de {meta.get('filas_entrada', '-')}"
    aperturas = f"{meta.get('series_analizadas', '-')} de {meta.get('series_detectadas', '-')}"
    cambio = f"; solicitado: {solicitado}" if solicitado != aplicado else ""
    lineas = [
        f"- Formato detectado: tabla larga ({periodo} / {dimension} / {valor_txt or 'valor'}).",
        f"- Alcance de series aplicado: {aplicado}{cambio}; filas analizadas: {filas}; aperturas analizadas: {aperturas}.",
    ]
    if meta.get("alcance_aplicado") != "nivel_general" and not _hay_hallazgo_nivel_general(hallazgos):
        lineas.append("- Lectura de alcance: no se seleccionaron señales comunicables en nivel general; los hallazgos corresponden a aperturas y requieren contexto sectorial.")
    return lineas


def _referencia_hallazgo(h: models.Hallazgo) -> str | None:
    evidencia = h.evidencia or {}
    if evidencia.get("ubicacion_legible"):
        # Tablas de CSV o PDF: fila y columna (o página y cuadro) del archivo de origen.
        return str(evidencia["ubicacion_legible"])
    if evidencia.get("ubicaciones_excel"):
        return "; ".join(_ubicacion_excel_legible(x) for x in evidencia["ubicaciones_excel"])
    if evidencia.get("hoja") and evidencia.get("celda"):
        return f"{evidencia['hoja']}!{evidencia['celda']}"
    if evidencia.get("filas_detalle"):
        return "; ".join(str(f) for f in evidencia["filas_detalle"])
    if evidencia.get("periodo"):
        columnas = evidencia.get("columnas") or [evidencia.get("serie") or evidencia.get("columna") or ""]
        return f"{evidencia.get('periodo_previo') or ''} → {evidencia['periodo']}: " + " / ".join(columnas)
    for clave in ("fila_detalle", "celda", "serie", "columna_detalle", "columna"):
        if evidencia.get(clave):
            return str(evidencia[clave])
    filas_detalle = evidencia.get("filas_detalle") or []
    if isinstance(filas_detalle, list) and filas_detalle:
        return "; ".join(str(item) for item in filas_detalle[:3])
    columnas = evidencia.get("columnas")
    if isinstance(columnas, list):
        cols = [str(c) for c in columnas if c]
        if cols:
            return " / ".join(cols)
    detalle = _detalle_notas_cobertura(evidencia)
    if detalle:
        return detalle

    descripcion = _md(h.descripcion)
    # «serie(s)» quedó en descripciones ya emitidas: se sigue reconociendo, además de la forma nueva.
    match = re.search(r"retrocesos en (?:\d+ series?|\d+ serie\(s\)|dos series) acumuladas", descripcion, re.IGNORECASE)
    if match:
        return match.group(0)
    match = re.search(r"serie acumulada '([^']+)'", descripcion, re.IGNORECASE)
    if match:
        return f"serie acumulada {match.group(1)}"
    return None


def _pregunta_sugerida(h: models.Hallazgo) -> str:
    """Fallback para cuando el hallazgo no trae pregunta_institucional persistida
    (no deberia pasar en la practica: guardrails.pregunta_institucional() la
    calcula y la graba para todo hallazgo nuevo). Reusa esa misma funcion en
    vez de mantener una segunda copia del mapa por lente -- tener dos copias
    fue justamente como se colo antes un slug tecnico sin tildar en un reporte."""
    pregunta = h.pregunta_institucional or guardrails.pregunta_institucional({"lente": h.lente, "modo": h.modo, "evidencia": h.evidencia})
    pregunta = _pulir_redaccion(pregunta)
    referencia = _referencia_hallazgo(h)
    if referencia and "la señal indicada" in pregunta:
        pregunta = pregunta.replace("la señal indicada", referencia)
        if referencia.startswith("retrocesos en "):
            pregunta = pregunta.replace(" se explica", " se explican")
    return pregunta


def _texto_limpio(texto: object) -> str:
    limpio = " ".join(_md(texto).split())
    limpio = re.sub(r"^Hallazgo #\d+\s*:?\s*", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"^Hallazgo #\d+\s+", "", limpio, flags=re.IGNORECASE)
    limpio = limpio.lstrip(": ").strip()
    return _pulir_redaccion(limpio)


def _texto_corto(texto: object, max_chars: int = 420) -> str:
    limpio = _texto_limpio(texto)
    if len(limpio) <= max_chars:
        return limpio
    # El PDF es evidencia descargable: no cortar una explicación a mitad de frase.
    return limpio


def _periodo_observado(datos):
    fechas = []
    anios = []
    for fila in datos or []:
        for clave, valor in fila.items():
            if str(clave).lower() in {"año", "ano", "anio", "year"}:
                n = perfilado.numero(valor)
                if n is None and isinstance(valor, str):
                    from services.controles_excel.periodos import leer as leer_periodo

                    p = leer_periodo(valor)
                    n = p["anio"] if p and p.get("frecuencia") == "anual" and p.get("marca") else None
                if n is not None and 1800 <= n <= 2200 and float(n).is_integer():
                    anios.append(int(n))
            if str(clave).lower() in {"periodo", "período", "fecha", "mes"}:
                fecha = perfilado.fecha(valor)
                if fecha is not None:
                    fechas.append(fecha.strftime("%Y-%m"))
    if fechas:
        return f"{min(fechas)} a {max(fechas)}"
    if anios:
        return f"{min(anios)} a {max(anios)}"
    # Tablas anchas: períodos en encabezados con valores, no en la fecha de carga.
    columnas = {str(k) for fila in datos or [] for k, v in fila.items() if perfilado.numero(v) is not None}
    anuales = sorted(k for k in columnas if re.fullmatch(r"(?:19|20)\d{2}", k))
    # Un año con marca de provisorio o estimado («2025 (p)», «2025*», «2025 est.») también es
    # un período observado: se incluye en el rango y se dice cuál lleva la marca.
    from services.controles_excel.periodos import leer as leer_periodo

    marcados = {}
    for k in columnas:
        p = leer_periodo(k) if not re.fullmatch(r"(?:19|20)\d{2}", k) else None
        if p and p.get("frecuencia") == "anual" and p.get("marca") and 1800 <= p["anio"] <= 2200:
            marcados[str(p["anio"])] = k.strip()
    if len(anuales) + len(marcados) >= 2 and anuales:
        todos = sorted(set(anuales) | set(marcados))
        texto = f"{todos[0]} a {todos[-1]}"
        if marcados:
            texto += " (" + ", ".join(f"«{marcados[a]}»" for a in sorted(marcados)) + " con marca de provisorio o estimado)"
        return texto
    fechas = sorted({f.strftime("%Y-%m") for k in columnas if (f := perfilado.fecha(k)) is not None})
    if len(fechas) >= 2:
        return f"{fechas[0]} a {fechas[-1]}"
    return _periodos_por_contenido(datos, columnas) or "No identificado en los datos; no se infiere de la fecha de carga"


NOMBRES_MES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
               "noviembre", "diciembre")


def _periodos_por_contenido(datos, columnas_numericas):
    """Períodos reconocidos por su forma («2024-Q1», «2025-T1», «2024-12», «1T 2025»), en una
    columna de rótulos o en los encabezados de columnas con valores, sin depender del nombre."""
    from services.controles_excel.periodos import etiqueta, leer_eje

    def rango(valores):
        from services.controles_excel.periodos import leer
        por_frecuencia = {}
        for valor in valores:
            p = leer(valor)
            if p and p.get("anio"):
                por_frecuencia.setdefault(p["frecuencia"], []).append(p)
        if len(por_frecuencia) > 1:
            tramos = []
            for frecuencia, ps in sorted(por_frecuencia.items()):
                ps.sort(key=lambda p: (p["anio"], p["sub"]))
                tramos.append(f"{frecuencia}: {etiqueta(ps[0])} a {etiqueta(ps[-1])}")
            return "; ".join(tramos)
        eje = leer_eje(valores)
        if not eje:
            return None
        leidos = [p for p in eje["periodos"] if p and not p.get("anio_inferido") and p.get("anio")]
        if len(leidos) < 2:
            # Meses sin año («Enero» … «Diciembre»): se dice el tramo y que el rótulo no trae el año.
            sin_anio = sorted((p for p in eje["periodos"] if p and p.get("anio_inferido")), key=lambda p: p["ordinal"])
            if eje["frecuencia"] == "mensual" and len(sin_anio) >= 2:
                ciclos = sin_anio[-1]["anio"] - sin_anio[0]["anio"] + 1
                tramo = f"{NOMBRES_MES[sin_anio[0]['sub'] - 1]} a {NOMBRES_MES[sin_anio[-1]['sub'] - 1]}"
                return tramo + (f", {ciclos} ciclos" if ciclos > 1 else "") + " (sin año en el rótulo)"
            return None
        leidos.sort(key=lambda p: p["ordinal"])
        return f"{etiqueta(leidos[0])} a {etiqueta(leidos[-1])}"

    from services.carga_archivos import META_PDF

    filas = [f for f in datos or [] if isinstance(f, dict)]
    for clave in dict.fromkeys(k for f in filas[:200] for k in f):
        if clave in META_PDF:
            continue
        temporal = perfilado.normalizar_texto(str(clave)) in {"fecha", "periodo", "mes", "ano", "anio", "year"}
        valores = [f.get(clave) for f in filas if isinstance(f.get(clave), str) or
                   (temporal and isinstance(f.get(clave), (int, float)) and not isinstance(f.get(clave), bool))]
        if len(valores) >= 3:
            encontrado = rango(list(dict.fromkeys(valores)))
            if encontrado:
                return encontrado
    return rango([k for k in (filas[0] if filas else {}) if k in columnas_numericas and k not in META_PDF])


def _advertencia_periodo(referencia: object, observado: str) -> str | None:
    """No equipara el período declarado con las fechas efectivamente leídas."""
    if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", str(referencia or "")):
        return None
    rango = re.fullmatch(r"(\d{4}-\d{2}) a (\d{4}-\d{2})", observado)
    anual = re.fullmatch(r"(\d{4}) a (\d{4})", observado)
    fuera = (rango and not rango[1] <= str(referencia) <= rango[2]) or (anual and not anual[1] <= str(referencia)[:4] <= anual[2])
    if fuera:
        return (
            "- Diferencia temporal a aclarar: el período de referencia declarado no está dentro "
            "del rango observado en los datos. Confirmá si corresponde al corte del informe o "
            "corregí la referencia antes de comparar períodos."
        )
    return None


def _grupos_relacionados(hallazgos):
    """Agrupación de presentación; conserva cada control y su evidencia original."""
    grupos = []
    for i, h in enumerate(hallazgos, 1):
        ev = h.evidencia or {}
        columnas = set(ev.get("columnas") or ev.get("series") or [ev.get("serie") or ""])
        if ev.get("hoja") and ev.get("celda"):
            clave = ("celda", ev["hoja"], ev["celda"])
        elif h.modo in {"coherencia", "corte_temporal", "corte_temporal_conjunto"} and ev.get("periodo"):
            fecha = perfilado.fecha(ev.get("periodo_raw") or ev["periodo"])
            clave = ("transicion", fecha.strftime("%Y-%m") if fecha else ev["periodo"], ev.get("dimension"))
        else:
            clave = ("control", i)
        clave = (*clave, ev.get("archivo_origen"), ev.get("hoja"), ev.get("bloque_excel"))
        encontrado = next((g for g in grupos if g[0] == clave and (clave[0] != "transicion" or bool(g[2] & columnas))), None)
        if encontrado:
            encontrado[1].append(i)
            encontrado[2].update(columnas)
        else:
            grupos.append((clave, [i], columnas))
    return [(clave[0], indices) for clave, indices, _ in grupos if len(indices) > 1]


def _texto_triangulacion(texto: object) -> str:
    limpio = _texto_limpio(texto)
    if limpio.startswith("priorizado"):
        limpio = "Priorizado" + limpio[len("priorizado"):]
    return limpio


def _textos_unicos(valores: Sequence[object], limite: int = 4) -> list[str]:
    salida: list[str] = []
    vistos: set[str] = set()
    for valor in valores:
        texto = _texto_triangulacion(valor)
        clave = " ".join(texto.lower().split())
        if not texto or clave in vistos:
            continue
        vistos.add(clave)
        salida.append(texto)
        if len(salida) >= limite:
            break
    return salida


def _criterio_severidad_markdown(por_severidad: dict[str, int]) -> str:
    criterios: list[str] = []
    if por_severidad.get("alta"):
        criterios.append("alta = posible ruptura de trazabilidad, cálculo o control que requiere contexto antes de decidir")
    if por_severidad.get("media"):
        criterios.append("media = señal relevante que necesita justificación metodológica o documental")
    if por_severidad.get("baja"):
        criterios.append("baja = señal exploratoria útil para seguimiento")
    return "; ".join(criterios) if criterios else "sin señales seleccionadas"


def _resumen_hallazgo(h: models.Hallazgo) -> str:
    evidencia = h.evidencia or {}
    ubicacion = (
        evidencia.get("fila_detalle")
        or ("; ".join(str(f) for f in evidencia.get("filas_detalle", [])[:2]) if isinstance(evidencia.get("filas_detalle"), list) and evidencia.get("filas_detalle") else None)
        or evidencia.get("celda")
        or evidencia.get("serie")
        or (" / ".join(str(c) for c in evidencia.get("columnas", []) if c) if isinstance(evidencia.get("columnas"), list) else None)
        or evidencia.get("columna_detalle")
        or evidencia.get("columna")
        or _detalle_notas_cobertura(evidencia)
        or _referencia_hallazgo(h)
        or "la señal indicada"
    )
    return f"{_nombre_lente(h.lente)} ({h.severidad}): {_pulir_redaccion(ubicacion)}. {_texto_limpio(h.descripcion)}"


def _mapa_convergencia(tri: models.Triangulacion | None) -> dict[int, list[dict]]:
    mapa: dict[int, list[dict]] = {}
    if not tri or not tri.convergencia_multilente:
        return mapa
    for grupo in tri.convergencia_multilente:
        for hid in grupo.get("hallazgo_ids", []):
            mapa.setdefault(hid, []).append(grupo)
    return mapa


def _linea_convergencia(h: models.Hallazgo, convergencia_por_hallazgo: dict[int, list[dict]]) -> str | None:
    grupos = convergencia_por_hallazgo.get(h.id)
    if not grupos:
        return None
    partes = []
    for grupo in grupos[:2]:
        otras = [_nombre_lente(x) for x in grupo.get("lentes", []) if x != h.lente]
        etiqueta = "coincidencia esperable" if grupo.get("fuerza") == "debil" else "independiente"
        partes.append(f"{', '.join(otras)} (mismo {grupo.get('locus_tipo')}: {grupo.get('locus_valor')}; {etiqueta})")
    return "Converge con: " + "; ".join(partes)


ESTADOS_CERTIFICACION = {
    # Los estados de evaluación (en_revision..reemplazada) salen de
    # certificaciones_svc.ESTADOS_VISIBLES -- un solo lugar de verdad para el
    # lenguaje visible. "lista_para_emision" nunca se muestra como "aprobado
    # por IA": se muestra como "Apto para instancia humana de decisión".
    **certificaciones_svc.ESTADOS_VISIBLES,
    "conforme": "Conforme",
    "observado": "Observado",
    "no_evaluable": "No evaluable",
    "vigente": "Vigente",
    "reemplazado": "Reemplazado",
    "suspendido": "Suspendido",
    "revocado": "Revocado",
}


def _estado_certificacion(valor: object) -> str:
    texto = str(valor or "-")
    return ESTADOS_CERTIFICACION.get(texto, texto.replace("_", " ").capitalize())


def _fecha_certificacion(valor: object) -> str:
    if isinstance(valor, datetime.datetime):
        return valor.strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(valor, datetime.date):
        return valor.isoformat()
    return _md(valor)


def _anexo_certificacion_b1(informe: models.Informe) -> list[str]:
    """Genera el anexo B-1 obligatorio sin confundir análisis con certificación."""
    lineas = [
        "## Anexo obligatorio de Gobernanza Multilente B-1",
        "",
        "Este anexo deja constancia del estado del protocolo de control aplicado al informe. "
        "Acompaña la exportación aun cuando la evaluación no haya comenzado o todavía no exista un sello.",
        "",
    ]
    evaluaciones = list(getattr(informe, "evaluaciones_certificacion", None) or [])
    evaluaciones = [
        evaluacion
        for evaluacion in evaluaciones
        if getattr(getattr(evaluacion, "protocolo", None), "codigo", None) == "B-1"
    ]
    if not evaluaciones:
        lineas.extend([
            "- **Protocolo:** Gobernanza Multilente B-1.",
            "- **Estado:** No iniciado.",
            "- **Sello:** No emitido.",
            "- **Lectura correcta:** este reporte contiene resultados del análisis multilente, pero no acredita que el informe haya superado el protocolo B-1.",
            "",
            "### Controles y evidencia",
            "",
            "Todavía no existe una evaluación B-1 asociada al informe. Es una revisión institucional opcional: no condiciona este reporte ni el comprobante automático, y no exige repetir manualmente los cálculos. Si se inicia, requiere evidencia, revisión y decisión humanas propias.",
            "",
        ])
        return lineas

    evaluacion = max(evaluaciones, key=lambda item: int(getattr(item, "id", 0) or 0))
    protocolo = evaluacion.protocolo
    resultados = list(getattr(evaluacion, "resultados", None) or [])
    aplicables = [resultado for resultado in resultados if getattr(resultado, "aplica", True)]
    conformes = [resultado for resultado in aplicables if getattr(resultado, "estado", None) == "conforme"]
    observados = [resultado for resultado in aplicables if getattr(resultado, "estado", None) == "observado"]
    no_evaluables = [resultado for resultado in aplicables if getattr(resultado, "estado", None) == "no_evaluable"]
    no_aplicables = [resultado for resultado in resultados if not getattr(resultado, "aplica", True)]
    sello = getattr(evaluacion, "sello", None)

    lineas.extend([
        f"- **Protocolo y versión:** {_md(protocolo.codigo)} v{_md(protocolo.version)} — {_md(protocolo.nombre)}.",
        f"- **Estado de la evaluación:** {_estado_certificacion(getattr(evaluacion, 'estado', None))}.",
        f"- **Evaluación iniciada:** {_fecha_certificacion(getattr(evaluacion, 'creado_en', None))}.",
        f"- **Última reevaluación:** {_fecha_certificacion(getattr(evaluacion, 'reevaluado_en', None))}.",
        f"- **Huella del objeto evaluado (SHA-256):** `{_md(getattr(evaluacion, 'hash_objeto', None))}`.",
        f"- **Resumen de controles:** {len(conformes)} conformes; {len(observados)} observados; "
        f"{len(no_evaluables)} no evaluables; {len(no_aplicables)} no aplicables; {len(resultados)} totales.",
        "",
        "### Controles y evidencia",
        "",
    ])

    for resultado in resultados:
        control = resultado.control
        aplica = bool(getattr(resultado, "aplica", True))
        estado = "No aplicable" if not aplica else _estado_certificacion(getattr(resultado, "estado", None))
        perfiles_lente = certificaciones_svc.perfiles_control_versionados(
            protocolo, control.codigo, getattr(control, "lente", None)
        )
        lente = ", ".join(perfil["nombre"] for perfil in perfiles_lente) or "Transversal"
        lineas.extend([
            f"### {_md(control.codigo)} · {_md(control.nombre)}",
            "",
            f"- **Qué evalúa:** {_md(control.descripcion)}",
            f"- **Lente:** {lente}.",
            f"- **Criticidad:** {_md(getattr(control, 'criticidad', None)).capitalize()}.",
            f"- **Resultado:** {estado}.",
        ])
        for perfil in perfiles_lente:
            lineas.append(f"- **Pregunta central de {perfil['nombre']}:** {perfil['pregunta_central']}")
            lineas.append(f"- **Preguntas de control de {perfil['nombre']}:**")
            lineas.extend(f"  - {_md(pregunta)}" for pregunta in perfil["preguntas"])
            lineas.append(
                f"- **Evidencia mínima esperada:** {', '.join(_md(item) for item in perfil['evidencia_minima'])}."
            )
        if not aplica:
            lineas.append(
                f"- **Justificación de no aplicabilidad:** {_md(getattr(resultado, 'justificacion_aplicabilidad', None))}"
            )
        if getattr(resultado, "observacion", None):
            lineas.append(f"- **Observación:** {_md(resultado.observacion)}")
        if getattr(resultado, "accion_requerida", None):
            lineas.append(f"- **Acción requerida:** {_md(resultado.accion_requerida)}")
        lineas.append(f"- **Reevaluado:** {_fecha_certificacion(getattr(resultado, 'reevaluado_en', None))}.")
        evidencias = list(getattr(resultado, "evidencias", None) or [])
        if evidencias:
            lineas.append("- **Evidencia registrada:**")
            for evidencia in evidencias:
                referencia = _md(getattr(evidencia, "referencia", None))
                sufijo = "" if referencia == "-" else f" — referencia: {referencia}"
                lineas.append(f"  - {_md(getattr(evidencia, 'descripcion', None))}{sufijo}")
        else:
            lineas.append("- **Evidencia registrada:** Sin evidencia asociada.")
        lineas.append("")

    try:
        hash_actual = certificaciones_svc.snapshot_informe(informe)[1]
    except AttributeError:
        # Fixtures de test livianas (SimpleNamespace) no siempre traen todos
        # los campos de un Informe real; sin ellos no podemos recalcular el
        # hash, así que no afirmamos un cambio que no podemos verificar.
        hash_actual = evaluacion.hash_objeto
    reporte = certificaciones_svc.construir_reporte_evaluacion(evaluacion, hash_actual)

    lineas.extend(["## Anexos autónomos por lente (protocolo B-1)", ""])
    lineas.append(
        "Cada lente tiene su propio anexo, con la misma estructura, tomada siempre de la "
        "matriz canónica de lentes. Un mismo control puede alimentar más de un anexo "
        "La vinculación de controles depende de la versión del protocolo. En B-1 1.2, "
        "Rizoma queda fuera de conformidad y de la evidencia institucional."
    )
    lineas.append("")
    for anexo in reporte["anexos_lentes"]:
        lineas.append(f"### Anexo · {_md(anexo['nombre'])}")
        lineas.append("")
        lineas.append(f"- **Objetivo / pregunta central:** {_md(anexo['pregunta_central'])}")
        lineas.append("- **Preguntas de control:**")
        lineas.extend(f"  - {_md(p)}" for p in anexo["preguntas"])
        lineas.append(f"- **Evidencia mínima esperada:** {', '.join(_md(e) for e in anexo['evidencia_minima'])}.")
        lineas.append(
            "- **Controles ejecutados:** " + (", ".join(_md(c) for c in anexo["controles_ejecutados"]) or "Ninguno.")
        )
        lineas.append(
            "- **Evidencia efectivamente utilizada:** "
            + ("; ".join(_md(e) for e in anexo["evidencia_utilizada"]) or "Sin evidencia registrada.")
        )
        lineas.append(
            "- **Hallazgos de la lente:** " + ("; ".join(_md(h) for h in anexo["hallazgos"]) or "Sin hallazgos.")
        )
        lineas.append(
            "- **Información faltante:** "
            + ("; ".join(_md(f) for f in anexo["informacion_faltante"]) or "Ninguna registrada.")
        )
        if anexo["estado"] == "no_aplicable":
            lineas.append(f"- **Estado:** No aplicable. **Justificación:** {_md(anexo['justificacion_no_aplicable'])}")
        else:
            lineas.append(f"- **Estado:** {_estado_certificacion(anexo['estado'])}.")
        lineas.append(
            "- **Observaciones:** " + ("; ".join(_md(o) for o in anexo["observaciones"]) or "Sin observaciones.")
        )
        lineas.append(
            "- **Acción requerida:** " + ("; ".join(_md(a) for a in anexo["accion_requerida"]) or "Ninguna pendiente.")
        )
        lineas.append(f"- **Reevaluación:** {_fecha_certificacion(anexo['reevaluacion'])}.")
        lineas.append(f"- **Límites propios de esta lente:** {'; '.join(_md(lim) for lim in anexo['limites'])}.")
        lineas.append("")

    if reporte["para_concluir"]:
        lineas.extend(["## Para concluir se requiere:", ""])
        lineas.extend(f"- {_md(item)}" for item in reporte["para_concluir"])
        lineas.append("")

    lineas.extend(["### Política de modelos de IA y manifiesto de ejecución", ""])
    lineas.append(f"- **Huella de la matriz canónica versionada:** `{_md(reporte['matriz_lentes_hash'])}`.")
    politica = reporte["model_policy"]
    if politica.get("aplica"):
        lineas.append(
            f"- **Modelos habilitados por la política de {_md(protocolo.codigo)} v{_md(protocolo.version)}:** "
            + ", ".join(_md(m) for m in politica.get("modelos_habilitados", [])) + "."
        )
        lineas.append(f"- **Mínimo de modelos con respuesta exigido:** {politica.get('modelos_minimos_con_respuesta', 0)}.")
        lineas.append(
            "- **Cumplimiento de la política en esta evaluación:** "
            + ("Cumple." if reporte["model_policy_cumplida"] else "No cumple: la emisión del sello queda bloqueada.")
        )
    else:
        lineas.append(f"- **Política de modelos:** No aplica a este protocolo. {_md(politica.get('motivo'))}")
    manifiesto = reporte["manifiesto_modelos"]
    if manifiesto:
        lineas.append("- **Manifiesto de ejecución:**")
        for item in manifiesto:
            estado_m = "respondió" if item.get("respondio") else "sin respuesta"
            lineas.append(
                f"  - {_md(item.get('modelo'))} ({_md(item.get('proveedor'))}, versión/identificador informado "
                f"`{_md(item.get('identificador_version'))}`) — {estado_m}, {_fecha_certificacion(item.get('fecha'))}, "
                f"controles: {', '.join(_md(c) for c in item.get('controles', [])) or '—'}."
            )
    else:
        lineas.append("- **Manifiesto de ejecución:** No hay modelos de IA registrados para este informe.")
    lineas.append("")

    lineas.extend(["### Alcance del análisis y análisis excluidos", ""])
    lineas.append(
        f"- **Estado de la evaluación (lenguaje para decisión humana):** {_md(reporte['estado_visible'])}."
    )
    if sello:
        lineas.extend([
            f"- **Estado del sello:** {_estado_certificacion(getattr(sello, 'estado', None))}.",
            f"- **Emitido:** {_fecha_certificacion(getattr(sello, 'emitido_en', None))}.",
            f"- **Responsable de emisión:** {_md(getattr(getattr(sello, 'emitido_por', None), 'nombre', None))}.",
            f"- **Alcance del análisis:** {_md(getattr(sello, 'resumen_alcance', None))}",
            f"- **Identificador verificable:** `{_md(getattr(sello, 'identificador_publico', None))}`.",
        ])
        excluidos = list(getattr(sello, "limitaciones", None) or [])
        if excluidos:
            lineas.append("- **Análisis excluidos —lista no exhaustiva—:**")
            lineas.extend(f"  - {_md(item)}" for item in excluidos)
        else:
            lineas.append("- **Análisis excluidos —lista no exhaustiva—:** No se registraron exclusiones adicionales.")
        lineas.extend(["", f"> {certificaciones_svc.DECLARACION_SELLO}", ""])
    else:
        lineas.extend([
            "- **Estado del sello:** No emitido.",
            "- **Lectura correcta:** la evaluación y sus evidencias son trazables, pero este informe todavía no cuenta con una constancia B-1 vigente.",
        ])
    lineas.extend([
        "",
        "La constancia acredita la ejecución y el resultado de un protocolo definido. No certifica verdad absoluta, ausencia total de errores, validez jurídica ni reemplaza la revisión y decisión humanas.",
        "",
    ])
    return lineas


def _lineas_lectura_reporte(informe):
    """Cuánto del archivo pudo leerse: va antes de cualquier señal, no al final."""
    cobertura = dict(getattr(getattr(informe, "devolucion", None), "cobertura", None) or {})
    datos = ((cobertura.get("excel") or (informe.saneamiento or {}).get("excel") or {}) or {}).get("lectura") or {}
    from services.controles_excel.lectura import lineas as lineas_lectura
    from services.controles_excel.lectura import lineas_pdf, resumen_pdf

    partes = lineas_lectura(datos) + lineas_pdf(resumen_pdf((informe.saneamiento or {}).get("pdf") or {}))
    # Cuando no hay series por período no se puede calcular ese porcentaje, pero sí se sabe qué
    # filas y qué hojas entraron. Decir sólo «no calculable» deja al lector sin ninguna medida.
    resumen_excel = list(cobertura.get("excel_resumen") or [])
    if resumen_excel and not datos.get("series_aparentes"):
        partes.append(f"**{resumen_excel[0]}**")
        partes.extend(resumen_excel[1:])
    return [f"- {_pulir_redaccion(x)}" for x in partes]


def _detalle_reporte_markdown(
    informe: models.Informe,
    hallazgos: list[models.Hallazgo],
    incluir_triangulacion: bool,
    incluir_devolucion: bool,
    incluir_detalle_modelos: bool = False,
) -> str:
    area = informe.area
    tri = informe.triangulacion
    hay_apoyo_ia = bool(
        getattr(informe, "interpretaciones", None)
        or (tri and (tri.coincidencias or tri.divergencias or tri.hallazgos_singulares))
    )
    convergencia_por_hallazgo = _mapa_convergencia(tri)
    fecha = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")
    prioridad = {"alta": 0, "media": 1, "baja": 2}

    def _clave_orden(h: models.Hallazgo) -> tuple:
        grupos = convergencia_por_hallazgo.get(h.id, [])
        converge_fuerte = any(g.get("fuerza") == "fuerte" for g in grupos)
        evidencia = h.evidencia or {}
        observado = evidencia.get("resultado_actual_recalculado")
        patron = evidencia.get("resultado_patron_recalculado")
        # A igual severidad, primero la diferencia efectiva; después el cambio
        # metodológico cuyo resultado coincide. Ninguno de los dos es un error
        # confirmado sin validar el criterio con el área responsable.
        contraste = 1 if observado is None or patron is None else (0 if str(observado).casefold() != str(patron).casefold() else 2)
        return (prioridad.get(h.severidad, 9), 0 if h.modo == "coherencia_fisico_financiera" else 1, contraste, 0 if converge_fuerte else 1, h.lente, -lectura_temporal.intensidad(h) if lectura_temporal.anual(h) else 0, h.id)

    if any((h.evidencia or {}).get('puntaje_prioridad') is not None for h in hallazgos):
        hallazgos = sorted(hallazgos, key=lambda h: (_clave_politica(h), _clave_orden(h)))
    else:
        hallazgos = sorted(hallazgos, key=_clave_orden)
    solo_exploratorios = bool(hallazgos) and all(
        h.lente == "rizoma" or h.modo == "exploratorio" or h.tipo_evidencia == "ASOCIACION_EXPLORATORIA"
        for h in hallazgos
    )
    trayectorias: dict[tuple, list[tuple[int, str, str]]] = {}
    for indice, hallazgo in enumerate(hallazgos, 1):
        if hallazgo.lente != "orquesta" or hallazgo.modo != "coherencia_fisico_financiera":
            continue
        evidencia = hallazgo.evidencia or {}
        previo, actual = evidencia.get("periodo_previo"), evidencia.get("periodo")
        columnas = evidencia.get("columnas") or []
        if previo and actual and len(columnas) == 2:
            clave = (evidencia.get("dimension"), evidencia.get("serie"), tuple(columnas))
            trayectorias.setdefault(clave, []).append((indice, str(previo), str(actual)))
    tramos_relacionados = []
    for tramos in trayectorias.values():
        tramos.sort(key=lambda tramo: tramo[1])
        if len(tramos) > 1 and all(uno[2] == dos[1] for uno, dos in zip(tramos, tramos[1:])):
            tramos_relacionados.append([tramo[0] for tramo in tramos])
    por_severidad = {"alta": 0, "media": 0, "baja": 0}
    for h in hallazgos:
        por_severidad[h.severidad] = por_severidad.get(h.severidad, 0) + 1
    from services.casos_revision import agrupar as _agrupar_casos

    _revision = _agrupar_casos(hallazgos)
    por_prioridad = {"alta": 0, "media": 0, "baja": 0, **_revision["prioridades"]}
    principal = hallazgos[0] if hallazgos else None
    controles_solicitados = _controles_solicitados_informe(informe)
    controles_no_evaluados = [
        control for control in controles_solicitados
        if control.get("estado") == "no_evaluable"
    ]
    lentes_activas = sorted({h.lente for h in hallazgos})
    nivel = ("alta" if por_prioridad["alta"] else "media" if por_prioridad["media"] else "baja" if hallazgos else "sin señales")
    tono = {
        "alta": "Hay señales de alta prioridad para revisar antes de decidir.",
        "media": "Hay señales relevantes que conviene contextualizar o documentar.",
        "baja": "Hay señales leves o exploratorias útiles para seguimiento.",
        "sin señales": "No se seleccionaron señales para este reporte.",
    }[nivel]
    if solo_exploratorios:
        tono = "Se encontraron asociaciones exploratorias para contextualizar; no son conclusiones ni prueban causalidad."
    pregunta_inicial = _pregunta_sugerida(principal) if principal else "¿Qué alcance tuvo la revisión y qué quedó fuera?"
    senal_inicial = (
        _texto_corto(principal.descripcion, 480)
        if principal
        else "No aparecieron señales que requieran una revisión prioritaria."
    )
    por_que_importa = {
        "alta": "Puede afectar una decisión o un control importante. Conviene revisarla antes de avanzar.",
        "media": "Merece contexto o documentación adicional antes de aceptarla o descartarla.",
        "baja": "Es una observación exploratoria. Puede dejarse en seguimiento sin tratarla como un problema confirmado.",
        "sin señales": "Los controles ejecutados no seleccionaron señales. Esto no demuestra ausencia de errores; revisá también la cobertura y lo no evaluado.",
    }[nivel]
    siguiente_paso = (
        pregunta_inicial
        if principal
        else "No hay señales seleccionadas que aclarar. Revisá la cobertura y los controles no evaluables antes de usar este reporte como antecedente de la revisión."
    )
    temporal = lectura_temporal.resumen(hallazgos)
    if temporal.get('cantidad', 0) >= 10 and not any((h.evidencia or {}).get('naturaleza') == 'control' for h in hallazgos):
        tono = "La lectura requiere distinguir variaciones anuales y señales de otros controles."
        senal_inicial = (f"{plural.contar(temporal['cantidad'], 'señal temporal anual', 'señales temporales anuales')} y "
                         f"{plural.contar(temporal['otras_senales'], 'señal', 'señales')} de otros controles. No equivalen a ese número de errores.")
        por_que_importa = "Varios movimientos pueden compartir contexto de período, unidad, cobertura o metodología. Una variación nominal no demuestra un cambio real."
        siguiente_paso = "Empezar por el resumen de variaciones anuales y su contexto compartido; después revisar las referencias de cada cuadro y los controles de fórmulas por separado."
    if not principal and controles_solicitados:
        resumen_controles = " ".join(
            f"{control.get('nombre')}: {control.get('resultado')}"
            for control in controles_solicitados
        )
        senal_inicial = resumen_controles
        if controles_no_evaluados:
            tono = "La pregunta declarada no pudo evaluarse por completo con la estructura disponible."
            por_que_importa = "Cero señales no equivale a conformidad cuando un control pedido quedó sin evaluar."
            siguiente_paso = "Revisar la estructura indicada en el motivo de no evaluación y volver a ejecutar el análisis."
        else:
            tono = "Los controles pedidos fueron ejecutados y su resultado se informa por separado de las señales."
            por_que_importa = "La respuesta surge de cálculos determinísticos aplicados a la estructura identificada."
            siguiente_paso = resumen_controles

    unidad = f"{_md(area.nombre)} ({_md(area.codigo)})"
    if (area.codigo or "").upper() == "GENERAL":
        unidad = "No informada (carga rápida)"
    dominio = _md(informe.dominio)
    periodo_observado = _periodo_observado(informe.datos)
    from services.reportes.registro import construir as _construir_registro

    registro = _construir_registro(informe, hallazgos)
    advertencia_periodo = (
        _advertencia_periodo(informe.periodo, periodo_observado) if registro["periodo"]["declarado"] is not False else None
    )
    archivos_origen = (informe.saneamiento or {}).get("archivos_origen", []) if isinstance(informe.saneamiento, dict) else []
    orientacion = _orientacion_informe(informe)
    estado_barrido = _estado_barrido_legible(
        informe.devolucion.estado if informe.devolucion else None,
        bool(hallazgos),
    )
    if not orientacion and informe.devolucion and informe.devolucion.estado == "COBERTURA_PARCIAL":
        estado_barrido = registro["primera_linea"].rstrip(".") + "; no equivale a conformidad completa"
    elif solo_exploratorios:
        estado_barrido = "Se encontraron asociaciones exploratorias para revisar; no son observaciones mecánicas"
    lentes_explicadas = "; ".join(
        f"{_nombre_lente(lente)}: {_descripcion_lente(lente)}"
        for lente in lentes_activas
    ) or "ninguna"
    cobertura_lentes = ((getattr(informe, "devolucion", None) and informe.devolucion.cobertura) or {}).get("lentes", [])
    def _resultado_lente(item: dict) -> str:
        estado = item.get("estado")
        if estado in {"no_evaluable", "no_aplicable"}:
            motivo = f" ({_md(item['motivo'])})" if item.get("motivo") else ""
            return estado.replace("_", " ") + motivo
        if estado == "sin_senales_comunicables":
            return "sin señales comunicables"
        from services.reporte_ejecutivo import senales

        return senales(item.get("hallazgos", 0))

    controles_ejecutados = "; ".join(
        f"{_nombre_lente(item.get('lente'))}: {_resultado_lente(item)}"
        for item in cobertura_lentes if isinstance(item, dict) and item.get("lente") and item.get("estado") not in {"no_evaluable","no_aplicable"}
    ) or "Cobertura no registrada"
    controles_fuera = "; ".join(
        f"{_nombre_lente(item.get('lente'))}: {_resultado_lente(item)}"
        for item in cobertura_lentes if item.get('estado') in {'no_aplicable','no_evaluable'}
    )
    control_negativo_rizoma = rizoma_svc.evidencia_control_negativo(informe.datos or []) if not hallazgos else None
    pocos_periodos = len(informe.datos or []) <= 8 and any(
        re.search(r"periodo|período|fecha|mes|año|anio", str(clave), re.I)
        for fila in (informe.datos or []) for clave in fila.keys()
    )
    retroceso_acumulado = any(
        isinstance(fundamento, dict) and fundamento.get("regla") == "serie_acumulada_retrocede"
        for fundamento in ((h.limites or {}).get("fundamento_regla") for h in hallazgos)
    )

    lineas = [
        "# Reporte de apoyo para la revisión",
        "",
        "## Cómo leer este reporte",
        "",
        "Este documento es un punto de partida para evaluar, contrastar y mejorar; no es un diagnóstico cerrado ni una respuesta que deba aceptarse sin revisión.",
        "",
        "- **Tu tarea:** comprobar la evidencia, aportar el contexto que el sistema no conoce y cuestionar las interpretaciones que no correspondan.",
        "- **Qué puede cambiar:** una señal puede confirmarse, reformularse, quedar en seguimiento o cerrarse después de la revisión.",
        "- **Qué muestra el aprendizaje:** las correcciones y decisiones humanas permiten comparar el reporte inicial con una versión mejor fundamentada.",
        "",
        "## 1. Lectura rápida",
        "",
        tono,
        "",
        f"- **Qué querías revisar:** {_md(orientacion)}" if orientacion else "- **Tipo de exploración:** abierta, sin una pregunta previa.",
        f"- **Qué llamó la atención:** {lenguaje_llano.traducir_en_texto(senal_inicial)}",
        f"- **{'Por qué merece revisión' if principal else 'Cómo interpretar este resultado'}:** {por_que_importa}",
        f"- **Qué revisar ahora:** {lenguaje_llano.traducir_en_texto(siguiente_paso)}",
        "",
        "### Resumen técnico",
        "",
        f"- Hallazgos seleccionados: {len(hallazgos)}",
        *(["- Los hallazgos pueden estar relacionados; su cantidad no equivale al número de errores ni de hechos independientes."] if len(hallazgos) > 1 else []),
        *[
            f"- Lecturas relacionadas: señales {', '.join(map(str, grupo))} corresponden a "
            f"{'una misma celda' if tipo == 'celda' else 'una misma transición temporal'}. "
            "No deben contarse automáticamente como problemas independientes; se conservan sus evidencias por separado."
            for tipo, grupo in _grupos_relacionados(hallazgos)
        ],
        *[f"- Tramos relacionados: señales {', '.join(map(str, grupo))} describen períodos consecutivos de una misma trayectoria físico-financiera; no deben contarse como casos independientes." for grupo in tramos_relacionados],
        f"- Casos por prioridad alta/media/baja (política única: rareza, impacto y evidencia): {por_prioridad['alta']}/{por_prioridad['media']}/{por_prioridad['baja']}",
        f"- Severidad original de los controles alta/media/baja: {por_severidad['alta']}/{por_severidad['media']}/{por_severidad['baja']} (dato histórico; no es la prioridad).",
        f"- Lecturas que produjeron señales: {lentes_explicadas}.",
        f"- Controles ejecutados y resultado: {controles_ejecutados}.",
        *([f"- Controles no aplicables o no evaluables: {controles_fuera}."] if controles_fuera else []),
        *(["- Lectura del retroceso: Ajedrecista aplica una regla de consistencia de acumulados; no es una inferencia de tendencia de Cronista."] if retroceso_acumulado else []),
        *(
            ["- Controles pedidos por la persona:"]
            + [f"  - **{_md(control.get('nombre'))}:** {_md(control.get('resultado'))} (estado: {_md(control.get('estado'))})." for control in controles_solicitados]
            if controles_solicitados else []
        ),
        *(
            [f"- Control negativo de Rizoma: {_md(control_negativo_rizoma['metodo'])} entre "
             f"{_md(control_negativo_rizoma['columnas'][0])} y {_md(control_negativo_rizoma['columnas'][1])}; "
             f"r = {control_negativo_rizoma['coeficiente_pearson']}; n = {control_negativo_rizoma['n_observaciones']}; "
             f"por debajo del umbral |r| ≥ {control_negativo_rizoma['umbral_seleccion_abs']}."]
            if control_negativo_rizoma else []
        ),
        *([f"- Primer foco sugerido: {_nombre_lente(principal.lente)}{(' · ' + _nombre_modo(principal.modo)) if principal.modo else ''}"] if principal else []),
        "",
        "## 2. Qué información se analizó",
        "",
        f"- Unidad responsable: {unidad}",
        f"- {registro['periodo']['texto']}",
        *([advertencia_periodo] if advertencia_periodo else []),
        f"- Dominio: {dominio}",
        (f"- {plural.contar(len(archivos_origen), 'Archivo de origen', 'Archivos de origen')}: "
         f"{', '.join(str(nombre) for nombre in archivos_origen)}") if archivos_origen
        else "- Archivos de origen: no registrados en cargas anteriores a esta versión.",
        f"- Registros analizados: {len(informe.datos or [])}. El conteo de filas no acredita por sí mismo que sean datos agregados.",
        *_lineas_lectura_reporte(informe),
        *( [f"- Limitación temporal: con solo {len(informe.datos or [])} registros/períodos, la capacidad para detectar patrones temporales es limitada."] if pocos_periodos else [] ),
        f"- Orientación declarada: {_md(orientacion)}" if orientacion else "- Tipo de lectura: exploración abierta, sin una pregunta previa.",
        "- Alcance de la orientación: ayuda a priorizar y explicar señales; no limita el barrido abierto ni convierte la pregunta en una conclusión." if orientacion else "- Alcance: exploración abierta de controles aplicables; las señales, cuando existen, abren preguntas para revisión.",
        f"- Generado: {fecha}",
        f"- Resultado general: {estado_barrido}.",
        "",
        "## 3. Cómo usar este resultado",
        "",
        "Este reporte identifica puntos que conviene revisar; no confirma errores, irregularidades ni responsabilidades.",
        "",
        f"- **Pregunta para empezar:** {lenguaje_llano.traducir_en_texto(pregunta_inicial)}",
        "- **Después de revisar:** registrar si la señal queda explicada, si continúa en seguimiento o si necesita una revisión formal."
        if principal else "- **Después de revisar:** registrar la cobertura y los controles no evaluables; si aparece información nueva, repetir la revisión.",
        "",
        "## 4. Señales que conviene revisar",
        "",
    ]

    from services.excel_cobertura import resumen_lineas
    excel_lineas = resumen_lineas(((getattr(informe, "devolucion", None) and informe.devolucion.cobertura) or {}).get("excel") or (informe.saneamiento or {}).get("excel"))
    if excel_lineas:
        lineas.extend(["", "## Cobertura del Excel", ""])
        lineas.extend(f"- {_md(x)}" for x in excel_lineas)
    lineas.extend(_lineas_priorizadas(hallazgos))
    contexto_series = _contexto_series_markdown(informe, hallazgos)
    contexto_pdf = _contexto_pdf_markdown(informe)
    contexto_extra = contexto_pdf + contexto_series
    if contexto_extra:
        punto = lineas.index("## 3. Cómo usar este resultado")
        lineas[punto:punto] = contexto_extra + [""]

    if not hallazgos:
        if controles_no_evaluados:
            lineas.append("No aparecieron señales seleccionadas, pero uno o más controles pedidos quedaron **no evaluados**. Este resultado no debe leerse como conformidad.")
        else:
            lineas.append("No aparecieron señales que requieran una revisión prioritaria con la información disponible.")
        lineas.append("")
    hay_controles_tabulares = any((h.evidencia or {}).get('puntaje_prioridad') is not None for h in hallazgos)
    seleccion_ejecutiva = _portada_politica(hallazgos) if hay_controles_tabulares else hallazgos
    mapa_casos = _casos_por_senal(hallazgos)
    for idx, h in enumerate(seleccion_ejecutiva, start=1):
        ubicacion = _referencia_hallazgo(h) or "No se pudo precisar una ubicación única"
        nivel_h, ejes_h, caso_h = _prioridad_y_ejes(h, mapa_casos)
        lineas.extend([
            f"### {idx}. Señal de prioridad {_prioridad_legible(nivel_h)}" + (f" · {caso_h}" if caso_h else ""),
            "",
            f"- **Qué pasó:** {lenguaje_llano.resumen_de(h)}",
            f"- **Por qué esta prioridad:** {ejes_h}",
            f"- **Qué se observó:** {lenguaje_llano.traducir_en_texto(_texto_corto(h.descripcion, 480))}",
            f"- **Dónde mirar:** {_pulir_redaccion(ubicacion)}"
            + (f" ({', '.join(v) if isinstance((v := (h.evidencia or {}).get('visibilidad_origen')), list) else v})" if (h.evidencia or {}).get("visibilidad_origen") else "")
            + ".",
            f"- **Qué conviene preguntar:** {lenguaje_llano.traducir_en_texto(_pregunta_sugerida(h))}",
            f"- **Qué aporta esta lectura:** {_nombre_lente(h.lente)} {_descripcion_lente(h.lente)}.",
        ])
        if (h.evidencia or {}).get("formula"):
            lineas.append(f"- **Detalle técnico:** fórmula en el archivo `{h.evidencia['formula']}`")
        contexto_tecnico = _contexto_tecnico_markdown(h)
        if contexto_tecnico:
            lineas.append(f"- **Contexto que puede explicar la señal:** {contexto_tecnico}")
        linea_convergencia = _linea_convergencia(h, convergencia_por_hallazgo)
        if linea_convergencia:
            lineas.append(f"- **Otras lecturas relacionadas:** {linea_convergencia.removeprefix('Converge con: ')}")
        lineas.extend([
            "- **Cómo actuar:** buscar contexto o documentación antes de escalar; si la explicación resulta suficiente, registrar el cierre.",
            "",
        ])

    if hay_controles_tabulares:
        lineas.extend(lectura_temporal.lineas_markdown(hallazgos))
        lineas.extend(["## Detalle completo de controles y contexto", "", "Los casos y el contexto están agrupados al inicio del anexo; la evidencia numérica se conserva a continuación.", ""])
    lineas.extend(["## 5. Evidencia para verificar", ""])
    if not hallazgos:
        lineas.append("Sin hallazgos seleccionados. Esto no implica ausencia de controles ni de evidencia: ver cobertura y resultados negativos registrados en el resumen técnico.")
        lineas.append("")
    for idx, h in enumerate(hallazgos, start=1):
        evidencia = _evidencia_markdown(h.evidencia)
        lineas.extend([f"### Evidencia de la señal {idx}", ""])
        if evidencia:
            lineas.extend(f"- {item}" for item in evidencia)
        else:
            lineas.append("- Sin evidencia estructurada adicional.")
        lineas.append("")

    if incluir_triangulacion and tri:
        lineas.extend(["## 6. Comparación entre lecturas de IA", ""])
        interpretaciones = list(informe.interpretaciones or [])
        if hay_apoyo_ia:
            lineas.append("Esta comparación ayuda a priorizar preguntas. Que dos modelos coincidan no demuestra que una señal sea verdadera.")
        else:
            lineas.append("No se incorporaron comentarios de IA sobre las señales. Las señales anteriores provienen de cuentas y controles automáticos. La interpretación previa del documento se declara por separado.")
        lineas.append("")
        if interpretaciones:
            lineas.append("**Modelos seleccionados y resultado:**")
            # La lectura de las señales y la exploración del libro son tareas distintas;
            # sin la segunda, una exploración fallida parecía completa (informes 244 y 245).
            from services.reporte_ejecutivo import _estado_exploracion

            manifiesto = ((getattr(informe.devolucion, "cobertura", None) or {}).get("manifiesto") or {}) if informe.devolucion else {}
            estrategias = {m.get("proveedor"): m.get("estrategia_semantica") for m in manifiesto.get("modelos", [])}
            for interpretacion in interpretaciones:
                estrategia = estrategias.get(interpretacion.modelo)
                lineas.append(
                    f"- {_md(interpretacion.modelo)}: {_estado_modelo_reporte(interpretacion, manifiesto)}"
                    + (f"; exploración del libro {_estado_exploracion(estrategia)}" if estrategia else "")
                    + "."
                )
            lineas.append("")
        if tri.convergencia_multilente:
            lineas.append("**Convergencia multilente** (preguntas distintas que, cada una por su propia razón, apuntan al mismo punto del reporte — no es votación; el detalle de cada hallazgo en la sección 4 indica dónde converge):")
            for item in tri.convergencia_multilente[:4]:
                lentes_fmt = ", ".join(_nombre_lente(x) for x in item.get("lentes", []))
                etiqueta = "independiente" if item.get("fuerza") == "fuerte" else "coincidencia esperable, no independiente"
                linea = f"- {lentes_fmt} coinciden sobre el mismo {item.get('locus_tipo')} ({item.get('locus_valor')}) — {etiqueta}."
                if item.get("con_contexto_tecnico"):
                    linea += f" {item['con_contexto_tecnico']} de {item.get('total_hallazgos', '?')} señales de este grupo ya fueron contextualizadas por el conciliador."
                lineas.append(linea)
            lineas.append("")
        modelos_con_respuesta = {i.modelo for i in interpretaciones if getattr(i, "contenido", None)}
        interpretacion_ia = ((getattr(informe.devolucion, "cobertura", None) or {}).get("interpretacion_ia") or {}) if informe.devolucion else {}
        if interpretacion_ia.get("linea_estado"):
            lineas.extend([_md(interpretacion_ia["linea_estado"]), ""])
        if tri.coincidencias and len(modelos_con_respuesta) >= 2:
            lineas.append("**Priorización coincidente (k de n modelos que recibieron cada señal; no es certeza):**")
            for texto in _textos_unicos(tri.coincidencias):
                lineas.append(f"- {texto}")
            lineas.append("")
        if tri.divergencias:
            lineas.append("**Priorización sin acuerdo entre los modelos que recibieron la señal:**")
            for texto in _textos_unicos(tri.divergencias):
                lineas.append(f"- {texto}")
            lineas.append("")
        if tri.hallazgos_singulares:
            modelos = [str(item.get("modelo")) for item in tri.hallazgos_singulares if item.get("modelo")]
            if modelos:
                lineas.append(f"**Modelos consultados:** {', '.join(modelos)}")
                lineas.append("**Lectura de modelos:** las interpretaciones se usan como apoyo para priorizar preguntas; no reemplazan la evidencia estructurada de los hallazgos.")
                for item in tri.hallazgos_singulares:
                    atribuida = item.get("lectura_atribuida") or (f"{item.get('modelo')}: {item.get('lectura')}" if item.get("lectura") else None)
                    if atribuida:
                        lineas.append(f"- {_texto_corto(atribuida, 700)}")
                lineas.append("")
        for d in interpretacion_ia.get("lecturas_descartadas") or []:
            lineas.append(f"- Lectura descartada de {_md(d.get('modelo'))}: {_md('; '.join(map(str, d.get('motivos') or [])) or 'motivo no informado')}.")
        if hay_apoyo_ia and not tri.coincidencias and not tri.divergencias and not tri.hallazgos_singulares:
            lineas.append("No hay triangulación comunicable para este informe.")
            lineas.append("")
        if incluir_detalle_modelos and tri.hallazgos_singulares:
            lineas.extend(["### Detalle completo de modelos", ""])
            for item in tri.hallazgos_singulares:
                modelo = _md(item.get("modelo")) + (f" ({item['rol']})" if item.get("rol") in {"principal", "respaldo"} else "")
                lectura = _texto_corto(item.get("lectura"), 700)
                confianza = _md(item.get("confianza"))
                lineas.append(f"- {modelo} ({confianza}): {lectura}")
            lineas.append("")

    if incluir_devolucion:
        numero = "7" if incluir_triangulacion and tri else "6"
        lineas.extend([f"## {numero}. Próximos pasos sugeridos", ""])
        from services.reporte_ejecutivo import _proximos_pasos

        lineas.extend(f"- {paso}" for paso in _proximos_pasos(_revision, registro))
        lineas.append("")
        if hallazgos and _revision["casos"]:
            lineas.extend([
                "Después de verificar la evidencia y pedir el contexto necesario, la persona responsable puede:",
                "",
                "- Cerrar la señal si encuentra una explicación suficiente.",
                "- Dejarla en seguimiento si necesita observar su evolución.",
                "- Pedir una aclaración o documentación adicional.",
                "- Escalarla a revisión formal si la evidencia lo justifica.",
                "",
                "Estas acciones son posteriores al control y no condicionan la emisión automática del comprobante.",
            ])
        elif informe.devolucion:
            if pocos_periodos:
                lineas.append(f"La ausencia de señales debe leerse con cautela: solo se analizaron {len(informe.datos or [])} registros/períodos.")
        else:
            lineas.append("No hay devolución consolidada disponible.")
        lineas.append("")

    lineas.extend(_anexo_controles_automaticos(informe))

    lineas.extend(["## Anexo técnico de señales", ""])
    if not hallazgos:
        lineas.append("No hay detalles técnicos de señales para mostrar.")
        lineas.append("")
    for idx, h in enumerate(hallazgos, start=1):
        lineas.extend([
            f"### Señal {idx}",
            "",
            f"- Lente: {_nombre_lente(h.lente)}",
            f"- Modo de análisis: {_nombre_modo(h.modo)}",
            f"- Tipo de evidencia: {_pulir_redaccion(_md(h.tipo_evidencia).replace('_', ' ').lower())}",
            f"- Incertidumbre: {_md(h.incertidumbre)}",
        ])
        fundamento = _fundamento_regla_markdown(h)
        if fundamento:
            lineas.append(f"- Fundamento y trazabilidad: {fundamento}")
        lineas.append("")

    lineas.extend([
        "## Alcance y límites",
        "",
        ALCANCE_REVISION,
        "",
        "- Trabaja con la información agregada que se cargó; no conoce por sí solo el contexto completo del área.",
        "- Una señal es una invitación a revisar, no una prueba de error, culpa, ilegalidad o responsabilidad.",
        "- Las asociaciones abren preguntas y no demuestran relaciones de causa y efecto.",
        *(["- La coincidencia entre modelos no convierte una interpretación en certeza."] if hay_apoyo_ia else []),
        "- No reemplaza el criterio experto, la decisión humana, una auditoría ni los procedimientos formales.",
        "- No evalúa ideologías ni la oportunidad, el mérito o la conveniencia de una decisión.",
        "",
        "## Cierre",
        "",
        "Este documento organiza preguntas para una revisión responsable, neutral y basada en evidencia agregada. La decisión de escalar, pedir contexto o descartar una señal queda fuera del sistema y corresponde a la persona responsable.",
        "",
    ])
    return "\n".join(lineas)



def _pdf_escape(texto: str) -> str:
    limpio = _sin_glifos_faltantes(texto).encode("cp1252", "replace").decode("latin-1")
    return limpio.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _texto_pdf_desde_markdown(markdown_texto: str) -> list[tuple[str, int, bool]]:
    lineas: list[tuple[str, int, bool]] = []
    for raw in markdown_texto.splitlines():
        linea = raw.strip()
        if not linea:
            lineas.append(("", 11, False))
            continue
        if linea.startswith("# "):
            lineas.append((linea[2:], 18, True))
        elif linea.startswith("## "):
            lineas.append((linea[3:], 14, True))
        elif linea.startswith("### "):
            lineas.append((linea[4:], 12, True))
        elif linea.startswith("- "):
            lineas.append(("• " + linea[2:], 10, False))
        else:
            lineas.append((linea, 10, False))
    return lineas


def _wrap_pdf(texto: str, max_chars: int) -> list[str]:
    if not texto:
        return [""]
    palabras = texto.split()
    lineas: list[str] = []
    actual = ""
    for palabra in palabras:
        candidato = palabra if not actual else actual + " " + palabra
        if len(candidato) <= max_chars:
            actual = candidato
        else:
            if actual:
                lineas.append(actual)
            while len(palabra) > max_chars:
                lineas.append(palabra[:max_chars])
                palabra = palabra[max_chars:]
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or [""]


def _render_reporte_pdf_basico(markdown_texto: str) -> bytes:
    """Genera un PDF textual y legible sin depender de librerias externas."""
    width = 595
    height = 842
    left = 54
    top = 790
    bottom = 52
    objetos: list[bytes] = []
    paginas: list[int] = []
    stream_actual: list[str] = []
    y = top

    def nueva_pagina() -> None:
        nonlocal stream_actual, y
        if stream_actual:
            contenido = "\n".join(stream_actual).encode("latin-1", "replace")
            objetos.append(b"<< /Length " + str(len(contenido)).encode() + b" >>\nstream\n" + contenido + b"\nendstream")
            contenido_id = 4 + len(objetos)
            objetos.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {contenido_id} 0 R >>".encode()
            )
            paginas.append(4 + len(objetos))
        stream_actual = []
        y = top

    for texto, size, bold in _texto_pdf_desde_markdown(markdown_texto):
        max_chars = max(42, int((width - left * 2) / (size * 0.47)))
        wrapped = _wrap_pdf(texto.replace("**", ""), max_chars)
        for linea in wrapped:
            leading = size + 5
            if y - leading < bottom:
                nueva_pagina()
            font = "F2" if bold else "F1"
            stream_actual.append(f"BT /{font} {size} Tf {left} {y} Td ({_pdf_escape(linea)}) Tj ET")
            y -= leading
        y -= 3 if texto else 5
    nueva_pagina()
    if not paginas:
        stream_actual.append(f"BT /F1 10 Tf {left} {top} Td (Reporte sin contenido) Tj ET")
        nueva_pagina()

    kids = " ".join(f"{pid} 0 R" for pid in paginas)
    base = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(paginas)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    todos = base + objetos
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(todos, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(todos) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(todos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def _inline_reportlab(texto: str) -> str:
    """Convierte el pequeño subconjunto inline usado por los reportes."""
    salida = html.escape(re.sub(r"\\([_])", r"\1", texto))
    salida = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", salida)
    salida = re.sub(r"`(.+?)`", r"<font color='#34506f'>\1</font>", salida)
    return salida


FUENTES_UNICODE = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
)

# Sin una fuente con estos glifos (Helvetica de base), se escriben con caracteres que sí tiene.
REEMPLAZOS_SIN_GLIFO = {"→": "»", "←": "«", "≈": "aprox. ", "≤": "<=", "≥": ">=", "−": "-", "✓": "sí", "✗": "no"}


def _fuente_unicode() -> tuple[str | None, str | None]:
    """Una fuente con flechas y signos (DejaVu), en la ruta de la distribución que esté instalada."""
    for regular, negrita in FUENTES_UNICODE:
        if os.path.exists(regular) and os.path.exists(negrita):
            return regular, negrita
    return None, None


def _sin_glifos_faltantes(texto: str) -> str:
    for a, b in REEMPLAZOS_SIN_GLIFO.items():
        texto = texto.replace(a, b)
    return texto


def _filas_tabla_md(lineas_tabla: list[str]) -> list[list[str]]:
    filas = []
    for linea in lineas_tabla:
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in celdas if c):
            continue  # separador del encabezado
        filas.append(celdas)
    return filas


def render_reporte_pdf(markdown_texto: str) -> bytes:
    """Genera un PDF institucional con jerarquía visual y Unicode.

    Mantiene un generador básico como respaldo para que una falla de la capa
    estética nunca impida descargar la evidencia del análisis.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            KeepTogether,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        return _render_reporte_pdf_basico(markdown_texto)

    es_comprobante = markdown_texto.lstrip().startswith("# Comprobante de controles automáticos aplicados")

    regular_path, bold_path = _fuente_unicode()
    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    if regular_path and bold_path:
        if "GobernanzaSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("GobernanzaSans", regular_path))
            pdfmetrics.registerFont(TTFont("GobernanzaSans-Bold", bold_path))
        font_regular = "GobernanzaSans"
        font_bold = "GobernanzaSans-Bold"

    navy = colors.HexColor("#B01C2E")
    blue = colors.HexColor("#8C1626")
    blue_soft = colors.HexColor("#F8E9EC")
    ink = colors.HexColor("#2E292A")
    muted = colors.HexColor("#62595B")
    line = colors.HexColor("#E5DADD")
    gold = colors.HexColor("#765D52")
    green_soft = colors.HexColor("#E9F7EF")
    green = colors.HexColor("#177245")
    paper = colors.white

    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "GovBody", parent=base["BodyText"], fontName=font_regular,
        fontSize=7.8 if es_comprobante else 9.2,
        leading=9.8 if es_comprobante else 13.2,
        textColor=ink, spaceAfter=2 if es_comprobante else 5,
        allowWidows=0, allowOrphans=0,
    )
    bullet = ParagraphStyle(
        "GovBullet", parent=body, leftIndent=12, firstLineIndent=0,
        bulletIndent=1, spaceAfter=1.5 if es_comprobante else 4,
    )
    h2 = ParagraphStyle(
        "GovH2", parent=body, fontName=font_bold,
        fontSize=10.4 if es_comprobante else 13,
        leading=12.5 if es_comprobante else 16,
        textColor=navy, spaceBefore=4 if es_comprobante else 10,
        spaceAfter=3 if es_comprobante else 7,
        keepWithNext=True,
    )
    h3 = ParagraphStyle(
        "GovH3", parent=body, fontName=font_bold, fontSize=10.5,
        leading=13.5, textColor=blue, spaceBefore=7, spaceAfter=5,
        keepWithNext=True,
    )
    cover_title = ParagraphStyle(
        "GovCoverTitle", parent=body, fontName=font_bold,
        fontSize=16 if es_comprobante else 20,
        leading=19 if es_comprobante else 25,
        textColor=paper, spaceAfter=0,
    )
    cover_subtitle = ParagraphStyle(
        "GovCoverSubtitle", parent=body, fontName=font_regular, fontSize=8.4,
        leading=11, textColor=colors.HexColor("#FBE3E6"), spaceAfter=0,
    )
    callout = ParagraphStyle(
        "GovCallout", parent=body,
        fontSize=7.6 if es_comprobante else 8.7,
        leading=9.7 if es_comprobante else 12.5,
        textColor=colors.HexColor("#3A4C5F"),
    )
    status_style = ParagraphStyle(
        "GovStatus", parent=body, fontName=font_bold,
        fontSize=8.8 if es_comprobante else 10,
        leading=11 if es_comprobante else 13, textColor=green,
    )
    status_exploratorio_style = ParagraphStyle(
        "GovStatusExploratorio", parent=status_style, textColor=navy,
    )

    salida = io.BytesIO()
    margen_lateral = 12 * mm if es_comprobante else 17 * mm
    doc = SimpleDocTemplate(
        salida, pagesize=A4, rightMargin=margen_lateral, leftMargin=margen_lateral,
        topMargin=14 * mm if es_comprobante else 18 * mm,
        bottomMargin=13 * mm if es_comprobante else 17 * mm,
        title="Reporte Gobernanza Multilente", author="Gobernanza Multilente",
        subject="Controles automáticos aplicados y señales para revisión",
    )

    def encabezado_pie(canvas, documento) -> None:
        ancho, alto = A4
        canvas.saveState()
        canvas.setFillColor(navy)
        canvas.rect(0, alto - 8 * mm, ancho, 8 * mm, stroke=0, fill=1)
        canvas.setFillColor(gold)
        canvas.rect(0, alto - 8.8 * mm, ancho, .8 * mm, stroke=0, fill=1)
        canvas.setFont(font_bold, 7.5)
        canvas.setFillColor(colors.white)
        canvas.drawString(margen_lateral, alto - 5.3 * mm, "GOBERNANZA MULTILENTE")
        canvas.setStrokeColor(line)
        canvas.line(margen_lateral, 10 * mm if es_comprobante else 12 * mm, ancho - margen_lateral, 10 * mm if es_comprobante else 12 * mm)
        canvas.setFont(font_regular, 7)
        canvas.setFillColor(muted)
        etiqueta_pie = ("Comprobante de controles automáticos aplicados" if es_comprobante else "Reporte de apoyo para la revisión") + " · Una segunda lectura antes de decidir"
        canvas.drawString(margen_lateral, 7 * mm if es_comprobante else 8.2 * mm, etiqueta_pie)
        canvas.drawRightString(ancho - margen_lateral, 7 * mm if es_comprobante else 8.2 * mm, f"Página {documento.page}")
        canvas.restoreState()

    if font_regular == "Helvetica":
        markdown_texto = _sin_glifos_faltantes(markdown_texto)
    tabla_body = ParagraphStyle("GovTabla", parent=body, fontSize=7.6, leading=9.4, spaceAfter=0)
    numerada_style = ParagraphStyle("GovNumerada", parent=bullet, leftIndent=17, spaceAfter=5)
    tabla_head = ParagraphStyle("GovTablaHead", parent=tabla_body, fontName=font_bold, textColor=navy)

    def tabla_desde_md(lineas_tabla):
        filas = _filas_tabla_md(lineas_tabla)
        if not filas:
            return None
        ncol = max(len(f) for f in filas)
        filas = [f + [""] * (ncol - len(f)) for f in filas]
        datos = [[Paragraph(_inline_reportlab(c), tabla_head if i == 0 else tabla_body) for c in f] for i, f in enumerate(filas)]
        # Columnas cortas a la izquierda (número, prioridad, lugar) y la descripción con el resto.
        largos = [max(len(f[j]) for f in filas) for j in range(ncol)]
        fijas = [min(max(3, largo) * 1.9 * mm + 2 * mm, 48 * mm) for largo in largos[:-1]]
        anchos = fijas + [max(40 * mm, doc.width - sum(fijas))]
        tabla = Table(datos, colWidths=anchos, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), .6, blue),
            ("LINEBELOW", (0, 1), (-1, -1), .25, line),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        return tabla

    story = []
    titulo_creado = False
    inicio_limites = None
    pendiente_tabla: list[str] = []
    lineas_md = markdown_texto.splitlines() + [""]
    for raw in lineas_md:
        linea_md = raw.strip()
        if linea_md.startswith("|") and linea_md.endswith("|"):
            pendiente_tabla.append(linea_md)
            continue
        if pendiente_tabla:
            tabla = tabla_desde_md(pendiente_tabla)
            pendiente_tabla = []
            if tabla is not None:
                story.extend([tabla, Spacer(1, 2 * mm)])
        numerada = re.match(r"^(\d{1,3})\.\s+(.*)$", linea_md)
        if numerada:
            story.append(Paragraph(_inline_reportlab(numerada.group(2)), numerada_style, bulletText=numerada.group(1) + "."))
            continue
        if linea_md == '<!-- salto-pagina -->':
            # Si la página anterior se llenó justo, un salto común deja una hoja en blanco: los espacios
            # sueltos del final pasan solos a la página nueva. Se quitan, y el salto no actúa en una página vacía.
            from reportlab.platypus.flowables import PageBreakIfNotEmpty
            while story and isinstance(story[-1], Spacer):
                story.pop()
            story.append(PageBreakIfNotEmpty())
            continue
        if not linea_md:
            story.append(Spacer(1, .7 * mm if es_comprobante else 1.2 * mm))
            continue
        if linea_md.startswith("# ") and not titulo_creado:
            titulo = linea_md[2:]
            caja = Table(
                [[Paragraph("GOBERNANZA MULTILENTE", cover_subtitle),
                  Paragraph(_inline_reportlab(titulo), cover_title)]],
                colWidths=[34 * mm if es_comprobante else 43 * mm, doc.width - (34 * mm if es_comprobante else 43 * mm)],
            )
            caja.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), navy),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 8 * mm),
                ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
                ("RIGHTPADDING", (1, 0), (1, 0), 8 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm if es_comprobante else 8 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm if es_comprobante else 8 * mm),
                ("LINEBEFORE", (1, 0), (1, 0), 1.2, gold),
                ("ROUNDEDCORNERS", [8]),
            ]))
            story.extend([caja, Spacer(1, 2 * mm if es_comprobante else 5 * mm)])
            titulo_creado = True
            continue
        if linea_md.startswith("## "):
            if linea_md == "## Alcance y límites":
                inicio_limites = len(story)
            texto = Paragraph(_inline_reportlab(linea_md[3:]), h2)
            franja = Table([[texto]], colWidths=[doc.width])
            franja.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), blue_soft),
                ("BOX", (0, 0), (-1, -1), .5, line),
                ("LINEBEFORE", (0, 0), (0, 0), 3, blue),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1 * mm if es_comprobante else 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm if es_comprobante else 2 * mm),
            ]))
            espacio_seccion = .7 * mm if es_comprobante else 2 * mm
            franja.keepWithNext = True
            separador = Spacer(1, espacio_seccion)
            separador.keepWithNext = True
            story.extend([Spacer(1, espacio_seccion), franja, separador])
            continue
        if linea_md.startswith("### "):
            story.append(Paragraph(_inline_reportlab(linea_md[4:]), h3))
            continue
        if linea_md.startswith("> "):
            texto = Paragraph(_inline_reportlab(linea_md[2:]), callout)
            caja = Table([[texto]], colWidths=[doc.width - 4 * mm])
            caja.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E5")),
                ("LINEBEFORE", (0, 0), (0, 0), 3, gold),
                ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#E9D7A8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm if es_comprobante else 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm if es_comprobante else 3 * mm),
            ]))
            story.append(KeepTogether([caja, Spacer(1, 2 * mm)]))
            continue
        if linea_md.startswith("- "):
            story.append(Paragraph(_inline_reportlab(linea_md[2:]), bullet, bulletText="•"))
            continue
        if linea_md.startswith("**Estado:**") or linea_md.startswith("**Resultado automático:**"):
            tiene_exploratoria = "SEÑAL EXPLORATORIA" in linea_md or "SEÑALES EXPLORATORIAS" in linea_md
            estado = Paragraph(_inline_reportlab(linea_md), status_exploratorio_style if tiene_exploratoria else status_style)
            caja = Table([[estado]], colWidths=[doc.width - 4 * mm])
            caja.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), blue_soft if tiene_exploratoria else green_soft),
                ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#B8CFE4") if tiene_exploratoria else colors.HexColor("#A9D8BC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]))
            story.append(caja)
            continue
        story.append(Paragraph(_inline_reportlab(linea_md), body))

    if inicio_limites is not None:
        story[inicio_limites:] = [KeepTogether(story[inicio_limites:])]
    if not story:
        story.append(Paragraph("Reporte sin contenido", body))
    try:
        doc.build(story, onFirstPage=encabezado_pie, onLaterPages=encabezado_pie)
        return salida.getvalue()
    except Exception:
        return _render_reporte_pdf_basico(markdown_texto)

def render_reporte_html(markdown_texto: str) -> str:
    """Convierte el reporte Markdown a un HTML simple, legible y UTF-8.

    El Markdown queda como formato tecnico editable, pero para usuarios finales
    conviene entregar HTML: abre bien en navegador, respeta tildes y se puede
    imprimir/guardar como PDF sin mostrar marcas como ##, ** o guiones crudos.
    """
    partes: list[str] = []
    en_lista = False

    def cerrar_lista() -> None:
        nonlocal en_lista
        if en_lista:
            partes.append("</ul>")
            en_lista = False

    def inline(src: str) -> str:
        out = html.escape(src)
        out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
        out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
        return out

    tabla: list[str] = []

    def cerrar_tabla() -> None:
        if not tabla:
            return
        filas = _filas_tabla_md(tabla)
        tabla.clear()
        if not filas:
            return
        partes.append("<table>")
        partes.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in filas[0]) + "</tr>")
        for f in filas[1:]:
            partes.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in f) + "</tr>")
        partes.append("</table>")

    for raw in markdown_texto.splitlines():
        linea = raw.strip()
        if linea.startswith("|") and linea.endswith("|"):
            cerrar_lista()
            tabla.append(linea)
            continue
        cerrar_tabla()
        if not linea or linea.startswith("<!--"):
            cerrar_lista()
            continue
        if linea.startswith("### "):
            cerrar_lista()
            partes.append(f"<h3>{inline(linea[4:])}</h3>")
        elif linea.startswith("## "):
            cerrar_lista()
            partes.append(f"<h2>{inline(linea[3:])}</h2>")
        elif linea.startswith("# "):
            cerrar_lista()
            partes.append(f"<h1>{inline(linea[2:])}</h1>")
        elif linea.startswith("- "):
            if not en_lista:
                partes.append("<ul>")
                en_lista = True
            partes.append(f"<li>{inline(linea[2:])}</li>")
        else:
            cerrar_lista()
            partes.append(f"<p>{inline(linea)}</p>")
    cerrar_tabla()
    cerrar_lista()
    cuerpo = "\n".join(partes)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Reporte Gobernanza Multilente</title>
  <style>
    :root {{ font-family: Inter, Arial, sans-serif; color: #162033; background: #f3f6f9; }}
    body {{ margin: 0; padding: 32px; }}
    main {{ max-width: 920px; margin: 0 auto; background: #fff; border: 1px solid #dbe3ec; border-radius: 10px; padding: 34px 42px; box-shadow: 0 18px 45px rgba(22,32,51,.08); }}
    h1 {{ font-size: 28px; margin: 0 0 22px; }}
    h2 {{ font-size: 20px; margin: 30px 0 12px; padding-top: 18px; border-top: 1px solid #e4ebf2; }}
    h3 {{ font-size: 16px; margin: 22px 0 8px; }}
    p, li {{ font-size: 15px; line-height: 1.58; }}
    ul {{ padding-left: 22px; }}
    li {{ margin: 7px 0; }}
    code {{ background: #eef3f8; padding: 1px 4px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ text-align: left; vertical-align: top; padding: 4px 6px; border-bottom: 1px solid #e4ebf2; }}
    @media print {{ body {{ background: #fff; padding: 0; }} main {{ box-shadow: none; border: 0; padding: 0; }} }}
  </style>
</head>
<body>
  <main>
{cuerpo}
  </main>
</body>
</html>"""


def _encabezar_consulta(texto, informe, hallazgos):
    orientacion = _orientacion_informe(informe)
    controles = _controles_solicitados_informe(informe)
    cobertura = getattr(getattr(informe, "devolucion", None), "cobertura", None) or {}
    if not controles:
        controles = (cobertura.get("controles_solicitados") or {}).get("controles") or []
    no_evaluados = [c for c in controles if c.get("estado") == "no_evaluable"]
    parciales = [c for c in controles if c.get("cobertura_parcial")]
    # Si la consulta no pudo evaluarse, eso es el resultado: va en la primera línea y no repartido
    # entre secciones. Las señales generales no responden la pregunta que la persona declaró.
    if str(cobertura.get("estado") or "") == "PREGUNTA_NO_EVALUADA":
        estado = (
            "La pregunta declarada no pudo evaluarse con la estructura disponible. "
            "Lo que sigue son señales generales del barrido: no responden la consulta."
        )
    elif no_evaluados or parciales:
        estado = "La consulta quedó sin evaluar o se evaluó parcialmente. No equivale a un control superado."
    elif controles:
        estado = "Los controles específicos solicitados fueron ejecutados. Sus resultados se indican a continuación; no certifican el informe."
    elif orientacion:
        estado = "No hay una evaluación específica registrada para la consulta. Las señales generales no acreditan que se haya respondido."
    else:
        estado = "Exploración abierta, sin una consulta específica declarada."
    from services.reportes.registro import construir
    from services.resultado_revision import alcance

    lectura = alcance(informe)
    registro = construir(informe, hallazgos, cobertura)
    # Lo no leído o no controlado va en la primera línea: antes que cualquier señal.
    salida = ["", f"**{registro['primera_linea']}**", ""]
    detalle_pdf = [x for x in lectura["detalle_pdf"] if x not in texto]
    if detalle_pdf:
        salida.extend([*detalle_pdf, ""])
    salida.extend(["## Resultado de la consulta", "", estado, ""])
    if orientacion:
        salida.append(f"- **Consulta:** {_md(orientacion)}")
    for c in controles:
        salida.append(f"- **{_md(c.get('nombre'))}:** {_md(c.get('resultado'))}")
    from services.columnas_declaradas import linea_declarada

    restringido = linea_declarada(cobertura.get("restricciones_declaradas"))
    if restringido:
        salida.append(f"- **Restricción declarada:** {restringido}")
    from services.casos_revision import agrupar
    from services.reporte_ejecutivo import senales
    resumen = agrupar(hallazgos)
    salida.append(
        f"- **Qué se encontró:** {plural.contar(resumen['casos_revision'], 'caso')} de control ({senales(resumen['senales_control'])} para revisar); "
        f"{plural.contar(resumen['senales_contexto'], 'variación temporal individual', 'variaciones temporales individuales')} como contexto; "
        f"{plural.contar(resumen['senales_exploratorias'], 'asociación exploratoria', 'asociaciones exploratorias')} separadas"
        + (f"; {plural.contar(resumen.get('notas_alcance', 0), 'nota', 'notas')} de alcance de cruces" if resumen.get("notas_alcance") else "")
        + ". No equivalen a errores confirmados."
    )
    fuera = [p for p in registro["pendientes"]]
    no_aplica = [c for c in registro["controles"] if c["estado"] == "no_aplicable"]
    if fuera:
        salida.append("- **Qué quedó fuera:** " + "; ".join(
            (f"{p['archivo']}: " if p.get("archivo") else "") + f"{p['donde']} ({_md(p['motivo'])})" for p in fuera) + ".")
    if no_aplica:
        salida.append("- **No aplicable:** " + "; ".join(f"{c['nombre']} ({_md(c.get('motivo') or 'no aplica')})" for c in no_aplica) + ".")
    if not fuera and not no_aplica:
        salida.append("- **Alcance:** se leyó todo lo cargado y se ejecutaron todos los controles; la ausencia de señales no certifica el informe.")
    from services.reporte_ejecutivo import _proximos_pasos

    salida += [f"- **Próximo paso:** {_proximos_pasos(resumen, registro)[0]}", ""]
    titulo, separador, resto = texto.partition("\n")
    # El estado ya encabeza el documento: no repetirlo más abajo.
    resto = "\n".join(x for x in resto.split("\n") if not x.startswith("**Alcance:"))
    return titulo + "\n" + "\n".join(salida) + "\n" + resto


def _con_lectura_revisada(texto, informe):
    """Una tabla leída de un PDF o una imagen lo dice arriba, debajo del título."""
    lr = (getattr(informe, "saneamiento", None) or {}).get("lectura_revisada")
    if not (isinstance(lr, dict) and lr.get("archivo_original")):
        return texto
    if "**Tabla leída " in texto[:2000]:
        return texto  # ya la trae el informe ejecutivo
    titulo, _, resto = texto.partition("\n")
    con_ocr = "con OCR " if lr.get("origen") == "revision_ocr" else ""
    return f"{titulo}\n\n**Tabla leída {con_ocr}de {_md(lr['archivo_original'])} y revisada por una persona antes de analizar.**\n{resto}"


def _lectura_al_principio(texto):
    """La advertencia de transcripción conserva precedencia sobre la nueva trazabilidad."""
    aviso = re.search(r"(?m)^\*\*Tabla leída[^\n]+\*\*[ \t]*$", texto)
    if aviso:
        etiqueta = aviso.group(0)
        texto = texto[:aviso.start()] + texto[aviso.end():]
        titulo, _, resto = texto.partition("\n")
        return titulo + "\n\n" + etiqueta + "\n" + resto
    return texto


_ANEXO_LECTURA = "### Qué se leyó y qué se controló\n"


def _insertar_lectura(texto, bloque):
    """En el informe con anexo, la lectura va en «Qué se leyó y qué se controló»; si no, debajo del título."""
    if _ANEXO_LECTURA in texto:
        antes, _, despues = texto.partition(_ANEXO_LECTURA)
        return antes + _ANEXO_LECTURA + "\n" + bloque + "\n" + despues
    titulo, _, resto = texto.partition("\n")
    return titulo + "\n" + bloque + "\n" + resto


def _con_lector_cuadro(texto, informe, detalle_por_cuadro=True):
    """La cobertura del lector se exporta también con cero señales y con lectura parcial."""
    from services import interpretacion_previa as ip
    from services.lector_mapa import resumen_lectura
    previa = (getattr(informe, "saneamiento", None) or {}).get(ip.CAMPO)
    if previa:
        texto = _insertar_lectura(texto, "\n**Interpretación confirmada antes de los controles**\n\n"
                                  + "\n".join(_md(t) for t in ip.resumen(previa)) + "\n")
        if detalle_por_cuadro:
            texto = texto.rstrip("\n") + "\n\n### Interpretación por cuadro\n\n" + "\n\n".join(_md(t) for t in ip.lineas(previa)) + "\n"

    mapa = (getattr(informe, "saneamiento", None) or {}).get("mapa_lectura") or {}
    if not mapa:
        return _lectura_al_principio(texto)
    r = resumen_lectura(mapa)
    estado = {"completada": "completada", "parcial": "PARCIAL", "no_completada": "NO COMPLETADA"}[r["estado"]]
    lineas = ["", f"**Lector del cuadro: lectura {estado}.** "
              f"{r['hojas']} hojas; {r['tramos_con_lectura']} de {r['tramos']} bloques con al menos dos respuestas; "
              f"las lectoras de IA acordaron {r['relaciones_acordadas']} relaciones para verificar (aparte de los cierres que comprueba el motor); "
              f"{mapa.get('senales', 0)} señales. "
              f"Versión `{_md(mapa.get('version') or 'no informada')}`.",
              "La IA propone relaciones a ciegas, las reglas comprueban los números y la persona decide. "
              "Cero señales no certifica el informe ni implica que se hayan identificado todas sus relaciones."]
    if r["lecturas_fallidas"]:
        lineas.append(f"- {r['lecturas_fallidas']} respuestas de las lectoras fallaron; la cobertura quedó limitada.")
    lineas.append(f"Se controlaron {r['relaciones_controladas']} relaciones. Recibir las lecturas no garantiza "
                  "que se hayan identificado y controlado todos los totales del cuadro.")
    if r["diferencias_no_mostradas"]:
        lineas.append(f"**Detalle limitado:** se muestran {r['diferencias_mostradas']} de "
                      f"{r['diferencias_total']} diferencias de las relaciones controladas; "
                      f"{r['diferencias_no_mostradas']} adicionales quedan registradas. "
                      "El límite es de cinco por relación; no son un recuento de errores independientes.")
        for limite in r["limites_de_muestra"]:
            lineas.append(f"- {_md(limite['archivo'])}, hoja {_md(limite['hoja'])}, relación "
                          f"{_md(limite['relacion'])}: {limite['mostradas']} de {limite['total']} diferencias mostradas.")
    for x in mapa.get("sin_leer") or []:
        cuadro = f", cuadro {_md(x['bloque'])}" if x.get("bloque") is not None else ""
        lineas.append(f"- {_md(x.get('archivo'))}, hoja {_md(x.get('hoja'))}{cuadro}: {_md(x.get('motivo')).rstrip('. ')}.")
    lineas.append("")
    return _lectura_al_principio(_insertar_lectura(texto, "\n".join(lineas)))


def linea_modo_revision(informe):
    """Qué revisión fue, en una línea; en la rápida, también lo que no corrió. Vacío en corridas anteriores."""
    meta = getattr(informe, "saneamiento", None) or {}
    modo = meta.get("modo_revision")
    if modo == "rapida":
        rapida = meta.get("revision_rapida") or {}
        no_corrieron = rapida.get("no_corrieron") or []
        linea = "**Revisión rápida: sin IA." + (f" No se corrieron: {', '.join(no_corrieron)}." if no_corrieron else "") + "**"
        if rapida.get("presupuesto"):
            linea += " Las reglas de presupuesto corrieron porque se declaró el dominio presupuestario."
        return linea
    if modo == "profunda":
        return "**Revisión profunda: la IA interpretó cada cuadro y una persona confirmó la interpretación antes de los controles.**"
    return ""


def _con_modo_revision(texto, informe):
    """La primera línea, debajo del título, dice qué revisión fue."""
    linea = linea_modo_revision(informe)
    if not linea:
        return texto
    titulo, _, resto = texto.partition("\n")
    return f"{titulo}\n\n{linea}\n{resto}"


def render_comprobante_controles_markdown(informe, job=None):
    from services.reportes.formato import normalizar_documento, valores_de_hallazgos

    return normalizar_documento(_con_modo_revision(_con_lector_cuadro(_con_lectura_revisada(_render_comprobante_controles_markdown(informe, job), informe), informe), informe),
                                valores_de_hallazgos(getattr(informe, "hallazgos", None)))


def _render_comprobante_controles_markdown(informe,job=None):
    from services.reporte_ejecutivo import anexo_contexto, lineas
    hs=list(getattr(informe,'hallazgos',[]) or [])
    detalle=_detalle_comprobante_controles_markdown(informe,job)
    from services.semantica_excel import markdown, presentar_cobertura
    detalle += markdown(presentar_cobertura(getattr(getattr(informe,"devolucion",None),"cobertura",None)).get("exploracion_semantica"))
    from services.casos_revision import agrupar
    r=agrupar(hs)
    if r["senales_tecnicas"] <= 20 and not any(c["related_findings"] for c in r["casos"]):
        return _encabezar_consulta(detalle, informe, hs)
    # `lineas` ya abre con lo no leído, la consulta declarada y las consultas al área.
    return '\n'.join(lineas(informe,hs,'Comprobante de controles automáticos aplicados')+['<!-- salto-pagina -->','## Anexo técnico completo','']+anexo_contexto(hs)+['',detalle])


def render_reporte_markdown(informe, hallazgos, incluir_triangulacion, incluir_devolucion, incluir_detalle_modelos=False, pieza="completo"):
    from services.reportes.formato import normalizar_documento, valores_de_hallazgos

    return normalizar_documento(
        _con_modo_revision(
            _con_lector_cuadro(_con_lectura_revisada(_render_reporte_markdown(informe, hallazgos, incluir_triangulacion, incluir_devolucion, incluir_detalle_modelos, pieza), informe), informe,
                               detalle_por_cuadro=pieza != "ejecutivo"),
            informe),
        valores_de_hallazgos(hallazgos),
    )


def _render_reporte_markdown(informe,hallazgos,incluir_triangulacion,incluir_devolucion,incluir_detalle_modelos=False,pieza="completo"):
    from services.reporte_ejecutivo import anexo_contexto, lineas
    if pieza not in {"ejecutivo", "anexo", "completo"}:
        raise ValueError("Pieza de reporte inválida")
    if pieza == "ejecutivo":
        # Página 1 para quien decide (consultas al área), su detalle y un anexo técnico breve.
        return "\n".join(lineas(informe, hallazgos))
    detalle=_detalle_reporte_markdown(informe,hallazgos,incluir_triangulacion,incluir_devolucion,incluir_detalle_modelos)
    from services.semantica_excel import markdown, presentar_cobertura
    detalle += markdown(presentar_cobertura(getattr(getattr(informe,"devolucion",None),"cobertura",None)).get("exploracion_semantica"))
    from services.casos_revision import agrupar
    r=agrupar(hallazgos)
    if pieza == "anexo":
        return _encabezar_consulta("\n".join(["# Anexo técnico", ""] + anexo_contexto(hallazgos) + ["", "## Registro técnico de la corrida", "La evidencia y los textos originales de la corrida se conservan a continuación; la prioridad de presentación puede diferir de la severidad histórica.", "", detalle]), informe, hallazgos)
    if r["senales_tecnicas"] <= 20 and not any(c["related_findings"] for c in r["casos"]):
        return _encabezar_consulta(detalle, informe, hallazgos)
    return '\n'.join(lineas(informe,hallazgos)+['<!-- salto-pagina -->','## Anexo técnico completo','']+anexo_contexto(hallazgos)+['',detalle])
