"""Los avisos push: los que salen de una acción y los programados.

No se prueba el Web Push en sí (eso es pywebpush): se reemplaza `push_a` y se
mira a quién le habla, qué le dice y que no repita.
"""

from datetime import date, datetime

import pytest

import app as app_mod


@pytest.fixture
def pushes(monkeypatch):
    enviados = []
    monkeypatch.setattr(app_mod, 'push_disponible', lambda: True)
    monkeypatch.setattr(app_mod, 'push_a',
                        lambda tipo, ids, titulo, cuerpo, url='/', etiqueta=None:
                        enviados.append({'tipo': tipo, 'ids': sorted(i for i in set(ids) if i),
                                         'titulo': titulo, 'cuerpo': cuerpo}) or 1)
    return enviados


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'Admin', 'role': 'admin'}
    return c


# ── Al instante ───────────────────────────────────────────────────────────────

def test_aceptar_un_pago_le_avisa_al_vecino(admin, base, pushes):
    base['avisos_pago'] = [{'id': 'av-1', 'consorcio_id': 'cons-1', 'vecino_id': 'vec-1',
                            'cobro_id': 'cobro-1', 'monto': 100, 'estado': 'pendiente',
                            'fecha_pago': '2026-08-05', 'unidad_id': 'uf-1'}]
    admin.put('/api/admin/avisos-pago/av-1', json={'estado': 'aceptado'})
    assert pushes[-1]['ids'] == ['vec-1']
    assert pushes[-1]['titulo'] == 'Tu pago quedó registrado'


def test_resolver_un_reclamo_le_avisa_al_vecino(admin, base, pushes, monkeypatch):
    monkeypatch.setattr(app_mod, '_mail_respuesta_reclamo', lambda *a, **k: None)
    base['reclamos'] = [{'id': 'rec-1', 'consorcio_id': 'cons-1', 'vecino_id': 'vec-1',
                         'titulo': 'Gotera', 'estado': 'activo'}]
    base['reclamo_mensajes'] = []
    admin.put('/api/admin/reclamos/rec-1', json={'estado': 'resuelto'})
    assert pushes[-1] == {'tipo': 'vecino', 'ids': ['vec-1'],
                          'titulo': 'Tu reclamo quedó resuelto', 'cuerpo': 'Gotera'}


# ── Programados ───────────────────────────────────────────────────────────────

@pytest.fixture
def cron(base, pushes, monkeypatch, app_modulo):
    monkeypatch.setenv('CRON_SECRET', 'shh')
    base['avisos_enviados'] = []
    base['consorcios'][0]['dias_gracia_mora'] = 2
    app_modulo.app.config['TESTING'] = True
    return app_modulo.app.test_client()


def _cobro(base, vto, estado='pendiente'):
    base['cobros'] = [{'id': 'cobro-1', 'consorcio_id': 'cons-1', 'unidad_id': 'uf-1',
                       'estado': estado, 'total': 100, 'periodo': '2026-08',
                       'fecha_vencimiento': vto}]


def test_el_cron_pide_el_secreto(cron):
    assert cron.post('/api/cron/diario').status_code == 401
    assert cron.post('/api/cron/diario', headers={'Authorization': 'Bearer otro'}).status_code == 401


def test_sin_secreto_configurado_no_corre(cron, monkeypatch):
    monkeypatch.delenv('CRON_SECRET')
    assert cron.post('/api/cron/diario', headers={'Authorization': 'Bearer '}).status_code == 401


def test_recuerda_tres_dias_antes_del_vencimiento(base, pushes, cron):
    _cobro(base, '2026-08-13')
    app_mod.avisos_diarios(hoy=date(2026, 8, 10))
    assert pushes[0]['ids'] == ['vec-1']
    assert pushes[0]['titulo'] == 'Tu expensa vence el 13/08'


def test_el_dia_del_vencimiento_avisa_que_vence_hoy(base, pushes, cron):
    _cobro(base, '2026-08-10')
    app_mod.avisos_diarios(hoy=date(2026, 8, 10))
    assert pushes[0]['titulo'] == 'Hoy vence tu expensa'


def test_no_repite_el_mismo_recordatorio(base, pushes, cron):
    _cobro(base, '2026-08-13')
    app_mod.avisos_diarios(hoy=date(2026, 8, 10))
    app_mod.avisos_diarios(hoy=date(2026, 8, 10))
    assert len(pushes) == 1


def test_pasados_los_dias_de_gracia_queda_vencido(base, pushes, cron):
    _cobro(base, '2026-08-10')
    app_mod.avisos_diarios(hoy=date(2026, 8, 12))     # 2 días: dentro de la gracia
    assert base['cobros'][0]['estado'] == 'pendiente'
    app_mod.avisos_diarios(hoy=date(2026, 8, 13))
    assert base['cobros'][0]['estado'] == 'vencido'
    titulos = [p['titulo'] for p in pushes]
    assert 'Tu expensa venció' in titulos
    assert '1 expensa pasó a vencida' in titulos


def test_un_cobro_pagado_no_recibe_recordatorios(base, pushes, cron):
    _cobro(base, '2026-08-10', estado='pagado')
    app_mod.avisos_diarios(hoy=date(2026, 8, 20))
    assert pushes == []
    assert base['cobros'][0]['estado'] == 'pagado'


def test_el_endpoint_diario_corre_con_el_secreto(base, cron):
    _cobro(base, '2099-01-01')
    r = cron.post('/api/cron/diario', headers={'Authorization': 'Bearer shh'})
    assert r.status_code == 200
    assert r.get_json() == {'recordatorios': 0, 'vencidos': 0}


def test_recuerda_la_reserva_que_empieza_en_dos_horas(base, pushes, cron):
    base['reservas_amenities'] = [
        {'id': 'res-1', 'vecino_id': 'vec-1', 'fecha': '2026-08-10', 'hora_inicio': '20:00:00',
         'estado': 'confirmada', 'amenities': {'nombre': 'SUM'}},
        {'id': 'res-2', 'vecino_id': 'vec-1', 'fecha': '2026-08-10', 'hora_inicio': '23:30:00',
         'estado': 'confirmada', 'amenities': {'nombre': 'Parrilla'}},
    ]
    ahora = datetime(2026, 8, 10, 18, 0, tzinfo=app_mod.ZONA_AR)
    app_mod.avisos_cada_hora(ahora=ahora)
    app_mod.avisos_cada_hora(ahora=ahora)
    assert [p['titulo'] for p in pushes] == ['Hoy a las 20:00 tenés SUM']
