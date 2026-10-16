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
