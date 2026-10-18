"""Recorrido básico: cada rol entra y abre cada sección sin que nada explote.

Es la red de seguridad más gruesa: no valida reglas de negocio, valida que
ninguna pantalla tire errores de JavaScript, ningún endpoint devuelva 500 y que
en mobile nada se salga de la pantalla. Las reglas de negocio van en tests
específicos (test_flujos_*.py).
"""

import pytest

from conftest import capturar

SECCIONES_ADMIN = ['dashboard', 'consorcios', 'gastos', 'liquidaciones', 'cobros',
                   'balance', 'comunicacion', 'amenities', 'config']
SECCIONES_VECINO = ['inicio', 'comunicados', 'expensas', 'gastos', 'reclamos',
                    'mensajes', 'reservas', 'archivos', 'perfil']


def _sin_scroll_horizontal(page):
    ancho = page.evaluate('document.documentElement.scrollWidth')
    vista = page.evaluate('window.innerWidth')
    return ancho <= vista + 1, ancho, vista


@pytest.mark.parametrize('seccion', SECCIONES_ADMIN)
def test_admin_abre_cada_seccion(abrir, seccion):
    page, vigia = abrir('admin')
    assert '/dashboard/admin' in page.url
    page.evaluate("([s]) => show(s, document.querySelector(`[onclick^=\"show('${s}'\"]`))", [seccion])
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(300)
    capturar(page, f'admin-desktop-{seccion}')
    vigia.verificar(f'admin → {seccion}')


@pytest.mark.parametrize('seccion', SECCIONES_VECINO)
def test_vecino_abre_cada_seccion(abrir, seccion):
    page, vigia = abrir('vecino')
    assert '/dashboard/vecino' in page.url
    page.evaluate('(s) => showSection(s)', seccion)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(300)
    capturar(page, f'vecino-desktop-{seccion}')
    vigia.verificar(f'vecino → {seccion}')


@pytest.mark.parametrize('rol', ['admin', 'vecino'])
def test_mobile_carga_sin_errores_ni_scroll_horizontal(abrir, rol):
    page, vigia = abrir(rol, 'mobile')
    capturar(page, f'{rol}-mobile-inicio')
    ok, ancho, vista = _sin_scroll_horizontal(page)
    assert ok, f'{rol} mobile: el contenido mide {ancho}px en una pantalla de {vista}px'
    vigia.verificar(f'{rol} mobile')


def test_superadmin_entra_al_panel(abrir):
    page, vigia = abrir('superadmin')
    page.goto('/superadmin')
    page.wait_for_load_state('networkidle')
    assert '/superadmin' in page.url, f'redirigió a {page.url}'
    capturar(page, 'superadmin-desktop-panel')
    vigia.verificar('superadmin → /superadmin')


def test_admin_comun_no_entra_al_superadmin(abrir):
    # Contesta 404 a propósito: ni siquiera revela que el panel existe.
    page, _ = abrir('admin')
    resp = page.goto('/superadmin')
    assert resp.status == 404, f'un admin sin privilegio recibió {resp.status} en /superadmin'


def test_admin_pendiente_va_a_la_solicitud(abrir):
    page, vigia = abrir('pendiente')
    assert '/solicitud' in page.url
    capturar(page, 'pendiente-desktop-solicitud')
    vigia.verificar('admin pendiente → /solicitud')


def test_vecino_no_entra_al_panel_admin(abrir):
    page, _ = abrir('vecino')
    page.goto('/dashboard/admin')
    page.wait_for_load_state('networkidle')
    assert '/dashboard/admin' not in page.url
