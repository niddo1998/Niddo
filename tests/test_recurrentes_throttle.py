"""La lista de gastos no barre las plantillas recurrentes en cada pedido.

La pantalla de Gastos pide la lista cada vez que se cambia de mes o de
consorcio, y barrer las plantillas son dos consultas más por clic. Se barre la
primera vez y después como mucho cada diez minutos, salvo que se haya cargado o
editado un gasto en el medio.
"""

import pytest


@pytest.fixture
def admin(base, app_modulo, monkeypatch):
    llamadas = []
    monkeypatch.setattr(app_modulo, 'generar_recurrentes',
                        lambda admin_id, hoy=None: llamadas.append(admin_id) or 0)
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'Admin', 'role': 'admin'}
    base.setdefault('gastos', [])
    return c, llamadas


def test_cambiar_de_mes_no_vuelve_a_barrer(admin):
    c, llamadas = admin
    for mes in ('2026-07', '2026-08', '2026-09'):
        assert c.get(f'/api/gastos?desde={mes}-01&hasta={mes}-28').status_code == 200
    assert llamadas == ['admin-1']


def test_despues_de_cargar_un_gasto_se_vuelve_a_barrer(admin):
    c, llamadas = admin
    c.get('/api/gastos')
    c.post('/api/gastos', json={'consorcio_id': 'cons-1', 'monto': 10, 'descripcion': 'x',
                                'recurrente': True, 'dia_carga': 5})
    c.get('/api/gastos')
    assert llamadas == ['admin-1', 'admin-1']


def test_pasados_diez_minutos_se_vuelve_a_barrer(admin, app_modulo):
    c, llamadas = admin
    c.get('/api/gastos')
    with c.session_transaction() as s:
        visto = dict(s['recurrentes_revisados'])
        visto['at'] -= app_modulo.RECURRENTES_CADA_SEG + 1
        s['recurrentes_revisados'] = visto
    c.get('/api/gastos')
    assert len(llamadas) == 2
