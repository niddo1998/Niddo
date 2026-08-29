"""La liquidación arranca con lo que el consorcio ya tiene configurado.

El recargo del 2º vencimiento se carga una vez, en Configuración, y vale para
todas las liquidaciones de ese edificio. El alta lo tomaba de `d.get(...)` con
default 0 y el modal de nueva liquidación no lo manda: la liquidación nacía en
cero y, si nadie miraba la pestaña de configuración antes de enviarla, salía
sin recargo.
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


@pytest.fixture
def consorcio_configurado(base):
    con = next(c for c in base['consorcios'] if c['id'] == 'cons-1')
    con['recargo_segundo_vto'] = 7.5
    return con


def _crear(admin, **extra):
    payload = {'consorcio_id': 'cons-1', 'periodo': '2026-08',
               'auto_generar': False}
    payload.update(extra)
    return admin.post('/api/liquidaciones', json=payload)


def test_la_liquidacion_hereda_el_recargo_del_consorcio(admin, consorcio_configurado):
    r = _crear(admin)
    assert r.status_code == 201
    assert r.get_json()['interes_2_vto'] == 7.5


def test_lo_que_mande_la_pantalla_le_gana_a_la_configuracion(admin, consorcio_configurado):
    """Editar el recargo de una liquidación puntual sigue siendo posible."""
    r = _crear(admin, interes_2_vto=3)
    assert r.get_json()['interes_2_vto'] == 3


def test_un_recargo_en_cero_explicito_se_respeta(admin, consorcio_configurado):
    """Cero mandado a propósito no es lo mismo que cero por falta de dato."""
    r = _crear(admin, interes_2_vto=0)
    assert r.get_json()['interes_2_vto'] == 0


def test_sin_configuracion_la_liquidacion_nace_en_cero(admin, base):
    r = _crear(admin)
    assert r.get_json()['interes_2_vto'] == 0
