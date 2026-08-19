"""Ningún dato de usuario se pinta en el DOM sin escapar.

Los dashboards arman el HTML con `innerHTML` y template literals. Es rápido y
la pantalla depende de eso, así que el arreglo no fue sacarlo sino escapar cada
valor que escribe una persona. El problema de un arreglo así es que dura hasta
la próxima tabla que alguien agregue.

Este test es el que hace que dure: recorre las interpolaciones de los tres
templates y falla si aparece un campo de texto que no pasó por `esc()`. Cuando
falla sobre código nuevo, la respuesta correcta casi siempre es envolver el
valor, no agregar el campo a la lista de excepciones.
"""

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'

# Los nombres de columna que escribe una persona, en cualquiera de las tablas.
CAMPOS_DE_TEXTO = (
    r'(titulo|cuerpo|descripcion|nombre|apellido|email|categoria|notas|'
    r'observaciones|respuesta_admin|condiciones_uso|rubro|unidad|numero|'
    r'piso|direccion|cuit|encargado_\w+|opcion|mi_opcion|medio_pago|'
    r'archivo_nombre|adjunto_nombre|metodo_pago|frecuencia|motivo\w*)'
)

ESCAPADORES = ('esc(', 'escHtml(', 'escapar(')

# Únicas dos excepciones, y las dos por motivo verificable:
EXCEPCIONES = {
    # Escapa adentro: `return escHtml(cat)`.
    'categoriaBadge(g.categoria)',
    # No pinta la categoría: pinta la palabra ' selected'.
    "d.categoria === c ? ' selected' : ''",
}


def _interpolaciones(src):
    """Cada `${...}` del archivo, con las llaves balanceadas."""
    for m in re.finditer(r'\$\{', src):
        prof, j = 1, m.end()
        while j < len(src) and prof:
            if src[j] == '{':
                prof += 1
            elif src[j] == '}':
                prof -= 1
            j += 1
        # Se le sacan los template literals anidados: cada uno trae sus propias
        # interpolaciones y el bucle las visita por su cuenta.
        yield re.sub(r'`[^`]*`', '', src[m.end():j - 1])


def _sin_escapar(ruta):
    pendientes = []
    for expr in _interpolaciones(ruta.read_text()):
        if expr.strip() in EXCEPCIONES:
            continue
        for campo in re.finditer(r'\.' + CAMPOS_DE_TEXTO + r'\b\s*(.?)', expr):
            # Un campo seguido de `?` es la condición de un ternario: lo que se
            # pinta es alguna de las ramas, y cada rama se revisa por su lado.
            if campo.group(2) == '?':
                continue
            contexto = expr[max(0, campo.start() - 60):campo.end() + 3]
            if any(e in contexto for e in ESCAPADORES):
                continue
            pendientes.append(expr.strip()[:90])
            break
    return sorted(set(pendientes))


@pytest.mark.parametrize('nombre', [
    'admin_dashboard.html',
    'vecino_dashboard.html',
    'superadmin.html',
])
def test_no_queda_dato_de_usuario_sin_escapar(nombre):
    pendientes = _sin_escapar(TEMPLATES / nombre)
    assert not pendientes, (
        f'{nombre}: {len(pendientes)} interpolaciones sin escapar.\n'
        + '\n'.join(f'  - {p}' for p in pendientes)
        + '\n\nEnvolvelas con esc()/escHtml() antes de mergear.'
    )


@pytest.mark.parametrize('nombre', [
    'admin_dashboard.html',
    'vecino_dashboard.html',
])
def test_el_template_define_su_escapador(nombre):
    """Sin el helper, todo lo de arriba sería un `esc is not defined` en runtime."""
    src = (TEMPLATES / nombre).read_text()
    assert re.search(r'const (esc|escHtml) = ', src)


def test_el_escapador_cubre_los_cinco_caracteres():
    """`&<>"'` — sin las comillas se escapa el texto pero no los atributos."""
    for nombre in ('admin_dashboard.html', 'vecino_dashboard.html'):
        src = (TEMPLATES / nombre).read_text()
        cuerpo = re.search(r'const (?:esc|escHtml) = .*?\n.*?\n', src, re.S).group(0)
        for entidad in ('&amp;', '&lt;', '&gt;', '&quot;', '&#39;'):
            assert entidad in cuerpo, f'{nombre}: falta {entidad}'
