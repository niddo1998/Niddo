"""El número de una UF identifica la unidad dentro del consorcio (#32).

La carga masiva desde Excel ya no deja duplicar una UF existente; el alta y la
edición manual tienen que respetar la misma regla: con dos «UF 1» no hay forma
de saber a cuál corresponde cada expensa, cobro o vecino.
"""

import pytest

from tests.test_carga_masiva_consorcios import admin  # noqa: F401

URL = '/api/consorcios/cons-1/unidades'


def _ufs(base, cid='cons-1'):
    return [u for u in base['unidades_funcionales'] if u['consorcio_id'] == cid]


@pytest.mark.parametrize('numero', ['1A', '1a', ' 1A '])
def test_alta_con_numero_repetido_se_rechaza(admin, base, numero):
    r = admin.post(URL, json={'numero': numero})
    assert r.status_code == 409
    assert 'Ya existe la UF' in r.get_json()['error']
    assert len(_ufs(base)) == 1


@pytest.mark.parametrize('numero', ['', '   ', None])
def test_alta_sin_numero_se_rechaza(admin, base, numero):
    r = admin.post(URL, json={'numero': numero})
    assert r.status_code == 400
    assert len(_ufs(base)) == 1


def test_numero_numerico_no_tira_500(admin, base):
    r = admin.post(URL, json={'numero': 7})
    assert r.status_code == 201
    assert r.get_json()['numero'] == '7'


def test_mismo_numero_en_otro_consorcio_vale(admin, base):
    """La unicidad es por consorcio: el `2B` del consorcio ajeno no cuenta."""
    r = admin.post(URL, json={'numero': '2B'})
    assert r.status_code == 201


def test_editar_al_numero_de_otra_uf_se_rechaza(admin, base):
    base['unidades_funcionales'].append({'id': 'uf-3', 'consorcio_id': 'cons-1', 'numero': '3C'})
    r = admin.put(f'{URL}/uf-3', json={'numero': '1a'})
    assert r.status_code == 409
    assert next(u for u in base['unidades_funcionales'] if u['id'] == 'uf-3')['numero'] == '3C'


def test_editar_la_misma_uf_sin_cambiar_el_numero_vale(admin, base):
    r = admin.put(f'{URL}/uf-1', json={'numero': '1A', 'piso': '1'})
    assert r.status_code == 200
    assert next(u for u in base['unidades_funcionales'] if u['id'] == 'uf-1')['piso'] == '1'


def test_editar_a_numero_vacio_se_rechaza(admin, base):
    r = admin.put(f'{URL}/uf-1', json={'numero': '  '})
    assert r.status_code == 400
    assert next(u for u in base['unidades_funcionales'] if u['id'] == 'uf-1')['numero'] == '1A'
