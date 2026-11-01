"""Síntesis acotada de revisión; el anexo conserva la evidencia íntegra."""

import re
from collections import Counter

from services.casos_revision import agrupar
from services.plural import contar, senales  # noqa: F401  (senales se reexporta: ya la importan otros módulos)

# Al final de cada caso del PDF: el PDF es lo que la gente se lleva, y la respuesta se da en la aplicación.
INVITACION_RESPUESTA_PDF = "Respondé en la aplicación: ¿qué resultó ser esta señal?"


def _lente_legible(lente):
    """El nombre con el que la lente se anuncia en pantalla, no su identificador interno.

    «rizoma» o «cronista» no le dicen nada a quien lee el informe; sí le dice algo «conexiones
    exploratorias» o «evolución temporal».
    """
    from services.jobs import NOMBRES_ETAPA_LENTE

    clave = str(lente or "").strip()
    return NOMBRES_ETAPA_LENTE.get(clave) or clave.replace("_", " ").capitalize() or "—"


def _regla_legible(evidencia, lente):
    regla = str((evidencia or {}).get("regla") or "").strip()
    return regla.replace("_", " ") if regla else _lente_legible(lente)


def corto(v, n=360):
    return " ".join(str(v or "").split())


_RECHAZO = re.compile(r"hipótesis \d+ rechazada", re.I)


def relaciones_descartadas(motivos) -> tuple[int, list]:
    """Relaciones propuestas por el modelo que la validación descartó, y los demás motivos."""
    motivos = motivos if isinstance(motivos, list) else ([motivos] if motivos else [])
    rechazos = [m for m in motivos if _RECHAZO.search(str(m))]
    return len(rechazos), [m for m in motivos if not _RECHAZO.search(str(m))]


def _estado_exploracion(estrategia: dict) -> str:
    """Estado de la exploración del libro, con el motivo de la falla en lenguaje llano."""
    if estrategia.get("evaluada"):
        cubiertos, total = estrategia.get("elementos_cubiertos"), estrategia.get("elementos_totales")
        return f"completada ({cubiertos}/{total} elementos)" if total else "completada"
    descartadas, motivos = relaciones_descartadas(estrategia.get("motivos") or [])
    if descartadas and not motivos:
        # La validación descartó relaciones que citaban textos que no están en el archivo: es la
        # protección funcionando, no una falla del proveedor.
        return (f"completada parcialmente: se descartaron {contar(descartadas, 'relación', 'relaciones')} "
                "que no coincidían con el archivo")
    motivo = str(motivos[0] if motivos else "").lower()
    if "límite de llamadas" in motivo:
        # Tope de consultas de la corrida, fijado a propósito: no es una falla del proveedor.
        return ("completada parcialmente: la IA recorrió el libro dentro del límite de consultas de la corrida; "
                "parte de las comparaciones entre cuadros quedó fuera")
    if "429" in motivo or "resource_exhausted" in motivo or "quota" in motivo:
        causa = "el proveedor no tenía cuota disponible"
    elif "token" in motivo or "truncad" in motivo:
        causa = "la respuesta se cortó por límite de extensión"
    elif "esquema" in motivo or "schema" in motivo or "formato" in motivo:
        causa = "la respuesta no respetó el formato requerido"
    elif "timeout" in motivo or "timed out" in motivo or "tiempo" in motivo:
        causa = "no respondió a tiempo"
    else:
        causa = "no se completó"
    return f"no completada: {causa}"


def _ubicacion(e):
    if e.get("hoja") and e.get("celda"):
        texto = f"{e['hoja']}!{e['celda']}"
    else:
        texto = ", ".join(e.get("ubicaciones_excel") or []) or "—"
    vis = e.get("visibilidad_origen")
    if vis:
        texto += " (" + (", ".join(vis) if isinstance(vis, list) else str(vis)) + ")"
    return texto


def _proximos_pasos(r, reg):
    """Pasos que surgen de este informe: las consultas al área, lo no leído y el contexto; nunca una lista genérica."""
    from services.reportes.consultas import consultas

    pasos = []
    for n, c in enumerate(consultas(r)[:3], 1):
        donde = c["donde"].split(";")[0]
        pasos.append(f"Consulta {n} ({c['prioridad']}, {donde}): {corto(c['preguntar'])}")
    no_leidos = [p for p in reg["pendientes"] if p["tipo"] == "no_leido"]
    if no_leidos:
        pasos.append("Preparar y volver a cargar lo que no se leyó: " + "; ".join(
            (f"{p['archivo']}: " if p.get("archivo") else "") + p["donde"] for p in no_leidos[:3]) + ".")
    if reg["cruces"]["estado"] in {"no_evaluado", "sin_emparejar"} and len(reg["archivos"]) > 1:
        pasos.append("Para cruzar los archivos, conservar el archivo de origen de cada fila o cargar cuadros con rótulos equivalentes.")
    if reg["cruces"]["no_comparables"]:
        pasos.append("Si los cuadros no comparables debían compararse, cargar ediciones con el mismo concepto, unidad, corte, cobertura y moneda.")
    if r["contexto"]:
        pasos.append("Contextualizar con el área las variaciones temporales agrupadas (inflación, cobertura, metodología).")
    if not pasos:
        pasos.append("No hay casos ni pendientes de lectura: conservar este registro como constancia de lo leído y controlado. "
                     "Que no haya señales no certifica el informe.")
    return pasos


# Qué controla cada lente, dicho en llano para la línea de cobertura.
QUE_CONTROLA = {
    "ajedrecista": "sumas, signos",
    "conciliador": "escalas",
    "cronista": "períodos",
    "orquesta": "coherencia entre cuadros",
    "matematico": "fórmulas",
    "radiologo": "antecedentes comparables",
    "rizoma": "asociaciones exploratorias",
}
ORDEN_CONTROLES = ("ajedrecista", "conciliador", "cronista", "orquesta", "matematico", "radiologo", "rizoma")

DONDE_DETALLE = ("en la pantalla del informe, «Detalle técnico opcional» → «Detalle técnico PDF» "
                 "(o «Descargar Markdown» para el informe completo)")


def _fecha(informe):
    creado = getattr(informe, "creado_en", None)
    return creado.strftime("%d/%m/%Y") + " (UTC)" if hasattr(creado, "strftime") else None



def _cierres_verificados(estructura):
    """Todos los cierres comprobados: totales y componentes, subtotales de columna y, en una carga mixta, los del CSV o PDF."""
    return sum(int(estructura.get(k) or 0) for k in ("cantidad_cierres", "cierres_columna", "cierres_planos"))


def _linea_cobertura(informe, reg, resultado, excel):
    """Una línea en llano: qué se revisó, con qué controles, cuántos cierres y qué quedó afuera."""
    from services.reportes.formato import numero

    hojas, cuadros = len(excel.get("hojas") or []), len(excel.get("bloques") or [])
    if hojas:
        revisado = f"Se {'revisó' if hojas == 1 else 'revisaron'} {contar(hojas, 'hoja')}" + (f" y {contar(cuadros, 'cuadro')}" if cuadros else "")
    else:
        n = len(getattr(informe, "datos", None) or [])
        revisado = f"Se {'revisó' if n == 1 else 'revisaron'} {contar(n, 'registro')}"
    controles = sorted((c for c in reg["controles"] if c["estado"] == "ejecutado"),
                       key=lambda c: ORDEN_CONTROLES.index(c.get("control")) if c.get("control") in ORDEN_CONTROLES else 99)
    que = [x.strip() for c in controles for x in QUE_CONTROLA.get(c.get("control"), str(c.get("nombre") or "").lower()).split(",")]
    que = list(dict.fromkeys(que))
    if que:
        revisado += " con los mismos controles —" + (", ".join(que[:-1]) + " y " + que[-1] if len(que) > 1 else que[0]) + "—"
    partes = [revisado]
    cierres = _cierres_verificados(resultado["estructura"])
    if cierres:
        partes.append(f"se verificaron {numero(cierres)} cierres entre totales y componentes" if cierres != 1
                      else "se verificó 1 cierre entre un total y sus componentes")
    pendientes = reg.get("pendientes") or []
    if not pendientes and reg.get("estado") == "completo":
        partes.append("no quedaron partes sin leer")
    return "; ".join(partes) + "."


def _contenido_oculto(excel):
    """Hojas, filas o columnas ocultas que se leyeron: se dicen arriba, no sólo en el anexo."""
    partes = []
    for h in (excel or {}).get("hojas") or []:
        v = h.get("visibilidad") if isinstance(h, dict) else None
        if not v:
            continue
        cosas = []
        if v.get("estado_hoja") in {"hidden", "veryHidden"}:
            cosas.append("la hoja está oculta")
        if v.get("filas_ocultas"):
            cosas.append(f"{len(v['filas_ocultas'])} {'fila oculta' if len(v['filas_ocultas']) == 1 else 'filas ocultas'}")
        if v.get("columnas_ocultas"):
            cosas.append(f"columnas ocultas {', '.join(v['columnas_ocultas'][:5])}")
        if cosas:
            partes.append(f"hoja «{h.get('hoja')}» ({', '.join(cosas)})")
    return "; ".join(partes[:6])


def _lineas_pendientes(reg):
    """Lo no leído o no controlado, arriba y con su motivo."""
    out = []
    # Con un solo archivo, su nombre ya está en la cabecera: no se repite en cada punto.
    varios = len({p.get("archivo") for p in reg.get("pendientes") or [] if p.get("archivo")}) > 1
    for tipo, rotulo in (("no_leido", "No se leyó"), ("no_controlado", "No se controló")):
        items = [p for p in reg.get("pendientes") or [] if p["tipo"] == tipo]
        if items:
            # Mismo motivo en varios lugares: el motivo se dice una vez.
            por_motivo = {}
            for p in items[:8]:
                por_motivo.setdefault(str(p.get("motivo")), []).append(
                    (f"{p['archivo']}: " if varios and p.get("archivo") else "") + str(p["donde"]))
            out.append(f"**{rotulo}:** " + "; ".join(
                (", ".join(lugares[:-1]) + " y " + lugares[-1] if len(lugares) > 1 else lugares[0]) + f" ({motivo})"
                for motivo, lugares in por_motivo.items())
                + (f"; y {len(items) - 8} más." if len(items) > 8 else "."))
    return out


def _linea_ia(cobertura):
    """El apoyo de IA en una línea: disponible para cuántas señales, sin fallas internas detalladas."""
    ia = cobertura.get("interpretacion_ia") or {}
    if (ia.get("etapa") or {}).get("estado") == "no_solicitada":
        return "Lectura de IA: no se usó (revisión rápida). Los controles y las consultas no dependen de ella."
    lectura = ia.get("cobertura_lectura") or {}
    leidas, totales = lectura.get("senales_leidas") or 0, lectura.get("senales_totales") or 0
    modelos = (cobertura.get("manifiesto") or {}).get("modelos") or []
    if modelos and all(((m.get("estado_tareas") or {}).get("lectura_senales") or {}).get("estado") == "no_solicitada" for m in modelos):
        return "Lectura de señales por IA: no solicitada porque no había señales para interpretar. La lectura inicial del cuadro y la exploración del libro se registran por separado."
    if not leidas:
        leidas = max([((x.get("alcance_ia") or {}).get("hallazgos_enviados") or 0) for x in modelos if x.get("respondio")] or [0])
    if leidas:
        return f"Lectura de IA: disponible para {contar(leidas, 'señal', 'señales')}" + (f" de las {totales} registradas, de control y de contexto" if totales else "") + "."
    return "Lectura de IA: no disponible en esta corrida. Los controles y las consultas no dependen de ella."


def _bloque_consulta_declarada(informe, cobertura):
    """Si la persona declaró una consulta o pidió controles específicos, su resultado va arriba."""
    from services.columnas_declaradas import linea_declarada
    from services.reportes.markdown import _controles_solicitados_informe, _md, _orientacion_informe

    orientacion = _orientacion_informe(informe)
    controles = _controles_solicitados_informe(informe) or (cobertura.get("controles_solicitados") or {}).get("controles") or []
    restringido = linea_declarada(cobertura.get("restricciones_declaradas"))
    no_evaluada = str(cobertura.get("estado") or "") == "PREGUNTA_NO_EVALUADA"
    if not (orientacion or controles or restringido or no_evaluada):
        return []
    from services.reportes.registro import motivo_validez

    validez = motivo_validez(cobertura)
    if no_evaluada and validez and not (orientacion or controles):
        out = ["## Controles sin ejecutar", "", f"No se ejecutaron los controles: {validez}. "
               "Volvé a cargar el archivo sin indicar un informe anterior, o con uno de la misma estructura.", ""]
        return out
    if no_evaluada:
        estado = ("La pregunta declarada no pudo evaluarse con la estructura disponible. "
                  "Las consultas de abajo son señales generales del barrido: no responden la pregunta.")
    elif any(c.get("estado") == "no_evaluable" or c.get("cobertura_parcial") for c in controles):
        estado = "La consulta quedó sin evaluar o se evaluó parcialmente. No equivale a un control superado."
    elif controles:
        estado = "Los controles específicos solicitados fueron ejecutados; no certifican el informe."
    elif orientacion:
        estado = "No hay una evaluación específica registrada para la consulta. Las señales generales no acreditan que se haya respondido."
    else:
        estado = "Se aplicó la restricción declarada."
    out = ["## Resultado de la consulta", "", estado, ""]
    if orientacion:
        out.append(f"- **Consulta:** {_md(orientacion)}")
    for c in controles:
        out.append(f"- **{_md(c.get('nombre'))}:** {_md(c.get('resultado'))}")
    if restringido:
        out.append(f"- **Restricción declarada:** {restringido}")
    return out + [""]


def _celda_tabla(texto, maximo=170):
    texto = corto(texto).replace("|", "/")
    return texto if len(texto) <= maximo else texto[: maximo - 1].rsplit(" ", 1)[0] + "…"


def _sino(v):
    return "no registrado" if v is None else ("sí" if v else "no")


def _linea_mismos(delta, b, a):
    """Mismo motor = mismas reglas (versión); mismo código = misma huella. Antes se confundían."""
    mm = (b.get("version_motor") == a.get("version_motor")) if b.get("version_motor") and a.get("version_motor") else None
    mc = (b.get("version_codigo") == a.get("version_codigo")) if b.get("version_codigo") and a.get("version_codigo") else None
    linea = (f"- Mismo archivo: {_sino(delta.get('mismo_excel'))}; mismo motor: {_sino(mm)}"
             + (f" ({a.get('version_motor')})" if mm else "")
             + f"; mismo código: {_sino(mc)}; mismas opciones: {_sino(delta.get('mismas_opciones'))}.")
    if mm and mc is False:
        linea += " El código cambió entre las dos corridas sin cambiar la versión de las reglas (por ejemplo, ajustes de presentación)."
    return linea


def nota_conteo_senales(r) -> str:
    """Explica por qué la suma por control difiere de las señales de control de la página 1."""
    resumenes = r.get("resumenes_contexto") or 0
    if not resumenes:
        return ""
    directas, en_casos = r.get("senales_control_directas", 0), r.get("variaciones_en_casos", 0)
    variaciones = (r.get("senales_contexto") or 0) + en_casos
    return (f"Cómo se cuentan las señales: los totales por control suman {contar(directas, 'señal directa', 'señales directas')} "
            f"y {contar(resumenes, 'resumen', 'resúmenes')} de contexto temporal, que agrupan "
            f"{contar(variaciones, 'variación temporal', 'variaciones temporales')} ({r.get('senales_contexto') or 0} quedaron como contexto "
            f"y {en_casos} forman parte de un caso); las {contar(r['senales_control'], 'señal', 'señales')} "
            f"de control de la página 1 son esas {contar(directas, 'señal directa', 'señales directas')} más las "
            f"{contar(en_casos, 'variación temporal', 'variaciones temporales')} que forman parte de un caso.")


def lineas(informe, hallazgos, titulo="Informe de revisión"):
    """Informe para quien decide: consultas al área en la página 1, su detalle y el anexo técnico."""
    from services.reportes.consultas import consultas, portada
    from services.reportes.formato import numero
    from services.reportes.registro import construir
    from services.reportes.registro import lineas_markdown as lineas_registro
    from services.resultado_revision import alcance

    r = agrupar(hallazgos)
    cobertura = getattr(getattr(informe, "devolucion", None), "cobertura", None) or {}
    reg = construir(informe, hallazgos, cobertura)
    m = cobertura.get("manifiesto") or {}
    delta = cobertura.get("comparacion_corridas") or {}
    excel = cobertura.get("excel") or (informe.saneamiento or {}).get("excel") or {}
    resultado = alcance(informe)
    lista = consultas(r)
    primeras, resto = portada(lista)

    # Página 1 · Qué preguntar al área
    archivos = [a["archivo"] for a in reg.get("archivos") or [] if a.get("archivo")]
    cabecera = []
    if archivos:
        cabecera.append(f"**Archivo{'s' if len(archivos) > 1 else ''}:** " + ", ".join(archivos))
    if _fecha(informe):
        cabecera.append(f"**Fecha:** {_fecha(informe)}")
    cabecera.append(f"Informe #{getattr(informe, 'id', '—')}")
    out = ["# " + titulo, ""]
    lr = (getattr(informe, "saneamiento", None) or {}).get("lectura_revisada")
    if isinstance(lr, dict) and lr.get("archivo_original"):
        # Una tabla leída de un PDF o una imagen lo dice arriba; si la leyó un OCR, también eso.
        con_ocr = "con OCR " if lr.get("origen") == "revision_ocr" else ""
        out.extend([f"**Tabla leída {con_ocr}de {lr['archivo_original']} y revisada por una persona antes de analizar.**", ""])
    pendientes = _lineas_pendientes(reg)
    if reg["estado"] != "completo":
        # Lo no leído o no controlado se anuncia primero, antes que cualquier consulta; si hay
        # detalle, va una sola vez, después de las consultas.
        if pendientes:
            estado = "LECTURA INSUFICIENTE" if reg["estado"] == "insuficiente" else "LECTURA PARCIAL"
            partes = []
            for tipo, rotulo in (("no_leido", "Sin leer"), ("no_controlado", "Sin controlar")):
                items = [p for p in reg.get("pendientes") or [] if p["tipo"] == tipo]
                if items:
                    partes.append(f"{rotulo}: " + "; ".join(str(p["donde"]) for p in items[:8])
                                  + (f"; y {len(items) - 8} más" if len(items) > 8 else ""))
            out.extend([f"**{estado}.** " + ". ".join(partes) + ". Los motivos, después de las consultas.", ""])
        else:
            out.extend([f"**{reg['primera_linea']}**", ""])
    out.extend([" · ".join(cabecera), ""])
    ocultas = _contenido_oculto(excel)
    if ocultas:
        out.extend([f"**Contenido oculto en el archivo:** {ocultas}. Se leyó y se controló como el resto.", ""])
    if resultado["detalle_pdf"]:
        out.extend([*resultado["detalle_pdf"], ""])
    out.extend(_bloque_consulta_declarada(informe, cobertura))
    out.extend(["## Qué preguntar al área", "", _linea_cobertura(informe, reg, resultado, excel), ""])
    if lista:
        out.append(
            f"Resultado: {contar(r['casos_revision'], 'caso')} de revisión ({contar(r['senales_control'], 'señal', 'señales')} de control) "
            f"agrupado{'s' if r['casos_revision'] != 1 else ''} por causa en {contar(len(lista), 'consulta')}"
            + (f"; estas son las {len(primeras)} prioritarias y el resto está en el anexo técnico." if resto else ".")
        )
        out.append("")
        duras = [c for c in primeras if c.get("tipo") == "no_cierra"]
        blandas = [c for c in primeras if c.get("tipo") != "no_cierra"]
        n = 0
        for grupo, titulo_grupo in ((duras, "**No cierra.** Se puede verificar en el propio archivo:"),
                                    (blandas, "**Para preguntar.** Cambios que pueden tener una explicación:")):
            if not grupo:
                continue
            if duras and blandas:
                out.extend([titulo_grupo, ""])
            for c in grupo:
                n += 1
                out.append(f"{n}. {c['resumen']}")
            out.append("")
        if duras and blandas:
            out.append("Las primeras son cuentas que no dan; las segundas, señales para preguntar. "
                       "El área debe revisar las causas antes de atribuir un error.")
        elif duras:
            out.append("Estas cuentas no cierran con los valores publicados. El área debe revisar las causas "
                       "y determinar qué dato o interpretación corresponde corregir.")
        else:
            out.append("Estas señales requieren contexto y una respuesta del área. Por sí solas no demuestran "
                       "un error en los datos. La decisión es de la persona responsable.")
    else:
        sin = f"no hay consultas para el área ({contar(r['casos_revision'], 'caso')} de revisión en lo que se leyó y controló). "
        # Con pendientes de lectura la frase abre el párrafo: con mayúscula.
        out.append(("No hay casos ni pendientes de lectura: " + sin) if not reg.get("pendientes") else sin[0].upper() + sin[1:])
        out[-1] += "Que no haya señales no certifica el informe."
    out.append("")
    if reg["estado"] != "completo" and pendientes:
        out.extend(pendientes)
        out.append("")

    # Página 2 · Detalle de cada consulta
    if primeras:
        out.extend(["<!-- salto-pagina -->", "## Detalle de las consultas", ""])
        for n, c in enumerate(primeras, 1):
            e = c["origen"]["primary_finding"].get("evidencia") or {}
            donde = c["donde"]
            vis = e.get("visibilidad_origen")
            if vis:
                donde += "; en contenido no visible: " + (", ".join(vis) if isinstance(vis, list) else str(vis))
            out.extend([
                f"### {n}. {c['prioridad'].upper()} · {c['titulo']} · {c['etiqueta']}",
                "",
                f"- **Qué pasó:** {c['que_paso']}",
                f"- **Qué preguntar:** {c['preguntar']}",
                f"- **Evidencia:** {c['que_pasa']}",
                f"- **Dónde:** {donde}.",
            ])
            if c.get("detalle_tecnico"):
                out.append(f"- **Detalle técnico:** {c['detalle_tecnico']}")
            # Sin enlace: el PDF circula y no lleva datos de la persona ni del informe en una dirección.
            out.append(f"- {INVITACION_RESPUESTA_PDF}")
            out.append("")

    # Anexo técnico, separado
    out.extend(["<!-- salto-pagina -->", "## Anexo técnico", "",
                "Respaldo de las consultas: resto de los casos, lectura, controles y metodología. "
                f"La evidencia completa de cada señal se descarga {DONDE_DETALLE}.", ""])
    out.extend(["### Resto de los casos", ""])
    if resto:
        out.extend(["| # | Prioridad | Lugar | Qué se observó |", "|---|---|---|---|"])
        for n, c in enumerate(resto, len(primeras) + 1):
            lugar = c["donde"].split(";")[0]
            if len(c["casos"]) > 1:
                lugar += f" ({len(c['casos'])} casos)"
            out.append(f"| {n} | {c['prioridad']} | {_celda_tabla(lugar, 60)} | {_celda_tabla(c['que_paso'])} |")
    else:
        out.append("- No hay otros casos: todas las consultas están arriba.")
    out.append("")
    if r.get("notas"):
        out.extend(["### Cruces entre archivos · notas de alcance", ""])
        out.extend("- " + corto(h.get("descripcion")) for h in r["notas"])
        out.extend(["- Las notas describen qué se comparó y qué no; no son señales de error.", ""])
    if r["exploratorias"]:
        out.extend(["### Asociaciones exploratorias", "",
                    f"- {contar(len(r['exploratorias']), 'asociación exploratoria', 'asociaciones exploratorias')} fuera de los casos de control; "
                    "se listan en el detalle técnico.", ""])
    out.extend(["### Variaciones temporales", ""])
    if r["contexto"]:
        por_periodo = Counter()
        for g in r["contexto"]:
            por_periodo[g["periodo"]] += g["cantidad"]
        mayores = sorted(por_periodo.items(), key=lambda x: (-x[1], x[0]))[:3]
        out.append(
            f"- {contar(r['senales_contexto'], 'variación temporal', 'variaciones temporales')} fuera de lo habitual quedaron como contexto, "
            f"en {contar(len(por_periodo), 'período')}; los de más movimiento: "
            + ", ".join(f"{a} ({v})" for a, v in mayores) + "."
            + (f" Otras {r['variaciones_en_casos']} forman parte de un caso." if r.get("variaciones_en_casos") else "")
        )
        out.append("- En moneda corriente, un salto nominal requiere contexto de inflación, cobertura y metodología; "
                   "no compite con los controles aritméticos. El listado completo está en el detalle técnico.")
    else:
        out.append("- No hay variaciones temporales registradas fuera de los casos.")
    out.append("")
    out.extend(lineas_registro(reg))
    out.extend(["## Controles ejecutados", ""])
    excluidos = []
    for c in reg["controles"]:
        if c["estado"] != "ejecutado":
            excluidos.append(c)
            continue
        motivo = corto(c.get("motivo"), 180).rstrip(".")
        out.append(f"- {c['nombre']}: {senales(c.get('senales'))}" + (f". {motivo}." if motivo else "."))
    nota = nota_conteo_senales(r)
    if nota:
        out.append("- " + nota)
    cierres = _cierres_verificados(resultado["estructura"]) or resultado["estructura"].get("cantidad_cierres")
    if cierres:
        out.append(f"- Sin diferencias: {numero(cierres)} {'cierres' if cierres != 1 else 'cierre'} entre totales y componentes "
                   f"verificado{'s' if cierres != 1 else ''} dentro de la tolerancia. No certifican todo el archivo.")
    elif cierres is not None:
        # Cero cierres no es un control que pasó: no se ejecutó, y se dice por qué.
        motivo = resultado["estructura"].get("motivo_sin_cierres") or "no se identificaron totales con sus componentes para verificar"
        if not any(c.get("nombre") == "Cierres entre totales y componentes" for c in excluidos):
            excluidos.append(dict(nombre="Cierres entre totales y componentes", estado="no_ejecutado", motivo=motivo))
    if excluidos:
        out.extend(["", "## Controles no aplicables o no ejecutados", ""])
        for c in excluidos:
            estado = "no aplica" if c["estado"] == "no_aplicable" else "no ejecutado"
            out.append(f"- {c['nombre']} · {estado}: {corto(c.get('motivo'), 200).rstrip('.') or 'sin motivo registrado'}.")
    out.extend(["", "## Cambios respecto de la corrida base", ""])
    if delta.get("estado") == "comparado":
        b, a = delta["base"], delta["actual"]
        out.extend([
            f"- Base: informe {b.get('informe_id')}, ejecución {b.get('ejecucion_id')}; motor {b.get('version_motor')}. "
            f"Actual: motor {a.get('version_motor')}.",
            "- " + "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in delta["conteos"].items()) + ".",
            _linea_mismos(delta, b, a),
            "- " + delta["advertencia"],
        ])
    else:
        out.append("- " + delta.get("motivo", "Esta corrida histórica no tiene comparación registrada. Puede elegirse una base desde la pantalla."))
    out.extend(["", "## Apoyo de IA", "", "- " + _linea_ia(cobertura),
                "- Es apoyo: no modifica los controles ni la prioridad, y su cobertura no mide la exactitud de la interpretación.", ""])
    out.extend(["## Metodología y registro de la corrida", ""])
    out.append(
        "- Cada consulta agrupa casos con una causa común: la misma fila en años seguidos, o un total consolidado que no cierra "
        "por la misma diferencia que el subtotal de uno de sus componentes. La prioridad combina cuánto se aparta el valor, "
        "su peso sobre el total del cuadro y el tipo de evidencia (aritmética exacta antes que patrón)."
    )
    out.append("- " + r["aclaracion"] + " Los controles son reproducibles; ninguna señal confirma por sí sola un error ni certifica el informe.")
    out.append(f"- {contar(len(informe.datos or []), 'registro')} incorporado{'s' if len(informe.datos or []) != 1 else ''}"
               + (f"; {contar(len(excel.get('hojas', [])), 'hoja')}; {contar(len(excel.get('bloques', [])), 'cuadro')}" if excel.get("hojas") else "")
               + f". {reg['periodo']['texto']}")
    if reg["periodo"]["declarado"] is not False and reg["periodo"]["valor"]:
        from services.reportes.markdown import _advertencia_periodo

        advertencia = _advertencia_periodo(reg["periodo"]["valor"], reg["periodo"]["observado"])
        if advertencia:
            out.append("- " + advertencia.lstrip("- "))
    out.append(f"- Motor: {m.get('version_motor', 'histórico no registrado')}. Código de la corrida: {m.get('version_codigo', 'no registrado')}.")
    if delta.get("estado") == "comparado":
        out.append(f"- Código de la corrida base: {delta['base'].get('version_codigo')}.")
    out.extend(["", "> Esta revisión no constituye una auditoría ni sustituye la decisión de la persona responsable.", ""])
    # Dentro del anexo, cada sección es un subtítulo: el anexo es una sola pieza, separada de las consultas.
    inicio = out.index("## Anexo técnico") + 1
    out[inicio:] = ["#" + x if x.startswith("## ") else x for x in out[inicio:]]
    return out


def anexo_contexto(hallazgos):
    r = agrupar(hallazgos)
    out = ["## Índice de casos y efectos asociados", ""]
    for c in r["casos"]:
        h = c["primary_finding"]
        e = h.get("evidencia") or {}
        ubicacion = (
            f"{e.get('hoja')}!{e.get('celda')}" if e.get("hoja") and e.get("celda") else _lente_legible(h.get("lente"))
        )
        # La huella sirve para comparar dos corridas del mismo archivo: se conserva, al final y
        # rotulada, en lugar de encabezar una línea que nadie puede leer.
        out.append(
            f"- {ubicacion} · {c['prioridad']} · {senales(c['cantidad_senales'])}. "
            f"Referencia técnica: {c['root_cause_id']}."
        )
        if c.get("referencias"):
            out.append("  - Celdas del caso: " + ", ".join(c["referencias"]) + ".")
        for a in c["related_findings"]:
            out.append("  - Efecto asociado: " + str(a.get("descripcion", "")))
    if r.get("notas"):
        out.extend(["", "## Notas de alcance de los cruces entre archivos", ""])
        for h in r["notas"]:
            out.append("- " + str(h.get("descripcion", "")))
    if r['exploratorias']:
        from services.casos_revision import huella, identidad
        out.extend(["", "## Índice de asociaciones exploratorias (fuera de los casos de control)", ""])
        for h in r['exploratorias']:
            referencia = "caso-" + huella([identidad(h)])[:16]
            out.append(f"- {_lente_legible(h.get('lente'))} · exploratoria · 1 señal. Referencia técnica: {referencia}.")
    out.extend(["", "## Contexto agrupado por año, hoja y cuadro", ""])
    for g in r["contexto"]:
        out.extend([f"### {g['periodo']} · {g['hoja']} · cuadro {g['cuadro']} · {senales(g['cantidad'])}", ""])
        for d in g["detalle"]:
            out.append("- " + str(d.get("descripcion", "")))
    return out
