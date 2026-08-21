# Admin mobile v2 — cajón, cierre guiado y carga de gasto en dos pasos

**Fecha:** 2026-08-16
**Estado:** aprobado por el usuario sobre el prototipo
**Prototipo aprobado:** `docs/mockups/admin-mobile-v2.html`
**Antecedente:** `docs/superpowers/specs/2026-07-30-admin-mobile-design.md` (v1, implementado y en `main`)

---

## 1. Problema

El v1 cerró los tres defectos que se propuso cerrar: el panel es alcanzable en un teléfono, el botón atrás funciona y el prorrateo de 14 columnas se lee. Pero el diagnóstico del usuario sobre el resultado fue:

> "los iconos son muy chicos, me gustaría que el menú sea desplegable, los iconos más user friendly, que sea más parecido a utilizar un iOS que a una página web" · "está bien pero se siente de escritorio".

Cuatro problemas concretos, medibles en el código actual:

| # | Problema | Evidencia |
|---|---|---|
| 1 | **Seis de las diez secciones viven escondidas** | `NIDDO_MOBILE_CONFIG.tabOf` en `admin_dashboard.html` manda `liquidaciones, proveedores, amenities, balance, mensajeria, config` a la hoja de "Más" |
| 2 | **Íconos por debajo del umbral cómodo** | `.bottom-btn .ic` mide 25px y la etiqueta `.63rem` en `niddo-mobile.css`; los íconos de botón usan `.ic-sm` = **16px** |
| 3 | **El consorcio es un filtro repetido, no un contexto** | Cinco `<select>` distintos para lo mismo: `filter-gastos-consorcio`, `filter-cobros-consorcio`, `filter-mora-consorcio`, `filter-liq-consorcio`, `auto-consorcio` |
| 4 | **Emitir expensas no tiene hilo conductor** | `Liquidaciones → + Nueva → detalle → 4 tabs internos (Rubros/Prorrateo/Envíos/Config) → Enviar`, y en ningún momento la app dice en qué punto del mes estás |

Y en la carga de gasto, el camino rápido cruza pasos que no necesita: la cámara llama a `ndGastoConFoto()`, que abre `modal-auto-extract`, donde todavía hay que elegir consorcio, apretar "Extraer datos" y revisar una tabla de 6 columnas dentro de un `overflow-x:auto`.

## 2. Alcance

**Entra:**
- `templates/admin_dashboard.html`: cajón, tab bar de 4, contexto de consorcio, sección de cierre de mes, confirmación de gasto, carga manual.
- `static/css/niddo-mobile.css` y `static/js/niddo-mobile.js`: el cajón y el tamaño de íconos son primitivos compartidos.
- `templates/vecino_dashboard.html`: sólo verificación de regresión. **No se le agrega cajón.**

**No entra:**
- Escritorio de admin: queda idéntico. Todo el CSS nuevo vive dentro de `@media(max-width:900px)` y el JS sale temprano.
- `proveedor_dashboard.html`, `login.html`, `index.html` (sub-proyecto 3).
- PWA, offline, notificaciones push.
- Backend: no se toca ningún endpoint ni el esquema. El cierre de mes guiado reordena llamadas que ya existen.

## 3. Regla transversal

**Lo que se pueda dejar igual que la versión del vecino, queda igual.** Es una instrucción explícita del usuario. En la práctica:

- Los primitivos existentes (sheet arrastrable, fila de lista, título grande colapsable, snackbar, push con back-swipe, safe areas) **se reusan sin modificar**.
- Lo que cambia en el primitivo compartido cambia **para los dos** dashboards. El tamaño de ícono es el único caso: sube en `niddo-mobile.css`, así que el vecino lo hereda y los dos siguen siendo el mismo sistema.
- Lo nuevo que sólo usa admin (cajón, stepper, teclado numérico) se agrega al archivo compartido pero **sólo se activa si el template lo declara** en su configuración. El vecino no lo declara y no lo ve.

## 4. Arquitectura de información

### 4.1 Tab bar: de 5 a 4

| Antes (v1) | Ahora (v2) |
|---|---|
| Hoy · Cobros · Gastos · Edificios · **Más** | Hoy · Gastos · Cobros · Edificios |

"Más" desaparece como tab. Su contenido pasa al cajón, que ya no es una hoja de 6 ítems sino el índice completo.

### 4.2 El cajón

Se abre con ☰ (arriba a la izquierda) o deslizando desde el borde izquierdo. Empuja con `transform`, no tapa. Se cierra arrastrando hacia la izquierda o tocando el scrim.

| Grupo | Ítems |
|---|---|
| Operación | Hoy · Gastos · Cobros · Cierre de mes · Liquidaciones |
| Padrón | Edificios · Proveedores · Amenities |
| Sistema | Balance · Mensajería · Configuración · Mi perfil |
| (pie fijo) | Cerrar sesión |

Arriba del índice, el consorcio activo como tarjeta tocable.

**Limitación aceptada:** con filas de 46px, doce entradas más encabezado y pie no entran en 812px. Quedan ~63px abajo del pliegue — "Mi perfil" asoma y hay que scrollear un toque. Se prefiere eso a recortar el índice.

### 4.3 El consorcio como contexto global

Los cinco `<select>` de consorcio se reemplazan, **en mobile**, por un contexto único que vive en el cajón y en el botón derecho del app bar. En escritorio los `<select>` siguen exactamente como están.

La implementación es deliberadamente conservadora: el contexto **escribe en los `<select>` existentes** y dispara su `change`. No se reescriben `loadGastos()`, `loadCobros()`, `loadMora()` ni `loadLiquidaciones()` — siguen leyendo de su propio `<select>`, que ahora está oculto en mobile y sincronizado. Es la opción que menos superficie toca y la que no puede romper el escritorio.

### 4.4 Cierre de mes

Sección nueva `sec-cierre`, con cuatro pasos en pantalla completa:

1. **Gastos del período** — lo cargado, el total por rubro, y cargar un gasto sin salir del flujo.
2. **Prorrateo** — las tarjetas plegables del v1, sin cambios, más el encabezado de control (total, suma %A, suma %C, UFs en mora).
3. **Vencimientos** — 1er vto, 2do vto, % de recargo, y los switches de publicación. Son los campos de `tab-liq-config-liq`.
4. **Enviar** — a cuántos vecinos, por qué canal, previsualizar uno, enviar. Es `modal-enviar`, desplegado en pantalla en vez de modal.

El botón atrás retrocede de paso antes de salir de la sección. `Liquidaciones` conserva el listado histórico y gana arriba una tarjeta del período en curso que entra al cierre.

**Los cuatro pasos son vistas del mismo estado, no un wizard con estado propio.** No se guarda "en qué paso está" en el servidor: el paso se deriva de la liquidación (¿existe? ¿tiene prorrateo calculado? ¿tiene vencimientos? ¿tiene envíos?). Así, salir y volver cae siempre donde corresponde sin persistir nada nuevo.

### 4.5 Cargar gasto

| Camino | Entrada | Pasos |
|---|---|---|
| Rápido | Botón de cámara en Gastos | Foto → tarjeta de confirmación → Guardar |
| Lote | "Varias facturas" | Fotos → confirmar de a una, con contador *n de N* |
| Manual | "Carga manual" | Teclado numérico → categoría → proveedor |

El paso de elegir modo **se mantiene** (pedido explícito), como hoja de tres opciones al tocar "+ Nuevo gasto". El botón de cámara lo saltea.

La tarjeta de confirmación reemplaza, **sólo en mobile**, la tabla `tbl-auto-results`. Consume el mismo array que hoy llena esa tabla y escribe en la misma estructura que lee `confirmBatchExtract()`. La tabla sigue existiendo para escritorio.

El consorcio no se pregunta: sale del contexto global (§4.3).

## 5. Íconos

| Qué | Antes | Ahora |
|---|---|---|
| Ícono de tab bar | 25px | **28px** |
| Etiqueta de tab bar | .63rem | **.68rem** |
| Alto del tab | 54px | **58px** |
| Fila del cajón | — | 46px, ícono 26px |
| Trazo | 1.8px | **2px** |

El activo del tab pasa a relleno, que el manual de marca ya pide ("line-style by default, filled only for active state") y hoy sólo se cumple a medias.

Estos cambios están en `niddo-mobile.css`, así que **el vecino los hereda**. Es intencional: los dos dashboards son el mismo sistema.

## 6. Arquitectura técnica

Mismo principio que v1: **aditivo y reversible**. No se reescriben los 184 KB de `admin_dashboard.html`.

### 6.1 El cajón es un primitivo opcional de la fundación

`niddo-mobile.js` gana `buildDrawer()`, que sólo corre si el template declara `drawer` en su configuración:

```js
window.NIDDO_MOBILE_CONFIG = {
    /* ... lo que ya había ... */
    drawer: {
        contextSelectors: ['filter-gastos-consorcio', 'filter-cobros-consorcio',
                           'filter-mora-consorcio', 'filter-liq-consorcio', 'auto-consorcio'],
        groups: [ { label: 'Operación', items: [ /* ... */ ] }, /* ... */ ]
    }
};
```

El vecino no lo declara, así que para él no existe. La hoja de "Más" se mantiene en el código para el vecino, que la sigue usando.

### 6.2 El botón izquierdo del app bar es dual

☰ en la raíz, ← dentro de una sub-pantalla. Dentro del cierre, ← retrocede de paso antes de salir. Es un solo botón con el ícono intercambiado, no dos botones.

### 6.3 El gesto de borde tiene dos dueños

Con sub-pantalla abierta, deslizar desde el borde izquierdo es "atrás" — eso ya existe. Sin sub-pantalla, abre el cajón. La condición es la misma bandera que ya usa el back-swipe, así que no hay ambigüedad ni conflicto de listeners.

### 6.4 El historial

El cierre de mes es una sección más (`sec-cierre`), así que entra en el `hashchange` que ya existe. El paso dentro del cierre **no** genera entrada de historial: el ← lo maneja el botón. Es deliberado — cuatro pasos empujando historial haría que salir del cierre requiera cuatro toques de atrás.

## 7. Orden de implementación

Cada paso es un commit atómico y deja la app funcionando.

1. **Íconos y tab bar de 4.** Toca la fundación compartida → se verifica el vecino antes de seguir.
2. **El cajón**, con el índice completo y el gesto de borde. *Cierra el problema #1.*
3. **Contexto de consorcio** sincronizando los cinco `<select>`. *Cierra el problema #3.*
4. **Sección de cierre de mes**, los 4 pasos, reusando el prorrateo del v1. *Cierra el problema #4.*
5. **Confirmación de gasto** con foto y lote.
6. **Carga manual** con teclado numérico.
7. **Barrido final** y repaso de criterios.

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| **Romper el vecino, que está en producción**, al tocar íconos y agregar el cajón a la fundación | El paso 1 es exclusivamente eso, con verificación del vecino antes de seguir. El cajón es opt-in por configuración |
| El contexto de consorcio desincroniza los cinco `<select>` y una pantalla muestra datos de otro edificio | El contexto escribe en los `<select>` y dispara `change` — no hay segunda fuente de verdad. Se verifica cambiando de consorcio y recorriendo las cuatro pantallas |
| Los cuatro pasos del cierre y el modal de liquidación existente se pisan | Los pasos leen y escriben los mismos campos que `guardarConfigLiq()` y `modal-enviar`. No se duplica lógica de guardado |
| El gesto de borde abre el cajón cuando el usuario quería volver atrás | La bandera de sub-pantalla decide; es exclusiva, no hay solapamiento |
| Sin tests, una regresión pasa desapercibida | Verificación manual por paso. Limitación real del repo que este trabajo no resuelve |

## 9. Verificación

- **Viewports:** 360×740, 390×844, 412×892 y **1440×900** (regresión de escritorio, obligatoria en cada paso).
- **Referencia visual:** `docs/mockups/admin-mobile-v2.html`.
- **Regresión del vecino:** obligatoria en el paso 1 y en el barrido final.

## 10. Criterios de éxito

1. Las 11 secciones son alcanzables desde el cajón sin pasar por una hoja de "Más".
2. Los íconos de tab bar miden 28px y ningún elemento interactivo mide menos de 44px.
3. Cambiar de consorcio desde el cajón cambia lo que muestran Gastos, Cobros, Morosidad y Liquidaciones, sin tocar ningún `<select>`.
4. Emitir las expensas del mes se hace recorriendo cuatro pasos con barra de progreso, y salir y volver cae en el paso que corresponde.
5. Se puede cargar un gasto con foto en dos pasos: foto y confirmar.
6. Se pueden cargar varias facturas seguidas, confirmando de a una con contador.
7. Se puede cargar un gasto sin comprobante con el teclado numérico.
8. **El escritorio de admin a 1440px es indistinguible del actual.**
9. **El dashboard del vecino sigue funcionando igual**, salvo los íconos, que crecen a propósito.
