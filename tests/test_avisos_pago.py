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


@pytest.mark.parametrize('estado', ['rechazado', 'pendiente'])
def test_el_admin_puede_poner_los_estados_del_vocabulario(admin, base, estado):
    _aviso(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente',
                  json={'estado': estado})
    assert r.status_code == 200
    assert base['avisos_pago'][0]['estado'] == estado


# ── Aceptar salda la expensa ─────────────────────────────────────────────────
#
# Aceptar no es sólo cambiar una palabra: si el cobro sigue pendiente después
# de que el administrador dio el visto bueno, la deuda queda viva en las dos
# pantallas y el aviso no sirvió para nada.

def _cobro(base, cid='cons-1'):
    base['cobros'] = [{'id': 'cobro-x', 'consorcio_id': cid, 'unidad_id': 'uf-1',
                       'periodo': '2026-08', 'monto_base': 100, 'total': 100,
                       'estado': 'pendiente', 'fecha_vencimiento': '2026-08-10'}]
    return base['cobros'][0]


def test_aceptar_un_aviso_marca_pagado_su_cobro(admin, base):
    cobro = _cobro(base)
    _aviso(base)
    base['avisos_pago'][0]['cobro_id'] = 'cobro-x'
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente', json={'estado': 'aceptado'})
    assert r.status_code == 200
    assert cobro['estado'] == 'pagado'
    assert cobro['fecha_pago'] == '2026-08-05'   # la que declaró el vecino


def test_aceptar_sin_saber_qué_expensa_pide_elegirla(admin, base):
    """El vecino puede informar un pago suelto, sin cobro asociado."""
    _cobro(base)
    _aviso(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente', json={'estado': 'aceptado'})
    assert r.status_code == 400
    assert base['avisos_pago'][0]['estado'] == 'pendiente'


def test_el_admin_puede_imputar_el_pago_a_una_expensa(admin, base):
    cobro = _cobro(base)
    _aviso(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente',
                  json={'estado': 'aceptado', 'cobro_id': 'cobro-x'})
    assert r.status_code == 200
    assert base['avisos_pago'][0]['cobro_id'] == 'cobro-x'
    assert cobro['estado'] == 'pagado'


def test_no_se_puede_saldar_la_expensa_de_otro_edificio(admin, base):
    """El cobro llega por el body: sin el chequeo, saldaría deuda ajena."""
    cobro = _cobro(base, cid='cons-2')
    _aviso(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente',
                  json={'estado': 'aceptado', 'cobro_id': 'cobro-x'})
    assert r.status_code == 400
    assert cobro['estado'] == 'pendiente'


def test_un_cobro_ajeno_tampoco_deja_el_aviso_aceptado(admin, base):
    """El rechazo tiene que ser anterior a escribir nada.

    Si el aviso se aceptaba primero y el cobro se validaba después, el 400
    dejaba el aviso aceptado para siempre, apuntando a un cobro de otro
    edificio y sin ninguna expensa saldada.
    """
    _cobro(base, cid='cons-2')
    _aviso(base)
    admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente',
              json={'estado': 'aceptado', 'cobro_id': 'cobro-x'})
    assert base['avisos_pago'][0]['estado'] == 'pendiente'
    assert base['avisos_pago'][0].get('cobro_id') is None


# ── Desaceptar devuelve la deuda ─────────────────────────────────────────────

def _aceptado(base):
    cobro = _cobro(base)
    _aviso(base)
    base['avisos_pago'][0]['cobro_id'] = 'cobro-x'
    base['avisos_pago'][0]['estado'] = 'aceptado'
    cobro['estado'] = 'pagado'
    cobro['fecha_pago'] = '2026-08-05'
    return cobro


@pytest.mark.parametrize('estado', ['rechazado', 'pendiente'])
def test_desaceptar_devuelve_el_cobro_a_pendiente(admin, base, estado):
    """Aceptar es lo que saldó la expensa; deshacerlo tiene que deshacer eso.

    Sin esto, un pago aceptado por error borraba la deuda para siempre: el
    aviso volvía a rojo y el cobro se quedaba en pagado.
    """
    cobro = _aceptado(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente', json={'estado': estado})
    assert r.status_code == 200
    assert cobro['estado'] == 'pendiente'
    assert cobro['fecha_pago'] is None


def test_rechazar_un_aviso_que_nunca_se_acepto_no_toca_nada(admin, base):
    cobro = _cobro(base)
    cobro['estado'] = 'pagado'          # lo pagó por otra vía
    _aviso(base)
    base['avisos_pago'][0]['cobro_id'] = 'cobro-x'
    admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente', json={'estado': 'rechazado'})
    assert cobro['estado'] == 'pagado'


def test_rechazar_no_toca_la_deuda(admin, base):
    cobro = _cobro(base)
    _aviso(base)
    base['avisos_pago'][0]['cobro_id'] = 'cobro-x'
    admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente', json={'estado': 'rechazado'})
    assert cobro['estado'] == 'pendiente'


@pytest.mark.parametrize('estado', ['revisando', '', None, 'ACEPTADO'])
def test_un_estado_de_fantasia_se_rechaza(admin, base, estado):
    _aviso(base)
    r = admin.put('/api/admin/avisos-pago/aviso-vec-1-pendiente',
                  json={'estado': estado})
    assert r.status_code == 400
    # Lo que importa no es el status sino que la fila no se haya movido: un 400
    # después de escribir seguiría estando roto.
    assert base['avisos_pago'][0]['estado'] == 'pendiente'
