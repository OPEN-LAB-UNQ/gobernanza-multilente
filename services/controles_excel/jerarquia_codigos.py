"""Jerarquías declaradas por código: «1», «1.1», «1.1.1», «2», «2.1»… (o «A.1», «1.1.»).

Cuando la columna de rótulos (o una columna de códigos a su izquierda) numera las filas con códigos
jerárquicos, cada fila con código padre es el total de sus hijos inmediatos: los códigos que lo
extienden en un nivel («1.2» → «1.2.1», «1.2.2»). Una fila «Total» sin código, al pie, es el total
de los códigos de primer nivel que tiene arriba. El cierre se controla columna por columna con la
tolerancia de redondeo del cuadro.

No se afirma nada si la jerarquía es ambigua: códigos repetidos, un hijo antes que su padre, hijos
salteados («2.1.1», «2.1.3» sin «2.1.2») o un padre que no cierra en ninguna columna (puede ser un
desglose parcial, «de los cuales»). Esos padres se devuelven como no comprobados, con el motivo.
Tampoco se toman como jerarquía números de fila, años ni códigos planos: hace falta que haya
códigos de más de un nivel y al menos un padre con dos hijos en el propio cuadro.
"""

import re

from .comun import es_numero, normalizar
from .conciliacion import relacion_corroborada
from .modelo import es_total
from .transversal import NO_SUMABLE, _h, _tolerancia

# Código solo en la celda: «1», «1.2», «1.2.3», «1.2.», «A.1», «II.1».
CODIGO = r"(?:\d{1,3}|[A-Z]|[IVX]{1,5})(?:\.\d{1,3})*"
CODIGO_SOLO = re.compile(rf"^({CODIGO})\.?$")
# Código delante del rótulo: «1.2 Largo plazo», «1.2.1. Bonos», «A.1 Activo». Un código de un solo
# nivel con letra («A», «I») exige el punto, para no tomar la primera palabra de un rótulo.
CODIGO_PREFIJO = re.compile(rf"^({CODIGO})(\.?)\s+\S")
MINIMO_FILAS = 3
PROPORCION_CODIFICADA = 0.5
# Desglose parcial declarado en el rótulo de un hijo: el padre no es la suma de sus hijos listados.
# Debe coincidir con DESGLOSE de services/ocr_local.py y static/ocr.js.
DESGLOSE = re.compile(r"\b(?:de (?:las|los) cuales|del cual|de la cual|incluye|entre (?:ellos|ellas))\b")


def _texto_fila(c, r):
    """Los textos de la fila a la izquierda de los importes (código y rótulo), normalizados."""
    valores = _valores(c)
    primera = min((x["idx"] for x in valores), default=10 ** 6)
    return normalizar(" ".join(str(c["crudos"].get((r, x["idx"])) or "") for x in c["columnas"] if x["idx"] < primera))


def _codigo_celda(v, prefijo):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return str(v) if 0 <= v < 1000 else None
    if isinstance(v, float):
        return None  # «1.10» y «1.1» no se distinguen en un número: no es un código confiable
    t = str(v).strip()
    m = CODIGO_SOLO.match(t)
    if m:
        codigo = m.group(1)
    elif prefijo:
        m = CODIGO_PREFIJO.match(t)
        if not m:
            return None
        codigo = m.group(1)
        if "." not in codigo and not codigo.isdigit() and not m.group(2):
            return None
    else:
        return None
    return codigo


def codigos_filas(c):
    """{fila: código} leído de la columna de códigos o del comienzo del rótulo; {} si no hay jerarquía."""
    valores = _valores(c)
    if not valores:
        return {}
    primera = min(x["idx"] for x in valores)
    # Columnas de rótulos y de códigos: las de la izquierda de los importes. Una columna de códigos
    # («1», «1.1», «2») puede leerse como numérica; si está a la izquierda del rótulo, es de códigos.
    textuales = [x for x in c["columnas"] if x["idx"] < primera]
    salida = {}
    for r in c["filas"]:
        codigo = None
        for x in textuales:
            v = c["crudos"].get((r, x["idx"]))
            codigo = _codigo_celda(v, prefijo=False)
            if codigo:
                break
        if not codigo:
            # Primer texto de la fila: código pegado al rótulo («1.2 Largo plazo»).
            for x in textuales:
                v = c["crudos"].get((r, x["idx"]))
                if isinstance(v, str) and v.strip():
                    codigo = _codigo_celda(v, prefijo=True)
                    break
        if codigo:
            salida[r] = codigo
    return salida


def _hijos_inmediatos(codigo, codigos):
    prefijo = codigo + "."
    return [k for k in codigos if k.startswith(prefijo) and "." not in k[len(prefijo):]]


def _salteados(hijos):
    """Hijos con numeración incompleta («2.1.1», «2.1.3»): falta alguno entre ellos."""
    ultimos = [h.split(".")[-1] for h in hijos]
    if not all(u.isdigit() for u in ultimos):
        return False
    numeros = sorted(int(u) for u in ultimos)
    return numeros != list(range(numeros[0], numeros[0] + len(numeros))) or numeros[0] > 1


def relaciones(c):
    """(relaciones, no comprobadas): relaciones = [(fila padre, [filas hijas], origen)]."""
    por_fila = codigos_filas(c)
    filas_datos = [r for r in c["filas"] if not es_total(c["etiquetas"].get(r))]
    if len(por_fila) < MINIMO_FILAS or len(por_fila) < PROPORCION_CODIFICADA * max(1, len(filas_datos)):
        return [], []
    if not any("." in k for k in por_fila.values()):
        return [], []  # sólo números sueltos (filas numeradas, códigos planos): no es jerarquía
    sin_comprobar = []
    vistos = {}
    for r, k in por_fila.items():
        vistos.setdefault(k, []).append(r)
    repetidos = {k for k, rs in vistos.items() if len(rs) > 1}
    fila_de = {k: rs[0] for k, rs in vistos.items() if k not in repetidos}
    salida = []
    for k, r in fila_de.items():
        hijos = _hijos_inmediatos(k, fila_de)
        if len(hijos) < 2:
            continue
        filas_hijas = [fila_de[h] for h in hijos]
        motivo = None
        if any(fh < r for fh in filas_hijas):
            motivo = "algún código hijo aparece antes que su padre: el orden no permite leer la jerarquía"
        elif _salteados(hijos):
            motivo = f"la numeración de sus subcuentas está incompleta ({', '.join(sorted(hijos)[:4])}…)"
        elif any(x.startswith(k + ".") for x in repetidos):
            motivo = "hay códigos repetidos entre sus subcuentas"
        elif any(DESGLOSE.search(_texto_fila(c, fh)) for fh in filas_hijas):
            motivo = "sus subcuentas son un desglose parcial («de las cuales», «incluye»): no tienen por qué sumar el total"
        if motivo:
            sin_comprobar.append(dict(fila=r, codigo=k, motivo=motivo))
            continue
        # Filas sin código dentro del tramo del padre («Otros», «Ajuste»): con una sola columna no se
        # puede confirmar qué suma el padre.
        ultimo = max(fila_de[x] for x in fila_de if x.startswith(k + "."))
        sueltas = any(r < f <= ultimo and f not in por_fila for f in c["filas"])
        salida.append((r, sorted(filas_hijas), "jerarquia_por_codigo", sueltas))
    if not salida:
        if repetidos:
            sin_comprobar.append(dict(fila=None, codigo=", ".join(sorted(repetidos)[:3]),
                                      motivo="hay códigos repetidos: la jerarquía es ambigua"))
        return [], sin_comprobar
    # «Total» sin código al pie: suma de los códigos de primer nivel que tiene arriba, siempre que entre
    # ellos no haya filas con importes y sin código («Otros gastos»): esas también podrían sumar.
    valores = _valores(c)
    inicio = c["filas"][0] - 1
    for r in c["filas"]:
        if not es_total(c["etiquetas"].get(r)) or r in por_fila:
            continue
        superiores = [fila_de[k] for k in fila_de if inicio < fila_de[k] < r
                      and not any(k.startswith(p + ".") for p in fila_de if p != k)]
        sin_codigo = [f for f in c["filas"] if inicio < f < r and f not in por_fila and not es_total(c["etiquetas"].get(f))
                      and any(c["valores"].get((f, x["idx"])) is not None for x in valores)]
        if len(superiores) >= 2 and not sin_codigo:
            salida.append((r, sorted(superiores), "total_de_codigos_de_primer_nivel", False))
        inicio = r
    return salida, sin_comprobar


def _valores(c):
    """Columnas de importes: numéricas y, si hay columna de rótulos, a su derecha."""
    etiqueta = c.get("etiqueta_idx")
    return [x for x in c["columnas"] if x["numerica"] and not x.get("identificador") and not x.get("tiempo")
            and x.get("rol_confirmado") not in {"porcentaje", "indice"}
            and (etiqueta is None or x["idx"] > etiqueta)]


def _columnas(c):
    return [x for x in _valores(c) if not NO_SUMABLE.search(str(x.get("nombre") or ""))]


def _rotulo(c, r, por_codigo):
    etiqueta = c["etiquetas"].get(r) or ""
    codigo = por_codigo.get(r)
    if codigo and not normalizar(etiqueta).startswith(codigo.lower()):
        return f"{codigo} {etiqueta}".strip()
    return etiqueta or (codigo or f"fila {r}")


def analizar(c, excluir=frozenset()):
    """(hallazgos, cierres verificados, no comprobados) de la jerarquía por código del cuadro."""
    rels, pendientes = relaciones(c)
    if not rels:
        return [], [], _sin_comprobar(c, pendientes)
    por_codigo = codigos_filas(c)
    # Una columna entra al control sólo si en ella cierra al menos un padre: rendimientos, haberes
    # medios o razones («Dev/Cred») no suman aunque su nombre no lo diga.
    cols = []
    for x in _columnas(c):
        for padre, hijas, _, _ in rels:
            declarado = c["valores"].get((padre, x["idx"]))
            partes = [c["valores"].get((h, x["idx"])) for h in hijas]
            if declarado is not None and all(p is not None for p in partes) and \
                    abs(declarado - sum(partes)) <= _tolerancia([declarado] + partes, len(partes)):
                cols.append(x)
                break
    # De abajo hacia arriba: si una subcuenta no cierra con las suyas, el padre se compara también con
    # el valor que la subcuenta tendría (la suma de sus hijos). Si así cierra, la diferencia del padre
    # es la misma de la subcuenta y no se señala dos veces.
    profundidad = {r: (por_codigo[r].count(".") if r in por_codigo else -1) for r, *_ in rels}
    rels = sorted(rels, key=lambda x: -profundidad[x[0]])
    sueltas_de = {padre: sueltas for padre, _, _, sueltas in rels}
    reconstruido = {}
    pruebas = []  # (padre, hijas, origen, [(x, declarado, suma, dif, partes, ok, explicado)])
    for padre, hijas, origen, _ in rels:
        filas = []
        for x in cols:
            declarado = c["valores"].get((padre, x["idx"]))
            partes = [c["valores"].get((h, x["idx"])) for h in hijas]
            if declarado is None or any(p is None for p in partes):
                continue
            suma = sum(partes)
            dif = declarado - suma
            tol = _tolerancia([declarado] + partes, len(partes))
            ok = abs(dif) <= tol
            alternativas = [reconstruido.get((h, x["idx"]), p) for h, p in zip(hijas, partes)]
            explicado = not ok and alternativas != partes and abs(declarado - sum(alternativas)) <= tol
            filas.append((x, declarado, suma, dif, partes, ok, explicado))
            if not ok and not explicado:
                reconstruido[(padre, x["idx"])] = sum(alternativas)
        pruebas.append((padre, hijas, origen, filas))
    # Con una sola columna, la estructura se confirma con los demás padres del cuadro.
    padres_que_cierran = sum(1 for *_, f in pruebas if f and all(p[5] or p[6] for p in f))
    padres_comparables = sum(1 for *_, f in pruebas if f)
    hallazgos, cierres = [], []
    for padre, hijas, origen, filas in pruebas:
        if not filas:
            continue
        buenas = sum(p[5] or p[6] for p in filas)
        n = len(filas)
        if n == 1:
            otros = padres_que_cierran - (1 if buenas else 0)
            confirmada = buenas == 1 or (not sueltas_de.get(padre) and otros >= 2
                                         and otros >= 0.6 * max(1, padres_comparables - 1))
        elif n <= 4:
            confirmada = buenas >= max(1, n - 1)
        else:
            confirmada = relacion_corroborada(buenas, n)
        if not confirmada:
            que = "subcuentas" if origen == "jerarquia_por_codigo" else "códigos de primer nivel"
            pendientes.append(dict(fila=padre, codigo=por_codigo.get(padre) or c["etiquetas"].get(padre),
                                   motivo=f"no cierra con sus {len(hijas)} {que} en {n - buenas} de {n} columnas: "
                                          "puede ser un desglose parcial o faltar filas"))
            continue
        for x, declarado, suma, dif, partes, ok, explicado in filas:
            ref = c.ref(padre, x["idx"])
            componentes = [c.ref(h, x["idx"]) for h in hijas]
            if ok:
                cierres.append(dict(archivo=c["archivo"], hoja=c["hoja"], cuadro=c["cuadro"], periodo=x.get("nombre"),
                                    origen=origen, total=ref, componentes=componentes, diferencia=dif))
                continue
            if explicado or ref in excluir:
                continue  # la diferencia es la de una subcuenta, que ya se señala
            rel = abs(dif) / max(abs(suma), abs(declarado), 1e-9)
            nombres = ", ".join(_rotulo(c, h, por_codigo) for h in hijas[:4]) + ("…" if len(hijas) > 4 else "")
            que = "sus subcuentas" if origen == "jerarquia_por_codigo" else "los códigos de primer nivel"
            h = _h(c, padre, x["idx"], "conciliacion_aritmetica",
                   f"«{_rotulo(c, padre, por_codigo)}» declara {es_numero(declarado)} y {que} ({nombres}) suman "
                   f"{es_numero(suma)}: diferencia {es_numero(dif)} ({rel * 100:.3g} %). La jerarquía la declaran los "
                   f"códigos de las filas y cierra en {buenas} de {n} columnas.",
                   120 if rel >= 0.0001 else 70,
                   {"total_declarado": declarado, "total_reconstruido": suma, "diferencia_absoluta": abs(dif),
                    "diferencia_con_signo": dif, "diferencia_porcentual": rel * 100,
                    "tolerancia_redondeo": _tolerancia([declarado] + partes, len(partes)),
                    "origen_relacion": origen, "periodos_corroborrados": buenas, "periodos_comparables": n,
                    "componentes": [{"celda": cc, "indicador": _rotulo(c, f, por_codigo), "valor": v}
                                    for cc, f, v in zip(componentes, hijas, partes)]},
                   participantes=componentes[:40],
                   accion=(f"Revisar el total y {'sus subcuentas' if origen == 'jerarquia_por_codigo' else 'sus componentes'}; "
                           "la diferencia no identifica por sí sola cuál de ellos es incorrecto."),
                   lente="conciliador")
            h["evidencia"]["grupo_relacion"] = f"celda:{ref}"
            hallazgos.append(h)
    return hallazgos, cierres, _sin_comprobar(c, pendientes)


def _sin_comprobar(c, pendientes):
    salida = []
    for p in pendientes:
        donde = f"fila {p['fila']}" if p.get("fila") else "el cuadro"
        salida.append(dict(archivo=c["archivo"], hoja=c["hoja"], cuadro=c["cuadro"], concepto=p.get("codigo"),
                           donde=f"cierre de «{p.get('codigo')}» ({donde} de «{c['hoja']}»)", motivo=p["motivo"]))
    return salida
