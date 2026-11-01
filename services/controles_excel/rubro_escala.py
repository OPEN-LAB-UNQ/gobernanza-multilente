"""Un rubro entero en otra escala (×1000, ×100, ×10 o al revés) con el total sin recalcular.

Cuando un «Total» no coincide con la suma de sus componentes en ningún período, se prueba si
multiplicar o dividir UN solo rubro por una potencia de diez hace que cierre en casi todos. Si hay
una única corrección así, es una señal precisa: qué fila y en qué factor. Si hay varias o ninguna,
no se dice nada (el cierre queda declarado como no comprobado).
"""
from .comun import es_numero, hallazgo, numero, referencia
from .conciliacion import es_total, relacion_corroborada, relaciones_cuadro
from .temporal import mapa_periodos

FACTORES = (1000.0, 100.0, 10.0, 0.1, 0.01, 0.001)


def _cierra(total, suma):
    return abs(total - suma) <= 1e-9 + 0.001 * max(abs(total), abs(suma))


def _factor_legible(f):
    return f"dividen por {es_numero(1 / f, 0)}" if f < 1 else f"multiplican por {es_numero(f, 0)}"


def _miles_leidos_como_decimales(pruebas, idx):
    """Las otras filas y el total tienen, casi todos, exactamente tres decimales: miles leídos como decimales."""
    otros = [v for _, _, vs, t in pruebas for k, v in enumerate(vs + [t]) if k != idx]
    if not otros:
        return False
    tres = [v for v in otros if abs(v * 100 - round(v * 100)) > 1e-6 and abs(v * 1000 - round(v * 1000)) < 1e-6]
    return len(tres) >= 0.8 * len(otros)


def analizar(series):
    salida = []
    for padre, hijos, _origen in relaciones_cuadro(series):
        if not es_total(padre) or len(hijos) < 2:
            continue
        mapas = [mapa_periodos(h) for h in hijos]
        pruebas = []
        for periodo, i in mapa_periodos(padre).items():
            if any(periodo not in m for m in mapas):
                continue
            js = [m[periodo] for m in mapas]
            vs = [numero(h["valores"][j]) for h, j in zip(hijos, js)]
            total = numero(padre["valores"][i])
            if total is None or any(v is None for v in vs):
                continue
            pruebas.append((i, js, vs, total))
        n = len(pruebas)
        if n < 4 or relacion_corroborada(sum(_cierra(t, sum(vs)) for _, _, vs, t in pruebas), n):
            continue
        candidatos = []
        for idx in range(len(hijos)):
            for f in FACTORES:
                buenas = sum(_cierra(t, sum(vs) - vs[idx] + vs[idx] * f) for _, _, vs, t in pruebas)
                if relacion_corroborada(buenas, n):
                    candidatos.append((idx, f, buenas))
        if len(candidatos) != 1:
            continue
        idx, f, buenas = candidatos[0]
        if _miles_leidos_como_decimales(pruebas, idx):
            # Lo que está en otra escala es la lectura («6,097» tomado como 6,097): ya se declaró como
            # formato ambiguo; señalar la única fila sin coma confundiría la causa.
            continue
        hijo = hijos[idx]
        celdas = [referencia(hijo, js[idx]) for _, js, _, _ in pruebas]
        totales = [referencia(padre, i) for i, _, _, _ in pruebas]
        detalle = (
            f"«{padre['etiqueta']}» no coincide con la suma de sus componentes en ningún período, pero coincide en "
            f"{buenas} de {n} si los valores de «{hijo['etiqueta']}» se {_factor_legible(f)}: esa fila parece estar en "
            "otra escala que el resto del cuadro."
        )
        h = hallazgo(
            hijo, pruebas[0][1][idx], "rubro_en_otra_escala", detalle, 120,
            calculo={"factor_que_cierra": f, "periodos_que_cierran": buenas, "periodos_comparables": n,
                     "fila_total": padre["etiqueta"]},
            participantes=celdas + totales,
            accion="Verificar la unidad de esa fila en la fuente y, si corresponde, corregirla o declararla.",
        )
        h["evidencia"]["ubicaciones_excel"] = celdas
        salida.append(h)
    return salida
