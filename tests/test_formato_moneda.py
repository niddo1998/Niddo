"""Los importes se escriben como se escriben acá: $ 1.234.567,89.

El mail del resumen y el cupón de pago armaban los números con f-strings
`${x:,.2f}`, que es el formato yanqui: $1,234.50. Un vecino que recibe su
expensa lee ahí mil doscientos treinta y cuatro con cincuenta *centavos de
más*, y es el único número de todo el mail que importa.
"""

import re
from pathlib import Path

import pytest

import app as app_mod


APP = Path(__file__).resolve().parent.parent / 'app.py'


# ── El formateador ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('valor,esperado', [
    (15430.5, '$ 15.430,50'),
    (0, '$ 0,00'),
    (None, '$ 0,00'),
    ('', '$ 0,00'),
    (-1234.5, '-$ 1.234,50'),
    (1234567.891, '$ 1.234.567,89'),
    ('no es un número', '$ 0,00'),
])
def test_pesos_escribe_el_formato_argentino(valor, esperado):
    assert app_mod.pesos(valor) == esperado


def test_el_signo_no_se_separa_del_numero():
    """Espacio duro: el importe no se parte en dos líneas."""
    assert ' ' in app_mod.pesos(1000)
    assert ' ' not in app_mod.pesos(1000).replace(' ', '')


def test_no_quedan_importes_en_formato_yanqui_en_el_backend():
    fuente = APP.read_text()
    # El propio `pesos()` usa `:,.2f` como paso intermedio; el resto no debería.
    sospechosas = [l.strip() for l in fuente.split('\n')
                   if re.search(r'\$\{[^}]+:,\.\df\}|\$ \{[^}]+:,\.\df\}', l)
                   and '`' not in l]
    assert not sospechosas, (
        'Estos importes se escriben con el formato yanqui:\n'
        + '\n'.join(f'  {l[:120]}' for l in sospechosas))


# ── El mail que recibe el vecino ─────────────────────────────────────────────

@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


@pytest.fixture
def con_resumen(base):
    base['liquidaciones'] = [{
        'id': 'liq-1', 'consorcio_id': 'cons-1', 'admin_id': 'admin-1',
        'periodo': '2026-08', 'numero_revision': 1, 'estado': 'borrador',
        'fecha_vencimiento_1': '2026-08-10', 'consorcios': {'nombre': 'Mío'},
    }]
    base['liquidacion_prorrateo'] = [{
        'id': 'pro-1', 'liquidacion_id': 'liq-1', 'unidad_id': 'uf-1',
        'total_unidad': 15430.5, 'expensa_a': 15430.5, 'saldo_anterior': 1234.5,
        'unidades_funcionales': {'numero': '1A', 'piso': '1', 'tipo': 'departamento',
                                 'vecino_nombre': 'Uno', 'vecino_email': 'uno@test'},
    }]
    base['liquidacion_rubros'] = []
    return base


def test_el_resumen_del_mail_lleva_los_importes_en_pesos(admin, con_resumen):
    html = admin.get('/api/liquidaciones/liq-1/resumen/uf-1'
                     '?format=html').get_data(as_text=True)
    assert '15.430,50' in html
    assert '15,430.50' not in html
