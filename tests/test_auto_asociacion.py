"""El vecino que el administrador cargó en el padrón entra solo.

Es el único camino que no pasa por la aprobación, y está bien que lo sea: la
verificación la hizo el administrador cuando escribió el mail en la unidad.

Tenía un bug anterior a todo esto. Escribía `consorcio_id` y `unidad` —el
número, texto— pero no `unidad_id`, que es de donde cuelga todo lo que el
vecino ve. El resultado era entrar al panel del edificio correcto y no
encontrar una sola expensa.
"""

import pytest


@pytest.fixture
def padron(base):
    """Una UF cargada por el admin con el mail del vecino, sin reclamar."""
    base['unidades_funcionales'].append({
        'id': 'uf-1d', 'consorcio_id': 'cons-1', 'numero': '1D',
        'vecino_email': 'esperado@test', 'vecino_id': None,
    })
    return base


def _alta(app_modulo, email='esperado@test', sub='auth0|esperado'):
    return app_modulo.upsert_user('vecino', sub, email, 'Esperado')


def test_entra_sin_pasar_por_la_aprobacion(padron, app_modulo):
    fila = _alta(app_modulo)
    v = next(x for x in padron['vecinos'] if x['id'] == fila['id'])
    assert v['consorcio_id'] == 'cons-1'
    assert v['estado_asociacion'] == 'aprobado'


def test_le_queda_la_unidad_y_no_solo_el_numero(padron, app_modulo):
    """El bug: sin unidad_id el vecino no veía ninguna expensa."""
    fila = _alta(app_modulo)
    v = next(x for x in padron['vecinos'] if x['id'] == fila['id'])
    assert v['unidad_id'] == 'uf-1d'
    assert v['unidad'] == '1D'


def test_la_unidad_queda_reclamada(padron, app_modulo):
    fila = _alta(app_modulo)
    uf = next(u for u in padron['unidades_funcionales'] if u['id'] == 'uf-1d')
    assert uf['vecino_id'] == fila['id']


def test_ve_sus_cobros_al_entrar(padron, app_modulo):
    """La prueba de que el arreglo sirve: la pantalla trae datos."""
    padron['cobros'].append({
        'id': 'cobro-1d', 'consorcio_id': 'cons-1', 'unidad_id': 'uf-1d',
        'estado': 'pendiente', 'total': 50, 'monto_base': 50,
        'interes_mora': 0, 'periodo': '2026-08',
    })
    _alta(app_modulo)
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|esperado', 'email': 'esperado@test',
                     'name': 'Esperado', 'role': 'vecino'}
    assert [x['id'] for x in c.get('/api/vecinos/cobros').get_json()] == ['cobro-1d']


# ── Lo que no tiene que pasar ─────────────────────────────────────────────────

def test_un_mail_que_no_esta_en_el_padron_no_entra(padron, app_modulo):
    fila = _alta(app_modulo, email='cualquiera@test', sub='auth0|cualquiera')
    v = next(x for x in padron['vecinos'] if x['id'] == fila['id'])
    assert v.get('consorcio_id') is None
    assert v.get('estado_asociacion') is None


def test_no_le_roba_la_unidad_a_quien_ya_la_tiene(padron, app_modulo):
    """Con vecino_id ya cargado la unidad está tomada: no se reasigna."""
    padron['unidades_funcionales'][-1]['vecino_id'] = 'vec-1'
    fila = _alta(app_modulo)
    v = next(x for x in padron['vecinos'] if x['id'] == fila['id'])
    assert v.get('consorcio_id') is None


def test_al_que_ya_esta_adentro_no_lo_toca(padron, app_modulo):
    """Segundo login: no vuelve a correr la auto-asociación."""
    _alta(app_modulo)
    padron['unidades_funcionales'].append({
        'id': 'uf-1e', 'consorcio_id': 'cons-1', 'numero': '1E',
        'vecino_email': 'esperado@test', 'vecino_id': None,
    })
    fila = _alta(app_modulo)
    v = next(x for x in padron['vecinos'] if x['id'] == fila['id'])
    assert v['unidad_id'] == 'uf-1d'
