"""Pagar la expensa con Mercado Pago.

Lo que importa no es que se arme el link —eso es Mercado Pago— sino lo que no
puede pasar: que un webhook falso marque algo como pagado, que un pago de otro
consorcio o por menos plata cierre una deuda, o que el token del edificio
llegue al navegador.
"""

import pytest

import app as app_mod
import mercadopago_niddo as mp
from cifrado import cifrar, descifrar


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'Admin', 'role': 'admin'}
    return c


@pytest.fixture
def conectado(base):
    base['consorcio_secretos'] = [{'consorcio_id': 'cons-1', 'mp_cuenta': 'edificio@mp',
                                   'mp_access_token_cifrado': cifrar('APP_USR-secreto')}]
    return base


@pytest.fixture
def mp_falso(monkeypatch):
    estado = {'pago': {'id': '99', 'estado': 'approved', 'monto': 100.0,
                       'cobro_id': 'cobro-1', 'fecha': '2026-08-05'}, 'tokens': []}

    def _pago(token, pid):
        estado['tokens'].append(token)
        return estado['pago']

    monkeypatch.setattr(mp, 'pago', _pago)
    monkeypatch.setattr(mp, 'cuenta', lambda t: {'email': 'edificio@mp'})
    monkeypatch.setattr(mp, 'crear_preferencia',
                        lambda token, cobro, *a, **k: {'id': 'pref', 'init_point': 'https://mp.test/pagar'})
    return estado


def test_el_token_se_guarda_cifrado(admin, base, mp_falso):
    base['consorcio_secretos'] = []
    r = admin.put('/api/admin/consorcios/cons-1/mercadopago', json={'access_token': 'APP_USR-abc'})
    assert r.status_code == 200
    fila = base['consorcio_secretos'][0]
    assert 'APP_USR-abc' not in fila['mp_access_token_cifrado']
    assert descifrar(fila['mp_access_token_cifrado']) == 'APP_USR-abc'


def test_el_estado_no_devuelve_el_token(admin, conectado):
    r = admin.get('/api/admin/consorcios/cons-1/mercadopago').get_json()
    assert r == {'conectado': True, 'cuenta': 'edificio@mp'}


def test_no_conecta_mp_en_un_consorcio_ajeno(admin, base, mp_falso):
    base['consorcio_secretos'] = []
    r = admin.put('/api/admin/consorcios/cons-2/mercadopago', json={'access_token': 'APP_USR-abc'})
    assert r.status_code == 404
    assert base['consorcio_secretos'] == []


def test_el_vecino_ve_el_boton_si_el_edificio_esta_conectado(client, conectado):
    assert client.get('/api/vecinos/cobro-actual').get_json()['pago_online'] is True


def test_sin_mp_no_hay_boton(client, base):
    base['consorcio_secretos'] = []
    assert client.get('/api/vecinos/cobro-actual').get_json()['pago_online'] is False


def test_el_vecino_obtiene_el_link_de_pago(client, conectado, mp_falso):
    r = client.post('/api/vecinos/cobros/cobro-1/pagar')
    assert r.get_json()['url'] == 'https://mp.test/pagar'


def test_el_webhook_marca_el_cobro_como_pagado(conectado, mp_falso, app_modulo):
    c = app_modulo.app.test_client()
    r = c.post('/webhooks/mercadopago/cons-1', json={'type': 'payment', 'data': {'id': '99'}})
    assert r.status_code == 200
    cobro = conectado['cobros'][0]
    assert cobro['estado'] == 'pagado'
    assert cobro['fecha_pago'] == '2026-08-05'
    assert 'operación 99' in cobro['notas']
    assert mp_falso['tokens'] == ['APP_USR-secreto']   # se verificó con la API


def test_un_pago_no_aprobado_no_marca_nada(conectado, mp_falso, app_modulo):
    mp_falso['pago']['estado'] = 'pending'
    app_modulo.app.test_client().post('/webhooks/mercadopago/cons-1?type=payment&data.id=99')
    assert conectado['cobros'][0]['estado'] == 'pendiente'


def test_un_pago_por_menos_no_cierra_la_deuda(conectado, mp_falso, app_modulo):
    mp_falso['pago']['monto'] = 10.0
    app_modulo.app.test_client().post('/webhooks/mercadopago/cons-1', json={'type': 'payment', 'data': {'id': '99'}})
    assert conectado['cobros'][0]['estado'] == 'pendiente'


def test_el_webhook_de_otro_consorcio_no_toca_el_cobro(conectado, mp_falso, app_modulo):
    conectado['consorcio_secretos'].append({'consorcio_id': 'cons-2', 'mp_cuenta': 'x',
                                            'mp_access_token_cifrado': cifrar('APP_USR-otro')})
    app_modulo.app.test_client().post('/webhooks/mercadopago/cons-2', json={'type': 'payment', 'data': {'id': '99'}})
    assert conectado['cobros'][0]['estado'] == 'pendiente'


def test_un_webhook_sin_id_valido_se_ignora(conectado, mp_falso, app_modulo):
    r = app_modulo.app.test_client().post('/webhooks/mercadopago/cons-1', json={'type': 'payment', 'data': {'id': 'x;drop'}})
    assert r.status_code == 200
    assert mp_falso['tokens'] == []
