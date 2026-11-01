"""Arma el mensaje directo y comprensible que se le muestra primero al
responsable de decisión, antes de preguntarle si quiere escalar algo."""
from __future__ import annotations

from services import guardrails, lectura_temporal, plural

ORDEN_LENTES = ("conciliador", "ajedrecista", "cronista", "orquesta", "radiologo", "rizoma", "matematico")
NOMBRE_LENTE = {
    "ajedrecista": "Ajedrecista",
    "conciliador": "Conciliador",
    "cronista": "Cronista",
    "orquesta": "Orquesta",
    "radiologo": "Radiólogo",
    "rizoma": "Rizoma",
    "matematico": "Matemático",
}


def _prioridad(h: dict) -> str:
    from services.casos_revision import es_nota, prioridad

    # Una nota de alcance nunca representa a su lente.
    return "nota" if es_nota(h) else prioridad(h)


def _hallazgo_representativo(hallazgos: list[dict]) -> dict:
    return sorted(
        hallazgos,
        key=lambda h: ({"alta": 0, "media": 1, "baja": 2}.get(_prioridad(h), 3), -lectura_temporal.intensidad(h) if lectura_temporal.anual(h) else 0),
    )[0]


def _modo_uso(informe) -> str:
    saneamiento = getattr(informe, "saneamiento", None) or {}
    if isinstance(saneamiento, dict):
        return saneamiento.get("modo_uso_multilente") or saneamiento.get("opciones_tecnicas", {}).get("modo_uso_multilente") or "revision_final"
    return "revision_final"


def _orientacion_analisis(informe) -> str:
    saneamiento = getattr(informe, "saneamiento", None) or {}
    if not isinstance(saneamiento, dict):
        return ""
    opciones = saneamiento.get("opciones_tecnicas")
    opciones = opciones if isinstance(opciones, dict) else {}
    valor = saneamiento.get("orientacion_analisis") or opciones.get("orientacion_analisis")
    return str(valor or "").strip()


def _controles_solicitados(informe) -> list[dict]:
    saneamiento = getattr(informe, "saneamiento", None) or {}
    if not isinstance(saneamiento, dict):
        return []
    bloque = saneamiento.get("controles_solicitados")
    if not isinstance(bloque, dict):
        return []
    return [item for item in (bloque.get("controles") or []) if isinstance(item, dict)]


def lineas_ia(consolidado: dict | None) -> list[str]:
    """Lectura con IA: estado de cada modelo, priorización «k de n» y lecturas atribuidas o descartadas.

    Nunca dice «varios modelos coincidieron»: cada señal se cuenta sobre los modelos que efectivamente
    la recibieron, y cada lectura se atribuye a su modelo.
    """
    consolidado = consolidado or {}
    out: list[str] = []
    if consolidado.get("linea_estado"):
        out.append("\n" + str(consolidado["linea_estado"]))
    if consolidado.get("coincidencias"):
        out.append("\nPriorización coincidente (k de n modelos que recibieron la señal; no es una votación ni una certeza):")
        out.extend(f"- {c}" for c in consolidado["coincidencias"])
    if consolidado.get("divergencias"):
        out.append("\nPriorización sin acuerdo entre los modelos que recibieron la señal (se muestra sin resolverla por votación):")
        out.extend(f"- {d}" for d in consolidado["divergencias"])
    if consolidado.get("priorizacion_sin_contraste"):
        out.append("\nPriorizadas por un solo modelo, sin otro que las haya recibido para contrastar:")
        out.extend(f"- {d}" for d in consolidado["priorizacion_sin_contraste"])
    if consolidado.get("respaldo_no_independiente"):
        out.append("- El modelo de respaldo no cuenta como coincidencia independiente.")
    lecturas = [
        hs.get("lectura_atribuida") or (f"{hs.get('modelo')}: {hs['lectura']}" if hs.get("modelo") else hs["lectura"])
        for hs in consolidado.get("hallazgos_singulares", [])
        if hs.get("lectura") or hs.get("lectura_atribuida")
    ]
    if lecturas:
        out.append("\nLectura en lenguaje llano (cada una atribuida a su modelo):")
        out.extend(f"- {lectura}" for lectura in lecturas)
    descartadas = consolidado.get("lecturas_descartadas") or []
    if descartadas:
        out.append("\nLecturas descartadas (no se usan en este resultado):")
        for d in descartadas:
            rol = d.get("rol")
            out.append(f"- {d.get('modelo')}{' (' + rol + ')' if rol in {'principal', 'respaldo'} else ''}: "
                       + ("; ".join(map(str, d.get("motivos") or [])) or "motivo no informado") + ".")
    return out


def armar_mensaje(hallazgos: list[dict], consolidado: dict, informe=None, cobertura=None) -> tuple[str, bool]:
    modo_uso = _modo_uso(informe)
    orientacion = _orientacion_analisis(informe)
    if not hallazgos:
        mensaje = (
            "Se hizo un barrido adicional sobre esta información con las lentes "
            "disponibles y no se encontró nada que amerite atención. "
            "Esto no garantiza que no haya nada. Si el informe todavía está en elaboración, esta lectura también puede servir para confirmar que los datos, comparaciones, hojas de controles o metodología, reglas y límites están suficientemente documentados antes de cerrar la versión. El barrido se hizo con "
            "método y quedó registrado."
        )
        if (consolidado or {}).get("linea_estado"):
            mensaje += "\n\n" + str(consolidado["linea_estado"])
        return mensaje, False

    por_lente: dict[str, list[dict]] = {}
    for h in hallazgos:
        por_lente.setdefault(h.get("lente", "sin_lente"), []).append(h)

    if modo_uso == "informe_en_construccion":
        apertura = "Según la lectura multilente realizada, estas señales funcionan como asistencia metodológica mientras el informe se construye. Usalas para mejorar datos, comparaciones, hojas de controles o metodología, reglas explícitas, evidencia y trazabilidad antes de cerrar una versión:"
    else:
        apertura = "Según la lectura multilente realizada, conviene ordenar estas preguntas antes de decidir. Si el informe todavía está en construcción, usalas también como guía para mejorar datos, comparaciones, hojas de controles o metodología, reglas explícitas, evidencia y trazabilidad antes de cerrarlo:"
    lineas = [apertura]
    temporal = lectura_temporal.resumen(hallazgos)
    if temporal:
        lineas.append(f"\n{plural.contar(temporal['cantidad'], 'señal anual', 'señales anuales')} para contextualizar y "
                      f"{plural.contar(temporal['otras_senales'], 'señal', 'señales')} de otros controles. No equivalen a ese número de errores.")
        lineas.append("Revisar primero el contexto compartido por período, unidad, cobertura y metodología; si son importes en moneda corriente, distinguir crecimiento nominal y real.")
    if orientacion:
        lineas.extend([
            "\nOrientación propuesta por la persona:",
            f"- {guardrails.sanitizar_texto(orientacion)}",
            "- Esta orientación ayuda a priorizar y contrastar la lectura, pero no limita el barrido abierto de las lentes.",
        ])
    controles_solicitados = _controles_solicitados(informe)
    if controles_solicitados:
        lineas.append("\nRespuesta a los controles pedidos:")
        lineas.extend(
            f"- {control.get('nombre')}: {control.get('resultado')}"
            for control in controles_solicitados
        )
    lineas.append("\nLectura multilente:")
    mostrados = set()
    for lente in ORDEN_LENTES:
        items = por_lente.get(lente, [])
        nombre = NOMBRE_LENTE[lente]
        if items:
            h = _hallazgo_representativo(items)
            mostrados.add(id(h))
            extra = "" if len(items) == 1 else f" (+{len(items) - 1} más)"
            lineas.append(f"- {nombre}: {h['descripcion']}{extra}")
        else:
            control = next((c for c in (cobertura or {}).get("lentes", []) if c.get("lente") == lente), {})
            if control.get("estado") in {"no_aplicable", "no_evaluable"}:
                lineas.append(f"- {nombre}: {control['estado'].replace('_', ' ')}. {control.get('motivo', '')}")
            else:
                lineas.append(f"- {nombre}: sin señales comunicables en este informe.")

    from services.casos_revision import prioridad

    alta_no_mostrada = [
        h for h in hallazgos if prioridad(h) == "alta" and id(h) not in mostrados
    ]
    if alta_no_mostrada:
        lineas.append("\nOtros puntos de prioridad alta:")
        for h in alta_no_mostrada[:4]:
            lineas.append(f"- {h['descripcion']}")

    lineas.extend(lineas_ia(consolidado))


    preguntas = [h.get("pregunta_institucional") for h in hallazgos if h.get("pregunta_institucional")]
    if preguntas:
        lineas.append("\nPregunta institucional inicial:")
        lineas.append(f"- {guardrails.sanitizar_texto(preguntas[0])}")

    lineas.append(
        "\nDecisión humana disponible: pedir contexto, dejar en seguimiento, "
        "cerrar por explicación suficiente o escalar formalmente. Cualquiera "
        "de esas decisiones queda registrada."
    )
    return "\n".join(lineas), True
