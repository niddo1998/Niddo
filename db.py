"""Acceso a la base: Postgres directo (Neon) con la misma interfaz que supabase-py.

Niddo nació hablando con Supabase por su API REST (PostgREST), y `app.py` tiene
más de 300 consultas escritas como

    supabase.table('cobros').select('*, consorcios(nombre)').eq('id', x).execute().data

Este módulo implementa ese mismo idioma —`table()`, `select()`, los filtros,
`order()`, `limit()`, `single()`, `insert/update/upsert/delete` y `execute()`—
pero lo traduce a SQL y lo corre contra Postgres con psycopg. Con eso la
migración a Neon no toca ninguna de esas consultas.

Lo que se cuida para que la app no note la diferencia:

- **El JSON lo arma Postgres** (`json_agg` / `row_to_json`), igual que hace
  PostgREST. Las fechas vuelven como texto ISO y los numeric como número, con
  el mismo formato que antes; no hay Decimal ni datetime de Python dando vueltas.
- **Los embebidos** (`'*, consorcios(nombre)'`) se resuelven por las claves
  foráneas del catálogo: hacia un padre devuelven un objeto (o null), hacia
  hijos una lista, como PostgREST.
- **Los errores** traen el texto y el código de Postgres (`23505: duplicate
  key...`), porque la app los reconoce por esos textos.
- **`single()`** con cero o varias filas levanta `APIError`, como supabase-py.
- **Escrituras** devuelven las filas afectadas, como el `return=representation`
  que supabase-py manda por defecto.

Los nombres de tablas y columnas nunca van pegados al SQL sin pasar por
`sql.Identifier`, y los valores siempre van como parámetros.
"""

import json
import re
import threading
from typing import Optional

import psycopg
from psycopg import sql


class APIError(Exception):
    """Error de la base, con el mismo espíritu que el de postgrest-py.

    `str(e)` lleva el código SQLSTATE adelante del mensaje: la app distingue
    algunos errores buscando '23505' o 'duplicate key' en el texto, y así
    siguen apareciendo los dos.
    """

    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(f'{code}: {message}' if code else message)


class Respuesta:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


# ── Esquema ───────────────────────────────────────────────────────────────────

class _Esquema:
    """Columnas, tipos y claves foráneas del schema public, leídos una vez."""

    def __init__(self, filas_columnas, filas_fks):
        self.tipos = {}  # {tabla: {columna: tipo}}
        for tabla, columna, tipo in filas_columnas:
            self.tipos.setdefault(tabla, {})[columna] = tipo
        # [(tabla, [columnas], tabla_referida, [columnas_referidas], nombre)]
        self.fks = filas_fks

    def tipo(self, tabla, columna):
        return self.tipos.get(tabla, {}).get(columna)

    def relacion(self, base, nombre, pista=None):
        """Cómo se llega de `base` a lo que nombra el embebido.

        Devuelve ('padre'|'hijos', cols_base, cols_otra, tabla_otra). `nombre`
        puede ser, como en PostgREST:

        - una tabla: `consorcios(nombre)`; si hay más de un camino hacia ella,
          `pista` (lo que va después del `!`) dice cuál: la columna o la FK.
        - la columna con la FK, o el nombre de la constraint:
          `actor:actor_id(nombre)` trae la fila de `administradores` a la que
          apunta `actor_id`.
        """
        def coincide(fk, columnas_propias, valor):
            return valor == fk[4] or list(columnas_propias) == [valor]

        if nombre in self.tipos:
            candidatas = (
                [('padre', f[1], f[3], f[2], f) for f in self.fks if f[0] == base and f[2] == nombre]
                + [('hijos', f[3], f[1], f[0], f) for f in self.fks if f[0] == nombre and f[2] == base])
            if pista:
                candidatas = [c for c in candidatas
                              if coincide(c[4], c[4][1], pista)]
        else:
            candidatas = [('padre', f[1], f[3], f[2], f) for f in self.fks
                          if f[0] == base and coincide(f, f[1], nombre)]
        if not candidatas:
            raise APIError(
                f"No hay relación entre '{base}' y '{nombre}' en el esquema",
                code='PGRST200')
        if len(candidatas) > 1:
            raise APIError(
                f"Hay más de una relación entre '{base}' y '{nombre}': "
                f"usá {nombre}!columna(...) para elegir una",
                code='PGRST201')
        return candidatas[0][:4]


_SQL_COLUMNAS = """
    select c.table_name, c.column_name, format_type(a.atttypid, a.atttypmod)
    from information_schema.columns c
    join pg_attribute a on a.attrelid = format('public.%I', c.table_name)::regclass
                       and a.attname = c.column_name
    where c.table_schema = 'public'
"""

_SQL_FKS = """
    select cl.relname,
           array(select attname from unnest(co.conkey) with ordinality k(n, i)
                 join pg_attribute on attrelid = co.conrelid and attnum = k.n order by k.i),
           ref.relname,
           array(select attname from unnest(co.confkey) with ordinality k(n, i)
                 join pg_attribute on attrelid = co.confrelid and attnum = k.n order by k.i),
           co.conname
    from pg_constraint co
    join pg_class cl on cl.oid = co.conrelid
    join pg_class ref on ref.oid = co.confrelid
    where co.contype = 'f' and co.connamespace = 'public'::regnamespace
"""


# ── Parseo del select y del or_ de PostgREST ──────────────────────────────────

def _partir_nivel_cero(texto):
    """Separa por comas que no estén dentro de paréntesis."""
    partes, actual, profundidad = [], '', 0
    for ch in texto:
        if ch == '(':
            profundidad += 1
        elif ch == ')':
            profundidad -= 1
        if ch == ',' and profundidad == 0:
            partes.append(actual)
            actual = ''
        else:
            actual += ch
    partes.append(actual)
    return [p.strip() for p in partes if p.strip()]


# [alias:]relación[!pista](columnas)
_EMBEBIDO = re.compile(r'^(?:(\w+)\s*:\s*)?(\w+)(?:!(\w+))?\s*\((.*)\)$', re.S)


def _parsear_select(columnas):
    """'*, actor:actor_id(nombre)' → (['*'], [('actor', 'actor_id', None, 'nombre')]).

    Cada embebido es (clave en el resultado, relación, pista, columnas).
    """
    simples, embebidos = [], []
    for parte in _partir_nivel_cero(columnas or '*'):
        m = _EMBEBIDO.match(parte)
        if m:
            alias, nombre, pista, cols = m.groups()
            embebidos.append((alias or nombre, nombre, pista, cols))
        else:
            simples.append(parte)
    return simples, embebidos


_OPERADORES = {
    'eq': '=', 'neq': '<>', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<=',
    'like': 'LIKE', 'ilike': 'ILIKE',
}


# ── Constructor de consultas ──────────────────────────────────────────────────

class Consulta:
    def __init__(self, cliente, tabla):
        self._cliente = cliente
        self._tabla = tabla
        self._op = 'select'
        self._columnas = '*'
        self._payload = None
        self._on_conflict = None
        self._filtros = []      # [(sql.Composable, [params])]
        self._orden = []        # [(columna, desc)]
        self._limite = None
        self._una = False
        self._negar = False

    # Operaciones
    def select(self, columnas='*', *_, **__):
        self._columnas = columnas
        return self

    def insert(self, payload, *_, **__):
        self._op, self._payload = 'insert', payload
        return self

    def upsert(self, payload, on_conflict=None, *_, **__):
        self._op, self._payload, self._on_conflict = 'upsert', payload, on_conflict
        return self

    def update(self, payload, *_, **__):
        self._op, self._payload = 'update', payload
        return self

    def delete(self, *_, **__):
        self._op = 'delete'
        return self

    # Filtros
    @property
    def not_(self):
        """`.not_.is_(...)`: niega el filtro que viene."""
        self._negar = True
        return self

    def _agregar(self, condicion, params):
        if self._negar:
            condicion = sql.SQL('NOT ({})').format(condicion)
            self._negar = False
        self._filtros.append((condicion, params))
        return self

    def _col(self, columna):
        return sql.Identifier(self._tabla, columna)

    def _comparar(self, columna, operador, valor):
        if operador in ('LIKE', 'ILIKE'):
            # PostgREST acepta * como comodín además de %.
            valor = str(valor).replace('*', '%')
            return self._agregar(
                sql.SQL('{}::text {} %s').format(self._col(columna), sql.SQL(operador)),
                [valor])
        return self._agregar(
            sql.SQL('{} {} {}').format(self._col(columna), sql.SQL(operador),
                                       self._cliente._param(self._tabla, columna)),
            [_valor_sql(valor)])

    def eq(self, columna, valor):
        return self._comparar(columna, '=', valor)

    def neq(self, columna, valor):
        return self._comparar(columna, '<>', valor)

    def gt(self, columna, valor):
        return self._comparar(columna, '>', valor)

    def gte(self, columna, valor):
        return self._comparar(columna, '>=', valor)

    def lt(self, columna, valor):
        return self._comparar(columna, '<', valor)

    def lte(self, columna, valor):
        return self._comparar(columna, '<=', valor)

    def like(self, columna, patron):
        return self._comparar(columna, 'LIKE', patron)

    def ilike(self, columna, patron):
        return self._comparar(columna, 'ILIKE', patron)

    def is_(self, columna, valor):
        palabra = {'null': 'NULL', 'true': 'TRUE', 'false': 'FALSE'}.get(
            str(valor).lower() if valor is not None else 'null')
        if palabra is None:
            raise APIError(f'is_ no acepta {valor!r}', code='PGRST100')
        return self._agregar(
            sql.SQL('{} IS {}').format(self._col(columna), sql.SQL(palabra)), [])

    def in_(self, columna, valores):
        valores = [_valor_sql(v) for v in valores]
        if not valores:
            # PostgREST con in.() no trae nada; un ANY de array vacío tampoco.
            return self._agregar(sql.SQL('FALSE'), [])
        return self._agregar(
            sql.SQL('{} = ANY({})').format(
                self._col(columna), self._cliente._param(self._tabla, columna, arreglo=True)),
            [valores])

    def match(self, criterios: dict):
        for columna, valor in criterios.items():
            self.eq(columna, valor)
        return self

    def or_(self, filtros: str, *_, **__):
        """El `or` de PostgREST en su forma simple: 'a.eq.1,b.ilike.%x%'."""
        condiciones, params = [], []
        for parte in _partir_nivel_cero(filtros):
            columna, _, resto = parte.partition('.')
            operador, _, valor = resto.partition('.')
            if operador == 'is':
                sub = Consulta(self._cliente, self._tabla).is_(columna, valor)
            elif operador in _OPERADORES:
                sub = Consulta(self._cliente, self._tabla)._comparar(
                    columna, _OPERADORES[operador], valor)
            else:
                raise APIError(f'Operador no soportado en or_: {operador}', code='PGRST100')
            condicion, p = sub._filtros[0]
            condiciones.append(condicion)
            params.extend(p)
        return self._agregar(
            sql.SQL('({})').format(sql.SQL(' OR ').join(condiciones)), params)

    # Forma del resultado
    def order(self, columna, desc=False, *_, **__):
        self._orden.append((columna, desc))
        return self

    def limit(self, n, *_, **__):
        self._limite = int(n)
        return self

    def single(self):
        self._una = True
        return self

    # Ejecución
    def execute(self):
        consulta, params = self._armar()
        filas = self._cliente._correr(consulta, params)
        if self._una:
            if len(filas) != 1:
                raise APIError(
                    'JSON object requested, multiple (or no) rows returned',
                    code='PGRST116',
                    details=f'The result contains {len(filas)} rows')
            return Respuesta(filas[0])
        return Respuesta(filas)

    # Armado del SQL
    def _where(self):
        if not self._filtros:
            return sql.SQL(''), []
        params = [p for _, ps in self._filtros for p in ps]
        return (sql.SQL(' WHERE ') + sql.SQL(' AND ').join(c for c, _ in self._filtros),
                params)

    def _lista_select(self, tabla, alias, columnas):
        """La lista de columnas de un SELECT, con los embebidos como subconsultas."""
        esquema = self._cliente._esquema()
        simples, embebidos = _parsear_select(columnas)
        partes = []
        for c in simples:
            if c == '*':
                partes.append(sql.SQL('{}.*').format(sql.Identifier(alias)))
            else:
                partes.append(sql.Identifier(alias, c))
        for i, (clave, nombre, pista, sub_columnas) in enumerate(embebidos):
            tipo, cols_base, cols_otra, otra = esquema.relacion(tabla, nombre, pista)
            alias_otra = f'{alias}_{i}'
            union = sql.SQL(' AND ').join(
                sql.SQL('{} = {}').format(sql.Identifier(alias_otra, co), sql.Identifier(alias, cb))
                for cb, co in zip(cols_base, cols_otra))
            interior = sql.SQL('SELECT {} FROM {} {} WHERE {}').format(
                self._lista_select(otra, alias_otra, sub_columnas),
                sql.Identifier('public', otra), sql.Identifier(alias_otra), union)
            if tipo == 'padre':
                sub = sql.SQL('(SELECT row_to_json(_e) FROM ({}) _e)').format(interior)
            else:
                sub = sql.SQL("(SELECT coalesce(json_agg(_e), '[]'::json) FROM ({}) _e)").format(interior)
            partes.append(sql.SQL('{} AS {}').format(sub, sql.Identifier(clave)))
        return sql.SQL(', ').join(partes)

    def _order_by(self):
        if not self._orden:
            return sql.SQL('')
        esquema = self._cliente._esquema()
        partes = []
        for columna, desc in self._orden:
            m = _EMBEBIDO.match(columna)
            if m:
                # order('unidades_funcionales(numero)'): ordena por la columna del padre.
                _, nombre, pista, col_otra = m.groups()
                _, cols_base, cols_otra, otra = esquema.relacion(self._tabla, nombre, pista)
                col_otra = col_otra.strip()
                union = sql.SQL(' AND ').join(
                    sql.SQL('_o.{} = {}').format(sql.Identifier(co), self._col(cb))
                    for cb, co in zip(cols_base, cols_otra))
                expr = sql.SQL('(SELECT _o.{} FROM {} _o WHERE {})').format(
                    sql.Identifier(col_otra), sql.Identifier('public', otra), union)
            else:
                expr = self._col(columna)
            partes.append(expr + sql.SQL(' DESC' if desc else ' ASC'))
        return sql.SQL(' ORDER BY ') + sql.SQL(', ').join(partes)

    def _armar(self):
        tabla = sql.Identifier('public', self._tabla)
        alias = sql.Identifier(self._tabla)
        where, params = self._where()

        if self._op == 'select':
            limite = sql.SQL(' LIMIT {}').format(sql.Literal(self._limite)) \
                if self._limite is not None else sql.SQL('')
            interior = sql.SQL('SELECT {} FROM {} AS {}{}{}{}').format(
                self._lista_select(self._tabla, self._tabla, self._columnas),
                tabla, alias, where, self._order_by(), limite)
            return (sql.SQL("SELECT coalesce(json_agg(_r), '[]'::json) FROM ({}) _r")
                    .format(interior), params)

        if self._op == 'delete':
            if not self._filtros:
                raise APIError('DELETE sin filtros: se rechaza para no vaciar la tabla',
                               code='21000')
            escritura = sql.SQL('DELETE FROM {} AS {}{} RETURNING {}.*').format(
                tabla, alias, where, alias)
            return _envolver(escritura), params

        if self._op == 'update':
            if not self._filtros:
                raise APIError('UPDATE sin filtros: se rechaza para no pisar la tabla',
                               code='21000')
            datos = dict(self._payload or {})
            if not datos:
                raise APIError('UPDATE sin columnas', code='PGRST100')
            sets = sql.SQL(', ').join(
                sql.SQL('{} = _v.{}').format(sql.Identifier(c), sql.Identifier(c))
                for c in datos)
            escritura = sql.SQL(
                'UPDATE {} AS {} SET {} FROM json_populate_record(null::{}, %s::json) AS _v{} '
                'RETURNING {}.*').format(tabla, alias, sets, tabla, where, alias)
            return _envolver(escritura), [_json(datos)] + params

        # insert / upsert
        filas = self._payload if isinstance(self._payload, list) else [self._payload]
        filas = [dict(f) for f in filas if f is not None]
        if not filas:
            return sql.SQL("SELECT '[]'::json"), []
        # Las columnas son la unión de las claves: a la fila que no trae una le
        # queda NULL, como en el insert de varias filas de PostgREST.
        columnas = []
        for f in filas:
            for c in f:
                if c not in columnas:
                    columnas.append(c)
        ids = sql.SQL(', ').join(sql.Identifier(c) for c in columnas)
        escritura = sql.SQL(
            'INSERT INTO {} AS {} ({}) SELECT {} FROM json_populate_recordset(null::{}, %s::json)'
        ).format(tabla, alias, ids, ids, tabla)
        if self._op == 'upsert':
            conflicto = [c.strip() for c in (self._on_conflict or '').split(',') if c.strip()] \
                or self._cliente._clave_primaria(self._tabla)
            actualizar = [c for c in columnas if c not in conflicto] or conflicto[:1]
            escritura += sql.SQL(' ON CONFLICT ({}) DO UPDATE SET {}').format(
                sql.SQL(', ').join(sql.Identifier(c) for c in conflicto),
                sql.SQL(', ').join(
                    sql.SQL('{} = EXCLUDED.{}').format(sql.Identifier(c), sql.Identifier(c))
                    for c in actualizar))
        escritura += sql.SQL(' RETURNING {}.*').format(alias)
        return _envolver(escritura), [_json(filas)]


def _envolver(escritura):
    """Devuelve las filas escritas como JSON, igual que un select."""
    return sql.SQL("WITH _w AS ({}) SELECT coalesce(json_agg(_w), '[]'::json) FROM _w") \
        .format(escritura)


def _json(valor):
    return json.dumps(valor, default=str)


def _valor_sql(valor):
    """Los valores de filtro como los mandaría PostgREST: texto, salvo None."""
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor
    return str(valor)


# ── Cliente ───────────────────────────────────────────────────────────────────

class Cliente:
    """Una conexión por proceso, perezosa y que se reabre si se cae.

    En Vercel cada instancia atiende un request a la vez y vive unos minutos,
    así que una conexión reutilizada alcanza. Neon apaga la base cuando no se
    usa y eso corta las conexiones abiertas: la siguiente consulta lo nota,
    reconecta y reintenta una vez.
    """

    def __init__(self, url):
        self._url = url
        self._conexion = None
        self._esquema_cache = None
        self._lock = threading.Lock()

    def table(self, nombre):
        return Consulta(self, nombre)

    from_ = table

    def _conectar(self):
        if self._conexion is None or self._conexion.closed or self._conexion.broken:
            # prepare_threshold=None: el pooler de Neon (PgBouncer en modo
            # transacción) puede repartir cada transacción en otra conexión, y
            # un prepared statement de una no existe en la otra.
            self._conexion = psycopg.connect(self._url, autocommit=True,
                                             prepare_threshold=None, connect_timeout=15)
        return self._conexion

    def _ejecutar(self, consulta, params):
        with self._lock:
            for intento in (1, 2):
                try:
                    # Una sentencia por consulta y en autocommit: un solo viaje
                    # a la base. Las fechas con zona salen en UTC porque la base
                    # tiene `timezone = 'UTC'` (ver schema.sql), como Supabase.
                    with self._conectar().cursor() as cur:
                        cur.execute(consulta, params)
                        return cur.fetchall()
                except psycopg.OperationalError as e:
                    self._conexion = None
                    if intento == 2:
                        raise APIError(str(e).strip(), code=getattr(e, 'sqlstate', None)) from e
                except psycopg.Error as e:
                    diag = getattr(e, 'diag', None)
                    raise APIError(
                        (diag.message_primary if diag and diag.message_primary else str(e)).strip(),
                        code=e.sqlstate,
                        details=diag.message_detail if diag else None) from e

    def _correr(self, consulta, params):
        filas = self._ejecutar(consulta, params)
        return filas[0][0] if filas else []

    def _esquema(self) -> _Esquema:
        if self._esquema_cache is None:
            columnas = self._ejecutar(_SQL_COLUMNAS, None)
            fks = self._ejecutar(_SQL_FKS, None)
            self._esquema_cache = _Esquema(columnas, fks)
        return self._esquema_cache

    def _param(self, tabla, columna, arreglo=False):
        """Un placeholder con cast al tipo de la columna.

        PostgREST manda todo como texto y Postgres lo convierte según la
        columna; acá se hace lo mismo con el cast explícito, así un uuid se
        compara como uuid y el índice se usa.
        """
        tipo = self._esquema().tipo(tabla, columna)
        if tipo is None:
            # Columna que no existe: que lo diga Postgres, con su 42703.
            return sql.SQL('%s')
        return sql.SQL('%s::' + tipo + ('[]' if arreglo else ''))

    def _clave_primaria(self, tabla):
        filas = self._ejecutar(
            "select a.attname from pg_index i join pg_attribute a "
            "on a.attrelid = i.indrelid and a.attnum = any(i.indkey) "
            "where i.indrelid = format('public.%%I', %s::text)::regclass and i.indisprimary",
            [tabla])
        return [f[0] for f in filas]


def create_client(url: Optional[str]) -> Cliente:
    if not url:
        raise RuntimeError('Falta DATABASE_URL (la cadena de conexión de Neon)')
    return Cliente(url)
