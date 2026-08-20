"""La fecha límite de una votación se hace cumplir.

`votaciones.fecha_limite` y `votos_necesarios` estaban en el schema desde v6
sin que ninguna línea de código los leyera. Como `estado` tampoco lo mueve
nadie —no hay cron—, una votación vencida seguía figurando 'activa' y
aceptando votos para siempre.

La regla vive en el backend y el listado la publica como `vigente`. Si la
pantalla la calculara por su cuenta, podría ofrecer un botón que el servidor
va a rechazar.
"""

from datetime import date, timedelta


def _dia(delta):
    return (date.today() + timedelta(days=delta)).isoformat()


def _limite(base, valor):
    base['votaciones'][0]['fecha_limite'] = valor


# ── Votar ─────────────────────────────────────────────────────────────────────

def test_no_vota_una_votacion_vencida(client, base):
    _limite(base, _dia(-1))
    r = client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert r.status_code == 400
    assert 'venció' in r.get_json()['error']
    assert base['votos'] == []


def test_el_ultimo_dia_todavia_se_vota(client, base):
    """El límite es un DATE y cuenta inclusive."""
    _limite(base, _dia(0))
    assert client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'}).status_code == 201


def test_sin_fecha_limite_se_vota(client, base):
    _limite(base, None)
    assert client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'}).status_code == 201


def test_antes_del_limite_se_vota(client, base):
    _limite(base, _dia(5))
    assert client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'}).status_code == 201


# ── El listado lo dice ────────────────────────────────────────────────────────

def test_el_listado_marca_la_vencida(client, base):
    _limite(base, _dia(-1))
    v = client.get('/api/votaciones').get_json()[0]
    assert v['vigente'] is False
    assert v['vencida'] is True


def test_el_listado_marca_la_viva(client, base):
    _limite(base, _dia(5))
    v = client.get('/api/votaciones').get_json()[0]
    assert v['vigente'] is True
    assert v['vencida'] is False


def test_una_cerrada_a_mano_no_figura_como_vencida(client, base):
    """`vencida` es "se pasó de fecha", no "está cerrada"."""
    base['votaciones'][0]['estado'] = 'cerrada'
    v = client.get('/api/votaciones').get_json()[0]
    assert v['vigente'] is False
    assert v['vencida'] is False


# ── Quórum ────────────────────────────────────────────────────────────────────

def test_informa_cuantos_votos_faltan(client, base):
    base['votaciones'][0]['votos_necesarios'] = 3
    assert client.get('/api/votaciones').get_json()[0]['falta_quorum'] == 3
    client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert client.get('/api/votaciones').get_json()[0]['falta_quorum'] == 2


def test_alcanzado_el_quorum_no_falta_nada(client, base):
    base['votaciones'][0]['votos_necesarios'] = 1
    client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert client.get('/api/votaciones').get_json()[0]['falta_quorum'] == 0


def test_sin_quorum_definido_no_falta_nada(client, base):
    assert client.get('/api/votaciones').get_json()[0]['falta_quorum'] == 0
