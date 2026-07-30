# Rediseño mobile del dashboard del vecino

**Fecha:** 2026-07-30
**Estado:** aprobado el diseño visual (prototipo), pendiente de aprobación el spec
**Prototipo de referencia:** `docs/mockups/vecino-mobile.html`

---

## 1. Problema

El sitio no tiene un lenguaje mobile. Cada template resuelve —o no resuelve— el teléfono por su cuenta:

| Template | Media queries | Estado en un teléfono |
|---|---|---|
| `vecino_dashboard.html` | 1 (`max-width:900px`) | Sidebar oculto, bottom-nav de 5 ítems. Nada más. |
| `admin_dashboard.html` | **0** | Sidebar fijo de 220px + tablas de 7 columnas. Zoom horizontal. |
| `proveedor_dashboard.html` | 1 | Mínimo. |
| `login.html` | 0 | — |

Además hay tres defectos concretos, no cosméticos:

1. **Tres secciones son inalcanzables en el teléfono.** `Reporte de Gastos`, `Votaciones` y `Archivos` sólo se abren desde `.app-sidebar`, que a ≤900px está en `display:none`, y no figuran en la `bottom-nav`. Votaciones es el peor caso: tiene deadline y badge de "nuevo".
2. **El botón atrás del sistema saca de la app.** Las secciones son divs con `display:none` y no hay manejo de `history`, así que el gesto de volver —el más usado en Android— cierra la sesión de navegación en vez de retroceder una pantalla.
3. **No se contemplan las safe areas.** Sin `viewport-fit=cover` ni `env(safe-area-inset-*)`, la `bottom-nav` de 60px queda parcialmente bajo el home indicator en iPhone.

Los patrones dominantes son de escritorio: `.table` de hasta 7 columnas, `.drawer` lateral de 460px, `.modal-box` centrado de 540px, y estados que dependen de `:hover`, que en un teléfono no existe.

## 2. Alcance

Este spec cubre **el sub-proyecto 1 de 3**: la fundación del lenguaje mobile más su aplicación al dashboard del vecino.

**Entra:**
- `static/css/niddo-mobile.css` y `static/js/niddo-mobile.js` nuevos.
- `templates/vecino_dashboard.html`: nueva IA de tabs, generadores de fila de las 3 tablas, meta viewport.

**No entra (sub-proyectos posteriores):**
- Sub-proyecto 2: `admin_dashboard.html`.
- Sub-proyecto 3: `proveedor_dashboard.html`, `login.html`, `index.html`.

**Explícitamente fuera (YAGNI):**
- PWA — decisión tomada: "chrome nativo, sin instalar". Sin manifest, sin service worker.
- Offline, cacheo, notificaciones push.
- Cualquier cambio al layout de escritorio.
- Reescritura de los dashboards o adopción de un framework.
- Infraestructura de tests. El repo no tiene ninguna hoy; introducirla es un trabajo aparte con su propia justificación.

## 3. Arquitectura de información

Las 9 secciones actuales se reorganizan en 5 tabs, ordenadas por frecuencia real de uso:

| Tab | Contiene | Notas |
|---|---|---|
| **Inicio** | Resumen + lo urgente | Saldo, votación abierta, reclamo con respuesta, últimos avisos. Accesos directos a informar pago y nuevo reclamo. |
| **Expensas** | Cuenta corriente · **Reporte de Gastos** (sub-pantalla) | Los dos responden la misma pregunta desde lados opuestos: *"¿en qué se va mi plata?"* |
| **Comunidad** | **Comunicados** (por defecto) · **Votaciones** · **Reclamos** | Segmented control. Los badges de votaciones y reclamos suben al ícono del tab. |
| **Reservas** | Amenities | Queda sola: es una tarea con flujo propio. |
| **Más** | Archivos · Perfil · Cerrar sesión | Lista agrupada tipo ajustes. |

Las tres huérfanas quedan resueltas: Gastos → sub-pantalla de Expensas · Votaciones → segmento de Comunidad · Archivos → Más.

**Riesgo asumido:** Reclamos queda a un nivel de profundidad pese a ser de alta intención cuando ocurre. Se mitiga con el acceso directo "Nuevo reclamo" en Inicio y el badge en el tab.

## 4. El lenguaje mobile

Un solo sistema de diseño, no adaptativo por plataforma. Lo único que varía por SO son los safe insets. Los tokens de color y tipografía salen de `niddo-brand.css` (Ruta Barrio) sin agregar ninguno nuevo.

| Primitivo | Qué reemplaza | Comportamiento |
|---|---|---|
| **Tab bar** | `.bottom-nav` | 5 tabs, 54px + safe inset. Ícono de línea que **se rellena** en activo, según el manual de marca. Badges numéricos. |
| **Top app bar** | `.app-header` fijo | Título grande que colapsa al scrollear en un título compacto centrado sobre fondo esmerilado. Botón atrás en sub-pantallas. |
| **Bottom sheet** | `.drawer` (460px lateral) y `.modal-box` (540px centrado) | Sube desde abajo, grabber, arrastrable para cerrar, scrim. |
| **Fila de lista** | `<table class="table">` | Ícono + título + subtítulo con estado + monto + chevron. El detalle completo va a una sheet. |
| **Navegación push** | — | Sub-pantallas entran desde la derecha, botón atrás y back-swipe desde el borde izquierdo. |
| **Segmented control** | Botones de filtro sueltos | Thumb deslizante. Agrupa las tres secciones de Comunidad. |
| **Chips de filtro** | `<select>` de filtro | Scroll horizontal, un toque. |
| **Snackbar** | `.toast` (anclado abajo a la derecha) | Ancho completo, por encima de la tab bar. |

Reglas transversales:
- Targets táctiles de 44px mínimo.
- Inputs a `font-size:16px` — por debajo de eso iOS hace zoom al enfocar.
- `touch-action: manipulation` y `-webkit-tap-highlight-color: transparent`.
- Estados `:active` con escala en todo lo tocable. Ningún estado depende de `:hover`.
- `100dvh` en vez de `100vh` — la barra de URL de Safari rompe `100vh`.
- `viewport-fit=cover` + `env(safe-area-inset-*)`.

## 5. Arquitectura técnica

**Principio: aditivo y reversible.** Los 103KB del template no se reescriben.

### 5.1 Archivos nuevos

- **`static/css/niddo-mobile.css`** — todo el lenguaje, íntegramente dentro de `@media (max-width:900px)`. Se carga después de `niddo-brand.css`.
- **`static/js/niddo-mobile.js`** — sheets, navegación push, colapso de título, segmented, snackbar, back-swipe, historial. Se autoinicializa y sale temprano si el viewport es de escritorio.

### 5.2 Cómo se integra sin reescribir el markup

| Pieza | Técnica | Toca el HTML |
|---|---|---|
| Drawers y modales → sheets | Sólo CSS: se reposiciona el DOM existente (`align-items:flex-end`, `translateY(100%)`, radio arriba). El JS agrega el grabber y el arrastre. | No |
| Tab bar | Generada por JS; llama al `showSection()` existente. | Se reemplaza la `.bottom-nav` actual |
| Segmented de Comunidad | Inyectado por JS; alterna entre las 3 `.section` hermanas manteniendo el tab activo. | No |
| Título grande y push nav | JS, leyendo la sección activa. | No |
| Tablas → listas | El generador de filas emite la fila-tarjeta además del `<tr>`; CSS muestra una u otra. | Sí, 3 funciones |
| Botón atrás del SO | `showSection()` se envuelve con `history.pushState` + `popstate`. | No |

**La única duplicación aceptada** es el markup de las filas de tabla: una función, un objeto de datos, dos formas de markup. Se elige sobre la alternativa —transformar el DOM con `MutationObserver` después de cada carga de datos— porque esa es frágil y depende del timing de la respuesta de la API. La duplicación es de forma, no de lógica; no hay dos fuentes de verdad.

### 5.3 Breakpoint

Uno solo, en **900px** — el que ya existe. Consecuencia asumida: las tablets en vertical (744–820px) reciben la interfaz de teléfono. Se prefiere eso a introducir un tercer estado de layout.

El manejo de historial se activa según el viewport al cargar la página. Caso borde aceptado: redimensionar la ventana cruzando los 900px sin recargar deja el historial desincronizado. En un teléfono no ocurre.

## 6. Orden de implementación

1. **Fundación CSS/JS** — los dos archivos nuevos, cargados por el template, sin cambios de comportamiento todavía. Verificable: el sitio se ve igual que hoy.
2. **Meta viewport y safe areas** — `viewport-fit=cover` y los insets.
3. **Tab bar y nueva IA** — las 5 tabs, el agrupador Comunidad, y con eso las tres secciones huérfanas dejan de serlo. *Acá se cierra el defecto #1.*
4. **Historial y botón atrás** — *cierra el defecto #2.*
5. **Sheets** — conversión CSS de los 3 overlays del vecino (`drawer-pago`, `drawer-reclamo`, `modal-cond`), más grabber y arrastre.
6. **Título grande y navegación push** — incluye Reporte de Gastos como sub-pantalla de Expensas.
7. **Tablas → listas** — las 3 tablas, una por vez.
8. **Barrido de detalle** — targets, tamaños de input, `:active`, snackbars, chips.

Cada paso es un commit atómico y deja la app funcionando.

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Romper el escritorio | Todo el CSS vive dentro de `@media (max-width:900px)`; el JS sale temprano. Revertir = borrar dos líneas del `<head>`. |
| El arrastre de las sheets pelea con el scroll interno | El arrastre se ata sólo al grabber y al header, nunca al cuerpo scrolleable. |
| Los generadores de fila se desincronizan entre escritorio y mobile | Ambos salen del mismo objeto en la misma función. Un cambio de campo toca un solo lugar. |
| `history.pushState` interfiere con Auth0 | El wrapper sólo maneja cambios de sección; las rutas de `/auth/*` son navegaciones reales del navegador y no pasan por él. |
| Sin tests, una regresión pasa desapercibida | Verificación manual explícita por paso (sección 8). Es una limitación real del repo, no algo que este trabajo resuelva. |

## 8. Verificación

No hay framework de test en el repo y este trabajo no introduce uno. La verificación es manual y por paso:

- **Viewports:** 390×844 (iPhone 14), 412×892 (Pixel 7), 360×740 (Android chico), 820×1180 (iPad vertical) y 1440×900 (escritorio, para confirmar que no cambió nada).
- **Referencia visual:** `docs/mockups/vecino-mobile.html` lado a lado.
- **Por paso:** consola sin errores, y el recorrido completo — abrir cada tab, entrar y volver de cada sub-pantalla, abrir y arrastrar cada sheet, enviar un reclamo, informar un pago, votar, reservar.
- **Regresión de escritorio:** a 1440px el dashboard tiene que ser idéntico al de hoy, verificado sección por sección.

## 9. Criterios de éxito

1. Las 9 secciones son alcanzables desde el teléfono. Ninguna queda huérfana.
2. El botón atrás del sistema retrocede de pantalla en vez de salir de la app.
3. Ninguna pantalla requiere zoom ni scroll horizontal a 360px de ancho.
4. La tab bar y las sheets respetan las safe areas en iPhone y en Android.
5. Ningún elemento interactivo mide menos de 44px, ni depende de `:hover`.
6. Las 3 tablas se leen como listas, con el detalle completo en sheet.
7. El escritorio a 1440px es indistinguible del actual.
8. Los primitivos quedan en archivos compartidos, listos para que admin los reuse en el sub-proyecto 2.
