"""Sugerencias: identidad real, permisos, persistencia y exportación segura."""
import csv
import io
from uuid import uuid4

import models
from routers import sugerencias

pytest_plugins = ["tests.test_ejemplos_zip"]


def preparar(flujo):
    client, factory, actual = flujo
    client.app.include_router(sugerencias.router, prefix="/api")
    return client, factory, actual


def payload(**extra):
    return {"pantalla": "proyecto-ia", "texto": "Quisiera que se vea el siguiente paso.",
            "solicitud_id": str(uuid4()), **extra}


def test_identidad_servidor_persistencia_y_reintento(flujo):
    client, factory, actual = preparar(flujo)
    data = payload(nombre="Nombre falso", usuario_id=4)
    res = client.post('/api/sugerencias', json=data)
    assert res.status_code == 201
    assert res.json()['nombre'] == 'Usuario 1'
    assert res.json()['usuario_id'] == 1
    assert client.post('/api/sugerencias', json=data).json()['id'] == res.json()['id']
    assert client.post('/api/sugerencias', json={**data, 'texto': 'Distinto'}).status_code == 409
    with factory() as db:
        assert db.query(models.SugerenciaPantalla).count() == 1
        assert db.query(models.Usuario).count() == 4
        assert db.query(models.SugerenciaPantalla).one().texto == data['texto']


def test_alumnos_pueden_enviar_pero_no_ver_ni_exportar_ajenos(flujo):
    client, factory, actual = preparar(flujo)
    for user_id in (1, 2, 3):
        actual['id'] = user_id
        assert client.post('/api/sugerencias', json=payload()).status_code == 201
        assert client.get('/api/sugerencias').status_code == 403
        assert client.get('/api/sugerencias/exportar').status_code == 403
    actual['id'] = 4
    assert client.get('/api/sugerencias').json()['total'] == 3
    assert client.get('/api/sugerencias?usuario_id=2').json()['total'] == 1
    assert client.get('/api/sugerencias?pantalla=inicio').json()['total'] == 0
    assert len(client.get('/api/sugerencias?limit=1&offset=1').json()['items']) == 1


def test_vacios_pantallas_desconocidas_y_limites(flujo):
    client, _, _ = preparar(flujo)
    for change in ({'texto': '  '}, {'texto': 'x'*5001}, {'pantalla': 'inventada'}, {'texto': 'a\x00b'}, {'solicitud_id':'bad'}):
        assert client.post('/api/sugerencias', json=payload(**change)).status_code == 422


def test_csv_filtros_tildes_multilinea_y_formula(flujo):
    client, _, actual = preparar(flujo)
    texto = '=HYPERLINK("https://example.test")\nQuiero más claridad; gracias'
    assert client.post('/api/sugerencias', json=payload(texto=texto)).status_code == 201
    assert client.post('/api/sugerencias', json=payload(pantalla='inicio')).status_code == 201
    actual['id'] = 4
    res = client.get('/api/sugerencias/exportar?pantalla=proyecto-ia')
    assert res.status_code == 200 and 'text/csv' in res.headers['content-type']
    rows = list(csv.reader(io.StringIO(res.content.decode('utf-8-sig')), delimiter=';'))
    assert len(rows) == 2 and rows[1][3] == "'" + texto
    assert rows[1][1] == 'Usuario 1'


def test_propias_y_edicion_no_permiten_acceso_ajeno(flujo):
    client, factory, actual = preparar(flujo)
    item=client.post('/api/sugerencias',json=payload()).json()
    actual['id']=2
    assert client.get('/api/sugerencias/mias').json()['total']==0
    assert client.patch('/api/sugerencias/'+str(item['id']),json={'texto':'Otro','texto_anterior':item['texto']}).status_code==404
    actual['id']=1
    assert client.get('/api/sugerencias/mias').json()['items'][0]['id']==item['id']
    cambio={'texto':'Que indique cuánto falta y cómo cerrar.','texto_anterior':item['texto']}
    url='/api/sugerencias/'+str(item['id'])
    assert client.patch(url,json=cambio).json()['texto']==cambio['texto']
    assert client.patch(url,json=cambio).status_code==200
    assert client.patch(url,json={**cambio,'texto':'Edición de otra ventana'}).status_code==409
    assert client.get('/api/sugerencias/mias').json()['items'][0]['texto']==cambio['texto']
    with factory() as db:
        events=db.query(models.ActivityEvent).filter_by(accion='sugerencia_corregida').all()
        assert len(events)==1
        assert events[0].metadata_evento['antes']==item['texto']
    actual['id']=4
    assert client.get('/api/sugerencias').json()['items'][0]['texto']==cambio['texto']


def test_edicion_rechaza_vacio_y_exceso_sin_cambiar_original(flujo):
    client, _, _ = preparar(flujo)
    item=client.post('/api/sugerencias',json=payload()).json()
    for texto in ['   ','x'*5001,'a\x00b']:
        assert client.patch('/api/sugerencias/'+str(item['id']),json={'texto':texto,'texto_anterior':item['texto']}).status_code==422
    assert client.get('/api/sugerencias/mias').json()['items'][0]['texto']==item['texto']
