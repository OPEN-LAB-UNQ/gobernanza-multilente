"""Resumen de lectura anual. Prioriza la presentación sin eliminar evidencia."""
from __future__ import annotations

from collections import Counter

from services import plural


def campo(h, nombre, defecto=None):
    return h.get(nombre, defecto) if isinstance(h, dict) else getattr(h, nombre, defecto)


def anual(h):
    ev = campo(h, 'evidencia', {}) or {}
    return campo(h, 'lente') == 'cronista' and bool(ev.get('requiere_contexto_anual'))


def intensidad(h):
    ev = campo(h, 'evidencia', {}) or {}
    return float(ev.get('ratio_maximo_vs_movimiento_tipico') or ev.get('ratio_vs_movimiento_tipico') or 0)


def resumen(hallazgos):
    agrupadas = [h for h in hallazgos if anual(h)]
    anuales = [d for h in agrupadas for d in ((campo(h, 'evidencia', {}) or {}).get('detalle_contexto') or [h])]
    if not anuales:
        return {}
    periodos = Counter(str((campo(h, 'evidencia', {}) or {}).get('periodo') or 'sin período') for h in anuales)
    hojas = {campo(h, 'evidencia', {}).get('hoja') for h in anuales}
    referencias = []
    for h in sorted(anuales, key=intensidad, reverse=True)[:5]:
        ev = campo(h, 'evidencia', {}) or {}
        referencias.append({'hoja':ev.get('hoja'), 'cuadro':ev.get('bloque_excel'),
            'serie':ev.get('serie'), 'periodo':ev.get('periodo'), 'ratio':intensidad(h),
            'ubicaciones':ev.get('ubicaciones_excel', [])})
    return {'cantidad':len(anuales), 'otras_senales':len(hallazgos)-len(agrupadas), 'grupos_contexto':len(agrupadas),
        'hojas':len(hojas-{None}), 'periodos':dict(sorted(periodos.items())), 'referencias':referencias,
        'aclaracion':'Son variaciones temporales para contextualizar, no errores confirmados ni controles de fórmulas incumplidos.',
        'criterio':'Las referencias iniciales se ordenan por salto relativo al movimiento histórico de cada serie. No comparan importes de distintas hojas ni acreditan gravedad institucional. Todos los hallazgos permanecen en el detalle.'}


def lineas_markdown(hallazgos):
    r = resumen(hallazgos)
    if not r:
        return []
    return ['## Cómo leer las variaciones anuales', '',
        f"- **{plural.contar(r['cantidad'], 'señal temporal anual', 'señales temporales anuales')} en {plural.contar(r['hojas'], 'hoja')}; "
        f"{plural.contar(r['otras_senales'], 'señal', 'señales')} de otros controles.**",
        '- '+r['aclaracion'],
        '- **Año de la variación:** '+ '; '.join(f"{p}: {plural.contar(n, 'señal', 'señales')}" for p,n in r['periodos'].items())+'.',
        '- Revisar primero el contexto compartido por período: unidad, base de comparación, cobertura y metodología. En moneda corriente, distinguir crecimiento nominal y real. Después revisar las celdas particulares.',
        '- '+r['criterio'], '', '**Referencias para empezar la lectura:**', '',
        *[f"- {x['hoja'] or 'Archivo'} · cuadro {x['cuadro'] or '-'} · {x['periodo']}: {x['serie']}. Ratio respecto del movimiento histórico: {x['ratio']:g}." for x in r['referencias']], '']
