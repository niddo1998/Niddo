"""Verificación numérica del prorrateo contra Postgres real (roadmap #16).

`tests/test_prorrateo.py` cubre la fórmula con el doble de la base. Esto la
recorre de punta a punta en el ambiente de pruebas: el administrador elige el
método en el consorcio, carga un gasto, genera la liquidación por la API y se
compara cada UF contra la cuenta hecha a mano (abajo, en cada caso).

El gasto es de $ 100.000,01 a propósito: con ese centavo ningún método reparte
exacto, así que también se prueba que el redondeo cierre en la primera UF y que
lo cobrado sume exactamente lo gastado.

Datos del seed (Edificio QA Libertador), en el orden en que liquida (por número):

    UF   m²  ambientes  %
    1A   60      2      20
    1B   80      3      30
    2A   60      2      20
    PB   90      1      30
         290     8     100

Cada caso usa un período de 2031 que no tiene otros gastos ni cobros, y al
final deja la base como estaba (borra liquidación y gasto, vuelve el método).
"""

import pytest

CONSORCIO = 'c0000000-0000-4000-8000-000000000001'
TOTAL = 100000.01
UFS = ['1A', '1B', '2A', 'PB']

# Las cuentas a mano. `expensa` ya trae el redondeo sumado en la primera UF.
CASOS = {
    # 100000,01 × 60/290 = 20689,6572 → 20689,66 ; ×80/290 = 27586,2097 → 27586,21
    # ×90/290 = 31034,4859 → 31034,49. Suman 100000,02 → la 1A absorbe −0,01.
    'm2': {'periodo': '2031-01',
           'expensa': [20689.65, 27586.21, 20689.66, 31034.49],
           'redondeo': [-0.01, 0, 0, 0],
           'porcentaje': [20.69, 27.586, 20.69, 31.034]},
    # ×2/8 = 25000,0025 → 25000,00 ; ×3/8 = 37500,0038 → 37500,00 ;
    # ×1/8 = 12500,0013 → 12500,00. Suman 100000,00 → la 1A suma +0,01.
    'ambientes': {'periodo': '2031-02',
                  'expensa': [25000.01, 37500.00, 25000.00, 12500.00],
                  'redondeo': [0.01, 0, 0, 0],
                  'porcentaje': [25.0, 37.5, 25.0, 12.5]},
    # ÷4 = 25000,0025 → 25000,00 cada una. Suman 100000,00 → la 1A suma +0,01.
    'partes_iguales': {'periodo': '2031-03',
                       'expensa': [25000.01, 25000.00, 25000.00, 25000.00],
                       'redondeo': [0.01, 0, 0, 0],
                       'porcentaje': [25.0, 25.0, 25.0, 25.0]},
    # ×20 % = 20000,002 → 20000,00 ; ×30 % = 30000,003 → 30000,00.
    # Suman 100000,00 → la 1A suma +0,01.
    'porcentaje': {'periodo': '2031-04',
                   'expensa': [20000.01, 30000.00, 20000.00, 30000.00],
                   'redondeo': [0.01, 0, 0, 0],
                   'porcentaje': [20.0, 30.0, 20.0, 30.0]},
}


def _ok(resp, contexto):
    assert resp.ok, f'{contexto}: HTTP {resp.status} {resp.text()[:300]}'
    return resp.json()


@pytest.mark.parametrize('metodo', list(CASOS))
def test_el_prorrateo_cuadra_al_centavo(abrir, metodo):
    caso = CASOS[metodo]
    page, vigia = abrir('admin')
    api = page.request

    original = next(c for c in _ok(api.get('/api/consorcios'), 'consorcios')
                    if c['id'] == CONSORCIO).get('metodo_prorrateo')
    gasto = liq = None
    try:
        _ok(api.put(f'/api/consorcios/{CONSORCIO}', data={'metodo_prorrateo': metodo}),
            'elegir método')
        gasto = _ok(api.post('/api/gastos', data={
            'consorcio_id': CONSORCIO, 'descripcion': f'QA prorrateo {metodo}',
            'categoria': 'mantenimiento', 'monto': TOTAL,
            'fecha_gasto': f'{caso["periodo"]}-10'}), 'cargar gasto')
        liq = _ok(api.post('/api/liquidaciones', data={
            'consorcio_id': CONSORCIO, 'periodo': caso['periodo'],
            'interes_2_vto': 10, 'auto_generar': True}), 'generar liquidación')
        filas = _ok(api.get(f'/api/liquidaciones/{liq["id"]}/prorrateo'), 'prorrateo')

        por_uf = {(f.get('unidades_funcionales') or {}).get('numero'): f for f in filas}
        assert sorted(por_uf) == sorted(UFS), f'UFs liquidadas: {sorted(por_uf)}'

        for i, uf in enumerate(UFS):
            f = por_uf[uf]
            assert float(f['expensa_a']) == caso['expensa'][i], f'{metodo} {uf} expensa'
            assert float(f['redondeo']) == caso['redondeo'][i], f'{metodo} {uf} redondeo'
            assert float(f['porcentaje_a']) == caso['porcentaje'][i], f'{metodo} {uf} %'
            # Sin deuda ni amenities: lo que paga es la expensa, y el 2º vto +10 %.
            assert float(f['total_unidad']) == caso['expensa'][i], f'{metodo} {uf} total'
            assert float(f['total_segundo_vto']) == round(caso['expensa'][i] * 1.1, 2), \
                f'{metodo} {uf} 2º vto'

        cobrado = round(sum(float(f['total_unidad']) for f in filas), 2)
        assert cobrado == TOTAL, f'{metodo}: se cobra {cobrado} y se gastó {TOTAL}'

        cabecera = next(x for x in _ok(api.get('/api/liquidaciones'), 'liquidaciones')
                        if x['id'] == liq['id'])
        assert float(cabecera['total_egresos']) == TOTAL
    finally:
        if liq:
            api.delete(f'/api/liquidaciones/{liq["id"]}')
        if gasto:
            api.delete(f'/api/gastos/{gasto["id"]}')
        api.put(f'/api/consorcios/{CONSORCIO}', data={'metodo_prorrateo': original or 'm2'})
    vigia.verificar(f'prorrateo {metodo}')
