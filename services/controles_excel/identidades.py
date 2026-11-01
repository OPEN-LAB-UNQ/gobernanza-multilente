"""Series repetidas en dos cuadros de la misma hoja que dejan de coincidir.

En estos informes el mismo importe aparece en más de una apertura: por ejemplo «Obras sociales»
en el cuadro por categorías y «OO.SS» en el cuadro por clases. La igualdad no se supone por el
nombre: se acepta sólo si los valores coinciden en casi todos los períodos. Entonces un año en
el que dejan de coincidir abre una pregunta sobre su comparabilidad o actualización.
"""

import math
from collections import defaultdict

from .comun import es_numero, hallazgo, numero, referencia
from .jerarquia_codigos import _codigo_celda, _hijos_inmediatos

IGUAL = 0.001


def _codigo(s):
    """Código jerárquico al comienzo del rótulo de la serie («3.5.1», «3.5.1 Préstamos»), o None."""
    return _codigo_celda(str(s.get("etiqueta") or "").split(" · ")[0].strip(), prefijo=True)


def _padre_de_hijo_unico(a, b, codigos):
    """Una fila es el código padre de la otra y ésta es su único hijo (3.5.1 = 3.5.1.1): son iguales por
    construcción, no una fila copiada."""
    ka, kb = _codigo(a), _codigo(b)
    if not ka or not kb:
        return False
    for padre, hijo in ((ka, kb), (kb, ka)):
        if _hijos_inmediatos(padre, codigos) == [hijo]:
            return True
    return False
MINIMO_PERIODOS = 4
MAXIMO_DESVIOS = 2
MATERIAL = 0.002


def _valores(s):
    return [numero(v) for v in s["valores"]]


_PASO = math.log10(1 + IGUAL)


def _candidatos(filas, valores):
    """Pares que comparten al menos tres valores no nulos iguales (±0,1 %) en el mismo período.

    Es condición necesaria de toda identidad que se informa (tres valores distintos de cero
    coincidentes), así que el resultado no cambia; evita comparar todos los pares en hojas grandes."""
    indice = defaultdict(list)
    claves = []
    for n, s in enumerate(filas):
        propias = []
        for i, v in enumerate(valores[n]):
            if v:
                propias.append((i, v > 0, math.floor(math.log10(abs(v)) / _PASO)))
        claves.append(propias)
        for k in propias:
            indice[k].append(n)
    pares = set()
    for n, propias in enumerate(claves):
        cuenta = defaultdict(int)
        for i, signo, k in propias:
            vistos = set()
            for d in (-1, 0, 1):
                for m in indice.get((i, signo, k + d), ()):
                    if m > n and m not in vistos:
                        vistos.add(m)
                        cuenta[m] += 1
        pares.update((n, m) for m, c in cuenta.items() if c >= 3)
    return pares


def analizar(series):
    por_hoja = defaultdict(list)
    for s in series:
        por_hoja[(s["archivo"], s["hoja"])].append(s)
    out = []
    for filas in por_hoja.values():
        valores = [_valores(s) for s in filas]
        posicion = {id(s): n for n, s in enumerate(filas)}
        codigos = None  # códigos jerárquicos de la hoja, sólo si hace falta mirarlos
        for n, m in sorted(_candidatos(filas, valores)):
            a, b = filas[n], filas[m]
            if a["periodos"] != b["periodos"]:
                continue
            mismo_cuadro = a["cuadro"] == b["cuadro"]
            if mismo_cuadro and (abs(a.get("nivel", 0) - b.get("nivel", 0)) > 0 or abs(a.get("fila", 0) - b.get("fila", 0)) <= 2):
                continue  # jerarquía o filas vecinas: un rubro puede coincidir con su subrubro
            va, vb = valores[posicion[id(a)]], valores[posicion[id(b)]]
            pares = [(i, x, y) for i, (x, y) in enumerate(zip(va, vb)) if x is not None and y is not None]
            if len(pares) < MINIMO_PERIODOS:
                continue
            iguales = [p for p in pares if abs(p[1] - p[2]) <= IGUAL * max(abs(p[1]), abs(p[2]), 1e-9)]
            distintos = [p for p in pares if p not in iguales]
            # La identidad debe sostenerse en casi toda la serie y sobre valores que varían.
            if len(iguales) < max(MINIMO_PERIODOS, 0.8 * len(pares)) or len(distintos) > MAXIMO_DESVIOS:
                continue
            if len({round(p[1], 6) for p in iguales if p[1]}) < 3:
                continue
            if mismo_cuadro:
                # Si el mismo patrón se repite en más de dos filas no es una copia: es una estructura.
                gemelas = sum(
                    1
                    for o in filas
                    if o is not a and o["periodos"] == a["periodos"]
                    and all(
                        x is not None and y is not None and abs(x - y) <= IGUAL * max(abs(x), abs(y), 1e-9)
                        for x, y in zip(va, valores[posicion[id(o)]])
                    )
                )
                if gemelas != 1:
                    continue
                if codigos is None:
                    codigos = sorted({k for k in map(_codigo, filas) if k})
                if _padre_de_hijo_unico(a, b, codigos):
                    continue  # el código padre con un único hijo repite su valor: no es una copia
                # Dos rubros distintos del mismo cuadro con la misma serie completa: fila duplicada.
                if distintos or len(iguales) < len(a["periodos"]) or len({round(p[1], 6) for p in iguales}) < 4:
                    continue
                out.append(
                    hallazgo(
                        a,
                        iguales[-1][0],
                        "filas_identicas",
                        f"«{a['etiqueta']}» y «{b['etiqueta']}» tienen exactamente los mismos valores en los "
                        f"{len(iguales)} períodos del cuadro. Puede ser una fila copiada sobre otra.",
                        110,
                        calculo=dict(fila_equivalente=b["etiqueta"], celda_equivalente=referencia(b, iguales[-1][0])),
                        participantes=[referencia(a, i) for i, _, _ in iguales]
                        + [referencia(b, i) for i, _, _ in iguales],
                        accion="Confirmar con el área si los dos rubros deben tener el mismo importe o si una fila quedó copiada sobre la otra.",
                        lente="conciliador",
                    )
                )
                continue
            for i, x, y in distintos:
                if abs(x - y) <= MATERIAL * max(abs(x), abs(y)):
                    continue
                out.append(
                    hallazgo(
                        a,
                        i,
                        "identidad_entre_cuadros",
                        f"«{a['etiqueta']}» y «{b['etiqueta']}» coinciden en {len(iguales)} de {len(pares)} períodos, "
                        f"pero en {a['periodos'][i]} valen {es_numero(x)} y {es_numero(y)}. La coincidencia histórica no demuestra "
                        "que ambos conceptos deban coincidir en este período; podría haber un cambio de cobertura o una actualización pendiente.",
                        110,
                        calculo=dict(
                            valor_otra_apertura=y,
                            celda_otra_apertura=referencia(b, i),
                            periodos_coincidentes=len(iguales),
                            periodos_comparables=len(pares),
                        ),
                        participantes=[referencia(a, i), referencia(b, i)],
                        accion="Confirmar con el área si ambos conceptos deben coincidir en este período; documentar la diferencia y corregir sólo si se confirma un error.",
                        lente="conciliador",
                    )
                )
    return out
