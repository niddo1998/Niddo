"""Un vecino sólo vota las asambleas de su edificio, y una vez por unidad.

El endpoint buscaba la votación por id y nada más, así que el UUID de la
asamblea del edificio de al lado entraba igual. Y el control de "una unidad, un
voto" estaba dentro de un `if unidad_id:`, de modo que un vecino todavía en
"Pendiente" —sin unidad asignada— no lo pisaba nunca y podía votar sin límite.
"""

import pytest


def _votos(base):
    return base['votos']


# ── La votación del otro edificio ─────────────────────────────────────────────

def test_no_puede_votar_la_asamblea_de_otro_consorcio(client, base):
    r = client.post('/api/votaciones/vot-2/votar', json={'opcion': 'Si'})
    # 404 y no 403: un 403 confirmaría que ese id existe.
    assert r.status_code == 404
    assert _votos(base) == []


def test_una_votacion_inexistente_tambien_da_404(client, base):
    r = client.post('/api/votaciones/no-existe/votar', json={'opcion': 'Si'})
    assert r.status_code == 404
    assert _votos(base) == []


# ── Sin unidad asignada ───────────────────────────────────────────────────────

def test_sin_unidad_no_vota(client, base):
    base['vecinos'][0]['unidad_id'] = None
    r = client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert r.status_code == 403
    assert _votos(base) == []


def test_sin_unidad_no_puede_votar_muchas_veces(client, base):
    """Era el agujero real: sin unidad, el control de uno-por-UF no aplicaba."""
    base['vecinos'][0]['unidad_id'] = None
    for _ in range(3):
        client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert _votos(base) == []


# ── Lo propio sigue funcionando ───────────────────────────────────────────────

def test_vota_su_asamblea(client, base):
    r = client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert r.status_code == 201, r.data
    assert [v['opcion'] for v in _votos(base)] == ['Si']


def test_su_unidad_vota_una_sola_vez(client, base):
    assert client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'}).status_code == 201
    r = client.post('/api/votaciones/vot-1/votar', json={'opcion': 'No'})
    assert r.status_code == 409
    assert len(_votos(base)) == 1


def test_una_opcion_que_no_esta_en_la_votacion_se_rechaza(client, base):
    r = client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Tal vez'})
    assert r.status_code == 400
    assert _votos(base) == []


def test_no_vota_una_votacion_cerrada(client, base):
    base['votaciones'][0]['estado'] = 'cerrada'
    r = client.post('/api/votaciones/vot-1/votar', json={'opcion': 'Si'})
    assert r.status_code == 400
    assert _votos(base) == []


def test_el_listado_solo_trae_las_de_su_consorcio(client):
    r = client.get('/api/votaciones')
    assert [v['id'] for v in r.get_json()] == ['vot-1']
