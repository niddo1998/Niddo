"""La plantilla de carga masiva de consorcios y UF.

El desplegable de "consorcio" en la hoja Unidades era una lista fija con los
edificios que ya existían: el que cargabas en la hoja Consorcios del mismo
archivo no aparecía. Ahora apunta a un nombre definido sobre una hoja oculta
que Excel recalcula. Estos tests miran la estructura; que las fórmulas den lo
que tienen que dar se probó calculándolas con datos (ver el commit).
"""

import app


def _plantilla(nombres):
    return app.build_carga_masiva_template([{'nombre': n, 'direccion': ''} for n in nombres])


def _validacion_consorcio(wb):
    dvs = wb['Unidades'].data_validations.dataValidation
    return next(dv for dv in dvs if 'A2' in str(dv.sqref))


def test_el_desplegable_de_unidades_apunta_a_la_lista_viva():
    dv = _validacion_consorcio(_plantilla(['Torre A']))
    assert dv.formula1 == app.NOMBRE_LISTA_CONSORCIOS
    assert 'A2:A1000' in str(dv.sqref)


def test_el_desplegable_existe_aunque_no_haya_consorcios_cargados():
    """Antes, sin consorcios existentes no había desplegable: justo el caso del
    administrador nuevo que carga todo por primera vez desde la planilla."""
    dv = _validacion_consorcio(_plantilla([]))
    assert dv.formula1 == app.NOMBRE_LISTA_CONSORCIOS


def test_la_lista_se_arma_en_una_hoja_oculta():
    wb = _plantilla(['Torre A', 'Torre B'])
    ws = wb['Listas']
    assert ws.sheet_state == 'hidden'
    assert [ws['A1'].value, ws['A2'].value] == ['Torre A', 'Torre B']
    # Debajo de los existentes, los que se escriban en la hoja Consorcios.
    assert 'Consorcios!' in ws['A3'].value


def test_la_lista_mira_la_hoja_consorcios_y_descarta_el_ejemplo():
    formula = _plantilla(['Torre A'])['Listas']['B1'].value
    assert 'Consorcios!$A$2' in formula
    assert app.MARCA_FILA_EJEMPLO in formula


def test_el_rango_se_estira_hasta_el_ultimo_nombre():
    wb = _plantilla(['Torre A'])
    nombre = wb.defined_names[app.NOMBRE_LISTA_CONSORCIOS]
    assert nombre.attr_text.startswith('OFFSET(Listas!$A$1')


def test_muchos_consorcios_no_se_cortan():
    """La lista literal de antes se cortaba a 255 caracteres."""
    nombres = [f'Edificio número {i} de la calle larga' for i in range(30)]
    ws = _plantilla(nombres)['Listas']
    assert [ws.cell(row=i + 1, column=1).value for i in range(30)] == nombres


def test_excel_calcula_las_formulas_al_abrir():
    assert _plantilla([]).calculation.fullCalcOnLoad is True
