"""Un vecino no puede mirar las expensas de otro.

El hermano de `test_pertenencia.py`, del lado del vecino. Ahí el UUID ajeno
viaja en la URL; acá viaja casi siempre en la query string —`?unidad_id=`—,
que es peor de ver porque parece un filtro y no un permiso.

Las expensas cuelgan de la unidad funcional, no del vecino, así que las tres
rutas de cobros reciben una unidad y ninguna comprobaba que fuera suya. Cada
test de abajo es esa request: sesión de `vec-1`, unidad de `vec-2`.

El último bloque es el simétrico y es el que importa que no se rompa: sobre lo
propio, todo tiene que seguir devolviendo exactamente lo de antes.
"""

import pytest

# El doble de Supabase y el arranque del entorno viven en test_pertenencia.py;
# duplicarlos acá los dejaría desincronizados a la primera corrección.
from test_pertenencia import FakeSupabase, app_mod


# ── Datos ─────────────────────────────────────────────────────────────────────
# Dos vecinos, dos edificios. Todo lo que termina en `-2` es del otro.
# `vec-1` tiene dos unidades para cubrir el caso multi-unidad, que es donde el
# orden de `unidades_del_vecino()` decide qué abre la pantalla por defecto.

def _datos():
    return {
        'vecinos': [
            {'id': 'vec-1', 'auth0_id': 'auth0|uno', 'consorcio_id': 'cons-1',
             'unidad_id': 'uf-1', 'unidad': '1A', 'nombre': 'Uno'},
            {'id': 'vec-2', 'auth0_id': 'auth0|dos', 'consorcio_id': 'cons-2',
             'unidad_id': 'uf-2', 'unidad': '2B', 'nombre': 'Dos'},
            {'id': 'vec-nuevo', 'auth0_id': 'auth0|nuevo', 'consorcio_id': None,
             'unidad_id': None, 'nombre': 'Recién llegado'},
        ],
        'vecinos_unidades': [
            {'id': 'vu-1', 'vecino_id': 'vec-1', 'unidad_id': 'uf-1b', 'activo': True},
        ],
        'consorcios': [
            {'id': 'cons-1', 'admin_id': 'admin-1', 'nombre': 'Mío'},
            {'id': 'cons-2', 'admin_id': 'admin-2', 'nombre': 'Ajeno'},
        ],
        'unidades_funcionales': [
            {'id': 'uf-1',  'consorcio_id': 'cons-1', 'numero': '1A'},
            {'id': 'uf-1b', 'consorcio_id': 'cons-1', 'numero': '1B'},
            {'id': 'uf-2',  'consorcio_id': 'cons-2', 'numero': '2B'},
        ],
        'cobros': [
            {'id': 'cobro-1', 'consorcio_id': 'cons-1', 'unidad_id': 'uf-1',
             'estado': 'pendiente', 'total': 100, 'monto_base': 100,
             'interes_mora': 0, 'periodo': '2026-08'},
            {'id': 'cobro-2', 'consorcio_id': 'cons-2', 'unidad_id': 'uf-2',
             'estado': 'pendiente', 'total': 999, 'monto_base': 999,
             'interes_mora': 0, 'periodo': '2026-08'},
        ],
        'gastos': [
            {'id': 'gasto-2', 'consorcio_id': 'cons-2', 'monto': 999,
             'descripcion': 'Ajeno', 'fecha_gasto': '2026-08-01'},
        ],
        'comprobantes_gastos': [
            {'id': 'comp-2', 'gasto_id': 'gasto-2', 'archivo_base64': 'eA==',
             'archivo_nombre': 'factura.pdf', 'mime_type': 'application/pdf'},
        ],
        'amenities': [{'id': 'amen-2', 'consorcio_id': 'cons-2', 'nombre': 'SUM'}],
        'administradores': [],
    }


@pytest.fixture
def base(monkeypatch):
    store = _datos()
    monkeypatch.setattr(app_mod, 'supabase', FakeSupabase(store))
    return store


def _cliente(base, sub='auth0|uno'):
    app_mod.app.config['TESTING'] = True
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': sub, 'email': 'uno@test', 'name': 'Uno', 'role': 'vecino'}
    return c


@pytest.fixture
def client(base):
    return _cliente(base)


# ── La unidad del otro ────────────────────────────────────────────────────────

@pytest.mark.parametrize('url', [
    '/api/vecinos/cobros?unidad_id=uf-2',
    '/api/vecinos/cobro-actual?unidad_id=uf-2',
    '/api/vecinos/cobros/cobro-2/cupon',
])
def test_no_puede_ver_expensas_ajenas(client, url):
    assert client.get(url).status_code == 404


def test_el_cupon_ajeno_no_filtra_el_importe(client):
    """El 404 tiene que llegar antes de armar el PDF, no después."""
    res = client.get('/api/vecinos/cobros/cobro-2/cupon')
    assert res.status_code == 404
    assert b'999' not in res.data
    assert b'PDF' not in res.data


def test_no_puede_ver_el_comprobante_de_otro_edificio(client):
    assert client.get('/api/gastos/gasto-2/comprobante').status_code == 404


def test_no_puede_listar_los_amenities_de_otro_edificio(client):
    assert client.get('/api/consorcios/cons-2/amenities').status_code == 404


# ── Enumerar la plataforma ────────────────────────────────────────────────────

def test_un_vecino_ya_asociado_no_lista_todos_los_consorcios(client):
    assert client.get('/api/public/consorcios').status_code == 404


def test_un_vecino_ya_asociado_no_baja_el_padron_de_otro(client):
    assert client.get('/api/public/consorcios/cons-2/unidades-libres').status_code == 404


def test_durante_el_alta_si_puede_elegir_consorcio(base):
    """El cerrojo no puede cerrarle la puerta a quien todavía no entró."""
    c = _cliente(base, sub='auth0|nuevo')
    res = c.get('/api/public/consorcios')
    assert res.status_code == 200
    assert {f['id'] for f in res.get_json()} == {'cons-1', 'cons-2'}

    res = c.get('/api/public/consorcios/cons-2/unidades-libres')
    assert res.status_code == 200
    assert [u['id'] for u in res.get_json()] == ['uf-2']


# ── Lo propio sigue andando ───────────────────────────────────────────────────

def test_ve_su_expensa_pidiendo_su_unidad(client):
    res = client.get('/api/vecinos/cobros?unidad_id=uf-1')
    assert res.status_code == 200
    assert [c['id'] for c in res.get_json()] == ['cobro-1']


def test_ve_su_segunda_unidad(client):
    """`vec-1` tiene uf-1b por `vecinos_unidades`: también es suya."""
    assert client.get('/api/vecinos/cobros?unidad_id=uf-1b').status_code == 200


def test_sin_unidad_id_abre_la_de_siempre(client):
    """Sin parámetro seguía la unidad de `vecinos`, y tiene que seguir siendo esa.

    Es lo que ve el vecino al entrar. Si el orden de `unidades_del_vecino()`
    cambiara, quien tiene dos unidades abriría la pantalla en la otra.
    """
    res = client.get('/api/vecinos/cobro-actual')
    assert res.status_code == 200
    assert res.get_json()['id'] == 'cobro-1'


def test_baja_el_cupon_de_su_cobro(client):
    res = client.get('/api/vecinos/cobros/cobro-1/cupon')
    assert res.status_code == 200
    assert res.data.startswith(b'%PDF')
