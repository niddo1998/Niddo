# Carga de gastos simplificada

Fecha: 2026-08-28
Rama de respaldo del estado anterior: `respaldo/gastos-completo`

## Problema

El formulario de gasto pide 17 datos repartidos en seis filas. Cargar una
factura de luz —lo que un administrador hace veinte veces por mes— obliga a
recorrer campos que casi nunca se llenan: proveedor, vencimiento, método de
pago, tipo y número de comprobante. La sección de Proveedores existe pero no
está desarrollada: es una tabla que nadie llena y un desplegable que siempre
dice "Sin proveedor".

## Qué se saca

Del modal de gasto se van seis campos:

| Campo | id |
|---|---|
| Proveedor | `m-gasto-proveedor` |
| Fecha de vencimiento | `m-gasto-vto` |
| Método de pago | `m-gasto-metodo` |
| Fecha de pago | `m-gasto-fecha-pago` |
| Tipo de comprobante | `m-gasto-comp-tipo` |
| N° de comprobante | `m-gasto-comp-numero` |

El formulario queda en cuatro bloques: consorcio; alcance y descripción;
categoría, monto y fecha; y el pie con coeficiente, pagado, recurrencia,
notas y adjunto.

## Qué cambia de comportamiento

**"Marcado como pagado" viene tildado.** Un gasto se carga cuando ya se pagó;
ese es el caso normal y ahora es el default. El que no esté pagado se destilda.
Sin esto, el bloque de impagos del panel de inicio (`app.py`, resumen del
dashboard) crecería para siempre porque nadie tendría dónde marcar nada.

La recurrencia no cambia: sigue destildada, y el coeficiente sigue en A.

## Qué se saca de Proveedores

- Ítem del menú, sección, tabla y modal de alta en el panel del admin.
- Las cinco rutas `/api/proveedores`.
- La columna Proveedor de la tabla de gastos, la línea "Sin proveedor" de la
  tarjeta mobile y los chips de proveedor del alta rápida.
- La columna del Excel de carga masiva y su hoja "Proveedores existentes".
- La tabla de gastos del vecino pierde Proveedor y Vencimiento.
- `templates/proveedor_dashboard.html`, plantilla sin ruta que la sirva.

## Los tres caminos de carga quedan alineados

Formulario, Excel y extracción con IA piden lo mismo. La tabla de revisión de
la IA pierde la columna de vencimiento y deja de guardar proveedor y
comprobante; el Excel queda con consorcio, fecha, descripción, monto,
categoría, unidad, coeficiente, pagado, recurrencia y notas.

## Qué no se toca

**La base de datos.** Las columnas `proveedor_id`, `fecha_vencimiento`,
`fecha_pago`, `metodo_pago`, `comprobante_tipo` y `comprobante_numero` siguen
existiendo con lo cargado hasta hoy, igual que la tabla `proveedores`. Volver
a mostrar cualquiera de ellas es descomentar, no migrar.

**La liquidación PDF.** Mantiene sus columnas de proveedor, CUIT y
comprobante: los gastos viejos las muestran, los nuevos salen "—".

## Riesgo asumido

La Ley 941 obliga a rendir el comprobante junto al gasto. Desde este cambio la
liquidación deja de traerlo para los gastos nuevos. Es una decisión tomada a
sabiendas y reversible sin migración, porque el dato sigue teniendo dónde ir.
