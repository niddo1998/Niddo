"""El bloque «Datos de pago» del mail de expensas (#26).

Es lo que el vecino mira para pagar: fechas como se escriben acá
(10/11/2026) y nunca un «None» de Python cuando el consorcio no cargó banco
o la liquidación no tiene segundo vencimiento.
"""

import re

import app as app_mod


def _datos_de_pago(liq, consorcio):
    html = app_mod._generar_resumen_html(
        {'periodo': '2026-11', 'numero_revision': 1, **liq},
        {'unidad_id': 'uf-1', 'total_unidad': 1000},
        [], consorcio, {'numero': '1A'})
    bloque = html.split('Datos de pago', 1)[1].split('</table>', 1)[0]
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', bloque)).strip()


def test_sin_banco_ni_segundo_vencimiento_no_aparece_none():
    texto = _datos_de_pago(
        {'fecha_vencimiento_1': '2026-11-10', 'fecha_vencimiento_2': None,
         'interes_2_vto': None},
        {'banco_nombre': None, 'banco_cbu': None})
    assert 'None' not in texto
    assert '1er vencimiento 10/11/2026' in texto
    assert '2do vencimiento' not in texto
    assert 'Banco —' in texto and 'CBU —' in texto


def test_con_segundo_vencimiento_las_fechas_van_en_dd_mm_aaaa():
    texto = _datos_de_pago(
        {'fecha_vencimiento_1': '2026-11-10', 'fecha_vencimiento_2': '2026-11-20',
         'interes_2_vto': 5},
        {'banco_nombre': 'Banco Ficticio', 'banco_cbu': '0000000000000000000001'})
    assert '1er vencimiento 10/11/2026' in texto
    assert '2do vencimiento 20/11/2026 (+5%)' in texto
    assert '2026-11' not in texto
    assert 'Banco Banco Ficticio' in texto


def test_los_datos_bancarios_se_escapan():
    texto = app_mod._generar_resumen_html(
        {'periodo': '2026-11', 'fecha_vencimiento_1': '2026-11-10'},
        {'unidad_id': 'uf-1', 'total_unidad': 1000}, [],
        {'banco_nombre': '<b>x</b>', 'banco_cbu': '1'}, {'numero': '1A'})
    assert '<b>x</b>' not in texto
