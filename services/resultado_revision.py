"""Una lectura de alcance compartida por informes breves y comprobantes."""
from collections import defaultdict

from services.carga_archivos import fila_sin_separar, rotulos_poco_confiables
from services.controles_excel.lectura import lineas_pdf


def separar_datos(datos):
    grupos=defaultdict(list)
    seguros=[]
    for f in datos:
        if str(f.get('extraccion_pdf') or '').startswith('tabla'):
            grupos[(f.get('archivo_origen'),f.get('pagina_pdf'),f.get('tabla_pdf'))].append(f)
        else:
            seguros.append(f)
    excluidos=[]
    for clave,filas in grupos.items():
        if sum(fila_sin_separar(f) for f in filas) >= .5*len(filas) or rotulos_poco_confiables(filas[0]):
            excluidos.append(dict(archivo=clave[0],pagina=clave[1],tabla=clave[2],filas=len(filas),
                                 motivo='Encabezados o columnas no recuperados con fiabilidad'))
        else:
            seguros.extend(filas)
    return seguros,excluidos


ESTADOS_LEGIBLES = {
    'CON_SENALES_COMUNICABLES': 'CON SEÑALES PARA REVISAR',
    'SIN_SENALES_COMUNICABLES': 'SIN SEÑALES COMUNICABLES',
    'COBERTURA_PARCIAL': 'COBERTURA PARCIAL',
    'PREGUNTA_NO_EVALUADA': 'PREGUNTA NO EVALUADA',
}


def alcance(informe):
    from services.reportes.registro import _pdf_ajustado

    meta=getattr(informe,'saneamiento',None) or {}
    cov=getattr(getattr(informe,'devolucion',None),'cobertura',None) or {}
    # Una tabla chica leída completa no es una lectura insuficiente: el umbral de filas no la descarta.
    pdf=_pdf_ajustado(cov.get('pdf') or meta.get('pdf') or {})
    excel=(cov.get('excel') or meta.get('excel') or {}).get('lectura') or {}
    estado=ESTADOS_LEGIBLES.get(cov.get('estado'), cov.get('estado')) or 'ALCANCE ACOTADO'
    if pdf.get('estado')=='insuficiente':
        estado='COBERTURA DE LECTURA INSUFICIENTE'
    elif pdf.get('estado')=='parcial' or excel.get('estado') in {'parcial','insuficiente'}:
        estado='COBERTURA DE LECTURA PARCIAL'
    return dict(estado=estado,pdf=pdf,excel=excel,detalle_pdf=lineas_pdf(pdf),
                estructura=meta.get('estructura_revision') or {})
