"""El acceso del vecino cuelga de dos columnas, y casi nadie puede escribirlas.

Todo el gate del alta se apoya en una sola idea: `vecinos.consorcio_id` y
`vecinos.unidad_id` significan "aprobado y adentro". Ningún endpoint filtra por
`estado_asociacion` — no hace falta, porque sin esas columnas las consultas de
datos devuelven vacío solas. Eso es lo que hace que el endpoint que se agregue
mañana nazca cerrado sin que nadie se acuerde.

La idea vale mientras nada más las escriba. Este test es lo que hace que dure:
si aparece un tercer lugar que las toca, falla acá y no en producción seis
meses después. Cuando falle sobre código nuevo, la pregunta correcta es "¿este
camino verifica de verdad de quién es la unidad?", no "¿cómo lo agrego a la
lista?".
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / 'app.py'

# Los dos únicos caminos legítimos, cada uno con su razón:
#
#   _aprobar_vecino  — la aprobación del administrador. Es EL camino.
#   upsert_user      — auto-asociación por email. El admin cargó la unidad en
#                      el padrón con ese mail, así que ya dijo de quién es;
#                      la verificación la hizo él al escribirlo.
AUTORIZADAS = {'_aprobar_vecino', 'upsert_user'}

COLUMNAS = ('consorcio_id', 'unidad_id')


def _funcion_de(src, pos):
    """Nombre del `def` que contiene esa posición del archivo."""
    previos = [m for m in re.finditer(r'^def (\w+)', src[:pos], re.M)]
    return previos[-1].group(1) if previos else '(nivel de módulo)'


def _escrituras_a_vecinos(src):
    """Cada update/insert/upsert sobre `vecinos` que toque las dos columnas."""
    encontradas = []
    for m in re.finditer(r"table\('vecinos'\)\s*\.\s*(update|insert|upsert)\(", src):
        # El payload va hasta el `.execute()` de esa cadena.
        fin = src.find('.execute()', m.end())
        bloque = src[m.end():fin if fin > 0 else m.end() + 400]
        for col in COLUMNAS:
            if re.search(r"'" + col + r"'\s*:", bloque):
                encontradas.append((_funcion_de(src, m.start()), col))
    return encontradas


def test_solo_la_aprobacion_deja_entrar_a_un_vecino():
    src = APP.read_text()
    intrusas = sorted({fn for fn, _ in _escrituras_a_vecinos(src)
                       if fn not in AUTORIZADAS})
    assert not intrusas, (
        'Estas funciones escriben consorcio_id o unidad_id en `vecinos` y no '
        'deberían:\n' + '\n'.join(f'  - {f}' for f in intrusas) +
        '\n\nEsas dos columnas son el gate del alta: escribirlas es dejar a '
        'alguien adentro sin que el administrador lo apruebe.'
    )


def test_la_lista_de_autorizadas_no_quedo_vieja():
    """Si una autorizada se renombra o se borra, avisar en vez de aflojar."""
    src = APP.read_text()
    presentes = {fn for fn, _ in _escrituras_a_vecinos(src)}
    huerfanas = AUTORIZADAS - presentes
    assert not huerfanas, (
        f'AUTORIZADAS nombra funciones que ya no escriben esas columnas: '
        f'{sorted(huerfanas)}. Sacalas de la lista para que siga sirviendo.'
    )
