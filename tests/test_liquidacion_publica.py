"""La página pública de la liquidación, la que abre el QR del PDF.

En CABA la liquidación tiene que llevar un QR o link a los comprobantes del
período (Disp. DGDyPC 1146/2024), al reglamento y al manual de buenas prácticas
(Disp. 521/2025). Lo escanea cualquiera desde el papel, así que no pide login:
lo que importa es que el token no deje ver nada fuera de ESA liquidación.
"""

import pytest


@pytest.fixture
def publica(base, app_modulo):
    base['liquidaciones'] = [{
        'id': 'liq-1', 'consorcio_id': 'cons-1', 'admin_id': 'admin-1',
        'periodo': '2026-08', 'numero_revision': 1, 'estado': 'publicada',
        'token_publico': 'tok-largo-1234567',
        'consorcios': {'nombre': 'Mío', 'direccion': 'Corrientes 1'},
    }]
    base['liquidacion_rubros'] = [{'id': 'r-1', 'liquidacion_id': 'liq-1',
                                   'numero_rubro': 1, 'nombre': 'Sueldos', 'subtotal': 500}]
    base['liquidacion_items'] = [{'id': 'i-1', 'rubro_id': 'r-1', 'descripcion': 'Encargado',
                                  'monto': 500, 'gasto_id': 'g-1'}]
    base['comprobantes_gastos'] = [
        {'gasto_id': 'g-1', 'archivo_nombre': 'recibo.pdf',
         'archivo_base64': 'JVBERi0xLjQK', 'mime_type': 'application/pdf'},
        {'gasto_id': 'g-ajeno', 'archivo_nombre': 'otro.pdf',
         'archivo_base64': 'JVBERi0xLjQK', 'mime_type': 'application/pdf'},
    ]
    base['archivos_consorcio'] = []
    app_modulo.app.config['TESTING'] = True
    return app_modulo.app.test_client()


def test_la_pagina_abre_sin_login(publica):
    r = publica.get('/l/tok-largo-1234567')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Encargado' in html
    assert '/l/tok-largo-1234567/comprobante/g-1' in html
    assert 'Manual de Buenas Prácticas' in html


def test_no_se_indexa(publica):
    r = publica.get('/l/tok-largo-1234567')
    assert 'noindex' in r.headers['X-Robots-Tag']


def test_un_token_que_no_existe_da_404(publica):
    assert publica.get('/l/no-existe-este-token').status_code == 404
    assert publica.get('/l/corto').status_code == 404


def test_baja_el_comprobante_de_un_gasto_de_la_liquidacion(publica):
    r = publica.get('/l/tok-largo-1234567/comprobante/g-1')
    assert r.status_code == 200
    assert r.data.startswith(b'%PDF')


def test_no_deja_bajar_comprobantes_de_otros_gastos(publica):
    assert publica.get('/l/tok-largo-1234567/comprobante/g-ajeno').status_code == 404


def test_sin_reglamento_cargado_avisa_que_falta(publica):
    html = publica.get('/l/tok-largo-1234567').get_data(as_text=True)
    assert 'todavía no lo subió' in html
    assert publica.get('/l/tok-largo-1234567/reglamento').status_code == 404


def test_con_reglamento_lo_ofrece(publica, base):
    base['archivos_consorcio'] = [{'id': 'a-1', 'consorcio_id': 'cons-1', 'categoria': 'reglamento',
                                   'nombre': 'Reglamento.pdf', 'archivo_base64': 'JVBERi0xLjQK',
                                   'mime_type': 'application/pdf', 'created_at': '2026-01-01'}]
    assert '/l/tok-largo-1234567/reglamento' in publica.get('/l/tok-largo-1234567').get_data(as_text=True)
    assert publica.get('/l/tok-largo-1234567/reglamento').status_code == 200


def test_el_pdf_lleva_el_qr(app_modulo):
    from liquidacion_pdf import construir_pdf
    import pymupdf
    pdf = construir_pdf({'periodo': '2026-08'}, {'nombre': 'Mío'}, {}, [], [],
                        enlace='https://niddo.test/l/abc123abc123')
    texto = pymupdf.open(stream=pdf, filetype='pdf')[0].get_text()
    assert 'https://niddo.test/l/abc123abc123' in texto
    assert 'Buenas Prácticas' in texto


@pytest.mark.parametrize('ruta,texto', [('/terminos', 'Términos y condiciones'),
                                        ('/privacidad', 'Ley 25.326')])
def test_las_paginas_legales_abren_sin_login(app_modulo, base, ruta, texto):
    app_modulo.app.config['TESTING'] = True
    r = app_modulo.app.test_client().get(ruta)
    assert r.status_code == 200
    assert texto in r.get_data(as_text=True)


def test_el_pdf_muestra_la_composicion_del_saldo_si_esta_cargada():
    from liquidacion_pdf import construir_pdf
    import pymupdf
    texto = lambda liq: ''.join(p.get_text() for p in pymupdf.open(
        stream=construir_pdf(liq, {'nombre': 'Mío'}, {}, [], []), filetype='pdf'))
    assert 'Composición del saldo' not in texto({'periodo': '2026-08'})
    con = texto({'periodo': '2026-08', 'saldo_bancario': 1000, 'saldo_superfondo': 500})
    assert 'Composición del saldo' in con
    assert 'Fondo de reserva' in con


def test_quiero_ser_piloto_abre_el_registro_de_admin(app_modulo, base):
    app_modulo.app.config['TESTING'] = True
    html = app_modulo.app.test_client().get('/').get_data(as_text=True)
    assert 'href="/auth/login?role=admin&amp;registro=1"' in html
    assert 'Mercado Pago' not in html


def test_registro_pide_a_auth0_la_pantalla_de_alta(app_modulo, base, monkeypatch):
    pedidos = []
    monkeypatch.setattr(app_modulo.auth0, 'authorize_redirect',
                        lambda **k: pedidos.append(k) or ('', 302))
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    c.get('/auth/login?role=admin&registro=1')
    c.get('/auth/login?role=admin')
    assert pedidos[0].get('screen_hint') == 'signup'
    assert 'screen_hint' not in pedidos[1]
    with c.session_transaction() as s:
        assert s['pending_role'] == 'admin'


def test_los_legales_no_inventan_datos_de_la_sociedad(app_modulo, base, monkeypatch):
    for v in ('NIDDO_RAZON_SOCIAL', 'NIDDO_CUIT', 'NIDDO_DOMICILIO'):
        monkeypatch.delenv(v, raising=False)
    app_modulo.app.config['TESTING'] = True
    html = app_modulo.app.test_client().get('/terminos').get_data(as_text=True)
    assert 'es una plataforma web' in html
    assert 'CUIT' not in html
    assert 'Mercado Pago' not in html


def test_el_mail_de_contacto_por_defecto_es_el_de_niddo(app_modulo, base, monkeypatch):
    monkeypatch.delenv('NIDDO_EMAIL_CONTACTO', raising=False)
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    for ruta in ('/', '/terminos', '/privacidad'):
        assert 'mailto:niddo1998@gmail.com' in c.get(ruta).get_data(as_text=True)


def test_probar_sentry_es_solo_para_superadmin(app_modulo, base, monkeypatch):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    assert c.get('/superadmin/probar-sentry').status_code in (302, 401, 403)
    base['administradores'][0]['es_superadmin'] = True
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'Admin', 'role': 'admin'}
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    r = c.get('/superadmin/probar-sentry')
    assert r.status_code == 503
    assert 'SENTRY_DSN' in r.get_json()['mensaje']
