"""Tests de `generar_recurrentes` contra un Supabase falso.

El spec decía cubrir sólo el cálculo de períodos y dejar la parte que toca la
base al índice único. Igual conviene un smoke test del pegamento: si el
`select()` pide una columna que no existe, o el hijo sale con `recurrente` en
true, en producción se ve como gastos duplicándose en progresión geométrica y
acá se ve como un test rojo.

El doble valida los nombres de columna contra el schema real, así que un typo
en el select falla el test en vez de fallar en Vercel.
"""

import os
import sys
from datetime import date

import pytest

# `app.py` lee estas variables al importarse. Valores de juguete: los tests no
# tocan la red, el cliente de Supabase se reemplaza por el doble de abajo.
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'test')
os.environ.setdefault('AUTH0_DOMAIN', 'test.auth0.com')
os.environ.setdefault('AUTH0_CLIENT_ID', 'test')
os.environ.setdefault('AUTH0_CLIENT_SECRET', 'test')

import app as app_mod


COLUMNAS_GASTOS = {
    'id', 'consorcio_id', 'proveedor_id', 'unidad_id', 'descripcion', 'categoria',
    'monto', 'fecha_gasto', 'fecha_vencimiento', 'pagado', 'fecha_pago',
    'metodo_pago', 'recurrente', 'frecuencia', 'archivo_nombre', 'notas',
    'admin_id', 'created_at',
    # v12
    'dia_carga', 'gasto_origen_id', 'periodo_generado', 'tarifa_confirmada',
}


class _Resultado:
    def __init__(self, data):
        self.data = data


class _Consulta:
    """Imita el encadenado de supabase-py sobre una lista de dicts."""

    def __init__(self, tabla, filas, insertados):
        self.tabla = tabla
        self.filas = filas
        self.insertados = insertados
        self.filtros = []
        self.filtro_in = None
        self.a_insertar = None

    def select(self, cols):
        for col in (c.strip() for c in cols.split(',')):
            if col and col not in COLUMNAS_GASTOS:
                raise AssertionError(
                    f'El select pide "{col}", que no existe en {self.tabla}'
                )
        return self

    def eq(self, campo, valor):
        self.filtros.append((campo, valor))
        return self

    def in_(self, campo, valores):
        self.filtro_in = (campo, list(valores))
        return self

    def order(self, *a, **k):
        return self

    def insert(self, payload):
        self.a_insertar = payload
        return self

    def execute(self):
        if self.a_insertar is not None:
            fila = dict(self.a_insertar)
            for campo in fila:
                assert campo in COLUMNAS_GASTOS, f'El insert escribe "{campo}", que no existe'
            clave = (fila.get('gasto_origen_id'), fila.get('periodo_generado'))
            if clave[0] is not None:
                # El índice único de v12, replicado.
                for existente in self.filas:
                    if (existente.get('gasto_origen_id'),
                            existente.get('periodo_generado')) == clave:
                        raise Exception('duplicate key value violates unique constraint')
            fila.setdefault('id', f'hijo-{len(self.filas)}')
            self.filas.append(fila)
            self.insertados.append(fila)
            return _Resultado([fila])

        filas = self.filas
        for campo, valor in self.filtros:
            filas = [f for f in filas if f.get(campo) == valor]
        if self.filtro_in:
            campo, valores = self.filtro_in
            filas = [f for f in filas if f.get(campo) in valores]
        return _Resultado(list(filas))


class FakeSupabase:
    def __init__(self, filas):
        self.filas = filas
        self.insertados = []

    def table(self, nombre):
        return _Consulta(nombre, self.filas, self.insertados)


def plantilla(**extra):
    base = {
        'id': 'plantilla-1', 'admin_id': 'admin-1', 'consorcio_id': 'cons-1',
        'proveedor_id': None, 'unidad_id': None, 'descripcion': 'Sueldo encargado',
        'categoria': 'sueldos', 'monto': 400000, 'metodo_pago': 'transferencia',
        'notas': '', 'fecha_gasto': '2026-05-10', 'dia_carga': 10,
        'frecuencia': 'mensual', 'recurrente': True,
        'gasto_origen_id': None, 'periodo_generado': None, 'tarifa_confirmada': True,
    }
    base.update(extra)
    return base


@pytest.fixture
def fake(monkeypatch):
    def _armar(filas):
        s = FakeSupabase(filas)
        monkeypatch.setattr(app_mod, 'supabase', s)
        return s
    return _armar


def test_genera_los_meses_faltantes(fake):
    s = fake([plantilla()])
    creados = app_mod.generar_recurrentes('admin-1', hoy=date(2026, 8, 16))
    assert creados == 3
    assert [g['periodo_generado'] for g in s.insertados] == ['2026-06', '2026-07', '2026-08']


def test_el_hijo_no_es_recurrente(fake):
    """Si heredara el tilde, cada hijo generaría los suyos: progresión geométrica."""
    s = fake([plantilla()])
    app_mod.generar_recurrentes('admin-1', hoy=date(2026, 6, 10))
    assert s.insertados[0]['recurrente'] is False
    assert s.insertados[0]['gasto_origen_id'] == 'plantilla-1'


def test_el_hijo_copia_el_monto_sin_confirmar(fake):
    s = fake([plantilla()])
    app_mod.generar_recurrentes('admin-1', hoy=date(2026, 6, 10))
    hijo = s.insertados[0]
    assert hijo['monto'] == 400000
    assert hijo['tarifa_confirmada'] is False
    assert hijo['pagado'] is False
    assert hijo['fecha_gasto'] == '2026-06-10'


def test_es_idempotente(fake):
    s = fake([plantilla()])
    app_mod.generar_recurrentes('admin-1', hoy=date(2026, 8, 16))
    s.insertados.clear()
    creados = app_mod.generar_recurrentes('admin-1', hoy=date(2026, 8, 16))
    assert creados == 0
    assert s.insertados == []


def test_el_choque_contra_el_indice_unico_no_rompe(fake):
    """Dos requests en paralelo: la segunda inserción rebota y se ignora."""
    filas = [plantilla()]
    s = fake(filas)
    # Otra request ya creó junio entre nuestro chequeo y nuestra inserción.
    filas.append({'id': 'x', 'gasto_origen_id': 'plantilla-1', 'periodo_generado': '2026-06'})
    creados = app_mod.generar_recurrentes('admin-1', hoy=date(2026, 6, 30))
    assert creados == 0


def test_plantilla_sin_dia_no_genera(fake):
    s = fake([plantilla(dia_carga=None)])
    assert app_mod.generar_recurrentes('admin-1', hoy=date(2026, 8, 16)) == 0
    assert s.insertados == []


def test_no_toca_gastos_de_otro_admin(fake):
    s = fake([plantilla(admin_id='admin-2')])
    assert app_mod.generar_recurrentes('admin-1', hoy=date(2026, 8, 16)) == 0


def test_gasto_comun_no_genera_nada(fake):
    s = fake([plantilla(recurrente=False)])
    assert app_mod.generar_recurrentes('admin-1', hoy=date(2026, 8, 16)) == 0
