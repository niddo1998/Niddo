"""Enterarse de un mensaje sin tener que ir a mirar.

Los dos paneles preguntan cada veinte segundos, estén en la sección que estén,
si el otro lado escribió. Lo que se prueba es qué cuenta como "sin leer" —sólo
lo que escribió el otro, sólo lo no abierto, sólo de tus edificios— y que lo
que viaja para el aviso sea lo justo: quién, cuándo y cómo empieza.
"""

import pytest


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


def _mensaje(base, **campos):
    fila = {'id': f'msg-{len(base.setdefault("mensajes", [])) + 1}',
            'consorcio_id': 'cons-1', 'vecino_id': 'vec-1', 'autor': 'vecino',
            'cuerpo': 'Hola', 'leido_at': None,
            'created_at': f'2026-09-10T10:{len(base["mensajes"]):02d}:00+00:00'}
    fila.update(campos)
    base['mensajes'].append(fila)
    return fila


# ── El administrador ──────────────────────────────────────────────────────────

def test_sin_mensajes_no_hay_nada(admin, base):
    assert admin.get('/api/admin/mensajes/no-leidos').get_json() == {'sin_leer': 0, 'ultimos': []}


def test_cuenta_lo_que_escribieron_los_vecinos_sin_abrir(admin, base):
    _mensaje(base, cuerpo='Se rompió el portero')
    _mensaje(base, cuerpo='¿Me avisan?')
    _mensaje(base, cuerpo='Ya leído', leido_at='2026-09-10T11:00:00+00:00')
    _mensaje(base, autor='admin', cuerpo='Lo que escribí yo')

    data = admin.get('/api/admin/mensajes/no-leidos').get_json()
    assert data['sin_leer'] == 2


def test_el_aviso_trae_el_ultimo_de_cada_hilo_con_quien_lo_mando(admin, base):
    _mensaje(base, cuerpo='Primero')
    ultimo = _mensaje(base, cuerpo='Segundo')

    data = admin.get('/api/admin/mensajes/no-leidos').get_json()
    assert len(data['ultimos']) == 1
    aviso = data['ultimos'][0]
    assert aviso['id'] == ultimo['id']
    assert aviso['cuerpo'] == 'Segundo'
    assert aviso['vecino'] == 'Uno'
    assert aviso['unidad'] == '1A'
    assert aviso['vecino_id'] == 'vec-1'


def test_no_cuenta_mensajes_de_edificios_ajenos(admin, base):
    _mensaje(base, consorcio_id='cons-2', vecino_id='vec-2', cuerpo='Ajeno')
    assert admin.get('/api/admin/mensajes/no-leidos').get_json()['sin_leer'] == 0


def test_el_vecino_no_entra_por_la_ruta_del_admin(client, base):
    assert client.get('/api/admin/mensajes/no-leidos').status_code == 403


def test_el_texto_largo_viaja_recortado(admin, base):
    _mensaje(base, cuerpo='x' * 500)
    aviso = admin.get('/api/admin/mensajes/no-leidos').get_json()['ultimos'][0]
    assert len(aviso['cuerpo']) <= 141
    assert aviso['cuerpo'].endswith('…')


def test_un_mensaje_que_es_solo_un_archivo_dice_cual(admin, base):
    _mensaje(base, cuerpo='', adjunto_nombre='factura.pdf', adjunto_base64='AAAA')
    aviso = admin.get('/api/admin/mensajes/no-leidos').get_json()['ultimos'][0]
    assert 'factura.pdf' in aviso['cuerpo']
    assert 'adjunto_base64' not in aviso


# ── El vecino ─────────────────────────────────────────────────────────────────

def test_el_vecino_ve_el_ultimo_mensaje_de_la_administracion(client, base):
    _mensaje(base, autor='admin', cuerpo='Mañana viene el técnico')
    ultimo = _mensaje(base, autor='admin', cuerpo='Confirmado a las 10')

    data = client.get('/api/mensajes/no-leidos').get_json()
    assert data['sin_leer'] == 2
    assert data['ultimo']['id'] == ultimo['id']
    assert data['ultimo']['cuerpo'] == 'Confirmado a las 10'


def test_lo_que_escribio_el_vecino_no_le_cuenta_como_sin_leer(client, base):
    _mensaje(base, autor='vecino', cuerpo='Hola')
    data = client.get('/api/mensajes/no-leidos').get_json()
    assert data == {'sin_leer': 0, 'ultimo': None}


def test_abrir_el_hilo_apaga_el_aviso(client, base):
    _mensaje(base, autor='admin', cuerpo='Ya lo vemos')
    client.get('/api/mensajes')
    assert client.get('/api/mensajes/no-leidos').get_json() == {'sin_leer': 0, 'ultimo': None}
