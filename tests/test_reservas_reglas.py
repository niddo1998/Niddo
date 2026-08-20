"""Las reglas de una reserva más allá del solapamiento de horarios.

La validación original miraba una sola cosa: que el horario no pisara otra
reserva del mismo amenity. Todo lo demás pasaba.
"""

from datetime import date, timedelta

import pytest


@pytest.fixture(autouse=True)
def sin_mails(monkeypatch, app_modulo):
    """El mail de confirmación no es lo que se prueba acá."""
    monkeypatch.setattr(app_modulo, '_enviar_mail', lambda *a, **k: None)


def _dia(delta):
    return (date.today() + timedelta(days=delta)).isoformat()


def _reserva(**extra):
    return {'amenity_id': 'amen-1', 'fecha': _dia(3),
            'hora_inicio': '18:00', 'hora_fin': '20:00', **extra}


# ── Fechas ────────────────────────────────────────────────────────────────────

def test_no_reserva_para_ayer(client, base):
    r = client.post('/api/reservas_amenities', json=_reserva(fecha=_dia(-1)))
    assert r.status_code == 400
    assert 'pasó' in r.get_json()['error']
    assert base['reservas_amenities'] == []


def test_hoy_todavia_se_puede(client, base):
    r = client.post('/api/reservas_amenities', json=_reserva(fecha=_dia(0)))
    assert r.status_code == 201
    assert len(base['reservas_amenities']) == 1


def test_una_fecha_con_forma_de_cualquier_cosa_se_rechaza(client, base):
    r = client.post('/api/reservas_amenities', json=_reserva(fecha='el jueves'))
    assert r.status_code == 400
    assert base['reservas_amenities'] == []


# ── Lo que ya andaba tiene que seguir andando ─────────────────────────────────

def test_reserva_a_futuro(client, base):
    assert client.post('/api/reservas_amenities', json=_reserva()).status_code == 201


def test_el_horario_dado_vuelta_se_rechaza(client):
    r = client.post('/api/reservas_amenities',
                    json=_reserva(hora_inicio='20:00', hora_fin='18:00'))
    assert r.status_code == 400


def test_el_solapamiento_se_sigue_rechazando(client):
    assert client.post('/api/reservas_amenities', json=_reserva()).status_code == 201
    r = client.post('/api/reservas_amenities',
                    json=_reserva(hora_inicio='19:00', hora_fin='21:00'))
    assert r.status_code == 400
