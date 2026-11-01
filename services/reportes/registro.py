"""Registro único de lo leído y lo controlado.

De este registro salen el estado de la revisión, sus límites y la primera línea del informe y de
la pantalla. Se arma con lo que ya existe en el informe (saneamiento, cobertura, hallazgos) y es
tolerante a campos nuevos: lo que otras etapas agreguen se consume si está y se ignora si no.

Estructura (versión 1), para quien quiera alimentarlo:

    registro = {
      "version": 1,
      "estado": "completo" | "parcial" | "insuficiente",
      "primera_linea": str,               # lo no leído o no controlado, o que no quedó nada afuera
      "pendientes": [ {tipo: "no_leido" | "no_controlado", archivo, donde, motivo} ],
      "archivos": [ {archivo, tipo, filas_incorporadas, filas_sin_archivo_origen,
                     hojas_leidas: [str], hojas_no_leidas: [{hoja, motivo}],
                     paginas: {leidas, total, motivo} | None,
                     series: {leidas, aparentes, motivos} | None,
                     celdas_no_interpretables, formulas_sin_valor, ocultas,   # si otra etapa los informa
                     controles: [{control, nombre, estado, motivo, senales}],
                     extras: {...} } ],
      "controles": [ {control, nombre, estado: ejecutado | no_ejecutado | no_aplicable, motivo, senales, alcance} ],
      "cruces": {estado, detalle: [str], comparados, no_comparables, filas_emparejadas, filas_totales},
      "periodo": {declarado: bool | None, valor, observado, texto},
      "fuentes": [claves consumidas],
    }

Entradas que se consumen si existen (todas opcionales):
- saneamiento["registro_lectura"]: lista de {archivo, hoja?, pagina?, elemento?, estado: "leido" |
  "no_leido" | "no_controlado", motivo}. Canal genérico recomendado para etapas nuevas.
- por hoja en saneamiento["excel"]["hojas"]: estado/motivo, filas_no_interpretadas, oculta|hoja_oculta,
  celdas_no_interpretables, formulas_sin_valor (número o lista), revisada (bool).
- saneamiento["filas_sin_archivo_origen"] o, si falta, el conteo sobre los datos.
- saneamiento["periodo_declarado"] (bool) para no presentar como declarado un período por defecto.
- cobertura["lentes"], cobertura["excel"]["bloques"][i]["controles"], cobertura["control_interdocumental"].
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

from services.plural import contar, muestra

NOMBRE_CONTROL = {
    "conciliador": "Contexto técnico",
    "ajedrecista": "Coherencia interna",
    "cronista": "Evolución temporal",
    "orquesta": "Coherencia documental",
    "radiologo": "Antecedentes comparables",
    "rizoma": "Conexiones exploratorias",
    "matematico": "Cálculos y métodos",
}
CLAVES_HOJA_CONOCIDAS = {
    "hoja", "estado", "motivo", "archivo", "bloques", "filas_datos", "advertencias", "filas_estructura",
    "filas_preparadas", "filas_no_interpretadas", "oculta", "hoja_oculta", "celdas_no_interpretables",
    "formulas_sin_valor", "revisada", "visibilidad", "no_revisada", "avisos_lectura", "numeros_como_texto",
    "celdas_sin_dato", "celdas_no_numericas", "columnas_no_controladas", "cuadros_apilados",
    "encabezados_no_separados", "formulas_calculadas", "fuera_de_cuadros",
}


def _campo(obj, nombre, defecto=None):
    if isinstance(obj, dict):
        return obj.get(nombre, defecto)
    return getattr(obj, nombre, defecto)


def _cantidad(v):
    if v is None:
        return None
    if isinstance(v, dict):
        # {celdas: n | [..], ejemplos, mensaje} o {columna, celdas, ejemplos}
        return _cantidad(v.get("celdas")) if "celdas" in v else len(v)
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, (list, tuple, set, dict)):
        return len(v)
    return None


def _tipo(nombre):
    ext = os.path.splitext(str(nombre or ""))[1].lower()
    return {".xlsx": "excel", ".xlsm": "excel", ".xls": "excel", ".csv": "csv", ".tsv": "csv", ".pdf": "pdf"}.get(ext, "otro")


def _pdf_ajustado(meta):
    """Lectura del PDF, sin declarar insuficiente una tabla chica que se leyó completa."""
    from services.controles_excel.lectura import resumen_pdf

    r = resumen_pdf(meta or {})
    if (
        r
        and r.get("estado") == "insuficiente"
        and r.get("con_tablas")
        and not r.get("truncado")
        and (not r.get("paginas_documento") or r.get("paginas_analizadas") == r.get("paginas_documento"))
        and not r.get("cuadros_sin_separar")
        and not r.get("cuadros_sin_rotulos")
        and not r.get("paginas_sin_texto")
        and r.get("filas_utiles")
        and r.get("filas_utiles") == r.get("filas")
    ):
        r = {**r, "estado": "completa", "tabla_chica_completa": True}
    return r


def periodo(informe):
    """Período de referencia: declarado o no. Un valor por defecto no se presenta como declarado."""
    from services.reportes.markdown import _periodo_observado

    saneamiento = _campo(informe, "saneamiento") or {}
    valor = _campo(informe, "periodo")
    observado = _periodo_observado(_campo(informe, "datos") or [])
    declarado = saneamiento.get("periodo_declarado") if isinstance(saneamiento, dict) else None
    if declarado is None and valor:
        creado = _campo(informe, "creado_en")
        carga = creado.strftime("%Y-%m") if hasattr(creado, "strftime") else None
        # La carga rápida completa el período con el mes de carga cuando la persona no lo declara.
        if carga and str(valor) == carga:
            declarado = False
    if declarado is False:
        texto = (f"Período de referencia: no declarado (la carga se registró en {valor}; no se usa para comparar). "
                 f"Período observado en los datos: {observado}.")
    elif valor:
        texto = f"Período de referencia declarado: {valor}. Período observado en los datos: {observado}."
    else:
        texto = f"Período de referencia: no declarado. Período observado en los datos: {observado}."
    return dict(declarado=declarado, valor=valor, observado=observado, texto=texto)


def _notas_cruce(hallazgos):
    from services.casos_revision import es_nota

    out = []
    for h in hallazgos or []:
        if es_nota(h) and not (_campo(h, "evidencia") or {}).get("sondeo"):
            out.append(h)
    return out


def _cruces(hallazgos, archivos, interdoc):
    notas = _notas_cruce(hallazgos)
    comparados = [n for n in notas if (_campo(n, "evidencia") or {}).get("regla") == "cobertura_cruce_ediciones"]
    no_comparables = [n for n in notas if (_campo(n, "evidencia") or {}).get("regla") == "cruce_no_comparable"]
    emparejadas = sum(int((_campo(n, "evidencia") or {}).get("filas_emparejadas") or 0) for n in comparados)
    totales = sum(int((_campo(n, "evidencia") or {}).get("filas_totales") or 0) for n in comparados)
    detalle = [str(_campo(n, "descripcion") or "") for n in notas]
    estado_interdoc = (interdoc or {}).get("estado")
    motivo_interdoc = (interdoc or {}).get("motivo")
    if comparados and any((_campo(n, "evidencia") or {}).get("filas_emparejadas") for n in comparados):
        estado = "evaluado"
        texto = (f"Cruce entre archivos: {contar(len(comparados), 'cuadro comparado', 'cuadros comparados')}; "
                 f"{emparejadas} de {totales} filas emparejadas"
                 + (f"; {contar(len(no_comparables), 'cuadro no comparable', 'cuadros no comparables')}" if no_comparables else "") + ".")
    elif no_comparables:
        estado = "no_comparable"
        dims = sorted({d for n in no_comparables for d in (_campo(n, "evidencia") or {}).get("dimensiones_no_comparables") or []})
        texto = f"Cruce entre archivos no realizado: los cuadros no son comparables por {', '.join(dims)}."
    elif comparados:
        estado = "sin_emparejar"
        texto = f"Cruce entre archivos sin filas emparejadas: 0 de {totales} filas."
    elif len(archivos) < 2:
        estado = "no_aplicable"
        texto = "Un solo archivo: no hay cruce entre archivos."
    elif estado_interdoc == "evaluado":
        estado = "evaluado"
        texto = "Cruce entre archivos: " + (motivo_interdoc or "evaluado") + "."
    elif estado_interdoc == "no_aplicable" and "dos archivos" in str(motivo_interdoc or ""):
        estado = "no_evaluado"
        texto = (f"Cruce entre archivos no evaluado: se cargaron {len(archivos)} archivos pero las filas no conservan "
                 "su archivo de origen, por lo que no se pudo atribuir cada dato a su documento.")
    else:
        estado = "no_evaluado"
        pendientes = (interdoc or {}).get("condiciones_no_verificadas") or []
        texto = "Cruce entre archivos no evaluado" + (
            f": falta verificar {', '.join(map(str, pendientes))}." if pendientes else (f": {motivo_interdoc}." if motivo_interdoc else ".")
        )
    return dict(estado=estado, texto=texto, detalle=detalle, comparados=len(comparados),
                no_comparables=len(no_comparables), filas_emparejadas=emparejadas, filas_totales=totales)


def motivo_validez(cobertura):
    """Por qué no se ejecutaron los controles cuando fallaron las condiciones de validez; None si no fallaron."""
    validez = (cobertura or {}).get("condiciones_validez") or {}
    fallidas = [str(x.get("motivo")).strip().rstrip(".") for x in validez.get("condiciones_fallidas") or []
                if isinstance(x, dict) and x.get("motivo")]
    if not fallidas:
        return None
    texto = "condiciones de validez no cumplidas: " + "; ".join(dict.fromkeys(fallidas)).lower()
    if validez.get("cambio_esquema"):
        texto += " respecto del informe anterior"
    return texto


def _controles(cobertura, hallazgos):
    from services.casos_revision import es_nota

    conteo = defaultdict(int)
    for h in hallazgos or []:
        if not es_nota(h):
            conteo[_campo(h, "lente")] += 1
    out = []
    for c in (cobertura or {}).get("lentes") or []:
        estado = c.get("estado")
        if estado == "no_aplicable":
            e = "no_aplicable"
        elif estado == "no_evaluable" or c.get("ejecutado") is False:
            e = "no_ejecutado"
        else:
            e = "ejecutado"
        alcance = None
        if c.get("bloques_totales"):
            alcance = f"{c.get('bloques_evaluados', 0)} de {c['bloques_totales']} cuadros"
        senales = conteo.get(c.get("lente"), 0) if hallazgos is not None else c.get("hallazgos", 0)
        motivo = c.get("motivo") or (motivo_validez(cobertura) if e == "no_ejecutado" else None)
        out.append(dict(control=c.get("lente"), nombre=NOMBRE_CONTROL.get(c.get("lente"), c.get("lente")), estado=e,
                        motivo=motivo, senales=senales, alcance=alcance))
    return out


def _controles_por_archivo(archivo, bloques, globales, tipo):
    if tipo != "excel" or not bloques:
        return [dict(control=c["control"], nombre=c["nombre"], estado=c["estado"], motivo=c["motivo"]) for c in globales]
    por_control = defaultdict(list)
    for b in bloques:
        for lente, estado in (b.get("controles") or {}).items():
            por_control[lente].append(estado or {})
    out = []
    for c in globales:
        items = por_control.get(c["control"])
        if not items:
            out.append(dict(control=c["control"], nombre=c["nombre"], estado=c["estado"], motivo=c["motivo"]))
            continue
        evaluados = sum(x.get("estado") == "evaluado" for x in items)
        sin_evaluar = [x for x in items if x.get("estado") == "no_evaluable"]
        faltan = None
        if evaluados:
            estado, motivo = "ejecutado", f"en {evaluados} de {len(items)} cuadros"
            if sin_evaluar:
                # Un control que corrió en parte de los cuadros no cubre los demás: se declara.
                faltan = dict(cuadros=len(sin_evaluar), total=len(items),
                              motivo=sin_evaluar[0].get("motivo") or "condiciones del cuadro no verificadas")
        elif all(x.get("estado") == "no_aplicable" for x in items):
            estado, motivo = "no_aplicable", items[0].get("motivo")
        else:
            estado, motivo = "no_ejecutado", items[0].get("motivo")
        # Los controles tabulares del libro se ejecutan por cuadro aunque la lente no aplique.
        if c["estado"] == "ejecutado" and estado != "ejecutado" and "tabulares" in str(c.get("motivo") or ""):
            estado, motivo = "ejecutado", c.get("motivo")
        if "tabulares" in str(c.get("motivo") or ""):
            faltan = None
        out.append(dict(control=c["control"], nombre=c["nombre"], estado=estado, motivo=motivo, faltan=faltan))
    return out


def construir(informe, hallazgos=None, cobertura=None):
    saneamiento = _campo(informe, "saneamiento") or {}
    saneamiento = saneamiento if isinstance(saneamiento, dict) else {}
    if cobertura is None:
        cobertura = _campo(_campo(informe, "devolucion"), "cobertura") or {}
    cobertura = cobertura if isinstance(cobertura, dict) else {}
    if hallazgos is None:
        hallazgos = list(_campo(informe, "hallazgos") or [])
    datos = _campo(informe, "datos") or []
    fuentes = []
    excel = cobertura.get("excel") or saneamiento.get("excel") or getattr(informe, "_excel_ejecucion", None) or {}
    archivos = list(saneamiento.get("archivos_origen") or [])
    excel = excel if isinstance(excel, dict) else {}
    for b in excel.get("bloques") or []:
        if isinstance(b, dict) and b.get("archivo") and b["archivo"] not in archivos:
            archivos.append(b["archivo"])
    pdf_meta = cobertura.get("pdf") or saneamiento.get("pdf") or {}
    pdf_meta = pdf_meta if isinstance(pdf_meta, dict) else {}
    lectura_archivos = {a.get("archivo"): a for a in saneamiento.get("lectura_archivos") or [] if isinstance(a, dict) and a.get("archivo")}
    if lectura_archivos:
        fuentes.append("lectura_archivos")
    for a in lectura_archivos:
        if a not in archivos:
            archivos.append(a)
    for a in pdf_meta.get("archivos") or []:
        if a not in archivos:
            archivos.append(a)
    filas_por_archivo = defaultdict(int)
    sin_origen = 0
    # Las filas de un Excel no llevan «archivo_origen»: su bloque (inicio, fin, archivo) dice de qué libro salen.
    rangos = [(b["inicio"], b["fin"], b["archivo"]) for b in excel.get("bloques") or []
              if isinstance(b, dict) and b.get("archivo") and isinstance(b.get("inicio"), int) and isinstance(b.get("fin"), int)]
    for k, f in enumerate(datos):
        a = f.get("archivo_origen") if isinstance(f, dict) else None
        a = a or next((ar for i0, i1, ar in rangos if i0 <= k < i1), None)
        if a:
            filas_por_archivo[a] += 1
        else:
            sin_origen += 1
    if saneamiento.get("filas_sin_archivo_origen") is not None:
        sin_origen = _cantidad(saneamiento["filas_sin_archivo_origen"]) or 0
        fuentes.append("filas_sin_archivo_origen")
    lectura_excel = excel.get("lectura") or {}
    lectura_por_archivo = {a.get("archivo"): a for a in lectura_excel.get("archivos") or []}
    hojas = [h for h in excel.get("hojas") or [] if isinstance(h, dict) and h.get("hoja")]
    bloques = [b for b in excel.get("bloques") or [] if isinstance(b, dict)]
    pdf = _pdf_ajustado(pdf_meta)
    controles = _controles(cobertura, hallazgos)
    if not controles:
        lentes_informe = getattr(informe, "_condiciones_lentes", None) or {}
        controles = [dict(control=k, nombre=NOMBRE_CONTROL.get(k, k),
                          estado={"evaluado": "ejecutado", "no_aplicable": "no_aplicable"}.get(v.get("estado"), "no_ejecutado"),
                          motivo=v.get("motivo"), senales=None, alcance=None) for k, v in lentes_informe.items()]
    estructura = saneamiento.get("estructura_revision") or {}
    hay_total = any(
        isinstance(x, str) and x.strip().lower().startswith("total")
        for f in datos[:5000] if isinstance(f, dict) for x in (*f.keys(), *f.values()))
    if not hay_total and len(datos) >= 3 and all(isinstance(f, dict) for f in datos[-3:]):
        # Un total de arrastre de página («Transporte» en la última fila de un cuadro ancho, sin otro
        # total y con evidencia de suma parcial) también es un total. Sólo en la columna de rótulos.
        from services.controles_excel.conciliacion import arrastre_en_filas
        from services.lentes.util import columna_etiqueta_fila
        from services.perfilado import numero as _numero

        filas = [f for f in datos[:5000] if isinstance(f, dict)]
        rotulos = columna_etiqueta_fila(filas)
        numericas = {k for k, v in filas[-1].items() if k != rotulos and _numero(v) is not None}
        hay_total = len(numericas) >= 2 and arrastre_en_filas(filas, rotulos) is not None
    if (isinstance(estructura, dict) and estructura.get("cantidad_cierres") == 0
            and ((estructura.get("relaciones_candidatas") or 0) > 0 or hay_total)
            and not any(c.get("control") == "cierres_totales" for c in controles)):
        # Hay un total identificado y no se pudo comprobar con sus componentes: es un control que no
        # corrió, no un «0 verificados». Se declara al comienzo del informe, con su motivo.
        controles.append(dict(control="cierres_totales", nombre="Cierres entre totales y componentes",
                              estado="no_ejecutado", senales=None, alcance=None,
                              motivo=estructura.get("motivo_sin_cierres") or "no se pudo comprobar el total con sus componentes"))
    pendientes = []
    mapa = saneamiento.get("mapa_lectura") or {}
    if mapa:
        from services.lector_mapa import resumen_lectura
        resumen = resumen_lectura(mapa)
        controles.append(dict(control="lector_cuadro", nombre="Lector del cuadro",
                              estado="ejecutado" if resumen["estado"] in {"completada", "parcial"} else "no_ejecutado",
                              motivo=f"Lectura {resumen['estado']}; relaciones propuestas por IA y verificadas con reglas",
                              senales=mapa.get("senales", 0),
                              alcance=f"{resumen['tramos_con_lectura']} de {resumen['tramos']} bloques con al menos dos respuestas"))
        for x in mapa.get("sin_leer") or []:
            pendientes.append(dict(tipo="no_controlado", archivo=x.get("archivo"),
                                   donde=f"lector del cuadro, hoja «{x.get('hoja')}»" +
                                   (f", cuadro {x['bloque']}" if x.get("bloque") is not None else ""), motivo=x.get("motivo")))
        fallas = []
        for h in mapa.get("hojas") or []:
            respuestas = list((h.get("mapas") or {}).values())
            if sum(not r.get("error") for r in respuestas) < 2 or any(r.get("error") for r in respuestas):
                fallas.append(h)
        if fallas:
            # Una línea para todos los tramos sin respuesta, con la falla más frecuente de cada lectora.
            from collections import Counter

            hojas_f = list(dict.fromkeys(str(h.get("hoja")) for h in fallas))
            errores = Counter(f"{lectora}: {str(r.get('error')).rstrip('.')}" for h in fallas
                              for lectora, r in (h.get("mapas") or {}).items() if r.get("error"))
            if len(fallas) == 1:
                filas = fallas[0].get("filas")
                donde = f"lector del cuadro, hoja «{hojas_f[0]}»" + (f", filas {filas}" if filas else "")
            else:
                donde = (f"lector del cuadro en {contar(len(fallas), 'tramo')} de {contar(len(hojas_f), 'hoja')} ("
                         + ", ".join(f"«{x}»" for x in hojas_f[:4]) + (" y otras" if len(hojas_f) > 4 else "") + ")")
            archivos_f = {h.get("archivo") for h in fallas}
            pendientes.append(dict(tipo="no_controlado", archivo=archivos_f.pop() if len(archivos_f) == 1 else None,
                                   donde=donde,
                                   motivo="faltan respuestas de las lectoras"
                                   + (f" ({'; '.join(e for e, _ in errores.most_common(2))})" if errores else "")
                                   + "; ver cobertura del lector"))
    sin_comprobar = (estructura.get("cierres_sin_comprobar") or []) if isinstance(estructura, dict) else []
    if sin_comprobar:
        por_concepto = {}
        for x in sin_comprobar:
            por_concepto.setdefault(str(x.get("concepto") or "total"), []).append(str(x.get("periodo")))
        donde = "; ".join(f"cierre de «{c.strip()}» en {', '.join(ps)}" for c, ps in por_concepto.items())
        pendientes.append(dict(tipo="no_controlado", archivo=None, donde=donde,
                               motivo="el total o algún componente no tiene dato («s/d», «-» o vacío) en ese período"))
    # Totales separados de sus componentes por filas vacías y jerarquías por código que no se pudieron
    # comprobar: no se cuentan como verificados, se dicen al comienzo con su motivo.
    for clave in ("totales_separados", "jerarquia_sin_comprobar", "totales_aparentes_sin_comprobar"):
        for x in ((estructura.get(clave) or []) if isinstance(estructura, dict) else [])[:10]:
            if isinstance(x, dict) and x.get("donde"):
                pendientes.append(dict(tipo="no_controlado", archivo=x.get("archivo"), donde=str(x["donde"]),
                                       motivo=str(x.get("motivo") or "no se pudo comprobar el cierre")))
    # Sondeo previo: controles que no se aplicaron en una hoja porque su lectura no pasó el sondeo.
    sondeo = saneamiento.get("sondeo") or {}
    for x in (sondeo.get("abstenciones") or []) if isinstance(sondeo, dict) else []:
        if isinstance(x, dict) and x.get("donde"):
            from services.sondeo import nombre_control
            donde = str(x["donde"])
            if x.get("regla"):
                donde = donde.replace(f"«{str(x['regla']).replace('_', ' ')}»", f"«{nombre_control(x['regla'])}»")
            pendientes.append(dict(tipo="no_controlado", archivo=x.get("archivo"), donde=donde,
                                   motivo=str(x.get("motivo") or "la hoja no pasó el sondeo previo")))
    revisada = saneamiento.get("lectura_revisada") or {}
    if isinstance(revisada, dict) and revisada.get("celdas_marcadas"):
        motivos = revisada.get("motivos_marcadas") or []
        pendientes.append(dict(
            tipo="no_leido", archivo=revisada.get("archivo_original"),
            donde=f"{revisada['celdas_marcadas']} {'celda marcada' if revisada['celdas_marcadas'] == 1 else 'celdas marcadas'} en la revisión de lectura",
            motivo="se confirmaron sin corregir" + (": " + "; ".join(m[:1].lower() + m[1:] for m in motivos[:3]) if motivos else "")
                   + "; esos valores pueden estar mal leídos"))
    for r in saneamiento.get("cobertura_cifras") or []:
        if isinstance(r, dict) and r.get("declarar"):
            ejemplos = "; ".join((r.get("ejemplos") or [])[:2])
            pendientes.append(dict(
                tipo="no_leido", archivo=r.get("archivo"),
                donde=f"{r.get('sin_incorporar')} de {r.get('en_archivo')} cifras del archivo",
                motivo="no entraron al análisis" + (f" (por ejemplo {ejemplos})" if ejemplos else "")
                       + "; pueden haberse perdido al leer"))
    cifras = revisada.get("cifras") if isinstance(revisada, dict) else None
    if isinstance(cifras, dict) and cifras.get("declarar_faltan"):
        ejemplo = (cifras.get("ejemplos_faltan") or [""])[0]
        pendientes.append(dict(
            tipo="no_leido", archivo=revisada.get("archivo_original"),
            donde=f"{cifras.get('faltan')} de {cifras.get('en_original')} cifras del texto del PDF",
            motivo="no están en la tabla analizada" + (f" (por ejemplo «{ejemplo}»)" if ejemplo else "")
                   + "; pueden haberse perdido al leer"))
    if isinstance(cifras, dict) and cifras.get("declarar_ajenas"):
        ejemplo = (cifras.get("ejemplos_ajenas") or [""])[0]
        pendientes.append(dict(
            tipo="no_leido", archivo=revisada.get("archivo_original"),
            donde=f"{cifras.get('ajenas')} de {cifras.get('en_lectura')} cifras de la tabla analizada",
            motivo="no aparecen en el texto del PDF" + (f" (por ejemplo «{ejemplo}»)" if ejemplo else "")
                   + ": la lectura pudo desarmar el cuadro, o se corrigieron a mano en la revisión"))
    if isinstance(cifras, dict) and cifras.get("fuera_del_texto"):
        pendientes.append(dict(
            tipo="no_leido", archivo=revisada.get("archivo_original"), donde="contenido del PDF fuera del texto leído",
            motivo=str(cifras["fuera_del_texto"])))
    if isinstance(cifras, dict) and cifras.get("rotulos_distintos"):
        ejemplo = cifras["rotulos_distintos"][0]
        pendientes.append(dict(
            tipo="no_leido", archivo=revisada.get("archivo_original"),
            donde=contar(cifras.get("rotulos_distintos_n") or len(cifras["rotulos_distintos"]), "rótulo", "rótulos")
                  + " de la tabla analizada",
            motivo=f"no coinciden con el texto del PDF (por ejemplo «{ejemplo}»): pueden estar mal leídos, "
                   "o se escribieron a mano en la revisión"))
    for nombre in saneamiento.get("derivados_revision_lectura") or []:
        pendientes.append(dict(tipo="no_leido", archivo=str(nombre), donde="archivo completo",
                               motivo="se derivó a la revisión de lectura y no forma parte de este informe"))
    registro_archivos = []
    for nombre in archivos:
        tipo = _tipo(nombre)
        propias = [h for h in hojas if h.get("archivo") == nombre]
        leidas = [h["hoja"] for h in propias if h.get("texto_sin_cifras") or (
            (h.get("filas_preparadas", h.get("filas_datos", 0)) or 0) > 0 and h.get("estado", "incluida") == "incluida")]
        no_leidas = []
        ocultas, no_interp, formulas = [], 0, 0
        hay_no_interp = hay_formulas = False
        extras = {}
        for h in propias:
            if h["hoja"] not in leidas:
                no_leidas.append(dict(hoja=h["hoja"], motivo=h.get("motivo") or h.get("estado") or "sin datos incorporados"))
            if h.get("revisada") is False and h["hoja"] in leidas:
                no_leidas.append(dict(hoja=h["hoja"], motivo=h.get("motivo_no_revisada") or "hoja no revisada"))
            if h.get("oculta") or h.get("hoja_oculta"):
                ocultas.append(h["hoja"])
            if h.get("celdas_no_interpretables") is not None:
                hay_no_interp = True
                no_interp += _cantidad(h.get("celdas_no_interpretables")) or 0
            # Celdas de columnas numéricas que no se pudieron leer como número: quedan fuera de los
            # controles numéricos aunque el resto de la hoja se haya leído.
            if h.get("celdas_no_numericas"):
                hay_no_interp = True
                no_interp += sum(_cantidad(x) or 0 for x in h["celdas_no_numericas"] if isinstance(x, dict))
            if h.get("formulas_sin_valor") is not None:
                hay_formulas = True
                formulas += _cantidad(h.get("formulas_sin_valor")) or 0
            for k, v in h.items():
                if k not in CLAVES_HOJA_CONOCIDAS and v not in (None, [], {}, 0, False):
                    extras.setdefault(h["hoja"], {})[k] = v
        lectura = lectura_por_archivo.get(nombre)
        series = None
        if lectura:
            series = dict(leidas=lectura.get("series_leidas"), aparentes=lectura.get("series_aparentes"),
                          motivos=lectura.get("motivos") or {})
        paginas = None
        if tipo == "pdf" and pdf:
            paginas = dict(leidas=(pdf.get("paginas_analizadas") - (pdf.get("paginas_sin_texto") or 0)
                                   if pdf.get("paginas_analizadas") is not None else None), total=pdf.get("paginas_documento"),
                           estado=pdf.get("estado"), filas_utiles=pdf.get("filas_utiles"))
        la = lectura_archivos.get(nombre) or {}
        if la.get("tipo_detectado"):
            tipo = {"xlsx": "excel", "xls": "excel", "csv": "csv", "pdf": "pdf"}.get(la["tipo_detectado"], tipo)
        for h in propias:
            vis = h.get("visibilidad") or {}
            if vis.get("estado_hoja") in {"hidden", "veryHidden"} and h["hoja"] not in ocultas:
                ocultas.append(h["hoja"])
            nr = h.get("no_revisada")
            if isinstance(nr, dict):
                no_leidas[:] = [x for x in no_leidas if x["hoja"] != h["hoja"]]
                no_leidas.append(dict(hoja=h["hoja"], motivo=f"{contar(nr.get('celdas_numericas') or 0, 'celda numérica', 'celdas numéricas')} sin revisar: {nr.get('motivo') or 'sin motivo informado'}"))
        if la.get("celdas_no_interpretables"):
            hay_no_interp = True
            no_interp += sum(_cantidad(x) or 0 for x in la["celdas_no_interpretables"]) if isinstance(la["celdas_no_interpretables"], list) else (_cantidad(la["celdas_no_interpretables"]) or 0)
        avisos_archivo = list(la.get("avisos") or [])
        for h in propias:
            for a in h.get("avisos_lectura") or []:
                # El aviso de la hoja ya viene en la lectura del archivo con su prefijo: no se repite.
                if not any(str(x).endswith(str(a)) for x in avisos_archivo):
                    avisos_archivo.append(a)
        no_leido = la.get("estado") in {"fallido", "sin_datos"}
        reg = dict(
            archivo=nombre,
            tipo=tipo,
            estado_lectura=la.get("estado"),
            motivo_lectura=la.get("motivo"),
            avisos=list(dict.fromkeys(avisos_archivo)) or None,
            filas_incorporadas=filas_por_archivo.get(nombre) or sum(
                (h.get("filas_preparadas", h.get("filas_datos", 0)) or 0) for h in propias
            ) or None,
            hojas_leidas=leidas,
            hojas_no_leidas=no_leidas,
            paginas=paginas,
            series=series,
            celdas_no_interpretables=no_interp if hay_no_interp else None,
            formulas_sin_valor=formulas if hay_formulas else None,
            ocultas=ocultas or None,
            # Un archivo que no se leyó no tiene controles ejecutados.
            controles=[] if no_leido else _controles_por_archivo(
                nombre, [b for b in bloques if b.get("archivo") == nombre], controles, tipo),
            extras=extras or None,
        )
        registro_archivos.append(reg)
        if la.get("estado") in {"fallido", "sin_datos"}:
            pendientes.append(dict(tipo="no_leido", archivo=nombre, donde="archivo completo",
                                   motivo=la.get("motivo") or ("no se pudo leer" if la["estado"] == "fallido" else "sin datos")))
        for b in la.get("bloques_descartados") or []:
            pendientes.append(dict(tipo="no_leido", archivo=nombre, donde=f"página {b.get('pagina')}",
                                   motivo=f"{contar(b.get('filas') or 0, 'fila descartada', 'filas descartadas')}"))
        # Canal genérico de la lectura: lo que el lector no pudo leer o decidir, con su motivo.
        for x in la.get("pendientes_lectura") or []:
            if isinstance(x, dict) and x.get("tipo") in {"no_leido", "no_controlado"}:
                pendientes.append(dict(tipo=x["tipo"], archivo=nombre, donde=x.get("donde") or "archivo",
                                       motivo=x.get("motivo") or "sin motivo informado"))
        if la.get("filas_descartadas"):
            n = len(la["filas_descartadas"])
            pendientes.append(dict(tipo="no_leido", archivo=nombre,
                                   donde=("fila " if n == 1 else "filas ") + muestra(la["filas_descartadas"], maximo=6),
                                   motivo=("tienen más campos que el encabezado" if n > 1 else "tiene más campos que el encabezado")
                                   + ("; no se incorporaron" if n > 1 else "; no se incorporó") + " para no correr sus valores de columna"))
        for h in no_leidas:
            pendientes.append(dict(tipo="no_leido", archivo=nombre, donde=f"hoja «{h['hoja']}»", motivo=h["motivo"]))
        if hay_no_interp and no_interp:
            pendientes.append(dict(tipo="no_leido", archivo=nombre, donde=contar(no_interp, "celda", "celdas"),
                                   motivo="no se pudieron interpretar como números"))
        for h in propias:
            for e in h.get("encabezados_no_separados") or []:
                if isinstance(e, dict):
                    pendientes.append(dict(tipo="no_controlado", archivo=nombre,
                                           donde=f"hoja «{h['hoja']}», fila {e.get('fila')}",
                                           motivo=e.get("motivo") or "encabezado de otro cuadro no separado"))
            for x in h.get("fuera_de_cuadros") or []:
                if isinstance(x, dict):
                    pendientes.append(dict(tipo="no_controlado", archivo=nombre,
                                           donde=f"hoja «{h['hoja']}», filas {x.get('filas')} (columnas {x.get('columnas')})",
                                           motivo=f"{contar(x.get('valores') or 0, 'valor numérico', 'valores numéricos')} fuera de los cuadros leídos"))
            for c in h.get("columnas_no_controladas") or []:
                if isinstance(c, dict):
                    pendientes.append(dict(tipo="no_controlado", archivo=nombre,
                                           donde=f"hoja «{h['hoja']}», columna «{c.get('columna')}» ({c.get('celda') or c.get('letra')})",
                                           motivo=c.get("motivo") or "columna numérica fuera de los controles"))
        if hay_formulas and formulas:
            pendientes.append(dict(tipo="no_leido", archivo=nombre, donde=f"{formulas} fórmulas",
                                   motivo="sin valor calculado guardado en el archivo"))
        # Una hoja oculta cuyos datos se leyeron no está «sin leer»: se avisa que estaba oculta.
        ocultas_sin_leer = [h for h in ocultas if h not in leidas]
        if ocultas_sin_leer:
            pendientes.append(dict(tipo="no_leido", archivo=nombre, donde="hojas ocultas: " + ", ".join(ocultas_sin_leer),
                                   motivo="ocultas en el libro; verificar si debían revisarse"))
        ocultas_leidas = [h for h in ocultas if h in leidas]
        if ocultas_leidas:
            aviso = (f"{'Hoja oculta' if len(ocultas_leidas) == 1 else 'Hojas ocultas'} en el libro: "
                     f"{', '.join(ocultas_leidas)}; sus datos se leyeron y se controlaron. Verificar si debían publicarse.")
            reg["avisos"] = list(dict.fromkeys((reg["avisos"] or []) + [aviso]))
        if series and series.get("aparentes") and (series.get("leidas") or 0) < series["aparentes"]:
            pendientes.append(dict(tipo="no_leido", archivo=nombre,
                                   donde=f"{series['aparentes'] - (series.get('leidas') or 0)} de {series['aparentes']} series",
                                   motivo="; ".join(series["motivos"].keys()) or "no se reconocieron como series por período"))
        if paginas and paginas.get("total") and paginas.get("leidas") is not None and paginas["leidas"] < paginas["total"]:
            pendientes.append(dict(tipo="no_leido", archivo=nombre,
                                   donde=f"páginas {paginas['leidas'] + 1} a {paginas['total']}",
                                   motivo="fuera del límite de páginas analizadas"))
        if tipo == "pdf" and pdf.get("estado") == "insuficiente":
            pendientes.append(dict(tipo="no_leido", archivo=nombre, donde="tablas del documento",
                                   motivo="no se extrajeron tablas por período suficientes para aplicar controles"))
    # Lectura informada sin detalle por archivo: igual se declara lo que falta.
    if not any(a["tipo"] == "pdf" for a in registro_archivos) and pdf:
        if pdf.get("estado") == "insuficiente":
            pendientes.append(dict(tipo="no_leido", archivo=None, donde="tablas del PDF",
                                   motivo="no se extrajeron tablas por período suficientes para aplicar controles"))
        elif pdf.get("estado") == "parcial":
            pendientes.append(dict(tipo="no_leido", archivo=None, donde="parte del PDF",
                                   motivo="documento recortado o con cuadros sin columnas o rótulos confiables"))
    if not lectura_por_archivo and lectura_excel.get("series_aparentes") and (
        lectura_excel.get("series_leidas") or 0
    ) < lectura_excel["series_aparentes"]:
        faltan = lectura_excel["series_aparentes"] - (lectura_excel.get("series_leidas") or 0)
        pendientes.append(dict(tipo="no_leido", archivo=None,
                               donde=f"{faltan} de {lectura_excel['series_aparentes']} series",
                               motivo="no se reconocieron como series por período"))
    if len(archivos) > 1 and sin_origen:
        pendientes.append(dict(tipo="no_controlado", archivo=None, donde=f"{sin_origen} filas",
                               motivo="sin archivo de origen: no se pueden atribuir a un documento ni cruzar entre archivos"))
    if isinstance(pdf_meta, dict):
        for b in pdf_meta.get("bloques_descartados") or []:
            if isinstance(b, dict) and not (lectura_archivos.get(b.get("archivo")) or {}).get("bloques_descartados"):
                pendientes.append(dict(tipo="no_leido", archivo=b.get("archivo"), donde=f"página {b.get('pagina')}",
                                       motivo=f"{contar(b.get('filas') or 0, 'fila descartada', 'filas descartadas')}"))
    avisos = list(dict.fromkeys(
        [str(a) for a in saneamiento.get("avisos_lectura") or []]
        + [str(a) for a in (pdf_meta.get("avisos") or [] if isinstance(pdf_meta, dict) else [])]
        + [a for r_ in registro_archivos for a in r_.get("avisos") or []]
    ))
    for x in saneamiento.get("registro_lectura") or []:
        if isinstance(x, dict) and x.get("estado") in {"no_leido", "no_controlado"}:
            donde = x.get("donde") or x.get("elemento") or (f"hoja «{x['hoja']}»" if x.get("hoja") else None) or (
                f"página {x['pagina']}" if x.get("pagina") else "elemento sin identificar")
            pendientes.append(dict(tipo=x["estado"], archivo=x.get("archivo"), donde=donde, motivo=x.get("motivo") or "sin motivo informado"))
    if saneamiento.get("registro_lectura"):
        fuentes.append("registro_lectura")
    for a in registro_archivos:
        for c in a.get("controles") or []:
            f = c.get("faltan")
            if c["estado"] == "ejecutado" and f:
                pendientes.append(dict(tipo="no_controlado", archivo=a["archivo"],
                                       donde=f"{c['nombre']} en {f['cuadros']} de {f['total']} cuadros",
                                       motivo=f["motivo"]))
    for c in controles:
        if c["estado"] == "no_ejecutado":
            pendientes.append(dict(tipo="no_controlado", archivo=None, donde=c["nombre"], motivo=c.get("motivo") or "no ejecutado"))
    interdoc = cobertura.get("control_interdocumental") or getattr(informe, "_condiciones_interdocumentales", None) or {}
    cruces = _cruces(hallazgos, archivos, interdoc)
    if cruces["estado"] in {"no_evaluado", "sin_emparejar"} and len(archivos) > 1:
        pendientes.append(dict(tipo="no_controlado", archivo=None, donde="cruce entre archivos", motivo=cruces["texto"]))
    leido_algo = bool(datos)
    insuficiente = (pdf.get("estado") == "insuficiente" and all(_tipo(a) == "pdf" for a in archivos)) or (
        lectura_excel.get("estado") == "insuficiente") or (not leido_algo and bool(archivos))
    estado = "insuficiente" if insuficiente else ("parcial" if pendientes else "completo")
    no_leidos = [p for p in pendientes if p["tipo"] == "no_leido"]
    no_controlados = [p for p in pendientes if p["tipo"] == "no_controlado"]
    if not pendientes:
        partes = []
        if hojas:
            partes.append(contar(sum(len(a['hojas_leidas']) for a in registro_archivos), "hoja"))
        if pdf.get("paginas_documento"):
            partes.append(contar(pdf['paginas_documento'], "página"))
        primera = ("LECTURA COMPLETA. Se leyó todo lo cargado" + (f" ({contar(len(archivos), 'archivo')}" + (", " + ", ".join(partes) if partes else "") + ")" if archivos else "")
                   + " y se ejecutaron los controles aplicables.")
    else:
        def corto(p):
            return (f"{p['archivo']}: " if p.get("archivo") else "") + f"{p['donde']} ({p['motivo']})"

        trozos = []
        if no_leidos:
            trozos.append("Sin leer: " + "; ".join(corto(p) for p in no_leidos[:4]) + (f"; y {len(no_leidos) - 4} más" if len(no_leidos) > 4 else ""))
        if no_controlados:
            trozos.append("Sin controlar: " + "; ".join(corto(p) for p in no_controlados[:4]) + (f"; y {len(no_controlados) - 4} más" if len(no_controlados) > 4 else ""))
        primera = ("LECTURA INSUFICIENTE. " if estado == "insuficiente" else "LECTURA PARCIAL. ") + ". ".join(trozos) + "."
    if avisos:
        primera = primera.rstrip(".") + ". Avisos de lectura: " + "; ".join(a.rstrip(".") for a in avisos[:3]) + (
            f"; y {len(avisos) - 3} más" if len(avisos) > 3 else "") + "."
        primera = re.sub(r"\.\.+", ".", primera)
    return dict(
        version=1,
        estado=estado,
        primera_linea=primera,
        pendientes=pendientes,
        archivos=registro_archivos,
        controles=controles,
        cruces=cruces,
        periodo=periodo(informe),
        pdf=pdf or None,
        avisos=avisos,
        fuentes=fuentes,
    )


ESTADO_LEGIBLE = {"completo": "Lectura completa", "parcial": "Lectura parcial", "insuficiente": "Lectura insuficiente"}


def lineas_markdown(reg):
    """Sección «Qué se leyó y qué se controló», igual en todas las piezas."""
    out = ["## Qué se leyó y qué se controló", ""]
    for a in reg.get("archivos") or []:
        partes = [f"**{a['archivo']}**"]
        if a.get("hojas_leidas") or a.get("hojas_no_leidas"):
            partes.append(f"hojas leídas: {', '.join(a['hojas_leidas']) or 'ninguna'}")
        if a.get("hojas_no_leidas"):
            partes.append("no leídas: " + "; ".join(f"{h['hoja']} ({h['motivo']})" for h in a["hojas_no_leidas"]))
        if a.get("paginas"):
            p = a["paginas"]
            partes.append(f"páginas leídas: {p.get('leidas')} de {p.get('total') or 'total no informado'}")
        if a.get("filas_incorporadas"):
            partes.append(f"{a['filas_incorporadas']} filas incorporadas")
        if a.get("series") and a["series"].get("aparentes"):
            partes.append(f"{a['series']['leidas']} de {a['series']['aparentes']} series por período")
        for clave, nombre in (("celdas_no_interpretables", "celdas no interpretables"), ("formulas_sin_valor", "fórmulas sin valor guardado")):
            if a.get(clave):
                partes.append(f"{a[clave]} {nombre}")
        if a.get("ocultas"):
            partes.append("hojas ocultas: " + ", ".join(a["ocultas"]))
        if a.get("estado_lectura") in {"fallido", "sin_datos"}:
            partes.append(f"no leído ({a.get('motivo_lectura') or a['estado_lectura']})")
        out.append("- " + "; ".join(partes) + ".")
        for aviso in a.get("avisos") or []:
            out.append(f"  - Aviso de lectura: {aviso}")
        no = [c for c in a.get("controles") or [] if c["estado"] != "ejecutado"]
        si = [c for c in a.get("controles") or [] if c["estado"] == "ejecutado"]
        if si:
            out.append("  - Controles ejecutados: " + ", ".join(c["nombre"] for c in si) + ".")
        if no:
            out.append("  - No ejecutados: " + "; ".join(
                f"{c['nombre']} ({'no aplica' if c['estado'] == 'no_aplicable' else 'no ejecutado'}"
                + (f": {c['motivo']}" if c.get("motivo") else "") + ")" for c in no) + ".")
    out.append(f"- {reg['cruces']['texto']}")
    for d in reg["cruces"].get("detalle") or []:
        out.append(f"  - {d}")
    out.append(f"- {reg['periodo']['texto']}")
    out.append("")
    return out
