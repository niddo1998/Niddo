"""Un superadmin aprobado entra directo a /superadmin, elija el rol que elija."""

import pytest

import app as app_mod


@pytest.fixture
def con_superadmin(base, monkeypatch):
    base['administradores'].append(
        {'id': 'admin-sa', 'auth0_id': 'auth0|sa', 'estado': 'aprobado',
         'es_superadmin': True, 'email': 'sa@test', 'nombre': 'SA',
         'ultima_actividad': '2999-01-01T00:00:00+00:00'})
    app_mod.app.config['TESTING'] = True
    return base


def _callback(monkeypatch, sub, email, rol):
    monkeypatch.setattr(app_mod.auth0, 'authorize_access_token',
                        lambda: {'userinfo': {'sub': sub, 'email': email, 'name': email}})
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['pending_role'] = rol
    return c, c.get('/auth/callback')


@pytest.mark.parametrize('rol', ['admin', 'vecino'])
def test_superadmin_va_al_panel(con_superadmin, monkeypatch, rol):
    c, r = _callback(monkeypatch, 'auth0|sa', 'sa@test', rol)
    assert r.status_code == 302
    assert r.headers['Location'].endswith('/superadmin')
    with c.session_transaction() as s:
        assert s['user']['role'] == 'admin'
    # No se le crea una fila de vecino por haber elegido ese rol.
    assert not any(v.get('auth0_id') == 'auth0|sa' for v in con_superadmin['vecinos'])


def test_admin_comun_sigue_yendo_a_su_dashboard(con_superadmin, monkeypatch):
    _, r = _callback(monkeypatch, 'auth0|admin', 'admin@test', 'admin')
    assert r.headers['Location'].endswith('/dashboard/admin')


def test_superadmin_pendiente_no_va_al_panel(con_superadmin, monkeypatch):
    con_superadmin['administradores'][-1]['estado'] = 'pendiente'
    _, r = _callback(monkeypatch, 'auth0|sa', 'sa@test', 'vecino')
    assert r.headers['Location'].endswith('/dashboard/vecino')


def test_mismo_mail_con_otra_identidad_no_va_al_panel(con_superadmin, monkeypatch):
    _, r = _callback(monkeypatch, 'auth0|otro', 'sa@test', 'vecino')
    assert '/superadmin' not in r.headers['Location']


def test_login_con_sesion_abierta_manda_al_panel(con_superadmin):
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|sa', 'email': 'sa@test', 'name': 'SA', 'role': 'admin'}
    r = c.get('/login')
    assert r.headers['Location'].endswith('/superadmin')
