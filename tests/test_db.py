"""db.py contra un Postgres de verdad.

El resto de los tests usa el doble de conftest.py, que responde lo que la app
espera de la base. Estos prueban lo otro: que db.py efectivamente responda eso
—mismo JSON, mismos errores— cuando del otro lado hay Postgres.

Necesitan una base con `schema.sql` aplicado y se saltean si no hay una:

    NIDDO_TEST_DATABASE_URL=postgresql://...  pytest tests/test_db.py

Usar una rama de Neon creada para esto, nunca la principal: los tests escriben.
Lo que crean cuelga de un consorcio propio que se borra al final.
"""

import os
import uuid

import pytest

import db

URL = os.environ.get('NIDDO_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='sin NIDDO_TEST_DATABASE_URL')


@pytest.fixture(scope='module')
def cli():
    return db.create_client(URL)


@pytest.fixture
def cons(cli):
    """Un consorcio de prueba; al borrarlo arrastra todo lo que cuelga de él."""
    fila = cli.table('consorcios').insert({'nombre': f'test-db-{uuid.uuid4()}'}).execute().data[0]
    yield fila
    cli.table('consorcios').delete().eq('id', fila['id']).execute()


def test_insert_devuelve_la_fila_con_los_defaults(cli, cons):
    assert len(cons['id']) == 36
    assert cons['metodo_prorrateo'] == 'm2'
    assert cons['created_at'].endswith('+00:00')
    assert cons['tasa_interes_mora'] == 0


def test_tipos_como_los_devuelve_postgrest(cli, cons):
    uf = cli.table('unidades_funcionales').insert(
        {'consorcio_id': cons['id'], 'numero': '1A', 'superficie_m2': 55.5}).execute().data[0]
    gasto = cli.table('gastos').insert({
        'consorcio_id': cons['id'], 'descripcion': 'Luz', 'monto': 15430.50,
        'fecha_gasto': '2026-06-05', 'unidad_id': uf['id'],
    }).execute().data[0]
    assert gasto['monto'] == 15430.5 and isinstance(gasto['monto'], float)
    assert gasto['fecha_gasto'] == '2026-06-05'
    assert gasto['pagado'] is False
    vot = cli.table('votaciones').insert(
        {'consorcio_id': cons['id'], 'titulo': 'Pintura'}).execute().data[0]
    assert vot['opciones'] == ['Si', 'No', 'Abstención']


def test_insert_de_varias_filas_con_claves_distintas(cli, cons):
    filas = cli.table('unidades_funcionales').insert([
        {'consorcio_id': cons['id'], 'numero': '1', 'piso': 'PB'},
        {'consorcio_id': cons['id'], 'numero': '2'},
    ]).execute().data
    assert [f['numero'] for f in filas] == ['1', '2']
    assert filas[1]['piso'] is None


def test_filtros_orden_y_limite(cli, cons):
    cli.table('unidades_funcionales').insert([
        {'consorcio_id': cons['id'], 'numero': n, 'piso': p}
        for n, p in (('3', None), ('1', 'PB'), ('2', '1'))
    ]).execute()
    q = lambda: cli.table('unidades_funcionales').select('numero').eq('consorcio_id', cons['id'])
    assert [f['numero'] for f in q().order('numero').execute().data] == ['1', '2', '3']
    assert [f['numero'] for f in q().order('numero', desc=True).limit(2).execute().data] == ['3', '2']
    assert [f['numero'] for f in q().is_('piso', 'null').execute().data] == ['3']
    assert sorted(f['numero'] for f in q().not_.is_('piso', 'null').execute().data) == ['1', '2']
    assert sorted(f['numero'] for f in q().in_('numero', ['1', '3']).execute().data) == ['1', '3']
    assert q().in_('numero', []).execute().data == []
    assert sorted(f['numero'] for f in q().neq('numero', '2').execute().data) == ['1', '3']
    assert [f['numero'] for f in q().or_('numero.eq.1,piso.ilike.*1*').order('numero').execute().data] == ['1', '2']


def test_embebidos_hacia_el_padre_y_hacia_los_hijos(cli, cons):
    uf = cli.table('unidades_funcionales').insert(
        {'consorcio_id': cons['id'], 'numero': '7B'}).execute().data[0]
    cobro = cli.table('cobros').insert({
        'unidad_id': uf['id'], 'consorcio_id': cons['id'], 'periodo': '2026-07',
        'monto_base': 100, 'total': 100,
    }).execute().data[0]
    fila = cli.table('cobros').select('id, unidades_funcionales(numero), consorcios(nombre)') \
        .eq('id', cobro['id']).single().execute().data
    assert fila == {'id': cobro['id'], 'unidades_funcionales': {'numero': '7B'},
                    'consorcios': {'nombre': cons['nombre']}}
    hijos = cli.table('consorcios').select('nombre, unidades_funcionales(numero)') \
        .eq('id', cons['id']).execute().data
    assert hijos[0]['unidades_funcionales'] == [{'numero': '7B'}]


def test_embebido_con_alias_por_columna_de_la_fk(cli):
    """La auditoría del superadmin trae dos administradores de la misma tabla."""
    a = cli.table('administradores').insert(
        {'auth0_id': f'test|{uuid.uuid4()}', 'email': f'{uuid.uuid4()}@test', 'nombre': 'Actor'}).execute().data[0]
    b = cli.table('administradores').insert(
        {'auth0_id': f'test|{uuid.uuid4()}', 'email': f'{uuid.uuid4()}@test', 'nombre': 'Objetivo'}).execute().data[0]
    fila = cli.table('superadmin_auditoria').insert(
        {'actor_id': a['id'], 'target_id': b['id'], 'accion': 'aprobar'}).execute().data[0]
    res = cli.table('superadmin_auditoria') \
        .select('id, actor:actor_id(nombre), objetivo:target_id(nombre)') \
        .eq('id', fila['id']).single().execute().data
    assert res == {'id': fila['id'], 'actor': {'nombre': 'Actor'}, 'objetivo': {'nombre': 'Objetivo'}}
    # Sin decir por cuál FK, la relación es ambigua y tiene que fallar, no adivinar.
    with pytest.raises(db.APIError) as e:
        cli.table('superadmin_auditoria').select('administradores(nombre)').execute()
    assert e.value.code == 'PGRST201'
    con_pista = cli.table('superadmin_auditoria').select('administradores!target_id(nombre)') \
        .eq('id', fila['id']).single().execute().data
    assert con_pista == {'administradores': {'nombre': 'Objetivo'}}
    cli.table('superadmin_auditoria').delete().eq('id', fila['id']).execute()
    cli.table('administradores').delete().in_('id', [a['id'], b['id']]).execute()


def test_order_por_columna_del_padre(cli, cons):
    ufs = cli.table('unidades_funcionales').insert([
        {'consorcio_id': cons['id'], 'numero': n} for n in ('B', 'A')
    ]).execute().data
    liq = cli.table('liquidaciones').insert({
        'consorcio_id': cons['id'], 'admin_id': _admin(cli), 'periodo': '2026-07',
    }).execute().data[0]
    cli.table('liquidacion_prorrateo').insert(
        [{'liquidacion_id': liq['id'], 'unidad_id': u['id']} for u in ufs]).execute()
    filas = cli.table('liquidacion_prorrateo').select('unidades_funcionales(numero)') \
        .eq('liquidacion_id', liq['id']).order('unidades_funcionales(numero)').execute().data
    assert [f['unidades_funcionales']['numero'] for f in filas] == ['A', 'B']


def test_update_devuelve_solo_lo_que_toco(cli, cons):
    ufs = cli.table('unidades_funcionales').insert([
        {'consorcio_id': cons['id'], 'numero': n} for n in ('1', '2')
    ]).execute().data
    res = cli.table('unidades_funcionales').update({'piso': '3', 'ambientes': 2}) \
        .eq('id', ufs[0]['id']).execute().data
    assert len(res) == 1 and res[0]['piso'] == '3' and res[0]['ambientes'] == 2
    otra = cli.table('unidades_funcionales').select('piso').eq('id', ufs[1]['id']).single().execute()
    assert otra.data['piso'] is None


def test_upsert_actualiza_o_inserta(cli):
    usuario = str(uuid.uuid4())
    clave = 'usuario_tipo,usuario_id,seccion'
    fila = {'usuario_tipo': 'vecino', 'usuario_id': usuario, 'seccion': 'gastos'}
    primera = cli.table('secciones_vistas').upsert(fila, on_conflict=clave).execute().data[0]
    segunda = cli.table('secciones_vistas').upsert(
        {**fila, 'visto_at': '2030-01-01T00:00:00+00:00'}, on_conflict=clave).execute().data[0]
    assert primera['visto_at'] != segunda['visto_at'] == '2030-01-01T00:00:00+00:00'
    filas = cli.table('secciones_vistas').select('*').eq('usuario_id', usuario).execute().data
    assert len(filas) == 1
    cli.table('secciones_vistas').delete().eq('usuario_id', usuario).execute()


def test_upsert_solo_con_las_columnas_del_conflicto(cli, cons):
    """comunicados_leidos: marcar leído dos veces no rompe ni duplica."""
    com = cli.table('comunicados').insert({'admin_id': _admin(cli), 'consorcio_id': cons['id'],
                                          'asunto': 'a', 'cuerpo': 'b'}).execute().data[0]
    vec = cli.table('vecinos').insert({'auth0_id': f'test|{uuid.uuid4()}',
                                      'email': f'{uuid.uuid4()}@test'}).execute().data[0]
    fila = {'comunicado_id': com['id'], 'vecino_id': vec['id']}
    for _ in range(2):
        cli.table('comunicados_leidos').upsert(fila, on_conflict='comunicado_id,vecino_id').execute()
    assert len(cli.table('comunicados_leidos').select('id').eq('vecino_id', vec['id']).execute().data) == 1
    cli.table('vecinos').delete().eq('id', vec['id']).execute()


def test_upsert_por_columna_unica(cli):
    endpoint = f'https://push.test/{uuid.uuid4()}'
    datos = {'usuario_tipo': 'admin', 'usuario_id': str(uuid.uuid4()), 'endpoint': endpoint,
             'p256dh': 'k', 'auth': 'a'}
    cli.table('push_suscripciones').upsert(datos, on_conflict='endpoint').execute()
    cli.table('push_suscripciones').upsert({**datos, 'auth': 'b'}, on_conflict='endpoint').execute()
    filas = cli.table('push_suscripciones').select('auth').eq('endpoint', endpoint).execute().data
    assert filas == [{'auth': 'b'}]
    cli.table('push_suscripciones').delete().eq('endpoint', endpoint).execute()


def test_delete_devuelve_lo_borrado(cli, cons):
    uf = cli.table('unidades_funcionales').insert(
        {'consorcio_id': cons['id'], 'numero': 'X'}).execute().data[0]
    borradas = cli.table('unidades_funcionales').delete().eq('id', uf['id']).execute().data
    assert [b['id'] for b in borradas] == [uf['id']]
    assert cli.table('unidades_funcionales').delete().eq('id', uf['id']).execute().data == []


def test_update_o_delete_sin_filtros_se_rechazan(cli):
    with pytest.raises(db.APIError):
        cli.table('consorcios').delete().execute()
    with pytest.raises(db.APIError):
        cli.table('consorcios').update({'nombre': 'x'}).execute()


def test_errores_con_el_texto_que_la_app_reconoce(cli, cons):
    with pytest.raises(db.APIError) as e:
        cli.table('envio_programado').insert([
            {'consorcio_id': cons['id'], 'admin_id': _admin(cli)},
            {'consorcio_id': cons['id'], 'admin_id': _admin(cli)},
        ]).execute()
    assert '23505' in str(e.value) and 'duplicate key' in str(e.value)

    with pytest.raises(db.APIError) as e:
        cli.table('consorcios').select('no_existe').execute()
    assert '42703' in str(e.value) and 'does not exist' in str(e.value)


def test_single_sin_filas_falla_como_supabase(cli):
    with pytest.raises(db.APIError) as e:
        cli.table('consorcios').select('*').eq('id', str(uuid.uuid4())).single().execute()
    assert e.value.code == 'PGRST116'


def test_reconecta_si_se_corto_la_conexion(cli, cons):
    cli._conectar().close()
    assert cli.table('consorcios').select('id').eq('id', cons['id']).execute().data


def _admin(cli):
    filas = cli.table('administradores').select('id').limit(1).execute().data
    if filas:
        return filas[0]['id']
    return cli.table('administradores').insert(
        {'auth0_id': f'test|{uuid.uuid4()}', 'email': f'{uuid.uuid4()}@test'}).execute().data[0]['id']
