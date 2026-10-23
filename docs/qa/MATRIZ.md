# Matriz de flujos

Qué recorre el QA exploratorio. Cada corrida toma 2–3 flujos empezando por el
de «último recorrido» más viejo, y actualiza la fecha. Los flujos con 🔒 tocan
plata o permisos: se recorren al menos una vez por semana.

Cobertura E2E: ✅ automatizado · ◐ solo que la pantalla abre sin errores · — nada todavía.

## Administrador

| Flujo | E2E | Último recorrido |
|---|---|---|
| Login, dashboard y navegación por secciones | ◐ | — |
| Alta y edición de consorcio | — | 2026-10-22 |
| Carga de UF (individual y masiva desde Excel) | — | 2026-10-22 |
| Alta de vecino / asociación de vecino a UF | — | — |
| Carga de gastos (individual, masiva, recurrentes) | — | 2026-10-23 |
| 🔒 Generación de liquidación (prorrateo m², ambientes, partes iguales, %) | — | 2026-10-19 |
| 🔒 PDF de liquidación: montos, totales, datos bancarios | — | 2026-10-19 |
| 🔒 Cobros: registrar pago, mora, segundo vencimiento | — | 2026-10-20 |
| Export de cobros a Excel | — | 2026-10-20 |
| Comunicados y mensajes | — | — |
| Amenities y reservas | — | 2026-10-23 |
| Configuración (datos bancarios, Mercado Pago sandbox) | — | 2026-10-22 |
| Mobile: navegación inferior y cada pestaña | ◐ | — |

## Vecino

| Flujo | E2E | Último recorrido |
|---|---|---|
| Login, dashboard y navegación por secciones | ◐ | — |
| 🔒 Ver expensa actual, deuda y medios de pago | — | — |
| Descargar liquidación | — | — |
| Reclamos: crear y seguir | — | — |
| Reservas de amenities | — | 2026-10-23 |
| Mensajes con la administración | — | 2026-10-21 |
| Perfil | — | — |
| 🔒 No ve datos de otro consorcio / otra UF | — | 2026-10-22 |
| Mobile | ◐ | — |

## Superadmin

| Flujo | E2E | Último recorrido |
|---|---|---|
| 🔒 Acceso al panel (y 404 para admin común) | ✅ | — |
| 🔒 Aprobar / rechazar administradores | — | 2026-10-21 |
| 🔒 Impersonación de solo lectura | — | 2026-10-21 |
| Mapas del producto | — | — |

## Visitante

| Flujo | E2E | Último recorrido |
|---|---|---|
| Landing, «Empezar demo», legales | — | 2026-10-20 |
| 🔒 Liquidación pública por link | — | 2026-10-21 |
| Admin pendiente → formulario de solicitud | ✅ | — |

## Procesos automáticos

| Flujo | E2E | Último recorrido |
|---|---|---|
| Cron diario: vencimientos y mora (`/api/cron/diario`) | — | — |
| Cron horario: recordatorios de reservas | — | — |
