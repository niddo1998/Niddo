"""El JavaScript de los paneles parsea.

Los dos dashboards son un template con mil líneas de JavaScript inline adentro.
Nada de lo que corre en CI lo mira: los tests de Python prueban endpoints y el
navegador se entera del paréntesis que falta cuando la pantalla ya salió en
blanco, sin un solo error visible más que "no carga".

Esto lo renderiza como lo sirve Flask —las llaves de Jinja adentro del script
también tienen que dar JavaScript válido— y se lo pasa a `node --check`.
"""

import re
import shutil
import subprocess

import pytest


PANELES = [
    ('vecino', '/dashboard/vecino'),
    ('admin', '/dashboard/admin'),
]


def _scripts_inline(html):
    return re.findall(r'<script>(.*?)</script>', html, re.S)


@pytest.fixture
def sesiones(base, app_modulo):
    app_modulo.app.config['TESTING'] = True

    def como(rol, sub):
        c = app_modulo.app.test_client()
        with c.session_transaction() as s:
            s['user'] = {'sub': sub, 'email': 'x@test', 'name': 'X', 'role': rol}
        return c

    return {'vecino': como('vecino', 'auth0|uno'), 'admin': como('admin', 'auth0|admin')}


@pytest.mark.skipif(not shutil.which('node'), reason='node no está instalado')
@pytest.mark.parametrize('rol,ruta', PANELES)
def test_el_javascript_del_panel_parsea(sesiones, rol, ruta, tmp_path):
    html = sesiones[rol].get(ruta).get_data(as_text=True)
    scripts = _scripts_inline(html)
    assert scripts, f'{ruta} no trae ningún <script> inline'

    for i, src in enumerate(scripts):
        archivo = tmp_path / f'{rol}_{i}.js'
        archivo.write_text(src)
        r = subprocess.run(['node', '--check', str(archivo)],
                           capture_output=True, text=True)
        assert r.returncode == 0, (
            f'El script #{i} de {ruta} no parsea:\n{r.stderr}')
