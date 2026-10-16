"""Los numeritos del menú y los avisos al celular.

Un badge cuenta lo que llegó desde la última vez que se entró a esa sección, y
entrar lo borra hasta la próxima novedad. Las solicitudes de alta y los pagos
informados son tareas: esos quedan hasta que se resuelven.
"""

import pytest


def _cliente(app_modulo, user):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = user
    return c


@pytest.fixture
def admin(base, app_modulo):
    base['administradores'][0]['created_at'] = '2026-01-01T00:00:00+00:00'
    return _cliente(app_modulo, {'sub': 'auth0|admin', 'email': 'admin@test',
                                 'name': 'Admin', 'role': 'admin'})


@pytest.fixture
def datos(base):
    base['vecinos'][0]['created_at'] = '2026-01-01T00:00:00+00:00'
    base['reclamos'] = [{'id': 'rec-1', 'consorcio_id': 'cons-1', 'vecino_id': 'vec-1',
                         'titulo': 'x', 'created_at': '2026-09-01T10:00:00+00:00'}]
    base['reclamo_mensajes'] = []
    base['mensajes'] = []
    base['comunicados'] = [{'id': 'com-1', 'consorcio_id': 'cons-1', 'titulo': 'Corte de agua',
                            'created_at': '2026-09-02T10:00:00+00:00'},
                           {'id': 'com-2', 'consorcio_id': 'cons-2', 'titulo': 'Ajeno',
                            'created_at': '2026-09-02T10:00:00+00:00'}]
    base['cobros'][0]['created_at'] = '2026-09-03T10:00:00+00:00'
    base['secciones_vistas'] = []
    base['push_suscripciones'] = []
    return base


def test_el_admin_ve_el_reclamo_nuevo(admin, datos):
    assert admin.get('/api/novedades').get_json()['reclamos'] == 1


def test_entrar_a_la_seccion_lo_borra(admin, datos):
    admin.post('/api/novedades/visto', json={'seccion': 'reclamos'})
    assert admin.get('/api/novedades').get_json()['reclamos'] == 0


def test_vuelve_a_aparecer_con_una_respuesta_nueva(admin, datos):
    admin.post('/api/novedades/visto', json={'seccion': 'reclamos'})
    datos['reclamo_mensajes'].append({'id': 'm1', 'reclamo_id': 'rec-1', 'autor': 'vecino',
                                      'created_at': '2999-01-01T00:00:00+00:00'})
    assert admin.get('/api/novedades').get_json()['reclamos'] == 1


def test_las_solicitudes_quedan_hasta_resolverse_y_dicen_de_que_consorcio(admin, datos):
    datos['vecinos'].append({'id': 'vec-9', 'estado_asociacion': 'pendiente',
                             'consorcio_solicitado_id': 'cons-1'})
    n = admin.get('/api/novedades').get_json()
    assert n['solicitudes'] == 1
    assert n['solicitudes_por_consorcio'] == {'cons-1': 1}
    # No hay "visto" que las borre: son trabajo pendiente.
    assert admin.post('/api/novedades/visto', json={'seccion': 'solicitudes'}).status_code == 400


def test_el_vecino_ve_su_comunicado_y_su_expensa(client, datos):
    n = client.get('/api/novedades').get_json()
    assert n['comunicados'] == 1          # el del otro edificio no cuenta
    assert n['expensas'] == 1


def test_el_vecino_ve_la_respuesta_a_su_reclamo(client, datos):
    datos['reclamo_mensajes'].append({'id': 'm1', 'reclamo_id': 'rec-1', 'autor': 'admin',
                                      'created_at': '2026-09-05T00:00:00+00:00'})
    assert client.get('/api/novedades').get_json()['reclamos'] == 1
    client.post('/api/novedades/visto', json={'seccion': 'reclamos'})
    assert client.get('/api/novedades').get_json()['reclamos'] == 0


# ── Push ──────────────────────────────────────────────────────────────────────

SUB = {'endpoint': 'https://fcm.googleapis.com/fcm/send/abc',
       'keys': {'p256dh': 'BPk', 'auth': 'xyz'}}


@pytest.fixture
def con_vapid(monkeypatch, app_modulo):
    monkeypatch.setattr(app_modulo, 'VAPID_PUBLIC_KEY', 'pub')
    monkeypatch.setattr(app_modulo, 'VAPID_PRIVATE_KEY', 'priv')
    enviados = []

    def falso(sub, datos):
        enviados.append((sub['endpoint'], datos))
        return 'borrar' if 'muerta' in sub['endpoint'] else True
    monkeypatch.setattr(app_modulo, '_enviar_push', falso)
    return enviados


def test_sin_claves_no_se_ofrece(client, datos):
    assert client.get('/api/push/clave').get_json()['disponible'] is False


def test_el_vecino_se_suscribe_y_recibe_la_respuesta(client, admin, datos, con_vapid):
    assert client.post('/api/push/suscribir', json={'suscripcion': SUB}).status_code == 201
    admin.post('/api/admin/reclamos/rec-1/mensajes', json={'cuerpo': 'Ya va el plomero'})
    assert len(con_vapid) == 1
    endpoint, datos_push = con_vapid[0]
    assert endpoint == SUB['endpoint']
    assert datos_push['cuerpo'] == 'Ya va el plomero'
    assert datos_push['url'].endswith('#reclamos')


def test_un_comunicado_le_llega_solo_al_edificio(client, admin, datos, con_vapid):
    client.post('/api/push/suscribir', json={'suscripcion': SUB})
    datos['push_suscripciones'].append({'id': 'ps-2', 'usuario_tipo': 'vecino', 'usuario_id': 'vec-2',
                                        'endpoint': 'https://x/otro', 'p256dh': 'a', 'auth': 'b'})
    admin.post('/api/admin/comunicados', json={'consorcio_id': 'cons-1', 'titulo': 'Hola', 'cuerpo': 'Texto'})
    assert [e for e, _ in con_vapid] == [SUB['endpoint']]


def test_la_suscripcion_muerta_se_borra(app_modulo, datos, con_vapid):
    datos['push_suscripciones'].append({'id': 'ps-1', 'usuario_tipo': 'vecino', 'usuario_id': 'vec-1',
                                        'endpoint': 'https://x/muerta', 'p256dh': 'a', 'auth': 'b'})
    app_modulo.push_a('vecino', ['vec-1'], 't', 'c')
    assert datos['push_suscripciones'] == []


def test_una_suscripcion_trucha_se_rechaza(client, datos):
    r = client.post('/api/push/suscribir', json={'suscripcion': {'endpoint': 'http://x', 'keys': {}}})
    assert r.status_code == 400
