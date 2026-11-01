"""Índice de las celdas leídas: valor, rótulo, período, total del cuadro e identidades.

Sirve para que cada señal lleve, desde el análisis, tres datos que la prioridad necesita y que el
control que la detectó no siempre conoce:

- impacto: cuánto pesa el desvío sobre el total del mismo cuadro, en la unidad del cuadro;
- tabla derivada: si la celda es una variación o una participación calculable desde otra hoja del
  mismo libro (entonces la señal se subordina a la celda fuente, salvo que la celda no coincida con
  ese cálculo, que es un error propio);
- identidades: celdas del mismo período ligadas por cierres verificados (componente → subtotal →
  total), para agrupar señales por causa común.

No inventa relaciones: una tabla sólo se declara derivada si el cálculo coincide en varios
períodos, y los cierres vienen de estructura_revision (verificados en varios años).
"""

from __future__ import annotations

import re
from collections import defaultdict

from openpyxl.utils.cell import column_index_from_string

from services.controles_excel.comun import normalizar, numero

MINIMO_PERIODOS_DERIVADA = 3
PROPORCION_DERIVADA = 0.6
_TOTAL = re.compile(r"^\s*total\b", re.I)
_SUBTOTAL = re.compile(r"^\s*(sub)?total\b", re.I)


def _anio(nombre):
    n = numero(nombre)
    if n is not None and float(n).is_integer() and 1800 <= n <= 2200:
        return int(n)
    return None


def _decimales(v):
    texto = f"{abs(v):.6f}".rstrip("0")
    return len(texto.split(".")[1]) if "." in texto else 0


def _coincide(publicado, calculado):
    tolerancia = 0.5 * 10 ** -_decimales(publicado) + 1e-9 + 0.002 * abs(calculado)
    return abs(publicado - calculado) <= tolerancia


class Indice:
    def __init__(self, informe):
        self.celdas = {}  # (archivo, "Hoja!B5") -> dict
        self.series = defaultdict(dict)  # (archivo, hoja, bloque, rotulo) -> {periodo: ref}
        self.bloques = {}  # (archivo, hoja, bloque) -> dict(unidad, porcentual, rotulos)
        self.hijos = defaultdict(set)  # (archivo, ref total) -> refs componentes
        self.padres = defaultdict(set)
        self._derivadas = {}
        self._totales = {}
        self._por_periodo = defaultdict(list)  # (archivo, hoja, bloque, periodo) -> celdas
        saneamiento = getattr(informe, "saneamiento", None) or {}
        datos = getattr(informe, "datos", None) or []
        excel = saneamiento.get("excel") if isinstance(saneamiento, dict) else None
        estructura = saneamiento.get("estructura_revision") if isinstance(saneamiento, dict) else None
        unidades = defaultdict(list)
        for f in (estructura or {}).get("fichas") or []:
            unidades[(f.get("archivo"), f.get("hoja"), f.get("cuadro"))].append(f.get("unidad"))
        for b in (excel or {}).get("bloques") or []:
            self._leer_bloque(b, datos, unidades)
        for c in (estructura or {}).get("cierres_verificados") or []:
            archivo, hoja = c.get("archivo"), c.get("hoja")
            total = self._ref(hoja, c.get("total"))
            for comp in c.get("componentes") or []:
                comp = self._ref(hoja, comp)
                self.hijos[(archivo, total)].add(comp)
                self.padres[(archivo, comp)].add(total)

    @staticmethod
    def _ref(hoja, celda):
        celda = str(celda or "")
        return celda if "!" in celda else f"{hoja}!{celda}"

    def _leer_bloque(self, b, datos, unidades):
        archivo, hoja, bloque = b.get("archivo"), b.get("hoja"), b.get("bloque")
        columnas = b.get("columnas") or {}
        filas = b.get("filas") or []
        inicio = b.get("inicio") or 0
        if not columnas or not filas:
            return
        periodos = {nombre: _anio(nombre) for nombre in columnas}
        periodos = {k: v for k, v in periodos.items() if v is not None}
        if len(periodos) < 2:
            return
        primera = min(column_index_from_string(columnas[k]) for k in periodos)
        rotulos_col = sorted(
            (k for k in columnas if k not in periodos and column_index_from_string(columnas[k]) < primera),
            key=lambda k: column_index_from_string(columnas[k]),
        )
        lista_unidades = [u for u in unidades.get((archivo, hoja, bloque), []) if u]
        unidad = max(set(lista_unidades), key=lista_unidades.count) if lista_unidades else None
        porcentual = bool(unidad and ("%" in unidad or "porcentaje" in unidad))
        rotulos = []
        for local, fila in enumerate(filas):
            if inicio + local >= len(datos):
                break
            dato = datos[inicio + local] or {}
            rotulo = next((str(dato.get(k)) for k in rotulos_col if isinstance(dato.get(k), str) and dato.get(k).strip()), None)
            if not rotulo:
                continue
            rotulos.append(rotulo)
            clave = (archivo, hoja, bloque, normalizar(rotulo))
            for nombre, anio in periodos.items():
                ref = f"{hoja}!{columnas[nombre]}{fila}"
                valor = numero(dato.get(nombre))
                celda = dict(
                    valor=valor, rotulo=rotulo, periodo=anio, hoja=hoja, bloque=bloque, archivo=archivo, ref=ref
                )
                self.celdas[(archivo, ref)] = celda
                self._por_periodo[(archivo, hoja, bloque, anio)].append(celda)
                self.series[clave][anio] = ref
        self.bloques[(archivo, hoja, bloque)] = dict(unidad=unidad, porcentual=porcentual, rotulos=rotulos)

    # -- consultas -----------------------------------------------------------------------------

    def valor(self, archivo, ref):
        return (self.celdas.get((archivo, ref)) or {}).get("valor")

    def total(self, archivo, hoja, bloque, periodo):
        """Total declarado del cuadro en ese período; si no hay fila «Total», la suma de las filas."""
        clave = (archivo, hoja, bloque, periodo)
        if clave not in self._totales:
            self._totales[clave] = self._calcular_total(clave)
        return self._totales[clave]

    def _calcular_total(self, clave):
        candidatos = []
        suma, partes = 0.0, 0
        for c in self._por_periodo.get(clave, []):
            ref = c["ref"]
            if c["valor"] is None:
                continue
            if _TOTAL.match(c["rotulo"]):
                candidatos.append((0 if normalizar(c["rotulo"]) == "total" else 1, ref, c["valor"]))
            elif not _SUBTOTAL.match(c["rotulo"]):
                suma += c["valor"]
                partes += 1
        if candidatos:
            _, ref, valor = sorted(candidatos)[0]
            return valor, ref, "total declarado del cuadro"
        if partes >= 2:
            return suma, None, "suma de las filas del cuadro (sin fila de total)"
        return None, None, None

    def identidad(self, archivo, ref):
        """Ancestros y descendientes de la celda por cierres verificados del mismo período."""
        out = set()
        pendientes = [ref]
        while pendientes:
            x = pendientes.pop()
            for y in self.hijos.get((archivo, x), ()):
                if y not in out:
                    out.add(y)
                    pendientes.append(y)
        pendientes = [ref]
        while pendientes:
            x = pendientes.pop()
            for y in self.padres.get((archivo, x), ()):
                if y not in out:
                    out.add(y)
                    pendientes.append(y)
        out.discard(ref)
        return out

    def descendientes(self, archivo, ref):
        out, pendientes = set(), [ref]
        while pendientes:
            x = pendientes.pop()
            for y in self.hijos.get((archivo, x), ()):
                if y not in out:
                    out.add(y)
                    pendientes.append(y)
        return out

    def _relacion(self, clave_derivada):
        """Cómo se calcula una serie a partir de otra hoja del libro (o None)."""
        if clave_derivada in self._derivadas:
            return self._derivadas[clave_derivada]
        archivo, hoja, bloque, rotulo = clave_derivada
        serie_d = self.series.get(clave_derivada) or {}
        mejor = None
        for clave_f, serie_f in self.series.items():
            a2, h2, b2, r2 = clave_f
            if a2 != archivo or (h2, b2) == (hoja, bloque) or r2 != rotulo:
                continue
            if (self.bloques.get((a2, h2, b2)) or {}).get("porcentual"):
                continue
            for tipo in ("variacion", "participacion", "indice"):
                aciertos, comparados = 0, 0
                for p, ref_d in serie_d.items():
                    calculado = self._calculo(tipo, archivo, h2, b2, serie_f, p)
                    d = self.valor(archivo, ref_d)
                    if calculado is None or d is None:
                        continue
                    comparados += 1
                    aciertos += _coincide(d, calculado)
                if aciertos >= MINIMO_PERIODOS_DERIVADA and aciertos >= PROPORCION_DERIVADA * comparados:
                    if not mejor or aciertos > mejor[0]:
                        mejor = (aciertos, tipo, clave_f)
        self._derivadas[clave_derivada] = mejor and dict(tipo=mejor[1], fuente=mejor[2], periodos_coincidentes=mejor[0])
        return self._derivadas[clave_derivada]

    def _calculo(self, tipo, archivo, hoja_f, bloque_f, serie_f, p):
        actual = self.valor(archivo, serie_f.get(p)) if serie_f.get(p) else None
        if actual is None:
            return None
        if tipo in {"variacion", "indice"}:
            previo = self.valor(archivo, serie_f.get(p - 1)) if serie_f.get(p - 1) else None
            if not previo:
                return None
            return (actual / previo - 1) * 100 if tipo == "variacion" else actual / previo * 100
        total, _, base = self.total(archivo, hoja_f, bloque_f, p)
        if not total or base != "total declarado del cuadro":
            return None
        return actual / total * 100

    def derivada(self, archivo, ref):
        """Si la celda pertenece a una tabla calculable desde otra hoja, sus celdas fuente."""
        c = self.celdas.get((archivo, ref))
        if not c:
            return None
        clave = (archivo, c["hoja"], c["bloque"], normalizar(c["rotulo"]))
        rel = self._relacion(clave)
        if not rel:
            return None
        _, hoja_f, bloque_f, _ = rel["fuente"]
        serie_f = self.series[rel["fuente"]]
        p = c["periodo"]
        fuente = [serie_f[p]] if serie_f.get(p) else []
        if rel["tipo"] in {"variacion", "indice"} and serie_f.get(p - 1):
            fuente.append(serie_f[p - 1])
        if rel["tipo"] == "participacion":
            _, ref_total, _ = self.total(archivo, hoja_f, bloque_f, p)
            if ref_total:
                fuente.append(ref_total)
        calculado = self._calculo(rel["tipo"], archivo, hoja_f, bloque_f, serie_f, p)
        coincide = calculado is not None and c["valor"] is not None and _coincide(c["valor"], calculado)
        ampliadas = set(fuente)
        for f in fuente:
            ampliadas |= self.descendientes(archivo, f)
        nombre = {"variacion": "variación interanual", "participacion": "participación en el total", "indice": "índice respecto del año anterior"}[rel["tipo"]]
        return dict(
            tipo=rel["tipo"],
            descripcion=f"{nombre} calculable desde la hoja «{hoja_f}»",
            hoja_fuente=hoja_f,
            celdas_fuente=fuente,
            celdas_fuente_ampliadas=sorted(ampliadas),
            periodos_coincidentes=rel["periodos_coincidentes"],
            valor_calculado=calculado,
            subordinada=bool(coincide),
            inconsistente_con_fuente=bool(calculado is not None and c["valor"] is not None and not coincide),
        )


def _propias(e):
    hoja = e.get("hoja")
    out = []
    if e.get("celda"):
        out.append(Indice._ref(hoja, e["celda"]))
    for u in e.get("ubicaciones_excel") or []:
        ref = Indice._ref(hoja, u)
        h, _, rango = ref.rpartition("!")
        out.append(f"{h}!{rango.split(':')[-1]}")
    return list(dict.fromkeys(out))


def _desvio(e, valor):
    for clave in ("diferencia_absoluta",):
        if numero(e.get(clave)) is not None:
            return abs(numero(e[clave])), "diferencia entre total y componentes"
    obs = numero(e.get("valor_observado"))
    obs = obs if obs is not None else valor
    for clave, texto in (
        ("valor_edicion_anterior", "diferencia con la edición anterior"),
        ("interpolacion", "desvío respecto de la interpolación entre vecinos"),
        ("extrapolacion", "desvío respecto de la extrapolación local"),
    ):
        ref = numero(e.get(clave))
        if ref is not None and obs is not None:
            return abs(obs - ref), texto
    deltas = [abs(numero(d.get("delta"))) for d in e.get("detalle_series") or [] if numero(d.get("delta")) is not None]
    if numero(e.get("delta")) is not None:
        deltas.append(abs(numero(e["delta"])))
    if deltas:
        return max(deltas), "salto respecto del período anterior"
    mediana = numero(e.get("mediana_serie"))
    if obs is not None and mediana is not None:
        return abs(obs - mediana), "desvío respecto de la mediana de la serie"
    if obs is not None:
        return abs(obs), "valor de la celda"
    return None, None


def anotar(h, indice):
    """Agrega a la evidencia: impacto, tabla derivada e identidades (sin borrar nada)."""
    e = h.get("evidencia")
    if not isinstance(e, dict):
        return h
    if e.get("detalle_contexto"):
        # Un agrupado de contexto reúne celdas de varias hojas: se anota cada detalle, no el grupo.
        for d in e["detalle_contexto"]:
            if isinstance(d, dict):
                anotar(d, indice)
        return h
    archivo = e.get("archivo_origen")
    propias = _propias(e)
    leidas = [r for r in propias if (archivo, r) in indice.celdas]
    if not leidas:
        if "impacto" not in e and not e.get("materialidad"):
            e["impacto"] = dict(motivo="sin coordenadas de celda en un cuadro leído; no hay total con el cual medirlo")
        return h
    ref = leidas[-1]
    c = indice.celdas[(archivo, ref)]
    identidad = set()
    for r in leidas:
        identidad |= indice.identidad(archivo, r)
    if identidad:
        e["celdas_identidad"] = sorted(identidad)
    derivada = None
    for r in leidas:
        derivada = indice.derivada(archivo, r)
        if derivada:
            break
    if derivada:
        e["tabla_derivada"] = derivada
    serie = indice.series.get((archivo, c["hoja"], c["bloque"], normalizar(c["rotulo"]))) or {}
    if serie and c["periodo"] in (max(serie), min(serie)):
        # En el primer o el último período no hay vecino del otro lado: no hay confirmación bilateral.
        e["extremo_de_serie"] = True
    if e.get("materialidad") or "impacto" in e:
        return h
    bloque = indice.bloques.get((archivo, c["hoja"], c["bloque"])) or {}
    if derivada and derivada.get("subordinada"):
        e["impacto"] = dict(motivo="tabla derivada: el impacto se mide en la celda fuente")
        return h
    if bloque.get("porcentual"):
        e["impacto"] = dict(motivo="valores en porcentaje: no hay un total del cuadro en la misma unidad")
        return h
    total, ref_total, base = indice.total(archivo, c["hoja"], c["bloque"], c["periodo"])
    desvio, como = _desvio(e, c["valor"])
    if not total or desvio is None:
        e["impacto"] = dict(motivo="el cuadro no tiene un total (ni filas sumables) en ese período")
        return h
    e["impacto"] = dict(
        porcentaje=100 * desvio / abs(total),
        desvio=desvio,
        criterio_desvio=como,
        total=total,
        celda_total=ref_total,
        base=base,
        unidad=bloque.get("unidad") or "unidad del cuadro (no rotulada)",
    )
    return h


def anotar_todos(hallazgos, informe):
    try:
        indice = Indice(informe)
    except Exception:  # noqa: BLE001 — una estructura histórica incompleta no debe frenar el análisis
        return hallazgos
    if not indice.celdas:
        return hallazgos
    for h in hallazgos:
        try:
            anotar(h, indice)
        except Exception:  # noqa: BLE001
            continue
    return hallazgos
