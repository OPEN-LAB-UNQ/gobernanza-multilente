"""Consultas al área: los casos agrupados por causa y redactados como preguntas en lenguaje llano.

Es sólo presentación. Lee los casos de `casos_revision.agrupar` y su agrupación por causa
(`casos_revision.agrupar_consultas`); no cambia qué se detecta ni la prioridad. Cada consulta se
redacta con los valores de la evidencia, en formato es-AR, y termina en una pregunta para el área.
"""

from __future__ import annotations

import re
from collections import defaultdict

from services.reportes import lenguaje_llano
from services.reportes.formato import numero, unidad_legible

MAXIMO_PORTADA = 8
# Evidencia dura: se verifica en el propio archivo (una cuenta que no da, dos valores que se contradicen).
REGLAS_DURAS = {
    "conciliacion_aritmetica", "partes_no_suman_total", "total_columna_no_cierra", "componente_no_cierra_fila_y_columna",
    "columna_total_no_cierra", "total_sin_rotulo_no_cierra", "total_bloques_no_cierra", "total_omite_bloques",
    "saldo_final_no_cierra",
    "poblacion_implicita", "valor_fijo_distinto_de_formula", "formula_fuera_de_patron", "identidad_entre_cuadros",
    "devengado_supera_vigente", "pagado_supera_devengado", "pagado_supera_vigente", "devengado_supera_comprometido",
    "comprometido_supera_vigente", "credito_vigente_no_cierra_con_modificaciones",
}
MINIMO_PORTADA = 5

ETIQUETA_REGLA = {
    "porcentajes_como_cantidades": "unidad a confirmar",
    "conciliacion_aritmetica": "diferencia aritmética exacta",
    "pico_aislado": "valor que se aparta de su serie",
    "escala_extremo": "valor que se aparta de su serie (extremo)",
    "poblacion_implicita": "dos valores del mismo año que no son coherentes",
    "valor_fijo_distinto_de_formula": "valor cargado a mano donde otra celda usa fórmula",
    "formula_fuera_de_patron": "fórmula distinta del resto de la fila",
    "vacio_interior": "celda vacía dentro de una serie",
    "corte_temporal_conjunto": "salto simultáneo en varias series",
    "corte_temporal": "salto entre períodos fuera de lo habitual",
    "signo_aislado": "signo distinto del resto de la serie",
}


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _texto(v) -> str:
    return " ".join(str(v or "").split())


def _indicador(e) -> str:
    return _texto(e.get("indicador") or (e.get("ficha_serie") or {}).get("concepto") or e.get("serie") or "")


def _ambito(e, maximo=70) -> str:
    texto = _texto((e.get("ficha_serie") or {}).get("ambito"))
    return texto if len(texto) <= maximo else texto[: maximo - 1].rsplit(" ", 1)[0] + "…"


def _nombre(e) -> str:
    ind = _indicador(e)
    if ind:
        return f"«{ind}»"
    return f"la celda {_celda(e)}" if e.get("celda") else "la serie"


def _mayuscula(texto: str) -> str:
    """Mayúscula inicial, también después de «¿»."""
    for i, ch in enumerate(texto):
        if ch.isalpha():
            return texto[:i] + ch.upper() + texto[i + 1:]
    return texto


def _unidad(e) -> str:
    return unidad_legible((e.get("ficha_serie") or {}).get("unidad") or (e.get("materialidad") or {}).get("unidad") or "")


def _hoja(e) -> str:
    return f"«{e['hoja']}»" if e.get("hoja") else "el archivo"


def _periodo(e):
    try:
        return int(float(str(e.get("periodo"))))
    except (TypeError, ValueError):
        return None


def _celda(e, celda=None) -> str:
    celda = celda or e.get("celda")
    if not celda:
        return ""
    celda = str(celda)
    return celda.rpartition("!")[2] if "!" in celda else celda


def _referencia(e, celdas) -> str:
    """Hoja y celdas; un rango si las celdas son contiguas en una fila."""
    from services.casos_revision import _fila_columna

    celdas = [c for c in dict.fromkeys(_celda(e, c) for c in celdas) if c]
    if not celdas:
        return e.get("hoja") or "—"
    hoja = e.get("hoja")
    pos = [_fila_columna(c) for c in celdas]
    if len(celdas) >= 2 and all(pos) and len({p[0] for p in pos}) == 1:
        cols = sorted(p[1] for p in pos)
        if cols == list(range(cols[0], cols[0] + len(cols))):
            orden = sorted(celdas, key=lambda c: _fila_columna(c)[1])
            return f"{hoja}!{orden[0]}:{orden[-1]}" if hoja else f"{orden[0]}:{orden[-1]}"
    return (f"{hoja}!" if hoja else "") + ", ".join(celdas)


def _enumerar(items) -> str:
    items = [x for x in items if x]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def _sin_prefijo(descripcion: str) -> str:
    """Quita «Hoja!B5 · indicador · 2018: » o «[Hoja · cuadro 12] » del comienzo de una descripción."""
    texto = _texto(descripcion)
    texto = re.sub(r"^\[[^\]]{1,120}\]\s*", "", texto)
    texto = re.sub(r"^[^:]{1,160}![A-Z]{1,3}\d+(?::[A-Z]{1,3}\d+)?(?: · [^:]{0,120})?:\s*", "", texto)
    return texto


def _primera_oracion(texto: str, maximo: int = 260) -> str:
    texto = _texto(texto)
    m = re.search(r"(?<=[a-záéíóúñ0-9)%»])\.\s+(?=[A-ZÁÉÍÓÚÑ¿])", texto)
    if m:
        texto = texto[: m.start()]
    texto = texto.rstrip(". ")
    if len(texto) > maximo:
        texto = texto[: maximo - 1].rsplit(" ", 1)[0] + "…"
    return texto


def _con_unidad(e) -> str:
    u = _unidad(e)
    return f" ({u})" if u else ""


# ---------------------------------------------------------------------------------------------
# Redacción por tipo de señal
# ---------------------------------------------------------------------------------------------


def _cierre(g):
    o = g["origen"]["primary_finding"].get("evidencia") or {}
    per = _periodo(o)
    total, recon, dif = _num(o.get("total_declarado")), _num(o.get("total_reconstruido")), _num(o.get("diferencia_absoluta"))
    ceros = [_texto(c.get("indicador")) for c in o.get("componentes") or [] if _num(c.get("valor")) == 0]
    ambito = _ambito(o)
    nombre = _nombre(o) + (f" ({ambito})" if ambito else "") + (f" {per}" if per is not None else "")
    componentes = o.get("componentes") or []
    unico = componentes[0] if len(componentes) == 1 else None
    if unico:
        hecho = (f"{nombre} figura en {numero(total)}, pero el mismo concepto en {_celda(o, unico.get('celda'))}"
                 + (f" («{_texto(unico.get('indicador'))}»)" if _texto(unico.get("indicador")) else "")
                 + f" es {numero(recon)}")
    else:
        hecho = f"{nombre} figura en {numero(total)}, pero sus componentes suman {numero(recon)}"
    if unico:
        pregunta = "¿cuál de los dos valores es el correcto?"
    elif ceros:
        hecho += f" ({_enumerar([c + ' en 0' for c in ceros])})"
        pregunta = f"¿falta cargar {_enumerar(ceros)} o el total está mal?"
    else:
        pregunta = "¿el total está mal o falta (o sobra) algún componente?"
    efectos = []
    for c in g["efectos"]:
        x = c["primary_finding"].get("evidencia") or {}
        amb = _ambito(x)
        efectos.append(_nombre(x) + (f" ({amb})" if amb else "") + (f" {_periodo(x)}" if _periodo(x) is not None else ""))
    efecto = (f" Esa misma diferencia ({numero(dif)}) hace que {_enumerar(efectos)} tampoco cierre." if efectos else "")
    resumen = f"En {_hoja(o)}, {hecho}: {pregunta}{efecto}"
    que_pasa = f"{hecho}; diferencia {numero(dif)}" + _con_unidad(o) + "." + efecto
    celdas = [o.get("celda")] + [c for c in o.get("celdas_participantes") or [] if _celda(o, c) != o.get("celda")]
    donde = (f"{_referencia(o, [o.get('celda')])} (total); "
             + ("mismo concepto en " if unico else "componentes en ") + _referencia(o, celdas[1:]))
    for c in g["efectos"]:
        x = c["primary_finding"].get("evidencia") or {}
        donde += f"; el consolidado que tampoco cierra está en {_referencia(x, [x.get('celda')])}"
    preguntar = _mayuscula(pregunta)
    if ceros and not unico:
        preguntar += f" Si {_enumerar(ceros)} no corresponde{'n' if len(ceros) > 1 else ''}, el total debería ser {numero(recon)}."
    return resumen, que_pasa, donde, preguntar


def _valores_serie(evidencias):
    valores = {}
    for e in evidencias:
        p = _periodo(e)
        if p is None:
            continue
        for desplazamiento, clave in ((-1, "valor_anterior"), (0, "valor_observado"), (1, "valor_posterior")):
            v = _num(e.get(clave))
            if v is not None:
                valores.setdefault(p + desplazamiento, v)
    return dict(sorted(valores.items()))


def _compensacion(e):
    """Si otros componentes compensan el movimiento con un total que cierra: el hecho y la pregunta."""
    c = e.get("compensacion") or {}
    componentes = [x for x in c.get("componentes") or [] if _num(x.get("cambio")) is not None]
    if not componentes or _num(c.get("crecimiento_total")) is None:
        return None, None
    per = _periodo(e) or "ese período"
    movimientos = _enumerar([f"«{x['etiqueta']}» {'sube' if x['cambio'] > 0 else 'baja'} {numero(abs(x['cambio']))}"
                             for x in componentes])
    ritmo = 100 * (c["crecimiento_total"] - 1)
    hecho = (f"En {per} {movimientos}, fuera del ritmo del total ({'+' if ritmo >= 0 else ''}{numero(ritmo, 0)} %), "
             "y el total cierra")
    return hecho, f"¿se reasignaron partidas entre categorías en {per}?"


def _serie(g):
    evs = [c["primary_finding"].get("evidencia") or {} for c in g["casos"]]
    e = evs[0]
    valores = _valores_serie(evs)
    observados = sorted({_periodo(x) for x in evs if _periodo(x) is not None})
    pasos = [f"{numero(v)} ({p})" for p, v in valores.items()]
    if len(pasos) >= 2:
        recorrido = f"pasa de {pasos[0]} a " + _enumerar(pasos[1:])
    else:
        recorrido = "figura en " + (pasos[0] if pasos else "un valor fuera de su serie")
    factores = [_num(x.get("factor_escala")) for x in evs if _num(x.get("factor_escala"))]
    factor = max(factores) if factores else None
    veces = f"; unas {numero(round(factor), 0)} veces fuera de la escala de la serie" if factor and factor >= 2 else ""
    extremo = any(x.get("regla") == "escala_extremo" for x in evs)
    hecho = f"{_nombre(e)}{_con_unidad(e)} {recorrido}"
    if extremo:
        pregunta = "¿ese dato está en otra escala o corresponde a un período parcial?"
    elif len(observados) > 1:
        pregunta = "¿esos valores se cargaron en otra escala o con la coma corrida?"
    else:
        pregunta = "¿ese valor se cargó en otra escala o con la coma corrida?"
    compensa, reasignacion = _compensacion(e)
    if reasignacion:
        pregunta = reasignacion
    resumen = f"En {_hoja(e)}, {hecho}: {pregunta}"
    que_pasa = f"{hecho}{veces}." + (f" {compensa}." if compensa else "")
    ficha = e.get("ficha_serie") or {}
    por_periodo = dict(zip(ficha.get("periodos") or [], ficha.get("celdas") or []))
    celdas = [por_periodo.get(p) for p in observados] if por_periodo else []
    celdas = [c for c in celdas if c] or [x.get("celda") for x in evs]
    donde = _referencia(e, celdas)
    if len(observados) > 1:
        donde += f" ({len(observados)} años seguidos de la misma fila: {_enumerar([str(p) for p in observados])})"
    amb = _ambito(e)
    if amb:
        donde += f"; cuadro «{amb}»"
    if reasignacion:
        preguntar = _mayuscula(reasignacion) + " Si no, ¿ese valor se cargó en otra escala o con la coma corrida?"
    else:
        preguntar = _mayuscula(pregunta) + " Si el dato es correcto, ¿qué explica el cambio (cobertura, metodología, reclasificación)?"
    return resumen, que_pasa, donde, preguntar


def _poblacion(g):
    e = g["origen"]["primary_finding"].get("evidencia") or {}
    per = _periodo(e)
    vecinos = [numero(v, 0) for v in e.get("poblacion_vecinos") or [] if _num(v) is not None]
    rel = _celda(e, e.get("celda_relacionada"))
    hecho = (
        f"{_nombre(e)} {per if per is not None else ''} ({numero(_num(e.get('valor_observado')))}) no es coherente con "
        f"el importe del mismo año{f' (celda {rel})' if rel else ''}: la población que resulta de dividirlos es "
        f"{numero(_num(e.get('poblacion_implicita')), 0)}"
        + (f", contra {_enumerar(vecinos)} en los años vecinos" if vecinos else "")
    ).replace("  ", " ")
    pregunta = "¿cuál de los dos valores está mal cargado?"
    resumen = f"En {_hoja(e)}, {hecho}: {pregunta}"
    donde = _referencia(e, [e.get("celda"), e.get("celda_relacionada")])
    return resumen, hecho + ".", donde, "¿Cuál de los dos valores está mal cargado (importe o valor por persona)? Uno de los dos puede estar en otra escala."


def _valor_fijo(g):
    e = g["origen"]["primary_finding"].get("evidencia") or {}
    ref = _celda(e, e.get("celda_formula_de_referencia"))
    hecho = (
        f"{e.get('celda')} es un valor cargado a mano ({numero(_num(e.get('valor_fijo')))}); "
        f"con la misma fórmula que usa {ref or 'otra celda de la fila'} ({e.get('formula_trasladada') or 'la suma de sus componentes'}) "
        f"daría {numero(_num(e.get('valor_segun_formula')))}"
        f" (diferencia {numero(abs(_num(e.get('diferencia_con_signo')) or 0))})"
    )
    pregunta = "¿se cargó a mano a propósito o quedó desactualizado?"
    resumen = f"En {_hoja(e)}, {hecho}: {pregunta}"
    donde = _referencia(e, [e.get("celda")]) + (f"; fórmula de referencia en {ref}" if ref else "")
    return resumen, hecho + ".", donde, "¿El valor se cargó a mano a propósito? Si no, corregirlo o usar la misma fórmula."


def _formula(g):
    e = g["origen"]["primary_finding"].get("evidencia") or {}
    eje = "columna" if e.get("eje") == "columna" else "fila"
    celda = str(e.get("celda") or "")
    referencia = e.get("formula_referencia") or lenguaje_llano.patron_en_celda(e.get("patron_esperado"), celda)
    caso, _ = lenguaje_llano.clasificar(str(e.get("formula") or ""), referencia or "", eje)
    hecho = f"{celda}: {e.get('formula') or 'sin texto'}" + (f"; resto de la {eje}: {referencia}" if referencia else "")
    pregunta = ("¿el cambio de criterio fue intencional y está autorizado? ¿Desde cuándo rige?" if caso == "metodo"
                else "¿es intencional o quedó una referencia corrida o un rango incompleto?")
    resumen = f"En {_hoja(e)}, la fórmula de {celda} se aparta del patrón del resto de la {eje}: {pregunta}"
    return resumen, hecho + ".", _referencia(e, [celda]), _mayuscula(pregunta)


def _vacio(g):
    e = g["origen"]["primary_finding"].get("evidencia") or {}
    per = _periodo(e)
    anterior, posterior = _num(e.get("valor_anterior")), _num(e.get("valor_posterior"))
    if anterior == posterior == 0:
        hecho = f"{_nombre(e)} {per if per is not None else ''} está vacío, con 0 en el período anterior y en el siguiente"
    else:
        hecho = f"{_nombre(e)} {per if per is not None else ''} está vacío entre {numero(anterior)} y {numero(posterior)}"
    hecho = hecho.replace("  ", " ")
    pregunta = "¿significa cero, dato no disponible o falta cargarlo?"
    return f"En {_hoja(e)}, {hecho}: {pregunta}", _mayuscula(hecho) + ".", _referencia(e, [e.get("celda")]), _mayuscula(pregunta)


def _general(g):
    h = g["origen"]["primary_finding"]
    e = h.get("evidencia") or {}
    hecho = _primera_oracion(_sin_prefijo(h.get("descripcion")))
    per = _periodo(e)
    if e.get("regla") in {"corte_temporal_conjunto", "corte_temporal"} or g["origen"].get("causa_raiz_en_contexto"):
        pregunta = (f"¿hubo en {per} un cambio de cobertura, metodología o escala que lo explique?" if per
                    else "¿hubo un cambio de cobertura, metodología o escala que lo explique?")
    else:
        pregunta = "¿pueden confirmar ese valor con la fuente?"
    compensa, reasignacion = _compensacion(e)
    if reasignacion:
        pregunta = reasignacion
    lugar = _referencia(e, [e.get("celda")]) if e.get("celda") else (
        ", ".join(e.get("ubicaciones_excel") or []) or (e.get("hoja") or "—"))
    prefijo = f"En {_hoja(e)}, " if e.get("hoja") else ""
    cuerpo = hecho[0].lower() + hecho[1:] if prefijo and hecho[:2] != hecho[:2].upper() else hecho
    que_pasa = _mayuscula(hecho).rstrip(".") + "." + (f" {compensa}." if reasignacion else "")
    return f"{prefijo}{cuerpo}: {pregunta}", que_pasa, lugar, _mayuscula(pregunta)


def _unidad_porcentual(g):
    h = g["origen"]["primary_finding"]
    e = h.get("evidencia") or {}
    hecho = lenguaje_llano.resumen_llano(h)
    pregunta = "¿Estas columnas contienen cantidades o porcentajes?"
    accion = "Confirmar la unidad y corregir el encabezado o la interpretación; no cambiar las cifras sin contrastar la fuente."
    return (f"En {_hoja(e)}, {hecho} {pregunta}", str(h.get("descripcion") or hecho),
            _referencia(e, [e.get("celda")]), f"{pregunta} {accion}")


def redactar(g) -> dict:
    """Texto de una consulta: resumen de portada, qué pasa, dónde, qué preguntar y etiqueta."""
    from services.casos_revision import NOMBRE_EVIDENCIA, es_cierre

    e = g["origen"]["primary_finding"].get("evidencia") or {}
    regla = e.get("regla")
    if es_cierre(e) and _num(e.get("total_reconstruido")) is not None:
        partes = _cierre(g)
    elif regla in {"pico_aislado", "escala_extremo"}:
        partes = _serie(g)
    elif regla == "poblacion_implicita":
        partes = _poblacion(g)
    elif regla == "valor_fijo_distinto_de_formula":
        partes = _valor_fijo(g)
    elif regla == "formula_fuera_de_patron":
        partes = _formula(g)
    elif regla == "vacio_interior":
        partes = _vacio(g)
    elif regla == "porcentajes_como_cantidades":
        partes = _unidad_porcentual(g)
    else:
        partes = _general(g)
    resumen, que_pasa, donde, preguntar = (lenguaje_llano.traducir_en_texto(x) for x in partes)
    for relacion in e.get("conciliaciones") or []:
        if relacion.get("regla") == "poblacion_implicita" and _num(relacion.get("poblacion_implicita")) is not None:
            vecinos = [numero(v, 0) for v in relacion.get("poblacion_vecinos") or [] if _num(v) is not None]
            que_pasa += (f" Comprobación cruzada: la población implícita es {numero(relacion['poblacion_implicita'], 0)}"
                         + (f" frente a {_enumerar(vecinos)} en los años vecinos" if vecinos else "")
                         + (f" ({', '.join(relacion.get('celdas_participantes') or [])})" if relacion.get("celdas_participantes") else "")
                         + "; confirmar unidades y cobertura.")
    etiqueta = ETIQUETA_REGLA.get(regla) or NOMBRE_EVIDENCIA.get(g["origen"]["ejes"]["evidencia"]["nivel"]) or "señal a verificar"
    if g.get("motivo"):
        etiqueta += f"; agrupa {len(g['casos'])} casos ({g['motivo']})"
    titulo = (e.get("hoja") or "Archivo") + (f" · {_indicador(e)}" if _indicador(e) else "")
    tipo = "no_cierra" if (es_cierre(e) or regla in REGLAS_DURAS) else "para_preguntar"
    if e.get("formula"):
        detalle_tecnico = f"fórmula en el archivo: {e['formula']}"
    elif e.get("formula_de_referencia"):
        detalle_tecnico = (f"fórmula de referencia en el archivo ({e.get('celda_formula_de_referencia') or 'misma línea'}): "
                           f"{e['formula_de_referencia']}")
    else:
        detalle_tecnico = None
    return dict(titulo=titulo, resumen=resumen, que_paso=lenguaje_llano.resumen_de(g["origen"]["primary_finding"]),
                que_pasa=_mayuscula(que_pasa), donde=donde, preguntar=preguntar, etiqueta=etiqueta,
                prioridad=g["prioridad"], tipo=tipo, detalle_tecnico=detalle_tecnico)


RUPTURAS = {"pico_aislado", "escala_extremo", "salto_escala_final", "corte_temporal", "corte_temporal_conjunto"}
MINIMO_HOJAS_TRANSVERSAL = 3


def _transversales(lista, revision):
    """Rupturas el mismo año en varias hojas: una consulta común que va primero.

    Si en un mismo período hay saltos o cambios de escala en tres o más hojas, es más probable una
    causa común (metodología, cobertura, clasificación) que un error en cada hoja. Esas consultas se
    reúnen en una sola; sus casos quedan como evidencia de ella.
    """
    from services.casos_revision import NIVELES

    por_periodo = defaultdict(list)
    for c in lista:
        e = c["origen"]["primary_finding"].get("evidencia") or {}
        # Una fila que oscila varios años seguidos no es un salto de un año: queda como consulta propia.
        periodos = {_periodo(x["primary_finding"].get("evidencia") or {}) for x in c["casos"]}
        if e.get("regla") in RUPTURAS and _periodo(e) is not None and e.get("hoja") and len(periodos) == 1:
            por_periodo[_periodo(e)].append(c)
    contexto = defaultdict(int)
    for g in revision.get("contexto") or []:
        try:
            contexto[int(float(str(g.get("periodo"))))] += int(g.get("cantidad") or 0)
        except (TypeError, ValueError):
            continue
    nuevas, usadas = [], set()
    for per, miembros in por_periodo.items():
        hojas = list(dict.fromkeys((c["origen"]["primary_finding"].get("evidencia") or {}).get("hoja") for c in miembros))
        if len(hojas) < MINIMO_HOJAS_TRANSVERSAL:
            continue
        miembros.sort(key=lambda c: -NIVELES.get(c["prioridad"], 0))
        casos = [x for c in miembros for x in c["casos"]]
        detalle = []
        for c in miembros:
            e = c["origen"]["primary_finding"].get("evidencia") or {}
            detalle.append(f"«{e.get('hoja')}»" + (f" · {_nombre(e)}" if _indicador(e) else ""))
        en_contexto = (f" Además, ese año hay {contexto[per]} variaciones anuales que quedaron como contexto."
                       if contexto.get(per) else "")
        pregunta = f"¿cambió en {per} la metodología, la cobertura o la clasificación de los datos?"
        hecho = f"en {per} hay saltos o cambios de escala en {len(hojas)} hojas a la vez ({_enumerar([f'«{h}»' for h in hojas])})"
        nuevas.append(dict(
            casos=casos, origen=miembros[0]["origen"], efectos=[], motivo=f"mismo período en {len(hojas)} hojas",
            prioridad=max((c["prioridad"] for c in miembros), key=lambda x: NIVELES.get(x, 0)),
            posicion=min(c.get("posicion", 0) for c in miembros),
            titulo=f"{len(hojas)} hojas · {per}", resumen=f"{_mayuscula(hecho)}: {pregunta}",
            que_paso=(f"En {per} cambian de escala a la vez: {_enumerar(detalle)}. Que pase en varias hojas el mismo año "
                      "sugiere una causa común antes que un error en cada una."),
            que_pasa=_mayuscula(hecho) + "." + en_contexto + " Cada caso se detalla en el anexo como evidencia de esta consulta.",
            donde="; ".join(c["donde"] for c in miembros), preguntar=_mayuscula(pregunta)
            + " Si no hubo un cambio común, cada hoja se revisa por separado (ver los casos en el anexo).",
            etiqueta=f"patrón común en {len(hojas)} hojas", tipo="para_preguntar", detalle_tecnico=None,
            transversal=True, periodo=per, hojas=len(hojas)))
        usadas |= {id(c) for c in miembros}
    nuevas.sort(key=lambda c: (-NIVELES.get(c["prioridad"], 0), -c["hojas"], -c["periodo"]))
    return nuevas + [c for c in lista if id(c) not in usadas]


def consultas(revision) -> list[dict]:
    """Consultas redactadas, en el orden de prioridad de sus casos."""
    from services.casos_revision import agrupar_consultas

    out = []
    for g in agrupar_consultas(revision["casos"]):
        try:
            texto = redactar(g)
        except Exception:  # noqa: BLE001 - la redacción nunca puede impedir el informe
            h = g["origen"]["primary_finding"]
            texto = dict(titulo=(h.get("evidencia") or {}).get("hoja") or "Caso", resumen=_texto(h.get("descripcion")),
                         que_pasa=_texto(h.get("descripcion")), donde="—", preguntar="¿Pueden confirmarlo con la fuente?",
                         etiqueta="señal a verificar", prioridad=g["prioridad"], tipo="para_preguntar",
                         que_paso=lenguaje_llano.resumen_de(h), detalle_tecnico=None)
        out.append({**g, **texto})
    return _transversales(out, revision)


def portada(lista: list[dict]) -> tuple[list[dict], list[dict]]:
    """Las consultas de la primera página (5 a 8, primero las de prioridad alta) y el resto."""
    # Primero lo que no cierra (verificable en el archivo); después lo que conviene preguntar.
    lista = [c for c in lista if c.get("tipo") == "no_cierra"] + [c for c in lista if c.get("tipo") != "no_cierra"]
    altas = [c for c in lista if c["prioridad"] == "alta"]
    n = min(MAXIMO_PORTADA, max(len(altas), MINIMO_PORTADA))
    return lista[:n], lista[n:]
