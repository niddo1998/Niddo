"""El PDF de la liquidación, con la estructura que usa el mercado.

`liquidacion_pdf` no toca la base ni la red: se le pasan diccionarios y
devuelve bytes, así que se puede probar entero. Lo que se comprueba acá es que
el documento salga y que los bloques que la Ley 941 obliga a rendir estén
todos, no que se vea lindo — eso hay que mirarlo.
"""

import io

import pypdfium2 as pdfium
import pytest

from liquidacion_pdf import construir_pdf, pesos, periodo_largo


def _texto(datos):
    doc = pdfium.PdfDocument(io.BytesIO(datos))
    return '\n'.join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))


LIQ = {'id': 'liq-1', 'periodo': '2026-08', 'numero_revision': 1,
       'fecha_vencimiento_1': '2026-09-10', 'fecha_vencimiento_2': '2026-09-15',
       'interes_2_vto': 3, 'saldo_inicial': 100000.0, 'total_ingresos': 50000.0,
       'total_egresos': 30000.0, 'admin_id': 'admin-1'}
CON = {'nombre': 'Consorcio Pacheco 2876', 'direccion': 'Pacheco 2876, CABA',
       'cuit': '30-71250333-1', 'clave_suterh': '85693',
       'tasa_interes_mora': 3.0, 'recargo_segundo_vto': 3.0,
       'banco_nombre': 'Santander', 'banco_cbu': '0720014420000001309940'}
ADM = {'nombre': 'Diego Martin', 'cuit': '20-23073202-8',
       'matricula': 'RPA 10.455 / RPAC 679', 'email': 'a@test', 'telefono': '11-5989-3316'}
RUBROS = [{
    'numero_rubro': 2, 'nombre': 'Servicios públicos', 'subtotal': 30000.0,
    'porcentaje_sobre_total': 100.0,
    'items': [{'descripcion': 'Edenor período 07/2026', 'monto': 30000.0,
               'proveedor_nombre': 'Edenor SA', 'proveedor_cuit': '30-65511620-2',
               'comprobante_tipo': 'LSP A', 'comprobante_numero': '0014-23144929',
               'fecha_pago': '2026-07-23', 'coeficiente': 'A'}],
}]
PRORRATEO = [{
    'unidad_id': 'uf-1', 'unidades_funcionales': {'numero': '1A', 'vecino_nombre': 'RODRIGUEZ'},
    'saldo_anterior': 0, 'pago_realizado': 0, 'saldo_pendiente': 0, 'interes_mora': 0,
    'porcentaje_a': 100.0, 'expensa_a': 30000.0, 'porcentaje_b': 0, 'expensa_b': 0,
    'porcentaje_c': 0, 'adicional_ordinaria': 0, 'porcentaje_e': 0, 'expensa_e': 0,
    'gastos_particulares': 0, 'uso_amenities': 0, 'descuentos': 0, 'redondeo': 0,
    'total_unidad': 30000.0, 'total_segundo_vto': 30900.0,
}]


@pytest.fixture
def pdf():
    return construir_pdf(LIQ, CON, ADM, RUBROS, PRORRATEO)


def test_genera_un_pdf_de_verdad(pdf):
    assert pdf[:5] == b'%PDF-'
    assert len(pdf) > 2000


@pytest.mark.parametrize('bloque', [
    'MIS EXPENSAS',
    'Estado de cuentas y prorrateo',
    'Resumen de movimientos bancarios',
    'Estado patrimonial',
    'Subtotales por coeficiente',
    'Datos para el pago',
])
def test_estan_los_bloques_obligatorios(pdf, bloque):
    assert bloque in _texto(pdf)


@pytest.mark.parametrize('cita', ['Art. 10 inc. i', 'Art. 10 inc. c'])
def test_cita_la_ley_941(pdf, cita):
    """Los cuatro sistemas la imprimen al lado de cada cuadro."""
    assert cita in _texto(pdf)


def test_el_encabezado_identifica_al_consorcio_y_al_administrador(pdf):
    t = _texto(pdf)
    for dato in ('Pacheco 2876', '30-71250333-1', '85693',
                 'Diego Martin', 'RPA 10.455', '2026-09-10'):
        assert dato in t, dato


def test_el_gasto_lleva_proveedor_cuit_y_comprobante(pdf):
    """Es lo que la Ley 941 obliga a rendir y el resumen viejo no mostraba."""
    t = _texto(pdf)
    for dato in ('Edenor SA', '30-65511620-2', 'LSP A', '0014-23144929', '2026-07-23'):
        assert dato in t, dato


def test_la_tabla_trae_las_dos_columnas_de_vencimiento(pdf):
    t = _texto(pdf)
    assert '1er vto.' in t and '2do vto.' in t


def test_declara_la_tasa_y_el_recargo(pdf):
    """Octopus y Consorcio Abierto los ponen en el encabezado de la tabla."""
    t = _texto(pdf)
    assert 'Tasa de inter' in t and 'Recargo 2' in t


def test_solo_muestra_los_coeficientes_que_el_edificio_usa(pdf):
    """Imprimir A, B, C y E cuando sólo se usa A llena la hoja de ceros."""
    t = _texto(pdf)
    assert '% A' in t
    assert '% E' not in t


def test_con_dos_coeficientes_aparecen_los_dos():
    pr = [dict(PRORRATEO[0], porcentaje_e=100.0, expensa_e=5000.0)]
    t = _texto(construir_pdf(LIQ, CON, ADM, RUBROS, pr))
    assert '% A' in t and '% E' in t


def test_la_complementaria_lo_dice(pdf):
    liq = dict(LIQ, numero_revision=2)
    t = _texto(construir_pdf(liq, CON, ADM, RUBROS, PRORRATEO))
    assert 'complementaria' in t.lower()
    assert 'no reemplaza' in t.lower()


# ── Los formateadores ─────────────────────────────────────────────────────────

def test_formato_de_pesos_argentino():
    assert pesos(1234567.89).replace(' ', ' ') == '$ 1.234.567,89'
    assert pesos(-200).replace(' ', ' ') == '-$ 200,00'
    assert pesos(None).replace(' ', ' ') == '$ 0,00'


def test_el_importe_no_se_puede_partir():
    """El espacio entre el signo y el número es duro: si no, la columna
    angosta del prorrateo cortaba "$ 268.750,01" en dos líneas."""
    assert ' ' not in pesos(268750.01)
    assert ' ' in pesos(268750.01)


def test_periodo_en_castellano():
    assert periodo_largo('2026-08') == 'Agosto 2026'
    assert periodo_largo('cualquier cosa') == 'cualquier cosa'
