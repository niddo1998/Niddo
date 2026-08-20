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


# ── Capacidad del espacio ─────────────────────────────────────────────────────
# `capacidad_maxima` existe desde v3 y son personas; la reserva no decía cuántas
# venían, así que no había contra qué compararla.

def test_no_entra_mas_gente_que_la_capacidad(client, base):
    base['amenities'][0]['capacidad_maxima'] = 10
    r = client.post('/api/reservas_amenities', json=_reserva(cantidad_personas=11))
    assert r.status_code == 400
    assert '10 personas' in r.get_json()['error']
    assert base['reservas_amenities'] == []


def test_justo_la_capacidad_entra(client, base):
    base['amenities'][0]['capacidad_maxima'] = 10
    assert client.post('/api/reservas_amenities',
                       json=_reserva(cantidad_personas=10)).status_code == 201


def test_sin_capacidad_cargada_no_hay_tope(client, base):
    assert client.post('/api/reservas_amenities',
                       json=_reserva(cantidad_personas=500)).status_code == 201


def test_la_cantidad_queda_guardada(client, base):
    client.post('/api/reservas_amenities', json=_reserva(cantidad_personas=6))
    assert base['reservas_amenities'][0]['cantidad_personas'] == 6


def test_cero_personas_no_es_una_reserva(client, base):
    r = client.post('/api/reservas_amenities', json=_reserva(cantidad_personas=0))
    assert r.status_code == 400
    assert base['reservas_amenities'] == []


def test_una_cantidad_que_no_es_numero_se_rechaza(client, base):
    r = client.post('/api/reservas_amenities', json=_reserva(cantidad_personas='muchas'))
    assert r.status_code == 400
    assert base['reservas_amenities'] == []


def test_no_declarar_la_cantidad_sigue_siendo_valido(client, base):
    """El campo es opcional: las reservas viejas no lo tienen."""
    assert client.post('/api/reservas_amenities', json=_reserva()).status_code == 201
    assert base['reservas_amenities'][0]['cantidad_personas'] is None


# ── Cupo mensual por vecino ───────────────────────────────────────────────────

def test_respeta_el_tope_de_reservas_del_mes(client, base):
    base['amenities'][0]['max_reservas_mes'] = 1
    assert client.post('/api/reservas_amenities',
                       json=_reserva(hora_inicio='10:00', hora_fin='12:00')).status_code == 201
    r = client.post('/api/reservas_amenities',
                    json=_reserva(hora_inicio='15:00', hora_fin='17:00'))
    assert r.status_code == 400
    assert 'máximo es 1' in r.get_json()['error']
    assert len(base['reservas_amenities']) == 1


def test_sin_tope_cargado_reserva_todo_lo_que_quiera(client, base):
    for h in ('08:00', '10:00', '12:00'):
        assert client.post('/api/reservas_amenities',
                           json=_reserva(hora_inicio=h, hora_fin=h[:2] + ':59')).status_code == 201
    assert len(base['reservas_amenities']) == 3


def test_el_cupo_es_por_espacio_y_no_global(client, base):
    """Llenar el cupo del SUM no puede bloquear el otro amenity del edificio."""
    base['amenities'][0]['max_reservas_mes'] = 1
    base['amenities'].append({'id': 'amen-3', 'consorcio_id': 'cons-1',
                              'nombre': 'Parrilla', 'capacidad_maxima': None,
                              'max_reservas_mes': 1, 'condiciones_uso': '',
                              'consorcios': {'nombre': 'Mío'}})
    assert client.post('/api/reservas_amenities', json=_reserva()).status_code == 201
    r = client.post('/api/reservas_amenities', json=_reserva(amenity_id='amen-3'))
    assert r.status_code == 201


def test_una_reserva_cancelada_no_gasta_cupo(client, base):
    base['amenities'][0]['max_reservas_mes'] = 1
    client.post('/api/reservas_amenities', json=_reserva(hora_inicio='10:00', hora_fin='12:00'))
    base['reservas_amenities'][0]['estado'] = 'cancelada'
    r = client.post('/api/reservas_amenities', json=_reserva(hora_inicio='15:00', hora_fin='17:00'))
    assert r.status_code == 201
