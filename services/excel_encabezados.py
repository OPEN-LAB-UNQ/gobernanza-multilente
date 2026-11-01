"""Encabezados de varios niveles delimitados por celdas combinadas explícitas."""
import re

FILAS_ABAJO = 2  # filas de rótulos que una combinación vertical puede sumar debajo del encabezado detectado


def _fila_de_rotulos(fila) -> bool:
    """Rótulos con letras o años, sin cifras del cuerpo. Una fila de unidades («pesos», «%») no lo es: la lee
    después la cobertura como metadato, y el rótulo de cada columna sigue siendo el de arriba."""
    from services.carga_archivos import _celda_numerica, _celda_periodo, _compactar
    from services.excel_cobertura import UNIDAD_CELDA

    presentes = [_compactar(v) for v in fila if _compactar(v)]
    if not presentes or all(UNIDAD_CELDA.fullmatch(v) for v in presentes):
        return False
    if any(_celda_numerica(v) and not _celda_periodo(v) for v in fila):
        return False
    return any(re.search(r"[^\W\d_]{2}", v) for v in presentes) or sum(_celda_periodo(v) for v in fila) >= 2


def combinar(filas, rangos, header):
    """Devuelve niveles y nombres sólo si una combinación vertical enlaza filas del encabezado.

    Hacia arriba, un rótulo combinado que baja hasta el encabezado detectado suma las filas de
    arriba. Hacia abajo, rótulos combinados en dos filas («Código», «Jurisdicción») con los tipos
    debajo de un título que los abarca suman la fila de los tipos, aunque ninguna palabra de una
    lista la reconozca como encabezado (un censo nacional, cuadro de viviendas colectivas).
    No extiende rótulos fuera de su combinación ni toma cifras del cuerpo ni unidades como
    encabezados; un año en la fila de abajo («2023» bajo «Crédito vigente») es un rótulo.
    Las coordenadas de rangos son (fila inicial, columna inicial, fila final, columna final),
    con base 1; header usa base 0 como pandas.
    """
    from services.carga_archivos import _celda_numerica, _compactar

    def rotulo(a, b):
        return a <= len(filas) and b <= len(filas[a - 1]) and isinstance(filas[a - 1][b - 1], str)

    ultimo = max(header) + 1
    primeras = [a for a, b, c, d in rangos if a <= ultimo <= c and a < c and rotulo(a, b)]
    primero = min(primeras) if primeras and min(primeras) < min(header) + 1 else None
    if primero and any(_celda_numerica(v) for fila in filas[primero - 1:ultimo] for v in fila):
        primero = None
    bajan = [c for a, b, c, d in rangos if min(header) + 1 <= a <= ultimo < c and rotulo(a, b)]
    tope = min(max(bajan), ultimo + FILAS_ABAJO, len(filas)) if bajan else ultimo
    hasta = ultimo
    while hasta < tope and _fila_de_rotulos(filas[hasta]):
        hasta += 1
    if primero is None and hasta == ultimo:
        return None
    primero = primero or min(header) + 1
    ultimo = hasta
    ancho = len(filas[ultimo - 1])
    niveles = [list(fila) for fila in filas[primero - 1:ultimo]]
    for a, b, c, d in rangos:
        if a < primero or a > ultimo:
            continue
        valor = filas[a - 1][b - 1]
        # Un título que abarca varios grupos no se repite en cada nombre de columna.
        padre = b < d and any(a < e <= ultimo and b <= f <= h <= d and h - f < d - b
                              and f < h for e, f, g, h in rangos)
        if padre:
            valor = None
        for r in range(a, min(c, ultimo) + 1):
            for col in range(b, min(d, ancho) + 1):
                niveles[r - primero][col - 1] = valor
    nombres = []
    for col in range(ancho):
        partes = list(dict.fromkeys(_compactar(f[col]) for f in niveles if _compactar(f[col])))
        nombres.append(" ".join(partes))
    return list(range(primero - 1, ultimo)), nombres
