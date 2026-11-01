"""Capa exploratoria: hipotesis no validadas sobre un informe.

Fase experimental. Este modulo es deliberadamente ajeno al protocolo B-1/R-1:
su salida (una HipotesisExploratoria) no es un Hallazgo, no usa Severidad ni
los estados `conforme`/`observado` de enums.py, y ni services/certificaciones.py
ni routers/certificaciones.py lo importan (ver tests/test_pared_exploratoria.py).
Una hipotesis exploratoria no admite grados: HIPOTESIS_NO_VALIDADA es el
unico estado posible -- no hay escala de confianza numerica ni ranking,
porque un numero invita a leer una conjetura como medicion.

Dos pistas, elegidas porque son las que menos se prestan a leerse como
imputacion:

  Pista A -- preguntas que ningun analista formulo: un modelo lee el informe
  y propone interrogantes que las siete lentes no anticiparon (se le pasan
  las preguntas canonicas de services.lens_matrix con la consigna explicita
  de no repetirlas).

  Pista B -- correlaciones entre dimensiones que nadie declaro relacionadas:
  el calculo es determinista en Python, igual que el resto de los calculos
  del sistema. El modelo de lenguaje solo redacta la comunicacion del
  resultado, y siempre como coincidencia observada, nunca como causa.

Exclusion deliberada, no un olvido: este modulo nunca compara un informe con
antecedentes que terminaron en correccion. Señalar por semejanza se acerca a
atribuir responsabilidad por parecido, que es precisamente lo que este
sistema no hace. No agregar esa comparacion mas adelante creyendo que es una
mejora.
"""
from __future__ import annotations

import json
import re
import unicodedata
from enum import Enum
from typing import Any

import models
from config import settings
from services import ambito as ambito_svc
from services import guardrails
from services.lens_matrix import LENS_MATRIX
from services.plural import contar
from services.triangulacion_validacion import (
    CONSIGNA_DATOS,
    delimitar,
    es_instruccion,
    neutralizar_valor,
)

ESTADO_HIPOTESIS_NO_VALIDADA = "HIPOTESIS_NO_VALIDADA"

ROTULO_EXPERIMENTAL = (
    "Capa exploratoria -- fase experimental. Lo que sigue es una hipótesis "
    "no validada: no es un hallazgo, no fue revisada por ninguna lente y no "
    "interviene en ninguna constancia de certificación (B-1 ni R-1)."
)

DISCLAIMER_CORRELACION = (
    "esto es una coincidencia observada entre dos variables, no una relación "
    "causal: una correlación no implica que una cause la otra."
)

MAX_PREGUNTAS_PISTA_A = 5
# Dos corridas se distinguen por el momento de guardado: una corrida guarda
# todas sus hipótesis juntas.
SEPARACION_CORRIDAS_SEGUNDOS = 5


def _tipo_informe() -> str:
    """Cómo nombrar el informe en los prompts, según el ámbito declarado."""
    return "de una organización" if ambito_svc.es_organizacion() else "de gestion publica"
MAX_CORRELACIONES_PISTA_B = 5
UMBRAL_CORRELACION = 0.6


class TipoPista(str, Enum):
    PREGUNTAS_NO_FORMULADAS = "preguntas_no_formuladas"
    CORRELACIONES_NO_DECLARADAS = "correlaciones_no_declaradas"


# --- Pista A: preguntas que ningun analista formulo -------------------------


def preguntas_canonicas_de_las_lentes() -> list[str]:
    """Todas las preguntas ya cubiertas por las siete lentes, tal como estan
    en la matriz canonica -- lo que la Pista A tiene prohibido repetir."""
    preguntas: list[str] = []
    for lente in LENS_MATRIX:
        preguntas.append(lente["pregunta_central"])
        preguntas.extend(lente["preguntas"])
    return preguntas


def _estructura_libro(saneamiento: Any) -> list[dict[str, Any]]:
    """Hojas, títulos, unidades y fuentes del libro tal como los leyó la carga."""
    saneamiento = saneamiento if isinstance(saneamiento, dict) else {}
    hojas: dict[str, dict[str, Any]] = {}
    for e in ((saneamiento.get("contexto_semantico") or {}).get("elementos") or [])[:400]:
        hoja = hojas.setdefault(str(e.get("hoja") or ""), {"hoja": str(e.get("hoja") or ""), "titulos": [], "unidades": [], "fuentes": [], "notas": []})
        rol = str(e.get("rol") or "")
        destino = {"unidad": "unidades", "fuente": "fuentes"}.get(rol)
        if rol in {"titulo_subtitulo_nota", "titulo", "titulo_subtitulo", "poblacion_o_titulo"}:
            destino = "notas" if re.match(r"\s*nota\b", str(e.get("texto") or ""), re.I) else "titulos"
        if destino and len(hoja[destino]) < 4:
            hoja[destino].append(str(e.get("texto") or "")[:200])
    for b in ((saneamiento.get("excel") or {}).get("bloques") or [])[:40]:
        hoja = hojas.setdefault(str(b.get("hoja") or ""), {"hoja": str(b.get("hoja") or ""), "titulos": [], "unidades": [], "fuentes": [], "notas": []})
        hoja.setdefault("columnas", sorted({str(c) for c in (b.get("columnas") or {})})[:30])
    return [h for h in hojas.values() if h["hoja"] or any(h[k] for k in ("titulos", "unidades", "fuentes"))][:12]


def _contexto_informe(informe: models.Informe) -> dict[str, Any]:
    datos = list(informe.datos or [])
    columnas = sorted({col for fila in datos for col in fila.keys()})
    return {
        "periodo": getattr(informe, "periodo", None),
        "dominio": getattr(informe, "dominio", None),
        "columnas": columnas,
        "filas": len(datos),
        "estructura": _estructura_libro(getattr(informe, "saneamiento", None)),
        # Celdas y rótulos con forma de instrucción viajan citados como dato.
        "muestra": neutralizar_valor(datos[:5]),
    }


def _prompt_pista_a(contexto: dict[str, Any], preguntas_cubiertas: list[str]) -> str:
    listado = "\n".join(f"- {p}" for p in preguntas_cubiertas)
    return (
        f"Este es un informe agregado {_tipo_informe()} (sin datos individuales de "
        "personas). Un conjunto de siete lentes analiticas ya cubre estas preguntas "
        "-- no las repitas, ni ninguna variante cercana:\n"
        f"{listado}\n\n"
        "Contexto del informe (agregado, ya saneado; columnas, hojas con sus títulos, unidades y fuentes, y una muestra de filas):\n"
        + delimitar(json.dumps(contexto, ensure_ascii=False, default=str))
        + "\n" + CONSIGNA_DATOS + "\n\n"
        f"Proponé como maximo {MAX_PREGUNTAS_PISTA_A} preguntas que NINGUNA pregunta "
        "de esa lista anticipa -- lo que queda afuera de esa grilla. Cada pregunta tiene que "
        "nombrar literalmente al menos una columna, hoja, título, unidad, fuente o rótulo de "
        "fila del contexto y referirse a algo observable en estos datos. No formules preguntas "
        "genéricas sobre comunicación del informe, usos futuros, retroalimentación de usuarios "
        "o integración con otros sistemas. Una pregunta por "
        "linea, sin numerarlas, sin explicaciones adicionales, sin acusar ni atribuir "
        "responsabilidad a nadie, en tono de interrogante institucional a validar, "
        "nunca como conclusion."
    )


def _plano(texto: Any) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t.casefold()).split())


def _anclas_contexto(contexto: dict[str, Any]) -> set[str]:
    anclas: set[str] = set()
    for c in contexto.get("columnas") or []:
        anclas.add(_plano(c))
    for h in contexto.get("estructura") or []:
        anclas.add(_plano(h.get("hoja")))
        for k in ("titulos", "unidades", "fuentes", "columnas"):
            for t in h.get(k) or []:
                anclas.add(_plano(t))
                anclas.update(p for p in _plano(t).split() if len(p) >= 6)
    for fila in contexto.get("muestra") or []:
        for v in (fila or {}).values():
            if isinstance(v, str) and not es_instruccion(v):
                anclas.add(_plano(v))
    return {a for a in anclas if len(a) >= 3 and not re.fullmatch(r"\d+", a)}


def pregunta_especifica(pregunta: str, contexto: dict[str, Any]) -> bool:
    """Una pregunta de la pista A tiene que nombrar algo del contexto enviado."""
    texto = f" {_plano(pregunta)} "
    return any(f" {a} " in texto for a in _anclas_contexto(contexto))


def _llamar_modelo_pista_a(contexto: dict[str, Any]) -> dict[str, Any]:
    if not settings.openai_api_key:
        return {"modelo": settings.openai_model, "version": None, "texto": None, "error": "OPENAI_API_KEY no configurada"}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, timeout=40)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sos la capa exploratoria de un sistema de segunda lectura de "
                        f"informes {_tipo_informe()}. Solo formulas preguntas abiertas, "
                        "nunca conclusiones ni acusaciones."
                    ),
                },
                {"role": "user", "content": _prompt_pista_a(contexto, preguntas_canonicas_de_las_lentes())},
            ],
        )
        contenido = resp.choices[0].message.content
        if not contenido:
            raise ValueError("la respuesta no contiene texto")
        return {
            "modelo": settings.openai_model,
            "version": str(getattr(resp, "model", settings.openai_model)),
            "texto": contenido,
            "error": None,
        }
    except Exception as e:  # noqa: BLE001
        return {"modelo": settings.openai_model, "version": None, "texto": None, "error": str(e)}


def _partir_preguntas(texto: str) -> list[str]:
    lineas = [re.sub(r"^[\-\*\d\.\)\s]+", "", linea).strip() for linea in (texto or "").splitlines()]
    return [linea for linea in lineas if linea][:MAX_PREGUNTAS_PISTA_A]


def generar_pista_a_con_avisos(informe: models.Informe) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    """(hipotesis, error, avisos). Descarta preguntas genéricas (que no nombran
    nada del contexto enviado) y las que reproducen instrucciones incrustadas."""
    contexto = _contexto_informe(informe)
    resultado = _llamar_modelo_pista_a(contexto)
    if resultado["error"] or not resultado["texto"]:
        return [], resultado["error"], []
    hipotesis, genericas, inyectadas = [], [], []
    for pregunta in _partir_preguntas(resultado["texto"]):
        if es_instruccion(pregunta):
            inyectadas.append(pregunta)
            continue
        if not pregunta_especifica(pregunta, contexto):
            genericas.append(pregunta)
            continue
        hipotesis.append({
            "tipo_pista": TipoPista.PREGUNTAS_NO_FORMULADAS.value,
            "texto_hipotesis": guardrails.sanitizar_texto(pregunta),
            "modelo": resultado["modelo"],
            "version_modelo": resultado["version"],
        })
    avisos = []
    if genericas:
        avisos.append(f"pista A: {contar(len(genericas), 'pregunta descartada', 'preguntas descartadas')} por genéricas: no nombran ninguna columna, hoja, título, unidad ni rótulo del informe.")
    if inyectadas:
        avisos.append(f"pista A: {contar(len(inyectadas), 'pregunta descartada', 'preguntas descartadas')} por reproducir instrucciones incrustadas en los datos.")
    if not hipotesis:
        avisos.append("pista A: el modelo respondió, pero ninguna pregunta quedó anclada en el contenido del informe; no se guardaron preguntas.")
    return hipotesis, None, avisos


def generar_pista_a(informe: models.Informe) -> tuple[list[dict[str, Any]], str | None]:
    """Devuelve (hipotesis, error). Cada hipotesis es un dict listo para
    persistir con `guardar_hipotesis`. `error` es no-None cuando el modelo no
    pudo responder -- la funcion nunca lanza."""
    hipotesis, error, _ = generar_pista_a_con_avisos(informe)
    return hipotesis, error


# --- Pista B: correlaciones entre dimensiones que nadie declaro relacionadas -


def _numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


_RE_TOTAL = re.compile(r"^\s*(?:total|totales|subtotal|suma|total general)\b", re.IGNORECASE)
_RE_IDENTIFICADOR = re.compile(r"(?:^|[_\s])(?:c[oó]digo|codigo|cod|id|nro|n[uú]mero|numero)(?:$|[_\s])", re.IGNORECASE)
_RE_PERIODO = re.compile(r"^\s*(?:19|20)\d{2}(?:[-/]\d{1,2})?\s*$")


def _es_fila_total(fila: dict[str, Any]) -> bool:
    return any(isinstance(v, str) and _RE_TOTAL.match(v) for v in fila.values())


def _relaciones_derivadas(columnas: dict[str, list[float]]) -> set[frozenset[str]]:
    """Pares unidos por una identidad aritmética (c = a + b o c = a - b) que se
    cumple en casi todas las filas: correlacionan por construcción."""
    nombres = sorted(columnas)
    pares: set[frozenset[str]] = set()
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            for c in nombres:
                if c in (a, b):
                    continue
                xa, xb, xc = columnas[a], columnas[b], columnas[c]
                for combinado in ([x + y for x, y in zip(xa, xb)], [x - y for x, y in zip(xa, xb)], [y - x for x, y in zip(xa, xb)]):
                    cumple = sum(1 for z, w in zip(combinado, xc) if abs(z - w) <= max(1e-9, 0.01 * max(abs(w), abs(z))))
                    if xc and cumple >= max(3, 0.8 * len(xc)):
                        pares.update({frozenset((a, b)), frozenset((a, c)), frozenset((b, c))})
    return pares


def _columnas_numericas(datos: list[dict[str, Any]]) -> dict[str, list[float]]:
    columnas: dict[str, list[float]] = {}
    for fila in datos:
        for col, valor in fila.items():
            numero = _numero(valor)
            if numero is None:
                continue
            columnas.setdefault(col, []).append(numero)
    minimo = max(4, len(datos) // 2)
    return {col: valores for col, valores in columnas.items() if len(valores) >= minimo and len(valores) == len(datos)}


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 4 or n != len(ys):
        return None
    media_x = sum(xs) / n
    media_y = sum(ys) / n
    cov = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    var_x = sum((x - media_x) ** 2 for x in xs)
    var_y = sum((y - media_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / (var_x ** 0.5 * var_y ** 0.5)


def analizar_correlaciones(informe: models.Informe) -> dict[str, Any]:
    """Cálculo determinista con sus exclusiones explícitas.

    Excluye filas de total, columnas de código, pares de columnas que son
    períodos de una misma serie en formato ancho (correlacionan por el tamaño
    de cada rubro), pares unidos por una identidad aritmética y coeficientes
    que redondeados a tres decimales llegan a 0.999 (relación casi exacta).
    """
    datos = [f for f in list(informe.datos or []) if isinstance(f, dict)]
    filas_total = sum(1 for f in datos if _es_fila_total(f))
    datos = [f for f in datos if not _es_fila_total(f)]
    columnas = {
        c: v for c, v in _columnas_numericas(datos).items()
        if not _RE_IDENTIFICADOR.search(str(c))
    }
    derivadas = _relaciones_derivadas(columnas)
    nombres = sorted(columnas)
    pares: list[dict[str, Any]] = []
    excluidos = {"periodos_de_una_serie": 0, "relacion_aritmetica": 0, "casi_exacta": 0}
    for col_a, col_b in ((a, b) for i, a in enumerate(nombres) for b in nombres[i + 1:]):
        if _RE_PERIODO.match(str(col_a)) and _RE_PERIODO.match(str(col_b)):
            excluidos["periodos_de_una_serie"] += 1
            continue
        if frozenset((col_a, col_b)) in derivadas:
            excluidos["relacion_aritmetica"] += 1
            continue
        r = _pearson(columnas[col_a], columnas[col_b])
        if r is None:
            continue
        r3 = round(r, 3)
        if abs(r3) >= 0.999:
            excluidos["casi_exacta"] += 1
            continue
        if UMBRAL_CORRELACION <= abs(r3):
            pares.append({"columna_a": col_a, "columna_b": col_b, "r": r3, "n": len(columnas[col_a])})
    pares.sort(key=lambda p: abs(p["r"]), reverse=True)
    return {
        "pares": pares[:MAX_CORRELACIONES_PISTA_B],
        "columnas_comparables": len(nombres),
        "filas_total_excluidas": filas_total,
        "excluidos": excluidos,
    }


def calcular_correlaciones(informe: models.Informe) -> list[dict[str, Any]]:
    """Determinista: mismas entradas, mismo resultado. No usa ningun modelo."""
    return analizar_correlaciones(informe)["pares"]


def _redactar_correlacion_con_modelo(par: dict[str, Any]) -> dict[str, Any]:
    if not settings.openai_api_key:
        return {"modelo": settings.openai_model, "version": None, "texto": None, "error": "OPENAI_API_KEY no configurada"}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, timeout=40)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Redactas en una sola oracion, en español rioplatense (voseo), la comunicacion "
                        "de una coincidencia estadistica entre dos variables de un informe "
                        f"{_tipo_informe()}. Nunca uses lenguaje causal ('porque', 'debido a', "
                        "'explica', 'produce'). Siempre deja explicito que una correlacion no "
                        "implica causalidad. Nombrá las dos variables con sus nombres exactos, entre "
                        "comillas simples; nunca las llames 'variable A' o 'variable B'. Reproducí el "
                        "coeficiente y la cantidad de observaciones tal como se dan. No digas que es "
                        "'significativa' ni 'estadísticamente' nada: no se hizo ninguna prueba de "
                        "significación y con pocas observaciones la coincidencia puede ser azar. "
                        + CONSIGNA_DATOS
                    ),
                },
                {
                    "role": "user",
                    "content": delimitar(json.dumps(neutralizar_valor({
                        "variable_1": par["columna_a"], "variable_2": par["columna_b"],
                        "coeficiente_r": par["r"], "observaciones": par["n"],
                    }), ensure_ascii=False)),
                },
            ],
        )
        contenido = resp.choices[0].message.content
        if not contenido:
            raise ValueError("la respuesta no contiene texto")
        return {
            "modelo": settings.openai_model,
            "version": str(getattr(resp, "model", settings.openai_model)),
            "texto": contenido,
            "error": None,
        }
    except Exception as e:  # noqa: BLE001
        return {"modelo": settings.openai_model, "version": None, "texto": None, "error": str(e)}


MUESTRA_CHICA = 30


def _redaccion_por_defecto(par: dict[str, Any]) -> str:
    muestra = "; muestra chica, sin prueba de significación" if par["n"] < MUESTRA_CHICA else "; sin prueba de significación"
    return (
        f"'{par['columna_a']}' y '{par['columna_b']}' se mueven juntas en este informe "
        f"(coeficiente {par['r']}, sobre {par['n']} observaciones{muestra}); {DISCLAIMER_CORRELACION}"
    )


def problemas_redaccion(texto: str, par: dict[str, Any]) -> list[str]:
    """Lo que invalida una redacción del modelo frente al cálculo."""
    plano = _plano(texto)
    problemas = []
    for clave in ("columna_a", "columna_b"):
        if f" {_plano(par[clave])} " not in f" {plano} ":
            problemas.append(f"no nombra la variable «{par[clave]}»")
    if re.search(r"\bvariable\s+[ab12]\b", plano):
        problemas.append("reemplaza los nombres por 'variable A/B'")
    if re.search(r"significativ|significaci[oó]n estad|estad[ií]sticamente", texto, re.IGNORECASE) and not re.search(r"sin prueba de significaci", texto, re.IGNORECASE):
        problemas.append("afirma significación estadística sin prueba")
    r = f"{abs(par['r']):.3f}".rstrip("0").rstrip(".")
    if r not in texto.replace(",", "."):
        problemas.append("no reproduce el coeficiente calculado")
    return problemas


def generar_pista_b_con_avisos(informe: models.Informe) -> tuple[list[dict[str, Any]], list[str]]:
    """Calculo determinista + redaccion validada; los silencios se explican."""
    analisis = analizar_correlaciones(informe)
    hipotesis: list[dict[str, Any]] = []
    avisos: list[str] = []
    if not analisis["pares"]:
        exc = analisis["excluidos"]
        avisos.append(
            f"pista B: sin correlaciones con |r| ≥ {UMBRAL_CORRELACION} entre {analisis['columnas_comparables']} columnas numéricas comparables "
            f"(excluidos: {contar(analisis['filas_total_excluidas'], 'fila de total', 'filas de total')}, {contar(exc['periodos_de_una_serie'], 'par de períodos de una misma serie', 'pares de períodos de una misma serie')}, "
            f"{contar(exc['relacion_aritmetica'], 'par unido por una identidad aritmética', 'pares unidos por una identidad aritmética')}, {contar(exc['casi_exacta'], 'par casi exacto', 'pares casi exactos')}). No se generaron hipótesis."
        )
    for par in analisis["pares"]:
        redaccion = _redactar_correlacion_con_modelo(par)
        motivo = None
        if redaccion["error"] or not redaccion["texto"]:
            motivo = "el modelo no respondió"
        else:
            problemas = problemas_redaccion(redaccion["texto"], par)
            if problemas:
                motivo = "la redacción del modelo " + "; ".join(problemas)
        if motivo:
            texto, modelo, version = _redaccion_por_defecto(par), "plantilla_determinista", None
            avisos.append(f"pista B: «{par['columna_a']}» / «{par['columna_b']}» redactada con plantilla porque {motivo}.")
        else:
            texto, modelo, version = redaccion["texto"], redaccion["modelo"], redaccion["version"]
            if par["n"] < MUESTRA_CHICA and "muestra chica" not in texto.lower():
                texto = f"{texto.rstrip()} (Muestra chica: {par['n']} observaciones, sin prueba de significación.)"
        texto_saneado = guardrails.sanitizar_texto(texto)
        if "no implica" not in texto_saneado.lower():
            texto_saneado = f"{texto_saneado} ({DISCLAIMER_CORRELACION.capitalize()})"
        hipotesis.append({
            "tipo_pista": TipoPista.CORRELACIONES_NO_DECLARADAS.value,
            "texto_hipotesis": texto_saneado,
            "modelo": modelo,
            "version_modelo": version,
        })
    return hipotesis, avisos


def generar_pista_b(informe: models.Informe) -> list[dict[str, Any]]:
    """Calculo determinista + redaccion (con modelo si esta disponible, con
    una plantilla fija si no). Nunca lanza: sin API key igual devuelve
    hipotesis, con texto de plantilla."""
    return generar_pista_b_con_avisos(informe)[0]


# --- Persistencia -------------------------------------------------------


def guardar_hipotesis(db: Any, informe_id: int, hipotesis: list[dict[str, Any]]) -> list[models.HipotesisExploratoria]:
    filas = [
        models.HipotesisExploratoria(
            informe_id=informe_id,
            tipo_pista=item["tipo_pista"],
            texto_hipotesis=item["texto_hipotesis"],
            modelo=item["modelo"],
            version_modelo=item.get("version_modelo"),
            estado=ESTADO_HIPOTESIS_NO_VALIDADA,
        )
        for item in hipotesis
    ]
    db.add_all(filas)
    db.commit()
    for fila in filas:
        db.refresh(fila)
    return filas


def listar_hipotesis(db: Any, informe_id: int) -> list[models.HipotesisExploratoria]:
    return (
        db.query(models.HipotesisExploratoria)
        .filter(models.HipotesisExploratoria.informe_id == informe_id)
        .order_by(models.HipotesisExploratoria.creado_en.desc())
        .all()
    )


def agrupar_corridas(hipotesis: list[Any]) -> list[dict[str, Any]]:
    """Agrupa hipótesis guardadas por corrida (más reciente primero).

    Una corrida guarda todas sus hipótesis en una misma operación; una pausa
    mayor a SEPARACION_CORRIDAS_SEGUNDOS separa corridas distintas."""
    ordenadas = sorted(hipotesis, key=lambda h: (getattr(h, "creado_en", None) is None, getattr(h, "creado_en", None) or 0, getattr(h, "id", 0) or 0))
    corridas: list[list[Any]] = []
    anterior = None
    for h in ordenadas:
        momento = getattr(h, "creado_en", None)
        if not corridas or anterior is None or momento is None or (momento - anterior).total_seconds() > SEPARACION_CORRIDAS_SEGUNDOS:
            corridas.append([])
        corridas[-1].append(h)
        anterior = momento
    salida = [
        {"corrida": i + 1, "creado_en": grupo[0].creado_en if getattr(grupo[0], "creado_en", None) else None,
         "cantidad": len(grupo), "hipotesis": grupo}
        for i, grupo in enumerate(corridas)
    ]
    return list(reversed(salida))


def generar_para_informe_detallado(db: Any, informe: models.Informe) -> dict[str, Any]:
    """Corre las dos pistas y persiste lo producido; errores y avisos aparte."""
    errores: list[str] = []
    avisos: list[str] = []
    candidatas: list[dict[str, Any]] = []
    testigo = ambito_svc.declarar(ambito_svc.de_informe(informe))
    try:
        pista_a, error_a, avisos_a = generar_pista_a_con_avisos(informe)
        pista_b, avisos_b = generar_pista_b_con_avisos(informe)
    finally:
        ambito_svc.restaurar(testigo)
    candidatas.extend(pista_a)
    if error_a:
        errores.append(f"pista A (preguntas no formuladas): {error_a}")
    avisos.extend(avisos_a)
    candidatas.extend(pista_b)
    avisos.extend(avisos_b)
    guardadas = guardar_hipotesis(db, informe.id, candidatas)
    return {"guardadas": guardadas, "errores": errores, "avisos": avisos}


def generar_para_informe(db: Any, informe: models.Informe) -> tuple[list[models.HipotesisExploratoria], list[str]]:
    """Corre las dos pistas y persiste lo que produjeron. Devuelve las filas
    guardadas y la lista de errores no fatales (p.ej. modelo sin responder)."""
    resultado = generar_para_informe_detallado(db, informe)
    return resultado["guardadas"], resultado["errores"]
