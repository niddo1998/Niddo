# Gastos recurrentes: generación automática y confirmación de tarifa

**Fecha:** 2026-08-16
**Estado:** aprobado

## El problema

Hoy `gastos.recurrente` y `gastos.frecuencia` no hacen nada. El admin tilda "Gasto
recurrente", elige "mensual", y lo único que pasa es que se guarda el flag: aparece
un badge azul en la tabla y una columna "Sí" en el export CSV. Nada genera el gasto
del mes siguiente.

Hay un solo `insert` a `gastos` en toda la app (`api_gastos_create`), y es el del
formulario manual. No hay cron en ningún lado: `vercel.json` no tiene bloque
`crons`, no hay APScheduler ni Celery en `requirements.txt`, y no hay `pg_cron` en
los schemas.

El resultado es peor que no tener la función: la UI le promete al administrador una
automatización que no existe, así que un gasto fijo que se olvidó de cargar a mano
queda afuera de la liquidación sin que nadie lo note.

## Qué se construye

1. El gasto recurrente pasa a ser una **plantilla** con un día del mes elegido.
2. Cada período, la app genera el gasto de ese mes copiando el monto anterior.
3. Al entrar a Gastos, un cartel único lista las tarifas sin confirmar y permite
   ajustarlas ahí mismo. Confirmada una tarifa, no vuelve a aparecer.

## Decisiones tomadas

| Decisión | Resuelto |
|---|---|
| Qué apaga el cartel | Confirmar, haya cambiado el monto o no. Dos botones ("Sigue igual" / "Actualicé") y ambos marcan la tarifa como confirmada. Si solo la apagara un cambio de monto, un gasto con tarifa estable pediría confirmación para siempre. |
| Monto del gasto generado | Copia el del período anterior, marcado como sin confirmar. |
| Formato del cartel | Un modal único con todos los pendientes agrupados por consorcio, monto editable fila por fila. |
| Liquidaciones | **Sin cambios de flujo.** Los gastos siguen viniendo tildados por defecto. Solo se agrega un badge visual "sin confirmar". |
| Día 29–31 en meses cortos | Se recorta al último día del mes. |
| Atraso de varios períodos | Se generan todos los faltantes, no solo el último. |
| Frecuencia | Se respeta el campo existente: mensual, bimestral, trimestral, anual. |

### Riesgo aceptado

El selector de "Nueva liquidación" (`api_liquidacion_gastos_disponibles`) toma todos
los gastos cuya `fecha_gasto` cae en el período y trae tildados los que todavía no se
enviaron. Un gasto generado con el monto del mes anterior entra tildado a la
liquidación. Si el administrador liquida sin pasar antes por Gastos, les cobra a los
vecinos la tarifa vieja.

Se planteó destildarlos o bloquear la liquidación; el dueño del producto decidió no
tocar ese flujo. Queda registrado como riesgo asumido. La mitigación acordada es el
badge visual, que no cambia ningún comportamiento.

## Arquitectura

### Modelo de datos (schema v12)

Cuatro columnas en `gastos`:

| Columna | Tipo | Para qué |
|---|---|---|
| `dia_carga` | SMALLINT | Día del mes elegido, 1–31. Solo en plantillas. |
| `gasto_origen_id` | UUID → `gastos(id)` | Enlaza el hijo con su plantilla. NULL en plantillas y en gastos comunes. |
| `periodo_generado` | TEXT | `YYYY-MM` del hijo. NULL en plantillas. |
| `tarifa_confirmada` | BOOLEAN DEFAULT true | Los hijos nacen en `false`. |

Índice único sobre `(gasto_origen_id, periodo_generado)`. Es la garantía real de
idempotencia: dos pestañas abiertas a la vez chocan contra la base, no contra un
`if` en Python.

Los hijos nacen con `recurrente = false`, así que no generan nietos.

**Migración de lo existente:** los gastos que hoy tienen `recurrente = true` no
tienen día. Se completa `dia_carga` con el día de su propia `fecha_gasto`, para no
obligar a cargarlo a mano uno por uno.

### Generación

Función `generar_recurrentes(admin_id)` en `app.py`, idempotente, invocada desde:

- `GET /api/gastos` — al entrar a la pantalla de Gastos
- `GET /api/liquidacion/gastos-disponibles` — para que el gasto exista aunque el
  admin vaya directo a liquidar

Para cada plantilla activa (`recurrente = true`, `dia_carga IS NOT NULL`), calcula
los períodos vencidos desde `fecha_gasto` hasta hoy según `frecuencia`, y crea los
que falten copiando descripción, categoría, `proveedor_id`, `unidad_id` y `monto`,
con `pagado = false`, `fecha_pago = NULL` y `tarifa_confirmada = false`.

Se eligió generación perezosa antes que un cron de Vercel o `pg_cron`. El único
escenario donde un cron gana es "nadie entró a la app en tres meses y quiero los
gastos igual", que en administración de consorcios no ocurre: si nadie entró,
tampoco hay liquidación que emitir. A cambio, la generación perezosa no suma
endpoints públicos, secretos de cron ni extensiones de Postgres — esto último
importa especialmente ahora, con la migración de región pendiente, porque
`supabase db dump` no incluye el schema `cron`.

### Cartel de confirmación

`GET /api/gastos/tarifas-pendientes` devuelve los hijos con
`tarifa_confirmada = false`, agrupados por consorcio.

`POST /api/gastos/confirmar-tarifas` recibe `[{id, monto}]`, actualiza los montos
que cambiaron y marca todos como `tarifa_confirmada = true`.

En el frontend, `admin_dashboard.html` abre el modal al entrar a la sección Gastos
si hay pendientes.

## Manejo de errores

- La generación nunca debe romper la pantalla de Gastos: si falla, se loguea y la
  request sigue. Un gasto que no se generó se genera en la próxima entrada.
- Violación del índice único (carrera entre dos requests) se ignora en silencio: el
  gasto ya existe, que es el resultado buscado.
- Falta del schema v12 se reporta con el mismo patrón que ya usa `_falta_schema_v9`.

## Testing

El repo no tiene tests hoy. Se agrega `pytest` en un `requirements-dev.txt` aparte,
para no engordar el build de Vercel, y se testea la parte que concentra el riesgo:
el cálculo puro de períodos, sin base de datos.

- Mes cortado: día 31 en febrero cae en el 28 (y en el 29 en año bisiesto).
- Atraso de varios períodos: genera todos los faltantes.
- Frecuencias bimestral, trimestral y anual.
- Un período ya generado no se vuelve a generar.

La lógica que toca Supabase queda cubierta por el índice único, no por tests.

## Fuera de alcance

- Cambiar el flujo de liquidaciones.
- Fecha de fin de la recurrencia: se repite hasta que se destilde "recurrente" en
  la plantilla.
- Notificaciones por email de tarifas pendientes.
