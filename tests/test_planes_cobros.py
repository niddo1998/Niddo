"""Planes por edificio y lo que Niddo le cobra a cada administrador."""

from datetime import date, timedelta

import pytest

import app as app_mod

PLANES = [
    {'id': 'p10', 'nombre': 'Hasta 10 unidades', 'max_unidades': 10, 'precio_mensual': 20000, 'orden': 1},
    {'id': 'p25', 'nombre': 'Hasta 25 unidades', 'max_unidades': 25, 'precio_mensual': 45000, 'orden': 2},
    {'id': 'pmax', 'nombre': 'Más de 25', 'max_unidades': None, 'precio_mensual': 90000, 'orden': 3},
]


def _ufs(cid, n, desde=0):
    return [{'id': f'{cid}-uf{desde + i}', 'consorcio_id': cid, 'numero': str(desde + i)}
            for i in range(n)]


@pytest.fixture
def mundo(base):
    """admin-1 (cliente que paga) con un edificio de 10 unidades."""
    base['planes'] = [dict(p) for p in PLANES]
    base['cobros_niddo'] = []
    base.setdefault('negocio_movimientos', [])
    base.setdefault('negocio_config', [])
    base.setdefault('negocio_prospectos', [])
    base.setdefault('liquidaciones', [])
    base['unidades_funcionales'] = [u for u in base['unidades_funcionales'] if u['consorcio_id'] != 'cons-1']
    base['unidades_funcionales'] += _ufs('cons-1', 10)
    base['administradores'][0].update(gratis_hasta=None, es_fundador=False, siempre_gratis=False,
                                      nombre_contacto='Adm. Uno')
    base['administradores'].append(
        {'id': 'admin-sa', 'auth0_id': 'auth0|sa', 'estado': 'aprobado', 'es_superadmin': True,
         'email': 'sa@test', 'nombre': 'SA', 'ultima_actividad': '2999-01-01T00:00:00+00:00'})
    app_mod.app.config['TESTING'] = True
    return base


def _cliente(sub, rol='admin'):
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': sub, 'email': 'x@test', 'name': 'X', 'role': rol}
    return c


@pytest.fixture
def admin(mundo):
    return _cliente('auth0|admin')


@pytest.fixture
def sa(mundo):
    c = _cliente('auth0|sa')
    assert c.post('/api/superadmin/finanzas/desbloquear', json={'clave': '1165'}).status_code == 200
    return c


# ── El plan sale de la cantidad de unidades ──────────────────────────────────

@pytest.mark.parametrize('n, plan', [(0, 'p10'), (10, 'p10'), (11, 'p25'), (25, 'p25'), (26, 'pmax'), (900, 'pmax')])
def test_plan_para(n, plan):
    assert app_mod.plan_para(n, PLANES)['id'] == plan


def test_el_admin_ve_su_plan(admin):
    d = admin.get('/api/admin/mi-plan').get_json()
    assert d['edificios'][0]['plan'] == 'Hasta 10 unidades'
    assert d['edificios'][0]['unidades'] == 10
    assert d['edificios'][0]['siguiente']['nombre'] == 'Hasta 25 unidades'
    assert d['total'] == 20000
    assert d['sin_cargo'] is None


def test_la_unidad_11_pasa_de_plan_y_avisa(admin, mundo):
    r = admin.post('/api/consorcios/cons-1/unidades', json={'numero': '11'})
    assert r.status_code == 201
    assert 'Hasta 25 unidades' in r.get_json()['aviso_plan']
    assert admin.get('/api/admin/mi-plan').get_json()['total'] == 45000
    # La siguiente ya no avisa: sigue en el mismo plan.
    r = admin.post('/api/consorcios/cons-1/unidades', json={'numero': '12'})
    assert 'aviso_plan' not in r.get_json()


# ── Quién no paga ────────────────────────────────────────────────────────────

def test_motivos_sin_cargo():
    hoy = date(2026, 11, 12)
    assert app_mod.motivo_sin_cargo({'es_superadmin': True}, hoy) == 'equipo'
    assert app_mod.motivo_sin_cargo({'siempre_gratis': True}, hoy) == 'equipo'
    assert app_mod.motivo_sin_cargo({'gratis_hasta': '2027-01-01', 'es_fundador': True}, hoy) == 'fundador'
    assert app_mod.motivo_sin_cargo({'gratis_hasta': '2026-11-12'}, hoy) == 'prueba'
    assert app_mod.motivo_sin_cargo({'gratis_hasta': '2026-11-11'}, hoy) is None
    assert app_mod.motivo_sin_cargo({}, hoy) is None


def test_aprobar_le_da_la_prueba(sa, mundo):
    mundo['administradores'].append({'id': 'admin-n', 'auth0_id': 'auth0|n', 'estado': 'pendiente',
                                     'email': 'n@test', 'nombre': 'Nuevo'})
    sa.post('/api/superadmin/solicitudes/admin-n/aprobar')
    nuevo = next(a for a in mundo['administradores'] if a['id'] == 'admin-n')
    assert nuevo['gratis_hasta'] == (date.today() + timedelta(days=30)).isoformat()


# ── Cobros ───────────────────────────────────────────────────────────────────

def test_generar_cobra_solo_a_quien_paga(sa, mundo):
    mundo['administradores'].append({'id': 'admin-f', 'auth0_id': 'auth0|f', 'estado': 'aprobado',
                                     'email': 'f@test', 'nombre': 'Fundador', 'es_fundador': True,
                                     'gratis_hasta': '2999-01-01'})
    mundo['consorcios'].append({'id': 'cons-f', 'admin_id': 'admin-f', 'nombre': 'Del fundador'})
    mundo['administradores'].append({'id': 'admin-eq', 'auth0_id': 'auth0|eq', 'estado': 'aprobado',
                                     'email': 'eq@test', 'nombre': 'Equipo', 'siempre_gratis': True})
    mundo['consorcios'].append({'id': 'cons-eq', 'admin_id': 'admin-eq', 'nombre': 'Del equipo'})

    r = sa.post('/api/superadmin/cobros/generar', json={'periodo': '2026-11'})
    assert r.get_json()['generados'] == 2          # el del equipo ni se arma
    por_admin = {c['admin_id']: c for c in mundo['cobros_niddo']}
    assert por_admin['admin-1']['estado'] == 'pendiente'
    assert por_admin['admin-1']['total'] == 20000
    assert por_admin['admin-1']['detalle'][0]['plan'] == 'Hasta 10 unidades'
    assert por_admin['admin-f']['estado'] == 'bonificado'
    assert 'admin-eq' not in por_admin

    # Generar dos veces no duplica.
    assert sa.post('/api/superadmin/cobros/generar', json={'periodo': '2026-11'}).get_json()['generados'] == 0


def test_marcar_pagado_entra_en_finanzas_y_deshacer_lo_saca(sa, mundo):
    sa.post('/api/superadmin/cobros/generar', json={'periodo': '2026-11'})
    cid = mundo['cobros_niddo'][0]['id']

    assert sa.post(f'/api/superadmin/cobros/{cid}/pagado').status_code == 200
    mov = mundo['negocio_movimientos'][0]
    assert (mov['tipo'], mov['monto'], mov['categoria']) == ('ingreso', 20000, 'Suscripciones')
    assert sa.post(f'/api/superadmin/cobros/{cid}/pagado').status_code == 409

    resumen = sa.get('/api/superadmin/cobros?periodo=2026-11').get_json()['resumen']
    assert resumen['cobrado'] == 20000

    assert sa.post(f'/api/superadmin/cobros/{cid}/deshacer').status_code == 200
    assert mundo['negocio_movimientos'] == []
    assert mundo['cobros_niddo'][0]['estado'] == 'pendiente'


def test_cobros_estan_bajo_la_llave(mundo):
    c = _cliente('auth0|sa')
    assert c.get('/api/superadmin/cobros').status_code == 423
    assert c.post('/api/superadmin/cobros/generar', json={}).status_code == 423


def test_suscripciones_en_finanzas(sa, mundo):
    mundo['administradores'].append({'id': 'admin-f', 'auth0_id': 'auth0|f', 'estado': 'aprobado',
                                     'email': 'f@test', 'nombre': 'F', 'es_fundador': True,
                                     'gratis_hasta': '2999-01-01'})
    mundo['consorcios'].append({'id': 'cons-f', 'admin_id': 'admin-f', 'nombre': 'F'})
    s = sa.get('/api/superadmin/finanzas').get_json()['suscripciones']
    assert s['mrr'] == 20000
    assert s['potencial'] == 40000
    assert s['cuentas']['pagando'] == 1
    assert s['cuentas']['fundador'] == 1
    assert s['cuentas']['equipo'] == 1
    p10 = next(p for p in s['por_plan'] if p['plan'] == 'Hasta 10 unidades')
    assert (p10['edificios'], p10['pagando'], p10['sin_cargo']) == (2, 1, 1)


# ── Editar planes ────────────────────────────────────────────────────────────

def test_editar_planes(sa, mundo):
    nuevos = [{'id': 'p10', 'nombre': 'Chico', 'max_unidades': 15, 'precio_mensual': '25.000'},
              {'nombre': 'Grande', 'max_unidades': None, 'precio_mensual': 80000}]
    r = sa.put('/api/superadmin/planes', json={'planes': nuevos})
    assert r.status_code == 200
    assert [(p['nombre'], p['precio_mensual']) for p in mundo['planes']] == [('Chico', 25000), ('Grande', 80000)]


@pytest.mark.parametrize('planes', [
    [],
    [{'nombre': 'A', 'max_unidades': 10, 'precio_mensual': 1}],                       # sin plan sin tope
    [{'nombre': 'A', 'max_unidades': None}, {'nombre': 'B', 'max_unidades': None}],   # dos sin tope
    [{'nombre': 'A', 'max_unidades': 10}, {'nombre': 'B', 'max_unidades': 10},
     {'nombre': 'C', 'max_unidades': None}],                                          # tope repetido
])
def test_planes_invalidos(sa, planes):
    assert sa.put('/api/superadmin/planes', json={'planes': planes}).status_code == 400


def test_admin_comun_no_toca_planes_ni_cobros(admin):
    assert admin.put('/api/superadmin/planes', json={'planes': PLANES}).status_code == 404
    assert admin.get('/api/superadmin/cobros').status_code == 404
