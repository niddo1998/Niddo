# Carga automática de múltiples facturas

Fecha: 2026-07-27

## Problema

A principio de mes el administrador paga varias facturas de servicios (luz, gas, agua)
y necesita cargarlas como gastos. Hoy la carga automática con IA acepta un solo
comprobante por vez, así que hay que repetir el flujo completo —abrir el modal,
subir, esperar el análisis, confirmar— una vez por factura.

## Objetivo

Permitir subir varios comprobantes de una sola vez y que cada uno se convierta en su
propio gasto, con su comprobante adjunto, tras un único paso de revisión.

## Alcance

Se modifica únicamente `templates/admin_dashboard.html`.

El backend no cambia. Se reutilizan dos endpoints existentes y ya probados:

- `POST /api/gastos/extract` — analiza **un** comprobante y devuelve los campos extraídos.
- `POST /api/gastos` — crea **un** gasto; acepta `multipart/form-data` con el archivo
  en el campo `comprobante`.

## Flujo

1. **Subida.** La zona de arrastre acepta varios archivos, por drag & drop o por
   selección múltiple. Los archivos elegidos se listan y se puede quitar cualquiera
   antes de analizar. Máximo 10 archivos por lote; máximo 10 MB por archivo.
2. **Consorcio.** Un único select que aplica a todo el lote.
3. **Análisis.** El navegador llama a `/api/gastos/extract` una vez por archivo, en
   secuencia, mostrando el progreso: `Analizando 2 de 3 — metrogas.pdf`.
4. **Revisión.** Una tabla editable con una fila por factura.
5. **Carga.** Un botón crea todos los gastos tildados: una llamada a `POST /api/gastos`
   por fila, en secuencia, cada una con su comprobante adjunto.

## Por qué el análisis va en el navegador y no en el backend

Cada llamada a Groq tarda alrededor de 4,5 segundos (medido con archivos reales de
prueba). Procesar el lote entero dentro de una sola petición al backend sumaría esos
tiempos: tres facturas darían unos 14 segundos, por encima del límite de 10 segundos
que Vercel aplica por defecto a las funciones en el plan Hobby. Al superarse el límite
se perdería el lote completo.

Haciendo una petición por archivo desde el navegador, cada una dura lo que tarda una
sola factura y nunca se acerca al límite. Además el progreso es visible y una falla
queda aislada en su archivo.

El límite de 30 peticiones por minuto del plan gratuito de Groq deja margen de sobra
para un lote de 10.

## Tabla de revisión

Columnas:

| ✓ incluir | Descripción | Monto | Categoría | Fecha | Vencimiento | Pagado |
|---|---|---|---|---|---|---|

Se incluye **Pagado** porque el caso de uso es cargar facturas ya pagadas; sin esa
columna habría que editar cada gasto después de crearlo. Arranca destildado: que la
factura esté pagada es una decisión del administrador, no un dato que la IA infiera.

Las filas cuya extracción salió bien arrancan tildadas en la columna **✓ incluir**.

Los campos que la tabla no cubre —proveedor, método de pago, recurrente y frecuencia—
se guardan con su valor por defecto y se editan después desde el botón de editar del
gasto. Las notas que extrae la IA se guardan, pero no se muestran en la tabla por
espacio.

El modal pasa a usar la clase `wide` para acomodar las columnas.

### Camino único

Un lote de un solo archivo también va a la tabla, con una única fila. Esto reemplaza
el comportamiento anterior, en el que una sola factura abría el formulario de gasto
completo prellenado.

La contrapartida, aceptada explícitamente: al cargar se pierde el acceso directo a los
campos que la tabla no cubre. Se recupera editando el gasto ya creado. A cambio hay un
solo camino de código en lugar de dos.

## Manejo de errores

**Falla la extracción de un archivo.** Su fila se muestra en rojo con el motivo
devuelto por el backend, con el checkbox destildado para que no se cargue, y con un
botón que reintenta solo ese archivo. El resto del lote no se ve afectado.

**Falla el guardado de un gasto.** Los gastos que sí se crearon quedan creados. Al
terminar se informa cuáles fallaron y por qué. No se revierte nada: un gasto creado es
un dato válido aunque otro del mismo lote haya fallado.

**Validación previa.** Una fila sin monto no se puede cargar, porque `POST /api/gastos`
exige `consorcio_id` y `monto`. Esas filas se marcan y se excluyen.

## Estado en el frontend

Las dos variables actuales de un solo elemento se vuelven colecciones:

- `autoFileSelected` (un `File`) pasa a `autoFilesSelected` (arreglo de `File`).
- `autoExtractedData` (un objeto) pasa a `autoExtractedResults` (arreglo de objetos).

Cada entrada de `autoExtractedResults` mantiene el archivo que la originó, los campos
extraídos, si está tildada para cargar, y el error si la extracción falló. Esa
asociación es la que permite adjuntar el comprobante correcto a cada gasto.

## Verificación

El repositorio no tiene framework de tests.

La validación es un script local que ejercita el flujo contra la API real de Groq con
tres archivos de prueba —el mismo método usado para validar la migración a Groq— y
después una prueba manual en producción con facturas reales.
