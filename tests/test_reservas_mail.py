"""Reservar un amenity deja un comprobante en el mail del vecino.

Hasta acá la única confirmación era un toast: el vecino cerraba la pestaña y
no le quedaba nada con la fecha y la hora que había elegido.

Lo que se comprueba abajo es sobre todo que el mail no pueda voltear la
reserva. Es una notificación de algo ya guardado; si Resend está caído, la
reserva tiene que quedar igual.
"""

from datetime import date, timedelta

import pytest


@pytest.fixture
def mails(monkeypatch, app_modulo):
    enviados = []
    monkeypatch.setattr(app_modulo, '_enviar_mail',
                        lambda dest, asunto, html: enviados.append((dest, asunto, html)))
    return enviados


# Siempre en el futuro: el servidor rechaza las reservas en fechas pasadas, y
# una fecha fija hacía que la suite entera empezara a fallar el día después.
FECHA = (date.today() + timedelta(days=10)).isoformat()

RESERVA = {'amenity_id': 'amen-1', 'fecha': FECHA,
           'hora_inicio': '18:00', 'hora_fin': '20:00'}


def test_le_llega_el_mail_al_vecino(client, mails):
    r = client.post('/api/reservas_amenities', json=RESERVA)
    assert r.status_code == 201
    assert len(mails) == 1
    destinatarios, asunto, html = mails[0]
    assert destinatarios == ['uno@test']
    assert 'SUM' in asunto and FECHA in asunto


def test_el_mail_lleva_dia_horario_y_espacio(client, mails):
    client.post('/api/reservas_amenities', json=RESERVA)
    html = mails[0][2]
    for dato in ('SUM', 'Mío', FECHA, '18:00', '20:00'):
        assert dato in html, dato


def test_las_condiciones_de_uso_viajan_si_las_hay(client, base, mails):
    base['amenities'][0]['condiciones_uso'] = 'Dejar limpio'
    client.post('/api/reservas_amenities', json=RESERVA)
    assert 'Dejar limpio' in mails[0][2]


def test_sin_condiciones_no_aparece_el_bloque(client, mails):
    client.post('/api/reservas_amenities', json=RESERVA)
    assert 'Condiciones de uso' not in mails[0][2]


# ── El mail no manda sobre la reserva ─────────────────────────────────────────

def test_si_el_mail_explota_la_reserva_igual_queda(client, base, monkeypatch, app_modulo):
    def explota(*_a, **_k):
        raise RuntimeError('Resend caído')
    monkeypatch.setattr(app_modulo, '_enviar_mail', explota)
    r = client.post('/api/reservas_amenities', json=RESERVA)
    assert r.status_code == 201
    assert len(base['reservas_amenities']) == 1


def test_el_horario_ocupado_se_sigue_rechazando_y_no_manda_mail(client, base, mails):
    assert client.post('/api/reservas_amenities', json=RESERVA).status_code == 201
    r = client.post('/api/reservas_amenities', json=dict(RESERVA, hora_inicio='19:00',
                                                         hora_fin='21:00'))
    assert r.status_code == 400
    assert len(mails) == 1  # sólo el de la primera
