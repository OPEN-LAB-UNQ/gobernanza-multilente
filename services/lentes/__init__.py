from __future__ import annotations

import re

from sqlalchemy.orm import Session

import models
from enums import Lente, Severidad
from services import ambito as ambito_svc

from . import ajedrecista, conciliador, cronista, matematico, orquesta, radiologo, rizoma

_BAJAR_SEVERIDAD = {
    Severidad.ALTA.value: Severidad.MEDIA.value,
    Severidad.MEDIA.value: Severidad.BAJA.value,
    Severidad.BAJA.value: Severidad.BAJA.value,
}


def _previos_dominio(db: Session, informe: models.Informe) -> list[models.Informe]:
    """Informes previos del mismo dominio (banco), del cual el historial de la
    misma area es un subconjunto -- una sola consulta cubre ambos usos."""
    return (
        db.query(models.Informe)
        .filter(
            models.Informe.dominio == informe.dominio,
            models.Informe.id != informe.id,
            models.Informe.periodo != informe.periodo,
            models.Informe.creado_en < informe.creado_en,
        )
        .order_by(models.Informe.creado_en.asc())
        .all()
    )


def ejecutar_lentes_stream(db: Session, informe: models.Informe):
    # Se declara siempre, antes de cualquier lente, para que ninguna corrida herede el
    # ámbito de la anterior (los bloques de un Excel comparten el del informe completo).
    ambito_svc.declarar(ambito_svc.de_informe(informe))
    if (informe.saneamiento or {}).get("excel", {}).get("bloques"):
        from services.excel_cobertura import ejecutar_por_bloques
        yield from ejecutar_por_bloques(db, informe, _ejecutar_unidad)
    else:
        yield from _ejecutar_unidad(db, informe)


def _ejecutar_unidad(db: Session, informe: models.Informe, previos=None):
    """Version generadora de ejecutar_lentes(): yieldea (lente, hallazgos_nuevos)
    a medida que cada lente termina, para poder mostrar progreso en vivo.
    ejecutar_lentes() (abajo) es un envoltorio no-streaming que la consume
    entera -- misma logica, un solo lugar de verdad."""
    from services.resultado_revision import separar_datos
    datos, excluidos = separar_datos(informe.datos or [])
    from services import columnas_declaradas, perfilado
    from services import interpretacion_previa as ip
    interpretada = ip.de_unidad(informe)
    if interpretada is not None:
        identificadores = [c for c, r in interpretada.get("confirmada", {}).get("roles", {}).items() if r == "identificador"]
        declaradas = columnas_declaradas.detectar((informe.saneamiento or {}).get("orientacion_analisis"), datos)
        perfilado.declarar_identificadores(set(identificadores) | set(declaradas["columnas"]))
    previos_dominio = _previos_dominio(db, informe) if previos is None else previos
    from services import validez
    previos_dominio, antecedentes_excluidos = validez.antecedentes_comparables(informe, previos_dominio)
    condiciones = validez.aplicabilidad_lentes(informe, previos_dominio)
    if interpretada is not None:
        for lente in ip.LENTES:
            if not interpretada.get("plan", {}).get(lente):
                condiciones[lente] = {"estado": "no_aplicable", "motivo": "No seleccionado por la interpretación confirmada de este cuadro."}
        # El régimen no se deduce de «universidad» ni del dominio global.
        # Sin régimen determinado vale el ámbito que declaró quien cargó el informe.
        regimen = interpretada.get("confirmada", {}).get("regimen")
        ambito_svc.declarar("organizacion" if regimen == "privado" else "publico" if regimen == "publico"
                            else ambito_svc.de_informe(informe))
    if (informe.saneamiento or {}).get("periodos_excel_duplicados"):
        condiciones["cronista"] = {"estado": "no_evaluable", "motivo": _motivo_periodos_repetidos(datos)}
    informe._condiciones_lentes = condiciones
    informe._antecedentes_excluidos = antecedentes_excluidos
    interdocumental = validez.condiciones_interdocumentales(datos)
    informe._condiciones_interdocumentales = interdocumental
    historial = [p for p in previos_dominio if p.area_id == informe.area_id]
    datos_periodo_anterior = historial[-1].datos if historial else None
    historial_datos = [h.datos for h in historial]
    banco = [{"periodo": p.periodo, "datos": p.datos} for p in previos_dominio]

    crudos: list[dict] = []
    tabulares = _tabulares_sin_bloques(informe)

    nuevos = [{**h, "lente": Lente.AJEDRECISTA.value} for h in ajedrecista.imposibilidad(datos,
        **({"presupuestario": interpretada["plan"].get("presupuesto", False),
            "importes_estadisticos": [c for c, rol in interpretada["confirmada"].get("roles", {}).items()
                                     if rol == "importe" and interpretada["confirmada"].get("tipo") == "estadistica"]}
           if interpretada is not None else {}))] if condiciones["ajedrecista"]["estado"] == "evaluado" else []
    nuevos += [{**h, "lente": Lente.AJEDRECISTA.value} for h in (informe.saneamiento or {}).get("formula_hallazgos", [])]
    nuevos += tabulares.get("ajedrecista", [])
    crudos.extend(nuevos)
    yield "ajedrecista", nuevos

    notas = _notas(informe)
    nuevos = [{**h, "lente": Lente.CRONISTA.value} for h in cronista.analizar(datos, notas)] if condiciones["cronista"]["estado"] == "evaluado" else []
    problemas = condiciones["cronista"].get("problemas_periodo")
    if problemas and condiciones["cronista"]["estado"] == "evaluado" and not (informe.saneamiento or {}).get("version_controles_tabulares"):
        # Sin controles tabulares de Excel (CSV, PDF): la alerta del eje la emite la propia lente.
        nuevos += [{**h, "lente": Lente.CRONISTA.value} for h in cronista.alertas_periodo(datos, problemas)]
    nuevos += tabulares.get("cronista", [])
    crudos.extend(nuevos)
    yield "cronista", nuevos

    nuevos = [{**h, "lente": Lente.ORQUESTA.value} for h in orquesta.analizar(datos, historial_datos, permitir_interdocumental=interdocumental["estado"] == "evaluado")] if condiciones["orquesta"]["estado"] == "evaluado" else []
    nuevos += tabulares.get("orquesta", [])
    crudos.extend(nuevos)
    yield "orquesta", nuevos

    nuevos = [{**h, "lente": Lente.RADIOLOGO.value} for h in radiologo.analizar(informe.dominio, informe.periodo, datos, banco)] if condiciones["radiologo"]["estado"] == "evaluado" else []
    # La priorización contra el informe anterior también es comparación con
    # preinformes: se comunica como Radiólogo, nunca como Ajedrecista.
    if condiciones["radiologo"]["estado"] == "evaluado":
        nuevos += [{**h, "lente": Lente.RADIOLOGO.value} for h in ajedrecista.priorizacion(datos, datos_periodo_anterior)]
    nuevos += tabulares.get("radiologo", [])
    crudos.extend(nuevos)
    yield "radiologo", nuevos

    nuevos = [{**h, "lente": Lente.RIZOMA.value} for h in rizoma.analizar(datos,
        interpretacion=interpretada.get("confirmada") if interpretada is not None else None)] if condiciones["rizoma"]["estado"] == "evaluado" else []
    nuevos += tabulares.get("rizoma", [])
    crudos.extend(nuevos)
    yield "rizoma", nuevos

    nuevos = [{**h, "lente": Lente.MATEMATICO.value} for h in matematico.analizar(datos,
        **({"roles": interpretada["confirmada"].get("roles", {})} if interpretada is not None else {}))] if condiciones["matematico"]["estado"] == "evaluado" else []
    nuevos += [{**h, "lente": Lente.MATEMATICO.value} for h in (informe.saneamiento or {}).get("matematico_hallazgos", [])]
    nuevos += tabulares.get("matematico", [])
    crudos.extend(nuevos)
    yield "matematico", nuevos

    # El conciliador corre al final, como capa transversal: revisa el conjunto
    # completo de hallazgos sustantivos y, cuando puede explicarlos por un
    # artefacto tecnico, les baja la severidad y les adjunta contexto en vez
    # de duplicar la señal. Trabaja sobre copias; la lista final reemplaza
    # explícitamente el acumulador del consumidor mediante _crudos_finales.
    resultado_conciliador = conciliador.analizar(datos, crudos,
        **({"interpretacion": interpretada.get("confirmada")} if interpretada is not None else {})) if condiciones["conciliador"]["estado"] == "evaluado" else {"modulaciones": [], "hallazgo_general": None}
    antes = len(crudos)
    crudos = aplicar_conciliador(crudos, resultado_conciliador)
    crudos += [h for lente, hs in tabulares.items() if lente not in LENTES_PREVIAS for h in hs]
    yield "conciliador", crudos[antes:]
    # aplicar_conciliador ya no muta los dicts que veniamos acumulando -- devuelve
    # una lista nueva con las modulaciones (severidad/limites) aplicadas. Este
    # yield adicional le pasa esa lista completa a quien consume el generador
    # (ejecutar_analisis_stream), que reemplaza su acumulador en vez de confiar
    # en que los dicts se mutaran solos por alias compartido.
    yield "_crudos_finales", crudos


LENTES_PREVIAS = ("ajedrecista", "cronista", "orquesta", "radiologo", "rizoma", "matematico")


def _tabulares_sin_bloques(informe) -> dict[str, list[dict]]:
    """Controles por celda de tablas CSV/PDF cuando la carga no tiene cuadros de Excel
    (con Excel, ejecutar_por_bloques ya los incorpora)."""
    saneamiento = informe.saneamiento or {}
    tabulares = saneamiento.get("controles_tabulares") or []
    if not tabulares or (saneamiento.get("excel") or {}).get("bloques"):
        return {}
    from services.prioridad_controles import consolidar_contexto

    por_lente: dict[str, list[dict]] = {}
    for h in consolidar_contexto([dict(h) for h in tabulares]):
        por_lente.setdefault(h["lente"], []).append(h)
    condiciones = getattr(informe, "_condiciones_lentes", None)
    if isinstance(condiciones, dict):
        for lente in por_lente:
            if (condiciones.get(lente) or {}).get("estado") != "evaluado":
                condiciones[lente] = {
                    **(condiciones.get(lente) or {}), "estado": "evaluado",
                    "motivo": "Controles tabulares por celda sobre las tablas del archivo.",
                }
    return por_lente


def _notas(informe) -> list[dict]:
    """Títulos y notas del archivo (ya saneados) que pueden documentar un quiebre de serie."""
    elementos = ((informe.saneamiento or {}).get("contexto_semantico") or {}).get("elementos") or []
    return [
        {"texto": x.get("texto", ""), "celda": x.get("celda"), "hoja": x.get("hoja")}
        for x in elementos
        if x.get("rol") not in ("indicador_categoria", "nombre_hoja") and len(str(x.get("texto") or "")) >= 25
    ]


def _motivo_periodos_repetidos(datos: list[dict]) -> str:
    """Un encabezado de dos niveles (variable × período) no es un año repetido, pero el Cronista
    lee series de una sola variable: se declara no evaluado con ese motivo."""
    variables = set()
    for col in (datos[0].keys() if datos else []):
        m = re.match(r"^(.*\S)\s+((?:19|20)\d{2})(?:\.0)?$", str(col))
        if m:
            variables.add(m.group(1).strip().lower())
    if len(variables) >= 2:
        return ("Encabezado de dos niveles (variable × período): los controles tabulares lo leen por variable, "
                "pero la lectura temporal del Cronista no separa las variables; no evaluado en este cuadro.")
    return "Encabezados de período repetidos en este cuadro; corregir o aclarar los años antes de comparar la serie."


def ejecutar_lentes(db: Session, informe: models.Informe) -> list[dict]:
    """Corre las lentes sobre un informe y devuelve hallazgos crudos
    (sin persistir), cada uno con su lente de origen."""
    crudos: list[dict] = []
    for lente, nuevos in ejecutar_lentes_stream(db, informe):
        if lente == "_crudos_finales":
            crudos = nuevos
            continue
        crudos.extend(nuevos)
    return crudos


def aplicar_conciliador(crudos: list[dict], resultado_conciliador: dict) -> list[dict]:
    """Aplica las modulaciones del conciliador y devuelve una lista NUEVA --
    nunca muta los dicts que recibio en `crudos`. Cada modulacion (pistas
    tecnicas generales, o hallazgos presupuestarios) se evalua por separado:
    si logra emparejar al menos un hallazgo, lo modula (baja severidad,
    adjunta contexto_tecnico). Si UNA modulacion no logra emparejar nada --
    aunque otra si haya modulado algo -- se agrega la advertencia general
    para esa cobertura, para no perder en silencio el artefacto que no se
    pudo vincular a una senal puntual (antes el fallback dependia de un solo
    booleano global y una modulacion exitosa apagaba el aviso de otra que
    habia fallado). Separado de ejecutar_lentes para poder calibrar/testear
    sin base de datos.
    """
    resultado = [dict(h) for h in crudos]  # copias propias: el llamador conserva sus dicts intactos
    algo_modulado_global = False
    hubo_modulacion_sin_match = False
    modulados = set()
    organizacion = ambito_svc.es_organizacion()
    for mod in resultado_conciliador["modulaciones"]:
        matcheo_esta_modulacion = False
        for h in resultado:
            coincide_filas = mod["filas"] and set(h.get("evidencia", {}).get("filas") or []) & mod["filas"]
            coincide_presupuestario = mod["hallazgo_presupuestario"] and not organizacion and h.get("modo") == "imposibilidad" and re.search(
                r"devengado|pagado|credito|crédito|vigente", h.get("descripcion", ""), re.I
            )
            if not (coincide_filas or coincide_presupuestario):
                continue
            limites = dict(h.get("limites") or {})
            limites["contexto_tecnico"] = mod["contexto_tecnico"]
            h["limites"] = limites
            if id(h) not in modulados:
                h["severidad"] = _BAJAR_SEVERIDAD.get(h.get("severidad", "media"), h.get("severidad", "media"))
                modulados.add(id(h))
            algo_modulado_global = True
            matcheo_esta_modulacion = True
        if not matcheo_esta_modulacion:
            hubo_modulacion_sin_match = True

    if resultado_conciliador["hallazgo_general"] and (not algo_modulado_global or hubo_modulacion_sin_match):
        resultado.append({**resultado_conciliador["hallazgo_general"], "lente": Lente.CONCILIADOR.value})

    return resultado
