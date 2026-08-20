"""La cuenta corriente del vecino se baja en Excel y PDF.

`dlCobros()` era el último stub de la pantalla del vecino: mostraba
"próximamente" y no había endpoint detrás.

La ruta no acepta `unidad_id`: la unidad sale de la sesión. Es la diferencia
con /api/vecinos/cobros, que sí lo toma de la query y por eso podía usarse
para leer la cuenta corriente de otra unidad.
"""

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def test_baja_el_excel_de_su_cuenta(client):
    r = client.get('/api/vecinos/cobros/export')
    assert r.status_code == 200
    assert r.mimetype == XLSX
    # Un .xlsx es un zip: si el buffer viniera vacío o fuera JSON de error,
    # el magic number no estaría.
    assert r.data[:2] == b'PK'


def test_baja_el_pdf_de_su_cuenta(client):
    r = client.get('/api/vecinos/cobros/export?fmt=pdf')
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.data[:4] == b'%PDF'


def test_no_hay_parametro_para_pedir_otra_unidad(client, base):
    """Pasar unidad_id ajeno no cambia nada: el parámetro se ignora."""
    base['cobros'].append({
        'id': 'cobro-2', 'consorcio_id': 'cons-2', 'unidad_id': 'uf-2',
        'estado': 'pendiente', 'total': 999, 'monto_base': 999,
        'interes_mora': 0, 'periodo': '2026-08',
    })
    propio = client.get('/api/vecinos/cobros/export').data
    ajeno = client.get('/api/vecinos/cobros/export?unidad_id=uf-2').data
    assert len(propio) == len(ajeno)


def test_sin_unidad_asignada_avisa_en_vez_de_romper(client, base):
    base['vecinos'][0]['unidad_id'] = None
    r = client.get('/api/vecinos/cobros/export')
    assert r.status_code == 400
    assert 'unidad' in r.get_json()['error'].lower()
