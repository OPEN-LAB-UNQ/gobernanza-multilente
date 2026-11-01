"""Lector del cuadro: la IA lee y entiende, las reglas verifican.

1. Al cargar, se guarda la grilla de TODAS las hojas visibles con números, en el orden del libro. Lo que no se lee
   (hojas ocultas, más allá de MAX_FILAS x MAX_COLS o del tope de celdas del informe) se declara, nunca se omite.
2. Al analizar, las lectoras (GPT y Gemini; DeepSeek sólo si se agrega) leen cada hoja A CIEGAS, por tramos de VENTANA filas con el encabezado repetido: los números aparecen como «#» (los años se ven). Así no
   pueden acomodar la lectura a un dato equivocado. Cada uno devuelve un mapa con relaciones de un catálogo cerrado
   (sumas por columnas o por filas, acumulados, índice base 100, valores que no pueden ser cero, negativos o
   repetirse) y el fundamento de cada una según los rótulos.
3. Una relación vale si al menos 2 modelos proponen la misma relación normalizada (con dos lectoras, las dos).
4. Las reglas la verifican con los números. Si se cumple en la mayoría de sus aplicaciones, los números confirman la
   lectura y las celdas donde no se cumple son señales. Si tiene pocas aplicaciones, se le pregunta a quien hizo el
   informe («¿la fila 16 es la suma de las filas 17 a 33?») y sólo con su sí da señales. Si falla en muchas, la
   lectura no se confirma y no hay señal: es más probable que la lectura esté mal que el cuadro.

Los modelos nunca calculan ni dan señales: sólo eligen del catálogo. Las expresiones se evalúan con un intérprete
cerrado (+ - * / y paréntesis), nunca con eval.
"""
from __future__ import annotations

import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import logging
import math
import os
import re
from collections import ChainMap
from itertools import combinations
from typing import Any, Callable, Optional

VERSION = "lector-1.3"
MODOS = ("apagado", "observar", "activo")
LECTORAS = ("gpt", "gemini", "deepseek")  # las que el lector sabe consultar
LECTORAS_POR_DEFECTO = ("gpt", "gemini")  # DeepSeek, sólo si se agrega en LECTOR_LECTORAS
ALIAS_LECTORAS = {"openai": "gpt", "google": "gemini"}
NO_CONSULTADA = "No se consultó: está suspendida en este despliegue"
MAX_FILAS = 5000
MAX_COLS = 512
VENTANA_COLUMNAS = 80
MAX_CELDAS_INFORME = 300_000
VENTANA = 300
ENCABEZADO = 12
MIN_NUMEROS = 6
UMBRAL_CONFIRMA = 0.7
POCAS = 3
MAX_SENALES_POR_RELACION = 5
MAX_FALLAS_CRUCE = 200  # fallas de sumas entre las que se busca una celda común (pares: ~20.000)
ESPERA_SEGUNDOS = 90
TIPOS = ("columnas", "filas", "acumulado", "no_cero", "positivo", "base_100", "no_repite")


# ---------------------------------------------------------------------------------------------- grilla
def _col(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _idx(letra: str) -> int:
    n = 0
    for ch in letra:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _valor(v: Any) -> Any:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()[:10]
    s = str(v).strip()
    return s[:200] if s else None


def _grilla_hoja(filas) -> dict[str, Any]:
    celdas = {}
    for r, fila in enumerate(filas):
        if r >= MAX_FILAS:
            break
        for c, v in enumerate(list(fila)[:MAX_COLS]):
            v = _valor(v)
            if v is not None:
                celdas[f"{_col(c)}{r + 1}"] = v
    return celdas


def _numerica(celdas: dict) -> int:
    return sum(isinstance(v, float) for v in celdas.values())


def _csv_filas(contenido: bytes, tope: Optional[int] = MAX_FILAS):
    texto = contenido.decode("utf-8-sig", errors="replace")
    sep = ";" if texto.count(";") > texto.count(",") else ","
    for fila in csv.reader(texto.splitlines()[:tope], delimiter=sep):
        out = []
        for v in fila:
            v = v.strip()
            crudo = v.replace(".", "").replace(",", ".") if sep == ";" else v.replace(",", "")
            try:
                out.append(float(crudo) if re.fullmatch(r"-?\d+(\.\d+)?", crudo) else v)
            except ValueError:
                out.append(v)
        yield out


def _recorte(filas: int, cols: int) -> Optional[str]:
    partes = []
    if filas > MAX_FILAS:
        partes.append(f"filas {MAX_FILAS + 1} a {filas}")
    if cols > MAX_COLS:
        partes.append(f"columnas {_col(MAX_COLS)} a {_col(cols - 1)}")
    return ("no se leyeron " + " y ".join(partes)) if partes else None


def _fuera_del_tope(ws) -> tuple[int, int]:
    """Última fila y columna CON VALOR (Excel cuenta como usadas las celdas vacías con formato)."""
    celdas = getattr(ws, "_cells", None)
    if celdas is None:
        return ws.max_row or 0, ws.max_column or 0
    fila = col = 0
    for (r, c), celda in celdas.items():
        if celda.value not in (None, "") and (r > MAX_FILAS or c > MAX_COLS):
            fila, col = max(fila, r), max(col, c)
    return fila, col


def grillas(leidos) -> list[dict]:
    """Grillas de TODAS las hojas con números, en el orden del libro. Lo que no se lee queda declarado en «recorte»
    (y sin celdas si la hoja entera no se lee)."""
    from services import controles_excel

    salida = []
    libros = controles_excel._libros(leidos)
    try:
        for archivo, libro in libros:
            for ws in libro.valores.worksheets:
                recorte = _recorte(*_fuera_del_tope(ws))
                celdas = _grilla_hoja(ws.iter_rows(max_row=min(ws.max_row, MAX_FILAS),
                                                max_col=min(ws.max_column, MAX_COLS), values_only=True))
                if _numerica(celdas) < MIN_NUMEROS and not recorte:
                    continue
                if ws.sheet_state != "visible":
                    salida.append(dict(archivo=archivo, hoja=ws.title, celdas={}, recorte="hoja oculta: no se lee"))
                    continue
                salida.append(dict(archivo=archivo, hoja=ws.title, celdas=celdas, recorte=recorte))
    finally:
        controles_excel._cerrar(libros)
    for archivo, contenido in leidos:
        if archivo.lower().endswith(".csv"):
            filas = list(_csv_filas(contenido, None))
            celdas = _grilla_hoja(filas)
            if _numerica(celdas) >= MIN_NUMEROS:
                salida.append(dict(archivo=archivo, hoja=archivo, celdas=celdas,
                                   recorte=_recorte(len(filas), max((len(f) for f in filas), default=0))))
    # Tope de seguridad del informe: lo que no entra, se declara.
    total = 0
    for g in salida:
        total += len(g["celdas"])
        if total > MAX_CELDAS_INFORME and g["celdas"]:
            g["celdas"], g["recorte"] = {}, "supera el tope de celdas del lector para un informe: no se lee"
    return salida


def ciego(v: Any) -> str:
    """Lo que ve el modelo: años y rótulos; cada número es «#». Los rótulos pasan por la redacción de datos personales."""
    from services.sanitizacion import redactar_texto_libre

    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and 1800 <= v <= 2100 else "#"
    s = str(v).strip()
    if re.fullmatch(r"-?[\d.,]+%?", s) and not re.fullmatch(r"(18|19|20)\d\d", s):
        return "#"
    return str(redactar_texto_libre(s))[:80]


def _por_fila(celdas: dict) -> dict[int, list]:
    filas: dict[int, list] = {}
    for ref, v in celdas.items():
        m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
        if m:
            filas.setdefault(int(m.group(2)), []).append((_idx(m.group(1)), v))
    return filas


def _texto_fila(f: int, items: list, marca: str = "") -> str:
    """Una fila para el modelo; los números contiguos van juntos («B5:J5=#») para que una hoja grande quepa."""
    partes, i = [], 0
    items = sorted(items)
    while i < len(items):
        c, v = items[i]
        t = ciego(v)
        j = i
        while t == "#" and j + 1 < len(items) and items[j + 1][0] == items[j][0] + 1 and ciego(items[j + 1][1]) == "#":
            j += 1
        partes.append(f"{_col(c)}{f}:{_col(items[j][0])}{f}=#" if j > i else f"{_col(c)}{f}={t}")
        i = j + 1
    return f"fila {f}{marca}: " + " | ".join(partes)


def tramos(celdas: dict) -> list[tuple[int, int]]:
    """Tramos de VENTANA filas: una hoja grande se lee entera, en varias lecturas."""
    ultima = max(_por_fila(celdas) or [0])
    return [(d, min(d + VENTANA - 1, ultima)) for d in range(1, ultima + 1, VENTANA)] or [(1, 1)]


def texto_tramo(celdas: dict, desde: int, hasta: int) -> str:
    filas = _por_fila(celdas)
    encabezado = [f for f in sorted(filas) if f < desde and f <= ENCABEZADO]
    lineas = [_texto_fila(f, filas[f], " (encabezado)") for f in encabezado]
    lineas += [_texto_fila(f, filas[f]) for f in sorted(filas) if desde <= f <= hasta]
    return "\n".join(lineas)


def texto_grilla(celdas: dict) -> str:
    return "\n".join(_texto_fila(f, items) for f, items in sorted(_por_fila(celdas).items()))


def huella(texto: str) -> str:
    return hashlib.sha256((VERSION + texto).encode("utf-8")).hexdigest()[:20]


def bloques_columnas(celdas: dict) -> list[tuple[int, int]]:
    """Corta sólo por columnas vacías: un cuadro contiguo conserva sus componentes juntos.

    El tamaño objetivo es 80 columnas; un cuadro sin separadores puede superar ese tamaño,
    dentro del límite declarado de la grilla. Nunca se renumeran las coordenadas originales.
    """
    usadas = sorted({_idx(re.match(r"[A-Z]+", ref).group()) for ref in celdas})
    if not usadas:
        return []
    segmentos = []
    inicio = previo = usadas[0]
    for c in usadas[1:]:
        if c > previo + 1:
            segmentos.append((inicio, previo))
            inicio = c
        previo = c
    segmentos.append((inicio, previo))
    bloques = []
    inicio, fin = segmentos[0]
    for a, b in segmentos[1:]:
        if b - inicio + 1 > VENTANA_COLUMNAS:
            bloques.append((inicio, fin))
            inicio = a
        fin = b
    bloques.append((inicio, fin))
    return bloques


def unidades(grilla: dict) -> list[dict]:
    """Lecturas por filas y bloques de columnas, con rótulos comunes y coordenadas originales."""
    if not grilla.get("celdas"):
        return []
    out = []
    celdas = grilla["celdas"]
    # Repetir el eje textual (por ejemplo, los meses), pero nunca una columna de importes.
    eje = {ref: v for ref, v in celdas.items() if re.fullmatch(r"A\d+", ref)}
    if any(isinstance(v, float) for ref, v in eje.items() if int(ref[1:]) > ENCABEZADO):
        eje = {ref: v for ref, v in eje.items() if int(ref[1:]) <= ENCABEZADO}
    for a, b in bloques_columnas(celdas):
        seleccion = {ref: v for ref, v in celdas.items()
                     if a <= _idx(re.match(r"[A-Z]+", ref).group()) <= b}
        seleccion = {**eje, **seleccion}
        for d, h in tramos(seleccion):
            texto = texto_tramo(seleccion, d, h)
            if texto:
                out.append(dict(filas=[d, h], columnas=[_col(a), _col(b)], texto=texto, huella=huella(texto)))
    return out


# ---------------------------------------------------------------------------------------------- lectura (IA)
PEDIDO = """Sos analista de estadísticas públicas. Te paso UNA hoja de una planilla oficial como grilla de celdas
(«fila N: A1=valor | B1=valor ...»). Los números están ocultos a propósito: cada celda numérica aparece como «#»
(los años se muestran); celdas numéricas contiguas van juntas («B5:J5=#» son B5 a J5, todas números). Si la hoja es
larga, recibís un tramo de filas con las filas del encabezado marcadas «(encabezado)». Si es ancha, recibís un bloque de columnas con el eje textual común repetido. Las coordenadas son las originales; proponé sólo relaciones cuyos componentes estén visibles. Tu tarea es ENTENDER el cuadro por sus rótulos, títulos, notas y su forma, y decir qué
DEBERÍA cumplir. NO calcules nada ni busques errores. Si no estás seguro de algo, no lo pongas.

Devolvé SOLO un JSON con esta forma (los ejemplos son de otro cuadro):
{
 "que_es": "una oración: qué cuadro es",
 "relaciones": [
   {"tipo": "columnas", "destino": "F", "expresion": "G + H", "filas": [20, 60],
    "fundamento": "F es «Total hogares», suma de «Urbanos» (G) y «Rurales» (H)"},
   {"tipo": "filas", "destino": 30, "expresion": "31 + 32", "columnas": ["E", "F"],
    "fundamento": "la fila 30 «Región Norte» suma sus dos provincias, filas 31 y 32"},
   {"tipo": "acumulado", "destino": "J", "componente": "I", "eje": "filas", "filas": [8, 19],
    "fundamento": "J es «Acumulado en el año» de las altas mensuales de I"},
   {"tipo": "no_cero", "columnas": ["K"], "filas": [20, 60], "fundamento": "tasa de cobertura: nunca vale 0"},
   {"tipo": "positivo", "columnas": ["L"], "filas": [20, 60], "fundamento": "cantidad de personas: no puede ser negativa"},
   {"tipo": "base_100", "celdas": ["M44", "N44"], "fundamento": "índice con base en ese período = 100: vale 100 ahí"},
   {"tipo": "no_repite", "eje": "filas", "columnas": ["C", "D"], "filas": [20, 60],
    "fundamento": "importe mensual: no debería repetirse exactamente de un mes al siguiente"}
 ],
 "no_entendido": ["partes del cuadro que no pudiste interpretar"]
}
Tipos (sólo estos): «columnas» (letras de columna con + - * / números y paréntesis; vale para cada fila del rango),
«filas» (números de fila con + - * /; vale para cada columna listada; 100 y 1000 después de * o / son escala), «acumulado» (el destino de cada período es el
destino del período anterior más el componente; eje «filas» si los períodos van en filas, «columnas» si van en
columnas, y entonces destino y componente son números de fila y el rango va en "columnas": ["B", "M"]), y reglas de
plausibilidad «no_cero», «positivo», «base_100» y «no_repite» (eje «columnas» si los períodos van en columnas,
«filas» si van en filas). Incluí totales y subtotales con sus componentes, saldos (ingresos - egresos), acumulados,
índices y las reglas de plausibilidad que se deducen de lo que mide cada columna. Usá sólo filas y columnas que
existen en la grilla.

GRILLA:
"""


def _json_de(texto: str) -> dict:
    m = re.search(r"\{.*\}", (texto or "").strip(), re.S)
    data = json.loads(m.group(0) if m else texto)
    if not isinstance(data, dict):
        raise ValueError("la respuesta no es un objeto")
    return data


def llamar(lectora: str, prompt: str) -> tuple[dict, str]:
    """Una lectura de un proveedor configurado; (mapa, modelo). Las claves sólo están en la configuración."""
    from config import settings

    if lectora == "gpt":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada")
        from openai import OpenAI

        r = OpenAI(api_key=settings.openai_api_key, timeout=ESPERA_SEGUNDOS).chat.completions.create(
            model=settings.openai_model, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}])
        return _json_de(r.choices[0].message.content), str(getattr(r, "model", settings.openai_model))
    if lectora == "gemini":
        from google import genai

        if settings.google_genai_use_enterprise:
            # Igual que la triangulación: Vertex toma las credenciales del archivo configurado.
            if settings.google_application_credentials:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
            cliente = genai.Client(vertexai=True, project=settings.google_cloud_project,
                                   location=settings.google_cloud_location or "global")
        elif settings.gemini_api_key:
            cliente = genai.Client(api_key=settings.gemini_api_key)
        else:
            raise RuntimeError("GEMINI_API_KEY no configurada")
        # El cliente queda referenciado hasta tener la respuesta: si se libera antes, se cierra la conexión.
        r = cliente.models.generate_content(
            model=settings.gemini_model, contents=prompt,
            config={"temperature": 0, "response_mime_type": "application/json"})
        # Sólo las partes de texto (los modelos que razonan agregan partes de pensamiento).
        texto = "".join(getattr(p, "text", "") or "" for c in (getattr(r, "candidates", None) or [])
                        for p in (getattr(getattr(c, "content", None), "parts", None) or [])
                        if not getattr(p, "thought", False))
        return _json_de(texto or r.text), settings.gemini_model
    if lectora == "deepseek":
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY no configurada")
        import httpx

        url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        r = httpx.post(url, headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                       timeout=ESPERA_SEGUNDOS, json={
                           "model": settings.deepseek_model, "temperature": 0,
                           "response_format": {"type": "json_object"},
                           "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return _json_de(r.json()["choices"][0]["message"]["content"]), settings.deepseek_model
    raise ValueError(f"lectora desconocida: {lectora}")


def lectoras_pedidas() -> list[str]:
    """Las de LECTOR_LECTORAS, en el orden de LECTORAS; si no nombra ninguna conocida, las de por defecto."""
    from config import settings

    nombres = {m.strip().lower() for m in str(getattr(settings, "lector_lectoras", "") or "").split(",") if m.strip()}
    nombres = {ALIAS_LECTORAS.get(m, m) for m in nombres}
    if nombres - set(LECTORAS):
        logging.getLogger(__name__).warning("LECTOR_LECTORAS nombra lectoras desconocidas, que no se consultan: %s",
                                            ", ".join(sorted(nombres - set(LECTORAS))))
    return [lectora for lectora in LECTORAS if lectora in nombres] or list(LECTORAS_POR_DEFECTO)


def lectoras_habilitadas() -> list[str]:
    from config import settings

    return [lectora for lectora in lectoras_pedidas() if settings.modelo_habilitado(lectora)]


def lectoras_suspendidas() -> list[str]:
    """Pedidas pero suspendidas en MODELOS_SUSPENDIDOS: con dos lectoras, la que falta deja sin acuerdo; se declara."""
    from config import settings

    return [lectora for lectora in lectoras_pedidas() if not settings.modelo_habilitado(lectora)]


def leer(texto: str, lectoras: list[str], fn: Optional[Callable] = None) -> dict[str, dict]:
    """Las lectoras leen el mismo tramo a la vez; un proveedor que falla no frena a los demás."""
    prompt = PEDIDO + texto
    fn = fn or llamar  # se resuelve al usarla (las pruebas la sustituyen)

    def una(lectora):
        try:
            mapa, modelo = fn(lectora, prompt)
            relaciones = [r for r in (mapa.get("relaciones") or []) if isinstance(r, dict) and r.get("tipo") in TIPOS]
            return lectora, dict(modelo=modelo, que_es=str(mapa.get("que_es") or "")[:300],
                                 relaciones=relaciones[:60], error=None)
        except Exception as e:  # noqa: BLE001 — se registra el motivo y se sigue con las demás
            return lectora, dict(modelo=None, que_es="", relaciones=[], error=f"{type(e).__name__}: {str(e)[:160]}")

    if not lectoras:
        return {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(lectoras)) as ex:
        return dict(ex.map(una, lectoras))


# ---------------------------------------------------------------------------------------------- intérprete cerrado
_TOKEN = re.compile(r"\s*(?:([A-Z]{1,3})|(\d+(?:\.\d+)?)|([-+*/()]))")


def _tokens(expr: str) -> Optional[list[tuple[str, str]]]:
    s, pos, out = str(expr or "").upper(), 0, []
    while pos < len(s):
        if s[pos:].strip() == "":
            break
        m = _TOKEN.match(s, pos)
        if not m:
            return None
        if m.group(1):
            out.append(("letra", m.group(1)))
        elif m.group(2):
            out.append(("numero", m.group(2)))
        else:
            out.append(("op", m.group(3)))
        pos = m.end()
    return out or None


def calcular(expr: str, valor: Callable[[str], Optional[float]], tipo: str) -> tuple[Optional[float], bool]:
    """Evalúa + - * / ( ) sobre referencias. En «columnas» las letras son columnas; en «filas» los enteros son filas,
    salvo 100 o 1000 justo después de * o / (escala: «32 / 31 * 100»). Devuelve (resultado, usa * o /)."""
    toks = _tokens(expr)
    if not toks or len(toks) > 80:
        return None, False
    pos = 0
    refs = []
    mult = any(t == ("op", "*") or t == ("op", "/") for t in toks)

    def ver():
        return toks[pos] if pos < len(toks) else ("fin", "")

    def tomar():
        nonlocal pos
        pos += 1
        return toks[pos - 1]

    def factor():
        tipo_t, t = ver()
        anterior = toks[pos - 1] if pos else ("", "")
        if t == "-" and tipo_t == "op":
            tomar()
            return -factor()
        if t == "(":
            tomar()
            v = suma()
            if ver() != ("op", ")"):
                raise ValueError("paréntesis")
            tomar()
            return v
        if tipo_t == "letra":
            tomar()
            if tipo != "columnas":
                raise ValueError("letra en relación por filas")
            refs.append(t)
            v = valor(t)
            if v is None:
                raise LookupError(t)
            return v
        if tipo_t == "numero":
            tomar()
            escala = t in ("100", "1000") and anterior in (("op", "*"), ("op", "/"))
            es_ref = tipo == "filas" and t.isdigit() and not escala
            if es_ref:
                refs.append(t)
                v = valor(t)
                if v is None:
                    raise LookupError(t)
                return v
            return float(t)
        raise ValueError("expresión")

    def producto():
        v = factor()
        while ver() in (("op", "*"), ("op", "/")):
            op = tomar()[1]
            d = factor()
            v = v * d if op == "*" else v / d
        return v

    def suma():
        v = producto()
        while ver() in (("op", "+"), ("op", "-")):
            op = tomar()[1]
            d = producto()
            v = v + d if op == "+" else v - d
        return v

    try:
        res = suma()
    except (ValueError, LookupError, ZeroDivisionError):
        return None, False
    if pos != len(toks) or not refs or not math.isfinite(res):
        return None, False
    return res, mult


# ---------------------------------------------------------------------------------------------- verificación
def _numero(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _decimales(v: float) -> int:
    s = f"{round(v, 6):.6f}".rstrip("0").rstrip(".")
    return len(s.split(".")[1]) if "." in s else 0


def _tolerancia(destino: float, calculado: float, usados: list[float], mult: bool) -> float:
    if mult:
        return 0.01 * max(abs(destino), abs(calculado)) + 0.05
    return sum(0.5 * 10 ** (-min(_decimales(v), 4)) for v in [destino] + usados) + 1e-6 * abs(destino)


def _rango_filas(rel) -> range:
    f = rel.get("filas") or []
    try:
        a, b = int(f[0]), int(f[-1])
    except (TypeError, ValueError, IndexError):
        return range(0)
    return range(max(1, a), min(MAX_FILAS, b) + 1)


def _letras(lista) -> list[str]:
    return [str(c).strip().upper() for c in (lista or []) if re.fullmatch(r"[A-Za-z]{1,3}", str(c).strip())]


def _rango_letras(lista) -> list[str]:
    letras = _letras(lista)
    if len(letras) == 2 and _idx(letras[1]) - _idx(letras[0]) > 1:
        return [_col(i) for i in range(_idx(letras[0]), min(_idx(letras[1]), MAX_COLS - 1) + 1)]
    return letras


def _celdas_de(lista) -> list[str]:
    out = []
    for x in lista or []:
        m = re.fullmatch(r"\$?([A-Z]{1,3})\$?(\d+)", str(x).strip().upper())
        if m:
            out.append(f"{m.group(1)}{m.group(2)}")
    return out


def _aplicaciones(rel: dict, celdas: dict) -> list[dict]:
    tipo, apl = rel.get("tipo"), []

    def ap(destino, usadas, ok, **extra):
        apl.append(dict(celda=destino, celdas=sorted({destino, *usadas}), ok=bool(ok), **extra))

    if tipo in ("columnas", "filas"):
        if tipo == "columnas":
            destino_col = str(rel.get("destino") or "").strip().upper()
            if not re.fullmatch(r"[A-Z]{1,3}", destino_col):
                return []
            puntos = [(f"{destino_col}{f}", f, None) for f in _rango_filas(rel)]
        else:
            try:
                destino_fila = int(rel.get("destino"))
            except (TypeError, ValueError):
                return []
            puntos = [(f"{c}{destino_fila}", None, c) for c in _rango_letras(rel.get("columnas"))]
        for destino, f, c in puntos:
            d = _numero(celdas.get(destino))
            if d is None:
                continue
            usadas, vals = [], []

            def valor(x, f=f, c=c):
                ref = f"{x}{f}" if tipo == "columnas" else f"{c}{x}"
                v = _numero(celdas.get(ref))
                usadas.append(ref)
                vals.append(v)
                return v
            res, mult = calcular(rel.get("expresion"), valor, tipo)
            if res is None or destino in usadas:
                continue
            ap(destino, usadas, abs(d - res) <= _tolerancia(d, res, vals, mult), declarado=d, calculado=round(res, 6))
    elif tipo == "acumulado":
        if rel.get("eje") == "columnas":
            try:
                fd, fc = int(rel.get("destino")), int(rel.get("componente"))
            except (TypeError, ValueError):
                return []
            pasos = [(f"{c}{fd}", f"{c}{fc}") for c in _rango_letras(rel.get("columnas"))]
        else:
            cd = str(rel.get("destino") or "").strip().upper()
            cc = str(rel.get("componente") or "").strip().upper()
            if not (re.fullmatch(r"[A-Z]{1,3}", cd) and re.fullmatch(r"[A-Z]{1,3}", cc)):
                return []
            pasos = [(f"{cd}{f}", f"{cc}{f}") for f in _rango_filas(rel)]
        for (d0, _), (d1, c1) in zip(pasos, pasos[1:]):
            a, b, x = _numero(celdas.get(d0)), _numero(celdas.get(d1)), _numero(celdas.get(c1))
            if a is None or b is None or x is None:
                continue
            res = a + x
            ap(d1, [d0, c1], abs(b - res) <= _tolerancia(b, res, [a, x], False), declarado=b, calculado=round(res, 6))
    elif tipo in ("no_cero", "positivo"):
        for c in _rango_letras(rel.get("columnas")):
            for f in _rango_filas(rel):
                v = _numero(celdas.get(f"{c}{f}"))
                if v is not None:
                    ap(f"{c}{f}", [], v != 0 if tipo == "no_cero" else v >= 0, declarado=v)
    elif tipo == "base_100":
        for ref in _celdas_de(rel.get("celdas")):
            v = _numero(celdas.get(ref))
            if v is not None:
                ap(ref, [], abs(v - 100) <= 0.5, declarado=v, calculado=100.0)
    elif tipo == "no_repite":
        cols, filas = _rango_letras(rel.get("columnas")), list(_rango_filas(rel))
        pares = ([(f"{a}{f}", f"{b}{f}") for f in filas for a, b in zip(cols, cols[1:])] if rel.get("eje") != "filas"
                 else [(f"{c}{a}", f"{c}{b}") for c in cols for a, b in zip(filas, filas[1:])])
        for x, y in pares:
            vx, vy = _numero(celdas.get(x)), _numero(celdas.get(y))
            if vx is not None and vy is not None and vx != 0:
                ap(y, [x], vx != vy, declarado=vy)
    return apl


def verificar(rel: dict, celdas: dict) -> dict:
    """confirmada (los números confirman la lectura) / pocas (hay que preguntar) / no_confirmada / desconocida."""
    try:
        apl = _aplicaciones(rel, celdas)
    except (TypeError, ValueError, AttributeError):
        apl = []
    n, fallas = len(apl), [a for a in apl if not a["ok"]]
    tipo = rel.get("tipo")
    limite = 0.9 if tipo == "no_repite" else UMBRAL_CONFIRMA
    if n == 0:
        estado = "desconocida"
    elif n > POCAS or tipo in ("no_cero", "positivo", "no_repite"):
        estado = "confirmada" if (n - len(fallas)) >= limite * n else "no_confirmada"
    else:
        estado = "confirmada" if not fallas else "pocas"
    zona = sorted({c for a in apl for c in a["celdas"]})
    return dict(estado=estado, zona=zona, aplicaciones=n, fallas=fallas)


def _expresion_normal(expr) -> str:
    """«D + C» y «C+D» son la misma suma: los términos de una suma pura se ordenan."""
    s = re.sub(r"\s+", "", str(expr or "").upper())
    if re.fullmatch(r"[A-Z0-9]+(\+[A-Z0-9]+)*", s):
        return "+".join(sorted(s.split("+")))
    return s


def clave(rel: dict) -> tuple:
    """Lo que hace que dos propuestas sean la misma relación, aunque cada modelo le ponga otro rango de filas."""
    t = rel.get("tipo")
    if t in ("columnas", "filas"):
        return (t, str(rel.get("destino")).strip().upper(), _expresion_normal(rel.get("expresion")))
    if t == "acumulado":
        return (t, str(rel.get("destino")).strip().upper(), str(rel.get("componente")).strip().upper(), rel.get("eje"))
    if t == "base_100":
        return (t, tuple(sorted(_celdas_de(rel.get("celdas")))))
    return (t, tuple(sorted(_rango_letras(rel.get("columnas")))), rel.get("eje"))


def _texto_relacion(r: dict) -> str:
    t = r.get("tipo")
    if t in ("columnas", "filas"):
        return f"{r.get('destino')} = {r.get('expresion')}"
    if t == "acumulado":
        return f"{r.get('destino')} acumula {r.get('componente')}"
    alcance = r.get("celdas") or r.get("columnas") or []
    return f"{t} en {', '.join(map(str, alcance))[:60]}"


def acordar(mapas: dict[str, dict], celdas: dict, *, archivo: str = "", hoja: str = "") -> list[dict]:
    """Grupos de relaciones de lectoras distintas: la misma relación (mismo tipo, destino y fórmula, aunque el rango
    difiera). Compartir celdas no demuestra que las relaciones sean equivalentes."""
    rels = []
    for lectora, m in mapas.items():
        for r in m.get("relaciones") or []:
            v = verificar(r, celdas)
            if v["zona"]:
                rels.append(dict(rel=r, lectora=lectora, **v))
    claves = [clave(r["rel"]) for r in rels]
    grupos, usados = [], set()
    for i, r in enumerate(rels):
        if i in usados:
            continue
        g = [i]
        # Un voto por proveedor y sólo por la misma relación normalizada.
        for j in range(i + 1, len(rels)):
            if j in usados or rels[j]["lectora"] in {rels[k]["lectora"] for k in g}:
                continue
            if claves[j] == claves[i]:
                g.append(j)
        usados |= set(g)
        grupos.append([rels[k] for k in g])
    salida, crudas = [], []
    for g in grupos:
        if len(g) < 2:
            continue
        # Fallas que al menos 2 lectoras encuentran en el mismo lugar.
        fallas, propias = {}, {}
        for r in g:
            for fa in r["fallas"]:
                if any(set(fa["celdas"]) & set(fb["celdas"]) for s in g if s is not r for fb in s["fallas"]):
                    fallas.setdefault(fa["celda"], fa)
                    propias.setdefault(fa["celda"], r["rel"])  # el rango de la lectora que la encontró
        ok = sum(r["estado"] == "confirmada" for r in g)
        pocas = sum(r["estado"] == "pocas" for r in g)
        if ok >= 2:
            estado = "confirmada"
        elif ok + pocas >= 2 and pocas:
            estado = "a_confirmar"
        else:
            estado = "no_confirmada"
        base = g[0]["rel"]
        texto = _texto_relacion(base)
        # Una respuesta sólo autoriza esta relación en este archivo, hoja y zona.
        # El prefijo evita reutilizar los identificadores ambiguos de lector-1/1.1.
        identidad = [archivo, hoja, clave(base), sorted(set().union(*[set(r["zona"]) for r in g]))]
        gid = "r2-" + hashlib.sha256(json.dumps(identidad, ensure_ascii=False).encode()).hexdigest()[:24]
        ordenadas = sorted(fallas.values(), key=lambda f: (len(f["celda"]), f["celda"]))
        salida.append(dict(
            id=gid, tipo=base.get("tipo"), relacion=texto, fundamento=str(base.get("fundamento") or "")[:300],
            lectoras=[r["lectora"] for r in g], estado=estado, aplicaciones=max(r["aplicaciones"] for r in g),
            fallas=[dict(celda=f["celda"], declarado=f.get("declarado"), calculado=f.get("calculado"))
                    for f in ordenadas]))
        crudas.append((estado, [(f, propias[f["celda"]]) for f in ordenadas]))
    _cruzar(salida, crudas, celdas)
    return salida


def _cierra(rel: dict, destino: str, celdas) -> bool:
    """La relación cierra en esa celda destino; se calcula sólo esa aplicación."""
    m = re.fullmatch(r"([A-Z]{1,3})(\d+)", destino)
    if m and rel.get("tipo") == "columnas":
        rel = dict(rel, filas=[int(m.group(2))] * 2)
    elif m and rel.get("tipo") == "filas":
        rel = dict(rel, columnas=[m.group(1)])
    try:
        return any(a["celda"] == destino and a["ok"] for a in _aplicaciones(rel, celdas))
    except (TypeError, ValueError, AttributeError):
        return False


def _cruzar(salida: list[dict], crudas: list[tuple[str, list[tuple[dict, dict]]]], celdas: dict) -> None:
    """Fila × columna: una sola celda común a dos sumas que no cierran por la misma diferencia.

    Si con esa celda corregida cierran las dos, es la ubicación más probable (como la triangulación de totales
    del motor): cada falla guarda la celda, el valor que las cierra y la otra cuenta. Si alguna de las dos fallas
    admite más de una celda así (dos filas fallan por lo mismo en la misma columna), no se marca ninguna.
    Las relaciones que los números no confirman no dan señales: tampoco entran al cruce."""
    fallas = [(i, k, rel, f) for i, (estado, fs) in enumerate(crudas) if estado != "no_confirmada"
              for k, (f, rel) in enumerate(fs) if rel.get("tipo") in ("columnas", "filas")
              and _numero(f.get("declarado")) is not None and _numero(f.get("calculado")) is not None]
    if len(fallas) > MAX_FALLAS_CRUCE:
        return
    hallados: dict[tuple[int, int], list[tuple[tuple[int, int], dict]]] = {}
    for (i, k, ra, fa), (j, m, rb, fb) in combinations(fallas, 2):
        if i == j:
            continue
        comunes = (set(fa["celdas"]) & set(fb["celdas"])) - {fa["celda"], fb["celda"]}
        da, db = fa["calculado"] - fa["declarado"], fb["calculado"] - fb["declarado"]
        if len(comunes) != 1 or abs(abs(da) - abs(db)) > 1e-3 * max(abs(da), abs(db)) + 1e-6:
            continue
        x = comunes.pop()
        v = _numero(celdas.get(x))
        if v is None:
            continue
        for nuevo in (v - da, v + da):
            prueba = ChainMap({x: nuevo}, celdas)
            if _cierra(ra, fa["celda"], prueba) and _cierra(rb, fb["celda"], prueba):
                valor = round(nuevo, 6)
                hallados.setdefault((i, k), []).append(((j, m), dict(celda=x, valor_que_cierra=valor, con=fb["celda"],
                                                                      relacion_id=salida[j]["id"])))
                hallados.setdefault((j, m), []).append(((i, k), dict(celda=x, valor_que_cierra=valor, con=fa["celda"],
                                                                      relacion_id=salida[i]["id"])))
                break
    for (i, k), opciones in hallados.items():
        if len(opciones) == 1 and len(hallados[opciones[0][0]]) == 1:
            salida[i]["fallas"][k]["cruce"] = opciones[0][1]


# ---------------------------------------------------------------------------------------------- señales
def _cifra(v) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").rstrip("0").rstrip(",")


def _grupo_controlado(g: dict, confirmaciones: dict) -> bool:
    persona = (confirmaciones.get(g.get("id")) or {}).get("confirma")
    return persona is not False and (g.get("estado") == "confirmada" or
                                    (g.get("estado") == "a_confirmar" and persona is True))


def senales(hojas: list[dict], confirmaciones: dict) -> list[dict]:
    out = []
    for h in hojas:
        controladas = {g.get("id") for g in h.get("grupos") or [] if _grupo_controlado(g, confirmaciones)}
        for g in h.get("grupos") or []:
            if not _grupo_controlado(g, confirmaciones):
                continue
            quien = "los números del propio cuadro" if g["estado"] == "confirmada" else "quien hizo el informe"
            aritmetica = g["tipo"] in ("columnas", "filas", "acumulado", "base_100")
            for f in g["fallas"][:MAX_SENALES_POR_RELACION]:
                if g["tipo"] == "base_100":
                    texto = (f"{h['hoja']}!{f['celda']}: según cómo se lee el cuadro ({g['fundamento'] or g['relacion']}), "
                             f"es el período base del índice y debería valer 100; vale {_cifra(f.get('declarado'))}.")
                elif aritmetica:
                    # Una cuenta que no cierra no dice cuál de las celdas está mal: el total o alguna de sus partes.
                    texto = (f"{h['hoja']}!{f['celda']}: según cómo se lee el cuadro ({g['fundamento'] or g['relacion']}), "
                             f"la cuenta no cierra: con las demás celdas da {_cifra(f.get('calculado'))} y la celda dice "
                             f"{_cifra(f.get('declarado'))}. Alguna de las celdas que intervienen no está bien.")
                else:
                    texto = (f"{h['hoja']}!{f['celda']}: vale {_cifra(f.get('declarado'))}, y según cómo se lee el "
                             f"cuadro no debería ({g['fundamento'] or g['relacion']}).")
                # La otra cuenta sólo cuenta si también está controlada (confirmada por los números o la persona).
                cruce = f.get("cruce") if aritmetica and (f.get("cruce") or {}).get("relacion_id") in controladas else None
                if cruce:
                    texto += (f" La celda {h['hoja']}!{cruce['celda']} interviene en esta cuenta y en la de "
                              f"{h['hoja']}!{cruce['con']}, que no cierra por la misma diferencia; con "
                              f"{_cifra(cruce['valor_que_cierra'])} en {cruce['celda']} cerrarían las dos: es la "
                              "ubicación más probable.")
                total = len(g["fallas"])
                mostradas = min(total, MAX_SENALES_POR_RELACION)
                if total > mostradas:
                    texto += (f" Se muestran {mostradas} de {total} diferencias de esta relación; "
                              f"hay {total - mostradas} adicionales registradas.")
                out.append({
                    "lente": "conciliador",
                    "modo": "relacion_leida_no_cierra" if aritmetica else "plausibilidad_leida",
                    "descripcion": texto,
                    "severidad": "alta" if aritmetica else "media",
                    "incertidumbre": "baja" if g["estado"] == "a_confirmar" else "media",
                    "tipo_evidencia": "REGLA_FORMAL_O_ARITMETICA",
                    "metodo": f"lectura a ciegas de {len(g['lectoras'])} modelos de IA; verificación determinística; "
                              f"lectura confirmada por {quien}",
                    "evidencia": {
                        "regla": "relacion_leida_no_cierra" if aritmetica else "plausibilidad_leida",
                        # «archivo_origen», como las del motor: así una señal del lector y una del motor sobre
                        # la misma celda del mismo libro se agrupan en un caso, y no se mezclan libros distintos.
                        "archivo": h["archivo"], "archivo_origen": h["archivo"], "hoja": h["hoja"], "celda": f["celda"],
                        "relacion": g["relacion"], "fundamento": g["fundamento"], "lectoras": g["lectoras"],
                        "lectura_confirmada_por": "numeros" if g["estado"] == "confirmada" else "persona",
                        "aplicaciones": g["aplicaciones"], "declarado": f.get("declarado"),
                        "calculado": f.get("calculado"), "relacion_id": g["id"], "version": VERSION,
                        "diferencias_total": total, "diferencias_mostradas": mostradas,
                    },
                    "pregunta_institucional": f"Verificar {h['hoja']}!{f['celda']} contra la relación «{g['relacion']}».",
                    "limites": {"fundamento_regla": {
                        "regla": "relacion_leida_no_cierra" if aritmetica else "plausibilidad_leida",
                        "fuente": f"{h['archivo']} · {h['hoja']}",
                        "alcance": "relación propuesta por al menos dos modelos y contrastada con "
                                   f"{quien}; requiere revisar la interpretación y las celdas de origen",
                        "estado": "requiere_revision_humana",
                    }},
                })
                if cruce:
                    celda = f"{h['hoja']}!{cruce['celda']}"
                    out[-1]["evidencia"].update(
                        celda_probable=cruce["celda"], valor_que_cierra=cruce["valor_que_cierra"],
                        cuenta_cruzada=cruce["con"], ubicaciones_excel=[celda, f"{h['hoja']}!{f['celda']}"],
                        # Las dos cuentas y la triangulación del motor sobre la misma celda son un único caso.
                        grupo_relacion=f"celda:{celda}")
                    out[-1]["pregunta_institucional"] = (f"Verificar {celda} contra la fuente: con ese valor corregido "
                                                         "cerrarían las dos cuentas.")
    return out


def preguntas(hojas: list[dict], confirmaciones: dict) -> list[dict]:
    """Lo que hay que preguntarle a quien hizo el informe: relaciones con pocas aplicaciones."""
    return [dict(id=g["id"], archivo=h["archivo"], hoja=h["hoja"], relacion=g["relacion"], fundamento=g["fundamento"],
                 lectoras=g["lectoras"], respuesta=(confirmaciones.get(g["id"]) or {}).get("confirma"))
            for h in hojas for g in h.get("grupos") or [] if g["estado"] == "a_confirmar"]


def modo() -> str:
    from config import settings

    m = str(getattr(settings, "lector_ia", "apagado") or "apagado").strip().lower()
    return m if m in MODOS else "apagado"


def lectura_fallida(saneamiento: dict, etapa: str) -> dict:
    """Persistir una falla operativa sin exportar excepciones ni aparentar cobertura."""
    motivos = {"grillas": "No se pudo preparar la grilla para el lector del cuadro",
               "analizar": "No se pudo completar el análisis del lector del cuadro"}
    motivo = motivos[etapa]
    previo = (saneamiento or {}).get("mapa_lectura") or {}
    estado = dict(version=VERSION, modo=modo(), hojas=[], preguntas=[], senales=0,
                  confirmaciones=dict(previo.get("confirmaciones") or {}),
                  historial_confirmaciones=list(previo.get("historial_confirmaciones") or []),
                  fallo=dict(etapa=etapa, motivo=motivo),
                  sin_leer=[dict(archivo="Archivo cargado", hoja="no determinada", motivo=motivo)])
    return dict(estado=estado, senales=[])


def analizar(saneamiento: dict, fn: Optional[Callable] = None, lectoras: Optional[list[str]] = None,
             modo_forzado: Optional[str] = None) -> Optional[dict]:
    """Lee (o reusa la lectura guardada si la grilla no cambió), acuerda y verifica. Devuelve el estado a guardar en
    saneamiento["mapa_lectura"] y las señales (sólo en modo activo)."""
    m = modo_forzado or modo()
    grillas_ = (saneamiento or {}).get("grillas_lectura") or []
    if m == "apagado":
        return None
    if not grillas_:
        if (saneamiento or {}).get("lector_preparacion_fallida"):
            lectura = lectura_fallida(saneamiento, "grillas")
            lectura["estado"]["modo"] = m
            return lectura
        return None
    previo = (saneamiento or {}).get("mapa_lectura") or {}
    guardadas = {h.get("huella"): h for h in previo.get("hojas") or []}
    confirmaciones = dict(previo.get("confirmaciones") or {})
    lectoras = lectoras if lectoras is not None else lectoras_habilitadas()
    hojas, sin_leer = [], []
    for g in grillas_:
        if g.get("recorte"):
            sin_leer.append(dict(archivo=g["archivo"], hoja=g["hoja"], motivo=g["recorte"]))
        for u in unidades(g):
            anterior = guardadas.get(u["huella"])
            mapas = dict((anterior or {}).get("mapas") or {})
            pendientes = [lectora for lectora in lectoras if lectora not in mapas or mapas[lectora].get("error")]
            if pendientes:
                # Al reanalizar, recuperar sólo las respuestas faltantes; conservar las lecturas válidas.
                mapas.update(leer(u["texto"], pendientes, fn))
            hojas.append(dict(archivo=g["archivo"], hoja=g["hoja"], filas=u["filas"], columnas=u["columnas"], huella=u["huella"], mapas=mapas,
                              grupos=acordar(mapas, g["celdas"], archivo=g["archivo"], hoja=g["hoja"])))
    todas = senales(hojas, confirmaciones)
    estado = dict(version=VERSION, modo=m, hojas=hojas, confirmaciones=confirmaciones, sin_leer=sin_leer,
                  historial_confirmaciones=list(previo.get("historial_confirmaciones") or []),
                  preguntas=preguntas(hojas, confirmaciones), senales=len(todas))
    return dict(estado=estado, senales=todas if m == "activo" else [])


def resumen_lectura(mapa: dict) -> dict:
    """Cobertura de las respuestas recibidas, independiente de que hayan propuesto relaciones."""
    hojas = mapa.get("hojas") or []
    respuestas = [list((h.get("mapas") or {}).values()) for h in hojas]
    suficientes = sum(sum(not r.get("error") for r in rs) >= 2 for rs in respuestas)
    fallidas = sum(bool(r.get("error")) for rs in respuestas for r in rs)
    if mapa.get("fallo") or not suficientes:
        estado = "no_completada"
    elif suficientes < len(hojas) or fallidas or mapa.get("sin_leer"):
        estado = "parcial"
    else:
        estado = "completada"
    controlados = [(h, g) for h in hojas for g in h.get("grupos") or []
                   if _grupo_controlado(g, mapa.get("confirmaciones") or {})]
    total = sum(len(g.get("fallas") or []) for _, g in controlados)
    mostradas = sum(min(len(g.get("fallas") or []), MAX_SENALES_POR_RELACION) for _, g in controlados)
    limites = [dict(archivo=h.get("archivo"), hoja=h.get("hoja"), relacion=g.get("relacion"),
                    total=len(g["fallas"]), mostradas=MAX_SENALES_POR_RELACION)
               for h, g in controlados if len(g.get("fallas") or []) > MAX_SENALES_POR_RELACION]
    return dict(estado=estado, tramos=len(hojas), tramos_con_lectura=suficientes,
                hojas=len({(h.get("archivo"), h.get("hoja")) for h in hojas}),
                lecturas_fallidas=fallidas,
                relaciones_acordadas=sum(len(h.get("grupos") or []) for h in hojas),
                relaciones_controladas=len(controlados), diferencias_total=total,
                diferencias_mostradas=mostradas, diferencias_no_mostradas=total - mostradas,
                limites_de_muestra=limites)


def saneamiento_publico(saneamiento: Optional[dict], puede_confirmar: bool = False) -> Optional[dict]:
    """Lo que viaja a la pantalla: sin las grillas con números ni las respuestas completas de los modelos."""
    from services import interpretacion_previa as ip
    if saneamiento and ip.CAMPO in saneamiento:
        saneamiento = dict(saneamiento, **{ip.CAMPO: ip.publico(saneamiento[ip.CAMPO])})
    if not saneamiento or not ({"grillas_lectura", "mapa_lectura"} & set(saneamiento)):
        return saneamiento
    out = {k: v for k, v in saneamiento.items() if k != "grillas_lectura"}
    mapa = saneamiento.get("mapa_lectura")
    if mapa:
        requiere_reanalisis = mapa.get("version") != VERSION
        out["mapa_lectura"] = dict(
            version=mapa.get("version"), modo=mapa.get("modo"), senales=mapa.get("senales"),
            preguntas=mapa.get("preguntas") or [], puede_confirmar=bool(puede_confirmar and not requiere_reanalisis),
            requiere_reanalisis=requiere_reanalisis, resumen=resumen_lectura(mapa),
            fallo=mapa.get("fallo"),
            sin_leer=mapa.get("sin_leer") or [],
            hojas=[dict(archivo=h.get("archivo"), hoja=h.get("hoja"), filas=h.get("filas"), columnas=h.get("columnas"),
                        lecturas={k: dict(que_es=v.get("que_es"), error=bool(v.get("error")))
                                  for k, v in (h.get("mapas") or {}).items()},
                        relaciones_acordadas=len(h.get("grupos") or []))
                   for h in mapa.get("hojas") or []])
    return out


def confirmar(saneamiento: dict, pregunta_id: str, confirma: bool, usuario_id: int) -> tuple[dict, dict]:
    """Registra la respuesta a una pregunta del lector (vale la última; las anteriores quedan en el historial).
    Devuelve (saneamiento nuevo, pregunta actualizada). La señal se calcula al volver a analizar."""
    mapa = dict((saneamiento or {}).get("mapa_lectura") or {})
    if mapa.get("version") != VERSION:
        raise ValueError("Volvé a analizar el informe para confirmar cada relación en su archivo y hoja. Se conserva el historial anterior.")
    pregunta = next((q for q in mapa.get("preguntas") or [] if q.get("id") == pregunta_id), None)
    if pregunta is None:
        raise KeyError(pregunta_id)
    ubicaciones = {(q.get("archivo"), q.get("hoja"))
                   for q in mapa.get("preguntas") or [] if q.get("id") == pregunta_id}
    if len(ubicaciones) != 1:
        raise ValueError("La pregunta corresponde a más de una relación. Volvé a analizar el informe antes de responder.")
    registro = dict(confirma=bool(confirma), usuario_id=usuario_id, fecha=dt.datetime.utcnow().isoformat(timespec="seconds"))
    mapa["confirmaciones"] = {**(mapa.get("confirmaciones") or {}), pregunta_id: registro}
    mapa["historial_confirmaciones"] = [*(mapa.get("historial_confirmaciones") or []), dict(registro, id=pregunta_id)]
    mapa["preguntas"] = [dict(q, respuesta=bool(confirma)) if q.get("id") == pregunta_id else q
                         for q in mapa.get("preguntas") or []]
    nuevo = dict(saneamiento, mapa_lectura=mapa)
    return nuevo, next(q for q in mapa["preguntas"] if q.get("id") == pregunta_id)
