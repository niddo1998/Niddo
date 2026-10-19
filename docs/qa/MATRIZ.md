# Matriz de flujos

Qué recorre el QA exploratorio. Cada corrida toma 2–3 flujos empezando por el
de «último recorrido» más viejo, y actualiza la fecha. Los flujos con 🔒 tocan
plata o permisos: se recorren al menos una vez por semana.

Cobertura E2E: ✅ automatizado · ◐ solo que la pantalla abre sin errores · — nada todavía.

## Administrador

| Flujo | E2E | Último recorrido |
|---|---|---|
| Login, dashboard y navegación por secciones | ◐ | — |
| Alta y edición de consorcio | — | — |
| Carga de UF (individual y masiva desde Excel) | — | — |
| Alta de vecino / asociación de vecino a UF | — | — |
| Carga de gastos (individual, masiva, recurrentes) | — | — |
| 🔒 Generación de liquidación (prorrateo m², ambientes, partes iguales, %) | — | 2026-10-19 |
| 🔒 PDF de liquidación: montos, totales, datos bancarios | — | 2026-10-19 |
| 🔒 Cobros: registrar pago, mora, segundo vencimiento | — | — |
| Export de cobros a Excel | — | — |
| Comunicados y mensajes | — | — |
| Amenities y reservas | — | — |
| Configuración (datos bancarios, Mercado Pago sandbox) | — | — |
| Mobile: navegación inferior y cada pestaña | ◐ | — |

## Vecino

| Flujo | E2E | Último recorrido |
|---|---|---|
| Login, dashboard y navegación por secciones | ◐ | — |
| 🔒 Ver expensa actual, deuda y medios de pago | — | — |
| Descargar liquidación | — | — |
| Reclamos: crear y seguir | — | — |
| Reservas de amenities | — | — |
| Mensajes con la administración | — | — |
| Perfil | — | — |
| 🔒 No ve datos de otro consorcio / otra UF | — | 2026-10-19 |
| Mobile | ◐ | — |

## Superadmin

| Flujo | E2E | Último recorrido |
|---|---|---|
| 🔒 Acceso al panel (y 404 para admin común) | ✅ | — |
| 🔒 Aprobar / rechazar administradores | — | — |
| 🔒 Impersonación de solo lectura | — | — |
| Mapas del producto | — | — |

## Visitante

| Flujo | E2E | Último recorrido |
|---|---|---|
| Landing, «Empezar demo», legales | — | — |
| 🔒 Liquidación pública por link | — | — |
| Admin pendiente → formulario de solicitud | ✅ | — |

## Procesos automáticos

| Flujo | E2E | Último recorrido |
|---|---|---|
| Cron diario: vencimientos y mora (`/api/cron/diario`) | — | — |
| Cron horario: recordatorios de reservas | — | — |
