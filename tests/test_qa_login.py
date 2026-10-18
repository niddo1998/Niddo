"""El login de QA (/qa/login/<quien>) nunca puede existir fuera del ambiente de pruebas.

Es una puerta trasera a propósito: entra sin Auth0. Por eso la ruta solo se
registra con NIDDO_QA_LOGIN=1, en modo local y fuera de Vercel. Estos tests
cuidan las tres condiciones.
"""

import os

import app as app_mod


def _con_env(monkeypatch, **valores):
    for k in ('NIDDO_QA_LOGIN', 'NIDDO_LOCAL', 'FLASK_ENV', 'VERCEL'):
        monkeypatch.delenv(k, raising=False)
    for k, v in valores.items():
        monkeypatch.setenv(k, v)


def test_habilitado_solo_con_flag_local_y_fuera_de_vercel(monkeypatch):
    _con_env(monkeypatch, NIDDO_QA_LOGIN='1')
    monkeypatch.setattr(app_mod, '_ES_LOCAL', True)
    assert app_mod.qa_login_habilitado() is True


def test_sin_flag_no_se_habilita(monkeypatch):
    _con_env(monkeypatch)
    monkeypatch.setattr(app_mod, '_ES_LOCAL', True)
    assert app_mod.qa_login_habilitado() is False


def test_en_vercel_no_se_habilita_aunque_esten_los_flags(monkeypatch):
    _con_env(monkeypatch, NIDDO_QA_LOGIN='1', VERCEL='1')
    monkeypatch.setattr(app_mod, '_ES_LOCAL', True)
    assert app_mod.qa_login_habilitado() is False


def test_fuera_de_modo_local_no_se_habilita(monkeypatch):
    _con_env(monkeypatch, NIDDO_QA_LOGIN='1')
    monkeypatch.setattr(app_mod, '_ES_LOCAL', False)
    assert app_mod.qa_login_habilitado() is False


def test_la_ruta_no_existe_en_el_arranque_de_los_tests():
    # conftest.py no prende NIDDO_QA_LOGIN: así arranca producción.
    assert os.environ.get('NIDDO_QA_LOGIN') != '1'
    reglas = {r.rule for r in app_mod.app.url_map.iter_rules()}
    assert '/qa/login/<quien>' not in reglas
