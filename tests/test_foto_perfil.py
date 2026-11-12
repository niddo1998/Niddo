"""La foto de la cuenta de Google se guarda en la sesión para el avatar del panel."""

import pytest

import app as app_mod


def _entrar(monkeypatch, picture):
    monkeypatch.setattr(app_mod.auth0, 'authorize_access_token', lambda: {'userinfo': {
        'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'Admin Test', 'picture': picture}})
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['pending_role'] = 'admin'
    c.get('/auth/callback')
    with c.session_transaction() as s:
        return c, s['user'].get('picture')


def test_la_foto_queda_en_la_sesion(base, monkeypatch):
    c, foto = _entrar(monkeypatch, 'https://lh3.googleusercontent.com/a/foto')
    assert foto == 'https://lh3.googleusercontent.com/a/foto'
    html = c.get('/dashboard/admin').get_data(as_text=True)
    assert 'https://lh3.googleusercontent.com/a/foto' in html
    assert 'id="menu-cuenta"' in html


@pytest.mark.parametrize('rara', ['javascript:alert(1)', 'http://inseguro/foto.png', '', None])
def test_solo_se_acepta_https(base, monkeypatch, rara):
    _, foto = _entrar(monkeypatch, rara)
    assert foto == ''
