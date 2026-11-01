"""Contexto y relaciones verificadas compartidas por controles y presentación.

Las relaciones candidatas requieren cierre en varios períodos o, en series
cortas, la misma relación cerrando en otras hojas o cuadros del archivo. Una
igualdad numérica aislada nunca demuestra equivalencia administrativa.
"""
import re
from collections import defaultdict

from services.controles_excel.comun import normalizar, numero, referencia
from services.controles_excel.conciliacion import (
    clave_relacion,
    corroboradas_por_repeticion,
    es_total,
    estadistica_repeticion,
    firma_relacion,
    pruebas_relacion,
    relacion_corroborada,
    relaciones_cuadro,
)
from services.controles_excel.temporal import mapa_periodos
from services.perfilado import es_no_publicado, es_suprimido
from services.sanitizacion import redactar_texto_libre


def contexto_cuadro(ws, bloque):
    """Conserva títulos explícitos anteriores al encabezado, sin inventar ámbito."""
    header = min(bloque['encabezados'])
    candidatos = []
    # Sólo filas estructurales, nunca valores de otra tabla.
    for row in range(max(1, header - 8), header):
        valores = [ws.cell(row, col).value for col in range(1, min(ws.max_column, 5) + 1)]
        textos = [str(v).strip() for v in valores if isinstance(v, str) and v.strip()]
        if len(textos) != 1 or any(numero(v) is not None for v in valores):
            continue
        t = textos[0]
        if normalizar(t).startswith(('fuente', 'nota', 'en ', '(')) or len(t) > 180:
            continue
        candidatos.append(redactar_texto_libre(t))
    return candidatos[-1] if candidatos else None


def _rotulo_periodo(valor, periodo):
    """Cómo se lee el período en el archivo: «2025-09» y no su número interno."""
    import datetime as dt

    if isinstance(valor, (dt.datetime, dt.date)):
        return valor.strftime("%Y-%m")
    texto = str(valor if valor is not None else periodo).strip()
    return texto[:7] if re.fullmatch(r"\d{4}-\d{2}-\d{2}( 00:00:00)?", texto) else texto


def _no_publicados(marcas):
    """«datos suprimidos por confidencialidad estadística («<5», «s.e.»)», con las marcas que trae el cuadro."""
    partes = []
    for clase, texto in (('suprimido', 'datos suprimidos por confidencialidad estadística'),
                         ('menor', 'valores menores que la unidad mínima publicada')):
        propias = [f'«{m}»' for m, c in marcas.items() if c == clase][:3]
        if propias:
            partes.append(f'{texto} ({", ".join(propias)})')
    return ' y '.join(partes) or 'datos no publicados'


RITMO_ATIPICO = 1.5  # un componente se mueve fuera del ritmo del total si crece 1,5 veces más, o 1,5 veces menos
COBERTURA_COMPENSACION = 0.5


def _compensaciones(padre, hijos, pruebas):
    """Componentes que el mismo período se mueven fuera del ritmo del total y en sentido contrario.

    Con un total que cierra, los desvíos de los componentes respecto del crecimiento del total suman
    cero por construcción: no alcanza con que «otra categoría suba». Sólo cuentan los componentes cuyo
    propio cambio se aparta del ritmo del total y van en sentido opuesto; si juntos cubren al menos la
    mitad del desvío, la hipótesis de reclasificación entre categorías queda registrada en la serie.
    """
    orden = list(mapa_periodos(padre))
    por = {p[0]: p for p in pruebas if p[-1]}
    for a, b in zip(orden, orden[1:]):
        if a not in por or b not in por:
            continue
        va, ta, vb, tb = por[a][3], por[a][4], por[b][3], por[b][4]
        if not ta or ta <= 0 or not tb or tb <= 0:
            continue
        ritmo = tb / ta
        desvios = [y - x * ritmo for x, y in zip(va, vb)]
        atipicos = {k for k, (x, y) in enumerate(zip(va, vb))
                    if x > 0 and y >= 0 and not 1 / RITMO_ATIPICO <= (y / x) / ritmo <= RITMO_ATIPICO}
        for k, d in enumerate(desvios):
            if abs(d) <= 1e-9 * tb:
                continue
            # Movimientos menores que la décima parte del desvío no explican nada: no se cuentan.
            contra = sorted((j for j in atipicos if j != k and desvios[j] * d < 0 and abs(desvios[j]) >= .1 * abs(d)),
                            key=lambda j: -abs(desvios[j]))
            cubierto = sum(abs(desvios[j]) for j in contra)
            if contra and cubierto >= COBERTURA_COMPENSACION * abs(d):
                hijos[k].setdefault('compensacion', {})[str(b)] = dict(
                    periodo_previo=a, crecimiento_total=ritmo, desvio=d, cobertura=min(1.0, cubierto / abs(d)),
                    componentes=[dict(etiqueta=hijos[j]['etiqueta'], cambio=vb[j] - va[j], desvio=desvios[j])
                                 for j in contra[:3]],
                    celda_total=referencia(padre, por[b][1]))


def preparar(series):
    """Enriquece series locales; devuelve cierres verificados y relaciones con evidencia."""
    grupos = defaultdict(list)
    for s in series:
        s['ficha'] = dict(concepto=s['etiqueta'], ambito=s.get('ambito'), unidad=s.get('unidad'),
                          periodos=s['periodos'], archivo=s['archivo'], hoja=s['hoja'],
                          cuadro=s['cuadro'], celdas=s['celdas'], certeza='estructura_leida',
                          limites='El ámbito y la unidad se conservan cuando están explícitos; no acreditan comparabilidad externa.')
        grupos[(s['archivo'], s['hoja'], s['cuadro'])].append(s)
    cierres = []
    sin_comprobar = []
    candidatas = corroboradas = 0
    pocos_periodos = 0
    # Relaciones con algún período que incluye un dato no publicado («<5», «<0,1»): las que cierran (o no
    # tienen otros períodos para comprobar) y las que no cierran en los períodos comprobables.
    no_publicados_sin_comprobar = no_publicados_no_cierran = 0
    marcas = {}  # marca real encontrada → «suprimido» o «menor»
    leidas = []  # por cuadro: (padre, hijos, origen, pruebas, sin_dato)
    for filas in grupos.values():
        leidas.append([])
        for padre, hijos, origen in relaciones_cuadro(filas):
            candidatas += 1
            mapas = [mapa_periodos(h) for h in hijos]
            pruebas = []
            sin_dato = []
            con_no_publicados = False
            for periodo, i in mapa_periodos(padre).items():
                if any(periodo not in m for m in mapas):
                    continue
                jotas = [m[periodo] for m in mapas]
                vs = [numero(h['valores'][j]) for h, j in zip(hijos, jotas)]
                total = numero(padre['valores'][i])
                if total is None or any(v is None for v in vs):
                    sin_dato.append((periodo, i))
                    for v in [padre['valores'][i]] + [h['valores'][j] for h, j in zip(hijos, jotas)]:
                        if es_no_publicado(v):
                            con_no_publicados = True
                            marcas.setdefault(str(v).strip(), 'suprimido' if es_suprimido(v) else 'menor')
                    continue
                # Razones relativas para que la evidencia sobreviva a pesos/millones.
                ok = abs(total-sum(vs)) <= 1e-9 + .001 * max(abs(total), abs(sum(vs)))
                pruebas.append((periodo, i, jotas, vs, total, ok))
            if con_no_publicados:
                if any(not p[-1] for p in pruebas):
                    no_publicados_no_cierran += 1
                else:
                    no_publicados_sin_comprobar += 1
            leidas[-1].append((padre, hijos, origen, pruebas, sin_dato))
    # Series cortas (2 o 3 períodos): las corrobora la misma relación cerrando en otras hojas o cuadros, contada
    # como en la conciliación (una vez por relación, sin períodos insignificantes ni diferencias de redondeo).
    unicas = {}
    for cuadro in leidas:
        for p, h, o, _, _ in cuadro:
            unicas.setdefault(clave_relacion(p, h), estadistica_repeticion(firma_relacion(p, h, o), pruebas_relacion(p, h)))
    orden = list(unicas)
    repetidas = {orden[k] for k in corroboradas_por_repeticion([unicas[c] for c in orden])}
    por_repeticion = set()
    for cuadro in leidas:
        relaciones = []
        for padre, hijos, origen, pruebas, sin_dato in cuadro:
            repetida = False
            if not relacion_corroborada(sum(p[-1] for p in pruebas), len(pruebas)):
                if clave_relacion(padre, hijos) not in repetidas:
                    if len(pruebas) < 4:
                        pocos_periodos += 1
                    continue
                repetida = True
                por_repeticion.add(clave_relacion(padre, hijos))
            corroboradas += 1
            relaciones.append((padre, hijos, pruebas, repetida))
            _compensaciones(padre, hijos, pruebas)
            # Un período con «s/d» o vacío en el total o en un componente no se pudo comprobar: se dice.
            for periodo, i in sin_dato:
                sin_comprobar.append(dict(archivo=padre['archivo'], hoja=padre['hoja'], cuadro=padre['cuadro'],
                                          concepto=padre['etiqueta'], periodo=_rotulo_periodo(padre['periodos'][i], periodo),
                                          total=referencia(padre, i)))
            for periodo, i, js, vs, total, ok in pruebas:
                if ok:
                    cierres.append(dict(archivo=padre['archivo'], hoja=padre['hoja'], cuadro=padre['cuadro'],
                                        periodo=periodo, origen=origen, total=referencia(padre, i),
                                        componentes=[referencia(h,j) for h,j in zip(hijos,js)],
                                        diferencia=total-sum(vs)))
            # Padre y único hijo efectivo: demostrar identidad en TODOS los períodos comparables.
            if len(pruebas) == len(mapa_periodos(padre)) and all(p[-1] for p in pruebas):
                for idx, hijo in enumerate(hijos):
                    if all(abs(p[4]-p[3][idx]) <= 1e-9 + 1e-8*abs(p[4]) and
                           all(v == 0 for k,v in enumerate(p[3]) if k != idx) for p in pruebas):
                        for periodo,i,js,vs,total,ok in pruebas:
                            clave = '|'.join(sorted([referencia(padre,i),referencia(hijo,js[idx])]))
                            padre.setdefault('equivalencias', {})[str(periodo)] = clave
                            hijo.setdefault('equivalencias', {})[str(periodo)] = clave
        # El denominador debe ser un total del mismo cuadro y una relación comprobada.
        def descendientes(s, visitados):
            if id(s) in visitados:
                return []
            visitados.add(id(s))
            hijos = [h for p,hs,_,_ in relaciones if p is s for h in hs]
            return hijos + [d for h in hijos for d in descendientes(h,visitados)]
        for padre,hijos,pruebas,repetida in relaciones:
            if not es_total(padre):
                continue
            for s in descendientes(padre,set()):
                # No inferir materialidad entre unidades distintas.
                if s.get('unidad') != padre.get('unidad') or not s.get('unidad'):
                    continue
                mapa=mapa_periodos(s)
                for periodo,i,js,vs,total,ok in pruebas:
                    if periodo in mapa and total > 0:
                        valor=numero(s['valores'][mapa[periodo]])
                        if valor is not None:
                            orden = sorted(mapa)
                            posicion = orden.index(periodo)
                            vecinos = [numero(s['valores'][mapa[orden[k]]]) for k in (posicion-1, posicion+1) if 0 <= k < len(orden)]
                            vecinos = [v for v in vecinos if v is not None]
                            desvio = abs(valor - sum(vecinos)/len(vecinos)) if vecinos else abs(valor)
                            s.setdefault('materialidad', {})[str(periodo)] = dict(
                                porcentaje_total=100*abs(valor)/total,
                                porcentaje_desvio=100*desvio/total,
                                porcentaje_revision=100*max(abs(valor), desvio)/total, total=total,
                                celda_total=referencia(padre,i), unidad=s['unidad'],
                                base='Total del mismo cuadro, relación corroborada ' +
                                     ('en otras hojas o cuadros' if repetida else 'entre períodos'))
    motivo = None
    if not cierres:
        # Un control que no corrió no se informa como «0 verificados»: se dice por qué.
        if not series:
            motivo = 'no se identificaron series por período en las que buscar totales y componentes'
        elif no_publicados_no_cierran:
            motivo = ('los totales no cierran con sus componentes en los períodos que se pueden comprobar; los demás '
                      f'incluyen {_no_publicados(marcas)}')
        elif no_publicados_sin_comprobar:
            motivo = f'el total incluye {_no_publicados(marcas)}: sin esos valores el cierre no se puede comprobar'
        elif not candidatas and any(s.get('total_en_otra_columna') for s in series):
            motivo = ('hay filas «Total» en una columna de rótulos que no es la primera (bloques apilados, por ejemplo '
                      'uno por indicador): no se armaron los cierres de cada bloque')
        elif not candidatas:
            motivo = 'no se identificó una fila de total con sus componentes dentro de un mismo cuadro'
        elif not corroboradas and pocos_periodos == candidatas:
            motivo = ('los totales identificados tienen menos de 4 períodos comparables con sus componentes, '
                      'el mínimo para corroborar la relación, y no se repiten cerrando en otras 3 hojas o cuadros del archivo')
        elif not corroboradas:
            motivo = 'los totales identificados no cierran con sus componentes en suficientes períodos para corroborar la relación'
    return dict(version=1, fichas=[s['ficha'] for s in series], cierres_verificados=cierres,
                cantidad_cierres=len(cierres), relaciones_candidatas=candidatas,
                relaciones_corroboradas_por_repeticion=len(por_repeticion),
                motivo_sin_cierres=motivo, cierres_sin_comprobar=sin_comprobar[:30],
                alcance='Cierres de relaciones estructurales corroboradas; no certifican todo el archivo.')


def _lista_filas(filas):
    filas = sorted(filas)
    if len(filas) == 1:
        return f"la fila {filas[0]}"
    return "las filas " + ", ".join(map(str, filas[:-1])) + f" y {filas[-1]}"


def totales_separados(bloques, series, cierres):
    """Totales que filas vacías o sin cifras separan de sus componentes y cuyo cierre no se comprobó.

    El lector une un «Total» suelto con las filas de arriba cuando sólo lo separan filas sin datos; si
    aun así el cierre no se corrobora, o si el total quedó solo (arriba hay un bloque ya cerrado), no
    se informa como verificado: se declara al comienzo del informe, con las filas que lo separan.
    """
    salida = []
    con_series = {(s["archivo"], s["hoja"], s["cuadro"]) for s in series}
    verificadas = set()
    for c in cierres:
        m = re.match(r"^(.*)!([A-Z]+)(\d+)$", str(c.get("total") or ""))
        if m:
            verificadas.add((c.get("archivo"), m.group(1), int(m.group(3))))
    for b in bloques:
        t = b.get("total_separado")
        if not t:
            continue
        fila = t["fila_total"]
        if (b.get("archivo"), b.get("hoja"), fila) in verificadas:
            continue
        rotulo = t.get("rotulo") or "Total"
        sin_datos = t.get("filas_sin_datos") or []
        if t.get("unido"):
            if (b.get("archivo"), b.get("hoja"), b.get("bloque")) not in con_series:
                continue  # cuadro sin períodos: el total de columna lo controla otra regla sobre las filas unidas
            donde = f"filas {t['filas'][0]}–{t['filas'][1]}"
            motivo = (f"el cuadro está separado por filas vacías o sin datos ({_lista_filas(sin_datos)}); el total se "
                      "unió a las filas de arriba, pero su cierre con los componentes no se pudo corroborar")
        else:
            donde = f"fila {fila}"
            motivo = ("total separado de sus componentes por filas vacías"
                      + (f" o sin datos ({_lista_filas(sin_datos)})" if sin_datos else "")
                      + ": no se armó su cierre")
        salida.append(dict(archivo=b.get("archivo"), hoja=b.get("hoja"), cuadro=b.get("bloque"), concepto=rotulo,
                           donde=f"cierre de «{rotulo}» en {donde} de «{b.get('hoja')}»", fila_total=fila,
                           filas_sin_datos=sin_datos, motivo=motivo))
    return salida[:30]


def enriquecer(hallazgos, series):
    por_celda={(s['archivo'],s['hoja'],c):s for s in series for c in s['celdas']}
    for h in hallazgos:
        e=h.get('evidencia') or {}
        s=por_celda.get((e.get('archivo_origen'),e.get('hoja'),e.get('celda')))
        if not s:
            continue
        e['ficha_serie']=s['ficha']
        e['materialidad']=(s.get('materialidad') or {}).get(str(e.get('periodo')))
        compensacion=(s.get('compensacion') or {}).get(str(e.get('periodo')))
        if compensacion:
            e['compensacion']=compensacion
        # Conservar la agrupación que el control ya estableció (misma causa en varias señales).
        e['grupo_relacion']=(s.get('equivalencias') or {}).get(str(e.get('periodo'))) or e.get('grupo_relacion')
        e['rareza']={'factor_escala':e.get('factor_escala'), 'regla':e.get('regla')}
        independientes=[r for r in e.get('conciliaciones',[]) if r.get('regla') in {'conciliacion_aritmetica','poblacion_implicita'}]
        e['corroboracion_independiente']=bool(independientes)
        e['confianza_revision']='corroborada' if independientes else 'patron_a_verificar'
        e['politica_prioridad']='v3'
    return hallazgos
