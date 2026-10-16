"""Cada reclamo es una conversación entre el vecino y la administración.

Antes había una sola `respuesta_admin` que se pisaba y el vecino no podía
contestar. Y contestar no dejaba ninguna marca: el administrador no veía en la
lista qué reclamos ya había respondido.
"""

import pytest


def _cliente(app_modulo, user):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = user
    return c


@pytest.fixture
def mails(monkeypatch, app_modulo):
    enviados = []
    monkeypatch.setattr(app_modulo, '_enviar_mail',
                        lambda dest, asunto, html: enviados.append((dest, asunto, html)))
    return enviados


@pytest.fixture
def admin(base, app_modulo, mails):
    return _cliente(app_modulo, {'sub': 'auth0|admin', 'email': 'admin@test',
                                 'name': 'Admin', 'role': 'admin'})


@pytest.fixture
def vecino(client):
    return client


@pytest.fixture
def reclamos(base):
    base['reclamos'] = [
        {'id': 'rec-1', 'consorcio_id': 'cons-1', 'vecino_id': 'vec-1',
         'titulo': 'Pérdida', 'descripcion': 'Gotea', 'categoria': 'plomeria',
         'estado': 'activo', 'respuesta_admin': None,
         'created_at': '2026-08-01T10:00:00+00:00', 'updated_at': '2026-08-01T10:00:00+00:00'},
        {'id': 'rec-2', 'consorcio_id': 'cons-2', 'vecino_id': 'vec-2',
         'titulo': 'Ajeno', 'descripcion': 'x', 'categoria': 'otro', 'estado': 'activo',
         'created_at': '2026-08-01T10:00:00+00:00', 'updated_at': '2026-08-01T10:00:00+00:00'},
    ]
    base['reclamo_mensajes'] = []
    return base


def test_contestar_lo_marca_como_respondido_y_en_proceso(admin, reclamos, mails):
    r = admin.post('/api/admin/reclamos/rec-1/mensajes', json={'cuerpo': 'Mañana va el plomero'})
    assert r.status_code == 201
    fila = reclamos['reclamos'][0]
    assert fila['estado'] == 'en_proceso'
    assert fila['respuesta_admin'] == 'Mañana va el plomero'
    lista = admin.get('/api/admin/reclamos').get_json()
    assert lista[0]['respondido'] is True
    assert lista[0]['ultimo_autor'] == 'admin'
    assert mails and 'uno@test' in mails[0][0]


def test_el_vecino_ve_la_respuesta_como_nueva_hasta_abrirla(admin, vecino, reclamos):
    admin.post('/api/admin/reclamos/rec-1/mensajes', json={'cuerpo': 'Hola'})
    assert vecino.get('/api/reclamos').get_json()[0]['sin_leer'] == 1
    conv = vecino.get('/api/reclamos/rec-1/mensajes').get_json()
    assert [m['cuerpo'] for m in conv] == ['Hola']
    assert vecino.get('/api/reclamos').get_json()[0]['sin_leer'] == 0


def test_el_vecino_puede_contestar(admin, vecino, reclamos):
    admin.post('/api/admin/reclamos/rec-1/mensajes', json={'cuerpo': '¿Sigue goteando?'})
    r = vecino.post('/api/reclamos/rec-1/mensajes', json={'cuerpo': 'Sí, más que antes'})
    assert r.status_code == 201
    lista = admin.get('/api/admin/reclamos').get_json()
    assert lista[0]['ultimo_autor'] == 'vecino'
    assert lista[0]['sin_leer'] == 1


def test_contestar_uno_resuelto_lo_reabre(admin, vecino, reclamos):
    admin.post('/api/admin/reclamos/rec-1/mensajes', json={'cuerpo': 'Listo', 'estado': 'resuelto'})
    assert reclamos['reclamos'][0]['estado'] == 'resuelto'
    vecino.post('/api/reclamos/rec-1/mensajes', json={'cuerpo': 'No, sigue igual'})
    assert reclamos['reclamos'][0]['estado'] == 'en_proceso'


def test_uno_cerrado_no_se_contesta(vecino, reclamos):
    reclamos['reclamos'][0]['estado'] = 'cerrado'
    r = vecino.post('/api/reclamos/rec-1/mensajes', json={'cuerpo': 'hola'})
    assert r.status_code == 409


def test_resolver_sin_decir_que_se_hizo_no_se_puede(admin, reclamos):
    r = admin.post('/api/admin/reclamos/rec-1/mensajes', json={'estado': 'resuelto'})
    assert r.status_code == 400
    assert reclamos['reclamos'][0]['estado'] == 'activo'


def test_cambiar_solo_el_estado_se_puede(admin, reclamos):
    r = admin.post('/api/admin/reclamos/rec-1/mensajes', json={'estado': 'en_proceso'})
    assert r.status_code == 200
    assert reclamos['reclamos'][0]['estado'] == 'en_proceso'
    assert reclamos['reclamo_mensajes'] == []


def test_la_conversacion_ajena_no_se_lee_ni_se_escribe(admin, vecino, reclamos):
    assert vecino.get('/api/reclamos/rec-2/mensajes').status_code == 404
    assert vecino.post('/api/reclamos/rec-2/mensajes', json={'cuerpo': 'x'}).status_code == 404
    assert admin.get('/api/admin/reclamos/rec-2/mensajes').status_code == 404
    assert admin.post('/api/admin/reclamos/rec-2/mensajes', json={'cuerpo': 'x'}).status_code == 404


def test_la_respuesta_por_el_camino_viejo_entra_a_la_conversacion(admin, reclamos):
    admin.put('/api/admin/reclamos/rec-1', json={'estado': 'en_proceso', 'respuesta_admin': 'Ya va'})
    assert [m['cuerpo'] for m in reclamos['reclamo_mensajes']] == ['Ya va']
