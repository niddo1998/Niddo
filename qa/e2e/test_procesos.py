"""Procesos automáticos contra el ambiente de pruebas (roadmap #16).

El cron diario corre en Vercel con CRON_SECRET; acá levantar.sh le pone uno
local (`qa-cron-local`, que no es un secreto de nada). Se usa Torre QA Belgrano
para no tocar los cobros que miran los recorridos del navegador.
"""

import os
from datetime import date, timedelta

import requests

BASE = os.environ.get('NIDDO_QA_URL', 'http://localhost:5055')
CRON = {'Authorization': 'Bearer qa-cron-local'}
BELGRANO = 'c0000000-0000-4000-8000-000000000002'   # 2 UF, 0 días de gracia


def _admin():
    s = requests.Session()
    s.get(f'{BASE}/qa/login/admin')
    return s


def _cobros(s, periodo):
    r = s.get(f'{BASE}/api/cobros', params={'consorcio_id': BELGRANO, 'periodo': periodo})
    assert r.status_code == 200, r.text
    return r.json()


def test_el_cron_diario_sin_secreto_no_corre():
    assert requests.get(f'{BASE}/api/cron/diario').status_code == 401
    assert requests.get(f'{BASE}/api/cron/diario',
                        headers={'Authorization': 'Bearer otro'}).status_code == 401


def test_el_cron_diario_vence_lo_impago_y_recuerda_lo_que_vence():
    s = _admin()
    hoy = date.today()
    for periodo, vto in (('2001-01', hoy - timedelta(days=2)),    # ya vencido
                         ('2001-02', hoy + timedelta(days=3))):   # vence en 3 días
        r = s.post(f'{BASE}/api/cobros/generar', json={
            'consorcio_id': BELGRANO, 'periodo': periodo,
            'monto_base': 1000, 'fecha_vencimiento': vto.isoformat()})
        assert r.status_code == 200 and r.json()['generados'] == 2, r.text

    r = requests.post(f'{BASE}/api/cron/diario', headers=CRON)
    assert r.status_code == 200, r.text
    assert r.json()['vencidos'] >= 2
    assert r.json()['recordatorios'] >= 2
    assert {c['estado'] for c in _cobros(s, '2001-01')} == {'vencido'}
    assert {c['estado'] for c in _cobros(s, '2001-02')} == {'pendiente'}
    mora = s.get(f'{BASE}/api/cobros/mora', params={'consorcio_id': BELGRANO}).json()
    assert {c['periodo'] for c in mora} == {'2001-01'}

    # Correrlo de nuevo no vuelve a vencer ni a recordar lo mismo.
    otra = requests.post(f'{BASE}/api/cron/diario', headers=CRON).json()
    assert otra == {'recordatorios': 0, 'vencidos': 0}


def test_el_cron_horario_corre():
    r = requests.post(f'{BASE}/api/cron/cada-hora', headers=CRON)
    assert r.status_code == 200 and 'reservas' in r.json(), r.text
