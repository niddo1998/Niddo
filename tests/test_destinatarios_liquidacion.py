"""A qué mail le llega la liquidación.

Hay dos mails por unidad y no son el mismo: el que el administrador tipeó al
cargar la UF en el padrón, y el de la cuenta con la que el vecino entra a
Niddo. El envío miraba sólo el primero, así que una unidad cuyo vecino se
registró solo —lo normal— salía como "sin email configurado" y no recibía
nada, teniendo el mail a una tabla de distancia.
"""

import pytest

import app as app_mod


@pytest.fixture
def admin(base, app_modulo, monkeypatch):
    monkeypatch.setattr(app_modulo, '_enviar_mail', lambda *a, **k: None)
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


@pytest.fixture
def liquidada(base):
    """Tres unidades: una con mail sólo en el padrón, una sólo registrada, una con los dos."""
    base['unidades_funcionales'] = [
        {'id': 'uf-1', 'consorcio_id': 'cons-1', 'numero': '1A', 'vecino_email': 'padron1@test'},
        {'id': 'uf-2', 'consorcio_id': 'cons-1', 'numero': '2A', 'vecino_email': ''},
        {'id': 'uf-3', 'consorcio_id': 'cons-1', 'numero': '3A', 'vecino_email': 'padron3@test'},
    ]
    base['vecinos'] = [
        # Registrado y aprobado sobre la 2A: su mail es el único que existe.
        {'id': 'v-2', 'auth0_id': 'auth0|dos', 'email': 'cuenta2@test',
         'unidad_id': 'uf-2', 'consorcio_id': 'cons-1'},
        # Registrado sobre la 3A: le gana al del padrón.
        {'id': 'v-3', 'auth0_id': 'auth0|tres', 'email': 'cuenta3@test',
         'unidad_id': 'uf-3', 'consorcio_id': 'cons-1'},
        # Pendiente sobre la 1A: todavía no lo aprobaron, no recibe nada.
        {'id': 'v-1', 'auth0_id': 'auth0|uno', 'email': 'pendiente@test',
         'unidad_id': 'uf-1', 'consorcio_id': None, 'estado_asociacion': 'pendiente'},
    ]
    base['liquidaciones'] = [{
        'id': 'liq-1', 'consorcio_id': 'cons-1', 'admin_id': 'admin-1',
        'periodo': '2026-08', 'numero_revision': 1, 'estado': 'borrador',
        'consorcios': {'nombre': 'Mío'},
    }]
    base['liquidacion_prorrateo'] = [
        {'id': f'pro-{n}', 'liquidacion_id': 'liq-1', 'unidad_id': f'uf-{n}',
         'total_unidad': 1000, 'unidades_funcionales': u}
        for n, u in ((1, base['unidades_funcionales'][0]),
                     (2, base['unidades_funcionales'][1]),
                     (3, base['unidades_funcionales'][2]))
    ]
    return base


def _emails(admin, unidad):
    filas = admin.get('/api/liquidaciones/liq-1/prorrateo').get_json()
    return next(f['emails'] for f in filas if f['unidad_id'] == unidad)


def test_sin_vecino_registrado_se_usa_el_del_padron(admin, liquidada):
    assert _emails(admin, 'uf-1') == ['padron1@test']


def test_el_vecino_registrado_ya_no_figura_sin_email(admin, liquidada):
    assert _emails(admin, 'uf-2') == ['cuenta2@test']


def test_el_mail_de_la_cuenta_le_gana_al_del_padron(admin, liquidada):
    assert _emails(admin, 'uf-3') == ['cuenta3@test']


def test_el_pendiente_no_es_destinatario(admin, liquidada):
    """Todavía no lo aprobaron: no recibe la expensa del edificio."""
    assert 'pendiente@test' not in _emails(admin, 'uf-1')


def test_dos_vecinos_aprobados_en_la_misma_unidad_reciben_los_dos(admin, liquidada, base):
    base['vecinos'].append({'id': 'v-2b', 'auth0_id': 'auth0|dosb',
                            'email': 'inquilino2@test', 'unidad_id': 'uf-2',
                            'consorcio_id': 'cons-1'})
    assert sorted(_emails(admin, 'uf-2')) == ['cuenta2@test', 'inquilino2@test']


def test_el_envio_le_escribe_al_mail_de_la_cuenta(admin, liquidada, monkeypatch):
    enviados = []

    class _Emails:
        @staticmethod
        def send(mensaje):
            enviados.append(mensaje)
            return {'id': 'x'}

    import resend
    monkeypatch.setattr(resend, 'Emails', _Emails)
    monkeypatch.setattr(resend, 'api_key', 'test-key', raising=False)
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')

    r = admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert r.status_code == 200
    destinatarios = sorted(sum((m['to'] for m in enviados), []))
    assert destinatarios == ['cuenta2@test', 'cuenta3@test', 'padron1@test']
    assert r.get_json()['fallidos'] == 0
