"""El vecino corrige su propio perfil.

`/api/me` era sólo GET: para arreglar un nombre mal escrito había que entrar a
la base. La parte que importa de estos tests no es que el PUT guarde, sino todo
lo que tiene que seguir sin poder tocarse: email, identidad y permisos.
"""

import pytest


def _perfil(base, vid='vec-1'):
    return next(v for v in base['vecinos'] if v['id'] == vid)


def test_guarda_nombre_y_telefono(client, base):
    r = client.put('/api/me', json={'nombre': 'Uno Corregido',
                                    'telefono': '+54 11 5555'})
    assert r.status_code == 200
    assert _perfil(base)['nombre'] == 'Uno Corregido'
    assert _perfil(base)['telefono'] == '+54 11 5555'


def test_devuelve_el_perfil_ya_guardado(client):
    r = client.put('/api/me', json={'nombre': 'Uno Corregido'})
    assert r.get_json()['nombre'] == 'Uno Corregido'


def test_recorta_los_espacios(client, base):
    client.put('/api/me', json={'nombre': '  Uno  '})
    assert _perfil(base)['nombre'] == 'Uno'


def test_no_deja_el_nombre_vacio(client, base):
    r = client.put('/api/me', json={'nombre': '   '})
    assert r.status_code == 400
    assert _perfil(base)['nombre'] == 'Uno'


# ── Lo que no se toca ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('campo,valor', [
    ('email', 'otro@test'),
    ('auth0_id', 'auth0|dos'),
    ('consorcio_id', 'cons-2'),
    ('unidad_id', 'uf-2'),
    ('rol', 'administrador'),
    ('id', 'vec-2'),
])
def test_un_campo_fuera_de_la_lista_blanca_se_ignora(client, base, campo, valor):
    antes = dict(_perfil(base))
    r = client.put('/api/me', json={campo: valor})
    # Sin ningún campo editable en el body no hay nada que hacer: 400.
    assert r.status_code == 400
    assert _perfil(base)[campo] == antes[campo]


def test_el_campo_prohibido_no_viaja_de_polizon(client, base):
    """Mezclado con uno válido, el prohibido tampoco tiene que entrar."""
    r = client.put('/api/me', json={'nombre': 'Uno', 'consorcio_id': 'cons-2'})
    assert r.status_code == 200
    assert _perfil(base)['consorcio_id'] == 'cons-1'


def test_no_toca_el_perfil_de_otro_vecino(client, base):
    client.put('/api/me', json={'nombre': 'Uno Corregido'})
    assert _perfil(base, 'vec-2')['nombre'] == 'Dos'


def test_sin_sesion_no_hay_perfil(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    assert c.put('/api/me', json={'nombre': 'x'}).status_code == 401
