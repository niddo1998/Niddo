"""El vecino informa un pago y tiene que poder ver en qué quedó.

El endpoint de listado existía desde v6 y la pantalla nunca lo llamaba, así que
el aviso salía del navegador y no volvía nunca. Estos tests cubren las dos
mitades: que el listado sea suyo y sólo suyo, y que el estado que el admin
escribe sea uno de los que la pantalla del vecino sabe mostrar.
"""

import pytest


def _aviso(base, vecino_id='vec-1', estado='pendiente'):
    base['avisos_pago'].append({
        'id': f'aviso-{vecino_id}-{estado}', 'vecino_id': vecino_id,
        'consorcio_id': 'cons-1', 'unidad_id': 'uf-1', 'monto': 100,
        'fecha_pago': '2026-08-05', 'medio_pago': 'transferencia',
        'estado': estado, 'created_at': '2026-08-05T10:00:00+00:00',
    })


def test_lista_los_avisos_propios(client, base):
    _aviso(base)
    r = client.get('/api/avisos_pago')
    assert r.status_code == 200
    assert [a['estado'] for a in r.get_json()] == ['pendiente']


def test_no_lista_los_avisos_de_otro_vecino(client, base):
    _aviso(base, vecino_id='vec-2')
    r = client.get('/api/avisos_pago')
    assert r.get_json() == []


def test_el_estado_llega_hasta_el_vecino(client, base):
    _aviso(base, estado='aceptado')
    assert r_estado(client) == 'aceptado'


def r_estado(client):
    return client.get('/api/avisos_pago').get_json()[0]['estado']


# ── El admin escribe el estado ────────────────────────────────────────────────

@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


@pytest.mark.parametrize('estado', ['aceptado', 'rechazado', 'pendiente'])
def test_el_admin_puede_poner_los_estados_del_vocabulario(admin, base, estado):
    _aviso(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente',
                  json={'estado': estado})
    assert r.status_code == 200
    assert base['avisos_pago'][0]['estado'] == estado


@pytest.mark.parametrize('estado', ['revisando', '', None, 'ACEPTADO'])
def test_un_estado_de_fantasia_se_rechaza(admin, base, estado):
    _aviso(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente',
                  json={'estado': estado})
    assert r.status_code == 400
    # Lo que importa no es el status sino que la fila no se haya movido: un 400
    # después de escribir seguiría estando roto.
    assert base['avisos_pago'][0]['estado'] == 'pendiente'
