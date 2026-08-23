"""El panel de inicio del administrador.

Reemplaza a `/api/dashboard/kpis`, que tenía dos agujeros que este test cierra
de entrada: la morosidad se consultaba sin filtrar por consorcio —y como la app
habla con Supabase con la service key, la RLS no la frenaba, así que cada
administrador veía la mora de toda la plataforma— y se contaba por el estado
'vencido', que nadie escribe nunca.
"""

from datetime import date, timedelta

import pytest

import app as app_mod


HOY = date.today()
PERIODO = f'{HOY.year:04d}-{HOY.month:02d}'
AYER = (HOY - timedelta(days=1)).isoformat()
MANIANA = (HOY + timedelta(days=1)).isoformat()
LEJOS = (HOY + timedelta(days=60)).isoformat()


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


def _gasto(**kw):
    fila = {'id': 'g-1', 'admin_id': 'admin-1', 'consorcio_id': 'cons-1',
            'descripcion': 'Ascensor', 'categoria': 'ascensor', 'monto': 1000,
            'fecha_gasto': f'{PERIODO}-05', 'fecha_vencimiento': None,
            'pagado': True, 'tarifa_confirmada': True}
    fila.update(kw)
    return fila


def _cobro(**kw):
    fila = {'id': 'c-1', 'consorcio_id': 'cons-1', 'unidad_id': 'uf-1',
            'periodo': PERIODO, 'total': 5000, 'estado': 'pendiente',
            'fecha_vencimiento': MANIANA}
    fila.update(kw)
    return fila


def _resumen(admin):
    r = admin.get('/api/dashboard/resumen')
    assert r.status_code == 200
    return r.get_json()


# ── El agujero que traía el endpoint viejo ────────────────────────────────────

def test_la_mora_no_cruza_administradores(admin, base):
    """El cobro vencido del edificio ajeno no entra en la deuda de este admin."""
    base['cobros'] = [
        _cobro(id='mio', fecha_vencimiento=AYER, total=5000),
        _cobro(id='ajeno', consorcio_id='cons-2', unidad_id='uf-2',
               fecha_vencimiento=AYER, total=999999),
    ]
    plata = _resumen(admin)['plata']
    assert plata['deuda_vencida'] == 5000
    assert plata['ufs_en_mora'] == 1


def test_la_mora_se_calcula_por_fecha_y_no_por_estado(admin, base):
    """Nada pasa un cobro a 'vencido', así que la fecha es la única señal real."""
    base['cobros'] = [
        _cobro(id='vencido-real', estado='pendiente', fecha_vencimiento=AYER, total=3000),
        _cobro(id='al-dia', estado='pendiente', fecha_vencimiento=MANIANA, total=7000),
    ]
    plata = _resumen(admin)['plata']
    assert plata['deuda_vencida'] == 3000     # sólo el que ya venció
    assert plata['deuda_total'] == 10000      # los dos siguen impagos


def test_el_cobro_pagado_no_es_deuda(admin, base):
    base['cobros'] = [_cobro(estado='pagado', fecha_vencimiento=AYER)]
    plata = _resumen(admin)['plata']
    assert plata['deuda_total'] == 0
    assert plata['deuda_vencida'] == 0


def test_un_admin_sin_edificios_no_consulta_sin_filtro(admin, base):
    """Con `cids` vacío, un `.in_()` no filtra nada: hay que cortar antes."""
    base['consorcios'] = [{'id': 'cons-2', 'admin_id': 'admin-2', 'nombre': 'Ajeno'}]
    base['cobros'] = [_cobro(consorcio_id='cons-2', total=999999)]
    d = _resumen(admin)
    assert d['sin_consorcios'] is True
    assert d['consorcios'] == [] and d['atencion'] == []
    assert d['plata']['deuda_total'] == 0


# ── Bloque A: el semáforo de cierre ───────────────────────────────────────────

def test_sin_gastos_del_mes_el_paso_es_cargar_gastos(admin, base):
    base['gastos'] = []
    fila = _resumen(admin)['consorcios'][0]
    assert fila['estado'] == 'sin_gastos'
    assert fila['accion'] == 'Cargar gastos'
    assert fila['paso'] == 0


def test_con_gastos_y_sin_liquidacion_toca_liquidar(admin, base):
    base['gastos'] = [_gasto(monto=1500)]
    fila = _resumen(admin)['consorcios'][0]
    assert fila['estado'] == 'gastos'
    assert fila['accion'] == 'Generar liquidación'
    assert fila['gastos_mes'] == 1 and fila['total_gastos_mes'] == 1500


def test_el_gasto_del_mes_pasado_no_cuenta_como_del_mes(admin, base):
    base['gastos'] = [_gasto(fecha_gasto='2000-01-15', monto=1500)]
    fila = _resumen(admin)['consorcios'][0]
    assert fila['gastos_mes'] == 0
    assert fila['estado'] == 'sin_gastos'


def test_liquidacion_en_borrador_pide_revisar_el_prorrateo(admin, base):
    base['gastos'] = [_gasto()]
    base['liquidaciones'] = [{'id': 'liq-1', 'admin_id': 'admin-1',
                              'consorcio_id': 'cons-1', 'periodo': PERIODO,
                              'estado': 'borrador', 'numero_revision': 1,
                              'fecha_vencimiento_1': None}]
    fila = _resumen(admin)['consorcios'][0]
    assert fila['estado'] == 'prorrateo'
    assert fila['paso'] == 1
    assert fila['liquidacion_id'] == 'liq-1'


def test_con_vencimientos_cargados_lo_que_falta_es_enviar(admin, base):
    base['gastos'] = [_gasto()]
    base['liquidaciones'] = [{'id': 'liq-1', 'admin_id': 'admin-1',
                              'consorcio_id': 'cons-1', 'periodo': PERIODO,
                              'estado': 'borrador', 'numero_revision': 1,
                              'fecha_vencimiento_1': MANIANA}]
    fila = _resumen(admin)['consorcios'][0]
    assert fila['estado'] == 'vencimientos'
    assert fila['paso'] == 3
    assert fila['accion'] == 'Enviar los resúmenes'


def test_manda_la_ultima_revision_del_mismo_periodo(admin, base):
    """La reliquidación de la v8 es la que vale: es la que se emitió."""
    base['liquidaciones'] = [
        {'id': 'liq-1', 'admin_id': 'admin-1', 'consorcio_id': 'cons-1',
         'periodo': PERIODO, 'estado': 'borrador', 'numero_revision': 1,
         'fecha_vencimiento_1': None},
        {'id': 'liq-2', 'admin_id': 'admin-1', 'consorcio_id': 'cons-1',
         'periodo': PERIODO, 'estado': 'publicada', 'numero_revision': 2,
         'fecha_vencimiento_1': MANIANA},
    ]
    fila = _resumen(admin)['consorcios'][0]
    assert fila['liquidacion_id'] == 'liq-2'
    assert fila['estado'] == 'enviada'


def test_los_envios_se_cuentan_por_estado(admin, base):
    base['liquidaciones'] = [{'id': 'liq-1', 'admin_id': 'admin-1',
                              'consorcio_id': 'cons-1', 'periodo': PERIODO,
                              'estado': 'publicada', 'numero_revision': 1,
                              'fecha_vencimiento_1': MANIANA}]
    base['resumen_envios'] = [
        {'id': 'e-1', 'liquidacion_id': 'liq-1', 'estado': 'enviado'},
        {'id': 'e-2', 'liquidacion_id': 'liq-1', 'estado': 'leido'},
        {'id': 'e-3', 'liquidacion_id': 'liq-1', 'estado': 'fallido'},
        {'id': 'e-4', 'liquidacion_id': 'liq-1', 'estado': 'pendiente'},
    ]
    fila = _resumen(admin)['consorcios'][0]
    assert fila['envios'] == {'enviados': 2, 'fallidos': 1, 'pendientes': 1}


# ── Bloque B: la bandeja ──────────────────────────────────────────────────────

def _tipos(d):
    return [i['tipo'] for i in d['atencion']]


def test_la_bandeja_esta_vacia_cuando_no_hay_nada_pendiente(admin, base):
    assert _resumen(admin)['atencion'] == []


def test_el_envio_fallido_encabeza_la_bandeja(admin, base):
    """Un mail que rebotó es una expensa que el vecino nunca vio."""
    base['liquidaciones'] = [{'id': 'liq-1', 'admin_id': 'admin-1',
                              'consorcio_id': 'cons-1', 'periodo': PERIODO,
                              'estado': 'publicada', 'numero_revision': 1}]
    base['resumen_envios'] = [{'id': 'e-1', 'liquidacion_id': 'liq-1',
                               'estado': 'fallido'}]
    base['reclamos'] = [{'id': 'r-1', 'consorcio_id': 'cons-1', 'estado': 'activo',
                         'created_at': f'{HOY.isoformat()}T09:00:00+00:00'}]
    assert _tipos(_resumen(admin))[0] == 'envios_fallidos'


def test_la_bandeja_cuenta_solo_lo_de_sus_edificios(admin, base):
    base['reclamos'] = [
        {'id': 'mio', 'consorcio_id': 'cons-1', 'estado': 'activo',
         'created_at': f'{HOY.isoformat()}T09:00:00+00:00'},
        {'id': 'ajeno', 'consorcio_id': 'cons-2', 'estado': 'activo',
         'created_at': f'{HOY.isoformat()}T09:00:00+00:00'},
    ]
    item = next(i for i in _resumen(admin)['atencion'] if i['tipo'] == 'reclamos')
    assert item['cantidad'] == 1


def test_el_reclamo_cerrado_no_espera_a_nadie(admin, base):
    base['reclamos'] = [{'id': 'r-1', 'consorcio_id': 'cons-1', 'estado': 'resuelto',
                         'created_at': f'{HOY.isoformat()}T09:00:00+00:00'}]
    assert 'reclamos' not in _tipos(_resumen(admin))


def test_la_bandeja_dice_hace_cuanto_espera_el_mas_viejo(admin, base):
    viejo = (HOY - timedelta(days=6)).isoformat()
    base['reclamos'] = [
        {'id': 'r-1', 'consorcio_id': 'cons-1', 'estado': 'activo',
         'created_at': f'{viejo}T09:00:00+00:00'},
        {'id': 'r-2', 'consorcio_id': 'cons-1', 'estado': 'activo',
         'created_at': f'{HOY.isoformat()}T09:00:00+00:00'},
    ]
    item = next(i for i in _resumen(admin)['atencion'] if i['tipo'] == 'reclamos')
    assert item['cantidad'] == 2 and item['dias'] == 6


def test_las_tarifas_sin_confirmar_entran_a_la_bandeja(admin, base):
    base['gastos'] = [_gasto(id='g-1', tarifa_confirmada=False),
                      _gasto(id='g-2', tarifa_confirmada=True)]
    item = next(i for i in _resumen(admin)['atencion'] if i['tipo'] == 'tarifas')
    assert item['cantidad'] == 1


def test_los_avisos_de_pago_llegan_con_el_monto_declarado(admin, base):
    """Los endpoints existen sin pantalla: la bandeja es su puerta de entrada."""
    base['avisos_pago'] = [
        {'id': 'a-1', 'consorcio_id': 'cons-1', 'estado': 'pendiente', 'monto': 4000,
         'created_at': f'{HOY.isoformat()}T09:00:00+00:00'},
        {'id': 'a-2', 'consorcio_id': 'cons-1', 'estado': 'aceptado', 'monto': 9000,
         'created_at': f'{HOY.isoformat()}T09:00:00+00:00'},
    ]
    item = next(i for i in _resumen(admin)['atencion'] if i['tipo'] == 'avisos_pago')
    assert item['cantidad'] == 1 and item['monto'] == 4000


def test_la_solicitud_de_vecino_pendiente_se_ve_desde_el_panel(admin, base):
    base['vecinos'].append(
        {'id': 'vec-3', 'auth0_id': 'auth0|tres', 'estado_asociacion': 'pendiente',
         'consorcio_solicitado_id': 'cons-1', 'solicitud_at': f'{AYER}T09:00:00+00:00'})
    item = next(i for i in _resumen(admin)['atencion'] if i['tipo'] == 'solicitudes')
    assert item['cantidad'] == 1 and item['dias'] == 1


def test_la_factura_vencida_sin_pagar_entra_con_su_monto(admin, base):
    base['gastos'] = [
        _gasto(id='g-1', pagado=False, fecha_vencimiento=AYER, monto=2500),
        _gasto(id='g-2', pagado=False, fecha_vencimiento=MANIANA, monto=8000),
        _gasto(id='g-3', pagado=True, fecha_vencimiento=AYER, monto=9000),
    ]
    item = next(i for i in _resumen(admin)['atencion'] if i['tipo'] == 'gastos_vencidos')
    assert item['cantidad'] == 1 and item['monto'] == 2500


# ── Bloque C: los números de plata ────────────────────────────────────────────

def test_el_porcentaje_cobrado_se_mide_en_plata(admin, base):
    base['cobros'] = [
        _cobro(id='c-1', estado='pagado', total=7500),
        _cobro(id='c-2', estado='pendiente', total=2500),
    ]
    plata = _resumen(admin)['plata']
    assert plata['cobrado_pct'] == 75.0
    assert plata['emitido_monto'] == 10000 and plata['cobrado_monto'] == 7500
    assert plata['cobrado_periodo'] == PERIODO


def test_el_porcentaje_se_mide_contra_el_ultimo_periodo_emitido(admin, base):
    """A principio de mes todavía no se emitió nada; eso no es una caída a 0%."""
    anterior = app_mod._mes_anterior(PERIODO)
    base['cobros'] = [_cobro(id='c-1', periodo=anterior, estado='pagado', total=1000)]
    plata = _resumen(admin)['plata']
    assert plata['cobrado_periodo'] == anterior
    assert plata['cobrado_pct'] == 100.0


def test_sin_cobros_emitidos_el_porcentaje_es_nulo_y_no_cero(admin, base):
    base['cobros'] = []
    assert _resumen(admin)['plata']['cobrado_pct'] is None


def test_los_egresos_se_comparan_con_el_mes_anterior(admin, base):
    anterior = app_mod._mes_anterior(PERIODO)
    base['gastos'] = [
        _gasto(id='g-1', monto=1500, fecha_gasto=f'{PERIODO}-03'),
        _gasto(id='g-2', monto=1000, fecha_gasto=f'{anterior}-03'),
    ]
    plata = _resumen(admin)['plata']
    assert plata['egresos_mes'] == 1500
    assert plata['egresos_mes_anterior'] == 1000
    assert plata['variacion_egresos'] == 50.0


def test_sin_mes_anterior_no_hay_variacion_que_mostrar(admin, base):
    base['gastos'] = [_gasto(monto=1500)]
    assert _resumen(admin)['plata']['variacion_egresos'] is None


def test_los_honorarios_del_mes_salen_aparte(admin, base):
    base['gastos'] = [_gasto(id='g-1', categoria='honorarios', monto=300),
                      _gasto(id='g-2', categoria='ascensor', monto=700)]
    plata = _resumen(admin)['plata']
    assert plata['honorarios_mes'] == 300 and plata['egresos_mes'] == 1000


# ── Bloque D: la agenda ───────────────────────────────────────────────────────

def _agenda(admin, tipo=None):
    items = _resumen(admin)['agenda']
    return [i for i in items if tipo is None or i['tipo'] == tipo]


def test_la_agenda_trae_la_factura_que_vence_en_la_quincena(admin, base):
    base['gastos'] = [_gasto(pagado=False, fecha_vencimiento=MANIANA, monto=1200)]
    item = _agenda(admin, 'gasto')[0]
    assert item['fecha'] == MANIANA and item['monto'] == 1200
    assert item['consorcio'] == 'Mío'


def test_la_agenda_no_mira_mas_alla_de_catorce_dias(admin, base):
    base['gastos'] = [_gasto(pagado=False, fecha_vencimiento=LEJOS)]
    assert _agenda(admin, 'gasto') == []


def test_la_agenda_no_mira_para_atras(admin, base):
    base['gastos'] = [_gasto(pagado=False, fecha_vencimiento=AYER)]
    assert _agenda(admin, 'gasto') == []


def test_los_dos_vencimientos_de_la_expensa_son_dos_entradas(admin, base):
    base['liquidaciones'] = [{'id': 'liq-1', 'admin_id': 'admin-1',
                              'consorcio_id': 'cons-1', 'periodo': PERIODO,
                              'estado': 'publicada', 'numero_revision': 1,
                              'fecha_vencimiento_1': MANIANA,
                              'fecha_vencimiento_2': (HOY + timedelta(days=10)).isoformat()}]
    detalles = [i['detalle'] for i in _agenda(admin, 'vencimiento')]
    assert detalles == ['1er vencimiento', '2do vencimiento']


def test_la_agenda_sale_ordenada_por_fecha(admin, base):
    base['gastos'] = [
        _gasto(id='g-1', pagado=False, fecha_vencimiento=(HOY + timedelta(days=9)).isoformat()),
        _gasto(id='g-2', pagado=False, fecha_vencimiento=(HOY + timedelta(days=2)).isoformat()),
    ]
    fechas = [i['fecha'] for i in _agenda(admin)]
    assert fechas == sorted(fechas)


def test_la_reserva_cancelada_no_ocupa_la_agenda(admin, base):
    base['reservas_amenities'] = [
        {'id': 'res-1', 'amenity_id': 'amen-1', 'fecha': MANIANA,
         'hora_inicio': '18:00:00', 'estado': 'confirmada'},
        {'id': 'res-2', 'amenity_id': 'amen-1', 'fecha': MANIANA,
         'hora_inicio': '20:00:00', 'estado': 'cancelada'},
    ]
    reservas = _agenda(admin, 'reserva')
    assert len(reservas) == 1 and reservas[0]['titulo'] == 'SUM'


def test_la_reserva_del_edificio_ajeno_no_entra(admin, base):
    base['reservas_amenities'] = [
        {'id': 'res-2', 'amenity_id': 'amen-2', 'fecha': MANIANA,
         'hora_inicio': '20:00:00', 'estado': 'confirmada'}]
    assert _agenda(admin, 'reserva') == []


def test_el_envio_programado_cae_en_su_proximo_dia(admin, base):
    dia = min(HOY.day + 1, 28)
    base['envio_programado'] = [{'consorcio_id': 'cons-1', 'dia_mes': dia,
                                 'hora_envio': '09:00:00', 'activo': True}]
    envios = _agenda(admin, 'envio')
    assert len(envios) == 1 and envios[0]['fecha'][8:10] == f'{dia:02d}'


def test_el_envio_programado_apagado_no_se_agenda(admin, base):
    base['envio_programado'] = [{'consorcio_id': 'cons-1', 'dia_mes': min(HOY.day + 1, 28),
                                 'hora_envio': '09:00:00', 'activo': False}]
    assert _agenda(admin, 'envio') == []


# ── Degradación: una migración sin correr no deja la pantalla en blanco ───────

class _TablaQueFalla:
    """Doble que rompe sólo en una tabla, como una columna que todavía no existe."""

    def __init__(self, real, tabla_rota):
        self.real = real
        self.tabla_rota = tabla_rota

    def table(self, nombre):
        if nombre == self.tabla_rota:
            raise RuntimeError('column "estado_asociacion" does not exist')
        return self.real.table(nombre)


def test_una_tabla_que_falla_degrada_el_bloque_y_no_la_pantalla(admin, base,
                                                               app_modulo, monkeypatch):
    monkeypatch.setattr(app_modulo, 'supabase',
                        _TablaQueFalla(app_modulo.supabase, 'vecinos'))
    d = _resumen(admin)
    assert 'solicitudes' in d['degradado']
    # El cobro de `cons-1` del conftest sigue contándose: degrada el bloque
    # que falló, no la pantalla entera.
    assert d['consorcios'] and d['plata']['deuda_total'] == 100


# ── El día del mes, con meses cortos ──────────────────────────────────────────

@pytest.mark.parametrize('hoy, dia, esperado', [
    (date(2026, 1, 10), 20, date(2026, 1, 20)),   # este mes, todavía no pasó
    (date(2026, 1, 25), 20, date(2026, 2, 20)),   # ya pasó: el que viene
    (date(2026, 1, 10), 10, date(2026, 1, 10)),   # es hoy
    (date(2026, 1, 31), 31, date(2026, 1, 31)),
    (date(2026, 2, 5), 31, date(2026, 2, 28)),    # febrero recorta
    (date(2026, 12, 20), 5, date(2027, 1, 5)),    # cruza el año
    (date(2026, 1, 10), None, None),
    (date(2026, 1, 10), 99, None),
])
def test_proximo_dia_del_mes(hoy, dia, esperado):
    assert app_mod._proximo_dia_del_mes(hoy, dia) == esperado
