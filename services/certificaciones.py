"""Reglas determinísticas para protocolos B-1 y R-1.

La IA puede aportar señales y explicaciones, pero nunca emite el sello. Este
módulo calcula hashes, sugiere estados iniciales y aplica las condiciones
objetivas previas a la decisión humana de emisión.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import models
from services.lens_matrix import LENS_MATRIX

LENTES_POR_CONTROL_B1 = {
    "B1-04": {"ajedrecista"},
    "B1-05": {"cronista"},
    "B1-06": {"matematico"},
    "B1-07": {"orquesta", "radiologo", "rizoma"},
}

# Texto visible para la persona que decide -- nunca "aprobado por IA". El
# valor interno de `EvaluacionCertificacion.estado` no cambia: solo cambia lo
# que se muestra. Usado por la API pública, la exportación markdown y (vía el
# mismo texto) por el frontend.
ESTADOS_VISIBLES: dict[str, str] = {
    "en_revision": "En revisión",
    "con_observaciones": "Con observaciones",
    "lista_para_emision": "Apto para instancia humana de decisión",
    "sellada": "Sellada",
    "reemplazada": "Reemplazada",
}


def estado_visible(estado: str) -> str:
    return ESTADOS_VISIBLES.get(estado, (estado or "-").replace("_", " ").capitalize())


DECLARACION_SELLO = (
    "Esta constancia acredita que el objeto identificado atravesó el Protocolo de "
    "Gobernanza Multilente indicado, bajo controles estandarizados, evidencia "
    "trazable y decisión humana. No certifica verdad absoluta, ausencia total de "
    "errores, validez jurídica ni reemplaza la responsabilidad de quien decide."
)

EXCLUSIONES_BASE = {
    "B-1": [
        "No constituye dictamen jurídico ni certifica validez legal.",
        "No sustituye auditoría contable ni pericia forense documental.",
        "No contrasta bases externas salvo que un control lo registre expresamente.",
        "No garantiza verdad absoluta ni ausencia total de errores.",
    ],
    "R-1": [
        "No autoriza la contratación, adquisición ni puesta en producción del sistema.",
        "No sustituye evaluaciones jurídicas, de seguridad, privacidad o impacto que resulten exigibles.",
        "No garantiza el desempeño futuro del proyecto ni del modelo de IA.",
    ],
}


def exclusiones_completas(codigo: str, adicionales: list[str] | None = None) -> list[str]:
    salida: list[str] = []
    for item in [*EXCLUSIONES_BASE.get(codigo, []), *(adicionales or [])]:
        limpio = str(item).strip()
        if limpio and limpio not in salida:
            salida.append(limpio)
    return salida


def matriz_versionada(protocolo: object) -> list[dict[str, Any]]:
    """La evaluación lee la matriz congelada en su versión de protocolo."""
    snapshot = getattr(protocolo, "matriz_lentes", None) or []
    return list(snapshot) if snapshot else list(LENS_MATRIX)


def perfiles_control_versionados(protocolo: object, codigo: str, lente_declarada: str | None = None) -> list[dict[str, Any]]:
    ids = {
        "B1-04": ("ajedrecista",), "B1-05": ("cronista",),
        "B1-06": ("matematico",), "B1-07": ("orquesta", "radiologo", "rizoma"),
        "B1-08": ("conciliador",),
    }.get(codigo, (lente_declarada,) if lente_declarada else ())
    por_id = {item["id"]: item for item in matriz_versionada(protocolo)}
    if (getattr(protocolo, "model_policy", None) or {}).get("excluir_resultados_exploratorios"):
        ids = tuple(item for item in ids if item != "rizoma")
    return [por_id[item] for item in ids if item in por_id]


def hallazgos_institucionales(informe: object, protocolo: object) -> list:
    hallazgos = list(getattr(informe, "hallazgos", None) or [])
    if not (getattr(protocolo, "model_policy", None) or {}).get("excluir_resultados_exploratorios"):
        return hallazgos  # Las versiones históricas mantienen su interpretación.
    return [h for h in hallazgos if not (
        h.lente == "rizoma" or getattr(h, "modo", None) == "exploratorio"
        or getattr(h, "tipo_evidencia", None) == "ASOCIACION_EXPLORATORIA"
        or (h.evidencia or {}).get("naturaleza") == "exploratoria"
    )]

# Proveedor visible de cada identificador lógico de modelo usado en la
# triangulación (ver services/triangulacion.py). No es una versión de API:
# ver `limite_declarado` en model_policy de cada protocolo.
PROVEEDORES_MODELO: dict[str, str] = {
    "claude": "Anthropic",
    "gpt": "OpenAI",
    "gemini": "Google",
    "deepseek": "DeepSeek",
    "renderix": "Renderix",
    "llama": "Ollama / autoalojado",
}


def _hash_canonico(payload: Any) -> str:
    serializado = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def snapshot_informe(informe: models.Informe) -> tuple[dict[str, Any], str]:
    objeto = {
        "tipo": "informe",
        "id": informe.id,
        "area_id": informe.area_id,
        "periodo": informe.periodo,
        "dominio": informe.dominio,
        "modo": informe.modo,
        "datos": informe.datos or [],
        "saneamiento": informe.saneamiento or {},
    }
    huella = _hash_canonico(objeto)
    snapshot = {k: v for k, v in objeto.items() if k != "datos"}
    snapshot["filas"] = len(informe.datos or [])
    snapshot["hash_datos"] = _hash_canonico(informe.datos or [])
    return snapshot, huella


def snapshot_proyecto(proyecto: models.ProyectoIA) -> tuple[dict[str, Any], str]:
    objeto = {
        "tipo": "proyecto_ia",
        "id": proyecto.id,
        "titulo": proyecto.titulo,
        "organismo_area": proyecto.organismo_area,
        "situacion": proyecto.situacion,
        "estado": proyecto.estado,
        "entrega_final": proyecto.entrega_final,
        "retro_docente": proyecto.retro_docente,
    }
    return objeto, _hash_canonico(objeto)


def estado_inicial_b1(control: models.DefinicionControl, informe: models.Informe) -> str:
    """Sugiere un estado conservador a partir de evidencia ya existente.

    Una ausencia de hallazgos solo cuenta como conforme cuando la cobertura
    registra que la lente corrió. Los controles que requieren juicio humano
    permanecen no evaluables u observados.
    """
    if not informe.devolucion:
        return "no_evaluable"
    protocolo = getattr(control, "protocolo", None)
    hallazgos = hallazgos_institucionales(informe, protocolo)
    cobertura = informe.devolucion.cobertura or {}
    condiciones = cobertura.get("condiciones_validez") or {}
    if condiciones.get("puede_concluir") is False:
        return "no_evaluable"
    lentes_ejecutadas = {
        str(item.get("lente"))
        for item in cobertura.get("lentes", [])
        if isinstance(item, dict) and item.get("lente") and item.get("ejecutado", True)
        and item.get("estado") not in {"no_evaluable", "no_aplicable"}
    }
    codigo = control.codigo
    if codigo == "B1-01":
        return "conforme"
    if codigo == "B1-02":
        pdf = cobertura.get("pdf") or {}
        return "no_evaluable" if pdf.get("truncado_por_paginas") else "conforme"
    if codigo == "B1-03":
        return "conforme" if all(bool(h.evidencia) for h in hallazgos) else "observado"
    if codigo in LENTES_POR_CONTROL_B1:
        lentes = {p["id"] for p in perfiles_control_versionados(protocolo, codigo)}
        if any(h.lente in lentes for h in hallazgos):
            return "observado"
        return "conforme" if lentes & lentes_ejecutadas else "no_evaluable"
    if codigo == "B1-08":
        return "conforme" if cobertura else "no_evaluable"
    if codigo == "B1-09":
        return "observado" if hallazgos else "conforme"
    if codigo == "B1-10":
        decision = informe.devolucion.decision
        return "conforme" if decision and decision.tipo_decision == "cerrar" else "no_evaluable"
    return "no_evaluable"


def evidencia_inicial_b1(control: models.DefinicionControl, informe: models.Informe) -> dict[str, str] | None:
    estado = estado_inicial_b1(control, informe)
    if estado == "no_evaluable":
        return None
    protocolo = getattr(control, "protocolo", None)
    hallazgos = hallazgos_institucionales(informe, protocolo)
    por_lente = {p["id"] for p in perfiles_control_versionados(protocolo, control.codigo)} if control.codigo in LENTES_POR_CONTROL_B1 else set()
    ids = [str(h.id) for h in hallazgos if not por_lente or h.lente in por_lente]
    referencias = f"hallazgos:{','.join(ids)}" if ids else f"informe:{informe.id}"
    descripciones = {
        "B1-01": "Metadatos, alcance agregado y contexto del informe registrados.",
        "B1-02": "Cobertura de lectura y disponibilidad del material registradas por el análisis.",
        "B1-03": "Evidencias estructuradas de los hallazgos verificadas.",
        "B1-08": "Cobertura, exclusiones y límites globales conservados en la devolución.",
        "B1-09": "El análisis no produjo observaciones abiertas." if not hallazgos else "Existen observaciones que requieren respuesta y reevaluación.",
        "B1-10": "Decisión humana de cierre por explicación suficiente registrada.",
    }
    descripcion = descripciones.get(
        control.codigo,
        "Resultado inicial derivado de la cobertura y las señales del análisis multilente.",
    )
    from services.proveniencia import evidencia_origen
    return {"tipo": "analisis_multilente", "descripcion": descripcion, "referencia": referencias,
            "metadata_evidencia": {"proveniencia": evidencia_origen({}, informe)}}


def construir_manifiesto_modelos(informe: models.Informe | None) -> list[dict[str, Any]]:
    """Registra qué modelos de IA intervinieron realmente sobre este informe.

    Se basa en `InterpretacionModelo`, el registro de ejecución real (no en el
    resumen público `modelos_consultados`), para poder comprobar el
    cumplimiento de la `model_policy` de la versión del protocolo. El
    identificador de versión proviene de la respuesta efectiva del proveedor
    cuando su API lo informa; si no está disponible, el manifiesto lo declara
    expresamente en lugar de inferirlo.
    """
    if informe is None:
        return []
    lentes_con_hallazgos = sorted({h.lente for h in (informe.hallazgos or [])})
    controles = sorted(
        codigo
        for codigo, lentes in LENTES_POR_CONTROL_B1.items()
        if lentes & set(lentes_con_hallazgos)
    )
    manifiesto: list[dict[str, Any]] = []
    for interpretacion in getattr(informe, "interpretaciones", None) or []:
        manifiesto.append(
            {
                "modelo": interpretacion.modelo,
                "proveedor": PROVEEDORES_MODELO.get(interpretacion.modelo, "no registrado"),
                "identificador_version": getattr(interpretacion, "identificador_version", None) or "no informado por el proveedor",
                "respondio": interpretacion.error is None,
                "error": interpretacion.error,
                "fecha": interpretacion.creado_en.isoformat() if interpretacion.creado_en else None,
                "controles": controles,
                "lentes": lentes_con_hallazgos,
                "configuracion": {
                    "modo": "interpretacion_triangulada",
                    "entrada": "hallazgos_estructurados_del_informe",
                },
            }
        )
    return manifiesto


def motivos_incumplimiento_model_policy(
    protocolo: models.VersionProtocolo, manifiesto: list[dict[str, Any]] | None
) -> list[str]:
    """Compara la ejecución real (manifiesto) contra la `model_policy` fijada
    en la versión del protocolo. Dos evaluaciones bajo la misma versión deben
    cumplir la misma política mínima -- si no la cumple, el sello no puede
    emitirse (ver motivos_bloqueo)."""
    politica = getattr(protocolo, "model_policy", None) or {}
    if not politica.get("aplica", False):
        return []
    manifiesto = manifiesto or []
    motivos: list[str] = []
    respondieron = [item for item in manifiesto if item.get("respondio")]
    minimos = int(politica.get("modelos_minimos_con_respuesta", 0) or 0)
    if len(respondieron) < minimos:
        motivos.append(
            f"la política de modelos de {protocolo.codigo} v{protocolo.version} exige al menos "
            f"{minimos} modelos con respuesta válida; el manifiesto registra {len(respondieron)}"
        )
    habilitados = set(politica.get("modelos_habilitados") or [])
    if habilitados:
        no_habilitados = sorted({item["modelo"] for item in manifiesto if item.get("modelo") not in habilitados})
        if no_habilitados:
            motivos.append(
                "intervinieron modelos fuera de la política habilitada: " + ", ".join(no_habilitados)
            )
    # El contraste multimodelo exigido para controles específicos (p.ej.
    # B1-06/B1-07) se valida en motivos_bloqueo(), que sí tiene acceso a los
    # resultados de la evaluación concreta -- esta función solo compara el
    # manifiesto contra la política global (mínimos y modelos habilitados).
    return motivos


def motivos_bloqueo(evaluacion: models.EvaluacionCertificacion, hash_actual: str) -> list[str]:
    motivos: list[str] = []
    if evaluacion.hash_objeto != hash_actual:
        motivos.append("el objeto cambió desde que comenzó la evaluación")
    if not evaluacion.resultados:
        motivos.append("la evaluación no tiene controles")
        return motivos
    aplicables = [r for r in evaluacion.resultados if r.aplica]
    if not aplicables:
        motivos.append("ningún control quedó aplicable; no puede emitirse una constancia vacía")
    for resultado in evaluacion.resultados:
        control = resultado.control
        etiqueta = f"{control.codigo} {control.nombre}"
        if not resultado.aplica:
            if getattr(control, "obligatorio", False):
                motivos.append(f"{etiqueta}: es obligatorio y no puede marcarse como no aplicable")
            if not (resultado.justificacion_aplicabilidad or "").strip():
                motivos.append(f"{etiqueta}: falta justificar por qué no aplica")
            continue
        if resultado.estado != "conforme":
            motivos.append(f"{etiqueta}: permanece {resultado.estado}")
        if resultado.estado == "conforme" and not resultado.evidencias:
            motivos.append(f"{etiqueta}: falta evidencia")
        if hasattr(resultado, "revisado_por_id") and resultado.revisado_por_id is None:
            motivos.append(f"{etiqueta}: falta revisión humana explícita")
        if any(es_evidencia_exploratoria(e) for e in resultado.evidencias or []):
            motivos.append(f"{etiqueta}: una hipótesis exploratoria no es evidencia institucional")
    protocolo = getattr(evaluacion, "protocolo", None)
    manifiesto = getattr(evaluacion, "manifiesto_modelos", None) or []
    if protocolo is not None:
        if getattr(protocolo, "codigo", None) == "R-1":
            conclusion = getattr(evaluacion, "conclusion_r1", None)
            if not conclusion:
                motivos.append("R-1 requiere una conclusión humana explícita sobre la necesidad de IA")
            elif conclusion == "informacion_insuficiente":
                motivos.append("R-1 concluyó que la información es insuficiente; debe completarse antes de emitir")
        controles_con_contraste = set(
            (getattr(protocolo, "model_policy", None) or {}).get("controles_con_contraste_obligatorio", []) or []
        )
        if controles_con_contraste:
            aplicables_con_contraste = [
                r for r in evaluacion.resultados if r.aplica and r.control.codigo in controles_con_contraste
            ]
            if aplicables_con_contraste:
                respondieron = sum(1 for item in manifiesto if item.get("respondio"))
                if respondieron < 2:
                    controles_txt = ", ".join(sorted(r.control.codigo for r in aplicables_con_contraste))
                    motivos.append(
                        f"los controles {controles_txt} exigen contraste entre al menos dos modelos y el "
                        f"manifiesto registra {respondieron} con respuesta"
                    )
        motivos.extend(motivos_incumplimiento_model_policy(protocolo, manifiesto))
    return motivos


def responsables_que_revisaron(evaluacion: models.EvaluacionCertificacion) -> set[int]:
    """Identidades humanas que dejaron una revisión trazable en los controles."""
    responsables: set[int] = set()
    for resultado in getattr(evaluacion, "resultados", None) or []:
        revisado_por_id = getattr(resultado, "revisado_por_id", None)
        if revisado_por_id is not None:
            responsables.add(int(revisado_por_id))
        for cambio in getattr(resultado, "historial", None) or []:
            modificado_por_id = getattr(cambio, "modificado_por_id", None)
            if modificado_por_id is not None:
                responsables.add(int(modificado_por_id))
    return responsables


def es_evidencia_exploratoria(evidencia) -> bool:
    """Rechaza referencias tipadas a hipótesis; no valida el contenido de textos libres."""
    def buscar(valor):
        if isinstance(valor, dict):
            return any(str(k).lower() in {"hipotesis_id", "hipotesis_exploratoria_id"} or buscar(v) for k, v in valor.items())
        if isinstance(valor, list):
            return any(buscar(v) for v in valor)
        return isinstance(valor, str) and ("exploratori" in valor.lower() or valor.lower().startswith("hipotesis:") or valor == "HIPOTESIS_NO_VALIDADA")
    return buscar(getattr(evidencia, "tipo", "")) or buscar(getattr(evidencia, "referencia", "")) or buscar(getattr(evidencia, "metadata_evidencia", None))


def motivos_separacion_emisor(
    evaluacion: models.EvaluacionCertificacion, emisor_id: int
) -> list[str]:
    """Impide que una única persona revise y emita la misma constancia."""
    responsables = responsables_que_revisaron(evaluacion)
    if not responsables:
        return ["no hay una revisión humana identificada en los controles"]
    if responsables == {int(emisor_id)}:
        return [
            "la persona que emite no puede ser la única que revisó los controles; "
            "se requiere la intervención trazable de un segundo responsable"
        ]
    return []


def resumen_para_concluir(evaluacion: models.EvaluacionCertificacion, hash_actual: str) -> list[str]:
    """Consolida, sin duplicados, qué falta para poder concluir la
    evaluación. Reusa motivos_bloqueo() -- son la misma condición objetiva,
    mirada desde "qué falta" en vez de "por qué está bloqueada" -- salvo el
    cambio de objeto, que no se resuelve completando información sino
    iniciando una evaluación nueva."""
    motivos = [m for m in motivos_bloqueo(evaluacion, hash_actual) if "el objeto cambió" not in m]
    if len(responsables_que_revisaron(evaluacion)) <= 1:
        motivos.append(
            "la emisión requiere que un segundo responsable distinto de quien registró "
            "los resultados intervenga en la emisión"
        )
    return list(dict.fromkeys(motivos))


def anexos_lentes(evaluacion: models.EvaluacionCertificacion) -> list[dict[str, Any]]:
    """Construye los siete anexos autónomos, uno por lente, con estructura
    idéntica. Las preguntas, evidencia mínima y límites salen siempre de
    `LENS_MATRIX` -- nunca se hardcodean acá. Un mismo control (p.ej. B1-07)
    alimenta varios anexos de forma independiente. Solo aplica al protocolo
    B-1 (tipo_objeto == "informe"): R-1 evalúa condiciones de un proyecto de
    IA y no corre lentes."""
    if getattr(evaluacion.protocolo, "tipo_objeto", None) != "informe":
        return []
    informe = evaluacion.informe
    hallazgos = hallazgos_institucionales(informe, evaluacion.protocolo) if informe else []
    resultados = list(evaluacion.resultados or [])
    anexos: list[dict[str, Any]] = []
    for lente in matriz_versionada(evaluacion.protocolo):
        lente_id = lente["id"]
        controles_lente = [
            r
            for r in resultados
            if lente_id in {p["id"] for p in perfiles_control_versionados(evaluacion.protocolo, r.control.codigo, getattr(r.control, "lente", None))}
        ]
        hallazgos_lente = [h for h in hallazgos if h.lente == lente_id]
        aplicables = [r for r in controles_lente if r.aplica]
        evidencias = [e for r in controles_lente for e in (r.evidencias or [])]
        if not controles_lente:
            anexos.append({
                "lente": lente_id,
                "nombre": lente["nombre"],
                "pregunta_central": lente["pregunta_central"],
                "preguntas": lente["preguntas"],
                "evidencia_minima": lente["evidencia_minima"],
                "controles_ejecutados": [],
                "evidencia_utilizada": [],
                "hallazgos": [h.descripcion for h in hallazgos_lente],
                "informacion_faltante": [],
                "estado": "no_aplicable",
                "observaciones": [],
                "accion_requerida": [],
                "reevaluacion": None,
                "limites": lente["limites"],
                "justificacion_no_aplicable": (
                    "Ningún control de esta versión del protocolo está vinculado a esta lente."
                ),
            })
            continue
        estados_aplicables = {r.estado for r in aplicables}
        if not aplicables:
            estado_lente = "no_aplicable"
        elif "observado" in estados_aplicables:
            estado_lente = "observado"
        elif "no_evaluable" in estados_aplicables:
            estado_lente = "no_evaluable"
        else:
            estado_lente = "conforme"
        justificacion_na = None
        if estado_lente == "no_aplicable":
            justificaciones = [
                r.justificacion_aplicabilidad for r in controles_lente if not r.aplica and r.justificacion_aplicabilidad
            ]
            justificacion_na = "; ".join(justificaciones) if justificaciones else (
                "Los controles vinculados a esta lente fueron marcados no aplicables sin justificación registrada."
            )
        anexos.append({
            "lente": lente_id,
            "nombre": lente["nombre"],
            "pregunta_central": lente["pregunta_central"],
            "preguntas": lente["preguntas"],
            "evidencia_minima": lente["evidencia_minima"],
            "controles_ejecutados": [r.control.codigo for r in controles_lente],
            "evidencia_utilizada": [e.descripcion for e in evidencias],
            "hallazgos": [h.descripcion for h in hallazgos_lente],
            "informacion_faltante": [
                f"{r.control.codigo}: {', '.join(lente['evidencia_minima'])}"
                for r in controles_lente
                if r.estado == "no_evaluable"
            ],
            "estado": estado_lente,
            "observaciones": [r.observacion for r in controles_lente if r.observacion],
            "accion_requerida": [r.accion_requerida for r in controles_lente if r.accion_requerida],
            "reevaluacion": max(
                (r.reevaluado_en for r in controles_lente if r.reevaluado_en), default=None
            ),
            "limites": lente["limites"],
            "justificacion_no_aplicable": justificacion_na,
        })
    return anexos


def anexos_lentes_publicos(evaluacion: models.EvaluacionCertificacion) -> list[dict[str, Any]]:
    """Proyección pública mínima: demuestra el procedimiento sin publicar
    evidencia, hallazgos, observaciones ni otros textos libres del caso."""
    if getattr(evaluacion.protocolo, "tipo_objeto", None) != "informe":
        return []
    resultados = list(evaluacion.resultados or [])
    salida = []
    for lente in matriz_versionada(evaluacion.protocolo):
        lente_id = lente["id"]
        controles = [
            resultado for resultado in resultados
            if lente_id in {
                perfil["id"] for perfil in perfiles_control_versionados(
                    evaluacion.protocolo, resultado.control.codigo,
                    getattr(resultado.control, "lente", None),
                )
            }
        ]
        aplicables = [resultado for resultado in controles if resultado.aplica]
        estados = {resultado.estado for resultado in aplicables}
        if not controles or not aplicables:
            estado = "no_aplicable"
        elif "observado" in estados:
            estado = "observado"
        elif "no_evaluable" in estados:
            estado = "no_evaluable"
        else:
            estado = "conforme"
        salida.append({
            "lente": lente_id,
            "nombre": lente["nombre"],
            "pregunta_central": lente["pregunta_central"],
            "preguntas": lente["preguntas"],
            "controles_ejecutados": [resultado.control.codigo for resultado in controles],
            "estado": estado,
            "reevaluacion": max(
                (resultado.reevaluado_en for resultado in controles if resultado.reevaluado_en),
                default=None,
            ),
        })
    return salida


def ultima_revision(evaluacion: models.EvaluacionCertificacion):
    fechas = []
    for resultado in getattr(evaluacion, "resultados", None) or []:
        if getattr(resultado, "reevaluado_en", None):
            fechas.append(resultado.reevaluado_en)
        fechas.extend(
            cambio.creado_en for cambio in (getattr(resultado, "historial", None) or [])
            if getattr(cambio, "creado_en", None)
        )
    return max(fechas, default=getattr(evaluacion, "reevaluado_en", None))


def construir_reporte_evaluacion(evaluacion: models.EvaluacionCertificacion, hash_actual: str) -> dict[str, Any]:
    """Lectura única de una evaluación: la misma estructura alimenta la API,
    la exportación markdown y (a través de los mismos campos) la pantalla
    final. Un solo lugar de verdad evita que dos superficies muestren
    resultados distintos para la misma evaluación."""
    resultados = list(evaluacion.resultados or [])
    aplicables = [r for r in resultados if r.aplica]
    sello = getattr(evaluacion, "sello", None)
    protocolo = evaluacion.protocolo
    manifiesto = getattr(evaluacion, "manifiesto_modelos", None) or []
    return {
        "protocolo_codigo": protocolo.codigo,
        "protocolo_version": protocolo.version,
        "protocolo_nombre": protocolo.nombre,
        "estado_interno": evaluacion.estado,
        "estado_visible": estado_visible(evaluacion.estado),
        "hash_objeto": evaluacion.hash_objeto,
        "hash_vigente": evaluacion.hash_objeto == hash_actual,
        "creado_en": evaluacion.creado_en,
        "reevaluado_en": evaluacion.reevaluado_en,
        "controles": {
            "totales": len(resultados),
            "conformes": sum(1 for r in aplicables if r.estado == "conforme"),
            "observados": sum(1 for r in aplicables if r.estado == "observado"),
            "no_evaluables": sum(1 for r in aplicables if r.estado == "no_evaluable"),
            "no_aplicables": sum(1 for r in resultados if not r.aplica),
        },
        "anexos_lentes": anexos_lentes(evaluacion),
        "para_concluir": resumen_para_concluir(evaluacion, hash_actual),
        "manifiesto_modelos": manifiesto,
        "model_policy": getattr(protocolo, "model_policy", None) or {},
        "matriz_lentes_hash": _hash_canonico(matriz_versionada(protocolo)),
        "model_policy_cumplida": not motivos_incumplimiento_model_policy(protocolo, manifiesto),
        "conclusion_r1": getattr(evaluacion, "conclusion_r1", None),
        "fundamento_conclusion_r1": getattr(evaluacion, "fundamento_conclusion_r1", None),
        "sello": None if not sello else {
            "identificador_publico": sello.identificador_publico,
            "estado": sello.estado,
            "emitido_en": sello.emitido_en,
            "emitido_por": getattr(sello.emitido_por, "nombre", None),
            "alcance_del_analisis": sello.resumen_alcance,
            "analisis_excluidos": list(sello.limitaciones or []),
            "declaracion": DECLARACION_SELLO,
        },
    }


def estado_evaluacion(evaluacion: models.EvaluacionCertificacion) -> str:
    """Deriva el estado visible a partir de los mismos criterios que usa
    motivos_bloqueo() para permitir la emision -- evita que ambos calculos
    diverjan (p.ej. una evaluacion donde TODOS los controles quedaron no
    aplicables y justificados es emitible, y por lo tanto no puede quedar
    mostrada como "en_revision")."""
    if not evaluacion.resultados:
        return "en_revision"
    aplicables = [r for r in evaluacion.resultados if r.aplica]
    if not aplicables:
        return "en_revision"
    if any(not r.aplica and getattr(r.control, "obligatorio", False) for r in evaluacion.resultados):
        return "en_revision"
    if any(r.estado == "observado" for r in aplicables):
        return "con_observaciones"
    if any(r.estado == "no_evaluable" for r in aplicables):
        return "en_revision"
    if any(not r.aplica and not (r.justificacion_aplicabilidad or "").strip() for r in evaluacion.resultados):
        return "en_revision"
    if all(r.estado == "conforme" and bool(r.evidencias) for r in aplicables):
        if getattr(getattr(evaluacion, "protocolo", None), "codigo", None) == "R-1":
            if getattr(evaluacion, "conclusion_r1", None) in (None, "", "informacion_insuficiente"):
                return "en_revision"
        return "lista_para_emision"
    return "en_revision"
