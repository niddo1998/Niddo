"""El panel del negocio: Finanzas bajo llave y el plan comercial."""

from datetime import date

import pytest

import app as app_mod


@pytest.fixture
def sa(base):
    base['administradores'].append(
        {'id': 'admin-sa', 'auth0_id': 'auth0|sa', 'estado': 'aprobado',
         'es_superadmin': True, 'email': 'sa@test', 'nombre': 'SA',
         'ultima_actividad': '2999-01-01T00:00:00+00:00'})
    base.setdefault('liquidaciones', [])
    for t in ('negocio_movimientos', 'negocio_prospectos', 'negocio_config'):
        base.setdefault(t, [])
    app_mod.app.config['TESTING'] = True
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|sa', 'email': 'sa@test', 'name': 'SA', 'role': 'admin'}
    return c


def _abrir(c):
    r = c.post('/api/superadmin/finanzas/desbloquear', json={'clave': '1165'})
    assert r.status_code == 200


# ── La llave ─────────────────────────────────────────────────────────────────

def test_finanzas_arranca_bloqueada(sa):
    r = sa.get('/api/superadmin/finanzas')
    assert r.status_code == 423
    assert r.get_json()['bloqueado'] is True


def test_clave_incorrecta_no_abre(sa):
    r = sa.post('/api/superadmin/finanzas/desbloquear', json={'clave': '0000'})
    assert r.status_code == 403
    assert sa.get('/api/superadmin/finanzas').status_code == 423


def test_clave_correcta_abre_y_bloquear_cierra(sa):
    _abrir(sa)
    assert sa.get('/api/superadmin/finanzas').status_code == 200
    sa.post('/api/superadmin/finanzas/bloquear')
    assert sa.get('/api/superadmin/finanzas').status_code == 423


def test_muchos_intentos_obligan_a_esperar(sa):
    for _ in range(app_mod.FINANZAS_MAX_INTENTOS):
        sa.post('/api/superadmin/finanzas/desbloquear', json={'clave': 'x'})
    r = sa.post('/api/superadmin/finanzas/desbloquear', json={'clave': '1165'})
    assert r.status_code == 429


def test_admin_comun_no_llega_ni_con_la_clave(base):
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'A', 'role': 'admin'}
    assert c.post('/api/superadmin/finanzas/desbloquear', json={'clave': '1165'}).status_code == 404
    assert c.get('/api/superadmin/comercial').status_code == 404


def test_la_escritura_tambien_pide_la_clave(sa):
    r = sa.post('/api/superadmin/finanzas/movimientos',
                json={'tipo': 'gasto', 'fecha': '2026-01-01', 'monto': 10})
    assert r.status_code == 423


# ── Los números ──────────────────────────────────────────────────────────────

def test_movimientos_y_resumen(sa, base):
    _abrir(sa)
    hoy = date.today().isoformat()
    assert sa.post('/api/superadmin/finanzas/movimientos',
                   json={'tipo': 'ingreso', 'fecha': hoy, 'monto': '1.500,50',
                         'categoria': 'Suscripciones'}).status_code == 201
    assert sa.post('/api/superadmin/finanzas/movimientos',
                   json={'tipo': 'gasto', 'fecha': hoy, 'monto': 500,
                         'categoria': 'Servidores'}).status_code == 201
    d = sa.get('/api/superadmin/finanzas').get_json()
    assert d['kpis']['ingresos_mes'] == 1500.5
    assert d['kpis']['gastos_mes'] == 500
    assert d['kpis']['resultado_mes'] == 1000.5
    assert d['kpis']['caja'] == 1000.5
    assert d['gastos_por_categoria'][0]['categoria'] == 'Servidores'
    assert len(d['movimientos']) == 2

    mid = d['movimientos'][0]['id']
    assert sa.delete(f'/api/superadmin/finanzas/movimientos/{mid}').status_code == 200
    assert len(base['negocio_movimientos']) == 1


@pytest.mark.parametrize('cuerpo', [
    {'tipo': 'regalo', 'fecha': '2026-01-01', 'monto': 1},
    {'tipo': 'gasto', 'fecha': 'ayer', 'monto': 1},
    {'tipo': 'gasto', 'fecha': '2026-01-01', 'monto': 0},
    {'tipo': 'gasto', 'fecha': '2026-01-01', 'monto': 'mucho'},
])
def test_movimiento_invalido(sa, cuerpo):
    _abrir(sa)
    assert sa.post('/api/superadmin/finanzas/movimientos', json=cuerpo).status_code == 400


def test_burn_y_runway_con_meses_cerrados():
    meses = ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05']
    # Un aporte de capital en un mes cerrado no esconde el burn.
    movs = [{'tipo': 'ingreso', 'fecha': '2026-02-05', 'monto': 10000}]
    movs += [{'tipo': 'gasto', 'fecha': f'{m}-10', 'monto': 1000} for m in meses[1:4]]
    k = app_mod._resumen_finanzas(movs, meses)['kpis']
    assert k['caja'] == 7000
    assert k['burn'] == 1000
    assert k['runway_meses'] == 7.0


@pytest.mark.parametrize('txt, esperado', [
    ('90.000', 90000), ('1.500,50', 1500.5), ('1500.5', 1500.5), ('$ 2.000.000', 2000000),
    ('450', 450), ('-3', None), ('abc', None)])
def test_montos_como_se_escriben_en_argentina(txt, esperado):
    assert app_mod._neg_numero(txt) == esperado


def test_proyeccion_cuenta_solo_clientes_aprobados(sa, base):
    base['consorcios'][0]['admin_id'] = 'admin-1'     # cliente aprobado
    base['consorcios'][1]['admin_id'] = 'admin-sa'    # del equipo: no cuenta
    _abrir(sa)
    sa.put('/api/superadmin/finanzas/proyeccion', json={'precio_uf': 100, 'precio_consorcio': 1000})
    p = sa.get('/api/superadmin/finanzas').get_json()['proyeccion']
    assert (p['consorcios'], p['unidades']) == (1, 1)
    assert p['mensual'] == 1100
    assert p['anual'] == 13200


# ── Plan comercial ───────────────────────────────────────────────────────────

def test_pipeline_alta_cambio_de_etapa_y_baja(sa, base):
    r = sa.post('/api/superadmin/comercial/prospectos',
                json={'nombre': 'Adm. Pérez', 'unidades': '120', 'etapa': 'demo'})
    assert r.status_code == 201
    pid = r.get_json()['id']
    assert sa.patch(f'/api/superadmin/comercial/prospectos/{pid}',
                    json={'etapa': 'piloto'}).status_code == 200
    d = sa.get('/api/superadmin/comercial').get_json()
    assert d['prospectos'][0]['etapa'] == 'piloto'
    assert d['prospectos'][0]['nombre'] == 'Adm. Pérez'
    assert d['valores']['pilotos'] == 1
    assert sa.delete(f'/api/superadmin/comercial/prospectos/{pid}').status_code == 200
    assert base['negocio_prospectos'] == []


def test_prospecto_sin_nombre_o_etapa_rara(sa):
    assert sa.post('/api/superadmin/comercial/prospectos', json={}).status_code == 400
    assert sa.post('/api/superadmin/comercial/prospectos',
                   json={'nombre': 'X', 'etapa': 'casado'}).status_code == 400


def test_metas_muestran_el_avance_real(sa):
    sa.put('/api/superadmin/comercial/metas', json={'metas': [
        {'metrica': 'administradores', 'objetivo': 4},
        {'metrica': 'inventada', 'objetivo': 3},
    ]})
    metas = sa.get('/api/superadmin/comercial').get_json()['metas']
    assert len(metas) == 1
    assert metas[0]['actual'] == 1        # admin-1; el superadmin no cuenta
    assert metas[0]['avance'] == 25


def test_planes_y_notas_se_guardan(sa):
    sa.put('/api/superadmin/comercial/planes', json={'planes': [
        {'nombre': 'Básico', 'precio': '350', 'unidad': 'uf'}, {'nombre': ''}]})
    sa.put('/api/superadmin/comercial/notas', json={'texto': 'Arrancar por Palermo'})
    d = sa.get('/api/superadmin/comercial').get_json()
    assert d['planes'] == [{'nombre': 'Básico', 'precio': 350.0, 'unidad': 'uf', 'descripcion': ''}]
    assert d['notas'] == 'Arrancar por Palermo'
