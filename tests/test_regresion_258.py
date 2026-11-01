"""Casos del informe 258: conservar señales, limitar afirmaciones y separar piezas."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from services.casos_revision import prioridad
from services.reportes.markdown import render_reporte_markdown
from services.semantica_excel import presentar_cobertura, validar
from tests.test_controles_tabulares import analizar_libro, caso


def test_vacio_entre_ceros_media_y_hueco_material_sigue_alta():
    for valores, nivel in [([0, 0, 0, None, 0, 0, 0], 'media'), ([100, 110, 120, None, 140, 150, 160], 'alta')]:
        hallazgos = analizar_libro(caso(valores))
        h = next(x for x in hallazgos if x['evidencia']['regla'] == 'vacio_interior')
        assert prioridad(h) == nivel and h['severidad'] == nivel
        assert h['evidencia']['puntaje_prioridad'] == (50 if nivel == 'media' else 120)
    assert analizar_libro(caso([0] * 7)) == []


def evidencia():
    return [dict(id='a', texto='Desarrollo e integración', celda='A13', hoja='Según categorías'),
            dict(id='b', texto='Cuidado y educación', celda='A36', hoja='La Rioja')]


def hipotesis(texto):
    return dict(tipo='taxonomia', referencias=['a', 'b'], explicacion=texto, alternativa='La clasificación puede ser distinta.')


def test_rechaza_etiqueta_inventada_aunque_los_ids_existan():
    h = hipotesis("La etiqueta 'Educación' (celda A13) difiere de 'Cuidado y educación'.")
    with pytest.raises(ValueError, match='Discordancia'):
        validar([h], {'elementos': evidencia()})
    h['explicacion'] = "Comparar 'Desarrollo e integración' (celda A13) con 'Cuidado y educación' (celda A36)."
    assert validar([h], {'elementos': evidencia()})
    h['explicacion'] = "Comparar 'Cuidado y educación' (celda A13) con 'Desarrollo e integración' (celda A36)."
    with pytest.raises(ValueError, match='Discordancia'):
        validar([h], {'elementos': evidencia()})


def test_historico_se_filtra_sin_mutar_registro_original():
    h = {**hipotesis("'Educación' (celda A13) difiere de la otra categoría."), 'id': 'sem-2', 'evidencia_comparativa': evidencia()}
    cov = {'exploracion_semantica': {'titulo_estado': 'Exploración completada', 'hallazgos': [h]}}
    antes = deepcopy(cov)
    presentada = presentar_cobertura(cov)['exploracion_semantica']
    assert cov == antes
    assert presentada['hallazgos'] == []
    assert presentada['descartados_por_referencia'][0]['id'] == 'sem-2'
    assert presentada['resultado'] == 'sin_conclusion'


def test_chaco_patron_se_conserva_sin_afirmar_causa():
    from services.controles_excel.identidades import analizar
    a = dict(archivo='ejemplo.xlsx', hoja='Chaco', cuadro=1, etiqueta='GIPI', periodos=list(range(2016, 2023)), valores=[54.07, 63, 135, 183, 201, 426, 667], celdas=['B19','C19','D19','E19','F19','G19','H19'])
    b = {**a, 'cuadro': 2, 'etiqueta': 'Ayuda directa', 'valores': [54.44, 63, 135, 183, 201, 426, 667], 'celdas': ['B32','C32','D32','E32','F32','G32','H32']}
    h = analizar([a,b])[0]
    assert '6 de 7' in h['descripcion']
    assert 'quedó sin actualizar' not in h['descripcion']
    assert 'si ambos conceptos deben coincidir' in h['pregunta_institucional']
    b['valores'] = a['valores'][:]
    assert analizar([a,b]) == []


def test_ejecutivo_no_incluye_anexo_y_muestra_cruce(monkeypatch):
    from services.reportes import markdown as md
    monkeypatch.setattr(md, '_detalle_reporte_markdown', lambda *a: 'EVIDENCIA EXCLUSIVA DEL ANEXO')
    informe = SimpleNamespace(id=258, datos=[], saneamiento={}, devolucion=SimpleNamespace(cobertura={}))
    h = dict(lente='ajedrecista', modo='control_tabular', severidad='alta', descripcion='Dato para revisar', evidencia=dict(regla='escala_extremo', factor_escala=8.3, hoja='Corrientes', celda='H7', conciliaciones=[dict(regla='poblacion_implicita', poblacion_implicita=1195841, poblacion_vecinos=[120934], celdas_participantes=['Corrientes!H7','Corrientes!H6'])]))
    ejecutivo = render_reporte_markdown(informe, [h], True, True, pieza='ejecutivo')
    anexo = render_reporte_markdown(informe, [h], True, True, pieza='anexo')
    assert 'EVIDENCIA EXCLUSIVA DEL ANEXO' not in ejecutivo
    assert '1.195.841' in ejecutivo and '120.934' in ejecutivo
    assert anexo.startswith('# Anexo técnico') and 'EVIDENCIA EXCLUSIVA DEL ANEXO' in anexo
    assert 'no mide la exactitud' in ejecutivo


pytest_plugins = ['tests.test_ejemplos_zip']


def test_descargas_http_separadas_y_permisos(flujo):
    from io import BytesIO

    from pypdf import PdfReader

    from routers import informes
    from services import jobs
    from tests.test_ejemplos_zip import cargar

    client, _, actual = flujo
    client.app.include_router(informes.router, prefix='/api')
    response = cargar(client)
    informe_id = response['informe_id']
    assert jobs._process_one()
    url = f'/api/informes/{informe_id}/reporte'
    for pieza, titulo in [('ejecutivo', 'Informe de revisión'), ('anexo', 'Anexo técnico')]:
        out = client.post(url, json={'formato': 'pdf', 'pieza': pieza})
        assert out.status_code == 200, out.text
        assert f'reporte-{pieza}-' in out.headers['content-disposition']
        pdf = PdfReader(BytesIO(out.content))
        texto = '\n'.join(p.extract_text() for p in pdf.pages)
        assert titulo in texto
        if pieza == 'ejecutivo':
            assert 'Registro técnico de la corrida' not in texto
        else:
            assert 'Registro técnico de la corrida' in texto
    assert client.post(url, json={'pieza': 'desconocida'}).status_code == 422
    revision = client.get(f'/api/informes/{informe_id}/informe-revision.pdf')
    assert revision.status_code == 200
    assert 'informe-revision-' in revision.headers['content-disposition']
    assert 'Informe de revisión' in PdfReader(BytesIO(revision.content)).pages[0].extract_text()
    actual['id'] = 2
    assert client.get(f'/api/informes/{informe_id}/informe-revision.pdf').status_code == 403
    assert client.post(url, json={'pieza': 'anexo'}).status_code == 403
