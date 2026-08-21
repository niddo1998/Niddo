"""Emitir la liquidación crea la deuda que el vecino ve en su cuenta.

Era el agujero grande del circuito. La liquidación calculaba el total por
unidad y lo mandaba por mail, pero `cobros` —que alimenta Mis Expensas, el
cupón, la morosidad y el balance— se llenaba desde un modal aparte donde el
administrador tipeaba UN monto plano igual para todas las unidades. El número
del mail y el de la app podían no coincidir, y nada los ataba.
"""

import pytest

import app as app_mod


@pytest.fixture
def emitida(base, monkeypatch):
    monkeypatch.setattr(app_mod, '_enviar_mail', lambda *a, **k: None)
    base['unidades_funcionales'] = [
        {'id': 'uf-1', 'consorcio_id': 'cons-1', 'numero': '1A', 'vecino_email': 'uno@test'},
        {'id': 'uf-2', 'consorcio_id': 'cons-1', 'numero': '1B', 'vecino_email': 'dos@test'},
    ]
    base['liquidaciones'] = [{
        'id': 'liq-1', 'consorcio_id': 'cons-1', 'admin_id': 'admin-1',
        'periodo': '2026-08', 'numero_revision': 1, 'estado': 'borrador',
        'fecha_vencimiento_1': '2026-08-10', 'consorcios': {'nombre': 'Mío'},
    }]
    base['liquidacion_prorrateo'] = [
        {'id': 'pr-1', 'liquidacion_id': 'liq-1', 'unidad_id': 'uf-1',
         'total_unidad': 1030.0, 'interes_mora': 30.0,
         'unidades_funcionales': {'id': 'uf-1', 'numero': '1A', 'vecino_email': 'uno@test'}},
        {'id': 'pr-2', 'liquidacion_id': 'liq-1', 'unidad_id': 'uf-2',
         'total_unidad': 2000.0, 'interes_mora': 0.0,
         'unidades_funcionales': {'id': 'uf-2', 'numero': '1B', 'vecino_email': 'dos@test'}},
    ]
    base['liquidacion_rubros'] = []
    base['cobros'] = []
    base['resumen_envios'] = []
    return base


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


def test_emitir_crea_un_cobro_por_unidad(admin, emitida):
    r = admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert r.status_code == 200
    assert r.get_json()['cobros_generados'] == 2
    assert len(emitida['cobros']) == 2


def test_el_cobro_lleva_el_total_del_prorrateo(admin, emitida):
    """El punto de todo: el número del mail y el de la app son el mismo."""
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    cobro = next(c for c in emitida['cobros'] if c['unidad_id'] == 'uf-1')
    assert cobro['total'] == 1030.0
    assert cobro['interes_mora'] == 30.0
    assert cobro['monto_base'] == 1000.0      # el interés viaja aparte


def test_el_cobro_queda_atado_a_su_liquidacion(admin, emitida):
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert all(c['liquidacion_id'] == 'liq-1' for c in emitida['cobros'])
    assert all(c['periodo'] == '2026-08' for c in emitida['cobros'])
    assert all(c['fecha_vencimiento'] == '2026-08-10' for c in emitida['cobros'])


def test_emitir_dos_veces_no_duplica_la_deuda(admin, emitida):
    """Con dos pestañas abiertas o un doble click, el vecino no debe dos veces."""
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    r = admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert r.get_json()['cobros_generados'] == 0
    assert len(emitida['cobros']) == 2


def test_enviar_a_una_sola_unidad_solo_le_crea_el_cobro_a_esa(admin, emitida):
    admin.post('/api/liquidaciones/liq-1/enviar', json={'unidades_ids': ['uf-1']})
    assert [c['unidad_id'] for c in emitida['cobros']] == ['uf-1']


def test_el_reenvio_completa_los_que_faltaban(admin, emitida):
    admin.post('/api/liquidaciones/liq-1/enviar', json={'unidades_ids': ['uf-1']})
    r = admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert r.get_json()['cobros_generados'] == 1
    assert len(emitida['cobros']) == 2


def test_el_cobro_nace_pendiente(admin, emitida):
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert all(c['estado'] == 'pendiente' for c in emitida['cobros'])


def test_el_vecino_ve_en_su_cuenta_lo_que_dice_el_mail(admin, client, emitida, base):
    """La prueba de punta a punta del arreglo."""
    base['vecinos'][0]['unidad_id'] = 'uf-1'
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    visto = client.get('/api/vecinos/cobros').get_json()
    assert [c['total'] for c in visto] == [1030.0]


# ── El PDF adjunto ────────────────────────────────────────────────────────────
# El resumen del cuerpo del mail es personalizado y se lee bien, pero no es lo
# que la Ley 941 obliga a rendir: eso es la liquidación entera, con el detalle
# de cada gasto y la tabla de todas las unidades. Van juntos.

@pytest.fixture
def resend_falso(monkeypatch):
    enviados = []

    class _Emails:
        @staticmethod
        def send(mensaje):
            enviados.append(mensaje)
            return {'id': 'fake'}

    import resend
    monkeypatch.setattr(resend, 'Emails', _Emails)
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')
    return enviados


def test_el_mail_lleva_el_pdf_adjunto(admin, emitida, resend_falso):
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert len(resend_falso) == 2
    for m in resend_falso:
        adj = m.get('attachments')
        assert adj, 'el mail salió sin adjunto'
        assert adj[0]['filename'].endswith('.pdf')
        assert bytes(adj[0]['content'][:5]) == b'%PDF-'


def test_el_adjunto_se_llama_por_consorcio_y_periodo(admin, emitida, resend_falso):
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    nombre = resend_falso[0]['attachments'][0]['filename']
    assert nombre == 'expensas-mio-2026-08.pdf'


def test_la_complementaria_se_distingue_en_el_nombre(admin, emitida, resend_falso):
    emitida['liquidaciones'][0]['numero_revision'] = 2
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert resend_falso[0]['attachments'][0]['filename'].endswith('-rev2.pdf')


def test_es_el_mismo_pdf_para_todos(admin, emitida, resend_falso):
    """Se arma una vez: es la liquidación del consorcio, idéntica para todos.
    Generarla por unidad sería 40 veces el mismo trabajo en una request que ya
    manda 40 mails."""
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    a, b = (m['attachments'][0]['content'] for m in resend_falso)
    assert a == b


def test_si_el_pdf_falla_los_mails_salen_igual(admin, emitida, resend_falso, monkeypatch):
    """Quedarse sin avisar es peor que avisar sin adjunto."""
    monkeypatch.setattr(app_mod, '_pdf_de_liquidacion',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    r = admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert r.get_json()['enviados'] == 2
    assert all('attachments' not in m for m in resend_falso)


def test_el_nombre_del_adjunto_no_lleva_tildes_ni_enie(admin, emitida, resend_falso):
    """Viaja por mail y se guarda en cualquier sistema de archivos."""
    # El endpoint lee el consorcio embebido en la liquidación, no la fila suelta.
    emitida['liquidaciones'][0]['consorcios']['nombre'] = 'Edificio Ñandú Mío'
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    nombre = resend_falso[0]['attachments'][0]['filename']
    assert nombre == 'expensas-edificio-nandu-mio-2026-08.pdf'
    assert nombre.isascii()
