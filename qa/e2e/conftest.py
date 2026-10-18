"""Fixtures de los E2E: navegador, login por rol y un "detector" de errores.

Corren contra el ambiente de pruebas que levanta qa/levantar.sh. Cada página
que se abre queda vigilada: errores de JavaScript, console.error y respuestas
5xx de la propia app se juntan y el test falla al final si hubo alguno. Los
recursos externos (fuentes, CDNs) se cortan: el workspace no tiene salida a
internet y no son lo que se está probando.
"""

import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

BASE = os.environ.get('NIDDO_QA_URL', 'http://localhost:5055')
SALIDA = Path(__file__).resolve().parent.parent / '.salida' / 'capturas'
CHROMIUM = os.environ.get('QA_CHROMIUM', '/home/claude/.qa-chromium/chromium')
ARGS = ['--no-sandbox', '--disable-gpu', '--use-gl=swiftshader', '--disable-vulkan',
        '--disable-features=Vulkan', '--disable-dev-shm-usage']

ES_LOCAL = re.compile(r'^https?://(localhost|127\.0\.0\.1)(:\d+)?/')

DISPOSITIVOS = {
    'desktop': {'viewport': {'width': 1366, 'height': 800}},
    'mobile': {'viewport': {'width': 390, 'height': 844}, 'is_mobile': True,
               'has_touch': True, 'device_scale_factor': 2},
}


@pytest.fixture(scope='session')
def navegador():
    with sync_playwright() as p:
        opciones = {'args': ARGS}
        if Path(CHROMIUM).exists():
            opciones['executable_path'] = CHROMIUM
        b = p.chromium.launch(**opciones)
        yield b
        b.close()


class Vigia:
    """Junta todo lo que salió mal en una página mientras se la usa."""

    def __init__(self, page):
        self.problemas = []
        page.on('pageerror', lambda e: self.problemas.append(f'JS: {e}'))
        page.on('console', self._consola)
        page.on('response', self._respuesta)

    def _consola(self, msg):
        if msg.type != 'error':
            return
        url = (msg.location or {}).get('url', '')
        if url and not ES_LOCAL.match(url):
            return  # recurso externo bloqueado en el workspace
        if 'Failed to load resource' in msg.text and not url:
            return
        self.problemas.append(f'console.error: {msg.text} ({url})')

    def _respuesta(self, resp):
        if ES_LOCAL.match(resp.url) and resp.status >= 500:
            self.problemas.append(f'HTTP {resp.status}: {resp.request.method} {resp.url}')

    def verificar(self, contexto=''):
        assert not self.problemas, f'{contexto}\n' + '\n'.join(self.problemas)


@pytest.fixture
def abrir(navegador):
    """abrir(rol, dispositivo) -> (page, vigia), ya logueado con /qa/login/<rol>."""
    contextos = []

    def _abrir(rol, dispositivo='desktop'):
        ctx = navegador.new_context(base_url=BASE, locale='es-AR',
                                    timezone_id='America/Argentina/Buenos_Aires',
                                    **DISPOSITIVOS[dispositivo])
        ctx.route(re.compile(r'^https?://(?!localhost|127\.0\.0\.1).*'), lambda r: r.abort())
        contextos.append(ctx)
        page = ctx.new_page()
        vigia = Vigia(page)
        page.goto(f'/qa/login/{rol}')
        page.wait_for_load_state('networkidle')
        return page, vigia

    yield _abrir
    for c in contextos:
        c.close()


def capturar(page, nombre):
    SALIDA.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SALIDA / f'{nombre}.png'), full_page=True)
