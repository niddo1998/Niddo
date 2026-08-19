"""Un adjunto no puede ser una página que se ejecuta en el dominio de Niddo.

Los comprobantes se guardaban con el `content_type` que mandaba el cliente y se
servían inline. Subir un .html declarado `text/html` —o un SVG, que es XML con
scripts adentro— lo convertía en una página corriendo en el origen de Niddo,
con la sesión de quien la abriera.

El arreglo tiene dos mitades y las dos tienen que estar: en la subida se
reconoce el tipo por los primeros bytes y se rechaza lo que no sea PDF o
imagen; en la entrega se vuelve a deducir del contenido, porque las filas
cargadas antes de la validación pueden tener guardado cualquier `mime_type`.
"""

import io

import pytest

from test_pertenencia import FakeSupabase, app_mod


PDF  = b'%PDF-1.4\n' + b'contenido' * 10
PNG  = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40
JPG  = b'\xff\xd8\xff\xe0' + b'\x00' * 40
HTML = b'<html><script>alert(document.cookie)</script></html>'
SVG  = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


# ── El reconocimiento por contenido ───────────────────────────────────────────

@pytest.mark.parametrize('datos, esperado', [
    (PDF, 'application/pdf'),
    (PNG, 'image/png'),
    (JPG, 'image/jpeg'),
    (b'RIFF\x00\x00\x00\x00WEBPVP8 ', 'image/webp'),
    (HTML, None),
    (SVG, None),
    (b'', None),
])
def test_mime_real_mira_los_bytes_no_la_extension(datos, esperado):
    assert app_mod._mime_real(datos) == esperado


class _Subida:
    """Lo mínimo de un FileStorage que usa validar_adjunto()."""
    def __init__(self, datos, filename, content_type):
        self._datos, self.filename, self.content_type = datos, filename, content_type

    def read(self):
        return self._datos


@pytest.mark.parametrize('datos, filename, content_type', [
    (HTML, 'factura.pdf', 'application/pdf'),   # se disfraza de PDF
    (SVG,  'foto.png',    'image/png'),         # se disfraza de PNG
    (HTML, 'x.html',      'text/html'),         # ni se disfraza
])
def test_rechaza_lo_que_puede_ejecutarse(datos, filename, content_type):
    with pytest.raises(ValueError):
        app_mod.validar_adjunto(_Subida(datos, filename, content_type))


def test_rechaza_lo_que_pasa_de_cinco_megas():
    grande = PDF + b'\x00' * app_mod.TAMANO_MAXIMO_ADJUNTO
    with pytest.raises(ValueError):
        app_mod.validar_adjunto(_Subida(grande, 'gordo.pdf', 'application/pdf'))


def test_el_mime_sale_del_contenido_y_no_del_cliente():
    """Un PDF de verdad anunciado como text/html se guarda como PDF."""
    _, mime, _ = app_mod.validar_adjunto(_Subida(PDF, 'f.pdf', 'text/html'))
    assert mime == 'application/pdf'


def test_el_nombre_pierde_la_ruta_pero_conserva_los_acentos():
    """El nombre se le muestra al usuario: sanearlo no es reescribirlo."""
    _, _, nombre = app_mod.validar_adjunto(
        _Subida(PDF, '../../etc/Factura Edesur agosto.pdf', 'application/pdf'))
    assert nombre == 'Factura Edesur agosto.pdf'


def test_acepta_los_cuatro_formatos_de_siempre():
    for datos in (PDF, PNG, JPG):
        assert app_mod.validar_adjunto(_Subida(datos, 'a', 'application/octet-stream'))


# ── La entrega ────────────────────────────────────────────────────────────────

def _datos_con(comprobante):
    return {
        'vecinos': [{'id': 'vec-1', 'auth0_id': 'auth0|uno',
                     'consorcio_id': 'cons-1', 'unidad_id': 'uf-1'}],
        'consorcios': [{'id': 'cons-1', 'admin_id': 'admin-1'}],
        'gastos': [{'id': 'gasto-1', 'consorcio_id': 'cons-1'}],
        'comprobantes_gastos': [comprobante],
        'administradores': [],
        'vecinos_unidades': [],
    }


def _cliente(store, monkeypatch):
    monkeypatch.setattr(app_mod, 'supabase', FakeSupabase(store))
    app_mod.app.config['TESTING'] = True
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|uno', 'email': 'u@t', 'name': 'U', 'role': 'vecino'}
    return c


def test_una_fila_vieja_con_mime_html_no_se_sirve_como_html(monkeypatch):
    """El caso que importa: lo que ya está guardado de antes del arreglo."""
    import base64
    store = _datos_con({
        'id': 'comp-1', 'gasto_id': 'gasto-1',
        'archivo_base64': base64.b64encode(HTML).decode(),
        'archivo_nombre': 'trampa.html', 'mime_type': 'text/html',
    })
    res = _cliente(store, monkeypatch).get('/api/gastos/gasto-1/comprobante')
    assert res.status_code == 200
    assert 'text/html' not in res.headers['Content-Type']
    assert res.headers['Content-Type'].startswith('application/octet-stream')
    # Y que además baje en vez de abrirse.
    assert res.headers['Content-Disposition'].startswith('attachment')
    assert res.headers['X-Content-Type-Options'] == 'nosniff'


def test_un_pdf_legitimo_sigue_abriendose_en_la_pestana(monkeypatch):
    """La pantalla no cambia: el comprobante se sigue viendo con un click."""
    import base64
    store = _datos_con({
        'id': 'comp-1', 'gasto_id': 'gasto-1',
        'archivo_base64': base64.b64encode(PDF).decode(),
        'archivo_nombre': 'factura.pdf', 'mime_type': 'application/pdf',
    })
    res = _cliente(store, monkeypatch).get('/api/gastos/gasto-1/comprobante')
    assert res.status_code == 200
    assert res.headers['Content-Type'].startswith('application/pdf')
    assert res.headers['Content-Disposition'].startswith('inline')
