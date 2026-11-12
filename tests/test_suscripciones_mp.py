"""Débito automático con Mercado Pago: lo que Niddo le cobra a cada administrador.

La API de Mercado Pago se reemplaza por un doble que guarda lo que se le pidió.
"""

import hashlib
import hmac
from datetime import date, timedelta

import pytest

import app as app_mod
import suscripciones_mp as smp

PLANES = [
    {'id': 'p10', 'nombre': 'Hasta 10 unidades', 'max_unidades': 10, 'precio_mensual': 20000, 'orden': 1},
    {'id': 'p25', 'nombre': 'Hasta 25 unidades', 'max_unidades': 25, 'precio_mensual': 45000, 'orden': 2},
    {'id': 'pmax', 'nombre': 'Más', 'max_unidades': None, 'precio_mensual': 90000, 'orden': 3},
]


class MPFalso:
    """Lo mínimo de la API de suscripciones, en memoria."""

    def __init__(self):
        self.subs, self.cobros, self.llamadas = {}, {}, []

    def crear(self, admin_id, payer_email, monto, motivo, url_volver, url_webhook, empieza=None):
        sid = f'pre-{len(self.subs) + 1}'
        self.subs[sid] = {'id': sid, 'estado': 'pending', 'monto': monto, 'admin_id': admin_id,
                          'payer_email': payer_email, 'proximo_cobro': (empieza or '')[:10] or None,
                          'init_point': f'https://mp.test/{sid}'}
        self.llamadas.append(('crear', monto, empieza))
        return dict(self.subs[sid])

    def leer(self, sid):
        return dict(self.subs[sid])

    def actualizar(self, sid, monto=None, estado=None):
        self.llamadas.append(('actualizar', sid, monto, estado))
        if monto is not None:
            self.subs[sid]['monto'] = monto
        if estado:
            self.subs[sid]['estado'] = estado
        return dict(self.subs[sid])

    def leer_cobro(self, cid):
        return dict(self.cobros[cid])


@pytest.fixture
def mp(monkeypatch):
    falso = MPFalso()
    monkeypatch.setenv('MP_NIDDO_ACCESS_TOKEN', 'TEST-token')
    monkeypatch.delenv('MP_NIDDO_WEBHOOK_SECRET', raising=False)
    for nombre in ('crear', 'leer', 'actualizar', 'leer_cobro'):
        monkeypatch.setattr(smp, nombre, getattr(falso, nombre))
    return falso


@pytest.fixture
def mundo(base):
    base['planes'] = [dict(p) for p in PLANES]
    for t in ('cobros_niddo', 'suscripciones_mp', 'negocio_movimientos', 'negocio_config', 'negocio_prospectos'):
        base[t] = []
    base['unidades_funcionales'] = [u for u in base['unidades_funcionales'] if u['consorcio_id'] != 'cons-1']
    base['unidades_funcionales'] += [{'id': f'u{i}', 'consorcio_id': 'cons-1', 'numero': str(i)} for i in range(10)]
    base['administradores'][0].update(gratis_hasta=None, siempre_gratis=False, es_fundador=False,
                                      email_contacto='pagos@adm.test')
    app_mod.app.config['TESTING'] = True
    return base


@pytest.fixture
def admin(mundo):
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'A', 'role': 'admin'}
    return c


def _webhook(c, tipo, data_id):
    return c.post(f'/webhooks/mercadopago-niddo?type={tipo}&data.id={data_id}', json={})


# ── Sin token, todo apagado ──────────────────────────────────────────────────

def test_sin_token_no_se_puede_suscribir(admin, monkeypatch):
    monkeypatch.delenv('MP_NIDDO_ACCESS_TOKEN', raising=False)
    assert admin.post('/api/admin/suscripcion').status_code == 503
    assert admin.get('/api/admin/mi-plan').get_json()['mercadopago']['habilitado'] is False


# ── Alta ─────────────────────────────────────────────────────────────────────

def test_suscribirse_crea_el_debito_por_el_total(admin, mp, mundo):
    r = admin.post('/api/admin/suscripcion')
    assert r.status_code == 200
    assert r.get_json()['init_point'] == 'https://mp.test/pre-1'
    assert mp.llamadas == [('crear', 20000, None)]
    fila = mundo['suscripciones_mp'][0]
    assert (fila['admin_id'], fila['preapproval_id'], fila['payer_email']) == ('admin-1', 'pre-1', 'pagos@adm.test')


def test_con_pase_gratis_el_debito_arranca_cuando_vence(admin, mp, mundo):
    hasta = date.today() + timedelta(days=40)
    mundo['administradores'][0]['gratis_hasta'] = hasta.isoformat()
    admin.post('/api/admin/suscripcion')
    empieza = mp.llamadas[0][2]
    assert empieza.startswith((hasta + timedelta(days=1)).isoformat())


def test_no_se_duplica_un_debito_activo(admin, mp, mundo):
    admin.post('/api/admin/suscripcion')
    mp.subs['pre-1']['estado'] = 'authorized'
    _webhook(admin, 'subscription_preapproval', 'pre-1')
    assert admin.post('/api/admin/suscripcion').status_code == 409


def test_el_equipo_no_se_suscribe(admin, mp, mundo):
    mundo['administradores'][0]['siempre_gratis'] = True
    assert admin.post('/api/admin/suscripcion').status_code == 400


def test_al_volver_de_mp_se_ve_activa(admin, mp, mundo):
    admin.post('/api/admin/suscripcion')
    mp.subs['pre-1'].update(estado='authorized', proximo_cobro='2026-12-12')
    d = admin.get('/api/admin/mi-plan').get_json()['mercadopago']
    assert d['suscripcion']['estado'] == 'authorized'
    assert d['suscripcion']['proximo_cobro'] == '2026-12-12'


def test_cancelar(admin, mp, mundo):
    admin.post('/api/admin/suscripcion')
    assert admin.post('/api/admin/suscripcion/cancelar').status_code == 200
    assert mundo['suscripciones_mp'][0]['estado'] == 'cancelled'


# ── El monto sigue al plan ───────────────────────────────────────────────────

def test_pasar_de_plan_sube_el_debito(admin, mp, mundo):
    admin.post('/api/admin/suscripcion')
    mp.subs['pre-1']['estado'] = 'authorized'
    _webhook(admin, 'subscription_preapproval', 'pre-1')
    admin.post('/api/consorcios/cons-1/unidades', json={'numero': 'nueva'})   # la 11
    assert ('actualizar', 'pre-1', 45000, None) in mp.llamadas
    assert mundo['suscripciones_mp'][0]['monto'] == 45000


def test_pase_gratis_nuevo_pausa_el_debito(mundo, mp, monkeypatch):
    mundo['suscripciones_mp'].append({'admin_id': 'admin-1', 'preapproval_id': 'pre-9',
                                      'estado': 'authorized', 'monto': 20000, 'proximo_cobro': '2026-12-01'})
    mp.subs['pre-9'] = {'id': 'pre-9', 'estado': 'authorized', 'monto': 20000, 'proximo_cobro': '2026-12-01'}
    mundo['administradores'][0]['gratis_hasta'] = (date.today() + timedelta(days=90)).isoformat()
    assert app_mod.sincronizar_suscripcion_de('admin-1') == 'actualizada'
    assert mundo['suscripciones_mp'][0]['estado'] == 'paused'
    # Cuando vence, la pasada diaria la reactiva.
    mundo['administradores'][0]['gratis_hasta'] = (date.today() - timedelta(days=1)).isoformat()
    assert app_mod.sincronizar_todas_las_suscripciones() == {'suscripciones_actualizadas': 1}
    assert mundo['suscripciones_mp'][0]['estado'] == 'authorized'


# ── Webhook de cobros ────────────────────────────────────────────────────────

def _con_debito(mundo, mp):
    mundo['suscripciones_mp'].append({'admin_id': 'admin-1', 'preapproval_id': 'pre-1',
                                      'estado': 'authorized', 'monto': 20000})
    mp.cobros['ap-1'] = {'id': 'ap-1', 'preapproval_id': 'pre-1', 'pago_id': '777',
                         'aprobado': True, 'monto': 20000, 'fecha': '2026-12-01'}


def test_cobro_aprobado_salda_el_mes_y_entra_en_finanzas(admin, mp, mundo):
    _con_debito(mundo, mp)
    r = _webhook(admin, 'subscription_authorized_payment', 'ap-1')
    assert r.get_json()['resultado'] == 'registrado'
    cobro = mundo['cobros_niddo'][0]
    assert (cobro['periodo'], cobro['estado'], cobro['total'], cobro['mp_pago_id']) == ('2026-12', 'pagado', 20000, '777')
    mov = mundo['negocio_movimientos'][0]
    assert (mov['tipo'], mov['monto'], mov['categoria']) == ('ingreso', 20000, 'Suscripciones')

    # Mercado Pago repite el aviso: no se cuenta dos veces.
    assert _webhook(admin, 'subscription_authorized_payment', 'ap-1').get_json()['resultado'] == 'repetido'
    assert len(mundo['negocio_movimientos']) == 1


def test_cobro_aprobado_salda_el_cobro_pendiente_ya_generado(admin, mp, mundo):
    _con_debito(mundo, mp)
    mundo['cobros_niddo'].append({'id': 'c-1', 'admin_id': 'admin-1', 'periodo': '2026-12',
                                  'total': 20000, 'estado': 'pendiente', 'detalle': []})
    _webhook(admin, 'subscription_authorized_payment', 'ap-1')
    assert len(mundo['cobros_niddo']) == 1
    assert mundo['cobros_niddo'][0]['estado'] == 'pagado'


def test_cobro_rechazado_no_hace_nada(admin, mp, mundo):
    _con_debito(mundo, mp)
    mp.cobros['ap-1']['aprobado'] = False
    _webhook(admin, 'subscription_authorized_payment', 'ap-1')
    assert mundo['cobros_niddo'] == [] and mundo['negocio_movimientos'] == []


def test_webhook_falla_la_api_pide_reintento(admin, mp, mundo, monkeypatch):
    _con_debito(mundo, mp)

    def rompe(_):
        raise smp.ErrorMercadoPago('caída')
    monkeypatch.setattr(smp, 'leer_cobro', rompe)
    assert _webhook(admin, 'subscription_authorized_payment', 'ap-1').status_code == 502


# ── Firma del webhook ────────────────────────────────────────────────────────

def test_firma(monkeypatch):
    monkeypatch.setenv('MP_NIDDO_WEBHOOK_SECRET', 'secreto')
    v1 = hmac.new(b'secreto', b'id:ap-1;request-id:req-9;ts:1700;', hashlib.sha256).hexdigest()
    assert smp.firma_valida(f'ts=1700,v1={v1}', 'req-9', 'AP-1')
    assert not smp.firma_valida(f'ts=1700,v1={v1}', 'otro', 'ap-1')
    assert not smp.firma_valida('', 'req-9', 'ap-1')


def test_webhook_con_firma_mala_se_rechaza(admin, mp, mundo, monkeypatch):
    monkeypatch.setenv('MP_NIDDO_WEBHOOK_SECRET', 'secreto')
    _con_debito(mundo, mp)
    r = admin.post('/webhooks/mercadopago-niddo?type=subscription_authorized_payment&data.id=ap-1',
                   json={}, headers={'x-signature': 'ts=1,v1=falsa', 'x-request-id': 'r'})
    assert r.status_code == 401
    assert mundo['cobros_niddo'] == []


# ── El módulo arma bien el pedido a Mercado Pago ─────────────────────────────

def test_crear_arma_el_preapproval(monkeypatch):
    monkeypatch.setenv('MP_NIDDO_ACCESS_TOKEN', 'TEST-token')
    pedido = {}

    def llamar(metodo, ruta, token, cuerpo=None):
        pedido.update(metodo=metodo, ruta=ruta, token=token, cuerpo=cuerpo)
        return {'id': 'pre-1', 'status': 'pending', 'init_point': 'https://mp/x',
                'auto_recurring': cuerpo['auto_recurring'], 'external_reference': cuerpo['external_reference']}
    monkeypatch.setattr(smp, '_llamar', llamar)
    s = smp.crear('admin-1', 'a@b.c', 45000, 'Niddo', 'https://v', 'https://w', '2027-01-01T10:00:00.000-03:00')
    ar = pedido['cuerpo']['auto_recurring']
    assert (pedido['metodo'], pedido['ruta'], pedido['token']) == ('POST', '/preapproval', 'TEST-token')
    assert (ar['frequency'], ar['frequency_type'], ar['currency_id'], ar['transaction_amount']) == (1, 'months', 'ARS', 45000)
    assert ar['start_date'].startswith('2027-01-01')
    assert pedido['cuerpo']['status'] == 'pending'
    assert (s['estado'], s['admin_id'], s['init_point']) == ('pending', 'admin-1', 'https://mp/x')
