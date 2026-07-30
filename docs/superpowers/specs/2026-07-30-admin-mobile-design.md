# Rediseño mobile del panel de administrador

**Fecha:** 2026-07-30
**Estado:** pendiente de aprobación
**Sub-proyecto:** 2 de 3 (el 1 —fundación + vecino— está mergeado en `main`)
**Prototipo aprobado:** `docs/mockups/admin-mobile.html`

---

## 1. Problema

`admin_dashboard.html` son 166 KB con **cero media queries**. En un teléfono no hay degradación: hay un layout de escritorio servido tal cual.

| Qué | Estado |
|---|---|
| Sidebar | `position:fixed; width:220px`, siempre visible |
| `.main` | `margin-left:220px` — a 360px de ancho quedan 140px útiles |
| `.topbar` | `position:fixed; left:220px` |
| Tablas | 17, con 3 a 4 columnas la más chica y **14 la más grande** |
| Modales | 17 |
| Anchos fijos inline | 19, de los cuales **8 superan los 360px** (el mayor: 940px) |

Tres defectos concretos:

1. **El panel es inusable en un teléfono.** No es "se ve apretado": con `margin-left:220px` sobre 360px de viewport, el contenido vive en una franja de 140px con scroll horizontal permanente.
2. **El botón atrás cambia la URL y no pasa nada.** `show()` escribe `window.location.hash` (línea 1240) y hay restauración desde el hash **sólo al cargar la página** (líneas 1207 y 3001). No hay listener de `hashchange` ni de `popstate`. Al volver, la URL retrocede y la vista se queda quieta: el administrador aprieta atrás, no ve reacción, aprieta de nuevo, y termina saliendo del panel.
3. **La tabla de prorrateo tiene 14 columnas.** `UF · Piso · Copropietario · Sdo.Ant. · Pago · Sdo.Pend. · Int. · %A · Exp.A · %C · Adic.Ord. · Particulares · Total · Acción`. Es una planilla de cálculo, no una tabla.

## 2. Alcance

**Entra:**
- `templates/admin_dashboard.html`: layout mobile, tab bar, historial, generadores de fila de las tablas priorizadas, anchos inline que desbordan.
- `static/css/niddo-mobile.css` y `static/js/niddo-mobile.js`: se extienden con lo que admin necesita y el vecino no tenía.

**No entra:**
- Sub-proyecto 3: `proveedor_dashboard.html`, `login.html`, `index.html`.
- Cualquier cambio al layout de escritorio de admin.
- PWA, offline, notificaciones push.
- Infraestructura de tests.

## 3. Los tres niveles de tarea

Decidido con el usuario el 2026-07-30. No todas las tareas de administración son iguales en un teléfono:

**Nivel 1 — el teléfono es mejor que la computadora.**
- **Cargar un gasto sacándole foto a la factura.** Estás parado frente al proveedor; hoy eso obliga a volver al escritorio.
- Ver KPIs: consorcios activos, gastos sin aprobar, UFs en mora.
- Aprobar una reserva de amenity.
- Enviar un comunicado.

**Nivel 2 — consulta sí, edición no urgente.**
- Listados de consorcios, UFs, proveedores, cobros, historial de liquidaciones.
- Se leen como listas con el detalle en sheet. Editar desde el teléfono es posible pero incómodo, y no es lo que se va a hacer parado en la calle.

**Nivel 3 — las tareas pesadas.**
- Prorrateo, generar liquidación, carga en lote de comprobantes, importar padrón.

**Decisión del usuario sobre el nivel 3:** rediseñar el prorrateo para mobile, no esconderlo ni dejarlo con scroll horizontal. Se le señaló que es la opción más cara y la que más riesgo tiene de perder legibilidad; la eligió igual. Ver §5.

## 4. Arquitectura de información

Las 10 secciones (`dashboard, consorcios, gastos, cobros, proveedores, balance, mensajeria, config, amenities, liquidaciones`) se reorganizan en 5 tabs:

| Tab | Contiene | Por qué |
|---|---|---|
| **Hoy** | KPIs + lo que requiere acción: gastos sin aprobar, reservas por confirmar, liquidación en curso, mora del día | Es la pregunta que un administrador se hace al abrir el teléfono |
| **Cobros** | Cobros y mora del período | Lo que más se consulta fuera del escritorio |
| **Gastos** | Con el botón de *cargar gasto con foto* arriba de todo | La única tarea nivel 1 pura |
| **Edificios** | Consorcios → UFs → vecinos, navegación push de tres niveles | Consulta jerárquica |
| **Más** | Liquidaciones, proveedores, amenities, balance, mensajería, configuración | Todo lo demás |

Mensajería hoy es un placeholder (*"estará disponible en la próxima versión"*). Se deja en Más con ese mismo estado; este spec no la implementa.

## 5. El prorrateo

La pieza central y la más riesgosa. Las 14 columnas no son 14 cosas sueltas: son cuatro grupos.

| Grupo | Columnas originales |
|---|---|
| Identidad | UF · Piso · Copropietario |
| Arrastre del período anterior | Sdo.Ant. → Pago → Sdo.Pend. → Int. |
| Expensa del período | %A → Exp.A · %C → Adic.Ord. |
| Extras y resultado | Particulares · **Total** |

Cada UF pasa a ser una **tarjeta plegada** que muestra unidad, copropietario, porcentaje ordinario y total. Al tocarla se despliega con los cuatro grupos completos. Los porcentajes van como chip al lado del monto que generan (`Ordinaria 16,67% · $148.363`), que es la relación que en la grilla quedaba a seis columnas de distancia.

**Ninguna de las 14 columnas se pierde.** La acción de previsualizar vive en el pie de la tarjeta desplegada.

**Lo que sí se pierde, y hay que decirlo:** la comparación entre unidades. La grilla existe para barrer 24 filas de un vistazo, cazar el outlier y confirmar que los porcentajes cierran en 100%. Una tarjeta por vez no hace eso. Se compensa con:

1. **Encabezado de control** — total del período, suma de %A, suma de %C y cuántas UFs están en mora. Es el chequeo que se hacía barriendo la grilla, precalculado. Si una suma no da 100,00% se muestra en terracota.
2. **Orden y filtro** — *Por unidad · Mayor a menor · Sólo mora*.
3. **Borde terracota** en las UFs con saldo pendiente, para encontrarlas sin leer números.

**Criterio de aceptación específico:** si al usarlo con datos reales de 24 UFs la compensación no alcanza, la salida es agregar un modo "tabla" opcional con scroll horizontal, disponible sólo en esa pantalla. No se implementa ahora — se decide después de que el usuario lo pruebe con una liquidación real.

## 6. Qué se reusa de la fundación y qué no

La fundación del sub-proyecto 1 paga, pero no todo sale gratis. Inventario honesto:

| Primitivo | Estado |
|---|---|
| Safe areas, tap-highlight, `touch-action` | ✅ **Gratis** — ya son globales dentro del `@media` |
| **Bottom sheets** | ✅ **Gratis** — admin usa `.modal-overlay` + `.modal-box`, las mismas clases que el vecino. Los 17 modales se convierten sin escribir CSS |
| Inputs a 16px | ✅ **Gratis** — y admin no tiene `font-size` inline en ningún campo de formulario, así que la regla alcanza sola |
| Snackbars, targets ≥44px, `100dvh` | ✅ **Gratis** — cuelgan de `.nd-mobile` |
| Tab bar | ⚠️ **Generalizar** — el CSS está scopeado a `#nd-tabbar` y el JS a `TAB_OF`, ambos con las secciones del vecino |
| Título grande y colapso | ⚠️ **Adaptar** — apunta a `.app-header`; admin usa `.topbar`, con otra geometría |
| `.nd-list` / `.nd-row` | ⚠️ **Extender** — la regla que oculta tablas dice `.table`; admin usa `.tbl` |
| Hoja de "Más" | ⚠️ **Parametrizar** — `MAS_ITEMS` está hardcodeado con las secciones del vecino |
| Historial | ⚠️ **Distinto** — el vecino no escribía hash y hubo que agregarlo; admin ya lo escribe pero le falta el listener |
| Tarjetas de prorrateo | ❌ **Nuevo** |
| Captura de gasto con foto | ❌ **Nuevo** |

La conclusión operativa: **la fundación deja de ser específica del vecino.** Los mapas de secciones, títulos e ítems de Más pasan a ser configuración que cada template declara, en vez de constantes dentro del JS.

## 7. Arquitectura técnica

Mismo principio que el sub-proyecto 1: **aditivo y reversible**, sin reescribir los 166 KB.

### 7.1 La fundación se parametriza

`niddo-mobile.js` deja de traer las secciones del vecino adentro. Cada template declara su configuración antes de cargar el script:

```html
<script>
window.NIDDO_MOBILE_CONFIG = {
    navFn: 'show',            /* la función de navegación del template */
    sectionPrefix: 'sec-',    /* el vecino usa 'section-' */
    tabs: [ /* … */ ],
    titles: { /* … */ },
    masItems: [ /* … */ ]
};
</script>
```

El vecino recibe la suya con exactamente los valores que hoy están hardcodeados, así que su comportamiento no cambia. **Eso hay que verificarlo explícitamente:** el sub-proyecto 1 ya está en producción y esta refactorización lo toca.

### 7.2 `show(id, el)` tiene dos parámetros

A diferencia de `showSection(name)`, la de admin recibe el elemento clickeado para marcar el `.nav-link` activo. Los botones de la tab bar no lo pasan. El wrapper debe llamar `original(id, undefined)`, que es seguro: la función hace `if (el) el.classList.add('active')`. En mobile el sidebar está oculto, así que no marcar el link no tiene efecto visible.

### 7.3 El historial

`show()` ya hace `window.location.hash = id`, que crea entrada de historial. Falta el listener que reaccione al volver:

- Agregar `hashchange` (o `popstate`) que llame a `show(hash)`.
- **Guarda de re-entrancia obligatoria:** `show()` escribe el hash, lo que dispara `hashchange`, que llamaría a `show()` otra vez. Sin bandera, es un bucle. Se usa el mismo patrón `restoring` del sub-proyecto 1.

### 7.4 Las tablas

17 tablas es demasiado para convertirlas todas. Se priorizan por uso real en teléfono:

| Prioridad | Tabla | Columnas |
|---|---|---|
| 1 | Cobros | 10 |
| 2 | Gastos | 9 |
| 3 | **Prorrateo** | **14** |
| 4 | Consorcios | 6 |
| 5 | UFs | 7 |
| 6 | Proveedores | 6 |
| 7 | Liquidaciones | 6 |

Las 10 restantes (rubros, envíos, resultados de extracción, errores de importación, etc.) viven dentro de flujos de nivel 3 que no son el foco. Para esas se aplica el fallback: **contenedor con `overflow-x:auto`**, que evita que rompan el layout de la página aunque no sean cómodas. Está explícitamente aceptado.

### 7.5 Los anchos inline que desbordan

8 elementos tienen `width` inline mayor a 360px (hasta 940px). Un atributo `style` le gana a cualquier hoja, así que se editan en el template: `width:940px` → `width:100%; max-width:940px`. Es el mismo arreglo que se hizo en los dos inputs de búsqueda del vecino.

### 7.6 Breakpoint

900px, el mismo. Admin no tiene ninguno hoy, así que no hay nada que reconciliar.

## 8. Orden de implementación

1. **Parametrizar la fundación** y verificar que el vecino —que está en producción— sigue igual.
2. **Layout base de admin en mobile**: ocultar sidebar, `.main` sin margen, `.topbar` adaptada. *Acá se cierra el defecto #1.*
3. **Tab bar y hoja de Más** con la configuración de admin.
4. **Historial con `hashchange`** y guarda de re-entrancia. *Cierra el defecto #2.*
5. **Los 17 modales como sheets** — verificación, porque el CSS ya debería aplicar solo.
6. **Anchos inline que desbordan** — los 8 mayores a 360px.
7. **Tablas 1 y 2** (cobros, gastos) como listas.
8. **Captura de gasto con foto.**
9. **El prorrateo como tarjetas.** *Cierra el defecto #3.* Es la tarea más grande; va al final para llegar con los primitivos ya probados.
10. **Tablas 4 a 7** como listas, y `overflow-x:auto` para las 10 restantes.
11. **Barrido final** y repaso de criterios.

Cada paso es un commit atómico y deja la app funcionando.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| **Romper el vecino, que ya está en producción**, al parametrizar la fundación | Es el riesgo más serio de este sub-proyecto. El paso 1 es exclusivamente esa refactorización, con verificación del vecino en los 4 viewports antes de seguir |
| El prorrateo en tarjetas resulta ilegible con 24 UFs | Encabezado de control + orden + filtro. Si no alcanza, modo tabla opcional (§5) |
| Romper el escritorio de admin | Todo el CSS dentro de `@media(max-width:900px)`; el JS sale temprano |
| El `hashchange` entra en bucle con `show()` | Guarda `restoring`, patrón ya probado en el sub-proyecto 1 |
| 17 modales es mucha superficie para que algo falle | El CSS es el mismo que ya funciona en el vecino; el paso 5 es verificación, no implementación |
| Sin tests, una regresión pasa desapercibida | Verificación manual por paso. Limitación real del repo que este trabajo no resuelve |

## 10. Verificación

No hay framework de tests y este trabajo no introduce uno.

- **Viewports:** 360×740, 390×844, 412×892, 820×1180 y **1440×900** (regresión de escritorio, obligatoria en cada paso).
- **Referencia visual:** `docs/mockups/admin-mobile.html`.
- **Regresión del vecino:** obligatoria en el paso 1 y en el barrido final, porque está en producción.
- **El prorrateo se verifica con una liquidación real**, no con datos inventados. Es la única pantalla donde el volumen (24 UFs) cambia el juicio sobre si el diseño sirve.

## 11. Criterios de éxito

1. Las 10 secciones son alcanzables desde el teléfono.
2. Ninguna pantalla requiere scroll horizontal a 360px, salvo las 10 tablas de nivel 3 con `overflow-x:auto`, que scrollean dentro de su contenedor sin romper la página.
3. El botón atrás retrocede de sección en vez de cambiar la URL sin efecto.
4. Las 14 columnas del prorrateo siguen presentes y legibles, y el encabezado de control permite confirmar que los porcentajes cierran sin desplegar ninguna tarjeta.
5. Se puede cargar un gasto con foto de la factura de punta a punta.
6. Los 17 modales suben como sheets y se pueden arrastrar para cerrar.
7. Ningún elemento interactivo mide menos de 44px ni depende de `:hover`.
8. **El escritorio de admin a 1440px es indistinguible del actual.**
9. **El dashboard del vecino sigue funcionando igual que antes de parametrizar la fundación**, en mobile y en escritorio.
