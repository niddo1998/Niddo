"""El vecino baja el resumen de su expensa: el PDF de la liquidación.

Antes bajaba un "cupón" con el total y poco más. Lo que quiere guardar es el
resumen que le llega por mail: el detalle de gastos y lo que le toca pagar.
"""

import pytest


@pytest.fixture
def con_liquidacion(base):
    base['cobros'][0]['liquidacion_id'] = 'liq-1'
    base['liquidaciones'] = [{'id': 'liq-1', 'consorcio_id': 'cons-1', 'admin_id': 'admin-1',
                              'periodo': '2026-08', 'estado': 'publicada',
                              'consorcios': {'nombre': 'Mío', 'metodo_prorrateo': 'm2'}}]
    base['liquidacion_rubros'] = []
    base['liquidacion_items'] = []
    base['liquidacion_prorrateo'] = [{'id': 'p1', 'liquidacion_id': 'liq-1', 'unidad_id': 'uf-1',
                                      'porcentaje_a': 100, 'expensa_a': 100, 'total_unidad': 100,
                                      'total_segundo_vto': 100,
                                      'unidades_funcionales': {'numero': '1A'}}]
    base['administradores'][0].update({'nombre': 'Admin'})
    return base


def test_baja_el_pdf_de_la_liquidacion(client, con_liquidacion):
    r = client.get('/api/vecinos/cobros/cobro-1/resumen')
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.data[:5] == b'%PDF-'


def test_una_expensa_sin_liquidacion_baja_el_comprobante(client, base):
    r = client.get('/api/vecinos/cobros/cobro-1/resumen')
    assert r.status_code == 302
    assert r.headers['Location'].endswith('/api/vecinos/cobros/cobro-1/cupon')


def test_la_expensa_de_otro_no_se_baja(client, con_liquidacion):
    con_liquidacion['cobros'].append({'id': 'cobro-ajeno', 'unidad_id': 'uf-2', 'consorcio_id': 'cons-2',
                                      'liquidacion_id': 'liq-1'})
    assert client.get('/api/vecinos/cobros/cobro-ajeno/resumen').status_code == 404
