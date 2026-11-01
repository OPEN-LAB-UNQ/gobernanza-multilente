"""Casos de revisión conservadores: no eliminan señales ni prueban causalidad."""

import hashlib
import json
from collections import Counter, defaultdict
from copy import deepcopy

from services.lectura_temporal import anual, campo


def huella(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def registro(h):
    copia = {
        k: deepcopy(campo(h, k))
        for k in ("id", "lente", "modo", "descripcion", "severidad", "evidencia", "pregunta_institucional")
    }
    # Corregir la presentación histórica sin reescribir la corrida original.
    if (copia["evidencia"] or {}).get("regla") == "identidad_entre_cuadros":
        antigua = "Verificar cuál de las dos aperturas refleja la ejecución del período y corregir la otra."
        prudente = "Confirmar con el área si ambos conceptos deben coincidir en este período; documentar la diferencia y corregir sólo si se confirma un error."
        copia["descripcion"] = str(copia["descripcion"] or "").replace(
            "Una de las dos aperturas del mismo importe quedó sin actualizar.",
            "La coincidencia histórica no demuestra equivalencia; verificar cobertura y actualización.",
        ).replace(antigua, prudente)
        if copia["evidencia"].get("accion_revision") == antigua:
            copia["evidencia"]["accion_revision"] = prudente
        if copia["pregunta_institucional"] == antigua:
            copia["pregunta_institucional"] = prudente
    from services.reportes.lenguaje_llano import resumen_de, traducir_en_texto

    copia["resumen_llano"] = resumen_de(h)
    copia["descripcion_es"] = traducir_en_texto(copia["descripcion"])
    return copia


REGLAS_NOTA = {"cruce_no_comparable", "cobertura_cruce_ediciones"}


def es_nota(h):
    """Notas de alcance (por ejemplo, de un cruce entre ediciones): no son señales ni contexto temporal."""
    e = campo(h, "evidencia", {}) or {}
    return bool(e.get("nota_cruce")) or e.get("regla") in REGLAS_NOTA or bool(e.get("sondeo"))


def es_contexto(h):
    if es_nota(h):
        return False
    return anual(h) or (campo(h, "evidencia", {}) or {}).get("naturaleza") == "contexto"


# ---------------------------------------------------------------------------------------------
# Política única de prioridad: tres ejes explícitos por señal
# ---------------------------------------------------------------------------------------------
# Rareza (cuánto se aparta), impacto (peso del desvío sobre el total del cuadro, en su unidad) y
# evidencia (aritmética exacta > patrón; corroboración). Todas las piezas —ejecutivo, completo,
# pantalla y comprobante— leen la prioridad de acá; la severidad original de cada control queda
# como dato histórico y no se presenta como prioridad.

NIVELES = {"alta": 3, "media": 2, "baja": 1}
ESTRUCTURALES = {
    "anio_duplicado",
    "anio_no_entero",
    "anios_no_crecientes",
    "discontinuidad_anual",
    "cambio_tipo",
    "vacio_interior",
    "signo_aislado",
}
EXACTAS = {
    "conciliacion_aritmetica",
    "poblacion_implicita",
    "cambio_entre_ediciones",
    "serie_revisada_entre_ediciones",
    "cambio_de_escala_entre_ediciones",
    "series_intercambiadas_entre_ediciones",
    "serie_de_otro_rubro_entre_ediciones",
    "cambio_de_unidad_entre_ediciones",
    "cuadro_revisado_entre_ediciones",
    "cuadro_reexpresado_entre_ediciones",
    "resultado_concilia_con_patrimonio",
    "efectivo_final_concilia_con_estado_patrimonial",
    "partes_no_suman_total",
    "componentes_no_cierran_total",
    "complemento_porcentual_no_cierra",
}
UMBRAL_IMPACTO_ALTO = 1.0  # % del total del cuadro
UMBRAL_IMPACTO_BAJO = 0.1
# Un patrón (no una cuenta exacta) llega a ALTA con impacto medio sólo si pesa al menos esto del total.
UMBRAL_IMPACTO_PATRON = 0.5
# Un extremo de la serie sin vecino posterior no baja de ALTA si su peso sobre el total es alto.
EXTREMO_MATERIAL_SIN_TOPE = True
CAMBIO_EDICION = 0.05


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _fmt(v, decimales=2):
    from services.controles_excel.comun import es_numero

    return es_numero(v, decimales)


SALTOS_RECURRENTES = 2  # igual que series.SALTOS_PARECIDOS


def _rareza(h, e):
    r = e.get("regla")
    if r == "vacio_interior":
        if e.get("valor_anterior") == e.get("valor_posterior") == 0:
            return "baja", "hueco entre ceros"
        return "alta", "hueco dentro de una serie con valores"
    if r in ESTRUCTURALES:
        return "alta", "regla estructural incumplida"
    if r in {"series_intercambiadas_entre_ediciones", "serie_de_otro_rubro_entre_ediciones", "cambio_de_escala_entre_ediciones"}:
        return "alta", "la serie publicada cambió de fila o de escala entre ediciones"
    if r in {"cambio_de_unidad_entre_ediciones", "cuadro_revisado_entre_ediciones", "cuadro_reexpresado_entre_ediciones"}:
        return "media", "cambio extendido a todo el cuadro"
    if r == "conciliacion_aritmetica":
        dp = _num(e.get("diferencia_porcentual"))
        if dp is not None:
            # La conciliación ya descontó el redondeo: un total que no cierra por 1 % o más es un hecho aritmético.
            nivel = "alta" if dp >= 1 else "media" if dp >= 0.5 else "baja"
            return nivel, f"diferencia de {_fmt(dp)} % entre total y componentes"
    if r == "cambio_entre_ediciones":
        a, b = _num(e.get("valor_observado")), _num(e.get("valor_edicion_anterior"))
        if a is not None and b:
            d = abs(a / b - 1)
            nivel = "alta" if d >= 0.5 else "media" if d >= CAMBIO_EDICION else "baja"
            return nivel, f"cambio de {_fmt(100 * d, 1)} % respecto de la edición anterior"
    factor = _num(e.get("factor_escala")) or _num((e.get("rareza") or {}).get("factor_escala"))
    if factor:
        f = factor if factor >= 1 else 1 / factor
        if e.get("calibrado_por_volatilidad") and (_num(e.get("saltos_parecidos_en_la_serie")) or 0) >= SALTOS_RECURRENTES:
            # La serie repite saltos de ese orden (flujos trimestrales, cuentas chicas que oscilan): el control
            # ya lo calibró como habitual. El factor no la vuelve rara: queda como rareza media.
            return "media", f"se aparta {_fmt(f)} veces, en una serie con otros saltos del mismo orden"
        if e.get("rareza_media_sin_separacion"):
            # Fuera de la escala de su columna pero cerca de otros valores y sin un factor de potencia de diez.
            return "media", f"se aparta {_fmt(f)} veces, sin separarse claramente del resto de la columna"
        return ("alta" if f >= 8 else "media" if f >= 3 else "baja"), f"se aparta {_fmt(f)} veces de la escala esperada"
    ratio = _num(e.get("ratio_vs_movimiento_tipico")) or _num(e.get("ratio_maximo_vs_movimiento_tipico"))
    if ratio:
        nivel = "alta" if ratio >= 10 else "media" if ratio >= 3 else "baja"
        return nivel, f"salto de {_fmt(ratio, 1)} veces el movimiento típico"
    sev = str(campo(h, "severidad", "media") or "media")
    return (sev if sev in NIVELES else "media"), "nivel declarado por el control que la detectó"


def _impacto(e):
    """Peso del desvío sobre el total del cuadro, en la unidad del cuadro."""
    derivada = e.get("tabla_derivada") or {}
    if derivada.get("subordinada"):
        fuente = ", ".join(derivada.get("celdas_fuente") or []) or derivada.get("hoja_fuente") or "la hoja fuente"
        return "no_aplica", None, f"tabla derivada: el impacto se mide en la celda fuente ({fuente})"
    mat = e.get("materialidad") or {}
    imp = e.get("impacto") or {}
    pct = _num(mat.get("porcentaje_revision", mat.get("porcentaje_total"))) if mat else None
    base = mat.get("celda_total") if mat else None
    if pct is None:
        pct = _num(imp.get("porcentaje"))
        base = imp.get("celda_total") or imp.get("base")
    if pct is None:
        ficha = e.get("ficha_serie") or {}
        if imp.get("motivo"):
            motivo = imp["motivo"]
        elif ficha and not ficha.get("unidad"):
            motivo = "falta el rótulo de unidad del cuadro; sin él no se compara con el total"
        else:
            motivo = "sin total del cuadro con el cual medirlo"
        return "no_determinado", None, motivo
    nivel = "alta" if pct >= UMBRAL_IMPACTO_ALTO else "media" if pct >= UMBRAL_IMPACTO_BAJO else "baja"
    return nivel, pct, f"{_fmt(pct, 3 if pct < 0.1 else 2)} % del total" + (f" en {base}" if base else "")


def _evidencia(h, e, corroborada_caso=False):
    r = e.get("regla")
    if e.get("corroboracion_independiente") or any(
        x.get("regla") in {"conciliacion_aritmetica", "poblacion_implicita"} for x in e.get("conciliaciones", []) or []
    ):
        return "corroborada", "corroborada por un control independiente (conciliación)"
    if (e.get("tabla_derivada") or {}).get("inconsistente_con_fuente"):
        return "exacta", "la celda no coincide con el cálculo desde su hoja fuente"
    if r in EXACTAS or e.get("naturaleza") == "deterministica" or campo(h, "modo") == "coherencia_interdocumental":
        return "exacta", "aritmética exacta o comparación de valores publicados"
    if r in ESTRUCTURALES:
        return "exacta", "regla estructural verificable en la celda"
    if corroborada_caso:
        return "corroborada", "el desvío se propaga y se observa a la entrada y a la salida en totales o tablas derivadas"
    if (r == "escala_extremo" and not e.get("confirmacion_bilateral")) or e.get("extremo_de_serie"):
        return "patron_debil", "patrón sin confirmación bilateral (extremo de la serie)"
    if campo(h, "lente") == "rizoma" or e.get("naturaleza") == "exploratoria":
        return "exploratoria", "asociación exploratoria"
    return "patron", "patrón estadístico a verificar"


def ejes(h, corroborada_caso=False):
    """Rareza, impacto y evidencia de una señal, y la prioridad que resulta de combinarlos."""
    e = campo(h, "evidencia", {}) or {}
    rareza, detalle_rareza = _rareza(h, e)
    impacto, porcentaje, detalle_impacto = _impacto(e)
    evidencia, detalle_evidencia = _evidencia(h, e, corroborada_caso)
    if evidencia == "corroborada":
        nivel = "alta"
    elif evidencia == "exacta":
        if impacto in {"alta", "media"}:
            nivel = "alta"
        elif impacto == "baja":
            # Un total que no cierra (regla exacta) con una diferencia rara es un hecho, aunque pese poco.
            nivel = "alta" if rareza == "alta" else "media"
        else:
            nivel = "alta" if rareza == "alta" else "media"
    elif evidencia == "exploratoria":
        nivel = "baja"
    elif rareza == "alta" and (impacto in {"alta", "no_determinado"}
                               or (impacto == "media" and (porcentaje or 0) >= UMBRAL_IMPACTO_PATRON)):
        nivel = "alta"
    elif rareza == "baja" and impacto == "baja":
        nivel = "baja"
    else:
        nivel = "media"
    tope = None
    if evidencia == "patron_debil" and nivel == "alta" and not (EXTREMO_MATERIAL_SIN_TOPE and impacto == "alta"):
        nivel, tope = "media", "falta confirmación bilateral"
    if (e.get("tabla_derivada") or {}).get("subordinada") and nivel == "alta" and not corroborada_caso:
        nivel, tope = "media", "tabla derivada: se prioriza la celda fuente"
    if e.get("en_hoja_de_variaciones") and nivel == "alta":
        nivel, tope = "media", "signo distinto en una hoja de variaciones: puede ser normal; revisar la hoja base"
    if e.get("cierre_exacto") and nivel == "alta" and evidencia != "corroborada":
        nivel, tope = "media", ("la celda cierra exacto con su total y sus componentes: un error de escala o de "
                                "dígito en ella rompería la suma")
    if e.get("lectura_dudosa") and nivel == "alta":
        nivel, tope = "media", ("sus celdas están entre las que el comienzo del informe declara como posiblemente "
                                "mal leídas: verificar la lectura contra el original antes de consultar al área")
    puntaje = (
        100 * NIVELES[nivel]
        + 10 * {"corroborada": 4, "exacta": 3, "patron": 2, "patron_debil": 1}.get(evidencia, 0)
        + 3 * {"alta": 3, "media": 2, "no_determinado": 2, "baja": 1}.get(impacto, 0)
        + NIVELES.get(rareza, 0)
    )
    return dict(
        prioridad=nivel,
        puntaje=puntaje,
        rareza=dict(nivel=rareza, detalle=detalle_rareza),
        impacto=dict(nivel=impacto, porcentaje=porcentaje, detalle=detalle_impacto),
        evidencia=dict(nivel=evidencia, detalle=detalle_evidencia),
        motivo_tope=tope,
        politica="v4: rareza, impacto y evidencia",
    )


def prioridad(h):
    if es_nota(h):
        return "nota"
    if es_contexto(h):
        return "contexto"
    return ejes(h)["prioridad"]


NOMBRE_EVIDENCIA = {
    "exacta": "aritmética o regla exacta",
    "corroborada": "corroborada",
    "patron": "patrón a verificar",
    "patron_debil": "patrón sin confirmación",
    "exploratoria": "exploratoria",
}


def texto_ejes(x):
    """Una línea legible con los tres ejes: la misma en todas las piezas."""
    imp = x["impacto"]
    impacto = {
        "no_determinado": f"no determinado ({imp['detalle']})",
        "no_aplica": f"no aplica ({imp['detalle']})",
    }.get(imp["nivel"], f"{imp['nivel']} ({imp['detalle']})")
    if imp.get("porcentaje") is not None and imp["porcentaje"] > 100:
        # Más del 100 % no es un error de cálculo: el desvío supera al propio total del cuadro
        # (el valor fuera de escala es más grande que lo que el total registra). Se dice así.
        impacto = (f"{imp['nivel']} (el desvío es mayor que el propio total del cuadro: equivale al "
                   f"{imp['detalle']}; indica un valor fuera de escala, no un peso real sobre el total)")
    texto = (
        f"Rareza: {x['rareza']['nivel']} ({x['rareza']['detalle']}). Impacto: {impacto}. "
        f"Evidencia: {NOMBRE_EVIDENCIA.get(x['evidencia']['nivel'], x['evidencia']['nivel'])} ({x['evidencia']['detalle']})."
    )
    if x.get("motivo_tope"):
        texto += f" Prioridad limitada a media: {x['motivo_tope']}."
    return texto


def identidad(h):
    e = campo(h, "evidencia", {}) or {}
    # No incorporar valores ni prioridad: así sus cambios siguen siendo comparables.
    return huella(
        [
            e.get("archivo_origen"),
            e.get("hoja"),
            e.get("celda"),
            str(e.get("periodo")),
            e.get("regla"),
            campo(h, "lente"),
            campo(h, "modo"),
            e.get("ubicaciones_excel"),
            e.get("columnas"),
            e.get("serie"),
            None if e.get("celda") or e.get("ubicaciones_excel") else campo(h, "descripcion"),
        ]
    )[:24]


# ---------------------------------------------------------------------------------------------
# Agrupación por causa común
# ---------------------------------------------------------------------------------------------

def _ref(hoja, celda):
    celda = str(celda)
    if "!" in celda:
        return celda
    return f"{hoja}!{celda}" if hoja else celda


def _ultima(ref):
    hoja, _, rango = str(ref).rpartition("!")
    return (hoja + "!" if hoja else "") + rango.split(":")[-1]


def _todas(ref):
    from openpyxl.utils.cell import column_index_from_string, coordinate_from_string, get_column_letter

    hoja, _, rango = str(ref).rpartition("!")
    partes = rango.split(":")
    try:
        (c1, f1), (c2, f2) = coordinate_from_string(partes[0]), coordinate_from_string(partes[-1])
        i1, i2 = sorted((column_index_from_string(c1), column_index_from_string(c2)))
        out = [f"{get_column_letter(c)}{f}" for c in range(i1, i2 + 1) for f in range(min(f1, f2), max(f1, f2) + 1)]
    except (ValueError, TypeError):
        out = partes
    return [(hoja + "!" if hoja else "") + c for c in out]


def celdas_propias(e):
    """Celdas que la señal afirma: la celda y el final de cada rango (el período del salto)."""
    hoja = e.get("hoja")
    out = set()
    if e.get("celda"):
        out.add(_ref(hoja, e["celda"]))
    for u in e.get("ubicaciones_excel") or []:
        out.add(_ultima(_ref(hoja, u)))
    return out


def referencias(e):
    """Todas las celdas citadas por la señal, para conservarlas en el caso."""
    hoja = e.get("hoja")
    out = []
    for u in [e.get("celda")] + list(e.get("ubicaciones_excel") or []) + list(e.get("celdas_participantes") or []):
        if u:
            out.extend(_todas(_ref(hoja, u)) if ":" in str(u) else [_ref(hoja, u)])
    return out


def _periodo(e):
    try:
        return int(float(str(e.get("periodo"))))
    except (TypeError, ValueError):
        return None


def _subordinada(e):
    return bool((e.get("tabla_derivada") or {}).get("subordinada"))


def _vinculadas(a, b):
    """Motivo por el que dos señales comparten causa, o None."""
    ea, eb = a.get("evidencia") or {}, b.get("evidencia") or {}
    if ea.get("archivo_origen") != eb.get("archivo_origen"):
        return None
    pa, pb = celdas_propias(ea), celdas_propias(eb)
    if pa & pb:
        return "misma celda"
    da, db = ea.get("tabla_derivada") or {}, eb.get("tabla_derivada") or {}
    sub_a, sub_b = _subordinada(ea), _subordinada(eb)
    if sub_a and not sub_b and set(da.get("celdas_fuente_ampliadas") or da.get("celdas_fuente") or []) & pb:
        return "tabla derivada de la celda fuente"
    if sub_b and not sub_a and set(db.get("celdas_fuente_ampliadas") or db.get("celdas_fuente") or []) & pa:
        return "tabla derivada de la celda fuente"
    misma_hoja_periodo = (
        ea.get("hoja") == eb.get("hoja") and _periodo(ea) is not None and _periodo(ea) == _periodo(eb)
    )
    if sub_a and sub_b and misma_hoja_periodo:
        if set(da.get("celdas_fuente") or []) & set(db.get("celdas_fuente_ampliadas") or []) or set(
            db.get("celdas_fuente") or []
        ) & set(da.get("celdas_fuente_ampliadas") or []):
            return "componente y total de una tabla derivada"
    if not sub_a and not sub_b and misma_hoja_periodo:
        if pa & set(eb.get("celdas_identidad") or []) or pb & set(ea.get("celdas_identidad") or []):
            return "componente, subtotal y total del mismo período"
    if ea.get("hoja") != eb.get("hoja"):
        return None
    if (
        ea.get("grupo_relacion")
        and ea.get("grupo_relacion") == eb.get("grupo_relacion")
        and str(ea.get("periodo")) == str(eb.get("periodo"))
    ):
        return "relación de equivalencia"
    ra, rb = ea.get("regla"), eb.get("regla")
    if {ra, rb} == {"anio_duplicado", "discontinuidad_anual"}:
        dup, dis = (ea, eb) if ra == "anio_duplicado" else (eb, ea)
        from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

        try:
            ca, fa = coordinate_from_string(dup["celda"])
            cb, fb = coordinate_from_string(dis["celda"])
            if (
                fa == fb
                and column_index_from_string(cb) == column_index_from_string(ca) + 1
                and float(dis["periodo"]) == float(dup["periodo"]) + 2
            ):
                return "año duplicado y su efecto"
        except (ValueError, TypeError, KeyError):
            pass
    if ra == rb == "conciliacion_aritmetica" and str(ea.get("periodo")) == str(eb.get("periodo")):
        # Un total aparece explícitamente en la otra igualdad, y ambas rompen por la misma magnitud.
        ua = f"{ea.get('hoja')}!{ea.get('celda')}"
        ub = f"{eb.get('hoja')}!{eb.get('celda')}"
        compartida = ua in eb.get("celdas_participantes", []) or ub in ea.get("celdas_participantes", [])
        da_, db_ = ea.get("diferencia_absoluta"), eb.get("diferencia_absoluta")
        if compartida and da_ is not None and db_ is not None and abs(da_ - db_) <= max(0.05, 0.001 * max(da_, db_)):
            return "misma diferencia en totales encadenados"
    return None


def _corroborada_por_propagacion(primary, grupo):
    """El desvío de la celda fuente se ve a la entrada y a la salida (p y p+1) en sus derivadas o totales."""
    ep = primary.get("evidencia") or {}
    p = _periodo(ep)
    if p is None or _subordinada(ep):
        return False
    periodos = {_periodo(x.get("evidencia") or {}) for x in grupo if x is not primary}
    return p in periodos and (p + 1) in periodos


def agrupar(hallazgos):
    hs = [registro(h) for h in hallazgos]
    controles = []
    exploratorias = []
    notas = []
    sin_controlar = []  # señales que el sondeo previo dejó sin controlar: ni casos ni contexto
    anuales = []  # detalle del contexto temporal: puede resultar la causa raíz de un caso
    for h in hs:
        if es_nota(h):
            (sin_controlar if (h.get("evidencia") or {}).get("sondeo") else notas).append(h)
        elif h.get("lente") == "rizoma" or (h.get("evidencia") or {}).get("naturaleza") == "exploratoria":
            exploratorias.append(h)
        elif es_contexto(h):
            for d in (h["evidencia"] or {}).get("detalle_contexto") or [h]:
                # Una variación anual puede volverse el caso principal: necesita su frase llana, como las demás.
                if isinstance(d, dict):
                    from services.reportes.lenguaje_llano import resumen_de

                    d = {**d, "resumen_llano": d.get("resumen_llano") or resumen_de(d)}
                anuales.append(d if isinstance(d, dict) else registro(d))
        else:
            controles.append(h)
    unidades = controles + anuales
    n_controles = len(controles)
    padres = list(range(len(unidades)))
    motivos = defaultdict(set)

    def raiz(i):
        while padres[i] != i:
            padres[i] = padres[padres[i]]
            i = padres[i]
        return i

    def unir(i, j, motivo):
        ri, rj = raiz(i), raiz(j)
        if ri != rj:
            padres[rj] = ri
            motivos[ri] |= motivos.pop(rj, set())
        motivos[ri].add(motivo)

    for i, a in enumerate(unidades):
        for j in range(i):
            motivo = _vinculadas(unidades[j], a)
            if motivo:
                unir(j, i, motivo)
    grupos = defaultdict(list)
    for i in range(len(unidades)):
        grupos[raiz(i)].append(i)
    casos = []
    absorbidas = set()
    for r, miembros in grupos.items():
        if not any(i < n_controles for i in miembros):
            continue
        absorbidas |= {i for i in miembros if i >= n_controles}
        es_control = {id(unidades[i]) for i in miembros if i < n_controles}
        grupo = [unidades[i] for i in miembros]
        fuentes = {id(h) for h in grupo if not _subordinada(h.get("evidencia") or {})}
        cache = {id(h): ejes(h) for h in grupo}

        def orden(h):
            e = h.get("evidencia") or {}
            return (
                0 if (not fuentes or id(h) in fuentes) else 1,
                cache[id(h)]["prioridad"] != "alta",
                e.get("regla") == "discontinuidad_anual",
                0 if id(h) in es_control else 1,
                -cache[id(h)]["puntaje"],
                -float(e.get("puntaje_prioridad", 0) or 0),
                identidad(h),
            )

        grupo.sort(key=orden)
        primary = grupo[0]
        corroborada = len(grupo) > 1 and _corroborada_por_propagacion(primary, grupo)
        ejes_caso = ejes(primary, corroborada_caso=corroborada)
        niveles = [ejes_caso["prioridad"]] + [
            cache[id(h)]["prioridad"]
            for h in grupo[1:]
            if id(h) in es_control and not _subordinada(h.get("evidencia") or {})
        ]
        nivel = max(niveles, key=lambda x: NIVELES.get(x, 0))
        cid = "caso-" + huella(sorted(identidad(h) for h in grupo))[:16]
        refs = list(dict.fromkeys(c for h in grupo for c in referencias(h.get("evidencia") or {})))
        casos.append(
            dict(
                root_cause_id=cid,
                primary_finding=primary,
                related_findings=grupo[1:],
                prioridad=nivel,
                ejes=ejes_caso,
                cantidad_senales=len(grupo),
                referencias=refs,
                vinculos=sorted(motivos.get(r, set())),
                causa_raiz_en_contexto=id(primary) not in es_control,
                criterio="Relación técnica inferida; la causa requiere revisión humana"
                if len(grupo) > 1
                else "Señal única: no se encontraron otras señales relacionadas",
            )
        )
    casos.sort(
        key=lambda c: (
            -NIVELES.get(c["prioridad"], 0),
            -c["ejes"]["puntaje"],
            -float((c["primary_finding"].get("evidencia") or {}).get("puntaje_prioridad", 0) or 0),
            c["root_cause_id"],
        )
    )
    contextos = defaultdict(list)
    for i, d in enumerate(anuales):
        if n_controles + i in absorbidas:
            continue
        e = d.get("evidencia") or {}
        contextos[(e.get("archivo_origen"), str(e.get("periodo")), e.get("hoja"), e.get("bloque_excel"))].append(d)
    contexto = []
    for key, ds in sorted(contextos.items(), key=lambda x: str(x[0])):
        archivo, periodo, hoja, cuadro = key
        contexto.append(
            dict(
                archivo=archivo,
                periodo=periodo,
                hoja=hoja,
                cuadro=cuadro,
                cantidad=len(ds),
                referencias=ds[:5],
                detalle=ds,
            )
        )
    total_contexto = sum(x["cantidad"] for x in contexto)
    senales_control = n_controles + len(absorbidas)
    # Dos maneras de contar que el informe explicita: por control (cada resumen de contexto cuenta
    # uno) y por señal de control (controles más las variaciones anuales que integran un caso).
    resumenes_contexto = sum(1 for h in hs if es_contexto(h))
    return dict(
        version=3,
        exploratorias=exploratorias,
        senales_exploratorias=len(exploratorias),
        casos=casos,
        contexto=contexto,
        notas=notas,
        notas_alcance=len(notas),
        sin_controlar=sin_controlar,
        senales_sin_controlar=len(sin_controlar),
        casos_revision=len(casos),
        senales_control=senales_control,
        senales_control_directas=n_controles,
        variaciones_en_casos=len(absorbidas),
        resumenes_contexto=resumenes_contexto,
        senales_contexto=total_contexto,
        senales_tecnicas=senales_control + total_contexto,
        prioridades=dict(Counter(c["prioridad"] for c in casos)),
        politica_prioridad="Una sola política para todas las piezas: rareza, impacto sobre el total del cuadro y evidencia.",
        aclaracion="Los casos agrupan evidencia relacionada; no equivalen a errores confirmados ni a causas demostradas.",
    )


# ---------------------------------------------------------------------------------------------
# Consultas: casos que comparten causa, agrupados para quien tiene que preguntar al área
# ---------------------------------------------------------------------------------------------
# Sólo agrupa la presentación: no cambia los casos, su prioridad ni lo que se detecta. Las reglas
# son de estructura (fila, período, celdas compartidas, misma diferencia), nunca de nombres.


def _fila_columna(celda):
    from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

    try:
        col, fila = coordinate_from_string(str(celda).rpartition("!")[2].split(":")[0])
        return fila, column_index_from_string(col)
    except (ValueError, TypeError):
        return None


def es_cierre(e):
    """Señal de un total que no cierra con sus componentes (trae total y diferencia)."""
    return _num(e.get("diferencia_absoluta")) is not None and _num(e.get("total_declarado")) is not None


def _misma_serie_contigua(ea, eb):
    """(a) Misma fila de la misma hoja y cuadro, misma regla, en períodos contiguos."""
    if es_cierre(ea) or es_cierre(eb):
        return False  # cada período de un cierre es una igualdad distinta: no es la misma causa
    if not (ea.get("hoja") and ea.get("celda") and eb.get("celda")):
        return False
    if (ea.get("archivo_origen"), ea.get("hoja"), ea.get("bloque_excel"), ea.get("regla")) != (
        eb.get("archivo_origen"), eb.get("hoja"), eb.get("bloque_excel"), eb.get("regla")
    ):
        return False
    pa, pb = _periodo(ea), _periodo(eb)
    fa, fb = _fila_columna(ea["celda"]), _fila_columna(eb["celda"])
    if pa is None or pb is None or not fa or not fb or fa[0] != fb[0]:
        return False
    return abs(pa - pb) == 1 and abs(fa[1] - fb[1]) == 1


def _arrastre_de_diferencia(ea, eb):
    """(b) Dos cierres del mismo período que fallan por la misma diferencia y comparten celdas.

    Devuelve (origen, efecto): el total menor (el subtotal de un componente) es el origen y el
    total mayor (el consolidado) es el efecto. None si no se cumple.
    """
    if not (es_cierre(ea) and es_cierre(eb)):
        return None
    if ea.get("archivo_origen") != eb.get("archivo_origen") or str(ea.get("periodo")) != str(eb.get("periodo")):
        return None
    da, db = abs(_num(ea["diferencia_absoluta"])), abs(_num(eb["diferencia_absoluta"]))
    tolerancia = max(
        _num(ea.get("tolerancia_absoluta")) or 0.05,
        _num(eb.get("tolerancia_absoluta")) or 0.05,
        0.001 * max(da, db),
    )
    if abs(da - db) > tolerancia:
        return None
    celdas_a = {_ref(ea.get("hoja"), c) for c in ea.get("celdas_participantes") or []} | celdas_propias(ea)
    celdas_b = {_ref(eb.get("hoja"), c) for c in eb.get("celdas_participantes") or []} | celdas_propias(eb)
    if not celdas_a & celdas_b:
        return None
    ta, tb = abs(_num(ea["total_declarado"])), abs(_num(eb["total_declarado"]))
    return ("a", "b") if ta <= tb else ("b", "a")


def agrupar_consultas(casos):
    """Agrupa casos por causa para presentarlos como una sola consulta al área.

    Devuelve una lista ordenada como los casos (la consulta toma el lugar de su mejor caso):
    {casos, origen, efectos, motivo, prioridad}. «origen» es el caso que conviene preguntar primero;
    «efectos», los casos que se explican por él (por ejemplo, el consolidado que no cierra por la
    misma diferencia que un componente).
    """
    n = len(casos)
    padres = list(range(n))
    motivo = {}
    efecto_de = {}

    def raiz(i):
        while padres[i] != i:
            padres[i] = padres[padres[i]]
            i = padres[i]
        return i

    def unir(i, j):
        ri, rj = raiz(i), raiz(j)
        if ri != rj:
            padres[max(ri, rj)] = min(ri, rj)

    evid = [(c["primary_finding"].get("evidencia") or {}) for c in casos]
    for i in range(n):
        for j in range(i):
            arrastre = _arrastre_de_diferencia(evid[j], evid[i])
            if arrastre:
                origen, efecto = (j, i) if arrastre[0] == "a" else (i, j)
                efecto_de[efecto] = origen
                unir(i, j)
                motivo[raiz(i)] = "misma diferencia en un subtotal y en el consolidado"
            elif _misma_serie_contigua(evid[j], evid[i]):
                unir(i, j)
                motivo.setdefault(raiz(i), "misma serie en períodos contiguos")
    grupos = defaultdict(list)
    for i in range(n):
        grupos[raiz(i)].append(i)
    out = []
    for r in sorted(grupos):
        miembros = grupos[r]
        efectos = [i for i in miembros if i in efecto_de]
        origenes = [i for i in miembros if i not in efecto_de]
        if len(miembros) > 1 and all(_periodo(evid[i]) is not None for i in miembros) and not efectos:
            origenes.sort(key=lambda i: _periodo(evid[i]))
        origen = origenes[0] if origenes else miembros[0]
        out.append(
            dict(
                casos=[casos[i] for i in sorted(miembros, key=lambda i: (_periodo(evid[i]) or 0, i))],
                origen=casos[origen],
                efectos=[casos[i] for i in efectos],
                motivo=motivo.get(raiz(r)) if len(miembros) > 1 else None,
                prioridad=max((casos[i]["prioridad"] for i in miembros), key=lambda x: NIVELES.get(x, 0)),
                posicion=min(miembros),
            )
        )
    out.sort(key=lambda g: g["posicion"])
    return out


def snapshot(hallazgos, prioridad_historica=False):
    out = []
    # Las señales sin archivo anotado no cuentan como otra fuente: si no, una carga de un solo
    # archivo se guardaba con nombres en unas corridas y como «fuente_unica» en otras, y la
    # comparación entre corridas daba todo por nuevo (informes 288 y 289).
    archivos = {str(a) for h in hallazgos if (a := (campo(h, "evidencia", {}) or {}).get("archivo_origen"))}
    for h in hallazgos:
        e = campo(h, "evidencia", {}) or {}
        for d in e.get("detalle_contexto") or [h]:
            ev = deepcopy(campo(d, "evidencia", {}) or {})
            for k in ("root_cause_id", "primary_finding", "related_findings", "prioridad_revision"):
                ev.pop(k, None)
            comparable = registro(d)
            if len(archivos) <= 1:
                comparable["evidencia"] = {**ev, "archivo_origen": "fuente_unica"}
            out.append(
                dict(
                    key=identidad(comparable),
                    prioridad=(
                        campo(d, "severidad", "media") if prioridad_historica and not es_contexto(d) else prioridad(d)
                    ),
                    hoja=ev.get("hoja"),
                    celda=ev.get("celda"),
                    regla=ev.get("regla"),
                    contenido=huella({**ev, "archivo_origen": "fuente_unica"} if len(archivos) <= 1 else ev),
                )
            )
    return sorted(out, key=lambda x: (x["key"], x["contenido"]))


def comparar(base, actual):
    # Multiconjuntos: conservar incluso señales con idéntica localización.
    a = defaultdict(list)
    b = defaultdict(list)
    for x in base.get("snapshot_senales", []):
        a[x["key"]].append(x)
    for x in actual.get("snapshot_senales", []):
        b[x["key"]].append(x)
    r = dict(persistentes=[], nuevos=[], desaparecidos=[], cambiaron_prioridad=[], cambiaron_evidencia=[])
    for k in sorted(set(a) | set(b)):
        aa = sorted(a[k], key=lambda x: x["contenido"])
        bb = sorted(b[k], key=lambda x: x["contenido"])
        for x, y in zip(aa, bb):
            r["persistentes"].append(y)
            if x["prioridad"] != y["prioridad"]:
                r["cambiaron_prioridad"].append(dict(**y, anterior=x["prioridad"]))
            if x["contenido"] != y["contenido"]:
                r["cambiaron_evidencia"].append(y)
        r["nuevos"].extend(bb[len(aa) :])
        r["desaparecidos"].extend(aa[len(bb) :])

    def fuentes(m):
        fs = (m.get("proveniencia") or {}).get("fuentes", [])
        return sorted(f.get("sha256_bruto") for f in fs if f.get("sha256_bruto"))

    fa, fb = fuentes(base), fuentes(actual)
    mismo_excel = fa == fb if fa and fb else None
    r.update(
        estado="comparado",
        conteos={k: len(v) for k, v in r.items()},
        base={
            k: base.get(k)
            for k in ("informe_id", "ejecucion_id", "version_motor", "version_codigo", "sha256_procesado")
        },
        actual={
            k: actual.get(k)
            for k in ("informe_id", "ejecucion_id", "version_motor", "version_codigo", "sha256_procesado")
        },
        mismo_excel=mismo_excel,
        mismos_datos=(
            base.get("sha256_procesado") == actual.get("sha256_procesado")
            if base.get("sha256_procesado") and actual.get("sha256_procesado")
            else None
        ),
        mismo_motor=(
            base.get("version_motor") == actual.get("version_motor")
            if base.get("version_motor") and actual.get("version_motor")
            else None
        ),
        mismo_codigo=(
            base.get("version_codigo") == actual.get("version_codigo")
            if base.get("version_codigo") and actual.get("version_codigo")
            else None
        ),
        mismas_opciones=base.get("opciones_tecnicas") == actual.get("opciones_tecnicas"),
        advertencia="Si cambiaron motor y fuente, el delta no permite atribuir por sí solo la causa del cambio.",
    )
    return r


def buscar_base(db, informe):
    import models

    # Misma persona, área, dominio y nombre de fuente, o el mismo informe.
    fuentes = set((informe.saneamiento or {}).get("archivos_origen") or [])
    q = db.query(models.EjecucionAnalisis).join(
        models.Informe, models.Informe.id == models.EjecucionAnalisis.informe_id
    )
    q = q.filter(
        models.Informe.usuario_id == informe.usuario_id,
        models.Informe.area_id == informe.area_id,
        models.Informe.dominio == informe.dominio,
    )
    for ej in q.order_by(models.EjecucionAnalisis.id.desc()).limit(100):
        m = dict(ej.manifiesto or {})
        nombres = {f.get("nombre_original") for f in (m.get("proveniencia") or {}).get("fuentes", [])}
        if ej.informe_id != informe.id and (not fuentes or fuentes != nombres):
            continue
        if "snapshot_senales" not in m:
            previo = db.get(models.Informe, ej.informe_id)
            # Sólo recuperar hallazgos actuales si corresponden a esa última ejecución.
            ultima = (getattr(previo, "devolucion", None) and previo.devolucion.cobertura or {}).get("manifiesto", {})
            if ultima.get("ejecucion_id") != ej.id:
                continue
            m["snapshot_senales"] = snapshot(previo.hallazgos, prioridad_historica=True)
            m["opciones_tecnicas"] = (previo.saneamiento or {}).get("opciones_tecnicas")
            m["snapshot_reconstruido"] = True
        m.update(informe_id=ej.informe_id, ejecucion_id=ej.id)
        return m
    return None
