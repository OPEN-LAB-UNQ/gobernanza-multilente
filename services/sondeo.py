"""Sondeo previo de cada hoja («radiografía»): antes de presentar una señal, ver si la lectura es confiable.

Un error real ocupa un lugar (una celda, o una fila o columna a la que se arrastra). Cuando una misma regla
aparece en muchos lugares distintos de una misma hoja, lo más probable es que el motor no haya entendido cómo
está armado el cuadro («placa movida»), no que la hoja tenga decenas de errores. En ese caso la regla se
abstiene en esa hoja: sus señales pasan a nota de alcance (no se borran, quedan con el motivo) y el comienzo del
informe dice qué quedó sin controlar y por qué. Lo mismo cuando la misma regla marca la misma celda en varias
hojas del libro: puede ser la forma del cuadro que se repite o un error de plantilla, y el sondeo no los distingue.

Cada señal cuenta UN lugar: su celda ancla (la celda de la evidencia o la primera ubicación en su hoja). Los
lugares de una regla en una hoja son min(filas distintas, columnas distintas) de esas anclas: un error que se
arrastra por una fila o una columna cuenta uno. Una señal sin celda no cuenta. Nunca se abstiene una señal
corroborada por un control independiente.

Umbrales calibrados sólo con el banco de planillas oficiales correctas y los errores insertados en ellas
(20/10/2026), antes de la validación externa 4.
"""

from __future__ import annotations

import re
from collections import defaultdict

UMBRAL_LUGARES = 3        # lugares distintos de una regla en una hoja para abstenerse
UMBRAL_HOJAS = 3          # hojas en las que la misma regla marca la misma celda
VERSION = "sondeo-2"
# Una fórmula reemplazada por un valor en la misma celda de todas las hojas es un error de plantilla posible:
# el criterio de celda repetida en varias hojas no se aplica a las reglas de fórmulas.
SIN_CRITERIO_HOJAS = {"valor_fijo_distinto_de_formula", "formula_fuera_de_patron"}
# Una repetición puede ser la forma del cuadro o un error de plantilla: el sondeo no lo sabe y lo dice (auditoría, 28/10).
REPETIDO_EN_HOJAS = ("puede ser la forma del cuadro que se repite o un error de plantilla copiado en cada hoja; "
                     "no se puede distinguir sin mirarlo")

_CELDA = re.compile(r"^\$?([A-Z]{1,3})\$?(\d+)$")

NOMBRE_CONTROL = {
    "valor_fijo_distinto_de_formula": "valor cargado a mano donde otra celda usa fórmula",
    "periodo_faltante": "período que falta en la serie",
    "signo_opuesto_columna": "signo opuesto al resto de la columna",
    "valor_fuera_de_escala_columna": "valor fuera de la escala de su columna",
    "valor_fuera_de_escala_fila_columna": "valor fuera de la escala de su fila y su columna",
    "pico_aislado": "valor que se aparta de su serie",
    "escala_extremo": "valor extremo fuera de la escala de su serie",
    "periodo_duplicado": "período repetido",
    "anio_duplicado": "año repetido",
    "periodo_fuera_de_secuencia": "período fuera de secuencia",
    "valor_negativo_en_magnitud_no_negativa": "negativo en una magnitud que no puede serlo",
    "serie_acumulada_retrocede": "serie acumulada que retrocede",
    "cambio_tipo": "cambio en el tipo de dato de la columna",
    "valor_aislado_en_cuadro": "valor que se aparta del resto del cuadro",
    "filas_identicas": "filas idénticas",
    "fila_no_cierra_total": "fila que no cierra con su total",
    "columna_total_no_cierra": "columna de total que no cierra",
    "total_sin_rotulo_no_cierra": "total sin rótulo que no cierra",
    "partes_no_suman_total": "partes que no suman el total",
    "signo_aislado": "signo distinto del resto de la serie",
    "valor_repetido": "valor repetido",
    "valor_identico_otra_fila": "valor idéntico al de otra fila",
    "decimal_en_columna_de_enteros": "valor con decimales en una columna de enteros",
    "vacio_interior": "celda vacía dentro de una serie",
    "corte_temporal": "salto fuera de lo habitual",
    "corte_temporal_conjunto": "salto simultáneo en varias series",
}


def nombre_control(regla):
    return NOMBRE_CONTROL.get(regla) or str(regla or "control").replace("_", " ")


def _ev(h):
    e = h.get("evidencia") if isinstance(h, dict) else getattr(h, "evidencia", None)
    return e if isinstance(e, dict) else {}


def _coordenada(texto):
    m = _CELDA.match(str(texto or "").replace("$", "").upper().strip())
    return (m.group(1), int(m.group(2))) if m else None


def ancla(e):
    """Celda que representa a la señal en su hoja: la de la evidencia, o la primera ubicación en esa hoja."""
    c = _coordenada(e.get("celda"))
    if c:
        return c
    hoja = e.get("hoja")
    for lugar in list(e.get("ubicaciones_excel") or []) + list(e.get("celdas_participantes") or []):
        h, _, ref = str(lugar).rpartition("!")
        if h.strip("'") != hoja:
            continue
        c = _coordenada(ref.split(":")[0])
        if c:
            return c
    return None


def lugares_distintos(grupo):
    """min(filas distintas, columnas distintas) de las anclas: un error que se arrastra por una fila o columna
    cuenta uno. Sin anclas, 0 (no hay base para abstenerse)."""
    cs = {a for a in (ancla(e) for e in grupo) if a}
    if not cs:
        return 0
    return min(len({c[0] for c in cs}), len({c[1] for c in cs}))


def aplicar(hallazgos, es_senal):
    """Marca como «sin controlar» las señales de reglas que no pasan el sondeo. Devuelve la lista de abstenciones.

    es_senal(h) dice si h cuenta hoy como señal (ni contexto ni nota). Sólo se sondean señales ubicadas en una hoja.
    """
    grupos = defaultdict(list)
    por_celda = defaultdict(set)
    candidatas = []
    for h in hallazgos:
        e = _ev(h)
        if not e.get("hoja") or not e.get("regla") or not es_senal(h):
            continue
        candidatas.append(h)
        grupos[(e.get("archivo_origen"), e["hoja"], e["regla"])].append(e)
        a = ancla(e)
        if a and e["regla"] not in SIN_CRITERIO_HOJAS:
            por_celda[(e.get("archivo_origen"), e["regla"], a)].add(e["hoja"])
    tam = {k: lugares_distintos(g) for k, g in grupos.items()}
    abstenciones = {}
    for h in candidatas:
        e = _ev(h)
        if e.get("corroboracion_independiente"):
            continue
        k = (e.get("archivo_origen"), e["hoja"], e["regla"])
        a = ancla(e)
        if tam[k] >= UMBRAL_LUGARES:
            clave = ("hoja",) + k
            motivo = (f"marca {tam[k]} lugares distintos de la hoja: puede que no se haya entendido cómo está armado "
                      "el cuadro o que el mismo error se repita en cada lugar; no se puede distinguir sin mirarlo")
        elif a and len(por_celda.get((e.get("archivo_origen"), e["regla"], a), ())) >= UMBRAL_HOJAS:
            clave = ("libro", e.get("archivo_origen"), e["regla"])
            motivo = f"marca la misma celda en varias hojas: {REPETIDO_EN_HOJAS}"
        else:
            continue
        e["sondeo"] = dict(version=VERSION, motivo=motivo)
        if isinstance(h, dict):
            h["evidencia"] = e
            h["descripcion"] = "[Sin controlar por el sondeo previo] " + str(h.get("descripcion") or "")
        x = abstenciones.setdefault(clave, dict(archivo=e.get("archivo_origen"), regla=e["regla"], tipo=clave[0],
                                                motivo=motivo, senales=0, hojas=set(), celdas=set()))
        x["senales"] += 1
        x["hojas"].add(e["hoja"])
        if a:
            x["celdas"].add(f"{a[0]}{a[1]}")
    out = []
    for x in abstenciones.values():
        hojas, celdas = sorted(x.pop("hojas")), sorted(x.pop("celdas"), key=lambda c: (len(c), c))
        nombre = nombre_control(x["regla"])
        if x.pop("tipo") == "hoja":
            donde = f"control «{nombre}» en la hoja «{hojas[0]}»"
            hoja = hojas[0]
        else:
            donde = (f"control «{nombre}» en {len(hojas)} hojas ({', '.join(f'«{h}»' for h in hojas[:3])}"
                     + (f" y {len(hojas) - 3} más" if len(hojas) > 3 else "") + ")")
            x["motivo"] = (f"marca las mismas celdas ({', '.join(celdas[:4])}{' y otras' if len(celdas) > 4 else ''}) "
                           f"en {len(hojas)} hojas: {REPETIDO_EN_HOJAS}")
            hoja = None
        out.append(dict(x, hoja=hoja, hojas=hojas, celdas=celdas[:20], donde=donde))
    out.sort(key=lambda a: (-a["senales"], str(a["archivo"]), str(a["donde"])))
    return out


def es_sin_controlar(h):
    return bool(_ev(h).get("sondeo"))
