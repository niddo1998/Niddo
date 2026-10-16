"""La deuda que cada unidad trae del sistema anterior.

Ningún administrador arranca de cero: viene de otro sistema con vecinos que
deben meses. Sin esto, la primera liquidación en Niddo sale mal justo en los
morosos, que son los que reclaman.
"""

import io

import openpyxl
import pytest

import app as app_mod
from tests.test_prorrateo import edificio, _item, _prorratear  # noqa: F401
from tests.test_carga_masiva_consorcios import admin, _subir, _plantilla, _escribir  # noqa: F401


def test_la_primera_liquidacion_trae_el_saldo_anterior(edificio):
    edificio['unidades_funcionales'][0]['saldo_inicial'] = 10000.0
    _item(edificio, 1000.0)
    p = _prorratear(edificio)
    assert p['uf-1']['saldo_anterior'] == 10000.0
    assert p['uf-1']['saldo_pendiente'] == 10000.0
    assert p['uf-1']['interes_mora'] == 300.0          # 3 % del consorcio
    assert p['uf-2']['saldo_anterior'] == 0.0


def test_un_saldo_a_favor_descuenta_sin_interes(edificio):
    edificio['unidades_funcionales'][0]['saldo_inicial'] = -200.0
    _item(edificio, 1000.0)
    p = _prorratear(edificio)
    assert p['uf-1']['saldo_pendiente'] == -200.0
    assert p['uf-1']['interes_mora'] == 0.0


def test_con_cobros_en_niddo_el_saldo_inicial_ya_no_entra(edificio):
    """Entra una sola vez: después lo arrastra el cobro de cada mes."""
    edificio['unidades_funcionales'][0]['saldo_inicial'] = 10000.0
    edificio['cobros'] = [{'id': 'c-1', 'unidad_id': 'uf-1', 'periodo': '2026-06',
                           'total': 500.0, 'estado': 'pagado'}]
    _item(edificio, 1000.0)
    assert _prorratear(edificio)['uf-1']['saldo_anterior'] == 0.0


def test_la_planilla_trae_la_columna(admin):
    ws = _plantilla(admin)['Carga']
    encabezado = next(r for r in ws.iter_rows(values_only=True) if r and r[0] == 'consorcio*')
    assert 'saldo_anterior' in encabezado


def test_la_carga_masiva_guarda_el_saldo(admin, base):
    base['unidades_funcionales'] = []
    wb = _plantilla(admin)
    _escribir(wb['Carga'], [['Nuevo', '', '', '', '', '1A', '1', 'departamento', 50, 2, '', '', 15000]])
    r = _subir(admin, wb)
    assert r['unidades_creadas'] == 1
    assert base['unidades_funcionales'][0]['saldo_inicial'] == 15000


def test_resubir_con_saldos_actualiza_las_unidades_existentes(admin, base):
    """Migrar es en dos tandas: primero las unidades, después la deuda."""
    base['unidades_funcionales'] = [{'id': 'uf-1', 'consorcio_id': 'cons-1', 'numero': '1A'}]
    wb = _plantilla(admin)
    _escribir(wb['Carga'], [['Mío', '', '', '', '', '1A', '', '', None, None, '', '', 7000]])
    r = _subir(admin, wb)
    assert r['saldos_actualizados'] == 1
    assert r['unidades_creadas'] == 0
    assert base['unidades_funcionales'][0]['saldo_inicial'] == 7000
