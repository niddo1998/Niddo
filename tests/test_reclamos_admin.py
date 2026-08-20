"""El administrador atiende los reclamos de sus edificios.

El circuito estaba cortado de este lado: el vecino ya mostraba respuesta_admin
cuando venía con texto, pero nadie tenía dónde escribirla. Y el adjunto —que
en un reclamo suele ser el reclamo entero— sólo lo servía una ruta
allowed_roles=['vecino'], así que la foto no le llegaba al que la necesita.
"""

import base64

import pytest

# Un PNG de 1x1, lo mínimo que reconoce un navegador.
PNG = base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    '0000000a49444154789c6300010000050001'
    '0d0a2db40000000049454e44ae426082')).decode()


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


@pytest.fixture
def reclamos(base):
    base['reclamos'] = [
        {'id': 'rec-1', 'consorcio_id': 'cons-1', 'vecino_id': 'vec-1',
         'titulo': 'Pérdida en el baño', 'descripcion': 'Gotea',
         'categoria': 'plomeria', 'estado': 'activo', 'respuesta_admin': None,
         'adjunto_base64': PNG, 'adjunto_nombre': 'foto.png',
         'adjunto_mime': 'image/png', 'created_at': '2026-08-01T10:00:00+00:00',
         'updated_at': '2026-08-01T10:00:00+00:00'},
        {'id': 'rec-2', 'consorcio_id': 'cons-2', 'vecino_id': 'vec-2',
         'titulo': 'Ajeno', 'descripcion': 'De otro edificio',
         'categoria': 'otro', 'estado': 'activo', 'respuesta_admin': None,
         'adjunto_base64': PNG, 'adjunto_nombre': 'ajena.png',
         'adjunto_mime': 'image/png', 'created_at': '2026-08-01T10:00:00+00:00',
         'updated_at': '2026-08-01T10:00:00+00:00'},
    ]
    return base['reclamos']


# ── El listado ────────────────────────────────────────────────────────────────

def test_lista_solo_los_de_sus_edificios(admin, reclamos):
    r = admin.get('/api/admin/reclamos')
    assert r.status_code == 200
    assert [x['id'] for x in r.get_json()] == ['rec-1']


# ── El adjunto ────────────────────────────────────────────────────────────────

def test_el_admin_abre_la_foto_del_reclamo(admin, reclamos):
    r = admin.get('/api/admin/reclamos/rec-1/adjunto')
    assert r.status_code == 200
    assert r.mimetype == 'image/png'
    assert r.data[:8] == bytes.fromhex('89504e470d0a1a0a')


def test_no_abre_el_adjunto_de_otro_edificio(admin, reclamos):
    r = admin.get('/api/admin/reclamos/rec-2/adjunto')
    assert r.status_code == 404


def test_un_reclamo_sin_adjunto_da_404(admin, reclamos):
    reclamos[0]['adjunto_base64'] = None
    assert admin.get('/api/admin/reclamos/rec-1/adjunto').status_code == 404


def test_el_vecino_no_entra_por_la_ruta_del_admin(client, reclamos):
    assert client.get('/api/admin/reclamos/rec-1/adjunto').status_code == 403


# ── La respuesta llega al vecino ──────────────────────────────────────────────

def test_lo_que_escribe_el_admin_lo_ve_el_vecino(admin, client, reclamos):
    admin.put('/api/admin/reclamos/rec-1',
              json={'estado': 'en_proceso', 'respuesta_admin': 'Va el plomero el martes'})
    visto = client.get('/api/reclamos').get_json()[0]
    assert visto['estado'] == 'en_proceso'
    assert visto['respuesta_admin'] == 'Va el plomero el martes'


def test_el_listado_no_arrastra_el_base64_del_adjunto(admin, reclamos):
    """Con select('*') cada fila bajaba la foto entera aunque nadie la abriera."""
    fila = admin.get('/api/admin/reclamos').get_json()[0]
    assert 'adjunto_nombre' in fila
    assert 'adjunto_base64' not in fila


# ── El vecino se entera ───────────────────────────────────────────────────────
# Un reclamo es lo que uno reporta y después espera. Sin aviso, el vecino tiene
# que acordarse de entrar a mirar si le contestaron.

@pytest.fixture
def mails(monkeypatch, app_modulo):
    enviados = []
    monkeypatch.setattr(app_modulo, '_enviar_mail',
                        lambda dest, asunto, html: enviados.append((dest, asunto, html)))
    return enviados


def test_le_avisa_al_vecino_que_le_respondieron(admin, reclamos, mails):
    admin.put('/api/admin/reclamos/rec-1',
              json={'estado': 'en_proceso', 'respuesta_admin': 'Va el plomero el martes'})
    assert len(mails) == 1
    destinatarios, asunto, html = mails[0]
    assert destinatarios == ['uno@test']
    assert 'Pérdida en el baño' in asunto
    assert 'Va el plomero el martes' in html
    assert 'En proceso' in html


def test_sin_respuesta_escrita_igual_avisa_el_cambio_de_estado(admin, reclamos, mails):
    admin.put('/api/admin/reclamos/rec-1', json={'estado': 'en_proceso'})
    assert len(mails) == 1
    assert 'En proceso' in mails[0][2]


def test_si_el_aviso_explota_la_respuesta_igual_queda(admin, reclamos, monkeypatch,
                                                      app_modulo):
    def explota(*_a, **_k):
        raise RuntimeError('Resend caído')
    monkeypatch.setattr(app_modulo, '_enviar_mail', explota)
    r = admin.put('/api/admin/reclamos/rec-1',
                  json={'estado': 'resuelto', 'respuesta_admin': 'Listo'})
    assert r.status_code == 200
    assert reclamos[0]['respuesta_admin'] == 'Listo'
