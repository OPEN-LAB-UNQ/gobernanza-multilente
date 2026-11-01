"""Conciliación de jerarquías y relaciones repetidas, con tolerancias explícitas."""

import re
from collections import defaultdict
from itertools import combinations

from .comun import hallazgo, normalizar, numero, referencia
from .temporal import mapa_periodos, periodos_ambiguos

TOL_ABS = 0.05
TOL_REL = 0.001
MATERIAL = 0.002  # diferencias menores al 0,2 % son redondeo de la fuente, no un hallazgo


def coincide(a, b):
    return abs(a - b) <= TOL_ABS + TOL_REL * max(abs(a), abs(b))


def relacion_corroborada(buenas, comparables):
    """Series largas: 4 períodos y 80 %. Series de 4 períodos: basta que cierre en 3 (un solo desvío)."""
    if comparables == 4:
        return buenas >= 3
    return buenas >= 4 and buenas / max(comparables, 1) >= 0.8


SERIE_CORTA = (2, 3)  # períodos comparables que no alcanzan para corroborar una relación sola
REPETICIONES_MINIMAS = 3


def clave_relacion(total, componentes):
    """Identidad de una relación por sus celdas: la sangría y el total que precede pueden armar la misma."""
    return (total["archivo"], total["hoja"], tuple(total["celdas"]), tuple(tuple(x["celdas"]) for x in componentes))


def firma_relacion(total, componentes, origen):
    """La misma relación en otra hoja o cuadro del archivo: mismo origen, misma unidad y mismos rótulos del total
    y de sus componentes (por ejemplo, una provincia por hoja con los mismos cuadros)."""
    return (total["archivo"], origen, total.get("unidad"), normalizar(total["etiqueta"]),
            tuple(sorted(normalizar(x["etiqueta"]) for x in componentes)))


def pruebas_relacion(total, componentes):
    """Períodos comparables de total = suma de componentes: (i, declarado, esperado, cierra, posiciones, período,
    redondeo). `redondeo`: la diferencia entra en medio dígito de la resolución de los sumandos por su cantidad."""
    from .totales_cruzados import _tolerancia_suma

    salida = []
    mapas = [mapa_periodos(x) for x in componentes]
    for periodo, i in mapa_periodos(total).items():
        if any(periodo not in m for m in mapas):
            continue
        posiciones = [m[periodo] for m in mapas]
        declarado = numero(total["valores"][i])
        partes = [numero(x["valores"][j]) for x, j in zip(componentes, posiciones)]
        if declarado is None or any(x is None for x in partes):
            continue
        esperado = sum(partes)
        # Una compensación entre componentes no nulos también corrobora.
        # Sólo omitir períodos donde todos los importes sean insignificantes.
        if max(abs(declarado), abs(esperado), *(abs(x) for x in partes)) <= TOL_ABS:
            continue
        redondeo = abs(declarado - esperado) <= _tolerancia_suma(declarado, partes)
        salida.append((i, declarado, esperado, coincide(declarado, esperado), posiciones, periodo, redondeo))
    return salida


def estadistica_repeticion(firma, pruebas):
    """(firma, períodos que cierran, comparables, períodos que fallan) de una relación; en la comparación entre
    hojas, una diferencia dentro del redondeo de la resolución cuenta como cierre."""
    fallan = frozenset(p[5] for p in pruebas if not (p[3] or p[6]))
    return firma, len(pruebas) - len(fallan), len(pruebas), fallan


def corroboradas_por_repeticion(relaciones):
    """{índice: repeticiones que cierran} de las relaciones de serie corta corroboradas por repetición.

    `relaciones` es una lista de `estadistica_repeticion`. Con 2 o 3 períodos una relación no se corrobora sola;
    la corrobora la misma firma cerrando en todos sus períodos en al menos otras tres hojas o cuadros del
    archivo. Si la propia falla (a lo sumo en un período), esas repeticiones completas tienen que ser además el
    80 % de las demás y ninguna otra puede fallar en el mismo período: un error insertado en una hoja deja
    intactas las otras; una diferencia de criterio (una categoría no publicada ese año en varias hojas) no.
    Una repetición que no cierra en dos períodos o más es otro cuadro con los mismos rótulos (tasas debajo de
    importes, aunque la unidad no se haya leído): no cuenta ni a favor ni en contra."""
    por_firma = defaultdict(list)
    for k, (firma, _, _, _) in enumerate(relaciones):
        por_firma[firma].append(k)
    salida = {}
    for k, (firma, buenas, comparables, fallan) in enumerate(relaciones):
        if comparables not in SERIE_CORTA or buenas < comparables - 1:
            continue
        otras = [j for j in por_firma[firma]
                 if j != k and relaciones[j][2] >= 2 and relaciones[j][1] >= relaciones[j][2] - 1]
        completas = [j for j in otras if not relaciones[j][3]]
        if len(completas) < REPETICIONES_MINIMAS:
            continue
        if fallan and (len(completas) < 0.8 * len(otras) or any(fallan & relaciones[j][3] for j in otras)):
            continue
        salida[k] = len(completas)
    return salida


def es_total(s):
    return normalizar(s["etiqueta"]).split(" ")[0] in ("total", "subtotal") or bool(s.get("arrastre"))


# Suma parcial al pie de una página que sigue en la próxima («Transporte», «Van», «Suma y sigue»).
ARRASTRE_RE = re.compile(r"(?:transporte|van|suma y sigue|a transportar)[:.]*")
# Arrastre que abre la página siguiente: un componente más, y evidencia de que el «Transporte» de la
# página anterior era una suma parcial.
VIENE_RE = re.compile(r"^vienen?\s+de\b")
# Filas que pueden resumir el cuadro sin sumarse a él («Promedio por provincia», «Tasa de desocupación»).
# Son candidatas: sólo quedan fuera de un cierre si con ellas no cierra y sin ellas sí. «Media» sólo
# como promedio («Media tensión» es un rubro); «Tasa» sólo de un indicador («Tasa vial» es un recurso);
# nunca «Variación de existencias», que suma en las cuentas nacionales.
FILA_NO_SUMABLE = re.compile(
    r"^(?:(?:promedio|mediana|porcentaje|indice)\b|%"
    r"|media(?:$|\s+(?:por|de|del|anual|mensual|simple|aritmetica|ponderada|geometrica|movil)\b)"
    r"|tasas?\s+(?:de\s+|bruta\s+de\s+)?(?:variacion|crecimiento|desocupacion|desempleo|actividad|empleo|"
    r"mortalidad|natalidad|fecundidad|inflacion|interes|ocupacion|pobreza|indigencia|escolarizacion|"
    r"analfabetismo|participacion|incidencia|letalidad|prevalencia)\b)")


def es_arrastre(etiqueta):
    return bool(ARRASTRE_RE.fullmatch(normalizar(etiqueta)))


def _cierra(padre, hijos):
    """La relación total = suma de componentes se corrobora en suficientes períodos."""
    mapas = [mapa_periodos(h) for h in hijos]
    buenas = comparables = 0
    for periodo, i in mapa_periodos(padre).items():
        if any(periodo not in m for m in mapas):
            continue
        total = numero(padre["valores"][i])
        vs = [numero(h["valores"][m[periodo]]) for h, m in zip(hijos, mapas)]
        if total is None or any(v is None for v in vs):
            continue
        comparables += 1
        buenas += coincide(total, sum(vs))
    return relacion_corroborada(buenas, comparables)


def _pruebas(padre, hijos):
    """(cierra, valores de los hijos) en cada período comparable."""
    mapas = [mapa_periodos(h) for h in hijos]
    for periodo, i in mapa_periodos(padre).items():
        if any(periodo not in m for m in mapas):
            continue
        total = numero(padre["valores"][i])
        vs = [numero(h["valores"][m[periodo]]) for h, m in zip(hijos, mapas)]
        if total is not None and all(v is not None for v in vs):
            yield coincide(total, sum(vs)), vs


def _sin_sobrante(padre, componentes):
    """Un componente de más: con él la relación no cierra donde vale distinto de cero; sin él cierra en todos los
    períodos comparables (ADELANTOS TRANSITORIOS, categoría propia, leído por la sangría dentro de PRÉSTAMOS en
    el perfil de vencimientos de un ministerio: distinto de cero sólo en los primeros años). Se saca de la relación.
    Un error insertado no produce ese patrón: el total tendría que haber cambiado justo en el valor del
    componente, y un componente alterado deja de cerrar sin él donde no vale cero."""
    if len(componentes) < 3 or all(ok for ok, _ in _pruebas(padre, componentes)):
        return componentes
    for k in range(len(componentes)):
        resto = componentes[:k] + componentes[k + 1:]
        sin = list(_pruebas(padre, resto))
        if len(sin) >= 4 and all(ok for ok, _ in sin):
            return resto
    return componentes


def _suma_en_algun_periodo(padre, hijos):
    mapas = [mapa_periodos(h) for h in hijos]
    for periodo, i in mapa_periodos(padre).items():
        if any(periodo not in m for m in mapas):
            continue
        total = numero(padre["valores"][i])
        vs = [numero(h["valores"][m[periodo]]) for h, m in zip(hijos, mapas)]
        if total is not None and vs and all(v is not None for v in vs) and coincide(total, sum(vs)):
            return True
    return False


def _arrastre_final(filas):
    """La última serie del cuadro es un total de arrastre de página si se rotula «Transporte» (o «Van»,
    «Suma y sigue», «A transportar»), el cuadro no tiene otro total y hay evidencia de que es una suma
    parcial: su valor es la suma de las filas de arriba en al menos un período, o el cuadro trae una
    fila «Viene de…». Sin evidencia es un rubro («Transporte» como gasto). «Viene de…» no es un total:
    es un componente más."""
    if len(filas) < 3 or not es_arrastre(filas[-1]["etiqueta"]):
        return None
    if any(es_total(s) for s in filas[:-1]):
        return None
    previas = [s for s in filas[:-1] if not FILA_NO_SUMABLE.match(normalizar(s["etiqueta"]))]
    if any(VIENE_RE.match(normalizar(s["etiqueta"])) for s in previas) or _suma_en_algun_periodo(filas[-1], previas):
        return filas[-1]
    return None


def arrastre_en_filas(datos, columna):
    """Índice de la última fila de un cuadro de filas (dict) si es un total de arrastre, con el mismo
    criterio que `_arrastre_final`: rótulo de arrastre en `columna`, ningún otro total, y la suma de las
    filas de arriba en alguna columna numérica o una fila «Viene de…». Si no, None."""
    if not columna or len(datos) < 3:
        return None
    etiquetas = [normalizar((f or {}).get(columna)) for f in datos]
    if not es_arrastre(etiquetas[-1]) or any(e.split(" ")[0] in ("total", "subtotal") for e in etiquetas[:-1]):
        return None
    if any(VIENE_RE.match(e) for e in etiquetas[:-1]):
        return len(datos) - 1
    previas = [f for f, e in zip(datos[:-1], etiquetas[:-1]) if not FILA_NO_SUMABLE.match(e)]
    for clave, valor in datos[-1].items():
        if clave == columna:
            continue
        total = numero(valor)
        vs = [numero(f.get(clave)) for f in previas]
        if total is not None and vs and all(v is not None for v in vs) and coincide(total, sum(vs)):
            return len(datos) - 1
    return None


def relaciones_cuadro(series):
    grupos = defaultdict(list)
    for s in series:
        # Años sueltos junto a trimestres: cada frecuencia es su propia jerarquía; la serie anual y la
        # trimestral de una misma fila no se cortan entre sí la sangría.
        grupos[(s["archivo"], s["hoja"], s["cuadro"], s.get("frecuencia"))].append(s)
    for filas in grupos.values():
        arrastre = _arrastre_final(filas)
        if arrastre is not None:
            arrastre["arrastre"] = True
        paneles = None if es_total(filas[0]) else _paneles(filas)
        for padre, componentes, origen in _relaciones_paneles(paneles) if paneles else _relaciones_grupo(filas):
            dudosas = [x for x in componentes if FILA_NO_SUMABLE.match(normalizar(x["etiqueta"]))]
            if dudosas:
                # «Promedio por provincia» entre los componentes: se saca sólo si con ella el total no
                # cierra y sin ella sí. Una «Tasa vial» que suma queda adentro.
                sin = [x for x in componentes if x not in dudosas]
                if len(sin) >= 2 and not _cierra(padre, componentes) and _cierra(padre, sin):
                    componentes = sin
            yield padre, _sin_sobrante(padre, componentes), origen


def _paneles(filas):
    """«Total», sus componentes y, debajo, paneles con los mismos componentes («Varones», «Mujeres»), todos
    sin sangría ni rótulo de total: cada encabezado es el total de su panel, no de todo lo que sigue.
    Devuelve [(encabezado, componentes)] si la secuencia entera se reparte en dos o más paneles con los
    mismos rótulos en el mismo orden; si no, None."""
    if len(filas) < 6 or len({x["nivel"] for x in filas}) != 1:
        return None
    rotulos = [normalizar(x["etiqueta"]) for x in filas]
    # El primer componente reaparece en la segunda fila del panel siguiente.
    repetido = next((j for j in range(4, len(rotulos)) if rotulos[j] == rotulos[1]), None)
    if repetido is None or len(rotulos) % (repetido - 1):
        return None
    ancho = repetido - 1  # encabezado y sus componentes
    componentes = rotulos[1:ancho]
    paneles = []
    for k in range(0, len(filas), ancho):
        if rotulos[k + 1:k + ancho] != componentes or rotulos[k] in componentes:
            return None
        paneles.append((filas[k], filas[k + 1:k + ancho]))
    return paneles


def _relaciones_paneles(paneles):
    """Paneles sin total arriba (perfil de vencimientos: cada instrumento con su CAPITAL e INTERÉS): cada
    encabezado es el total de su panel; si el último panel es «TOTAL», su encabezado suma los de los demás
    paneles y cada componente suma los del mismo rótulo (TOTAL · CAPITAL = suma de los CAPITAL)."""
    for encabezado, componentes in paneles:
        yield encabezado, componentes, "panel_repetido"
    total, partes = paneles[-1], paneles[:-1]
    if es_total(total[0]) and len(partes) >= 2:
        yield total[0], [p[0] for p in partes], "total_de_paneles"
        for j, componente in enumerate(total[1]):
            yield componente, [p[1][j] for p in partes], "total_de_paneles"


def _relaciones_grupo(filas):
    for i, s in enumerate(filas):
        siguientes = []
        for otra in filas[i + 1 :]:
            if otra["nivel"] <= s["nivel"]:
                break
            siguientes.append(otra)
        if siguientes:
            nivel = min(x["nivel"] for x in siguientes)
            componentes = [x for x in siguientes if x["nivel"] == nivel and not es_total(x)]
            if len(componentes) >= 2:
                yield s, componentes, "jerarquia_por_sangria"
        if es_total(s):
            # Un total o subtotal puede encabezar su grupo sin sangría. Respetar el
            # límite del siguiente total y tomar un solo nivel para no
            # sumar también los detalles de cada componente.
            if i == 0 or normalizar(s["etiqueta"]).startswith("subtotal"):
                posteriores = []
                for otra in filas[i + 1:]:
                    if es_total(otra) or otra["nivel"] < s["nivel"]:
                        break
                    posteriores.append(otra)
                paneles = _paneles([s] + posteriores)
                if paneles:
                    for k, (encabezado, componentes) in enumerate(paneles):
                        yield encabezado, componentes, "total_precede_componentes" if k == 0 else "panel_repetido"
                elif posteriores:
                    nivel = min(x["nivel"] for x in posteriores)
                    componentes = [x for x in posteriores if x["nivel"] == nivel]
                    if len(componentes) >= 2:
                        yield s, componentes, "total_precede_componentes"
            previas = filas[:i]
            if normalizar(s["etiqueta"]).startswith("subtotal"):
                ultimo = max((j for j, x in enumerate(previas) if es_total(x)), default=-1)
                previas = previas[ultimo + 1 :]
            previas = [x for x in previas if not es_total(x)]
            if previas:
                nivel = min(x["nivel"] for x in previas)
                componentes = [x for x in previas if x["nivel"] == nivel]
                if len(componentes) >= 2:
                    yield s, componentes, "total_de_componentes_sin_doble_conteo"


def relaciones_entre_cuadros(series):
    # Candidatas por identidad del indicador, unidad y hoja. La igualdad debe
    # estar corroborada en >=80% de años comparables, nunca por el nombre solo.
    grupos = defaultdict(list)
    for s in series:
        if s.get("unidad") and len(mapa_periodos(s)) >= 4:
            grupos[(s["archivo"], s["hoja"], s["unidad"], normalizar(s["etiqueta"]))].append(s)
    for filas in grupos.values():
        if len(filas) > 12:
            continue  # sin búsqueda combinatoria indiscriminada
        for s in filas:
            otras = [
                o
                for o in filas
                if o["cuadro"] != s["cuadro"] and len(set(mapa_periodos(o)) & set(mapa_periodos(s))) >= 4
            ]
            for a, b in combinations(otras, 2):
                if a["cuadro"] != b["cuadro"]:
                    yield s, [a, b], "suma_entre_cuadros_corroborrada"
    # Indicador monetario y total repetido dentro de la misma hoja/unidad.
    for archivo, hoja in sorted({(s["archivo"], s["hoja"]) for s in series}):
        filas = [s for s in series if (s["archivo"], s["hoja"]) == (archivo, hoja)]
        for a, b in combinations(filas, 2):
            if (
                a["cuadro"] == b["cuadro"]
                or not a.get("unidad")
                or a["unidad"] != b.get("unidad")
                or len(set(mapa_periodos(a)) & set(mapa_periodos(b))) < 4
            ):
                continue
            if not (
                es_total(a)
                and es_total(b)
                or (es_total(a) and normalizar(b["etiqueta"]).startswith("en "))
                or (es_total(b) and normalizar(a["etiqueta"]).startswith("en "))
            ):
                continue
            yield a, [b], "indicador_repetido_entre_cuadros"


def analizar(series):
    out = []
    vistas = set()
    relaciones = []
    for total, componentes, origen in list(relaciones_cuadro(series)) + list(relaciones_entre_cuadros(series)):
        clave = clave_relacion(total, componentes)
        if clave in vistas:
            continue
        vistas.add(clave)
        relaciones.append((total, componentes, origen, pruebas_relacion(total, componentes)))
    # Una jerarquía visual no basta: exigir corroboración en otros períodos o, en series cortas, en la
    # misma relación repetida en otras hojas o cuadros del archivo.
    repetidas = corroboradas_por_repeticion(
        [estadistica_repeticion(firma_relacion(t, c, o), p) for t, c, o, p in relaciones])
    for k, (total, componentes, origen, pruebas) in enumerate(relaciones):
        buenas = sum(x[3] for x in pruebas)
        corroborada = relacion_corroborada(buenas, len(pruebas))
        repeticiones = None if corroborada else repetidas.get(k)
        if not corroborada and repeticiones is None:
            continue
        for i, declarado, esperado, ok, posiciones, _, redondeo in pruebas:
            # Por repetición entre hojas, una diferencia dentro del redondeo de la resolución no se señala:
            # las hojas chicas no entran en la tolerancia relativa que sí cubre a las grandes.
            if ok or (repeticiones and redondeo):
                continue
            diferencia = declarado - esperado
            relativo = abs(diferencia) / max(abs(esperado), abs(declarado), TOL_ABS)
            if relativo < MATERIAL:
                continue
            celdas = [referencia(total, i)] + [referencia(x, j) for x, j in zip(componentes, posiciones)]
            repeticion = (f" La misma relación cierra en todos sus períodos en otras {repeticiones} hojas o cuadros del archivo."
                          if repeticiones else "")
            out.append(
                hallazgo(
                    total,
                    i,
                    "conciliacion_aritmetica",
                    f"Total declarado {declarado:g}; reconstruido {esperado:g}; diferencia {diferencia:g} ({relativo * 100:.2f}% de la mayor magnitud)."
                    + repeticion,
                    110 if relativo >= 0.05 else 55,
                    dict(
                        total_declarado=declarado,
                        total_reconstruido=esperado,
                        diferencia_absoluta=abs(diferencia),
                        diferencia_con_signo=diferencia,
                        diferencia_porcentual=relativo * 100,
                        tolerancia_absoluta=TOL_ABS,
                        tolerancia_relativa=TOL_REL,
                        origen_relacion=origen,
                        periodos_corroborrados=buenas,
                        periodos_comparables=len(pruebas),
                        periodos_ambiguos_excluidos=periodos_ambiguos(total),
                        componentes=[
                            {"celda": referencia(x, j), "indicador": x["etiqueta"], "valor": x["valores"][j]}
                            for x, j in zip(componentes, posiciones)
                        ],
                        **({"corroboracion": "repeticion_en_otras_hojas", "repeticiones_que_cierran": repeticiones}
                           if repeticiones else {}),
                    ),
                    participantes=celdas,
                    lente="conciliador",
                    accion="Revisar el total y sus componentes con el área; la diferencia no identifica por sí sola cuál de ellos es incorrecto.",
                )
            )
    return out
