"""El alta y la edición manual de gastos validan como la carga masiva (#36).

La carga desde Excel ya rechazaba el monto cero o negativo y la fila sin
descripción (`_monto_excel` y `api_gastos_carga_masiva`). El formulario manual
los dejaba pasar: un gasto de -$ 500 entraba al prorrateo restándole expensa a
todas las UF, y uno sin descripción salía como «–» en la liquidación. Lo que no
se podía convertir (monto «abc», fecha «nada») terminaba en un 500.
"""

import pytest


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    base['gastos'] = []
    return c


def _gasto(**kw):
    d = {'consorcio_id': 'cons-1', 'descripcion': 'Luz', 'monto': 500,
         'fecha_gasto': '2026-10-10', 'categoria': 'electricidad'}
    d.update(kw)
    return d


@pytest.mark.parametrize('cambio', [
    {'monto': 0}, {'monto': -500}, {'monto': '-500'}, {'monto': ''},
    {'monto': 'abc'}, {'monto': '1e12'}, {'monto': None},
    {'descripcion': ''}, {'descripcion': '   '},
    {'fecha_gasto': 'nada'}, {'fecha_gasto': '2026-13-40'},
])
def test_el_alta_rechaza_lo_que_la_carga_masiva_rechaza(admin, base, cambio):
    r = admin.post('/api/gastos', json=_gasto(**cambio))
    assert r.status_code == 400, r.get_json()
    assert r.get_json()['error']
    assert base['gastos'] == []


def test_el_alta_rechaza_tambien_por_formulario(admin, base):
    """La pantalla manda multipart: el monto llega como texto."""
    r = admin.post('/api/gastos', data=_gasto(monto='0'),
                   content_type='multipart/form-data')
    assert r.status_code == 400
    assert base['gastos'] == []


def test_el_alta_valida_sigue_entrando(admin, base):
    r = admin.post('/api/gastos', data=_gasto(monto='45500.50'),
                   content_type='multipart/form-data')
    assert r.status_code == 201
    assert base['gastos'][0]['monto'] == 45500.5
    assert base['gastos'][0]['descripcion'] == 'Luz'


def test_sin_fecha_sigue_tomando_la_de_hoy(admin, base):
    d = _gasto()
    d.pop('fecha_gasto')
    assert admin.post('/api/gastos', json=d).status_code == 201


@pytest.fixture
def con_gasto(admin, base):
    base['gastos'] = [{'id': 'g-1', 'admin_id': 'admin-1', 'consorcio_id': 'cons-1',
                       'descripcion': 'Luz', 'monto': 500.0, 'fecha_gasto': '2026-10-10'}]
    return admin


@pytest.mark.parametrize('cambio', [
    {'monto': 0}, {'monto': -1}, {'monto': 'abc'}, {'descripcion': ''},
    {'fecha_gasto': 'nada'},
])
def test_la_edicion_tampoco_lo_deja_pasar(con_gasto, base, cambio):
    r = con_gasto.put('/api/gastos/g-1', json=cambio)
    assert r.status_code == 400, r.get_json()
    g = base['gastos'][0]
    assert (g['monto'], g['descripcion'], g['fecha_gasto']) == (500.0, 'Luz', '2026-10-10')


def test_la_edicion_parcial_sin_esos_campos_sigue_andando(con_gasto, base):
    r = con_gasto.put('/api/gastos/g-1', json={'pagado': True})
    assert r.status_code == 200
    assert base['gastos'][0]['pagado'] is True


def test_la_edicion_con_un_monto_valido_lo_guarda(con_gasto, base):
    r = con_gasto.put('/api/gastos/g-1', json={'monto': '612.30'})
    assert r.status_code == 200
    assert base['gastos'][0]['monto'] == 612.3
