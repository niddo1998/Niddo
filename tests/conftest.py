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
        self.columnas = '*'
        self.on_conflict = None

    def select(self, columnas='*', *_a, **_k):
        """Guarda qué columnas se pidieron para poder proyectarlas al ejecutar.

        Sin esto el doble devolvía la fila entera pasara lo que pasara, y un
        `select('*')` de más —el que se traía el adjunto en base64 en cada fila
        del listado— era indistinguible de uno acotado.
        """
        self.columnas = columnas
        return self

    @staticmethod
    def _campos(columnas):
        """Los nombres de primer nivel de un select de PostgREST.

        `vecinos(nombre, email)` cuenta como el campo `vecinos`: lo que interesa
        es qué claves quedan en la fila, no cómo se resuelve el embebido.
        """
        campos, actual, profundidad = [], '', 0
        for ch in columnas:
            if ch == '(':
                profundidad += 1
            elif ch == ')':
                profundidad -= 1
            elif ch == ',' and profundidad == 0:
                campos.append(actual)
                actual = ''
                continue
            if profundidad == 0 and ch not in '()':
                actual += ch
        campos.append(actual)
        return [c.strip().split('(')[0].strip() for c in campos if c.strip()]

    def _proyectar(self, fila):
        if not isinstance(fila, dict) or '*' in (self.columnas or '*'):
            return fila
        campos = self._campos(self.columnas)
        return {k: v for k, v in fila.items() if k in campos}

    def insert(self, payload):
        self.op, self.payload = 'insert', payload
        return self

    def upsert(self, payload, on_conflict=None, **_k):
        """upsert de PostgREST, respetando `on_conflict`.

        Tratarlo como un insert a secas hacía que el segundo login de la misma
        persona creara una fila nueva en vez de refrescar la suya, y eso esconde
        justo los bugs del camino de alta, que es donde el mismo usuario vuelve
        a pasar por el mismo código.
        """
        self.op, self.payload = 'upsert', payload
        self.on_conflict = on_conflict
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

    def is_(self, campo, valor):
        """`is_(campo, 'null')` de PostgREST: la fila no tiene ese valor.

        Se cuenta como nulo tanto la clave ausente como la explícitamente en
        None, porque el doble guarda diccionarios y una fila que nunca escribió
        la columna es lo mismo que una que la tiene vacía.
        """
        if valor in ('null', 'NULL', None):
            self.filtros.append(lambda f: f.get(campo) is None)
        else:
            self.filtros.append(lambda f: f.get(campo) is valor)
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
        if self.op == 'upsert':
            nuevas = self.payload if isinstance(self.payload, list) else [self.payload]
            resultado = []
            for fila in nuevas:
                existente = None
                if self.on_conflict:
                    clave = fila.get(self.on_conflict)
                    existente = next((f for f in self.filas
                                      if f.get(self.on_conflict) == clave), None)
                if existente is not None:
                    existente.update(fila)
                    resultado.append(existente)
                else:
                    fila = dict(fila)
                    fila.setdefault('id', f'{self.tabla}-nuevo-{len(self.filas)}')
                    self.filas.append(fila)
                    resultado.append(fila)
            return _Resultado(resultado)

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
            return _Resultado(self._proyectar(alcanzadas[0]) if alcanzadas else None)
        return _Resultado([self._proyectar(f) for f in alcanzadas])


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
        # `consorcios` va embebido a mano: el doble no resuelve los joins de
        # PostgREST, así que se guarda la fila como la devolvería el select
        # `amenities(..., consorcios(nombre))` que hace la app.
        'amenities': [
            {'id': 'amen-1', 'consorcio_id': 'cons-1', 'nombre': 'SUM',
             'capacidad_maxima': None, 'condiciones_uso': '',
             'consorcios': {'nombre': 'Mío'}},
            {'id': 'amen-2', 'consorcio_id': 'cons-2', 'nombre': 'Quincho ajeno',
             'capacidad_maxima': None, 'condiciones_uso': '',
             'consorcios': {'nombre': 'Ajeno'}},
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
