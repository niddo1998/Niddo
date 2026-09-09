"""Toda tabla que se ve en un teléfono tiene su lista de mobile.

El rediseño mobile convirtió las tablas a listas una por una, con una llamada
explícita a `NiddoMobile.renderList` al lado del `innerHTML` que llena el
`<tbody>`. Ese acuerdo no se podía romper ruidosamente: una feature nueva
escribía su tabla, pasaba los tests, y en el teléfono aparecía como escritorio
—contenida en su caja, scrolleando de costado— sin que nada avisara. Así se
volvieron de escritorio Edificios, Comunicación, Liquidaciones, Amenities y
Balance después de haberse construido la fundación.

Este test es lo que hace ruido. Si agregás un `<tbody id="...">`, o le ponés
`nd-keep-table` a la tabla y decidís conscientemente que ese flujo no es para
el teléfono, o escribís su lista.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES = RAIZ / 'templates'
HOJA_MOBILE = RAIZ / 'static' / 'css' / 'niddo-mobile.css'

DASHBOARDS = ['admin_dashboard.html', 'vecino_dashboard.html']

# Las que sí se dejan como tabla, con el motivo. Ninguna hoy: si alguna vuelve
# a entrar acá, que sea con una línea que diga por qué ese flujo no es para el
# teléfono.
EXCEPCIONES: dict[str, str] = {}


def tbodies_con_id(html: str) -> set[str]:
    return set(re.findall(r'<tbody[^>]*\bid="([^"]+)"', html))


def listas_declaradas(html: str) -> set[str]:
    return set(re.findall(r"""NiddoMobile\.renderList\(\s*['"]([^'"]+)['"]""", html))


def tablas_con_forma_propia(html: str) -> set[str]:
    """Tablas escondidas por id en la hoja de mobile, que traen su propia forma.

    La confirmación del gasto extraído con IA no es una lista: es una tarjeta
    por comprobante con los campos editables adentro. Vale igual —lo que el
    test defiende es que ninguna tabla llegue cruda al teléfono, no que todas
    terminen en `.nd-list`.
    """
    hoja = HOJA_MOBILE.read_text(encoding='utf-8')
    ocultas = set(re.findall(r'#([a-zA-Z0-9_-]+)\s*\{[^}]*display:\s*none', hoja))
    tbodies = set()
    for tabla_id, cuerpo in re.findall(r'<table[^>]*\bid="([^"]+)"([\s\S]*?)</table>', html):
        if tabla_id in ocultas:
            tbodies |= set(re.findall(r'<tbody[^>]*\bid="([^"]+)"', cuerpo))
    return tbodies


@pytest.mark.parametrize('nombre', DASHBOARDS)
def test_toda_tabla_tiene_lista_mobile(nombre):
    html = (TEMPLATES / nombre).read_text(encoding='utf-8')
    tablas = tbodies_con_id(html)
    listas = listas_declaradas(html)

    sueltas = sorted(tablas - listas - tablas_con_forma_propia(html) - set(EXCEPCIONES))
    assert not sueltas, (
        f'{nombre}: estas tablas se ven como escritorio en un teléfono porque '
        f'nadie escribió su lista: {sueltas}. Agregá el NiddoMobile.renderList '
        f'al lado del innerHTML que llena el <tbody>, o sumala a EXCEPCIONES '
        f'con el motivo por el que ese flujo no es para el teléfono.'
    )


@pytest.mark.parametrize('nombre', DASHBOARDS)
def test_no_sobran_listas(nombre):
    """Una lista sin su tabla es código muerto: la tabla se renombró o se fue."""
    html = (TEMPLATES / nombre).read_text(encoding='utf-8')
    huerfanas = sorted(listas_declaradas(html) - tbodies_con_id(html))
    assert not huerfanas, (
        f'{nombre}: estas listas de mobile apuntan a un <tbody> que no existe: '
        f'{huerfanas}.'
    )


# ── La fundación tiene que estar enganchada en las tres pantallas ────────────

@pytest.mark.parametrize('nombre', DASHBOARDS + ['superadmin.html'])
def test_la_pantalla_carga_la_fundacion(nombre):
    """Sin la hoja y el script, la pantalla es el sitio de escritorio achicado.

    superadmin entró tarde —se había construido sin nada de esto— y la única
    forma de que no se vuelva a quedar afuera es preguntarlo acá.
    """
    html = (TEMPLATES / nombre).read_text(encoding='utf-8')
    assert 'css/niddo-mobile.css' in html, f'{nombre}: no carga la hoja de mobile'
    assert 'js/niddo-mobile.js' in html, f'{nombre}: no carga la fundación de mobile'
    assert 'viewport-fit=cover' in html, (
        f'{nombre}: sin viewport-fit=cover las safe areas devuelven 0 y la tab '
        f'bar se apoya sobre el home indicator'
    )


@pytest.mark.parametrize('nombre', DASHBOARDS + ['superadmin.html'])
def test_la_pantalla_tiene_tab_bar(nombre):
    html = (TEMPLATES / nombre).read_text(encoding='utf-8')
    assert 'nd-tabbar' in html, f'{nombre}: no declara la tab bar'
    destinos = re.findall(r'data-tab="([^"]+)"', html)
    assert len(destinos) == 4 or nombre == 'vecino_dashboard.html', (
        f'{nombre}: la tab bar tiene {len(destinos)} destinos y se decidieron 4'
    )
