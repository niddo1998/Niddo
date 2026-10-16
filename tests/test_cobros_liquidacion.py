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


# ── El mail ───────────────────────────────────────────────────────────────────
# Sale por lote: de a uno eran dos viajes de red por unidad y con 40 unidades la
# request pasaba el límite de Vercel a mitad del envío. El lote de Resend no
# acepta adjuntos, así que el mail lleva el link a la página pública de la
# liquidación (PDF completo, comprobantes y reglamento, Disp. 1146/2024).

@pytest.fixture
def resend_falso(monkeypatch):
    llamadas = []

    class _Batch:
        @staticmethod
        def send(mensajes):
            llamadas.append(list(mensajes))
            return {'data': [{'id': 'fake'} for _ in mensajes]}

    import resend
    monkeypatch.setattr(resend, 'Batch', _Batch)
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')
    return llamadas


def test_los_mails_salen_en_un_solo_lote(admin, emitida, resend_falso):
    r = admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert r.get_json()['enviados'] == 2
    assert len(resend_falso) == 1
    assert len(resend_falso[0]) == 2


def test_el_mail_lleva_el_link_a_la_liquidacion_publica(admin, emitida, resend_falso):
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    token = emitida['liquidaciones'][0]['token_publico']
    for m in resend_falso[0]:
        assert f'/l/{token}' in m['html']


def test_los_envios_se_registran_de_una_vez(admin, emitida, resend_falso):
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert len(emitida['resumen_envios']) == 2
    assert all(e['estado'] == 'enviado' for e in emitida['resumen_envios'])


def test_si_el_lote_falla_quedan_como_fallidos(admin, emitida, monkeypatch):
    class _Batch:
        @staticmethod
        def send(mensajes):
            raise RuntimeError('resend caído')

    import resend
    monkeypatch.setattr(resend, 'Batch', _Batch)
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')
    r = admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert r.get_json()['fallidos'] == 2
    assert emitida['liquidaciones'][0]['estado'] == 'borrador'
    assert all(e['estado'] == 'fallido' for e in emitida['resumen_envios'])


def test_la_complementaria_se_distingue_en_el_asunto(admin, emitida, resend_falso):
    emitida['liquidaciones'][0]['numero_revision'] = 2
    admin.post('/api/liquidaciones/liq-1/enviar', json={})
    assert resend_falso[0][0]['subject'].startswith('📋 Expensa complementaria')


def test_el_nombre_del_pdf_no_lleva_tildes_ni_enie(app_modulo):
    """Se descarga y se guarda en cualquier sistema de archivos."""
    nombre = app_modulo._nombre_pdf_liquidacion({'periodo': '2026-08', 'numero_revision': 1},
                                                {'nombre': 'Edificio Ñandú Mío'})
    assert nombre == 'expensas-edificio-nandu-mio-2026-08.pdf'
