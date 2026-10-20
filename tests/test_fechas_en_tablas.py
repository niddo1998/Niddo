"""Las fechas que se leen en el panel salen como 30/09/2026, no 2026-09-30.

El ISO de la base se colaba en las tablas de Cobros (#24). Este test recorre
el panel del administrador y falla si una fecha se pinta como texto sin pasar
por `fmtFecha`. Quedan afuera los usos que no son texto para leer: el
`value` de un `<input type="date">` (que exige ISO), los argumentos de un
`onclick` y los `data-val` que se usan para ordenar.
"""

import re
from pathlib import Path

PANEL = Path(__file__).resolve().parent.parent / 'templates' / 'admin_dashboard.html'
NO_ES_TEXTO = ('value="${', 'onclick=', 'data-val=')
FORMATEADORES = ('fmtFecha(', 'toLocaleDateString(')


def test_las_fechas_del_panel_pasan_por_fmtFecha():
    crudas = []
    for n, linea in enumerate(PANEL.read_text().splitlines(), 1):
        if any(x in linea for x in NO_ES_TEXTO):
            continue
        for m in re.finditer(r'\$\{([^}]*\.fecha_\w+[^}]*)\}', linea):
            if not any(f in m.group(1) for f in FORMATEADORES):
                crudas.append(f'L{n}: {m.group(0)[:90]}')
    assert not crudas, 'Fechas sin fmtFecha:\n' + '\n'.join(crudas)
