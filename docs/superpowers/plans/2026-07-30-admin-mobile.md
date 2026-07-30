# Rediseño mobile del admin — Plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development o superpowers:executing-plans para implementar tarea por tarea. Los pasos usan checkbox (`- [ ]`).

**Goal:** Hacer usable el panel de administrador en un teléfono, incluida la tabla de prorrateo de 14 columnas, sin tocar el escritorio ni romper el dashboard del vecino que ya está en producción.

**Architecture:** Se parametriza la fundación del sub-proyecto 1 para que deje de ser específica del vecino, y se aplica a admin. Todo el CSS dentro de `@media(max-width:900px)`; el JS sale temprano en escritorio.

**Tech Stack:** Flask + Jinja2, HTML/CSS/JS sin framework ni build step.

**Spec:** `docs/superpowers/specs/2026-07-30-admin-mobile-design.md`
**Referencia visual:** `docs/mockups/admin-mobile.html`

## Global Constraints

- **Todo el CSS nuevo dentro de `@media (max-width:900px)`.** El escritorio a 1440px queda idéntico.
- **⚠ Orden de cascada:** el `<style>` inline de cada template se carga **después** de `niddo-mobile.css`, así que a igual especificidad **gana el inline**. Para pisar una propiedad que el inline declara hay que subir especificidad con un id o con `.nd-mobile` — nunca `!important`. Un atributo `style="..."` no se puede pisar desde CSS: se edita el template. **Verificar siempre el valor computado, no asumir que la regla se aplicó.**
- **Tokens sólo de `niddo-brand.css`** (Ruta Barrio). No inventar hex.
- **Targets ≥44px. Inputs ≥16px** (por debajo, iOS zoomea al enfocar).
- **Ningún estado nuevo puede depender de `:hover`.**
- **No se introduce framework de tests.** Verificación en navegador, especificada por paso.
- **No se toca `proveedor_dashboard.html`, `login.html` ni `index.html`.**
- **Voseo argentino** en todo texto visible.
- **Rama:** `feat/mobile-admin`. Un commit por tarea.

## Refinamiento sobre el spec §7.1 — riesgo del paso 1 eliminado

El spec proponía que **cada** template declarara su config, lo que obligaba a tocar `vecino_dashboard.html`, que está en producción.

**Se cambia:** los valores por defecto de la fundación **son los del vecino**. Entonces:

- `vecino_dashboard.html` **no se modifica** en la Task 1. Cero riesgo para producción.
- Sólo `admin_dashboard.html` declara `window.NIDDO_MOBILE_CONFIG`.
- Si algún día se agrega un tercer consumidor, ahí sí conviene mover los defaults afuera. Queda anotado como deuda, no como trabajo de ahora.

## Cómo verificar (todas las tareas)

Banco de pruebas (el panel real requiere login por Auth0, que no se puede automatizar):

```bash
python3 /private/tmp/claude-501/-Users-santiagodespontin-Niddo/1e9938ff-9f96-434f-98d8-5ce3bc9ced69/scratchpad/harness.py
```

Sirve el vecino en `/` y hay que extenderlo con una ruta `/admin` en la Task 2.

| Viewport | Medidas | Qué prueba |
|---|---|---|
| Android chico | 360 × 740 | El ancho mínimo real |
| iPhone | 390 × 844 | Safe areas iOS |
| **Escritorio** | **1440 × 900** | **Que no se rompió nada** |

**Regresión del vecino: obligatoria en las Tasks 1 y 11**, porque está en producción.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `static/js/niddo-mobile.js` | Se parametriza. Los defaults quedan siendo los del vecino. |
| `static/css/niddo-mobile.css` | Se generaliza (`#nd-tabbar` → clase) y se extiende con lo de admin. |
| `templates/admin_dashboard.html` | Config, tab bar, anchos inline, generadores de fila. |
| `templates/vecino_dashboard.html` | **No se toca** hasta la Task 11 (sólo verificación). |

---

### Task 1: Parametrizar la fundación sin tocar el vecino

**Files:**
- Modify: `static/js/niddo-mobile.js`
- Modify: `static/css/niddo-mobile.css`

**Interfaces:**
- Produces: `window.NIDDO_MOBILE_CONFIG` como punto de extensión, con claves `navFn`, `sectionPrefix`, `headerSelector`, `tabOf`, `titles`, `masItems`, `navPassesElement`, `usesHash`.

- [ ] **Step 1: Leer la config con defaults del vecino**

En `niddo-mobile.js`, justo después de `document.documentElement.classList.add('nd-mobile');`, insertar:

```javascript
    /* ── Configuración ────────────────────────────────────────────────────
       Los valores por defecto son los del vecino, que fue el primer
       consumidor. Así ese template no necesita declarar nada y no hubo que
       tocarlo para que admin entrara. Si aparece un tercer consumidor,
       conviene mover estos defaults a su propio template. */
    var CFG = window.NIDDO_MOBILE_CONFIG || {};

    var navFn          = CFG.navFn || 'showSection';
    var sectionPrefix  = CFG.sectionPrefix || 'section-';
    var headerSelector = CFG.headerSelector || '.app-header';
    var navPassesEl    = CFG.navPassesElement === true;
    var usesHash       = CFG.usesHash === true;
```

- [ ] **Step 2: Reemplazar las tres constantes hardcodeadas**

Cambiar `var TAB_OF = { … };` por:

```javascript
    var TAB_OF = CFG.tabOf || {
        inicio: 'inicio', expensas: 'expensas', gastos: 'expensas',
        comunicados: 'comunidad', votaciones: 'comunidad', reclamos: 'comunidad',
        reservas: 'reservas', archivos: 'mas', perfil: 'mas'
    };
```

Cambiar `var TITLES = { … };` por:

```javascript
    var TITLES = CFG.titles || {
        inicio: 'Inicio', expensas: 'Mis expensas', gastos: 'Gastos del consorcio',
        comunicados: 'Comunicados', votaciones: 'Votaciones', reclamos: 'Reclamos',
        reservas: 'Reservas', archivos: 'Archivos', perfil: 'Mi perfil'
    };
```

Cambiar `var MAS_ITEMS = [ … ];` por:

```javascript
    var MAS_ITEMS = CFG.masItems || [
        { section: 'archivos', label: 'Archivos', icon: 'ic-carpeta' },
        { section: 'gastos', label: 'Gastos del consorcio', icon: 'ic-balance' },
        { section: 'perfil', label: 'Mi perfil', icon: 'ic-vecino' }
    ];
```

- [ ] **Step 3: Generalizar `wrapShowSection` a cualquier función de navegación**

Reemplazar la función entera por:

```javascript
    /* La función de navegación la define el <script> inline del template:
       showSection(name) en el vecino, show(id, el) en admin. La envolvemos
       en vez de tocarla, para que el escritorio siga usando la original. */
    function wrapNav() {
        var original = window[navFn];
        if (typeof original !== 'function') return;
        window[navFn] = function (name) {
            /* show(id, el) usa el segundo argumento para marcar el nav-link
               del sidebar. Desde la tab bar no hay elemento; la función ya
               hace `if (el)`, así que pasar undefined es seguro y en mobile
               el sidebar está oculto igual. */
            original.call(this, name, navPassesEl ? arguments[1] : undefined);
            setTab(TAB_OF[name] || name);
            setTitle(name);
            if (!restoring && !usesHash) {
                history.pushState({ ndSection: name }, '', '#' + name);
            }
        };
    }
```

`usesHash` existe porque admin ya escribe `window.location.hash` dentro de su propia `show()`: empujar además con `pushState` duplicaría entradas y el atrás necesitaría dos toques.

- [ ] **Step 4: Generalizar el selector del header y del prefijo de sección**

Reemplazar `document.querySelector('.app-header')` por `document.querySelector(headerSelector)` en `buildHeader()` y en `watchScroll()`.

En el `DOMContentLoaded`, reemplazar la llamada a `window.showSection(initial)` por `window[navFn](initial)`, y `wrapShowSection()` por `wrapNav()`.

En `buildMas()`, reemplazar `window.showSection(item.section)` por `window[navFn](item.section)`.

- [ ] **Step 5: Generalizar el CSS de la tab bar**

En `niddo-mobile.css`, agregar la clase `.nd-tabbar` como alternativa al id, para que admin no tenga que llamar `nd-tabbar` a su barra:

```css
    #nd-tabbar.bottom-nav,
    .bottom-nav.nd-tabbar { /* … las mismas propiedades … */ }

    #nd-tabbar .bottom-btn,
    .nd-tabbar .bottom-btn { /* … */ }
```

Y en el JS, cambiar el selector de `setTab` a:

```javascript
        var tabs = document.querySelectorAll('#nd-tabbar .bottom-btn, .nd-tabbar .bottom-btn');
```

- [ ] **Step 6: Verificar que el vecino no cambió — obligatorio**

Con el banco de pruebas en `/`, a **390 × 844**:

```javascript
JSON.stringify({
  tabs: [...document.querySelectorAll('.bottom-btn')].map(b=>b.dataset.tab),
  alcanzables: ['inicio','comunicados','expensas','gastos','reclamos','votaciones','reservas','archivos','perfil']
    .every(s => { showSection(s); return document.getElementById('section-'+s).classList.contains('active'); }),
  titulo: (showSection('expensas'), document.querySelector('.nd-largetitle').textContent),
  masItems: [...document.querySelectorAll('.nd-mas-item')].map(i=>i.textContent.trim()),
  grabbers: document.querySelectorAll('.nd-grabber').length
})
```

Esperado, **idéntico a antes de esta tarea**:
`tabs` = `["inicio","expensas","comunidad","reservas","mas"]` · `alcanzables` = `true` · `titulo` = `"Mis expensas"` · `masItems` = `["Archivos","Gastos del consorcio","Mi perfil","Cerrar sesión"]` · `grabbers` = `4` (los 3 overlays del template más la hoja de Más, que también lleva grabber).

Probar el atrás: `showSection('reservas'); showSection('archivos'); history.back();` → vuelve a `#reservas`.

A **1440 × 900**: `NiddoMobile.isMobile()` → `false`, sidebar `flex`, sin `nd-mobile` en `<html>`.

- [ ] **Step 7: Commit**

```bash
git add static/js/niddo-mobile.js static/css/niddo-mobile.css
git commit -m "refactor: la fundacion mobile deja de ser especifica del vecino"
```

---

### Task 2: Layout base de admin en mobile

Cierra el defecto #1: hoy `.main` tiene `margin-left:220px` sobre 360px de viewport.

**Files:**
- Modify: `templates/admin_dashboard.html` (meta viewport, carga de los archivos)
- Modify: `static/css/niddo-mobile.css`
- Modify: el banco de pruebas, para agregar `/admin`

- [ ] **Step 1: Agregar la ruta `/admin` al banco de pruebas**

En `harness.py`:

```python
@app.route("/admin")
def admin():
    return render_template("admin_dashboard.html")
```

Y rutas de API con datos de mentira para `/api/consorcios`, `/api/gastos`, `/api/cobros`, `/api/proveedores`, `/api/liquidaciones`. El fallback `/api/<path:rest>` que ya existe devuelve `[]` para el resto.

- [ ] **Step 2: Meta viewport y carga**

En `admin_dashboard.html` línea 5, agregar `, viewport-fit=cover` al content del viewport.

Después del `<link>` de `niddo-brand.css` (línea 10), agregar:

```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/niddo-mobile.css') }}">
    <script src="{{ url_for('static', filename='js/niddo-mobile.js') }}" defer></script>
```

- [ ] **Step 3: CSS del layout**

Dentro del `@media` de `niddo-mobile.css`:

```css
    /* ── Layout de admin ─────────────────────────────────────────────────
       El sidebar de 220px sobre 360px de viewport deja 140px útiles. En
       mobile desaparece y su contenido se reparte entre la tab bar y la
       hoja de Más. */
    .nd-mobile .sidebar { display: none; }
    .nd-mobile .topbar {
        left: 0;
        padding: var(--safe-top) 12px 0;
        height: auto;
        flex-direction: column;
        align-items: stretch;
    }
    .nd-mobile .main {
        margin-left: 0;
        padding: calc(var(--safe-top) + 96px) 16px
                 calc(var(--tabbar-h) + var(--safe-bottom) + 16px);
        min-height: 100dvh;
    }
    /* Los botones de la topbar viven en la fila del título. */
    .nd-mobile .topbar-btn { position: absolute; top: var(--safe-top); right: 8px; }
```

- [ ] **Step 4: Verificar**

En `/admin` a **360 × 740**:

```javascript
JSON.stringify({
  sidebar: getComputedStyle(document.querySelector('.sidebar')).display,
  mainMargin: getComputedStyle(document.querySelector('.main')).marginLeft,
  scrollHorizontal: document.documentElement.scrollWidth > window.innerWidth
})
```

Esperado: `{"sidebar":"none","mainMargin":"0px","scrollHorizontal":false}`.

A **1440 × 900**: sidebar `flex`, `mainMargin` `220px`, topbar `left:220px`.

- [ ] **Step 5: Commit**

```bash
git add templates/admin_dashboard.html static/css/niddo-mobile.css
git commit -m "feat: layout mobile del panel de admin, que hasta ahora no tenia ninguno"
```

---

### Task 3: Tab bar y hoja de Más de admin

**Files:**
- Modify: `templates/admin_dashboard.html`

- [ ] **Step 1: Declarar la config**

En `admin_dashboard.html`, **antes** del `<script>` de `niddo-mobile.js` (que va con `defer`, pero la config tiene que existir cuando corre):

```html
    <script>
    window.NIDDO_MOBILE_CONFIG = {
        navFn: 'show',
        sectionPrefix: 'sec-',
        headerSelector: '.topbar',
        navPassesElement: true,
        usesHash: true,
        tabOf: {
            dashboard: 'hoy',
            cobros: 'cobros',
            gastos: 'gastos',
            consorcios: 'edificios',
            liquidaciones: 'mas', proveedores: 'mas', amenities: 'mas',
            balance: 'mas', mensajeria: 'mas', config: 'mas'
        },
        titles: {
            dashboard: 'Hoy', cobros: 'Cobros', gastos: 'Gastos',
            consorcios: 'Edificios', liquidaciones: 'Liquidaciones',
            proveedores: 'Proveedores', amenities: 'Amenities',
            balance: 'Balance', mensajeria: 'Mensajería', config: 'Configuración'
        },
        masItems: [
            { section: 'liquidaciones', label: 'Liquidaciones', icon: 'ic-liquidacion' },
            { section: 'proveedores',   label: 'Proveedores',   icon: 'ic-proveedor' },
            { section: 'amenities',     label: 'Amenities',     icon: 'ic-reserva' },
            { section: 'balance',       label: 'Balance',       icon: 'ic-balance' },
            { section: 'mensajeria',    label: 'Mensajería',    icon: 'ic-mensaje' },
            { section: 'config',        label: 'Configuración', icon: 'ic-config' }
        ]
    };
    </script>
```

- [ ] **Step 2: Markup de la tab bar**

Justo antes de `<div class="main">`:

```html
<nav class="bottom-nav nd-tabbar">
    <button class="bottom-btn active" data-tab="hoy" onclick="show('dashboard')"><span class="bottom-btn-icon"><svg class="ic"><use href="#ic-panel"></use></svg></span><span>Hoy</span></button>
    <button class="bottom-btn" data-tab="cobros" onclick="show('cobros')"><span class="bottom-btn-icon"><svg class="ic"><use href="#ic-cobro"></use></svg></span><span>Cobros</span></button>
    <button class="bottom-btn" data-tab="gastos" onclick="show('gastos')"><span class="bottom-btn-icon"><svg class="ic"><use href="#ic-expensa"></use></svg></span><span>Gastos</span></button>
    <button class="bottom-btn" data-tab="edificios" onclick="show('consorcios')"><span class="bottom-btn-icon"><svg class="ic"><use href="#ic-edificio"></use></svg></span><span>Edificios</span></button>
    <button class="bottom-btn" data-tab="mas" onclick="NiddoMobile.openMas()"><span class="bottom-btn-icon"><svg class="ic"><use href="#ic-mas"></use></svg></span><span>Más</span></button>
</nav>
```

La `.bottom-nav` no existe en el CSS de admin, así que sus estilos base también hay que agregarlos al `@media` (posición fija, `display:flex`, borde superior). Copiar de la declaración base del vecino.

- [ ] **Step 3: Verificar**

```javascript
JSON.stringify(['dashboard','cobros','gastos','consorcios','liquidaciones','proveedores','amenities','balance','mensajeria','config']
  .map(s => { show(s); const a=document.querySelector('.nd-tabbar .bottom-btn.active');
              return [s, document.getElementById('sec-'+s).classList.contains('active'), a?a.dataset.tab:null]; }))
```

Esperado: las 10 en `true`, con `dashboard→hoy`, `cobros→cobros`, `gastos→gastos`, `consorcios→edificios` y las 6 restantes → `mas`.

Tocar Más → sube la hoja con los 6 ítems.

- [ ] **Step 4: Commit**

```bash
git add templates/admin_dashboard.html static/css/niddo-mobile.css
git commit -m "feat: tab bar de 5 items y hoja de Mas en el panel de admin"
```

---

### Task 4: El botón atrás reacciona

Cierra el defecto #2: `show()` ya escribe el hash pero no hay listener, así que volver cambia la URL sin cambiar la vista.

**Files:**
- Modify: `static/js/niddo-mobile.js`

- [ ] **Step 1: Listener de `hashchange` con guarda de re-entrancia**

En `niddo-mobile.js`, dentro del `DOMContentLoaded`, después de `wrapNav()`:

```javascript
        if (usesHash) {
            /* show() escribe el hash, lo que dispara hashchange, que
               llamaría a show() otra vez: sin la guarda es un bucle. */
            window.addEventListener('hashchange', function () {
                var name = location.hash.slice(1);
                if (!name || !TAB_OF[name]) return;
                var actual = document.querySelector('.section.active');
                if (actual && actual.id === sectionPrefix + name) return;
                restoring = true;
                try { window[navFn](name); } finally { restoring = false; }
            });
        }
```

La comparación con la sección activa es la segunda defensa: aunque el hash cambie, si ya estamos en esa sección no se re-navega.

- [ ] **Step 2: Verificar que no hay bucle y que el atrás funciona**

En `/admin` a **360 × 740**:

```javascript
(() => new Promise(async res => {
  const esperar = ms => new Promise(r=>setTimeout(r,ms));
  const traza = [];
  show('cobros'); await esperar(150);
  show('gastos'); await esperar(150);
  history.back(); await esperar(300);
  traza.push(['1er atras', location.hash, document.querySelector('.section.active').id]);
  history.back(); await esperar(300);
  traza.push(['2do atras', location.hash, document.querySelector('.section.active').id]);
  res(JSON.stringify(traza));
}))()
```

Esperado: `#cobros` / `sec-cobros`, después `#dashboard` (o vacío) / `sec-dashboard`. **Consola sin errores y sin señales de recursión.**

En el vecino (`/`), confirmar que `usesHash` es `false` y su atrás sigue andando como antes.

- [ ] **Step 3: Commit**

```bash
git add static/js/niddo-mobile.js
git commit -m "fix: en admin el boton atras cambiaba la URL sin cambiar la vista"
```

---

### Task 5: Los 17 modales como sheets

Debería ser verificación, no implementación: admin usa `.modal-overlay` + `.modal-box`, las mismas clases que el vecino, así que el CSS ya escrito aplica solo.

**Files:**
- Modify: `static/css/niddo-mobile.css` (sólo si aparece alguna diferencia)

- [ ] **Step 1: Verificar los 17**

```javascript
JSON.stringify({
  overlays: document.querySelectorAll('.modal-overlay').length,
  grabbers: document.querySelectorAll('.nd-grabber').length,
  wide: document.querySelectorAll('.modal-box.wide').length,
  muestra: (openModal('modal-gasto'), (() => {
      const p = document.querySelector('#modal-gasto .modal-box'), r = p.getBoundingClientRect();
      return { ancho: Math.round(r.width), viewport: window.innerWidth,
               pegadoAbajo: Math.round(window.innerHeight - r.bottom),
               radio: getComputedStyle(p).borderTopLeftRadius };
  })())
})
```

Esperado: `overlays` = 17, `grabbers` = 17, y la muestra a ancho completo pegada abajo con radio 26px.

- [ ] **Step 2: Revisar la variante `.wide`**

`modal-box.wide` puede traer un `max-width` o `width` propio que pise el `width:100%` de la sheet. Verificar el valor computado de una `.wide` y, si desborda, agregar dentro del `@media`:

```css
    .nd-mobile .modal-box.wide { width: 100%; max-width: 100%; }
```

- [ ] **Step 3: Verificar a mano tres modales representativos**

`modal-gasto` (formulario largo), `modal-nueva-liq` (flujo de varios pasos) y `modal-ayuda` (sólo lectura): que suban desde abajo, que el arrastre del grabber las cierre, que scrollear el cuerpo **no** las cierre, y que ningún input dispare zoom.

- [ ] **Step 4: Commit**

```bash
git add static/css/niddo-mobile.css
git commit -m "feat: los 17 modales de admin suben como bottom sheets"
```

---

### Task 6: Los anchos inline que desbordan

8 elementos tienen `width` inline mayor a 360px, hasta 940px. Un atributo `style` le gana a cualquier hoja: se editan en el template.

**Files:**
- Modify: `templates/admin_dashboard.html`

- [ ] **Step 1: Listarlos**

```bash
grep -o 'style="[^"]*width:[0-9]\{3,\}px[^"]*"' templates/admin_dashboard.html | sort -u
```

- [ ] **Step 2: Convertir cada uno**

Patrón: `width:940px` → `width:100%;max-width:940px`. En escritorio queda igual (el contenedor es más ancho que el max-width); en mobile se adapta.

- [ ] **Step 3: Verificar**

A **360 × 740**, recorrer las 10 secciones y confirmar `document.documentElement.scrollWidth <= window.innerWidth` en todas, salvo donde haya tablas todavía sin convertir (Tasks 7 y 10).

A **1440 × 900**: los 8 elementos conservan su ancho original.

- [ ] **Step 4: Commit**

```bash
git add templates/admin_dashboard.html
git commit -m "fix: 8 anchos inline de hasta 940px desbordaban la pantalla en mobile"
```

---

### Task 7: Cobros y gastos como listas

Las dos tablas más consultadas: 10 y 9 columnas.

**Files:**
- Modify: `templates/admin_dashboard.html`
- Modify: `static/css/niddo-mobile.css`

**Interfaces:**
- Consumes: `.nd-list`, `.nd-row`, `.nd-row-ic`, `.nd-row-main`, `.nd-row-t`, `.nd-row-s`, `.nd-row-amt` del sub-proyecto 1.

- [ ] **Step 1: Extender la regla que oculta tablas**

El vecino usa `.table`; admin usa `.tbl`. Dentro del `@media`:

```css
    .nd-mobile .card .tbl,
    .nd-mobile .table-wrap .table { display: none; }
```

- [ ] **Step 2: Emitir la lista en el generador de cobros**

Localizar la función que llena el `<tbody>` de cobros (`grep -n "tbody-cobros\|tb-cobros" templates/admin_dashboard.html`) y, después del `innerHTML`, agregar el bloque `.nd-list` con la misma fuente de datos. Campos: unidad, vecino, período, total, estado.

**Antes de escribir, confirmar los nombres de campo contra los `<td>` que la función ya emite.** En el sub-proyecto 1, cuatro nombres asumidos resultaron equivocados.

- [ ] **Step 3: Ídem para gastos**

Campos: descripción, proveedor, categoría, monto, fecha, estado de aprobación.

- [ ] **Step 4: Verificar**

Por cada tabla, que la cantidad de `.nd-row` coincida con la de `<tr>` de datos, que la `.tbl` esté en `display:none`, y que no haya scroll horizontal a 360px. A 1440px, las tablas se ven con todas sus columnas y las `.nd-list` ocultas.

- [ ] **Step 5: Commit**

```bash
git add templates/admin_dashboard.html static/css/niddo-mobile.css
git commit -m "feat: cobros y gastos se leen como listas en mobile"
```

---

### Task 8: Cargar un gasto con foto

La única tarea donde el teléfono le gana a la computadora.

**Files:**
- Modify: `templates/admin_dashboard.html`
- Modify: `static/css/niddo-mobile.css`

- [ ] **Step 1: CSS del botón**

```css
    .nd-camera {
        display: flex; align-items: center; gap: 14px;
        width: 100%; padding: 19px; margin-bottom: 12px;
        border: none; border-radius: 20px;
        background: linear-gradient(145deg, var(--nd-terracota), var(--nd-terracota-hondo));
        box-shadow: 0 5px 18px rgba(196, 80, 43, .28);
        font-family: var(--font); text-align: left; cursor: pointer;
        transition: transform .12s;
    }
    .nd-camera:active { transform: scale(.97); }
    .nd-camera-ic {
        width: 46px; height: 46px; flex-shrink: 0; border-radius: 15px;
        background: rgba(255,255,255,.2);
        display: flex; align-items: center; justify-content: center;
    }
    .nd-camera-ic .ic { width: 25px; height: 25px; color: #fff; }
    .nd-camera b { display: block; color: #fff; font-size: 1rem; font-weight: 800; }
    .nd-camera span { display: block; color: rgba(255,255,255,.86); font-size: .79rem; font-weight: 600; }
```

- [ ] **Step 2: Markup, arriba de todo en la sección de gastos**

```html
<button class="nd-camera" onclick="document.getElementById('nd-gasto-foto').click()">
    <span class="nd-camera-ic"><svg class="ic"><use href="#ic-subir"></use></svg></span>
    <span><b>Cargar gasto con foto</b><span>Sacale una foto a la factura</span></span>
</button>
<input type="file" id="nd-gasto-foto" accept="image/*" capture="environment" style="display:none"
       onchange="abrirGastoConFoto(this.files[0])">
```

`capture="environment"` abre la cámara trasera directamente en vez del selector de archivos.

- [ ] **Step 3: Conectar con el flujo de gasto existente**

`abrirGastoConFoto(file)` tiene que abrir `modal-gasto` con el archivo ya adjunto. Revisar cómo `modal-gasto` recibe hoy su comprobante (probablemente un `<input type="file">` propio) y asignar el `File` mediante un `DataTransfer`:

```javascript
function abrirGastoConFoto(file) {
    if (!file) return;
    openModal('modal-gasto');
    var destino = document.querySelector('#modal-gasto input[type="file"]');
    if (destino) {
        var dt = new DataTransfer();
        dt.items.add(file);
        destino.files = dt.files;
        destino.dispatchEvent(new Event('change', { bubbles: true }));
    }
}
```

El `dispatchEvent` es necesario para que corra la previsualización o la extracción automática que ya exista.

- [ ] **Step 4: Verificar**

El botón sólo aparece en mobile. Al elegir una imagen, `modal-gasto` sube como sheet con el archivo adjunto y el nombre visible. A 1440px el botón no existe.

- [ ] **Step 5: Commit**

```bash
git add templates/admin_dashboard.html static/css/niddo-mobile.css
git commit -m "feat: cargar un gasto sacandole foto a la factura desde el telefono"
```

---

### Task 9: El prorrateo como tarjetas

La tarea más grande. Cierra el defecto #3. Va acá y no antes para llegar con todos los primitivos ya probados.

**Files:**
- Modify: `templates/admin_dashboard.html` (`loadProrrateo`, línea ~2747)
- Modify: `static/css/niddo-mobile.css`

**Interfaces:**
- Consumes: los campos que `loadProrrateo` ya usa: `p.unidades_funcionales.{numero,piso,vecino_nombre}`, `p.saldo_anterior`, `p.pago_realizado`, `p.saldo_pendiente`, `p.interes_mora`, `p.porcentaje_a`, `p.expensa_a`, `p.porcentaje_c`, `p.adicional_ordinaria`, `p.gastos_particulares`, `p.total_unidad`, `p.unidad_id`.

- [ ] **Step 1: CSS de las tarjetas**

Copiar el bloque `.pro-head`, `.pcard`, `.pcard-h`, `.pcard-uf`, `.pcard-n`, `.pcard-tot`, `.pcard-arr`, `.pcard-body`, `.pgroup`, `.pline`, `.pcard-foot` desde `docs/mockups/admin-mobile.html`, dentro del `@media` y con los nombres de token del brand.

- [ ] **Step 2: Encabezado de control**

Es lo que reemplaza la lectura de la grilla. Se calcula sobre **todos** los registros, no sobre los visibles:

```javascript
    const sumaA = data.reduce((a,p) => a + (p.porcentaje_a||0), 0);
    const sumaC = data.reduce((a,p) => a + (p.porcentaje_c||0), 0);
    const total = data.reduce((a,p) => a + (p.total_unidad||0), 0);
    const enMora = data.filter(p => (p.saldo_pendiente||0) > 0).length;
    const cierraA = Math.abs(sumaA - 100) < 0.01;
    const cierraC = Math.abs(sumaC - 100) < 0.01;
```

Los chips de suma van en verde si cierran y en terracota si no. **Ese es el punto entero del encabezado:** que un prorrateo mal calculado se vea sin desplegar ninguna tarjeta.

- [ ] **Step 3: Las tarjetas**

Una por UF, plegada por defecto, con los cuatro grupos adentro. Los porcentajes como chip al lado del monto que generan. El botón de previsualizar en el pie.

- [ ] **Step 4: Orden y filtro**

Chips *Por unidad · Mayor a menor · Sólo mora* que reordenan o filtran el arreglo y vuelven a renderizar.

- [ ] **Step 5: Verificar que no se perdió ninguna columna**

```javascript
(() => { const c = document.querySelector('.pcard'); c.querySelector('.pcard-h').click();
  return JSON.stringify({
    enElHeader: c.querySelector('.pcard-h').innerText.replace(/\n/g,' | '),
    lineas: [...c.querySelectorAll('.pline')].map(l=>l.innerText.replace(/\n/g,' ')),
    accion: !!c.querySelector('.pcard-foot button')
  }); })()
```

Esperado: UF, copropietario y piso en el header; 8 líneas (saldo anterior, pago, saldo pendiente, interés, ordinaria con %, adicional con %, particulares, total); y la acción presente. **Total: 14 de 14.**

Verificar además que la suma de los totales de las tarjetas coincide con el total del encabezado.

- [ ] **Step 6: Verificar con datos reales — no se salta**

Esta pantalla se juzga con una liquidación real de 24 UFs, no con datos inventados. Es la única donde el volumen cambia el veredicto. Si el usuario no puede proveerla, dejar la tarea marcada como verificada sólo parcialmente y decirlo, en vez de darla por buena.

- [ ] **Step 7: Commit**

```bash
git add templates/admin_dashboard.html static/css/niddo-mobile.css
git commit -m "feat: el prorrateo de 14 columnas se lee como tarjetas plegables en mobile"
```

---

### Task 10: El resto de las tablas

**Files:**
- Modify: `templates/admin_dashboard.html`
- Modify: `static/css/niddo-mobile.css`

- [ ] **Step 1: Cuatro tablas más como listas**

Consorcios (6 col), UFs (7), proveedores (6), liquidaciones (6). Mismo patrón de la Task 7, reusando `.nd-list` / `.nd-row`.

- [ ] **Step 2: Fallback para las 10 restantes**

Rubros, envíos, resultados de extracción, errores de importación y demás viven dentro de flujos de nivel 3. No se convierten; se encierran para que no rompan la página:

```css
    /* Estas viven dentro de flujos que no son para el teléfono. No se
       convierten: sólo se evita que desborden la página. Aceptado en el
       spec §7.4. */
    .nd-mobile .card > .tbl { display: table; }
    .nd-mobile .nd-tabla-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
```

Envolver cada una en `<div class="nd-tabla-scroll">`.

- [ ] **Step 3: Verificar**

Que ninguna sección haga scrollear la **página** en horizontal. Las tablas de nivel 3 scrollean dentro de su contenedor.

- [ ] **Step 4: Commit**

```bash
git add templates/admin_dashboard.html static/css/niddo-mobile.css
git commit -m "feat: cuatro tablas mas como listas y contencion del resto"
```

---

### Task 11: Barrido final y criterios

**Files:**
- Modify: `static/css/niddo-mobile.css`

- [ ] **Step 1: Detalle**

KPIs a una columna, `.page-header` apilado, chips de filtro con scroll horizontal, targets ≥44px en la topbar.

- [ ] **Step 2: Los 9 criterios del spec**

| # | Criterio | Cómo |
|---|---|---|
| 1 | 10 secciones alcanzables | Recorrerlas con `show()` |
| 2 | Sin scroll horizontal de página | `scrollWidth <= innerWidth` en las 10 |
| 3 | Atrás retrocede | `history.back()` cambia la vista |
| 4 | 14 columnas presentes | El chequeo de la Task 9 |
| 5 | Gasto con foto de punta a punta | A mano |
| 6 | 17 sheets arrastrables | Contar grabbers, probar 3 |
| 7 | Targets ≥44px, sin `:hover` | Filtrar por `getBoundingClientRect().height < 44` |
| 8 | **Escritorio de admin idéntico** | Recorrer las 10 a 1440px |
| 9 | **El vecino sigue igual** | Recorrer sus 9 secciones en mobile y escritorio |

Anotar en el commit cualquier criterio que no se cumpla, en vez de darlo por bueno.

- [ ] **Step 3: Commit**

```bash
git add static/css/niddo-mobile.css
git commit -m "feat: barrido final del panel de admin en mobile"
```

---

## Self-review del plan

**Cobertura del spec:** los 11 pasos de §8 mapean a las Tasks 1–11. Los 3 defectos de §1 se cierran en Tasks 2, 4 y 9. Los 9 criterios de §11 se verifican en la Task 11.

**Consistencia:** `CFG`, `navFn`, `sectionPrefix`, `headerSelector`, `navPassesEl`, `usesHash` se definen en la Task 1 y se consumen con esos nombres en 3 y 4. `.nd-list` / `.nd-row*` vienen del sub-proyecto 1 y se reusan en 7, 9 y 10.

**Desviación del spec, deliberada:** §7.1 proponía que cada template declarara su config. Se cambió a defaults = vecino, para no tocar el template que está en producción. Documentado arriba.

**Deuda conocida:**
- Los defaults del vecino viven dentro de `niddo-mobile.js`. Con un tercer consumidor conviene sacarlos.
- 10 de las 17 tablas quedan con `overflow-x:auto` en vez de convertirse. Aceptado en el spec §7.4.
- La Task 9 no se puede verificar del todo sin una liquidación real de 24 UFs.
