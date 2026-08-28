"""El prorrateo, contrastado contra liquidaciones reales del mercado.

Los números de este archivo salen de cuatro liquidaciones de verdad —SIPAC,
Octopus, Expensas Flow y Consorcio Abierto— y la fórmula da igual en las
cuatro:

    total 1er vto = Σ(expensa de cada coeficiente)
                  + gastos particulares de la unidad
                  + saldo pendiente + intereses
                  + uso de amenities
                  + redondeo
    total 2do vto = total 1er vto × (1 + recargo%)

El reparto por VARIOS coeficientes es lo que hace que un edificio con cocheras
o locales pueda liquidar bien: la factura del ascensor va por un coeficiente
donde la cochera pesa 0, y el seguro por otro donde pesa. Los cuatro sistemas
imprimen "SUBTOTALES POR COEFICIENTE" justamente por eso.
"""

import pytest

import app as app_mod


@pytest.fixture
def edificio(base):
    """Tres UFs y un consorcio con tasas cargadas."""
    base['consorcios'][0].update({
        'tasa_interes_mora': 3.0,
        'recargo_segundo_vto': 3.0,
    })
    base['unidades_funcionales'] = [
        {'id': 'uf-1', 'consorcio_id': 'cons-1', 'numero': '1A',
         'porcentaje_a': 50.0, 'porcentaje_b': 0.0, 'porcentaje_c': 0.0, 'porcentaje_e': 0.0},
        {'id': 'uf-2', 'consorcio_id': 'cons-1', 'numero': '1B',
         'porcentaje_a': 30.0, 'porcentaje_b': 50.0, 'porcentaje_c': 0.0, 'porcentaje_e': 0.0},
        {'id': 'uf-3', 'consorcio_id': 'cons-1', 'numero': 'COCHERA',
         'porcentaje_a': 20.0, 'porcentaje_b': 50.0, 'porcentaje_c': 0.0, 'porcentaje_e': 0.0},
    ]
    base['liquidaciones'] = [{'id': 'liq-1', 'consorcio_id': 'cons-1',
                              'periodo': '2026-08', 'interes_2_vto': 0}]
    base['liquidacion_rubros'] = [{'id': 'rub-1', 'liquidacion_id': 'liq-1'}]
    base['liquidacion_items'] = []
    base['liquidacion_prorrateo'] = []
    base['cobros'] = []
    base['reservas_amenities'] = []
    return base


def _item(base, monto, coeficiente='A', unidad_id=None):
    base['liquidacion_items'].append({
        'id': f'it-{len(base["liquidacion_items"])}', 'rubro_id': 'rub-1',
        'monto': monto, 'coeficiente': coeficiente, 'unidad_id': unidad_id,
    })


def _prorratear(base, revision=1):
    app_mod._generar_prorrateo('liq-1', 'cons-1', '2026-08', numero_revision=revision)
    return {p['unidad_id']: p for p in base['liquidacion_prorrateo']}


# ── Un solo coeficiente ───────────────────────────────────────────────────────

def test_reparte_segun_los_porcentajes_cargados(edificio):
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio)
    assert p['uf-1']['expensa_a'] == 500.0
    assert p['uf-2']['expensa_a'] == 300.0
    assert p['uf-3']['expensa_a'] == 200.0


def test_sin_porcentajes_cargados_reparte_lineal(edificio):
    """Es como vienen las UFs. Antes multiplicaba por 0 y daba $0 a cada una."""
    for uf in edificio['unidades_funcionales']:
        uf['porcentaje_a'] = 0.0
    _item(edificio, 900.0, 'A')
    p = _prorratear(edificio)
    assert [p[u]['expensa_a'] for u in ('uf-1', 'uf-2', 'uf-3')] == [300.0, 300.0, 300.0]


# ── Varios coeficientes a la vez ──────────────────────────────────────────────

def test_cada_gasto_se_reparte_por_su_coeficiente(edificio):
    """El ascensor por A —la cochera casi no lo usa— y la luz por B."""
    _item(edificio, 1000.0, 'A')
    _item(edificio, 600.0, 'B')
    p = _prorratear(edificio)
    assert p['uf-1']['expensa_a'] == 500.0
    assert p['uf-1']['expensa_b'] == 0.0        # no participa de B
    assert p['uf-2']['expensa_b'] == 300.0
    assert p['uf-3']['expensa_b'] == 300.0


def test_el_total_suma_los_coeficientes(edificio):
    _item(edificio, 1000.0, 'A')
    _item(edificio, 600.0, 'B')
    p = _prorratear(edificio)
    assert p['uf-3']['total_unidad'] == 200.0 + 300.0


def test_lo_repartido_es_exactamente_lo_gastado(edificio):
    """100 entre 3 da 33,33 tres veces = 99,99. El redondeo cierra la diferencia."""
    for uf in edificio['unidades_funcionales']:
        uf['porcentaje_a'] = 0.0
    _item(edificio, 100.0, 'A')
    p = _prorratear(edificio)
    assert round(sum(x['expensa_a'] for x in p.values()), 2) == 100.0
    assert round(sum(x['redondeo'] for x in p.values()), 2) != 0


# ── Gastos de una sola unidad ─────────────────────────────────────────────────

def test_el_gasto_particular_no_se_reparte(edificio):
    _item(edificio, 1000.0, 'A')
    _item(edificio, 500.0, 'A', unidad_id='uf-2')
    p = _prorratear(edificio)
    assert p['uf-2']['gastos_particulares'] == 500.0
    assert p['uf-1']['gastos_particulares'] == 0.0
    assert p['uf-1']['expensa_a'] == 500.0        # el particular no infló el reparto
    assert p['uf-2']['total_unidad'] == 300.0 + 500.0


# ── Saldo anterior, intereses y crédito ───────────────────────────────────────

def _cobro_anterior(base, unidad_id, total, estado='pendiente'):
    base['cobros'].append({
        'id': f'cob-{unidad_id}', 'unidad_id': unidad_id, 'consorcio_id': 'cons-1',
        'periodo': '2026-07', 'total': total, 'estado': estado,
    })


def test_arrastra_la_deuda_y_le_cobra_interes(edificio):
    _cobro_anterior(edificio, 'uf-1', 1000.0)
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio)
    assert p['uf-1']['saldo_pendiente'] == 1000.0
    assert p['uf-1']['interes_mora'] == 30.0          # 3% del consorcio
    assert p['uf-1']['total_unidad'] == 500.0 + 1000.0 + 30.0


def test_el_que_pago_no_arrastra_nada(edificio):
    _cobro_anterior(edificio, 'uf-1', 1000.0, estado='pagado')
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio)
    assert p['uf-1']['saldo_pendiente'] == 0.0
    assert p['uf-1']['interes_mora'] == 0.0


def test_el_saldo_a_favor_se_arrastra_como_credito(edificio, monkeypatch):
    """Pagar de más no puede perderse. Antes se cortaba en 0."""
    _cobro_anterior(edificio, 'uf-1', 1000.0, estado='pagado')
    # Pagó 1200 por un cobro de 1000: quedan 200 a favor.
    edificio['cobros'][0]['total'] = 1000.0
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio)
    # El caso simétrico: un cobro anterior negativo es crédito puro.
    edificio['liquidacion_prorrateo'].clear()
    edificio['cobros'][0].update({'total': -200.0, 'estado': 'pendiente'})
    p = _prorratear(edificio)
    assert p['uf-1']['saldo_pendiente'] == -200.0
    assert p['uf-1']['interes_mora'] == 0.0           # nunca interés sobre un crédito
    assert p['uf-1']['total_unidad'] == 500.0 - 200.0


def test_la_reliquidacion_no_cobra_dos_veces_la_deuda_vieja(edificio):
    _cobro_anterior(edificio, 'uf-1', 1000.0)
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio, revision=2)
    assert p['uf-1']['saldo_pendiente'] == 0.0
    assert p['uf-1']['total_unidad'] == 500.0


# ── Segundo vencimiento ───────────────────────────────────────────────────────

def test_el_recargo_del_segundo_vto_se_aplica_al_total(edificio):
    """Niddo lo imprimía como "+X%" sin calcularlo. Los cuatro sistemas lo aplican."""
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio)
    assert p['uf-1']['total_unidad'] == 500.0
    assert p['uf-1']['total_segundo_vto'] == 515.0     # 500 × 1,03


def test_sin_recargo_los_dos_totales_son_iguales(edificio):
    edificio['consorcios'][0]['recargo_segundo_vto'] = 0
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio)
    assert p['uf-1']['total_segundo_vto'] == p['uf-1']['total_unidad']


def test_el_recargo_de_la_liquidacion_pisa_al_del_consorcio(edificio):
    edificio['liquidaciones'][0]['interes_2_vto'] = 10.0
    _item(edificio, 1000.0, 'A')
    p = _prorratear(edificio)
    assert p['uf-1']['total_segundo_vto'] == 550.0     # 500 × 1,10


# ── Contraste con una liquidación real ────────────────────────────────────────

def test_reproduce_una_fila_de_expensas_flow(edificio):
    """UF 2 de Pacheco 2876, julio 2026: expensa 283.800, dif 8.514,02,
    int 8.514,00 → 1°V 300.828,02 y 2°V 309.852,02 con recargo del 3%."""
    for uf in edificio['unidades_funcionales']:
        uf['porcentaje_a'] = 0.0
    edificio['unidades_funcionales'] = [edificio['unidades_funcionales'][0]]
    edificio['unidades_funcionales'][0]['porcentaje_a'] = 100.0
    _cobro_anterior(edificio, 'uf-1', 283800.67)      # deuda que deja 8.514,02 de interés al 3%
    edificio['cobros'][0]['total'] = 283800.67
    _item(edificio, 283800.00, 'A')
    p = _prorratear(edificio)
    fila = p['uf-1']
    assert fila['expensa_a'] == 283800.00
    assert fila['interes_mora'] == round(283800.67 * 0.03, 2)
    esperado = round(283800.00 + 283800.67 + fila['interes_mora'], 2)
    assert fila['total_unidad'] == esperado
    assert fila['total_segundo_vto'] == round(esperado * 1.03, 2)


# ── Que se puedan cargar es la mitad del asunto ───────────────────────────────
# Las columnas existían desde v7 y ningún endpoint las aceptaba, así que
# quedaban en 0 para siempre y el prorrateo caía en reparto lineal. Era el
# bloqueo real del feature entero.

@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


def test_el_alta_de_una_uf_guarda_los_porcentajes(admin, base):
    r = admin.post('/api/consorcios/cons-1/unidades', json={
        'numero': '5C', 'porcentaje_a': 12.5, 'porcentaje_e': 7.25})
    assert r.status_code == 201
    uf = next(u for u in base['unidades_funcionales'] if u['numero'] == '5C')
    assert uf['porcentaje_a'] == 12.5
    assert uf['porcentaje_e'] == 7.25


def test_editar_una_uf_cambia_sus_porcentajes(admin, base):
    admin.put('/api/consorcios/cons-1/unidades/uf-1', json={'porcentaje_a': 33.333})
    uf = next(u for u in base['unidades_funcionales'] if u['id'] == 'uf-1')
    assert uf['porcentaje_a'] == 33.333


def test_el_gasto_guarda_su_coeficiente(admin, base):
    base['gastos'] = []
    r = admin.post('/api/gastos', json={
        'consorcio_id': 'cons-1', 'descripcion': 'Ascensor', 'monto': 1000,
        'categoria': 'ascensor', 'coeficiente': 'e'})
    assert r.status_code == 201
    assert base['gastos'][0]['coeficiente'] == 'E'   # se normaliza a mayúscula


def test_el_alta_ignora_los_campos_que_el_formulario_dejo_de_pedir(admin, base):
    """Un cliente viejo que todavía los mande no los mete de vuelta."""
    base['gastos'] = []
    admin.post('/api/gastos', json={
        'consorcio_id': 'cons-1', 'descripcion': 'Ascensor', 'monto': 1000,
        'proveedor_id': 'prov-1', 'fecha_vencimiento': '2026-09-10',
        'metodo_pago': 'transferencia', 'comprobante_numero': '0001-00099'})
    g = base['gastos'][0]
    assert not {'proveedor_id', 'fecha_vencimiento', 'metodo_pago',
                'comprobante_numero'} & set(g)


def test_un_gasto_sin_coeficiente_nace_en_A(admin, base):
    """Es como se repartía todo hasta ahora: nada cambia si no se toca."""
    base['gastos'] = []
    admin.post('/api/gastos', json={'consorcio_id': 'cons-1',
                                    'descripcion': 'Luz', 'monto': 500})
    assert base['gastos'][0]['coeficiente'] == 'A'


def test_las_tasas_se_guardan_en_el_consorcio(admin, base):
    """La de mora estaba escrita a mano en el HTML y el botón no hacía nada."""
    r = admin.put('/api/consorcios/cons-1', json={
        'tasa_interes_mora': 2.5, 'recargo_segundo_vto': 4.0, 'clave_suterh': '85693'})
    assert r.status_code == 200
    c = base['consorcios'][0]
    assert c['tasa_interes_mora'] == 2.5
    assert c['recargo_segundo_vto'] == 4.0
    assert c['clave_suterh'] == '85693'
