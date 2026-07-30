# Rediseño mobile del vecino — Plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar tarea por tarea. Los pasos usan checkbox (`- [ ]`).

**Goal:** Dar al dashboard del vecino un lenguaje mobile nativo —tab bar, bottom sheets, listas en vez de tablas, navegación push— sin tocar el layout de escritorio.

**Architecture:** Dos archivos nuevos y compartidos (`static/css/niddo-mobile.css`, `static/js/niddo-mobile.js`) que mejoran progresivamente el markup existente. Todo el CSS vive dentro de `@media (max-width:900px)`; el JS sale temprano si el viewport es de escritorio. Revertir todo = borrar dos líneas del `<head>`.

**Tech Stack:** Flask + Jinja2, HTML/CSS/JS sin framework ni build step. Tokens de `static/css/niddo-brand.css` (Ruta Barrio).

**Spec:** `docs/superpowers/specs/2026-07-30-vecino-mobile-design.md`
**Referencia visual:** `docs/mockups/vecino-mobile.html`

## Global Constraints

- **Todo el CSS nuevo va dentro de `@media (max-width:900px)`.** Ni una regla fuera. El escritorio a 1440px tiene que quedar idéntico.
- **Tokens únicamente de `niddo-brand.css`.** No inventar hex. Paleta Ruta Barrio: `--nd-terracota #E8734A`, `--nd-terracota-hondo #C4502B`, `--nd-verde #2F6F5E`, `--nd-amarillo #F2B705`, `--nd-crema #F6EFE7`, `--nd-tinta #2A211C`, `--nd-borde #E2D6C8`.
- **Tipografías:** `Fredoka` para display (`var(--font-d)` si existe, si no `'Fredoka'`), `Nunito Sans` para texto (`var(--font)`).
- **Targets táctiles ≥ 44px.** Inputs con `font-size:16px` mínimo (por debajo, iOS hace zoom al enfocar).
- **Ningún estado nuevo puede depender de `:hover`.** Usar `:active`.
- **No se introduce framework de tests.** La verificación es en navegador, especificada paso a paso.
- **No se toca `admin_dashboard.html`, `proveedor_dashboard.html`, `login.html` ni `index.html`.** Son sub-proyectos posteriores.
- **Voseo argentino** en todo texto visible, sin jerga técnica.
- **Rama:** `feat/mobile-vecino`. Un commit por tarea.
- **⚠ Orden de cascada (descubierto en la Task 2):** el `<style>` inline del template se carga **después** de `niddo-mobile.css`, así que a igual especificidad **gana el inline**. Cuando una regla nueva pise una propiedad que el inline ya declara (`height`, `width`, `position`, `display`…), hay que subir especificidad con un id o una clase extra — nunca con `!important`. Verificar siempre el valor computado, no asumir que la regla se aplicó.

## Cómo verificar (todas las tareas)

El servidor se levanta con:

```bash
cd /Users/santiagodespontin/Niddo/Niddo && python3 app.py
```

Viewports obligatorios en cada verificación:

| Nombre | Medidas | Qué prueba |
|---|---|---|
| Android chico | 360 × 740 | El ancho mínimo real |
| iPhone | 390 × 844 | Safe areas de iOS |
| Pixel | 412 × 892 | Safe areas de Android |
| **Escritorio** | **1440 × 900** | **Que no se rompió nada** |

La verificación de escritorio a 1440px es obligatoria en **todas** las tareas. Si algo cambió ahí, la tarea falló.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `static/css/niddo-mobile.css` (nuevo) | Todo el lenguaje visual mobile. Un solo `@media`. |
| `static/js/niddo-mobile.js` (nuevo) | Comportamientos: sheets, push, colapso de título, segmented, historial. |
| `templates/vecino_dashboard.html` (modificar) | Meta viewport, carga de los dos archivos, tab bar, generadores de fila. |

---

### Task 1: Los dos archivos nuevos, cargados y sin efecto

Crear la base y enchufarla. Al terminar, el sitio se ve **exactamente igual que antes** en todos los viewports. Eso es lo que se verifica: que la infraestructura entra sin cambiar nada.

**Files:**
- Create: `static/css/niddo-mobile.css`
- Create: `static/js/niddo-mobile.js`
- Modify: `templates/vecino_dashboard.html:5` (meta viewport) y `:11` (después del `<link>` de niddo-brand.css)

**Interfaces:**
- Consumes: nada.
- Produces: `window.NiddoMobile` con `{ isMobile(): boolean, BREAKPOINT: 900 }`. Todas las tareas siguientes cuelgan de este objeto.

- [ ] **Step 1: Crear `static/css/niddo-mobile.css`**

```css
/* ==========================================================================
   Niddo — Lenguaje mobile
   Todo lo de este archivo vive dentro del @media. El escritorio no se toca.
   Tokens: niddo-brand.css (Ruta Barrio).
   ========================================================================== */

@media (max-width: 900px) {

  /* Las safe areas del sistema, disponibles como tokens. */
  :root {
    --safe-top:    env(safe-area-inset-top, 0px);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
    --safe-left:   env(safe-area-inset-left, 0px);
    --safe-right:  env(safe-area-inset-right, 0px);
    --tabbar-h: 54px;
  }

  /* Nada depende de :hover en un teléfono, y el tap highlight gris de
     Android/iOS pelea con nuestros propios estados :active. */
  * { -webkit-tap-highlight-color: transparent; }
  button, a, .row, .tab { touch-action: manipulation; }

}
```

- [ ] **Step 2: Crear `static/js/niddo-mobile.js`**

```javascript
/* ==========================================================================
   Niddo — Comportamientos mobile
   Sale temprano en escritorio: en >900px este archivo no hace absolutamente
   nada, así el dashboard de escritorio queda intacto.
   ========================================================================== */
(function () {
  'use strict';

  var BREAKPOINT = 900;

  function isMobile() {
    return window.innerWidth <= BREAKPOINT;
  }

  window.NiddoMobile = {
    BREAKPOINT: BREAKPOINT,
    isMobile: isMobile
  };

  if (!isMobile()) return;

  document.documentElement.classList.add('nd-mobile');
})();
```

- [ ] **Step 3: Cambiar el meta viewport**

En `templates/vecino_dashboard.html` línea 5, reemplazar:

```html
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
```

por:

```html
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
```

`viewport-fit=cover` es lo que hace que `env(safe-area-inset-*)` devuelva valores distintos de cero. Sin esto, las safe areas de la Task 3 no funcionan.

- [ ] **Step 4: Cargar los dos archivos**

En `templates/vecino_dashboard.html`, justo después de la línea 11 (`<link rel="stylesheet" ... niddo-brand.css ...>`), agregar:

```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/niddo-mobile.css') }}">
    <script src="{{ url_for('static', filename='js/niddo-mobile.js') }}" defer></script>
```

El orden importa: `niddo-mobile.css` va **después** de `niddo-brand.css` para poder pisar tokens, y **antes** del `<style>` inline para que el inline siga ganando donde haga falta.

- [ ] **Step 5: Verificar que no cambió nada**

Levantar el servidor, entrar al dashboard del vecino y comprobar:

| Viewport | Qué esperar |
|---|---|
| 1440 × 900 | Idéntico a antes. Sidebar visible, sin bottom-nav. |
| 390 × 844 | Idéntico a antes. Sidebar oculto, bottom-nav de 5 ítems. |

En la consola del navegador:

```javascript
NiddoMobile.isMobile()
```

Esperado: `true` a 390px de ancho, `false` a 1440px.

```javascript
document.documentElement.classList.contains('nd-mobile')
```

Esperado: `true` a 390px (recargando en ese tamaño), `false` a 1440px.

Consola sin errores en ambos tamaños.

- [ ] **Step 6: Commit**

```bash
git add static/css/niddo-mobile.css static/js/niddo-mobile.js templates/vecino_dashboard.html
git commit -m "feat: base del lenguaje mobile, cargada y sin efecto todavía"
```

---

### Task 2: Tab bar de 5 ítems y las tres secciones rescatadas

Cierra el defecto #1 del spec: hoy `gastos`, `votaciones` y `archivos` son **inalcanzables** en el teléfono. Esta tarea es la que más valor entrega de todo el plan.

**Files:**
- Modify: `templates/vecino_dashboard.html:301-307` (la `<nav class="bottom-nav">` actual)
- Modify: `static/css/niddo-mobile.css`
- Modify: `static/js/niddo-mobile.js`

**Interfaces:**
- Consumes: `window.NiddoMobile.isMobile()` de la Task 1. La función global `showSection(name)` que ya existe en el template (línea ~660).
- Produces: `NiddoMobile.setTab(tabId)` y `NiddoMobile.TAB_OF` — un mapa de `nombre de sección → id de tab`, que la Task 4 usa para sincronizar el historial.

- [ ] **Step 1: Reemplazar el markup de la bottom-nav**

En `templates/vecino_dashboard.html`, reemplazar el bloque completo de las líneas 301–307 (desde `<nav class="bottom-nav">` hasta `</nav>`) por:

```html
<nav class="bottom-nav" id="nd-tabbar">
    <button class="bottom-btn active" data-tab="inicio" onclick="showSection('inicio')">
        <span class="bottom-btn-icon"><svg class="ic"><use href="#ic-edificio"></use></svg></span><span>Inicio</span>
    </button>
    <button class="bottom-btn" data-tab="expensas" onclick="showSection('expensas')">
        <span class="bottom-btn-icon"><svg class="ic"><use href="#ic-expensa"></use></svg></span><span>Expensas</span>
    </button>
    <button class="bottom-btn" data-tab="comunidad" onclick="showSection('comunicados')">
        <span class="bottom-btn-icon"><svg class="ic"><use href="#ic-megafono"></use></svg></span><span>Comunidad</span>
        <i class="nd-tab-badge" id="nd-badge-comunidad" style="display:none">0</i>
    </button>
    <button class="bottom-btn" data-tab="reservas" onclick="showSection('reservas')">
        <span class="bottom-btn-icon"><svg class="ic"><use href="#ic-reserva"></use></svg></span><span>Reservas</span>
    </button>
    <button class="bottom-btn" data-tab="mas" onclick="NiddoMobile.openMas()">
        <span class="bottom-btn-icon"><svg class="ic"><use href="#ic-mas"></use></svg></span><span>Más</span>
    </button>
</nav>
```

Nota: se sacan los `id="bnav-*"`, porque `showSection()` los usa para marcar el activo y ahora ese trabajo lo hace `NiddoMobile.setTab()` con `data-tab`. El ícono `#ic-mas` está confirmado en `templates/_icons.html`.

- [ ] **Step 2: Agregar el CSS de la tab bar**

Dentro del `@media` de `static/css/niddo-mobile.css`, antes del `}` de cierre:

```css
  /* ── Tab bar ─────────────────────────────────────────────────────────── */
  .bottom-nav {
    height: auto;
    padding-bottom: var(--safe-bottom);
    background: rgba(255,255,255,.9);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
  }
  .bottom-btn {
    height: var(--tabbar-h);
    min-height: 44px;
    position: relative;
    gap: 3px;
  }
  .bottom-btn span:last-child { font-size: .63rem; font-weight: 700; }
  .bottom-btn .ic { width: 25px; height: 25px; transition: transform .18s cubic-bezier(.34,1.56,.64,1); }
  .bottom-btn:active .ic { transform: scale(.88); }
  .bottom-btn.active .ic { transform: translateY(-1px) scale(1.06); }
  .nd-tab-badge {
    position: absolute; top: 4px; left: calc(50% + 6px);
    min-width: 17px; height: 17px; padding: 0 4px; border-radius: 9px;
    background: var(--nd-terracota-hondo); color: #fff;
    font-size: .6rem; font-weight: 800; font-style: normal;
    display: flex; align-items: center; justify-content: center;
    border: 2px solid #fff;
  }

  /* El main tiene que despejar la tab bar más la safe area. */
  .app-main { padding-bottom: calc(var(--tabbar-h) + var(--safe-bottom) + 16px); }
```

- [ ] **Step 3: Agregar `setTab` y `openMas` al JS**

En `static/js/niddo-mobile.js`, antes del `})();` final:

```javascript
  /* ── Tab bar ─────────────────────────────────────────────────────────── */

  /* Qué tab se ilumina para cada sección. Comunidad agrupa tres secciones;
     Más agrupa las que viven en la hoja. */
  var TAB_OF = {
    inicio: 'inicio',
    expensas: 'expensas',
    gastos: 'expensas',
    comunicados: 'comunidad',
    votaciones: 'comunidad',
    reclamos: 'comunidad',
    reservas: 'reservas',
    archivos: 'mas',
    perfil: 'mas'
  };

  function setTab(tabId) {
    var tabs = document.querySelectorAll('#nd-tabbar .bottom-btn');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle('active', tabs[i].dataset.tab === tabId);
    }
  }

  /* showSection() es global y la definen los templates. La envolvemos para
     que además sincronice el tab activo. */
  function wrapShowSection() {
    var original = window.showSection;
    if (typeof original !== 'function') return;
    window.showSection = function (name) {
      original.apply(this, arguments);
      setTab(TAB_OF[name] || name);
    };
  }

  NiddoMobile.TAB_OF = TAB_OF;
  NiddoMobile.setTab = setTab;
  NiddoMobile.openMas = function () {
    /* La hoja de "Más" llega en la Task 5. Hasta entonces, ir a perfil. */
    window.showSection('perfil');
  };

  document.addEventListener('DOMContentLoaded', function () {
    wrapShowSection();
    setTab('inicio');
  });
```

Importante: `wrapShowSection` corre en `DOMContentLoaded`, después de que el `<script>` inline del template definió `showSection`. El `defer` del `<script>` de la Task 1 garantiza ese orden.

- [ ] **Step 4: Verificar que las tres huérfanas ya se alcanzan**

Con el servidor levantado, a **390 × 844**, en la consola:

```javascript
['gastos','votaciones','archivos'].map(s => { showSection(s); return [s, document.getElementById('section-'+s).classList.contains('active'), document.querySelector('#nd-tabbar .bottom-btn.active').dataset.tab]; })
```

Esperado exactamente:

```
[["gastos", true, "expensas"], ["votaciones", true, "comunidad"], ["archivos", true, "mas"]]
```

Es decir: cada sección se activa, y el tab correcto queda iluminado.

Después, a mano: tocar los 5 tabs y confirmar que cada uno abre su sección y se ilumina. Confirmar que la tab bar no queda tapada por el home indicator (a 390×844 con safe areas simuladas, tiene que sobrar espacio abajo).

A **1440 × 900**: la tab bar sigue oculta y el sidebar funciona igual que antes. Consola sin errores.

- [ ] **Step 5: Commit**

```bash
git add static/css/niddo-mobile.css static/js/niddo-mobile.js templates/vecino_dashboard.html
git commit -m "feat: tab bar de 5 items; gastos, votaciones y archivos dejan de ser inalcanzables en mobile"
```

---

### Task 3: El botón atrás del sistema navega en vez de salir

Cierra el defecto #2 del spec. Hoy las secciones son divs con `display:none` sin manejo de `history`, así que el gesto de volver —el más usado en Android— saca de la app.

**Files:**
- Modify: `static/js/niddo-mobile.js`

**Interfaces:**
- Consumes: `NiddoMobile.TAB_OF` y el `window.showSection` ya envuelto en la Task 2.
- Produces: nada nuevo hacia afuera.

- [ ] **Step 1: Agregar el manejo de historial**

En `static/js/niddo-mobile.js`, dentro del IIFE, reemplazar la función `wrapShowSection` completa por esta versión:

```javascript
  /* Bandera para distinguir una navegación que dispara el usuario (hay que
     empujar al historial) de una que viene del propio popstate (no hay que
     empujar, o se duplica la entrada). */
  var restoring = false;

  function wrapShowSection() {
    var original = window.showSection;
    if (typeof original !== 'function') return;
    window.showSection = function (name) {
      original.apply(this, arguments);
      setTab(TAB_OF[name] || name);
      if (!restoring) {
        history.pushState({ ndSection: name }, '', '#' + name);
      }
    };
  }

  function onPopState(e) {
    var name = (e.state && e.state.ndSection) || 'inicio';
    restoring = true;
    try {
      window.showSection(name);
    } finally {
      restoring = false;
    }
  }
```

- [ ] **Step 2: Enchufarlo en el arranque**

Reemplazar el bloque `document.addEventListener('DOMContentLoaded', ...)` de la Task 2 por:

```javascript
  document.addEventListener('DOMContentLoaded', function () {
    wrapShowSection();

    /* La entrada inicial del historial, para que el primer "atrás" tenga
       adónde volver en vez de salirse del sitio. */
    var initial = (location.hash || '#inicio').slice(1);
    if (!TAB_OF[initial]) initial = 'inicio';
    history.replaceState({ ndSection: initial }, '', '#' + initial);

    window.addEventListener('popstate', onPopState);

    restoring = true;
    try {
      window.showSection(initial);
    } finally {
      restoring = false;
    }
  });
```

Esto además da deep links: entrar a `/vecino#reservas` abre reservas directamente.

- [ ] **Step 3: Verificar la navegación hacia atrás**

A **390 × 844**, en la consola:

```javascript
showSection('expensas'); showSection('reservas'); showSection('archivos');
history.back();
```

Esperar ~100 ms y comprobar:

```javascript
[location.hash, document.querySelector('.section.active').id]
```

Esperado: `["#reservas", "section-reservas"]` — o sea, volvió una pantalla en vez de salir.

Repetir `history.back()` dos veces más y confirmar que llega a `#expensas` y después a `#inicio`, sin salirse del sitio ni tirar errores.

Probar el deep link: cargar la URL del dashboard con `#votaciones` al final y confirmar que abre votaciones con el tab "Comunidad" encendido.

A **1440 × 900**: el JS sale temprano, así que `showSection` **no** está envuelta y el hash no cambia. Verificar en consola que al llamar `showSection('expensas')` el `location.hash` sigue vacío. El escritorio queda intacto.

- [ ] **Step 4: Commit**

```bash
git add static/js/niddo-mobile.js
git commit -m "fix: el boton atras del sistema navegaba fuera de la app en vez de volver de seccion"
```

---

### Task 4: Los overlays se convierten en bottom sheets

Los 3 overlays del vecino (`drawer-pago`, `drawer-reclamo`, `modal-cond`) pasan a subir desde abajo, con grabber y arrastre para cerrar. **El markup no se toca**: es CSS que reposiciona el DOM existente, más JS que agrega el grabber.

**Files:**
- Modify: `static/css/niddo-mobile.css`
- Modify: `static/js/niddo-mobile.js`

**Interfaces:**
- Consumes: `NiddoMobile.isMobile()`. Las funciones globales `closeDrawer(id)` y `closeModal(id)` del template (líneas ~671–682).
- Produces: nada nuevo hacia afuera.

- [ ] **Step 1: CSS de las sheets**

Dentro del `@media` de `static/css/niddo-mobile.css`:

```css
  /* ── Bottom sheets ───────────────────────────────────────────────────────
     Mismo DOM que en escritorio, reposicionado. El drawer venía de la
     derecha y el modal del centro; en mobile los dos suben desde abajo. */
  .drawer-overlay { align-items: flex-end; justify-content: center; }
  .modal-overlay  { align-items: flex-end; justify-content: center; padding: 0; }

  .drawer,
  .modal-box {
    width: 100%; max-width: 100%;
    height: auto; max-height: 88%;
    border: none; border-radius: 26px 26px 0 0;
    box-shadow: 0 -8px 40px rgba(42,33,28,.22);
    transform: translateY(100%);
    transition: transform .34s cubic-bezier(.32,.72,0,1);
    padding-bottom: var(--safe-bottom);
    display: flex; flex-direction: column;
  }
  .drawer-overlay.open .drawer,
  .modal-overlay.open .modal-box { transform: translateY(0); }

  /* Durante el arrastre mandamos nosotros el transform, sin transición. */
  .drawer.nd-dragging,
  .modal-box.nd-dragging { transition: none; }

  .nd-grabber {
    padding: 10px 0 4px;
    display: flex; justify-content: center;
    cursor: grab; touch-action: none; flex-shrink: 0;
  }
  .nd-grabber::after {
    content: ''; width: 38px; height: 5px;
    border-radius: 3px; background: #D8C9B8;
  }

  .drawer-body, .mb { overflow-y: auto; flex: 1; }
  .drawer-footer, .mf { position: static; flex-shrink: 0; }

  /* Los inputs por debajo de 16px hacen que iOS zoomee al enfocar. */
  .fc, input, select, textarea { font-size: 16px; }
```

- [ ] **Step 2: JS del grabber y el arrastre**

En `static/js/niddo-mobile.js`, antes del `})();` final:

```javascript
  /* ── Bottom sheets ───────────────────────────────────────────────────── */

  /* El arrastre se ata sólo al grabber, nunca al cuerpo scrolleable: si no,
     arrastrar para leer cerraría la hoja. */
  function makeDraggable(panel, overlay) {
    var grabber = document.createElement('div');
    grabber.className = 'nd-grabber';
    panel.insertBefore(grabber, panel.firstChild);

    grabber.addEventListener('pointerdown', function (e) {
      var y0 = e.clientY;
      var h = panel.offsetHeight;
      panel.classList.add('nd-dragging');
      grabber.setPointerCapture(e.pointerId);

      function move(ev) {
        var dy = Math.max(0, ev.clientY - y0);
        panel.style.transform = 'translateY(' + dy + 'px)';
        overlay.style.background = 'rgba(42,33,28,' + Math.max(0, .5 - dy / h * .7) + ')';
      }
      function up(ev) {
        grabber.removeEventListener('pointermove', move);
        grabber.removeEventListener('pointerup', up);
        panel.classList.remove('nd-dragging');
        panel.style.transform = '';
        overlay.style.background = '';
        if (ev.clientY - y0 > 90) closeOverlay(overlay);
      }
      grabber.addEventListener('pointermove', move);
      grabber.addEventListener('pointerup', up);
    });
  }

  /* Usamos las funciones del template si están, para no duplicar la lógica
     de limpieza de formularios que puedan tener. */
  function closeOverlay(overlay) {
    var id = overlay.id;
    if (overlay.classList.contains('drawer-overlay') && typeof window.closeDrawer === 'function') {
      window.closeDrawer(id);
    } else if (typeof window.closeModal === 'function') {
      window.closeModal(id);
    } else {
      overlay.classList.remove('open');
    }
  }

  function initSheets() {
    var overlays = document.querySelectorAll('.drawer-overlay, .modal-overlay');
    for (var i = 0; i < overlays.length; i++) {
      var overlay = overlays[i];
      var panel = overlay.querySelector('.drawer, .modal-box');
      if (!panel || panel.querySelector(':scope > .nd-grabber')) continue;
      makeDraggable(panel, overlay);

      /* Tocar el fondo cierra. */
      overlay.addEventListener('click', function (ev) {
        if (ev.target === this) closeOverlay(this);
      });
    }
  }
```

Agregar `initSheets();` dentro del `DOMContentLoaded` de la Task 3, después de `window.addEventListener('popstate', onPopState);`.

- [ ] **Step 3: Verificar las tres sheets**

A **390 × 844**, en la consola:

```javascript
document.querySelectorAll('.nd-grabber').length
```

Esperado: `3` — un grabber en `drawer-pago`, `drawer-reclamo` y `modal-cond`.

Abrir cada una y comprobar que sube desde abajo, no desde el costado:

```javascript
openDrawer('drawer-pago');
getComputedStyle(document.querySelector('#drawer-pago .drawer')).transform
```

Esperado: una matriz sin desplazamiento (`matrix(1, 0, 0, 1, 0, 0)`) con la hoja visible abajo.

A mano, en cada una de las tres:
- Arrastrar el grabber hacia abajo unos 100px y soltar → se cierra.
- Arrastrar 30px y soltar → vuelve a su lugar, no se cierra.
- Hacer scroll dentro del cuerpo de la hoja → **no** se cierra.
- Tocar el fondo oscuro → se cierra.
- Enfocar un input → iOS no debe hacer zoom (el `font-size:16px`).

Verificar que **informar un pago** y **crear un reclamo** siguen funcionando de punta a punta desde la sheet.

A **1440 × 900**: `drawer-pago` sigue entrando desde la derecha con sus 460px, y `modal-cond` sigue centrado. Los grabbers están en el DOM pero ocultos por el CSS de escritorio — confirmar que no se ven.

- [ ] **Step 4: Commit**

```bash
git add static/css/niddo-mobile.css static/js/niddo-mobile.js
git commit -m "feat: los drawers y el modal del vecino suben como bottom sheets arrastrables en mobile"
```

---

### Task 5: Título grande colapsable y hoja de "Más"

Reemplaza el `.app-header` fijo por una barra que muestra el título de la pantalla y lo colapsa al scrollear. Además completa el tab "Más", que en la Task 2 quedó como atajo a perfil.

**Files:**
- Modify: `static/css/niddo-mobile.css`
- Modify: `static/js/niddo-mobile.js`

**Interfaces:**
- Consumes: `NiddoMobile.setTab`, `NiddoMobile.TAB_OF`, `closeOverlay`.
- Produces: `NiddoMobile.openMas()` en su versión definitiva, reemplazando el atajo de la Task 2.

- [ ] **Step 1: CSS del título y de la hoja de Más**

Dentro del `@media`:

```css
  /* ── Top app bar ─────────────────────────────────────────────────────── */
  .app-header {
    height: auto;
    padding: var(--safe-top) 12px 0;
    flex-direction: column; align-items: stretch;
    transition: box-shadow .2s, background .2s;
  }
  .app-header.nd-scrolled {
    background: rgba(251,246,239,.86);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
  }
  .header-brand { display: none; }
  .header-center { padding: 0; }

  .nd-titlerow { display: flex; align-items: center; min-height: 48px; }
  .nd-largetitle {
    font-family: 'Fredoka', var(--font);
    font-weight: 600; font-size: 1.7rem;
    letter-spacing: -.025em; line-height: 1.15;
    padding: 0 4px 10px;
    transition: opacity .18s, transform .18s;
  }
  .app-header.nd-scrolled .nd-largetitle {
    opacity: 0; transform: translateY(-8px) scale(.94);
    height: 0; padding: 0; overflow: hidden;
  }
  .nd-compacttitle {
    flex: 1; text-align: center;
    font-family: 'Fredoka', var(--font);
    font-weight: 600; font-size: 1rem;
    opacity: 0; transform: translateY(6px);
    transition: opacity .2s, transform .2s;
  }
  .app-header.nd-scrolled .nd-compacttitle { opacity: 1; transform: none; }

  /* La hoja de Más reusa el aspecto de las sheets de la Task 4. */
  #nd-mas-overlay { align-items: flex-end; justify-content: center; }
  #nd-mas-sheet {
    width: 100%; background: var(--surface);
    border-radius: 26px 26px 0 0;
    padding-bottom: calc(var(--safe-bottom) + 8px);
    transform: translateY(100%);
    transition: transform .34s cubic-bezier(.32,.72,0,1);
  }
  #nd-mas-overlay.open #nd-mas-sheet { transform: translateY(0); }
  .nd-mas-item {
    display: flex; align-items: center; gap: 12px;
    width: 100%; min-height: 52px; padding: 14px 20px;
    background: none; border: none; border-bottom: 1px solid var(--border2);
    font-family: var(--font); font-size: .95rem; font-weight: 700;
    color: var(--text); text-align: left; cursor: pointer;
  }
  .nd-mas-item:last-child { border-bottom: none; }
  .nd-mas-item:active { background: var(--surface2); }
  .nd-mas-item.danger { color: var(--nd-terracota-hondo); }
```

- [ ] **Step 2: JS del título y de la hoja**

En `static/js/niddo-mobile.js`, antes del `})();`:

```javascript
  /* ── Top app bar ─────────────────────────────────────────────────────── */

  var TITLES = {
    inicio: 'Inicio', expensas: 'Mis expensas', gastos: 'Gastos del consorcio',
    comunicados: 'Comunicados', votaciones: 'Votaciones', reclamos: 'Reclamos',
    reservas: 'Reservas', archivos: 'Archivos', perfil: 'Mi perfil'
  };

  function buildHeader() {
    var header = document.querySelector('.app-header');
    if (!header || header.querySelector('.nd-largetitle')) return;

    var row = document.createElement('div');
    row.className = 'nd-titlerow';
    var compact = document.createElement('div');
    compact.className = 'nd-compacttitle';
    row.appendChild(compact);

    var large = document.createElement('div');
    large.className = 'nd-largetitle';

    header.insertBefore(row, header.firstChild);
    header.appendChild(large);
  }

  function setTitle(name) {
    var t = TITLES[name] || '';
    var large = document.querySelector('.nd-largetitle');
    var compact = document.querySelector('.nd-compacttitle');
    if (large) large.textContent = t;
    if (compact) compact.textContent = t;
  }

  function watchScroll() {
    var header = document.querySelector('.app-header');
    if (!header) return;
    window.addEventListener('scroll', function () {
      header.classList.toggle('nd-scrolled', window.scrollY > 26);
    }, { passive: true });
  }

  /* ── Hoja de "Más" ───────────────────────────────────────────────────── */

  var MAS_ITEMS = [
    { section: 'archivos', label: 'Archivos', icon: 'ic-carpeta' },
    { section: 'gastos',   label: 'Gastos del consorcio', icon: 'ic-balance' },
    { section: 'perfil',   label: 'Mi perfil', icon: 'ic-vecino' }
  ];

  function buildMas() {
    if (document.getElementById('nd-mas-overlay')) return;

    var overlay = document.createElement('div');
    overlay.className = 'drawer-overlay';
    overlay.id = 'nd-mas-overlay';

    var sheet = document.createElement('div');
    sheet.id = 'nd-mas-sheet';

    var grabber = document.createElement('div');
    grabber.className = 'nd-grabber';
    sheet.appendChild(grabber);

    MAS_ITEMS.forEach(function (item) {
      var b = document.createElement('button');
      b.className = 'nd-mas-item';
      b.innerHTML = '<svg class="ic"><use href="#' + item.icon + '"></use></svg>' + item.label;
      b.addEventListener('click', function () {
        closeMas();
        window.showSection(item.section);
      });
      sheet.appendChild(b);
    });

    var out = document.createElement('a');
    out.className = 'nd-mas-item danger';
    out.href = '/auth/logout';
    out.innerHTML = '<svg class="ic"><use href="#ic-salir"></use></svg>Cerrar sesión';
    sheet.appendChild(out);

    overlay.appendChild(sheet);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', function (ev) {
      if (ev.target === overlay) closeMas();
    });
  }

  function closeMas() {
    var o = document.getElementById('nd-mas-overlay');
    if (o) o.classList.remove('open');
  }
```

Reemplazar la asignación provisoria de `NiddoMobile.openMas` de la Task 2 por:

```javascript
  NiddoMobile.openMas = function () {
    var o = document.getElementById('nd-mas-overlay');
    if (!o) return;
    o.classList.add('open');
    setTab('mas');
  };
```

Y en el `DOMContentLoaded`, después de `initSheets();`, agregar:

```javascript
    buildHeader();
    buildMas();
    watchScroll();
```

Además, dentro del `window.showSection` envuelto (Task 3), agregar `setTitle(name);` justo después de `setTab(TAB_OF[name] || name);`.

- [ ] **Step 3: Verificar**

A **390 × 844**, en la consola:

```javascript
showSection('expensas');
[document.querySelector('.nd-largetitle').textContent, document.querySelector('.nd-compacttitle').textContent]
```

Esperado: `["Mis expensas", "Mis expensas"]`.

```javascript
window.scrollTo(0, 200);
document.querySelector('.app-header').classList.contains('nd-scrolled')
```

Esperado: `true`. Volviendo a `window.scrollTo(0,0)`, esperado `false`.

Tocar el tab **Más** → sube la hoja con Archivos, Gastos del consorcio, Mi perfil y Cerrar sesión. Tocar Archivos → se cierra la hoja y abre la sección. Arrastrar la hoja hacia abajo → se cierra.

A **1440 × 900**: el header sigue mostrando el logo y los badges de consorcio/UF como antes; no aparece ningún título grande. Consola sin errores.

- [ ] **Step 4: Commit**

```bash
git add static/css/niddo-mobile.css static/js/niddo-mobile.js
git commit -m "feat: titulo grande colapsable y hoja de Mas en mobile"
```

---

### Task 6: La cuenta corriente se lee como lista

Primera de las tres tablas. `renderCobrosTable()` pasa a emitir, además del `<tr>` de escritorio, un bloque de fila-tarjeta para mobile. CSS muestra uno u otro.

**Files:**
- Modify: `templates/vecino_dashboard.html:898-930` (`renderCobrosTable`)
- Modify: `static/css/niddo-mobile.css`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: las clases `.nd-list`, `.nd-row` y sus hijas, que las Tasks 7 reusan.

- [ ] **Step 1: CSS de la lista**

Dentro del `@media`:

```css
  /* ── Listas que reemplazan tablas ────────────────────────────────────── */
  .table-wrap .table { display: none; }      /* la tabla de escritorio */
  .table-wrap .table-filters { padding: 12px; }

  .nd-list { display: block; }
  .nd-row {
    display: flex; align-items: center; gap: 12px;
    width: 100%; min-height: 60px; padding: 14px 16px;
    background: var(--surface); border: none;
    border-bottom: 1px solid var(--border2);
    font-family: var(--font); text-align: left; cursor: pointer;
  }
  .nd-row:last-child { border-bottom: none; }
  .nd-row:active { background: var(--surface2); }
  .nd-row-ic {
    width: 40px; height: 40px; flex-shrink: 0; border-radius: 13px;
    display: flex; align-items: center; justify-content: center;
    background: var(--nd-terracota-dim); color: var(--nd-terracota-hondo);
  }
  .nd-row-ic.ok { background: var(--nd-verde-dim); color: var(--nd-verde); }
  .nd-row-main { flex: 1; min-width: 0; }
  .nd-row-t { font-size: .93rem; font-weight: 700; letter-spacing: -.01em; }
  .nd-row-s {
    font-size: .79rem; color: var(--muted); font-weight: 600;
    margin-top: 2px; display: flex; align-items: center; gap: 6px;
  }
  .nd-row-amt { font-size: .93rem; font-weight: 800; letter-spacing: -.01em; flex-shrink: 0; }
```

Y fuera del `@media`, al final del archivo, la contraparte de escritorio:

```css
/* En escritorio manda la tabla; las filas mobile no existen visualmente. */
@media (min-width: 901px) {
  .nd-list { display: none; }
}
```

- [ ] **Step 2: Emitir las filas mobile**

En `templates/vecino_dashboard.html`, dentro de `renderCobrosTable()`, la función termina en la línea 934 con `tb.innerHTML = rows.join('');` (la fila de totales ya se agregó con `rows.push(...)` justo antes). Reemplazar esa última línea por:

```javascript
    tb.innerHTML = rows.join('');

    /* Misma fuente de datos, otra forma: la lista que se ve en mobile.
       Si cambia un campo, se cambia acá y en el <tr> de arriba, en la misma
       función y sobre el mismo objeto. */
    const wrap = tb.closest('.table-wrap');
    let list = wrap.querySelector('.nd-list');
    if (!list) {
        list = document.createElement('div');
        list.className = 'nd-list';
        wrap.appendChild(list);
    }
    list.innerHTML = S.cobros.map(c => {
        const pagado = c.estado === 'pagado';
        return `<button class="nd-row" onclick="openPagoForCobro('${c.id}')">
            <span class="nd-row-ic ${pagado ? 'ok' : ''}"><svg class="ic"><use href="#ic-expensa"></use></svg></span>
            <span class="nd-row-main">
                <span class="nd-row-t">${c.periodo || '–'}</span>
                <span class="nd-row-s"><span class="dot ${pagado ? 'ok' : 'danger'}"></span>${pagado ? 'Pagada' : 'Vence el ' + fmtD(c.fecha_vencimiento)}</span>
            </span>
            <span class="nd-row-amt">${fmt$(c.total)}</span>
        </button>`;
    }).join('');
```

Los nombres de campo están verificados contra los `<td>` que la función ya emite: `c.periodo`, `c.estado`, `c.fecha_vencimiento`, `c.total`, `c.id`. La fila de totales del escritorio **no** se replica en la lista mobile: ahí el total va en el KPI de arriba, y repetirlo como una fila más confundiría.

- [ ] **Step 3: Verificar**

A **390 × 844**, entrando a Expensas, en la consola:

```javascript
[document.querySelectorAll('#tb-cobros .data-row').length, document.querySelectorAll('.nd-list .nd-row').length]
```

Esperado: los dos números iguales y mayores que cero — una fila mobile por cada `<tr>`.

```javascript
getComputedStyle(document.querySelector('#table-cobros')).display
```

Esperado: `"none"` — la tabla no se ve en mobile.

A mano: confirmar que no hay scroll horizontal a 360px, que cada fila muestra período, estado y monto, y que tocarla abre el flujo de pago.

A **1440 × 900**:

```javascript
[getComputedStyle(document.querySelector('#table-cobros')).display, getComputedStyle(document.querySelector('.nd-list')).display]
```

Esperado: `["table", "none"]` — en escritorio manda la tabla y la lista está oculta.

- [ ] **Step 4: Commit**

```bash
git add templates/vecino_dashboard.html static/css/niddo-mobile.css
git commit -m "feat: la cuenta corriente se lee como lista en mobile en vez de tabla de 7 columnas"
```

---

### Task 7: Las tablas de gastos y reservas se leen como listas

Mismo patrón de la Task 6 aplicado a las dos tablas restantes. Reusa las clases `.nd-list` / `.nd-row` ya definidas — no se agrega CSS nuevo.

**Files:**
- Modify: `templates/vecino_dashboard.html:1012` (`loadGastos`) y la función `loadMisReservas` (**no** `loadReservas` — la tabla `tb-reservas` la llena `loadMisReservas`)

**Nombres verificados contra el código:** las dos funciones usan variables **locales**, no `S.*`. En `loadGastos` la data es `const data`; en `loadMisReservas` es `const d`. Los campos son `g.descripcion`, `g.proveedores?.nombre`, `g.fecha_gasto`, `g.monto`; y `r.amenities?.nombre`, `r.fecha`, `r.hora_inicio`, `r.hora_fin`, `r.estado`.

**Interfaces:**
- Consumes: `.nd-list`, `.nd-row`, `.nd-row-ic`, `.nd-row-main`, `.nd-row-t`, `.nd-row-s`, `.nd-row-amt` de la Task 6.
- Produces: nada nuevo.

- [ ] **Step 1: Lista de gastos**

En `loadGastos()`, después de asignar el `innerHTML` de `tb-gastos`, agregar:

```javascript
    const wrapG = document.getElementById('tb-gastos').closest('.table-wrap');
    let listG = wrapG.querySelector('.nd-list');
    if (!listG) {
        listG = document.createElement('div');
        listG.className = 'nd-list';
        wrapG.appendChild(listG);
    }
    listG.innerHTML = data.map(g => `<div class="nd-row" style="cursor:default">
        <span class="nd-row-ic ok"><svg class="ic"><use href="#ic-balance"></use></svg></span>
        <span class="nd-row-main">
            <span class="nd-row-t">${g.descripcion || '–'}</span>
            <span class="nd-row-s">${g.proveedores?.nombre || 'Sin proveedor'} · ${fmtD(g.fecha_gasto)}</span>
        </span>
        <span class="nd-row-amt">${fmt$(g.monto)}</span>
    </div>`).join('');
```

`data` es la variable local que la función ya recorre con `data.map(g => ...)` para armar los `<tr>`. El bloque va **dentro** del `try`, después del `tb.innerHTML = ...`, para que `data` siga en alcance.

- [ ] **Step 2: Lista de reservas**

En `loadMisReservas()` — **no** en `loadReservas()` — después de asignar el `innerHTML` de `tb-reservas` y dentro del mismo `try`, agregar:

```javascript
    const wrapR = document.getElementById('tb-reservas').closest('.table-wrap');
    let listR = wrapR.querySelector('.nd-list');
    if (!listR) {
        listR = document.createElement('div');
        listR.className = 'nd-list';
        wrapR.appendChild(listR);
    }
    listR.innerHTML = d.map(r => {
        const activa = r.estado === 'confirmada';
        return `<div class="nd-row" style="cursor:default">
            <span class="nd-row-ic ${activa ? 'ok' : ''}"><svg class="ic"><use href="#ic-reserva"></use></svg></span>
            <span class="nd-row-main">
                <span class="nd-row-t">${r.amenities?.nombre || 'Amenity'}</span>
                <span class="nd-row-s"><span class="dot ${activa ? 'ok' : 'muted'}"></span>${fmtD(r.fecha)} · ${r.hora_inicio?.substring(0,5) || ''}–${r.hora_fin?.substring(0,5) || ''}</span>
            </span>
            ${activa ? `<button class="btn btn-danger btn-xs" onclick="cancelarReserva('${r.id}')">Cancelar</button>` : ''}
        </div>`;
    }).join('');
```

`d` es la variable local de la función. El `.substring(0,5)` recorta `18:00:00` a `18:00`, igual que hace el `<tr>` de escritorio.

- [ ] **Step 3: Verificar las dos**

A **390 × 844**, entrando a Reporte de Gastos y después a Reservas:

```javascript
['tb-gastos','tb-reservas'].map(id => { const w = document.getElementById(id).closest('.table-wrap'); return [id, document.querySelectorAll('#'+id+' tr').length, w.querySelectorAll('.nd-row').length]; })
```

Esperado: para cada tabla, la cantidad de `<tr>` y de `.nd-row` coinciden.

Confirmar visualmente que ninguna de las dos secciones tiene scroll horizontal a 360px, y que los montos y fechas se leen completos sin cortarse.

A **1440 × 900**: las dos tablas se ven como antes, con todas sus columnas, y ninguna `.nd-list` es visible.

- [ ] **Step 4: Commit**

```bash
git add templates/vecino_dashboard.html
git commit -m "feat: gastos y reservas se leen como listas en mobile"
```

---

### Task 8: Barrido final de detalle

Lo que queda para que se sienta terminado: snackbars a lo ancho, targets que hayan quedado chicos, y el repaso completo contra los criterios de éxito del spec.

**Files:**
- Modify: `static/css/niddo-mobile.css`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: nada.

- [ ] **Step 1: Snackbars y targets**

Dentro del `@media`:

```css
  /* ── Snackbars ───────────────────────────────────────────────────────────
     En escritorio los toasts van abajo a la derecha; en mobile eso los mete
     debajo de la tab bar. Van a lo ancho, por encima de ella. */
  .toast-container {
    left: 12px; right: 12px;
    bottom: calc(var(--tabbar-h) + var(--safe-bottom) + 12px);
  }
  .toast { max-width: 100%; }

  /* ── Targets ─────────────────────────────────────────────────────────── */
  .btn { min-height: 44px; padding: 12px 18px; }
  .btn-sm, .btn-xs { min-height: 40px; }
  .hbtn, .mc, .dropzone-remove { min-width: 44px; min-height: 44px; }

  /* 100vh se rompe con la barra de URL de Safari. */
  .app-main { min-height: 100dvh; }
  .drawer { max-height: 88dvh; }

  /* Feedback táctil donde había hover. */
  .btn:active, .nav-btn:active, .dd-item:active { transform: scale(.97); }

  /* El calendario de reservas necesita poder scrollearse con el dedo. */
  .cal-grid { max-height: 60dvh; }
```

- [ ] **Step 2: Repasar los 8 criterios de éxito del spec**

Uno por uno, a 360 × 740 salvo donde se indique:

| # | Criterio | Cómo se comprueba |
|---|---|---|
| 1 | Las 9 secciones son alcanzables | `['inicio','comunicados','expensas','gastos','reclamos','votaciones','reservas','archivos','perfil'].every(s => { showSection(s); return document.getElementById('section-'+s).classList.contains('active'); })` → `true` |
| 2 | El atrás del sistema retrocede | `history.back()` tras navegar → vuelve de sección, no sale |
| 3 | Sin scroll horizontal | `document.documentElement.scrollWidth <= window.innerWidth` → `true` en las 9 secciones |
| 4 | Safe areas respetadas | La tab bar no queda bajo el home indicator en 390×844 |
| 5 | Targets ≥ 44px y sin `:hover` | `[...document.querySelectorAll('button, a')].filter(e => e.offsetParent && e.getBoundingClientRect().height < 44)` → array vacío |
| 6 | Las 3 tablas se leen como listas | Las 3 `.nd-list` tienen filas y las 3 `.table` están en `display:none` |
| 7 | **Escritorio idéntico** | A 1440×900, recorrer las 9 secciones y comparar contra `main` |
| 8 | Primitivos en archivos compartidos | `niddo-mobile.css` y `.js` no tienen nada específico del vecino salvo `TITLES`, `TAB_OF` y `MAS_ITEMS` |

Anotar en el commit cualquier criterio que no se cumpla, en vez de darlo por bueno.

- [ ] **Step 3: Verificar la regresión de escritorio contra `main`**

```bash
git stash list && git diff main --stat -- templates/vecino_dashboard.html
```

Revisar que el diff del template toque **sólo**: el meta viewport, los dos `<link>`/`<script>` nuevos, el bloque de la `bottom-nav`, y el final de las tres funciones de render. Ninguna regla del `<style>` inline debe haber cambiado.

- [ ] **Step 4: Commit**

```bash
git add static/css/niddo-mobile.css
git commit -m "feat: snackbars, targets tactiles y barrido final de detalle en mobile"
```

---

## Self-review del plan

**Cobertura del spec:** los 8 pasos de §6 del spec mapean a las Tasks 1–8. Los 3 defectos de §1 se cierran en Tasks 2 (secciones huérfanas), 3 (botón atrás) y 1 (safe areas, vía `viewport-fit=cover`). Los 8 criterios de éxito de §9 se verifican explícitamente en la Task 8.

**Consistencia de nombres:** `NiddoMobile.isMobile`, `.TAB_OF`, `.setTab`, `.openMas` se definen en Tasks 1–2 y se consumen con esos mismos nombres en 3–5. Las clases `.nd-list` / `.nd-row*` se definen en Task 6 y se reusan en Task 7. `closeOverlay` se define en Task 4 y se usa en Task 5.

**Deuda conocida, asumida a propósito:**
- El markup de fila se emite dos veces (escritorio y mobile) en las tres funciones de render. Justificado en §5.2 del spec: la alternativa —transformar el DOM tras cada respuesta de la API— es frágil por timing.
- `NiddoMobile.openMas` se define provisoriamente en la Task 2 y se reemplaza en la Task 5. Es deliberado: la Task 2 tiene que quedar funcionando por sí sola.
- Las Tasks 6 y 7 dependen de nombres de campo (`c.periodo`, `g.descripcion`, `r.amenity_nombre`) que hay que confirmar leyendo los `<td>` que cada función ya emite. Está señalado dentro de cada tarea.
