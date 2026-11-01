"""Condiciones verificables de una ejecución y registro conservador de faltantes."""
from __future__ import annotations

import math

from services.proveniencia import huella

DIMENSIONES = ("periodo", "unidad", "moneda", "universo", "cobertura", "escala", "entidad", "version", "comparabilidad")


def esquema(datos):
    columnas = {}
    for fila in datos:
        for nombre, valor in fila.items():
            tipo = "nulo" if valor is None else "booleano" if isinstance(valor, bool) else "numero" if isinstance(valor, (int, float)) else "texto" if isinstance(valor, str) else "estructura"
            columnas.setdefault(nombre, set()).add(tipo)
    estructura = {c: sorted(t - {"nulo"}) or ["nulo"] for c, t in sorted(columnas.items())}
    return {"columnas": estructura, "sha256": huella(estructura)}


def comparar_esquema(actual, esperado):
    fallas = []
    for col, tipos in esperado.get("columnas", {}).items():
        if col not in actual["columnas"]:
            fallas.append(f"falta columna {col}")
        elif set(actual["columnas"][col]) - set(tipos):
            fallas.append(f"cambió tipo de {col}")
    return fallas


def evaluar(informe, esquema_anterior=None):
    datos = informe.datos or []
    meta = getattr(informe, "saneamiento", None) or {}
    contrato = meta.get("contexto_validacion") or {}
    verificadas, no_verificadas, fallidas = [], [], []
    actual = esquema(datos)
    def registrar(nombre, valores, critica=False):
        incompleta = any(v is None or not str(v).strip() for v in valores)
        valores = sorted({str(v) for v in valores if v is not None and str(v).strip()})
        item = {"condicion": nombre, "critica": critica, "valores": valores}
        if not valores:
            no_verificadas.append({**item, "motivo": "No hay evidencia en los datos cargados"})
        elif len(valores) > 1 and nombre in {"unidad", "moneda", "escala", "universo", "entidad", "version", "comparabilidad"}:
            fallidas.append({**item, "motivo": "Valores incompatibles para una comparación conjunta"})
        elif incompleta:
            no_verificadas.append({**item, "motivo": "La condición falta en parte de los registros"})
        else:
            verificadas.append({**item, "alcance": "Presencia y consistencia declarada; no verifica veracidad externa"})
    criticas = set(contrato.get("condiciones_criticas") or [])
    for dimension in DIMENSIONES:
        valores = [r.get(dimension) for r in datos]
        # El período de carga por defecto no prueba el período al que corresponden los datos.
        registrar(dimension, valores, dimension in criticas)
    requeridos = contrato.get("campos_requeridos") or []
    for col in requeridos:
        item = {"condicion": f"campo:{col}", "critica": True}
        if not datos or any(r.get(col) is None or r.get(col) == "" for r in datos):
            no_verificadas.append({**item, "motivo": "Campo requerido ausente o incompleto"})
        else:
            verificadas.append(item)
    if not datos:
        fallidas.append({"condicion": "datos", "critica": True, "motivo": "Sin registros"})
    if any(isinstance(v, float) and not math.isfinite(v) for r in datos for v in r.values()):
        fallidas.append({"condicion": "numeros_finitos", "critica": True, "motivo": "Contiene NaN o infinitos"})
    esperado = contrato.get("esquema_esperado") or esquema_anterior
    cambios = comparar_esquema(actual, esperado) if esperado else []
    if cambios:
        fallidas.append({"condicion": "esquema", "critica": True, "motivo": "Cambio de esquema detectado", "detalle": cambios})
    if not esperado:
        no_verificadas.append({"condicion": "esquema_esperado", "critica": False, "motivo": "Sin contrato previo; huella actual registrada"})
    bloqueo = any(c["critica"] for c in fallidas + no_verificadas)
    for item in fallidas + no_verificadas:
        item["categoria_incidencia"] = "cambio_entorno_datos" if item["condicion"] == "esquema" else "condiciones_no_satisfechas"
    return {"estado": "no_evaluable" if bloqueo else "verificacion_parcial" if no_verificadas or fallidas else "conforme",
            "puede_concluir": not bloqueo, "condiciones_verificadas": verificadas,
            "condiciones_no_verificadas": no_verificadas, "condiciones_fallidas": fallidas,
            "esquema": actual, "cambio_esquema": bool(cambios)}


def naturaleza(hallazgo):
    if hallazgo.get('modo') in {'control_tabular', 'contexto_agrupado'}:
        return 'contexto' if (hallazgo.get('evidencia') or {}).get('naturaleza') == 'contexto' else 'control'
    if hallazgo.get("lente") == "rizoma" or hallazgo.get("modo") in {"exploratorio", "primer_digito_no_conforme"} or hallazgo.get("tipo_evidencia") == "ASOCIACION_EXPLORATORIA":
        return "exploratoria"
    ev = hallazgo.get("evidencia") or {}
    # Cronista declara contexto (estacionalidad, nota del archivo, cambio de nivel sostenido).
    if hallazgo.get("lente") == "cronista" and ev.get("naturaleza") == "contexto":
        return "contexto"
    if hallazgo.get("lente") == "ajedrecista" and hallazgo.get("modo") == "imposibilidad" and ev.get("regla"):
        return "deterministica"
    if hallazgo.get("modo") in {"total_no_coincide_componentes", "control_explicito"}:
        return "deterministica"
    if ev.get("naturaleza") == "deterministica":
        return "deterministica"
    return "interpretativa_con_calculo"


def antecedentes_comparables(informe, candidatos):
    """Exige evidencia de comparabilidad antes de usar un banco de preinformes."""
    aceptados, excluidos = [], []
    actual = esquema(informe.datos or [])
    for previo in candidatos:
        motivos = []
        if previo.area_id != informe.area_id:
            motivos.append("entidad distinta")
        if comparar_esquema(actual, esquema(previo.datos or [])):
            motivos.append("esquema incompatible")
        for dim in ("unidad", "moneda", "universo", "escala"):
            a = {str(r[dim]) for r in informe.datos or [] if r.get(dim) is not None}
            b = {str(r[dim]) for r in previo.datos or [] if r.get(dim) is not None}
            if not a or not b or a != b or len(a) != 1:
                motivos.append(f"{dim} no comparable o no verificada")
        if motivos:
            excluidos.append({"informe_id": previo.id, "motivos": motivos})
        else:
            aceptados.append(previo)
    return aceptados, excluidos


def aplicabilidad_lentes(informe, antecedentes):
    from services import perfilado
    from services.lentes.util import columnas_numericas
    from services.resultado_revision import separar_datos
    datos, excluidos = separar_datos(informe.datos or [])
    nums = columnas_numericas(datos)
    perfiles = perfilado.perfilar(datos)
    temporales = perfilado.columnas_temporales(perfiles)
    # Formatos anchos o año/mes son reconocidos por Cronista; no se descartarán por carecer de una columna 'periodo'.
    from services.lentes import cronista, rizoma
    from services.lentes.util import CORRELACION_MIN_N
    ancho = cronista._series_formato_ancho(datos)
    temporal = bool(temporales or ancho or cronista._series_formato_anio_mes(datos))
    columnas = {str(c) for r in datos for c in r}
    temporal = temporal or any(perfilado.fecha(c) for c in columnas)
    estados = {lente: {"estado": "evaluado", "motivo": "Condiciones básicas presentes; revisar límites por control"}
               for lente in ("ajedrecista", "cronista", "orquesta", "radiologo", "rizoma", "matematico", "conciliador")}
    from services.interpretacion_previa import de_unidad
    from services.lentes.matematico import motivo_abstencion
    interpretada = de_unidad(informe)
    abstencion = motivo_abstencion(datos, interpretada.get("confirmada", {}).get("roles", {}) if interpretada else None)
    if abstencion:
        estados["matematico"]["motivo"] = abstencion + " Los controles de fórmulas y aritmética se mantienen."
    def pendiente(lente, motivo, estado="no_evaluable"):
        estados[lente] = {"estado": estado, "motivo": motivo}
    if not nums:
        for lente in ("cronista", "orquesta", "rizoma"):
            pendiente(lente, "Sin columnas cuantitativas utilizables")
    if not temporal or (len(datos) < 3 and not ancho):
        pendiente("cronista", "Faltan períodos comparables o suficientes observaciones")
    else:
        problemas = cronista.problemas_periodo(datos)
        if problemas:
            p = problemas[0]
            pendiente("cronista", (
                f"Período duplicado o fuera de secuencia en la columna '{p['columna']}' (registro {p['fila'] + 1}: "
                f"'{p['valor']}'"
                + (f" y {len(problemas) - 1} más" if len(problemas) > 1 else "")
                + "). El análisis temporal no es evaluable hasta corregir el eje de períodos."))
            estados["cronista"]["problemas_periodo"] = problemas[:20]
    if len(nums) < 2 or len(datos) < CORRELACION_MIN_N:
        pendiente("rizoma", f"Se requieren dos columnas numéricas y al menos {CORRELACION_MIN_N} observaciones completas por par")
    elif not rizoma.evaluar_relaciones(datos):
        pendiente("rizoma", f"Sin pares no obvios con al menos {CORRELACION_MIN_N} observaciones completas y variación en ambas columnas")
    if ancho:
        pendiente('rizoma', 'Cuadro ancho de años: las filas son rubros heterogéneos, no observaciones comparables para correlación entre columnas anuales', 'no_aplicable')
    if informe.dominio != "presupuestario":
        pendiente("radiologo", "Fuera del dominio presupuestario calibrado", "no_aplicable")
    elif not antecedentes:
        pendiente("radiologo", "No hay preinformes con comparabilidad verificada")
    if excluidos:
        for nombre, estado in estados.items():
            estado["cuadros_excluidos"] = excluidos
            estado["cobertura_parcial"] = True
            if not datos:
                estados[nombre] = {**estado, "estado": "no_evaluable", "motivo": "Sin tablas con encabezados y columnas confiables para este control"}
    return estados


def condiciones_interdocumentales(datos):
    archivos = {r.get("archivo_origen") for r in datos if r.get("archivo_origen")}
    if len(archivos) < 2:
        return {"estado": "no_aplicable", "motivo": "No hay dos archivos que conciliar"}
    pendientes = []
    for dim in ("periodo", "entidad", "moneda", "unidad", "escala"):
        por_archivo = [{str(r[dim]) for r in datos if r.get("archivo_origen") == a and r.get(dim) is not None} for a in archivos]
        if any(r.get(dim) is None or not str(r[dim]).strip() for r in datos if r.get("archivo_origen") in archivos) or any(not valores for valores in por_archivo) or any(v != por_archivo[0] for v in por_archivo[1:]) or (dim != "periodo" and any(len(v) != 1 for v in por_archivo)):
            pendientes.append(dim)
    return {"estado": "no_evaluable" if pendientes else "evaluado",
            "condiciones_no_verificadas": pendientes,
            "motivo": "Requiere compatibilidad documental de período, entidad, moneda, unidad y escala" if pendientes else "Contexto documental coincidente"}
