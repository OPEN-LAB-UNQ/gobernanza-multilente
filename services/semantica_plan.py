"""Plan semántico completo, representación sin pérdida y cobertura por tarea.

Un barrido global válido cubre el corpus y sus comparaciones. Si no cabe, se
exigen TODOS los lotes locales y una segunda pasada de relaciones entre hojas.
No se atribuye cobertura a una mera transmisión o a una respuesta descartada.
"""

from __future__ import annotations

import hashlib
import json
import time
from itertools import product

LIMITES = {"renderix": 6000, "llama": 12000}
MAX_LLAMADAS = 24
MAX_SEGUNDOS = 240


def compacto(ctx):
    textos = []
    hojas = []
    roles = []
    tmap = {}
    hmap = {}
    rmap = {}

    def idx(m, arr, key):
        if key not in m:
            m[key] = len(arr)
            arr.append(key)
        return m[key]

    elementos = []
    for e in ctx.get("elementos", []):
        elementos.append(
            [
                e["id"],
                idx(hmap, hojas, (e["archivo"], e["hoja"])),
                e["celda"],
                idx(rmap, roles, e["rol"]),
                idx(tmap, textos, e["texto"]),
            ]
        )
    # Las aristas se codifican una sola vez. No se descartan comparaciones.
    # Celdas, rótulos y nombres de hoja con forma de instrucción viajan citados como dato.
    from services.triangulacion_validacion import neutralizar, neutralizar_valor

    return {
        "formato": "diccionarios-v1",
        "columnas_elementos": ["id", "hoja_idx", "celda", "rol_idx", "texto_idx"],
        "textos": [neutralizar(t) for t in textos],
        "hojas": neutralizar_valor(hojas),
        "roles": roles,
        "elementos": elementos,
        "periodos_por_elemento": {e["id"]: e["periodo_fila"] for e in ctx.get("elementos", []) if e.get("periodo_fila")},
        "rangos_combinados_por_elemento": {e["id"]: e["rango_combinado"] for e in ctx.get("elementos", []) if e.get("rango_combinado")},
        "contexto_bloques": [{"id": b["id"], "columnas": b.get("columnas_contexto", []),
                             "periodos_filas": b.get("periodos_filas", {})} for b in ctx.get("bloques", [])
                            if b.get("periodos_filas") or b.get("columnas_contexto")],
        "alcance_fragmentos": "Los lotes son recortes de transmisión, no cuadros ni ciclos del libro. Las filas no incluidas no están ausentes del original. Usar periodos_filas para desambiguar meses y verificar continuidad; no inferir años por el título ni por la fecha de carga.",
        "bloques": [[b["id"], b["referencias"]] for b in ctx.get("bloques", [])],
        "relaciones_adyacencia": {
            a: sorted({r["bloques"][1] for r in ctx.get("relaciones", []) if r["bloques"][0] == a})
            for a in sorted({r["bloques"][0] for r in ctx.get("relaciones", [])})
        },
    }


def tamano(ctx):
    return len(json.dumps(compacto(ctx), ensure_ascii=False, separators=(",", ":")).encode())


def planificar(corpus, presupuesto):
    elems = {e["id"]: e for e in corpus.get("elementos", [])}
    bs = {b["id"]: b for b in corpus.get("bloques", [])}
    relaciones = corpus.get("relaciones", [])

    def paquete(refs, bids):
        return {
            "elementos": [e for k, e in elems.items() if k in refs],
            "bloques": [{**bs[b], "referencias": [r for r in bs[b]["referencias"] if r in refs]} for b in sorted(bids)],
            "relaciones": [r for r in relaciones if set(r["bloques"]) <= bids],
        }

    completo = paquete(set(elems), set(bs))
    alcance = {
        "corpus_sha256": hashlib.sha256(json.dumps(corpus, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "elementos_totales": len(elems),
        "bloques_totales": len(bs),
        "relaciones_totales": len(relaciones),
        "exclusiones_corpus": {
            "elementos_omitidos": corpus.get("elementos_omitidos", 0),
            "errores": corpus.get("errores", []),
            "relaciones_limitadas": corpus.get("relaciones_limitadas", False),
        },
        "corpus_definido": "Todos los elementos saneados almacenados y todas las relaciones candidatas almacenadas; no equivale a todo contenido posible del archivo.",
    }
    if not elems:
        return {
            "estrategia": "sin_corpus",
            "tareas": [],
            "alcance": alcance,
            "error": "No hay contexto semántico almacenado.",
        }
    if tamano(completo) <= presupuesto:
        return {
            "estrategia": "global",
            "tareas": [{"id": "global-1", "fase": "global", "contexto": completo}],
            "alcance": alcance,
        }
    # Fragmentos con anclas repetidas preservan contexto de títulos/hojas/fuentes.
    fragmentos = {}
    locales = []
    visitados = set()
    omitidos = []
    for bid, b in bs.items():
        refs = [r for r in b["referencias"] if r in elems]
        anclas = [r for r in refs if elems[r]["rol"] != "indicador_categoria"]
        resto = [r for r in refs if r not in anclas]
        partes = []
        actual = set(anclas)
        if tamano(paquete(actual, {bid})) > presupuesto // 2:
            # No repetir TODAS las notas en cada lote. Conservar unas anclas
            # compartidas y tratar las restantes como contenido a cubrir.
            # Las comparaciones entre fragmentos de este mismo bloque se
            # incluyen abajo: no se pierde ninguna nota ni par comparativo.
            compartidas = set()
            for ref in anclas:
                if elems[ref]["rol"] in {"nombre_hoja", "titulo", "titulo_subtitulo", "unidad", "fuente"} and tamano(paquete(compartidas | {ref}, {bid})) <= presupuesto // 4:
                    compartidas.add(ref)
            anclas = [r for r in refs if r in compartidas]
            resto = [r for r in refs if r not in compartidas]
            actual = set(anclas)
        for ref in resto:
            prueba = actual | {ref}
            if tamano(paquete(prueba, {bid})) > presupuesto // 2 and actual != set(anclas):
                partes.append(actual)
                actual = set(anclas)
            actual.add(ref)
            if tamano(paquete(actual, {bid})) > presupuesto // 2:
                # Un elemento que no entra ni solo con sus anclas no se recorta: queda fuera de la
                # exploración, declarado en el alcance, y el resto del libro se explora igual.
                actual.discard(ref)
                omitidos.append(ref)
        if actual:
            partes.append(actual)
        fragmentos[bid] = partes
        for refs_set in partes:
            locales.append((refs_set, {bid}))
            visitados.update(refs_set)
    visitados.update(omitidos)
    if omitidos:
        alcance["omitidos_por_tamano"] = sorted(omitidos)
    for ref in elems.keys() - visitados:
        locales.append(({ref}, set()))

    def empaquetar(unidades, fase):
        tasks = []
        refs = set()
        bids = set()
        for r, b in unidades:
            nr, nb = refs | r, bids | b
            if refs and tamano(paquete(nr, nb)) > presupuesto:
                tasks.append({"id": f"{fase}-{len(tasks) + 1}", "fase": fase, "contexto": paquete(refs, bids)})
                refs, bids = set(), set()
                nr, nb = set(r), set(b)
            if tamano(paquete(nr, nb)) > presupuesto:
                raise ValueError("Una comparación transversal excede el contexto; estrategia incompleta.")
            refs, bids = nr, nb
        if refs:
            tasks.append({"id": f"{fase}-{len(tasks) + 1}", "fase": fase, "contexto": paquete(refs, bids)})
        return tasks

    # Segunda pasada cruza todas las relaciones, incluso las que caen entre lotes.
    # Uniones por pares de fragmentos: las fronteras de contexto no eliminan pares.
    transversales = []
    for rel in relaciones:
        a, b = rel["bloques"]
        for fa, fb in product(fragmentos.get(a, []), fragmentos.get(b, [])):
            transversales.append((fa | fb, {a, b}))
    # Las notas de un bloque también pueden quedar a lados distintos del corte.
    # Compararlas explícitamente, aun cuando no haya otro bloque relacionado.
    for bid, partes in fragmentos.items():
        for i, fa in enumerate(partes):
            for fb in partes[i + 1:]:
                transversales.append((fa | fb, {bid}))
    if not relaciones:
        bloques_fragmentados = list(fragmentos.items())
        for i, (a, partes_a) in enumerate(bloques_fragmentados):
            for b, partes_b in bloques_fragmentados[i + 1:]:
                for fa, fb in product(partes_a, partes_b):
                    transversales.append((fa | fb, {a, b}))
    if not transversales:
        transversales = locales
    try:
        tasks = empaquetar(locales, "local") + empaquetar(transversales, "transversal")
    except ValueError as exc:
        return {"estrategia": "lotes_transversal", "tareas": [], "alcance": alcance, "error": str(exc)}
    return {"estrategia": "lotes_transversal", "tareas": tasks, "alcance": alcance}


def ejecutar(fn, ctx, hallazgos, llamar):
    """Una estrategia por proveedor; conserva fallos, salidas y cobertura real."""
    modelo = ctx.get("_modelo") or getattr(fn, "__name__", "modelo").replace("_interpretar_", "")
    inicio = time.monotonic()
    corpus = ctx.get("contexto_semantico") or {}
    # Los controles numéricos conservan su presupuesto y su resultado independiente.
    base = (
        llamar(fn, {k: v for k, v in ctx.items() if k != "contexto_semantico"}, hallazgos)
        if hallazgos
        else {"modelo": modelo, "contenido": None, "error": None, "llamadas": []}
    )
    lectura_estado = (
        "no_solicitada" if not hallazgos
        else "completada" if base.get("contenido") is not None
        else "omitida" if base.get("status") == "skipped"
        else "fallida"
    )
    lectura_tarea = {"estado": lectura_estado, "error": base.get("error") if lectura_estado in {"fallida", "omitida"} else None}
    if not corpus.get("elementos"):
        return {**base, "estado_tareas": {"lectura_senales": lectura_tarea, "exploracion_libro": {"estado": "no_solicitada", "error": None}}}
    presupuesto = min(LIMITES.get(modelo, 12000), 12000)
    plan = planificar(corpus, presupuesto)
    # Lotes acotados con anclas y comparación transversal; no delegar todo el libro.
    while presupuesto > 1500 and any(len(t['contexto']['elementos']) > 120 for t in plan['tareas']):
        presupuesto = max(1500, presupuesto // 2)
        plan = planificar(corpus, presupuesto)
    version = base.get("identificador_version")
    ok = []
    errores = []
    items = []
    llamadas = list(base.get("llamadas", []))
    validos = set()
    bloques = set()
    enviados = set()
    bloques_enviados = set()
    cross = []
    if plan.get("error"):
        errores.append(plan["error"])
    tareas = list(plan["tareas"])
    reajustes = []
    posicion = 0
    while posicion < len(tareas):
        tarea = tareas[posicion]
        if len(llamadas) >= MAX_LLAMADAS or time.monotonic() - inicio > MAX_SEGUNDOS:
            errores.append("Límite de llamadas o tiempo de la estrategia alcanzado; quedan tareas sin completar.")
            break
        c = {k: v for k, v in ctx.items() if k != "contexto_semantico"}
        c.update(
            _semantica_activa=True,
            _validacion_por_elemento=True,
            _semantica_enviada=tarea["contexto"],
            _fase_semantica=tarea["fase"],
            _intentos_permitidos=min(2, MAX_LLAMADAS - len(llamadas)),
            # Para marcar hipótesis que contradicen señales del motor.
            _hallazgos_motor=[
                {"idx": i, "descripcion": h.get("descripcion"), "severidad": h.get("severidad")}
                for i, h in enumerate(hallazgos or [])
            ],
        )
        enviados.update(e["id"] for e in tarea["contexto"]["elementos"])
        bloques_enviados.update(b["id"] for b in tarea["contexto"]["bloques"])
        it = llamar(fn, c, [])
        for log in it.get("llamadas", []):
            llamadas.append({**log, "fase": tarea["fase"], "lote": tarea["id"]})
        contenido = it.get("contenido")
        version = it.get("identificador_version") or version
        if not contenido:
            # Una salida truncada no se arregla repitiendo el mismo lote.
            # Replanificar ese corpus con menos entrada y comparación transversal,
            # dentro del mismo límite total de llamadas y tiempo.
            truncada = any(log.get("error_type") == "token_limit" for log in it.get("llamadas", []))
            profundidad = tarea.get("subdivision", 0)
            bytes_actuales = tamano(tarea["contexto"])
            if truncada and profundidad < 2 and len(llamadas) < MAX_LLAMADAS:
                reducido = planificar(tarea["contexto"], max(1500, bytes_actuales // 2))
                nuevas = reducido.get("tareas", [])
                if nuevas and not reducido.get("error") and all(tamano(t["contexto"]) < bytes_actuales for t in nuevas):
                    nuevas = [{**t, "id": tarea["id"] + "/" + t["id"], "subdivision": profundidad + 1} for t in nuevas]
                    reajustes.append({"tarea": tarea["id"], "motivo": "token_limit", "subtareas": [t["id"] for t in nuevas]})
                    tareas[posicion:posicion + 1] = nuevas
                    continue
            errores.append(f"{tarea['id']}: {it.get('error') or 'Sin salida válida'}")
            posicion += 1
            continue
        posicion += 1
        items.extend(contenido.get("hallazgos_exploratorios", []))
        rechazadas = contenido.get("hipotesis_rechazadas", [])
        if rechazadas:
            errores.extend(f"{tarea['id']}: hipótesis {h['indice']} rechazada: {h['motivo']}" for h in rechazadas)
            continue  # conservar hipótesis buenas, sin acreditar cobertura completa del lote
        ok.append(tarea["id"])
        validos.update(e["id"] for e in tarea["contexto"]["elementos"])
        bloques.update(b["id"] for b in tarea["contexto"]["bloques"])
        if tarea["fase"] in {"global", "transversal"}:
            cross.append(tarea["id"])
    plan["tareas"] = tareas
    completas = bool(plan["tareas"]) and len(ok) == len(plan["tareas"]) and bool(cross)
    # Deduplicar sólo hipótesis idénticas del mismo proveedor, sin fabricar consenso.
    unicos = {}
    for h in items:
        unicos.setdefault((h["tipo"], tuple(sorted(h["referencias"]))), h)
    estrategia = {
        **plan["alcance"],
        "estrategia": plan["estrategia"],
        "status": "completed" if completas else "incomplete",
        "evaluada": completas,
        "tareas_totales": len(plan["tareas"]),
        "tareas_completadas": ok,
        "comparacion_transversal_completada": bool(cross)
        and all(t["id"] in ok for t in plan["tareas"] if t["fase"] in {"global", "transversal"}),
        "elementos_cubiertos": len(validos),
        "bloques_cubiertos": len(bloques),
        "motivos": errores,
        "reajustes_por_truncamiento": reajustes,
        "latency": round(time.monotonic() - inicio, 3),
        "max_llamadas": MAX_LLAMADAS,
        "max_segundos": MAX_SEGUNDOS,
    }
    # Dos tareas con estado propio. Nunca se sintetiza una lectura de señales:
    # si la lectura falló y la exploración respondió, el contenido sólo trae
    # lo que el modelo efectivamente produjo (hipótesis exploratorias).
    contenido = base.get("contenido")
    exploracion_estado = "completada" if completas else "incompleta" if (ok or items) else "fallida"
    if contenido is not None:
        contenido = {**contenido, "hallazgos_exploratorios": list(unicos.values())}
    elif ok or items:
        contenido = {"hallazgos_exploratorios": list(unicos.values())}
    errores_tareas = []
    if lectura_estado == "fallida":
        errores_tareas.append("Lectura de señales: " + str(base.get("error") or "sin salida válida"))
    if exploracion_estado == "fallida":
        errores_tareas.append("Exploración del libro: " + ("; ".join(errores) or "sin salida válida"))
    estado_tareas = {
        "lectura_senales": lectura_tarea,
        "exploracion_libro": {"estado": exploracion_estado, "error": "; ".join(errores) or None},
    }
    sem_alcance = {
        **plan["alcance"],
        "elementos_enviados": len(enviados),
        "bloques_enviados": len(bloques_enviados),
        "elementos_cubiertos": len(validos),
        "bloques_cubiertos": len(bloques),
        "parcial": not completas,
        "evaluada": completas,
        "estrategia": estrategia,
    }
    fallos = [x for x in llamadas if x.get("status") != "completed"]
    ultimo = fallos[-1] if fallos else {}
    diagnostico = {
        "status": "completed" if completas else "incomplete",
        "error_type": None if completas else ultimo.get("error_type") or "coverage_incomplete",
        "http_status": ultimo.get("http_status") if fallos else (llamadas[-1].get("http_status") if llamadas else None),
        "latency": estrategia["latency"],
        "input_tokens": sum(x["input_tokens"] for x in llamadas)
        if llamadas and all(x.get("input_tokens") is not None for x in llamadas)
        else None,
        "input_elements": sum(x.get("input_elements", 0) for x in llamadas),
        "output_received": any(x.get("output_received") for x in llamadas),
        "parse_status": "valid" if completas else ultimo.get("parse_status") or "incomplete",
        "discard_reason": None if completas else "; ".join(errores),
    }
    return {
        **base,
        "modelo": modelo,
        "identificador_version": version,
        "diagnostico": diagnostico,
        "contenido": contenido,
        "error": "; ".join(errores_tareas) or None,
        "estado_tareas": estado_tareas,
        "estrategia_semantica": estrategia,
        "llamadas": llamadas,
        "status": "completed" if completas else "incomplete",
        "alcance_ia": {**(base.get("alcance_ia") or {}), "semantica": sem_alcance},
        "intentos": len(llamadas),
    }
