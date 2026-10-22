"""Aislamiento entre administradores y entre vecinos, endpoint por endpoint (roadmap #16).

Un administrador ajeno (el perfil `superadmin` del ambiente de QA, que no tiene
consorcios propios) le pega a cada endpoint de administración con los IDs del
Admin QA: el consorcio, sus UF, gastos, cobros, liquidación, reclamos, avisos,
etc. Del lado vecino, `vecino2` intenta lo mismo con lo de `vecino` (otra UF
del mismo edificio). Para cada request se exige:

- que no devuelva datos del otro (ni en JSON, ni en Excel, ni en PDF), y
- al final, que ninguna tabla de la base haya cambiado.

Los datos de la víctima se crean por la API, como lo haría la app, en períodos
de 2099 para no cruzarse con los otros E2E (el cron no los toca).
"""

import io
import os
import zipfile
from datetime import date, timedelta

import psycopg
import pytest
import requests

BASE = os.environ.get('NIDDO_QA_URL', 'http://localhost:5055')
DB = os.environ.get('NIDDO_QA_DB', f"postgresql://niddo@localhost:{os.environ.get('PG_PORT', '54329')}/niddo_qa")

C1 = 'c0000000-0000-4000-8000-000000000001'     # Edificio QA Libertador (Admin QA)
UF1 = 'd0000000-0000-4000-8000-000000000001'    # 1A, de `vecino`
V1 = 'b0000000-0000-4000-8000-000000000001'
PERIODO = '2099-12'

# Textos que sólo aparecen en datos de la víctima. Si uno vuelve en la
# respuesta al intruso, hay fuga.
MARCAS = ['QA Libertador', 'Vecina Uno', 'vecino1.qa@niddo.test', 'EDIF.QA.LIBERTADOR',
          'Abono mantenimiento ascensor', 'Reclamo de aislamiento', 'Mensaje de aislamiento',
          'Comunicado de aislamiento']


def _sesion(quien):
    s = requests.Session()
    r = s.get(f'{BASE}/qa/login/{quien}', allow_redirects=False)
    assert r.status_code in (302, 303), f'no se pudo entrar como {quien}: {r.status_code}'
    return s


def _uno(cur, sql, *args):
    cur.execute(sql, args)
    fila = cur.fetchone()
    assert fila, f'sin datos para: {sql}'
    return str(fila[0])


def _foto(cur):
    cur.execute("select tablename from pg_tables where schemaname = 'public' order by 1")
    tablas = [t for (t,) in cur.fetchall()]
    foto = {}
    for t in tablas:
        # `ultima_actividad` es el reloj de sesión del propio intruso: que se
        # mueva no es tocar datos ajenos.
        cur.execute(f"select md5(coalesce(string_agg(f, '|' order by f), '')) "
                    f"from (select (to_jsonb(x) - 'ultima_actividad')::text f from public.{t} x) y")
        foto[t] = cur.fetchone()[0]
    return foto


@pytest.fixture(scope='module')
def victima():
    """Crea por la API los datos del Admin QA y de `vecino`, y devuelve sus IDs."""
    adm, vec = _sesion('admin'), _sesion('vecino')
    ok = lambda r: r.status_code in (200, 201) or pytest.fail(f'{r.request.method} {r.url}: {r.status_code} {r.text[:200]}')
    ok(adm.post(f'{BASE}/api/cobros/generar', json={
        'consorcio_id': C1, 'periodo': PERIODO, 'monto_base': 1000, 'fecha_vencimiento': '2099-12-10'}))
    ok(adm.post(f'{BASE}/api/liquidaciones', json={'consorcio_id': C1, 'periodo': PERIODO}))
    ok(adm.post(f'{BASE}/api/admin/comunicados', json={
        'consorcio_id': C1, 'titulo': 'Comunicado de aislamiento', 'cuerpo': 'Comunicado de aislamiento'}))
    ok(adm.post(f'{BASE}/api/admin/votaciones', json={'consorcio_id': C1, 'titulo': 'Votación de aislamiento'}))
    ok(adm.post(f'{BASE}/api/admin/archivos', data={'consorcio_id': C1, 'nombre': 'reglamento.pdf', 'categoria': 'reglamento'},
                files={'archivo': ('reglamento.pdf', b'%PDF-1.4 aislamiento', 'application/pdf')}))
    ok(vec.post(f'{BASE}/api/reclamos', json={'titulo': 'Reclamo de aislamiento', 'descripcion': 'Reclamo de aislamiento'}))
    ok(vec.post(f'{BASE}/api/mensajes', json={'cuerpo': 'Mensaje de aislamiento'}))

    with psycopg.connect(DB, autocommit=True) as con, con.cursor() as cur:
        cobro = _uno(cur, 'select id from cobros where unidad_id = %s and periodo = %s', UF1, PERIODO)
        ok(vec.post(f'{BASE}/api/avisos_pago', json={'cobro_id': cobro, 'monto': 1000, 'medio_pago': 'Transferencia'}))
        amen = _uno(cur, 'select id from amenities where consorcio_id = %s order by nombre limit 1', C1)
        dia = (date.today() + timedelta(days=20)).isoformat()
        ok(vec.post(f'{BASE}/api/reservas_amenities', json={
            'amenity_id': amen, 'fecha': dia, 'hora_inicio': '10:00', 'hora_fin': '11:00'}))
        lid = _uno(cur, 'select id from liquidaciones where consorcio_id = %s and periodo = %s order by created_at desc limit 1', C1, PERIODO)
        return {
            'cid': C1, 'uid': UF1, 'vid': V1, 'cobro': cobro, 'amen': amen, 'lid': lid,
            'gid': _uno(cur, 'select id from gastos where consorcio_id = %s order by created_at limit 1', C1),
            'reserva': _uno(cur, 'select id from reservas_amenities where amenity_id = %s order by created_at desc limit 1', amen),
            'pid': _uno(cur, 'select id from liquidacion_prorrateo where liquidacion_id = %s limit 1', lid),
            'com': _uno(cur, "select id from comunicados where titulo = 'Comunicado de aislamiento' limit 1"),
            'vot': _uno(cur, "select id from votaciones where titulo = 'Votación de aislamiento' limit 1"),
            'arch': _uno(cur, 'select id from archivos_consorcio where consorcio_id = %s limit 1', C1),
            'medio': _uno(cur, 'select id from medios_pago where consorcio_id = %s limit 1', C1),
            'reclamo': _uno(cur, "select id from reclamos where titulo = 'Reclamo de aislamiento' limit 1"),
            'msg': _uno(cur, "select id from mensajes where vecino_id = %s order by created_at desc limit 1", V1),
            'aviso': _uno(cur, 'select id from avisos_pago where cobro_id = %s limit 1', cobro),
        }


# (método, ruta, cuerpo). Las rutas usan los IDs de `victima`.
ADMIN = [
    ('PUT', '/api/consorcios/{cid}', {'nombre': 'INTRUSO', 'banco_cbu': '9999'}),
    ('DELETE', '/api/consorcios/{cid}', None),
    ('GET', '/api/consorcios/{cid}/unidades', None),
    ('POST', '/api/consorcios/{cid}/unidades', {'numero': 'INTRUSO'}),
    ('PUT', '/api/consorcios/{cid}/unidades/{uid}', {'numero': 'INTRUSO'}),
    ('DELETE', '/api/consorcios/{cid}/unidades/{uid}', None),
    ('GET', '/api/consorcios/{cid}/export/excel', None),
    ('GET', '/api/consorcios/{cid}/export/pdf', None),
    ('GET', '/api/gastos?consorcio_id={cid}', None),
    ('POST', '/api/gastos', {'consorcio_id': '{cid}', 'descripcion': 'INTRUSO', 'monto': 1,
                             'categoria': 'otros', 'fecha_gasto': '2099-12-01'}),
    ('PUT', '/api/gastos/{gid}', {'monto': 1}),
    ('DELETE', '/api/gastos/{gid}', None),
    ('GET', '/api/gastos/{gid}/comprobante', None),
    ('GET', '/api/gastos/export?consorcio_id={cid}', None),
    ('GET', '/api/cobros?consorcio_id={cid}', None),
    ('POST', '/api/cobros/generar', {'consorcio_id': '{cid}', 'periodo': '2098-01', 'monto_base': 1}),
    ('PUT', '/api/cobros/{cobro}', {'estado': 'pagado'}),
    ('GET', '/api/cobros/mora?consorcio_id={cid}', None),
    ('GET', '/api/cobros/export?consorcio_id={cid}', None),
    ('GET', '/api/balance?consorcio_id={cid}', None),
    ('GET', '/api/balance/export?consorcio_id={cid}', None),
    ('GET', '/api/consorcios/{cid}/amenities', None),
    ('POST', '/api/consorcios/{cid}/amenities', {'nombre': 'INTRUSO'}),
    ('PUT', '/api/consorcios/{cid}/amenities/{amen}', {'nombre': 'INTRUSO'}),
    ('DELETE', '/api/consorcios/{cid}/amenities/{amen}', None),
    ('GET', '/api/reservas_amenities?consorcio_id={cid}', None),
    ('DELETE', '/api/reservas_amenities/{reserva}', None),
    ('GET', '/api/consorcios/{cid}/vecinos/pendientes', None),
    ('POST', '/api/consorcios/{cid}/vecinos/{vid}/aprobar', {}),
    ('POST', '/api/consorcios/{cid}/vecinos/{vid}/rechazar', {}),
    ('POST', '/api/consorcios/{cid}/vecinos/{vid}/asignar-unidad', {'unidad_id': '{uid}'}),
    ('GET', '/api/admin/consorcios/{cid}/mercadopago', None),
    ('PUT', '/api/admin/consorcios/{cid}/mercadopago', {'access_token': 'TEST-intruso'}),
    ('DELETE', '/api/admin/consorcios/{cid}/mercadopago', None),
    ('GET', '/api/admin/mensajes?consorcio_id={cid}', None),
    ('GET', '/api/admin/mensajes/hilo/{vid}', None),
    ('POST', '/api/admin/mensajes/hilo/{vid}', {'cuerpo': 'INTRUSO'}),
    ('GET', '/api/admin/mensajes/adjunto/{msg}', None),
    ('GET', '/api/admin/comunicados?consorcio_id={cid}', None),
    ('POST', '/api/admin/comunicados', {'consorcio_id': '{cid}', 'titulo': 'INTRUSO', 'cuerpo': 'INTRUSO'}),
    ('DELETE', '/api/admin/comunicados/{com}', None),
    ('POST', '/api/admin/votaciones', {'consorcio_id': '{cid}', 'titulo': 'INTRUSO'}),
    ('PUT', '/api/admin/votaciones/{vot}', {'estado': 'cerrada'}),
    ('GET', '/api/admin/consorcios/{cid}/reglamento', None),
    ('DELETE', '/api/admin/archivos/{arch}', None),
    ('GET', '/api/admin/medios-pago?consorcio_id={cid}', None),
    ('POST', '/api/admin/medios-pago', {'consorcio_id': '{cid}', 'nombre': 'INTRUSO'}),
    ('DELETE', '/api/admin/medios-pago/{medio}', None),
    ('GET', '/api/admin/reclamos?consorcio_id={cid}', None),
    ('PUT', '/api/admin/reclamos/{reclamo}', {'estado': 'resuelto'}),
    ('GET', '/api/admin/reclamos/{reclamo}/adjunto', None),
    ('GET', '/api/admin/reclamos/{reclamo}/mensajes', None),
    ('POST', '/api/admin/reclamos/{reclamo}/mensajes', {'cuerpo': 'INTRUSO'}),
    ('GET', '/api/admin/avisos-pago?consorcio_id={cid}', None),
    ('PUT', '/api/admin/avisos-pago/{aviso}', {'estado': 'aprobado'}),
    ('GET', '/api/admin/avisos-pago/{aviso}/comprobante', None),
    ('GET', '/api/liquidaciones?consorcio_id={cid}', None),
    ('GET', '/api/liquidaciones/gastos-disponibles?consorcio_id={cid}&periodo=' + PERIODO, None),
    ('POST', '/api/liquidaciones', {'consorcio_id': '{cid}', 'periodo': '2098-01'}),
    ('PUT', '/api/liquidaciones/{lid}', {'estado': 'enviada'}),
    ('DELETE', '/api/liquidaciones/{lid}', None),
    ('GET', '/api/liquidaciones/{lid}/rubros', None),
    ('GET', '/api/liquidaciones/{lid}/prorrateo', None),
    ('PUT', '/api/liquidaciones/{lid}/prorrateo/{pid}', {'monto': 1}),
    ('GET', '/api/liquidaciones/{lid}/resumen/{uid}', None),
    ('GET', '/api/liquidaciones/{lid}/pdf', None),
    ('POST', '/api/liquidaciones/{lid}/enviar', {}),
    ('GET', '/api/liquidaciones/{lid}/envios', None),
    ('GET', '/api/envio-programado/{cid}', None),
    ('POST', '/api/envio-programado/{cid}', {'activo': True, 'dia_mes': 1}),
    ('GET', '/api/dashboard/resumen?consorcio_id={cid}', None),
    ('GET', '/api/gastos/tarifas-pendientes?consorcio_id={cid}', None),
]

# `vecino2` (UF 1B) contra lo de `vecino` (UF 1A), mismo edificio.
VECINO = [
    ('GET', '/api/vecinos/cobros/{cobro}/resumen', None),
    ('POST', '/api/vecinos/cobros/{cobro}/pagar', {}),
    ('GET', '/api/vecinos/cobros/{cobro}/cupon', None),
    ('DELETE', '/api/reclamos/{reclamo}', None),
    ('GET', '/api/reclamos/{reclamo}/adjunto', None),
    ('GET', '/api/reclamos/{reclamo}/mensajes', None),
    ('POST', '/api/reclamos/{reclamo}/mensajes', {'cuerpo': 'INTRUSO'}),
    ('GET', '/api/mensajes/{msg}/adjunto', None),
    ('DELETE', '/api/reservas_amenities/{reserva}', None),
    ('GET', '/api/vecinos/cobros', None),
    ('GET', '/api/reclamos', None),
    ('GET', '/api/mensajes', None),
    ('GET', '/api/avisos_pago', None),
    ('GET', '/api/liquidaciones/{lid}/resumen/{uid}', None),
    # Endpoints de administración: un vecino no entra.
    ('GET', '/api/consorcios', None),
    ('GET', '/api/cobros?consorcio_id={cid}', None),
    ('GET', '/api/liquidaciones/{lid}/pdf', None),
]


def _rellenar(valor, ids):
    if isinstance(valor, str):
        return valor.format(**ids)
    if isinstance(valor, dict):
        return {k: _rellenar(v, ids) for k, v in valor.items()}
    return valor


def _texto(r):
    """Lo que el intruso puede leer de la respuesta, también dentro de un Excel."""
    crudo = r.content
    if crudo[:2] == b'PK':                       # xlsx: el texto está en los XML
        with zipfile.ZipFile(io.BytesIO(crudo)) as z:
            return ' '.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist() if n.endswith('.xml'))
    return crudo.decode('utf-8', 'replace')


def _fugas(r):
    if r.content[:4] == b'%PDF':
        return ['devolvió un PDF']
    txt = _texto(r)
    return [m for m in MARCAS if m in txt]


@pytest.fixture(scope='module')
def foto_inicial(victima):
    with psycopg.connect(DB, autocommit=True) as con, con.cursor() as cur:
        return _foto(cur)


def _probar(quien, metodo, ruta, cuerpo, victima, vacio=True):
    s = _sesion(quien)
    r = s.request(metodo, BASE + _rellenar(ruta, victima), json=_rellenar(cuerpo, victima),
                  allow_redirects=False)
    assert r.status_code < 500, f'{metodo} {ruta}: {r.status_code} {r.text[:200]}'
    assert not _fugas(r), f'{quien} ve datos ajenos en {metodo} {ruta}: {_fugas(r)}'
    if vacio and 200 <= r.status_code < 300 and metodo == 'GET' and r.content[:2] != b'PK':
        # Un GET ajeno que responde 200 tiene que venir vacío (un Excel vacío
        # pesa varios KB por el formato: ahí manda el chequeo de fugas).
        assert len(r.content) < 600, f'{metodo} {ruta} devolvió {len(r.content)} bytes'


@pytest.mark.parametrize('metodo,ruta,cuerpo', ADMIN, ids=[f'{m} {r}' for m, r, _ in ADMIN])
def test_un_admin_no_toca_el_consorcio_de_otro(foto_inicial, victima, metodo, ruta, cuerpo):
    _probar('superadmin', metodo, ruta, cuerpo, victima)


@pytest.mark.parametrize('metodo,ruta,cuerpo', VECINO, ids=[f'{m} {r}' for m, r, _ in VECINO])
def test_un_vecino_no_toca_lo_de_otra_uf(foto_inicial, victima, metodo, ruta, cuerpo):
    # Los listados del vecino traen lo suyo (sus cobros): ahí alcanza con que
    # no aparezca nada de la otra UF.
    _probar('vecino2', metodo, ruta, cuerpo, victima, vacio=False)


def test_ninguna_request_ajena_cambio_la_base(foto_inicial):
    """Va último en el módulo: compara toda la base contra la foto de antes."""
    with psycopg.connect(DB, autocommit=True) as con, con.cursor() as cur:
        despues = _foto(cur)
    cambiadas = [t for t in foto_inicial if foto_inicial[t] != despues.get(t)]
    assert not cambiadas, f'las requests ajenas modificaron: {cambiadas}'
