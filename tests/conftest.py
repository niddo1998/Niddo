"""Doble de Supabase y arranque del entorno para los tests del portal del vecino.

`app.py` lee las variables de entorno al importarse y habla con Supabase en cada
request, así que sin estas dos cosas no hay test posible: ni siquiera el import.

El doble es deliberadamente tonto —listas de diccionarios y lambdas de filtro—
porque lo que se prueba acá no es Supabase sino qué preguntas le hace la app.
Un `.eq()` que falta se ve como una fila de más en el resultado.
"""

import os

import pytest

os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'test')
os.environ.setdefault('AUTH0_DOMAIN', 'test.auth0.com')
os.environ.setdefault('AUTH0_CLIENT_ID', 'test')
os.environ.setdefault('AUTH0_CLIENT_SECRET', 'test')
# Sin esto la cookie de sesión sale marcada Secure y el cliente de test, que
# habla http, no la manda: todas las requests darían 302 al login.
os.environ['NIDDO_LOCAL'] = '1'

import app as app_mod  # noqa: E402


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

    def neq(self, campo, valor):
        self.filtros.append(lambda f: f.get(campo) != valor)
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
# Dos vecinos en dos edificios distintos. Todo lo que termina en `-2` es del
# otro, y es lo que ninguna request de `vec-1` debería alcanzar.

def _datos():
    return {
        'vecinos': [
            {'id': 'vec-1', 'auth0_id': 'auth0|uno', 'consorcio_id': 'cons-1',
             'unidad_id': 'uf-1', 'unidad': '1A', 'nombre': 'Uno',
             'email': 'uno@test', 'telefono': '', 'rol': 'propietario'},
            {'id': 'vec-2', 'auth0_id': 'auth0|dos', 'consorcio_id': 'cons-2',
             'unidad_id': 'uf-2', 'unidad': '2B', 'nombre': 'Dos',
             'email': 'dos@test', 'telefono': '', 'rol': 'propietario'},
        ],
        'consorcios': [
            {'id': 'cons-1', 'admin_id': 'admin-1', 'nombre': 'Mío'},
            {'id': 'cons-2', 'admin_id': 'admin-2', 'nombre': 'Ajeno'},
        ],
        'unidades_funcionales': [
            {'id': 'uf-1', 'consorcio_id': 'cons-1', 'numero': '1A'},
            {'id': 'uf-2', 'consorcio_id': 'cons-2', 'numero': '2B'},
        ],
        'administradores': [
            {'id': 'admin-1', 'auth0_id': 'auth0|admin', 'estado': 'aprobado',
             'es_superadmin': False, 'email': 'admin@test', 'nombre': 'Admin',
             'ultima_actividad': '2999-01-01T00:00:00+00:00'},
        ],
        'amenities': [
            {'id': 'amen-1', 'consorcio_id': 'cons-1', 'nombre': 'SUM',
             'capacidad_maxima': None},
            {'id': 'amen-2', 'consorcio_id': 'cons-2', 'nombre': 'Quincho ajeno',
             'capacidad_maxima': None},
        ],
        'reservas_amenities': [],
        'votaciones': [
            {'id': 'vot-1', 'consorcio_id': 'cons-1', 'titulo': 'Mía',
             'estado': 'activa', 'opciones': ['Si', 'No'], 'fecha_limite': None},
            {'id': 'vot-2', 'consorcio_id': 'cons-2', 'titulo': 'Ajena',
             'estado': 'activa', 'opciones': ['Si', 'No'], 'fecha_limite': None},
        ],
        'votos': [],
        'cobros': [
            {'id': 'cobro-1', 'consorcio_id': 'cons-1', 'unidad_id': 'uf-1',
             'estado': 'pendiente', 'total': 100, 'monto_base': 100,
             'interes_mora': 0, 'periodo': '2026-08',
             'fecha_vencimiento': '2026-08-10'},
        ],
        'avisos_pago': [],
    }


@pytest.fixture
def base(monkeypatch):
    store = _datos()
    monkeypatch.setattr(app_mod, 'supabase', FakeSupabase(store))
    return store


@pytest.fixture
def client(base):
    """Sesión de `vec-1`, el vecino cuyos datos son los `-1`."""
    app_mod.app.config['TESTING'] = True
    c = app_mod.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|uno', 'email': 'uno@test', 'name': 'Uno',
                     'role': 'vecino'}
    return c


@pytest.fixture
def app_modulo():
    return app_mod
