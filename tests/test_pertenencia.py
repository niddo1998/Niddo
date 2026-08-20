"""Un administrador no puede tocar los datos de otro.

Hasta acá `require_auth` contestaba "sos un administrador aprobado" y nadie
contestaba "este consorcio es tuyo". Con las dos preguntas confundidas en una,
cambiar un UUID en la URL alcanzaba para editar la liquidación del edificio de
al lado, bajarse su padrón o mandarle un mail a sus vecinos.

Cada test de acá abajo es esa request: la sesión es la de `admin-1` y el UUID
es de `admin-2`. Se comprueban las dos mitades, porque una sola miente:

  * la respuesta es 404 —y no 403, que confirmaría que el UUID existe—;
  * la base quedó igual. Un endpoint que responde 404 después de haber
    escrito sigue estando roto, y el status por sí solo no lo muestra.

El último bloque es el simétrico: `admin-1` sobre sus propios datos tiene que
seguir funcionando. Sin eso, un `abort(404)` en el lugar equivocado pasaría
todos los tests de arriba y rompería la aplicación entera.
"""

import os

import pytest

# Igual que en test_generacion.py: `app.py` lee estas variables al importarse.
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'test')
os.environ.setdefault('AUTH0_DOMAIN', 'test.auth0.com')
os.environ.setdefault('AUTH0_CLIENT_ID', 'test')
os.environ.setdefault('AUTH0_CLIENT_SECRET', 'test')
# Sin esto la cookie de sesión sale marcada Secure y el cliente de test, que
# habla http, no la manda: todas las requests darían 302 al login.
os.environ['NIDDO_LOCAL'] = '1'

import app as app_mod


# ── Doble de Supabase ─────────────────────────────────────────────────────────
# El de test_generacion.py sirve para una tabla y valida columnas contra el
# schema de gastos. Acá hace falta lo otro: varias tablas, y update/delete de
# verdad para poder mirar si la fila cambió.

class _Resultado:
    def __init__(self, data):
        self.data = data


class _Consulta:
    def __init__(self, store, tabla):
        self.store = store
        self.tabla = tabla
        self.filas = store.setdefault(tabla, [])
        self.filtros = []
        self.op = 'select'
        self.payload = None
        self.una_sola = False

    # -- armado --
    def select(self, *_a, **_k):
        return self

    def insert(self, payload):
        self.op, self.payload = 'insert', payload
        return self

    def upsert(self, payload, **_k):
        self.op, self.payload = 'insert', payload
        return self

    def update(self, payload):
        self.op, self.payload = 'update', payload
        return self

    def delete(self):
        self.op = 'delete'
        return self

    def eq(self, campo, valor):
        self.filtros.append(lambda f: f.get(campo) == valor)
        return self

    def in_(self, campo, valores):
        valores = list(valores)
        self.filtros.append(lambda f: f.get(campo) in valores)
        return self

    def gte(self, campo, valor):
        self.filtros.append(lambda f: str(f.get(campo) or '') >= valor)
        return self

    def lte(self, campo, valor):
        self.filtros.append(lambda f: str(f.get(campo) or '') <= valor)
        return self

    def lt(self, campo, valor):
        self.filtros.append(lambda f: str(f.get(campo) or '') < valor)
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def single(self):
        self.una_sola = True
        return self

    # -- ejecución --
    def _match(self):
        return [f for f in self.filas if all(p(f) for p in self.filtros)]

    def execute(self):
        if self.op == 'insert':
            nuevas = self.payload if isinstance(self.payload, list) else [self.payload]
            creadas = []
            for fila in nuevas:
                fila = dict(fila)
                fila.setdefault('id', f'{self.tabla}-nuevo-{len(self.filas)}')
                self.filas.append(fila)
                creadas.append(fila)
            return _Resultado(creadas)

        alcanzadas = self._match()

        if self.op == 'update':
            for fila in alcanzadas:
                fila.update(self.payload)
            return _Resultado(list(alcanzadas))

        if self.op == 'delete':
            for fila in alcanzadas:
                self.filas.remove(fila)
            return _Resultado(list(alcanzadas))

        if self.una_sola:
            return _Resultado(alcanzadas[0] if alcanzadas else None)
        return _Resultado(list(alcanzadas))


class FakeSupabase:
    def __init__(self, store):
        self.store = store

    def table(self, nombre):
        return _Consulta(self.store, nombre)


# ── Datos ─────────────────────────────────────────────────────────────────────
# Dos administradores aprobados. Todo lo que termina en `-2` es del otro.

def _datos():
    return {
        'administradores': [
            {'id': 'admin-1', 'auth0_id': 'auth0|uno', 'estado': 'aprobado',
             'es_superadmin': False, 'email': 'uno@test', 'nombre': 'Uno',
             'ultima_actividad': '2999-01-01T00:00:00+00:00'},
            {'id': 'admin-2', 'auth0_id': 'auth0|dos', 'estado': 'aprobado',
             'es_superadmin': False, 'email': 'dos@test', 'nombre': 'Dos',
             'ultima_actividad': '2999-01-01T00:00:00+00:00'},
        ],
        'consorcios': [
            {'id': 'cons-1', 'admin_id': 'admin-1', 'nombre': 'Mío'},
            {'id': 'cons-2', 'admin_id': 'admin-2', 'nombre': 'Ajeno'},
        ],
        'unidades_funcionales': [
            {'id': 'uf-1', 'consorcio_id': 'cons-1', 'numero': '1A'},
            {'id': 'uf-2', 'consorcio_id': 'cons-2', 'numero': '2B'},
        ],
        'gastos': [
            {'id': 'gasto-1', 'admin_id': 'admin-1', 'consorcio_id': 'cons-1',
             'proveedor_id': 'prov-1', 'monto': 100, 'descripcion': 'Mío',
             'fecha_gasto': '2026-08-01'},
            {'id': 'gasto-2', 'admin_id': 'admin-2', 'consorcio_id': 'cons-2',
             'proveedor_id': 'prov-1', 'monto': 999, 'descripcion': 'Ajeno',
             'fecha_gasto': '2026-08-01'},
        ],
        'proveedores': [
            {'id': 'prov-1', 'admin_id': 'admin-1', 'nombre': 'Compartido'},
        ],
        'cobros': [
            {'id': 'cobro-1', 'consorcio_id': 'cons-1', 'unidad_id': 'uf-1',
             'estado': 'pendiente', 'total': 100, 'periodo': '2026-08',
             'fecha_pago': None},
            {'id': 'cobro-2', 'consorcio_id': 'cons-2', 'unidad_id': 'uf-2',
             'estado': 'pendiente', 'total': 999, 'periodo': '2026-08',
             'fecha_pago': None},
        ],
        'liquidaciones': [
            {'id': 'liq-1', 'admin_id': 'admin-1', 'consorcio_id': 'cons-1',
             'periodo': '2026-08', 'estado': 'borrador', 'numero_revision': 1},
            {'id': 'liq-2', 'admin_id': 'admin-2', 'consorcio_id': 'cons-2',
             'periodo': '2026-08', 'estado': 'borrador', 'numero_revision': 1},
        ],
        'liquidacion_prorrateo': [
            {'id': 'pro-1', 'liquidacion_id': 'liq-1', 'unidad_id': 'uf-1',
             'total_unidad': 100},
            {'id': 'pro-2', 'liquidacion_id': 'liq-2', 'unidad_id': 'uf-2',
             'total_unidad': 999},
        ],
        'liquidacion_rubros': [],
        'resumen_envios': [],
        'reclamos': [
            {'id': 'rec-1', 'consorcio_id': 'cons-1', 'estado': 'activo'},
            {'id': 'rec-2', 'consorcio_id': 'cons-2', 'estado': 'activo'},
        ],
        'avisos_pago': [
            {'id': 'aviso-1', 'consorcio_id': 'cons-1', 'estado': 'pendiente'},
            {'id': 'aviso-2', 'consorcio_id': 'cons-2', 'estado': 'pendiente'},
        ],
        'amenities': [
            {'id': 'amen-1', 'consorcio_id': 'cons-1', 'nombre': 'Quincho'},
            {'id': 'amen-2', 'consorcio_id': 'cons-2', 'nombre': 'SUM'},
        ],
        'reservas_amenities': [
            {'id': 'res-2', 'amenity_id': 'amen-2', 'vecino_id': 'vec-2'},
        ],
        'vecinos': [
            {'id': 'vec-2', 'consorcio_id': 'cons-2', 'unidad': 'Pendiente',
             'unidad_id': None},
        ],
        'comunicados': [],
        'votaciones': [],
        'medios_pago': [],
        'archivos_consorcio': [],
        'envio_programado': [
            {'id': 'env-2', 'consorcio_id': 'cons-2', 'dia_mes': 5},
        ],
        'comprobantes_gastos': [],
        'superadmin_auditoria': [],
    }


@pytest.fixture
def base(monkeypatch):
    store = _datos()
    monkeypatch.setattr(app_mod, 'supabase', FakeSupabase(store))
    return store


@pytest.fixture
def client(base):
    app_mod.app.config['TESTING'] = True
    with app_mod.app.test_client() as c:
        with c.session_transaction() as s:
            s['user'] = {'sub': 'auth0|uno', 'email': 'uno@test',
                         'name': 'Uno', 'role': 'admin'}
        yield c


def filas(store, tabla, **igual):
    return [f for f in store[tabla] if all(f.get(k) == v for k, v in igual.items())]


def una(store, tabla, fid):
    return next(f for f in store[tabla] if f['id'] == fid)


# ── Lecturas ajenas ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('url', [
    '/api/consorcios/cons-2/unidades',
    '/api/consorcios/cons-2/export/excel',
    '/api/consorcios/cons-2/export/pdf',
    '/api/consorcios/cons-2/amenities',
    '/api/consorcios/cons-2/vecinos/pendientes',
    '/api/cobros?consorcio_id=cons-2',
    '/api/liquidaciones/liq-2/rubros',
    '/api/liquidaciones/liq-2/prorrateo',
    '/api/liquidaciones/liq-2/envios',
    '/api/liquidaciones/liq-2/resumen/uf-2',
    '/api/envio-programado/cons-2',
    '/api/admin/reclamos?consorcio_id=cons-2',
    '/api/admin/avisos-pago?consorcio_id=cons-2',
    '/api/liquidaciones/gastos-disponibles?consorcio_id=cons-2&periodo=2026-08',
])
def test_leer_lo_ajeno_da_404(client, url):
    assert client.get(url).status_code == 404


def test_el_listado_de_cobros_sin_filtro_no_trae_los_ajenos(client):
    cobros = client.get('/api/cobros').get_json()
    assert [c['id'] for c in cobros] == ['cobro-1']


def test_el_balance_no_suma_los_cobros_ajenos(client, base):
    una(base, 'cobros', 'cobro-1')['estado'] = 'pagado'
    una(base, 'cobros', 'cobro-2')['estado'] = 'pagado'
    balance = client.get('/api/balance').get_json()
    assert balance['ingresos'] == 100


def test_el_historial_del_proveedor_no_mezcla_administradores(client):
    """El mismo proveedor puede estar cargado por varios administradores."""
    gastos = client.get('/api/proveedores/prov-1/gastos').get_json()
    assert [g['id'] for g in gastos] == ['gasto-1']


# ── Escrituras ajenas ─────────────────────────────────────────────────────────

def test_no_se_puede_editar_un_cobro_ajeno(client, base):
    r = client.put('/api/cobros/cobro-2', json={'estado': 'pagado', 'total': 0})
    assert r.status_code == 404
    assert una(base, 'cobros', 'cobro-2')['estado'] == 'pendiente'
    assert una(base, 'cobros', 'cobro-2')['total'] == 999


def test_no_se_puede_responder_un_reclamo_ajeno(client, base):
    r = client.put('/api/admin/reclamos/rec-2',
                   json={'estado': 'cerrado', 'respuesta_admin': 'listo'})
    assert r.status_code == 404
    assert una(base, 'reclamos', 'rec-2')['estado'] == 'activo'


def test_no_se_puede_aprobar_un_aviso_de_pago_ajeno(client, base):
    r = client.put('/api/admin/avisos-pago/aviso-2', json={'estado': 'aprobado'})
    assert r.status_code == 404
    assert una(base, 'avisos_pago', 'aviso-2')['estado'] == 'pendiente'


def test_no_se_puede_editar_el_prorrateo_de_una_liquidacion_ajena(client, base):
    r = client.put('/api/liquidaciones/liq-2/prorrateo/pro-2',
                   json={'total_unidad': 0})
    assert r.status_code == 404
    assert una(base, 'liquidacion_prorrateo', 'pro-2')['total_unidad'] == 999


def test_la_liquidacion_propia_no_habilita_un_prorrateo_ajeno(client, base):
    """El `lid` de la URL es propio y el `pid` no: el chequeo del padre pasa."""
    r = client.put('/api/liquidaciones/liq-1/prorrateo/pro-2',
                   json={'total_unidad': 0})
    assert una(base, 'liquidacion_prorrateo', 'pro-2')['total_unidad'] == 999
    assert r.get_json() == {}


def test_no_se_pueden_mandar_los_resumenes_de_una_liquidacion_ajena(client, base):
    r = client.post('/api/liquidaciones/liq-2/enviar', json={})
    assert r.status_code == 404
    assert base['resumen_envios'] == []


def test_no_se_pueden_borrar_unidades_ajenas(client, base):
    r = client.delete('/api/consorcios/cons-2/unidades/uf-2')
    assert r.status_code == 404
    assert filas(base, 'unidades_funcionales', id='uf-2')


def test_no_se_pueden_editar_unidades_ajenas(client, base):
    r = client.put('/api/consorcios/cons-2/unidades/uf-2', json={'numero': 'X'})
    assert r.status_code == 404
    assert una(base, 'unidades_funcionales', 'uf-2')['numero'] == '2B'


def test_no_se_pueden_crear_unidades_en_un_consorcio_ajeno(client, base):
    r = client.post('/api/consorcios/cons-2/unidades', json={'numero': '9Z'})
    assert r.status_code == 404
    assert not filas(base, 'unidades_funcionales', numero='9Z')


def test_no_se_pueden_generar_cobros_en_un_consorcio_ajeno(client, base):
    r = client.post('/api/cobros/generar',
                    json={'consorcio_id': 'cons-2', 'periodo': '2026-09',
                          'monto_base': 1})
    assert r.status_code == 404
    assert not filas(base, 'cobros', periodo='2026-09')


def test_no_se_puede_publicar_un_comunicado_en_una_cartelera_ajena(client, base):
    r = client.post('/api/admin/comunicados',
                    json={'consorcio_id': 'cons-2', 'titulo': 'Hola',
                          'cuerpo': 'Texto'})
    assert r.status_code == 404
    assert base['comunicados'] == []


def test_no_se_puede_cargar_un_medio_de_pago_en_un_consorcio_ajeno(client, base):
    """Sería redirigir la cobranza del edificio a otra cuenta."""
    r = client.post('/api/admin/medios-pago',
                    json={'consorcio_id': 'cons-2', 'nombre': 'Mi CBU'})
    assert r.status_code == 404
    assert base['medios_pago'] == []


def test_no_se_puede_abrir_una_votacion_en_un_consorcio_ajeno(client, base):
    r = client.post('/api/admin/votaciones',
                    json={'consorcio_id': 'cons-2', 'titulo': 'Cambio de admin'})
    assert r.status_code == 404
    assert base['votaciones'] == []


def test_no_se_puede_crear_un_amenity_ajeno(client, base):
    r = client.post('/api/consorcios/cons-2/amenities', json={'nombre': 'Pileta'})
    assert r.status_code == 404
    assert not filas(base, 'amenities', nombre='Pileta')


def test_no_se_puede_borrar_un_amenity_ajeno(client, base):
    r = client.delete('/api/consorcios/cons-2/amenities/amen-2')
    assert r.status_code == 404
    assert filas(base, 'amenities', id='amen-2')


def test_no_se_puede_cancelar_una_reserva_ajena(client, base):
    r = client.delete('/api/reservas_amenities/res-2')
    assert r.status_code == 404
    assert filas(base, 'reservas_amenities', id='res-2')


def test_no_se_pueden_ver_las_reservas_de_un_amenity_ajeno(client):
    """Traen nombre y unidad de cada vecino que reservó."""
    assert client.get('/api/reservas_amenities?amenity_id=amen-2').status_code == 404


def test_el_listado_de_reservas_sin_filtro_no_sale_de_los_consorcios_propios(client):
    reservas = client.get('/api/reservas_amenities').get_json()
    assert reservas == []


def test_no_se_puede_reservar_un_amenity_ajeno(client, base):
    r = client.post('/api/reservas_amenities',
                    json={'amenity_id': 'amen-2', 'fecha': '2026-09-01',
                          'hora_inicio': '10:00', 'hora_fin': '12:00'})
    assert r.status_code == 404
    assert len(base['reservas_amenities']) == 1


def test_no_se_puede_asignar_una_unidad_en_un_consorcio_ajeno(client, base):
    r = client.post('/api/consorcios/cons-2/vecinos/vec-2/asignar-unidad',
                    json={'unidad_id': 'uf-2'})
    assert r.status_code == 404
    assert una(base, 'vecinos', 'vec-2')['unidad'] == 'Pendiente'


def test_no_se_puede_programar_el_envio_de_un_consorcio_ajeno(client, base):
    r = client.post('/api/envio-programado/cons-2', json={'dia_mes': 28})
    assert r.status_code == 404
    assert una(base, 'envio_programado', 'env-2')['dia_mes'] == 5


def test_no_se_puede_cargar_un_gasto_en_un_consorcio_ajeno(client, base):
    r = client.post('/api/gastos', json={'consorcio_id': 'cons-2',
                                         'descripcion': 'Inventado', 'monto': 1})
    assert r.status_code == 404
    assert not filas(base, 'gastos', descripcion='Inventado')


def test_no_se_puede_mudar_un_gasto_propio_a_un_consorcio_ajeno(client, base):
    """El gasto es suyo, pero el destino no: aparecería en la pantalla de los
    vecinos del otro edificio, que filtra por consorcio y no por admin."""
    r = client.put('/api/gastos/gasto-1', json={'consorcio_id': 'cons-2'})
    assert r.status_code == 404
    assert una(base, 'gastos', 'gasto-1')['consorcio_id'] == 'cons-1'


def test_no_se_puede_crear_una_liquidacion_de_un_consorcio_ajeno(client, base):
    r = client.post('/api/liquidaciones',
                    json={'consorcio_id': 'cons-2', 'periodo': '2026-09',
                          'auto_generar': False})
    assert r.status_code == 404
    assert not filas(base, 'liquidaciones', periodo='2026-09')


# ── Lo propio sigue andando ───────────────────────────────────────────────────
# Un `abort(404)` de más pasa todos los tests de arriba y deja la aplicación
# inutilizable. Estos son los que lo detectan.

def test_el_dueno_lista_sus_unidades(client):
    r = client.get('/api/consorcios/cons-1/unidades')
    assert r.status_code == 200
    assert [u['id'] for u in r.get_json()] == ['uf-1']


def test_el_dueno_edita_su_cobro(client, base):
    r = client.put('/api/cobros/cobro-1', json={'estado': 'pagado'})
    assert r.status_code == 200
    assert una(base, 'cobros', 'cobro-1')['estado'] == 'pagado'


def test_el_dueno_edita_el_prorrateo_de_su_liquidacion(client, base):
    r = client.put('/api/liquidaciones/liq-1/prorrateo/pro-1',
                   json={'total_unidad': 250})
    assert r.status_code == 200
    assert una(base, 'liquidacion_prorrateo', 'pro-1')['total_unidad'] == 250


def test_el_dueno_carga_un_gasto_en_su_consorcio(client, base):
    r = client.post('/api/gastos', json={'consorcio_id': 'cons-1',
                                         'descripcion': 'Ascensor', 'monto': 50})
    assert r.status_code == 201
    assert filas(base, 'gastos', descripcion='Ascensor')


def test_el_dueno_publica_un_comunicado_en_su_cartelera(client, base):
    r = client.post('/api/admin/comunicados',
                    json={'consorcio_id': 'cons-1', 'titulo': 'Corte de agua',
                          'cuerpo': 'Mañana de 9 a 12'})
    assert r.status_code == 201
    assert len(base['comunicados']) == 1


def test_el_dueno_programa_el_envio_de_su_consorcio(client, base):
    r = client.post('/api/envio-programado/cons-1', json={'dia_mes': 3})
    assert r.status_code == 200
    assert filas(base, 'envio_programado', consorcio_id='cons-1')


def test_el_dueno_lista_las_unidades_de_su_consorcio_en_el_excel(client):
    assert client.get('/api/consorcios/cons-1/export/excel').status_code == 200
