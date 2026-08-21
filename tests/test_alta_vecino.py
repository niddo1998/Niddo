"""El alta de un vecino la aprueba el administrador.

Antes, con un login alcanzaba para quedarse con cualquier unidad libre de
cualquier edificio de la lista pública y ver sus expensas al instante. El
camino "no encuentro mi unidad" sí dejaba al vecino esperando, pero le escribía
`consorcio_id` igual, así que gastos, comunicados, archivos y medios de pago ya
le respondían con datos del edificio antes de que nadie lo mirara.

El gate no es un decorador nuevo: es que `consorcio_id` y `unidad_id` se quedan
en NULL hasta la aprobación. De esas dos columnas cuelga todo el acceso del
vecino, así que ningún endpoint tiene que acordarse de filtrar por estado. El
bloque del medio comprueba justamente eso, ruta por ruta.
"""

import pytest


@pytest.fixture
def nuevo(base, app_modulo):
    """Un vecino recién creado por Auth0: sin edificio, sin unidad."""
    base['vecinos'].append({
        'id': 'vec-nuevo', 'auth0_id': 'auth0|nuevo', 'nombre': 'Recién llegado',
        'email': 'nuevo@test', 'consorcio_id': None, 'unidad_id': None,
        'unidad': None, 'estado_asociacion': None, 'rol': 'propietario',
    })
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|nuevo', 'email': 'nuevo@test',
                     'name': 'Recién llegado', 'role': 'vecino'}
    return c


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


@pytest.fixture(autouse=True)
def sin_mails(monkeypatch, app_modulo):
    monkeypatch.setattr(app_modulo, '_enviar_mail', lambda *a, **k: None)


def _fila(base, vid='vec-nuevo'):
    return next(v for v in base['vecinos'] if v['id'] == vid)


PEDIDO = {'consorcio_id': 'cons-1', 'unidad_id': 'uf-1'}


# ── Pedir no es entrar ────────────────────────────────────────────────────────

def test_la_solicitud_no_lo_mete_adentro(nuevo, base):
    r = nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    assert r.status_code == 200
    v = _fila(base)
    assert v['estado_asociacion'] == 'pendiente'
    # Lo que importa: las dos columnas de las que cuelga el acceso siguen vacías.
    assert v['consorcio_id'] is None
    assert v['unidad_id'] is None
    assert v['consorcio_solicitado_id'] == 'cons-1'
    assert v['unidad_solicitada_id'] == 'uf-1'


def test_puede_pedir_sin_saber_su_unidad(nuevo, base):
    r = nuevo.post('/api/vecinos/asociar', json={'consorcio_id': 'cons-1'})
    assert r.status_code == 200
    assert _fila(base)['unidad_solicitada_id'] is None


def test_no_pide_una_unidad_de_otro_edificio(nuevo, base):
    r = nuevo.post('/api/vecinos/asociar',
                   json={'consorcio_id': 'cons-1', 'unidad_id': 'uf-2'})
    assert r.status_code == 400
    assert _fila(base)['estado_asociacion'] is None


def test_no_pide_dos_veces(nuevo, base):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    r = nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    assert r.status_code == 409


def test_el_que_ya_esta_adentro_no_vuelve_a_pedir(client, base):
    r = client.post('/api/vecinos/asociar', json={'consorcio_id': 'cons-2'})
    assert r.status_code == 409
    assert _fila(base, 'vec-1')['consorcio_id'] == 'cons-1'


# ── Mientras espera, no ve nada ───────────────────────────────────────────────

@pytest.mark.parametrize('url', [
    '/api/vecinos/cobros',
    '/api/vecinos/gastos',
    '/api/vecinos/gastos-reporte',
    '/api/vecinos/medios-pago',
    '/api/vecinos/mis-unidades',
    '/api/comunicados',
    '/api/archivos',
    '/api/votaciones',
])
def test_el_pendiente_no_ve_datos_del_edificio(nuevo, url):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    r = nuevo.get(url)
    assert r.status_code == 200
    assert r.get_json() == [], f'{url} le contestó con datos'


def test_el_pendiente_no_vota(nuevo, base):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    r = nuevo.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert r.status_code in (403, 404)
    assert base['votos'] == []


def test_el_pendiente_deja_de_enumerar_la_plataforma(nuevo):
    """Sin edificio la lista pública hace falta; con la solicitud hecha, no."""
    assert nuevo.get('/api/public/consorcios').status_code == 200
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    assert nuevo.get('/api/public/consorcios').status_code == 404


def test_puede_mirar_como_viene_su_solicitud(nuevo):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    d = nuevo.get('/api/vecinos/mi-solicitud').get_json()
    assert d['estado'] == 'pendiente'
    assert d['consorcio'] == 'Mío'
    assert d['unidad'] == '1A'


# ── El administrador resuelve ─────────────────────────────────────────────────

def test_la_bandeja_muestra_al_pendiente_con_su_unidad(nuevo, admin):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    filas = admin.get('/api/consorcios/cons-1/vecinos/pendientes').get_json()
    assert [f['id'] for f in filas] == ['vec-nuevo']
    assert filas[0]['unidad_solicitada'] == '1A'


def test_aprobar_lo_mete_adentro(nuevo, admin, base):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    r = admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/aprobar', json={})
    assert r.status_code == 200
    v = _fila(base)
    assert v['estado_asociacion'] == 'aprobado'
    assert v['consorcio_id'] == 'cons-1'
    assert v['unidad_id'] == 'uf-1'
    assert v['unidad'] == '1A'


def test_despues_de_aprobar_si_ve_sus_cobros(nuevo, admin):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/aprobar', json={})
    assert [c['id'] for c in nuevo.get('/api/vecinos/cobros').get_json()] == ['cobro-1']


def test_el_admin_puede_corregir_la_unidad(nuevo, admin, base):
    base['unidades_funcionales'].append({'id': 'uf-1c', 'consorcio_id': 'cons-1',
                                         'numero': '1C'})
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/aprobar',
               json={'unidad_id': 'uf-1c'})
    assert _fila(base)['unidad_id'] == 'uf-1c'


def test_al_que_no_supo_su_unidad_hay_que_elegirsela(nuevo, admin, base):
    nuevo.post('/api/vecinos/asociar', json={'consorcio_id': 'cons-1'})
    r = admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/aprobar', json={})
    assert r.status_code == 400
    assert _fila(base)['consorcio_id'] is None
    r = admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/aprobar',
                   json={'unidad_id': 'uf-1'})
    assert r.status_code == 200
    assert _fila(base)['consorcio_id'] == 'cons-1'


def test_rechazar_lo_deja_afuera_y_con_el_motivo(nuevo, admin, base):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    r = admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/rechazar',
                   json={'motivo': 'Esa unidad la ocupa otro propietario'})
    assert r.status_code == 200
    v = _fila(base)
    assert v['estado_asociacion'] == 'rechazado'
    assert v['consorcio_id'] is None
    assert v['motivo_rechazo'] == 'Esa unidad la ocupa otro propietario'


def test_el_rechazado_ve_el_motivo_y_puede_volver_a_pedir(nuevo, admin, base):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/rechazar',
               json={'motivo': 'Unidad equivocada'})
    d = nuevo.get('/api/vecinos/mi-solicitud').get_json()
    assert d['estado'] == 'rechazado'
    assert d['motivo_rechazo'] == 'Unidad equivocada'
    # La cuenta sigue viva: se equivocó de unidad, no es un intruso.
    assert nuevo.post('/api/vecinos/asociar', json=PEDIDO).status_code == 200


def test_no_se_resuelve_dos_veces(nuevo, admin):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/aprobar', json={})
    r = admin.post('/api/consorcios/cons-1/vecinos/vec-nuevo/aprobar', json={})
    assert r.status_code == 409


# ── Un administrador no resuelve solicitudes de otro edificio ─────────────────

@pytest.fixture
def admin_ajeno(base, app_modulo):
    base['administradores'].append({
        'id': 'admin-2', 'auth0_id': 'auth0|otro', 'estado': 'aprobado',
        'es_superadmin': False, 'email': 'otro@test', 'nombre': 'Otro',
        'ultima_actividad': '2999-01-01T00:00:00+00:00'})
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|otro', 'email': 'otro@test', 'name': 'Otro',
                     'role': 'admin'}
    return c


@pytest.mark.parametrize('accion', ['aprobar', 'rechazar'])
def test_el_admin_de_otro_edificio_no_resuelve(nuevo, admin_ajeno, base, accion):
    nuevo.post('/api/vecinos/asociar', json=PEDIDO)
    r = admin_ajeno.post(f'/api/consorcios/cons-1/vecinos/vec-nuevo/{accion}', json={})
    assert r.status_code == 404
    assert _fila(base)['estado_asociacion'] == 'pendiente'
