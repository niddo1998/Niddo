"""La pantalla del vecino nace sabiendo cuál de las tres es.

El vecino sin aprobar veía su dashboard un instante —los KPIs, el sidebar, todo—
y recién cuando /api/me y /api/vecinos/mi-solicitud contestaban le caía encima
el overlay de la sala de espera. El parpadeo no era un problema de animación:
la decisión de qué pantalla mostrar se tomaba en el navegador, después de
pintar la que no correspondía.

Ahora la toma el servidor y la página se renderiza ya resuelta. Estos tests
miran el HTML que sale de /dashboard/vecino, que es donde se ve.
"""

import re

import pytest


@pytest.fixture
def sesion(base, app_modulo):
    """Un cliente logueado como `vec-nuevo`, sin edificio todavía."""
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|nuevo', 'email': 'nuevo@test',
                     'name': 'Recién llegado', 'role': 'vecino'}
    return c


def _vecino(base, **campos):
    fila = {'id': 'vec-nuevo', 'auth0_id': 'auth0|nuevo', 'nombre': 'Recién llegado',
            'email': 'nuevo@test', 'consorcio_id': None, 'unidad_id': None,
            'unidad': None, 'estado_asociacion': None, 'rol': 'propietario',
            'consorcio_solicitado_id': None, 'unidad_solicitada_id': None,
            'solicitud_at': None, 'motivo_rechazo': None}
    fila.update(campos)
    base['vecinos'].append(fila)
    return fila


def _clases(html, overlay_id):
    m = re.search(r'<div class="([^"]*)" id="' + overlay_id + '">', html)
    assert m, f'no se encontró el overlay {overlay_id} en el HTML'
    return m.group(1).split()


def _visible(html, overlay_id):
    return 'visible' in _clases(html, overlay_id)


def test_el_pendiente_abre_en_la_sala_de_espera(sesion, base):
    _vecino(base, estado_asociacion='pendiente',
            consorcio_solicitado_id='cons-1', unidad_solicitada_id='uf-1')
    html = sesion.get('/dashboard/vecino').get_data(as_text=True)
    assert _visible(html, 'pending-overlay')
    assert not _visible(html, 'onboarding-overlay')


def test_la_espera_dice_qué_pidió_sin_ir_a_buscarlo(sesion, base):
    _vecino(base, estado_asociacion='pendiente',
            consorcio_solicitado_id='cons-1', unidad_solicitada_id='uf-1')
    html = sesion.get('/dashboard/vecino').get_data(as_text=True)
    assert 'Pediste entrar a Mío · UF 1A.' in html


def test_el_que_nunca_pidió_abre_en_el_alta(sesion, base):
    _vecino(base)
    html = sesion.get('/dashboard/vecino').get_data(as_text=True)
    assert _visible(html, 'onboarding-overlay')
    assert not _visible(html, 'pending-overlay')


def test_el_rechazado_abre_en_el_alta_con_el_motivo(sesion, base):
    _vecino(base, estado_asociacion='rechazado', motivo_rechazo='Esa UF ya tiene dueño')
    html = sesion.get('/dashboard/vecino').get_data(as_text=True)
    assert _visible(html, 'onboarding-overlay')
    assert 'Esa UF ya tiene dueño' in html


def test_el_motivo_del_rechazo_va_escapado(sesion, base):
    """Lo escribe el administrador y se pinta en la página de otro."""
    _vecino(base, estado_asociacion='rechazado',
            motivo_rechazo='<img src=x onerror=alert(1)>')
    html = sesion.get('/dashboard/vecino').get_data(as_text=True)
    assert '<img src=x onerror=alert(1)>' not in html
    assert '&lt;img src=x onerror=alert(1)&gt;' in html


def test_el_aprobado_no_ve_ningún_overlay(client, base):
    """`vec-1` está adentro: tiene consorcio_id y unidad_id."""
    html = client.get('/dashboard/vecino').get_data(as_text=True)
    assert not _visible(html, 'pending-overlay')
    assert not _visible(html, 'onboarding-overlay')
