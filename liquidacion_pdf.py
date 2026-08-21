"""El PDF de la liquidación, con la estructura que usa el mercado.

Vive aparte de `app.py` por lo mismo que `recurrentes.py`: es largo, es
determinístico y se puede probar sin una base de datos adelante. Se le pasan
diccionarios y devuelve bytes.

La estructura sale de comparar cuatro liquidaciones reales —SIPAC, Octopus,
Expensas Flow y Consorcio Abierto—, que coinciden casi por completo:

    1. Encabezado: consorcio, período, vencimientos, administración
    2. Rubros 1 a 10, cada gasto con proveedor, CUIT, comprobante y fecha
       de pago, subtotal por rubro y subtotales por coeficiente
    3. Resumen de movimientos bancarios      (Ley 941, art. 10 inc. i)
    4. Resumen de ingresos y egresos         (inc. i)
    5. Estado patrimonial                    (inc. c)
    6. Estado de cuentas y prorrateo: la tabla con TODAS las unidades
    7. Datos para el pago

El punto 6 es el que obliga a que sea un documento del consorcio y no de una
unidad: los cuatro mandan la liquidación entera y el vecino busca su fila.
Niddo mandaba un HTML recortado a una unidad, que se lee mejor pero no es lo
que la ley obliga a rendir.
"""

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

# La paleta de la marca, en los valores que ya usa el resumen HTML.
TERRACOTA = colors.HexColor('#C4502B')
TINTA = colors.HexColor('#2A211C')
GRIS = colors.HexColor('#574C42')
CREMA = colors.HexColor('#F6EFE7')
BORDE = colors.HexColor('#E2D6C8')

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

# Los diez rubros, con la cita legal que los cuatro imprimen al lado.
CITA_RUBRO = {
    1: 'Conf. Art. 10 inc. d Ley N° 941',
    2: 'Conf. Art. 10 inc. e y f Ley N° 941',
}


def periodo_largo(periodo):
    """'2026-07' → 'Julio 2026'. Devuelve lo que le den si no puede."""
    try:
        y, m = str(periodo).split('-')[:2]
        return f'{MESES[int(m)]} {y}'
    except Exception:
        return str(periodo or '')


# Espacio duro entre el signo y el número: el importe no se parte nunca en
# dos lineas, por angosta que quede la columna. Sin esto "$ 268.750,01" se
# cortaba despues del signo y la tabla del prorrateo quedaba ilegible.
NBSP = '\u00a0'


def pesos(n):
    """Formato argentino: $ 1.234.567,89, siempre en una sola linea."""
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        return f'${NBSP}0,00'
    entero, dec = f'{abs(v):,.2f}'.split('.')
    entero = entero.replace(',', '.')
    signo = '-' if v < 0 else ''
    return f'{signo}${NBSP}{entero},{dec}'


def porcentaje(n, decimales=3):
    try:
        return f'{float(n or 0):.{decimales}f}'.replace('.', ',')
    except (TypeError, ValueError):
        return '0,000'


def _estilos():
    base = getSampleStyleSheet()
    return {
        'titulo': ParagraphStyle('t', parent=base['Normal'], fontName='Helvetica-Bold',
                                 fontSize=16, leading=20, textColor=TERRACOTA,
                                 spaceAfter=4),
        'sub': ParagraphStyle('s', parent=base['Normal'], fontName='Helvetica',
                              fontSize=9, textColor=GRIS, spaceAfter=1),
        'rubro': ParagraphStyle('r', parent=base['Normal'], fontName='Helvetica-Bold',
                                fontSize=10, textColor=colors.white, spaceAfter=0),
        'seccion': ParagraphStyle('se', parent=base['Normal'], fontName='Helvetica-Bold',
                                  fontSize=11, textColor=TERRACOTA,
                                  spaceBefore=10, spaceAfter=4),
        'cita': ParagraphStyle('c', parent=base['Normal'], fontName='Helvetica-Oblique',
                               fontSize=7, textColor=GRIS, spaceAfter=3),
        'celda': ParagraphStyle('ce', parent=base['Normal'], fontName='Helvetica',
                                fontSize=7, leading=8.5, textColor=TINTA),
        'celda_r': ParagraphStyle('cr', parent=base['Normal'], fontName='Helvetica',
                                  fontSize=7, leading=8.5, alignment=TA_RIGHT),
        # La tabla del prorrateo es la más densa del documento: doce columnas
        # más dos por coeficiente. En cuerpo 7 los importes se parten al medio,
        # así que va en 6, que es el que usan SIPAC y Consorcio Abierto.
        'mini': ParagraphStyle('m', parent=base['Normal'], fontName='Helvetica',
                               fontSize=6, leading=7.2, textColor=TINTA),
        'mini_r': ParagraphStyle('mr', parent=base['Normal'], fontName='Helvetica',
                                 fontSize=6, leading=7.2, alignment=TA_RIGHT),
        'pie': ParagraphStyle('p', parent=base['Normal'], fontName='Helvetica',
                              fontSize=6.5, textColor=GRIS, alignment=TA_CENTER),
    }


def _encabezado(liq, consorcio, admin, E):
    """Consorcio, período y vencimientos a la izquierda; administración a la derecha.

    Los datos de la administración —CUIT, matrícula RPA/RPAC, domicilio,
    teléfono— los imprimen los cuatro y son obligatorios: es a quién reclamarle.
    """
    izq = [
        Paragraph(f"<b>{consorcio.get('nombre', '')}</b>", E['sub']),
        Paragraph(consorcio.get('direccion', '') or '', E['sub']),
    ]
    if consorcio.get('cuit'):
        izq.append(Paragraph(f"CUIT: {consorcio['cuit']}", E['sub']))
    if consorcio.get('clave_suterh'):
        izq.append(Paragraph(f"Clave SUTERH: {consorcio['clave_suterh']}", E['sub']))
    izq.append(Spacer(1, 3))
    if liq.get('fecha_vencimiento_1'):
        izq.append(Paragraph(f"<b>1° Vto:</b> {liq['fecha_vencimiento_1']}", E['sub']))
    if liq.get('fecha_vencimiento_2'):
        izq.append(Paragraph(f"<b>2° Vto:</b> {liq['fecha_vencimiento_2']}", E['sub']))

    der = [Paragraph('<b>Administración</b>', E['sub'])]
    for etiqueta, clave in (('', 'nombre'), ('CUIT: ', 'cuit'), ('Mat.: ', 'matricula'),
                            ('', 'direccion'), ('', 'email'), ('Tel: ', 'telefono')):
        if admin.get(clave):
            der.append(Paragraph(f"{etiqueta}{admin[clave]}", E['sub']))

    t = Table([[izq, der]], colWidths=[10 * cm, 7.5 * cm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [
        Paragraph('MIS EXPENSAS', E['titulo']),
        Paragraph(f"Liquidación de {periodo_largo(liq.get('periodo'))}", E['sub']),
        Spacer(1, 8), t, Spacer(1, 10),
    ]


def _tabla_rubro(rubro, E, ancho):
    """Un rubro con sus gastos, uno por fila.

    Cada gasto lleva proveedor, CUIT, tipo y número de comprobante, descripción,
    fecha de pago, coeficiente e importe. Es lo que la Ley 941 obliga a rendir
    y lo que Niddo perdía: el resumen mostraba categoría e importe.
    """
    num = rubro.get('numero_rubro', '')
    filas = [[
        Paragraph('<b>Proveedor / CUIT</b>', E['celda']),
        Paragraph('<b>Comprobante</b>', E['celda']),
        Paragraph('<b>Detalle</b>', E['celda']),
        Paragraph('<b>Pago</b>', E['celda']),
        Paragraph('<b>Coef.</b>', E['celda']),
        Paragraph('<b>Importe</b>', E['celda_r']),
    ]]
    for it in rubro.get('items', []):
        prov = it.get('proveedor_nombre') or '—'
        if it.get('proveedor_cuit'):
            prov += f"<br/><font size=6 color='#574C42'>CUIT {it['proveedor_cuit']}</font>"
        comp = ' '.join(x for x in (it.get('comprobante_tipo'),
                                    it.get('comprobante_numero')) if x) or '—'
        detalle = it.get('descripcion') or ''
        if it.get('unidad_id'):
            detalle += " <font size=6 color='#C4502B'>(gasto de una sola UF)</font>"
        filas.append([
            Paragraph(prov, E['celda']),
            Paragraph(comp, E['celda']),
            Paragraph(detalle, E['celda']),
            Paragraph(str(it.get('fecha_pago') or '—'), E['celda']),
            Paragraph(str(it.get('coeficiente') or 'A'), E['celda']),
            Paragraph(pesos(it.get('monto')), E['celda_r']),
        ])

    pct = porcentaje(rubro.get('porcentaje_sobre_total'), 2)
    filas.append([
        Paragraph(f"<b>Subtotal rubro {num}</b> &nbsp;·&nbsp; {pct}% del total",
                  E['celda']), '', '', '', '',
        Paragraph(f"<b>{pesos(rubro.get('subtotal'))}</b>", E['celda_r']),
    ])

    anchos = [ancho * p for p in (0.21, 0.15, 0.31, 0.12, 0.06, 0.15)]
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), CREMA),
        ('BACKGROUND', (0, -1), (-1, -1), CREMA),
        ('SPAN', (0, -1), (4, -1)),
        ('GRID', (0, 0), (-1, -1), 0.25, BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    encabezado = Table(
        [[Paragraph(f"{num}. {rubro.get('nombre', '').upper()}", E['rubro'])]],
        colWidths=[ancho])
    encabezado.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TERRACOTA),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))

    bloque = [Spacer(1, 8), encabezado]
    if num in CITA_RUBRO:
        bloque.append(Paragraph(CITA_RUBRO[num], E['cita']))
    bloque.append(t)
    return bloque


def _cuadro(titulo, filas, E, ancho, cita=None):
    """Los cuadros de dos columnas: concepto a la izquierda, importe a la derecha.

    Sirve para los tres que pide la Ley 941 —movimientos bancarios, ingresos y
    egresos, estado patrimonial—, que los cuatro sistemas imprimen igual.
    """
    datos = []
    for etiqueta, valor, fuerte in filas:
        estilo = 'celda'
        txt = f'<b>{etiqueta}</b>' if fuerte else etiqueta
        val = f'<b>{pesos(valor)}</b>' if fuerte else pesos(valor)
        datos.append([Paragraph(txt, E[estilo]), Paragraph(val, E['celda_r'])])

    t = Table(datos, colWidths=[ancho * 0.7, ancho * 0.3])
    estilos = [
        ('GRID', (0, 0), (-1, -1), 0.25, BORDE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    for i, (_, _, fuerte) in enumerate(filas):
        if fuerte:
            estilos.append(('BACKGROUND', (0, i), (-1, i), CREMA))
    t.setStyle(TableStyle(estilos))

    bloque = [Paragraph(titulo, E['seccion'])]
    if cita:
        bloque.append(Paragraph(cita, E['cita']))
    bloque.append(t)
    return KeepTogether(bloque)


def _tabla_prorrateo(liq, consorcio, prorrateos, coeficientes_usados, E, ancho):
    """Estado de cuentas y prorrateo: todas las unidades, una por fila.

    Es la tabla que hace que esto sea un documento del consorcio y no de una
    unidad. Las columnas de coeficiente se arman según los que el edificio use
    de verdad: imprimir A, B, C y E cuando sólo se usa A llena la hoja de ceros.
    """
    cab = [Paragraph(f'<b>{h}</b>', E['mini']) for h in
           ('UF', 'Propietario', 'Saldo ant.', 'Pago', 'Saldo pend.', 'Int.')]
    for c in coeficientes_usados:
        cab += [Paragraph(f'<b>% {c}</b>', E['mini']),
                Paragraph(f'<b>Expensa {c}</b>', E['mini_r'])]
    cab += [Paragraph('<b>Otros</b>', E['mini_r']),
            Paragraph('<b>Red.</b>', E['mini_r']),
            Paragraph('<b>1er vto.</b>', E['mini_r']),
            Paragraph('<b>2do vto.</b>', E['mini_r'])]

    filas = [cab]
    campo = {'A': ('porcentaje_a', 'expensa_a'), 'B': ('porcentaje_b', 'expensa_b'),
             'C': ('porcentaje_c', 'adicional_ordinaria'), 'E': ('porcentaje_e', 'expensa_e')}

    for pr in prorrateos:
        uf = pr.get('unidades_funcionales') or {}
        otros = round(float(pr.get('gastos_particulares') or 0)
                      + float(pr.get('uso_amenities') or 0)
                      - float(pr.get('descuentos') or 0), 2)
        fila = [
            Paragraph(str(uf.get('numero') or '—'), E['mini']),
            Paragraph(str(uf.get('vecino_nombre') or '—')[:28], E['mini']),
            Paragraph(pesos(pr.get('saldo_anterior')), E['mini_r']),
            Paragraph(pesos(pr.get('pago_realizado')), E['mini_r']),
            Paragraph(pesos(pr.get('saldo_pendiente')), E['mini_r']),
            Paragraph(pesos(pr.get('interes_mora')), E['mini_r']),
        ]
        for c in coeficientes_usados:
            pc, ec = campo[c]
            fila += [Paragraph(porcentaje(pr.get(pc)), E['mini']),
                     Paragraph(pesos(pr.get(ec)), E['mini_r'])]
        fila += [Paragraph(pesos(otros), E['mini_r']),
                 Paragraph(pesos(pr.get('redondeo')), E['mini_r']),
                 Paragraph(f"<b>{pesos(pr.get('total_unidad'))}</b>", E['mini_r']),
                 Paragraph(pesos(pr.get('total_segundo_vto')), E['mini_r'])]
        filas.append(fila)

    # La fila de totales es el control de que el reparto cerró.
    def suma(clave):
        return round(sum(float(p.get(clave) or 0) for p in prorrateos), 2)

    tot = [Paragraph('<b>TOTALES</b>', E['mini']), '',
           Paragraph(f"<b>{pesos(suma('saldo_anterior'))}</b>", E['mini_r']),
           Paragraph(f"<b>{pesos(suma('pago_realizado'))}</b>", E['mini_r']),
           Paragraph(f"<b>{pesos(suma('saldo_pendiente'))}</b>", E['mini_r']),
           Paragraph(f"<b>{pesos(suma('interes_mora'))}</b>", E['mini_r'])]
    for c in coeficientes_usados:
        pc, ec = campo[c]
        tot += [Paragraph(f"<b>{porcentaje(suma(pc), 2)}</b>", E['mini']),
                Paragraph(f"<b>{pesos(suma(ec))}</b>", E['mini_r'])]
    otros_tot = round(suma('gastos_particulares') + suma('uso_amenities') - suma('descuentos'), 2)
    tot += [Paragraph(f'<b>{pesos(otros_tot)}</b>', E['mini_r']),
            Paragraph(f"<b>{pesos(suma('redondeo'))}</b>", E['mini_r']),
            Paragraph(f"<b>{pesos(suma('total_unidad'))}</b>", E['mini_r']),
            Paragraph(f"<b>{pesos(suma('total_segundo_vto'))}</b>", E['mini_r'])]
    filas.append(tot)

    # Los anchos se reparten como proporciones y después se escalan al ancho
    # real: así la tabla ocupa la hoja entera tenga uno o cuatro coeficientes.
    # La de UF entra holgada a propósito — "COCHERA" es un número de unidad
    # tan válido como "1A" y partido en dos se lee mal.
    peso = [0.08, 0.11] + [0.082] * 4 + [0.045, 0.092] * len(coeficientes_usados) + \
           [0.085, 0.06, 0.09, 0.09]
    escala = ancho / sum(peso)
    t = Table(filas, colWidths=[p * escala for p in peso], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TERRACOTA),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), CREMA),
        ('SPAN', (0, -1), (1, -1)),
        ('GRID', (0, 0), (-1, -1), 0.25, BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    for i in range(1, len(filas) - 1, 2):
        t.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FBF8F4'))]))

    tasa = float(consorcio.get('tasa_interes_mora') or 0)
    recargo = float(liq.get('interes_2_vto') or consorcio.get('recargo_segundo_vto') or 0)
    encabezado = [Paragraph('Estado de cuentas y prorrateo', E['seccion'])]
    if tasa or recargo:
        encabezado.append(Paragraph(
            f'Tasa de interés: {porcentaje(tasa)}%  ·  '
            f'Recargo 2° vencimiento: {porcentaje(recargo, 2)}%', E['cita']))
    return encabezado + [t]


def _coeficientes_en_uso(prorrateos):
    """Los coeficientes que este edificio realmente reparte.

    Imprimir A, B, C y E cuando sólo se usa A llena la hoja de ceros y hace
    ilegible la tabla, que ya es la más ancha del documento.
    """
    campo = {'A': 'expensa_a', 'B': 'expensa_b',
             'C': 'adicional_ordinaria', 'E': 'expensa_e'}
    usados = [c for c, f in campo.items()
              if any(abs(float(p.get(f) or 0)) > 0 for p in prorrateos)]
    return usados or ['A']


def _subtotales_por_coeficiente(prorrateos, coeficientes, E, ancho):
    """El bloque que los cuatro imprimen al cierre: cuánto se repartió por cada uno."""
    campo = {'A': 'expensa_a', 'B': 'expensa_b',
             'C': 'adicional_ordinaria', 'E': 'expensa_e'}
    filas = [(f'Coeficiente {c}',
              round(sum(float(p.get(campo[c]) or 0) for p in prorrateos), 2), False)
             for c in coeficientes]
    total = round(sum(f[1] for f in filas), 2)
    filas.append(('TOTAL PRORRATEADO', total, True))
    return _cuadro('Subtotales por coeficiente', filas, E, ancho)


def construir_pdf(liq, consorcio, admin, rubros, prorrateos, banco=None):
    """Arma la liquidación completa y devuelve los bytes del PDF.

    Todo lo que necesita llega por parámetro: no toca la base ni la red, así
    que se puede probar entero sin levantar nada.

    El documento arranca vertical para los rubros y da vuelta la hoja para el
    prorrateo, que con varios coeficientes no entra de otra forma.
    """
    E = _estilos()
    buf = io.BytesIO()

    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                          topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                          title=f"Liquidación {periodo_largo(liq.get('periodo'))} — "
                                f"{consorcio.get('nombre', '')}",
                          author=admin.get('nombre', 'Niddo'))

    ancho_v = doc.width
    ancho_h = landscape(A4)[0] - 3.2 * cm

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont('Helvetica', 6.5)
        canvas.setFillColor(GRIS)
        canvas.drawCentredString(
            documento.pagesize[0] / 2, 0.8 * cm,
            f"{consorcio.get('nombre', '')} · {periodo_largo(liq.get('periodo'))} · "
            f"Página {documento.page} · Generado con Niddo")
        canvas.restoreState()

    doc.addPageTemplates([
        PageTemplate(id='vertical', frames=[Frame(
            doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='v')], onPage=pie),
        PageTemplate(id='horizontal', pagesize=landscape(A4), frames=[Frame(
            1.6 * cm, 1.4 * cm, ancho_h, landscape(A4)[1] - 2.8 * cm, id='h')], onPage=pie),
    ])

    coeficientes = _coeficientes_en_uso(prorrateos)
    story = _encabezado(liq, consorcio, admin, E)

    if int(liq.get('numero_revision') or 1) > 1:
        story.append(_cuadro(
            'Liquidación complementaria',
            [(f"Revisión {liq.get('numero_revision')} del período. Factura únicamente los "
              f"gastos cargados después del primer envío; no reemplaza a la anterior.",
              0, False)], E, ancho_v))

    # ── Rubros ──
    for r in sorted(rubros, key=lambda x: x.get('numero_rubro') or 0):
        story += _tabla_rubro(r, E, ancho_v)

    total_gastos = round(sum(float(r.get('subtotal') or 0) for r in rubros), 2)
    story.append(Spacer(1, 6))
    story.append(_cuadro('Total de gastos del período',
                         [('TOTAL DE GASTOS', total_gastos, True)], E, ancho_v))

    story.append(_subtotales_por_coeficiente(prorrateos, coeficientes, E, ancho_v))

    # ── Los tres cuadros de la Ley 941 ──
    saldo_inicial = float(liq.get('saldo_inicial') or 0)
    ingresos = float(liq.get('total_ingresos') or 0)
    egresos = float(liq.get('total_egresos') or total_gastos)
    saldo_cierre = round(saldo_inicial + ingresos - egresos, 2)

    story.append(_cuadro('Resumen de movimientos bancarios', [
        ('Saldo inicial', saldo_inicial, False),
        ('(+) Ingresos', ingresos, False),
        ('(−) Egresos', -egresos, False),
        ('SALDO AL CIERRE', saldo_cierre, True),
    ], E, ancho_v, cita='Conf. Art. 10 inc. i Ley N° 941'))

    a_cobrar = round(sum(float(p.get('total_unidad') or 0) for p in prorrateos), 2)
    story.append(_cuadro('Estado patrimonial', [
        ('Saldo de disponibilidades al cierre', saldo_cierre, False),
        ('Expensas y otros conceptos a cobrar', a_cobrar, False),
        ('PATRIMONIO NETO AL CIERRE', round(saldo_cierre + a_cobrar, 2), True),
    ], E, ancho_v, cita='Conf. Art. 10 inc. c Ley N° 941'))

    # ── Prorrateo, en horizontal ──
    story.append(NextPageTemplate('horizontal'))
    story.append(PageBreak())
    story += _tabla_prorrateo(liq, consorcio, prorrateos, coeficientes, E, ancho_h)

    banco = banco or consorcio
    datos_pago = [(e, v) for e, v in (
        ('Titular', banco.get('banco_titular') or consorcio.get('nombre', '')),
        ('Banco', banco.get('banco_nombre')),
        ('Cuenta', banco.get('banco_cuenta')),
        ('CBU', banco.get('banco_cbu')),
        ('Alias', banco.get('banco_alias')),
        ('CUIT', banco.get('banco_cuit_pago')),
    ) if v]
    if datos_pago:
        story.append(Paragraph('Datos para el pago', E['seccion']))
        t = Table([[Paragraph(f'<b>{e}</b>', E['celda']), Paragraph(str(v), E['celda'])]
                   for e, v in datos_pago], colWidths=[3 * cm, ancho_h - 3 * cm])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.25, BORDE),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t)

    doc.build(story)
    return buf.getvalue()
