"""Distingue encabezados aislados de columnas pertenecientes a un cuadro."""

import math
import re

# Código de serie de las planillas de un ministerio («84.2_CCFSBT_0_T_43», «145.1_IPC_NG_NACNAL_DICI_T_15»): número de
# cuadro y tramo, y segmentos en mayúsculas o dígitos separados por guiones bajos. Identifica la serie; no es un rótulo.
# Los guiones bajos pueden repetirse: «364.1_TOTALTAL__5», «327.1_INDICE_TIEMPO__13».
CODIGO_SERIE = re.compile(r"^\d{1,4}\.\d{1,3}(?:_+[A-Z0-9]+){2,}$")


def presente(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and str(v).strip() != ""


def es_anio(v):
    try:
        return not isinstance(v, bool) and 1800 <= float(v) <= 2200
    except (ValueError, TypeError):
        return False


def encabezados_aislados(encabezado, filas):
    """Índices de años en grupos separados por columnas vacías y sin datos debajo.

    Sólo se excluyen si existe otro grupo con >=3 períodos y datos. Se conservan
    columnas contiguas vacías, encabezados corruptos y cualquier grupo con datos.
    """
    ancho = len(encabezado)
    con_datos = {j for fila in filas for j, v in enumerate(fila[:ancho]) if presente(v)}
    ocupadas = [j for j, v in enumerate(encabezado) if presente(v) or j in con_datos]
    grupos = []
    for j in ocupadas:
        if not grupos or j != grupos[-1][-1] + 1:
            grupos.append([])
        grupos[-1].append(j)
    if not any(
        sum(es_anio(encabezado[j]) for j in g) >= 3 and any(j in con_datos and es_anio(encabezado[j]) for j in g)
        for g in grupos
    ):
        return []
    return [j for g in grupos if not any(j in con_datos for j in g) for j in g if es_anio(encabezado[j])]


def grupos_columnas(encabezado, filas):
    """Grupos separados por una columna completamente vacía en el cuadro."""
    ocupadas = [j for j, v in enumerate(encabezado) if presente(v) or any(j < len(f) and presente(f[j]) for f in filas)]
    grupos = []
    for j in ocupadas:
        if not grupos or j != grupos[-1][-1] + 1:
            grupos.append([])
        grupos[-1].append(j)
    return grupos


def paneles_anuales(encabezado, filas):
    grupos = grupos_columnas(encabezado, filas)
    candidatos = []
    for grupo in grupos:
        anios = [j for j in grupo if es_anio(encabezado[j])]
        if len(anios) >= 2 and any(
            j < anios[0] and presente(encabezado[j]) and not es_anio(encabezado[j]) for j in grupo
        ):
            candidatos.append(grupo)
    # Una columna vacía interior no divide por sí sola la serie: cada panel
    # necesita su propio rótulo antes de los períodos.
    return candidatos if len(candidatos) >= 2 else [list(range(len(encabezado)))]


def anio_rotulo(v):
    """Año de un rótulo de encabezado: número o texto, también con marca («2023 (p)») o con la
    unidad anotada («2024 (miles de asistentes)»). None si no es un año."""
    if not presente(v) or isinstance(v, bool):
        return None
    if es_anio(v):
        return float(v)
    if isinstance(v, str):
        from services.controles_excel.periodos import leer

        p = leer(v)
        if p and p["frecuencia"] == "anual" and (p.get("marca") or p.get("unidad")):
            return float(p["anio"])
    return None


def es_encabezado_anual(fila):
    numeros = []
    for v in fila:
        try:
            if presente(v) and not isinstance(v, bool):
                numeros.append(float(v))
        except (ValueError, TypeError):
            if anio_rotulo(v) is not None:
                numeros.append(anio_rotulo(v))
    return (
        sum(anio_rotulo(v) is not None for v in fila) >= 2
        and numeros
        and all(1800 <= v <= 2200 for v in numeros)
        and any(presente(v) and anio_rotulo(v) is None for v in fila)
        and anios_plausibles(numeros)
    )


def anios_plausibles(numeros):
    """Una fila de años se reconoce por su forma, no sólo por el rango 1800-2200: casi todos
    enteros y con pasos de calendario (regulares o cortos). Importes como 1920,5 · 1934,2 ·
    1950 o 1920 · 1934 · 1961 · 1996 son datos que caen en ese rango, no un encabezado."""
    if len(numeros) < 2:
        return True
    decimales = sum(not float(v).is_integer() for v in numeros)
    if decimales >= 2 and decimales * 2 >= len(numeros):
        return False
    if len(numeros) < 3:
        return True
    pasos = [abs(b - a) for a, b in zip(numeros, numeros[1:])]
    pasos_ordenados = sorted(pasos)
    mediana = pasos_ordenados[len(pasos) // 2]
    regulares = max(pasos.count(p) for p in set(pasos))
    return mediana <= 10 or regulares * 2 > len(pasos)


def _posiciones_numericas(fila):
    return {j for j, v in enumerate(fila) if _es_numero_celda(v)}


def continua_fila_de_datos(filas, i):
    """La fila anterior tiene números en al menos dos de las columnas donde ésta los tiene."""
    if not i:
        return False
    propias = _posiciones_numericas(filas[i])
    return len(propias & _posiciones_numericas(filas[i - 1])) >= 2


def filas_encabezado_anual(filas):
    """No confundir importes cercanos a 2000 con otro encabezado en el mismo cuadro."""
    resultado = []
    rotulos = {
        "indicador",
        "concepto",
        "categoría",
        "categoria",
        "clase",
        "rubro",
        "partida",
        "descripción",
        "descripcion",
        "detalle",
        "serie",
        "item",
        "ítem",
    }
    for i, fila in enumerate(filas):
        if not es_encabezado_anual(fila):
            continue
        etiqueta = next((str(v).strip().lower() for v in fila if presente(v) and not es_anio(v)), "")
        anterior = filas[i - 1] if i else []
        tras_datos = any(es_anio(v) or isinstance(v, (int, float)) and presente(v) for v in anterior)
        if resultado and tras_datos and etiqueta not in rotulos:
            continue
        # Una fila de datos con un año y un importe cercano a 2000 («Córdoba · 2019 · 2000»),
        # debajo de otra fila de datos con números en las mismas columnas, no es un encabezado.
        if etiqueta not in rotulos and continua_fila_de_datos(filas, i):
            continue
        resultado.append(i)
    return resultado


def _es_texto(v):
    return isinstance(v, str) and bool(v.strip())


def _es_numero_celda(v):
    if isinstance(v, bool) or not presente(v):
        return False
    if isinstance(v, (int, float)):
        return True
    from services.perfilado import partes_numero

    return isinstance(v, str) and partes_numero(v) is not None


def fila_rotulos_periodo(fila):
    """Celdas de una fila que son rótulos de período («2024», «T1 2025», «2023 (en millones)»)."""
    from services.controles_excel.periodos import leer

    return [j for j, v in enumerate(fila) if presente(v) and leer(v) is not None]


def encabezados_apilados(filas, conocidos):
    """Encabezados de otros cuadros apilados en la misma hoja, reconocidos por su forma.

    Un segundo cuadro debajo del primero trae su propio encabezado después de una fila vacía o de
    un título: una fila sin importes, con el rótulo de la primera columna y al menos dos rótulos de
    período (o los mismos rótulos que el encabezado anterior), seguida de filas cuyos números caen
    en las columnas que esa fila nombra. Leerla como una fila de datos del cuadro anterior dejaría
    el segundo cuadro sin controlar.
    """
    from services.perfilado import es_sin_dato

    if not conocidos:
        return []
    primero = min(conocidos)
    nuevos = []
    rotulos_previos = {
        str(v).strip().lower() for v in filas[primero] if _es_texto(v)
    } if primero < len(filas) else set()
    for i in range(primero + 1, len(filas)):
        if i in conocidos:
            continue
        fila = filas[i]
        celdas = {j: v for j, v in enumerate(fila) if presente(v)}
        # Los libros breves suelen apilar cuadros de dos columnas sin períodos:
        # título/«Carreras», datos, total, fila vacía y un encabezado nuevo.
        # También separa una matriz de categorías con varios rótulos de texto.
        # Exigir el separador y dos observaciones numéricas evita tomar una nota
        # o un rótulo aislado por el encabezado de otro cuadro.
        anteriores = [v for v in filas[i - 1] if presente(v)] if i else []
        primera = min(celdas) if celdas else -1
        segundo = str(celdas.get(primera + 1, "")).strip().casefold()
        rotulos_cantidad = {"cantidad", "total", "valor", "importe", "monto", "número", "numero",
                            "personas", "casos", "alumnos", "matrícula", "matricula", "carreras", "unidades"}
        if (not anteriores and primera == 0 and len(celdas) >= 2
                and (len(celdas) >= 3 or segundo in rotulos_cantidad)
                and all(_es_texto(v) and not _es_numero_celda(v) for v in celdas.values())):
            posiciones = set(celdas) - {primera}
            observaciones = 0
            for abajo in filas[i + 1 : i + 7]:
                if not any(presente(v) for v in abajo):
                    break
                numericas = _posiciones_numericas(abajo)
                if numericas and numericas <= posiciones:
                    observaciones += 1
            if observaciones >= 2:
                nuevos.append(i)
                rotulos_previos = {str(v).strip().lower() for v in celdas.values()}
                continue
        if len(celdas) < 3:
            continue
        if any(es_sin_dato(v) for v in celdas.values()):
            continue
        periodos = fila_rotulos_periodo(fila)
        textos = [j for j, v in celdas.items() if _es_texto(v) and not _es_numero_celda(v)]
        anios_num = [j for j, v in celdas.items() if not _es_texto(v) and es_anio(v)]
        # Ningún importe: sólo textos y años plausibles.
        if len(textos) + len(anios_num) < len(celdas):
            continue
        if anios_num and not anios_plausibles([float(celdas[j]) for j in anios_num]):
            continue
        primera = min(celdas)
        if primera not in textos:
            continue
        otros_periodos = [j for j in periodos if j != primera]
        mismos = sum(1 for j in textos if str(celdas[j]).strip().lower() in rotulos_previos)
        if len(otros_periodos) < 2 and mismos < 3:
            continue
        # Antes: fila vacía o un título de una sola celda. Pegado a los datos del cuadro anterior
        # sólo si la fila es inequívocamente un encabezado: tres o más períodos en secuencia regular.
        anterior = filas[i - 1] if i else []
        previas = [v for v in anterior if presente(v)]
        if previas and not (len(previas) == 1 and _es_texto(previas[0])) and not _secuencia_regular(fila, otros_periodos):
            continue
        # Debajo: filas con números sólo en las columnas que la fila nombra (o corridas una columna
        # a la izquierda de los períodos: el encabezado puede estar desplazado respecto de los datos).
        posiciones = set(celdas)
        if otros_periodos and min(otros_periodos) - 1 not in posiciones and min(otros_periodos) - 1 > primera:
            posiciones.add(min(otros_periodos) - 1)
        con_numeros = consistentes = 0
        for abajo in filas[i + 1 : i + 13]:
            numericas = {j for j, v in enumerate(abajo) if _es_numero_celda(v)}
            if not numericas:
                if con_numeros and not any(presente(v) for v in abajo):
                    break
                continue
            con_numeros += 1
            if numericas <= posiciones:
                consistentes += 1
            if con_numeros >= 6:
                break
        if consistentes >= 2 and consistentes >= 0.6 * con_numeros:
            nuevos.append(i)
            rotulos_previos = {str(v).strip().lower() for v in fila if _es_texto(v)}
    return nuevos


def _secuencia_regular(fila, columnas):
    """Tres o más rótulos de período, de izquierda a derecha, con un paso constante (2019, 2020, 2021…)."""
    from services.controles_excel.periodos import leer, ordinal

    if len(columnas) < 3:
        return False
    periodos = [leer(fila[j]) for j in sorted(columnas)]
    if any(p is None for p in periodos) or len({p["frecuencia"] for p in periodos}) != 1:
        return False
    ords = [ordinal(p) for p in periodos]
    pasos = {b - a for a, b in zip(ords, ords[1:])}
    return len(pasos) == 1 and 0 < next(iter(pasos)) <= 5
