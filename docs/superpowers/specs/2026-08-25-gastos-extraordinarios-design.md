# Gastos extraordinarios: flag, plan de cuotas y cobro al propietario

**Fecha:** 2026-08-25
**Estado:** aprobado

## El problema

Niddo no distingue un gasto ordinario de uno extraordinario. Todo gasto cargado
entra al mismo prorrateo y se le cobra al mismo destinatario, que es el único
contacto que tiene la UF.

Eso está mal por dos motivos distintos:

1. **Legal.** La expensa extraordinaria la paga el propietario, no el inquilino
   (Ley 27.551, art. 9). Hoy Niddo no tiene forma de decirlo, ni en el número ni
   en la boleta.
2. **Operativo.** Una obra se cobra en cuotas a lo largo de varios meses. Hoy el
   admin tiene que cargar tres gastos a mano y acordarse cada mes.

Y como pasa seguido en este repo, el molde está construido y vacío:

- `liquidacion_prorrateo.extraordinaria` existe desde v7 y **se escribe siempre
  en 0** (`app.py`, `_generar_prorrateo`).
- `liquidacion_items.es_cuota` / `cuota_actual` / `cuota_total` existen desde v7,
  el resumen del vecino ya dibuja una sección **"Obras en curso"** leyéndolos
  (`app.py`, `_generar_resumen_html`), y **nadie los escribe nunca**.
- El mapa de producto (`superadmin_mapa_categorias.html`) lista "Gestionar gastos
  extraordinarios" con sus tres ítems en gris.

## Qué se construye

1. Un gasto puede declararse **extraordinario**, con o sin plan de cuotas.
2. El plan de cuotas genera solo la cuota de cada mes, y es editable: si una
   cuota cambia, las siguientes se recalculan sobre el saldo.
3. El prorrateo separa la extraordinaria y la boleta muestra **dos totales**:
   el del inquilino y el del propietario.
4. La UF puede tener un email de propietario, opcional, que recibe copia de la
   boleta cuando el período trae extraordinarias.

## Decisiones tomadas

| Decisión | Resuelto |
|---|---|
| A quién se le cobra | **Una boleta, dos totales.** No se emite un documento aparte para el dueño. Es lo que hacen SIPAC y Consorcio Abierto, y no exige tener cargados los datos del propietario para que la función sirva. |
| Origen del gasto | **Flag + plan de cuotas en el gasto.** No hay entidad "obra" ni derrama: no se separa lo recaudado de lo gastado. Cubre el caso típico (llegó la factura, la cobro en N cuotas). |
| La deuda | **Un cobro por UF, deuda única.** `cobros` no se toca. El deudor frente al consorcio es siempre el propietario; el inquilino no tiene obligación directa. Mora, intereses y recargo del 2° vencimiento siguen operando sobre el total, sin cambios. |
| Aviso al propietario | **Email opcional por UF.** Cargado, recibe copia. Vacío, todo se comporta como hoy. No se usa `vecinos_unidades.rol` para segmentar: ese rol lo declara el vecino en su onboarding, no el admin. |
| Comportamiento de las cuotas | **Cuota fija, editable por período.** `total / N`, y el admin puede editar una cuota puntual; las siguientes se recalculan sobre el saldo. Sin índices de ajuste (ICL/IPC): el admin decide y Niddo obedece. |
| Coeficiente de reparto | El que declara el gasto (A/B/C/E), igual que un ordinario. No hay lógica de reparto nueva. |
| Qué es extraordinario | **Lo decide el admin, tildando.** Sin default por categoría: si un gasto es de conservación o de mejora lo define la asamblea, no el software. |

### Riesgos aceptados

**El saldo anterior y el interés de mora quedan del lado del propietario.** Están
dentro de `total_unidad` y por lo tanto fuera del "Total inquilino". Si la deuda
vieja era de expensas ordinarias impagas por el inquilino, se le muestra al dueño.
La alternativa —imputar cada pago a ordinaria y extraordinaria por separado— es
código de imputación que no se justifica todavía.

**El rubro 11 pierde la categoría del gasto.** Una reparación extraordinaria de
ascensor deja de figurar bajo "Abonos de servicios"; queda la descripción. Se
acepta a cambio de que la rendición agrupe bien y el PDF salga sin código de
agrupación nuevo.

### Fuera de alcance

- **Fondo de reserva / `saldo_superfondo`.** Conceptualmente cercano, feature
  aparte, ya está en el roadmap por su cuenta.
- **Traspaso de cuotas al vender la UF.** Si una unidad cambia de dueño a mitad
  de un plan, Niddo le sigue cobrando a la UF. Es correcto: la deuda es de la
  unidad.

## Arquitectura

### Modelo de datos (schema v19)

En `gastos`:

| Columna | Tipo | Para qué |
|---|---|---|
| `extraordinario` | `BOOLEAN NOT NULL DEFAULT false` | El flag. Nace en `false`: nada cambia hasta que alguien lo tilde. |
| `plan_monto_total` | `NUMERIC(14,2)` | Solo en la plantilla del plan: el total aprobado de la obra. |
| `cuotas_total` | `SMALLINT` | `NULL` = se cobra entero en el mes. |
| `cuota_numero` | `SMALLINT` | 1 en la plantilla, 2..N en los hijos. |

En `unidades_funcionales`: `propietario_nombre TEXT`, `propietario_email TEXT`,
ambos opcionales.

En `liquidacion_items`: `extraordinario BOOLEAN DEFAULT false`. Se congela al
emitir, igual que `coeficiente` y `unidad_id`: recategorizar un gasto el mes que
viene no puede mover una liquidación ya emitida. `es_cuota`, `cuota_actual` y
`cuota_total` ya existen y pasan a escribirse.

`cobros` y `liquidacion_prorrateo` **no cambian**. La columna `extraordinaria` de
v7 por fin se llena.

### El plan de cuotas reusa el mecanismo de recurrentes

`gasto_origen_id`, `periodo_generado`, `dia_carga` y el índice único que impide
duplicar existen desde v12. `periodos_pendientes()` ya resuelve meses cortos,
años bisiestos y atrasos de varios períodos, y está testeado.

La única modificación a `recurrentes.py` es un parámetro **`max_ocurrencias`**,
para que un plan de 3 cuotas pare en la 3 en vez de generar para siempre.

Igual que hoy con los recurrentes, **la plantilla es la cuota 1**: se liquida como
cualquier gasto, y las cuotas 2..N nacen después.

`recurrente` y `extraordinario` son **mutuamente excluyentes**, y el form lo
impide. Tildar los dos generaría hijos por dos caminos distintos sobre el mismo
registro. Un gasto extraordinario **sin** plan (`cuotas_total` nulo o 1) no genera
nada y lleva `cuota_numero` en `NULL`.

### Bug de herencia que hay que arreglar acá

`_CAMPOS_HEREDADOS` (`app.py`) **no incluye `coeficiente`**. Un gasto recurrente
con coeficiente C genera hijos con coeficiente A, en silencio, y se reparten mal
desde el segundo mes. Como el generador de cuotas se apoya en el mismo mecanismo,
sin arreglarlo las cuotas 2..N de una obra heredarían el mismo error: la obra se
repartiría por un coeficiente que no es el suyo.

Se agrega `coeficiente` a `_CAMPOS_HEREDADOS`, junto con `extraordinario`. El
arreglo corrige de paso los recurrentes ya existentes de aquí en más; no reescribe
hijos ya generados ni liquidaciones ya emitidas.

### Módulo nuevo: `cuotas.py`

Matemática pura, sin base de datos, testeable sin mocks — misma filosofía que
`recurrentes.py`, y por el mismo motivo: es donde se concentra el riesgo.

```
cuota_n = (plan_monto_total − Σ cuotas 1..n-1) / (cuotas_total − (n−1))
```

Si el admin edita la cuota 4 porque la obra se encareció, las 5 y 6 se recalculan
solas sobre lo que falta. **La última cuota se lleva el resto exacto**, con el
mismo criterio de centavos que ya usa `_repartir()`: la suma de las N cuotas da el
total aprobado, siempre.

### Cálculo del prorrateo

`_egresos_por_alcance()` hoy devuelve dos baldes (por coeficiente / particulares).
Pasa a devolver **tres**: agrega extraordinarios por coeficiente. El reparto usa
los mismos pesos y el mismo `_repartir()`.

De ahí sale `liquidacion_prorrateo.extraordinaria`.

**Los dos totales:**

- `total_unidad` **no cambia de significado**: todo lo que se le debe al consorcio
  por esa UF. Es el "Total propietario".
- El "Total inquilino" es `total_unidad − extraordinaria`, **derivado, no
  guardado**. No lleva columna porque es resta exacta entre dos valores ya
  guardados: no hay redondeo que pueda hacer discrepar el PDF del mail.

Los extraordinarios van a un **rubro 11, "Gastos extraordinarios"**, en vez de al
rubro de su categoría. `liquidacion_items.extraordinario` es la fuente de verdad
para el cálculo; el rubro 11 es lo que hace que el PDF y la rendición agrupen sin
código nuevo. `RUBRO_A_CATEGORIA_SIMPLE` suma `11: 'Extraordinarias'`.

## Pantallas

### Carga del gasto (`admin_dashboard.html`, fila de "Gasto recurrente")

Un segundo check, **"Gasto extraordinario"**, que despliega *monto total de la
obra* y *cantidad de cuotas*. Cuotas en 1 o vacío = entra entero en el mes.

Debajo, una línea calculada en vivo que dice lo que va a pasar: *"3 cuotas de
$300.000 — se cobran a los propietarios en 2026-08, 09 y 10"*. Sin eso,
"extraordinario" es una palabra y no una consecuencia visible.

### Lista de gastos y selector de liquidación

La columna que muestra el badge `recurrente`/`automático` suma `extraordinario` y
`cuota 2/3`. Filtro *Ordinarios / Extraordinarios / Todos*.

En el selector de "Nueva liquidación", los extraordinarios van **agrupados aparte
con su subtotal**: es la última pantalla antes de emitir, y es donde el admin
tiene que ver de un vistazo cuánto de esta liquidación se le cobra solo a los
dueños.

### Prorrateo del admin (tabla y cards mobile)

La columna `extraordinaria` aparece al lado de `adicional_ordinaria`. La card
mobile suma la línea, y el total se parte en **`Total inquilino`** y
**`Total unidad`**.

Cuando no hay extraordinarias en el período, la columna y la línea **no se
muestran**: un edificio que nunca hace obras no debería ver una columna de ceros
para siempre.

### La UF

Debajo de "Nombre / Email del vecino", **"Nombre / Email del propietario"**,
opcionales, aclarando que solo hacen falta si la unidad está alquilada. Van
también a la plantilla de carga masiva y al export, para que un edificio de 60
unidades no se cargue a mano.

### La boleta (`_generar_resumen_html`)

El bloque de extraordinarias va **después** del desglose por categoría, con su
propio encabezado y el detalle de cada obra con su cuota
(*"Impermeabilización de terraza — cuota 2 de 3"*). Abajo, los dos totales y una
frase explícita:

> Las expensas extraordinarias están a cargo del propietario (Ley 27.551, art. 9).

Esa frase importa más que el número: es lo que hace que el inquilino que recibe la
boleta entienda por qué hay dos totales sin llamar a la administración.

La sección **"Obras en curso"**, que ya existe en el resumen y nunca se dibujó, se
enciende sola: `es_cuota` por fin se escribe.

### El PDF (`liquidacion_pdf.py`)

El rubro 11 sale como cualquier otro rubro — `_tabla_rubro()` no cambia.
`_tabla_prorrateo()` suma la columna, condicionada igual que las de coeficiente en
`_coeficientes_en_uso()`: si nadie la usa, no ocupa ancho. En un documento
apaisado de doce columnas, eso no es cosmética.

### El envío (`api_liquidacion_enviar`)

Cuando la UF tiene `extraordinaria > 0` **y** `propietario_email` cargado, se manda
una segunda copia a esa dirección, con su propia fila en `resumen_envios` (así el
panel de envíos fallidos la cuenta igual que a las demás). El asunto del mail al
dueño menciona la extraordinaria; el del inquilino, no.

Si `propietario_email` es igual a `vecino_email`, se manda una sola vez.

### El vecino (card "Expensa Actual")

Cuando el período trae extraordinaria, debajo del total va una línea: *"incluye $X
de expensas extraordinarias"*. El `cobro` sigue siendo uno solo; el dato sale del
prorrateo del período.

Es la parte más recortable del alcance si hace falta una primera entrega más chica.

## Tests

| Archivo | Qué cubre |
|---|---|
| `tests/test_cuotas.py` (nuevo) | Que N cuotas sumen exactamente el total; que editar la cuota 4 recalcule 5 y 6; que la última se lleve el resto; que un plan de 1 cuota sea el gasto entero. Sin base de datos. |
| `tests/test_prorrateo.py` | Que la extraordinaria se reparta por el coeficiente del gasto; que `total_unidad − extraordinaria` dé el total del inquilino; **que una liquidación sin extraordinarios dé exactamente los mismos números que hoy**. |
| `tests/test_generacion.py` | Que el plan pare en la cuota N y no genere la N+1; que un gasto extraordinario sin plan no genere hijos; que el hijo herede `coeficiente` y `extraordinario` de la plantilla. |
| `tests/test_pdf_liquidacion.py` | Que la columna aparezca solo cuando hay extraordinarias. |

## Compatibilidad

Todas las columnas nacen con default y todas las pantallas condicionan lo nuevo a
que haya extraordinarias en el período. Un consorcio que nunca tilde el check ve y
paga exactamente lo mismo que antes, y sus liquidaciones ya emitidas dan los
mismos números.
