"""Los modales usan clases que existen y arrancan ocultos.

Este test existe por un bug que ninguno de los otros vio. Se agregaron dos
modales copiando la estructura de memoria —`modal`, `modal-h`, `modal-x`,
`modal-b`, `modal-f`— y las clases reales son otras: `modal-overlay`,
`modal-head`, `modal-close`, `modal-body`, `modal-footer`. Como
`.modal` no está definida en ningún lado, no había `display:none`: los dos
modales aparecían siempre, dentro del flujo de la página, encima del contenido.

La suite entera pasaba en verde. Los tests de Python prueban endpoints y
`node --check` prueba que el JavaScript parsee; una clase de CSS que no existe
no rompe ninguna de las dos cosas, sólo la pantalla.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES = RAIZ / 'templates'
CSS = RAIZ / 'static' / 'css'

PLANTILLAS = sorted(p.name for p in TEMPLATES.glob('*.html'))


def _css_disponible(ruta):
    """Todo el CSS que ve esa plantilla: el suyo y el de las hojas del proyecto."""
    css = '\n'.join(m for m in re.findall(r'<style>(.*?)</style>',
                                          ruta.read_text(), re.S))
    for hoja in CSS.glob('*.css'):
        css += '\n' + hoja.read_text()
    return css


def _clases_usadas(src, prefijo):
    """Los tokens de `class="..."` que arrancan con ese prefijo."""
    usadas = set()
    for m in re.finditer(r'class="([^"]*)"', src):
        for token in m.group(1).split():
            if token == prefijo or token.startswith(prefijo + '-'):
                usadas.add(token)
    return usadas


@pytest.mark.parametrize('nombre', PLANTILLAS)
def test_las_clases_de_modal_existen_en_el_css(nombre):
    ruta = TEMPLATES / nombre
    src = ruta.read_text()
    css = _css_disponible(ruta)

    huerfanas = sorted(c for c in _clases_usadas(src, 'modal')
                       if not re.search(r'\.' + re.escape(c) + r'\b', css))
    assert not huerfanas, (
        f'{nombre}: clases de modal que no están definidas en ningún CSS:\n'
        + '\n'.join(f'  - .{c}' for c in huerfanas)
        + '\n\nSin definición no hay display:none: el modal se dibuja siempre, '
          'dentro del flujo de la página.'
    )


@pytest.mark.parametrize('nombre', PLANTILLAS)
def test_lo_que_abre_openModal_es_un_overlay(nombre):
    """Un modal que no es `.modal-overlay` no tiene cómo ocultarse ni centrarse."""
    src = (TEMPLATES / nombre).read_text()
    objetivos = set(re.findall(r"openModal\('([^']+)'\)", src))

    rotos = []
    for mid in objetivos:
        m = re.search(r'<div([^>]*)id="' + re.escape(mid) + r'"([^>]*)>', src)
        if not m:
            rotos.append(f'{mid} (no existe el elemento)')
            continue
        if 'modal-overlay' not in m.group(1) + m.group(2):
            rotos.append(f'{mid} (no tiene la clase modal-overlay)')

    assert not rotos, (
        f'{nombre}: openModal() abre elementos que no son overlays:\n'
        + '\n'.join(f'  - {r}' for r in sorted(rotos))
    )


@pytest.mark.parametrize('nombre', PLANTILLAS)
def test_todo_overlay_se_puede_cerrar(nombre):
    """Un overlay sin forma de cerrarse deja la pantalla trabada."""
    src = (TEMPLATES / nombre).read_text()
    sin_salida = []
    for m in re.finditer(r'<div[^>]*class="[^"]*modal-overlay[^"]*"[^>]*id="([^"]+)"', src):
        mid = m.group(1)
        if f"closeModal('{mid}')" not in src:
            sin_salida.append(mid)
    assert not sin_salida, (
        f'{nombre}: overlays sin ningún closeModal(): ' + ', '.join(sorted(sin_salida))
    )
