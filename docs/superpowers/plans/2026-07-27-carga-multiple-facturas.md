# Carga múltiple de facturas — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir subir varios comprobantes de una sola vez y crear un gasto por cada uno, con su comprobante adjunto, tras un único paso de revisión en tabla editable.

**Architecture:** Todo el cambio vive en el bloque `<script>` de `templates/admin_dashboard.html` y en el markup del modal `modal-auto-extract`. El navegador llama a `POST /api/gastos/extract` una vez por archivo, en secuencia, y luego a `POST /api/gastos` una vez por gasto tildado. El backend no se toca.

**Tech Stack:** Flask + Jinja2 (servidor), JavaScript vanilla embebido en el template (cliente), Groq Vision vía el endpoint existente. Sin framework de tests: la verificación es `node --check` sobre el JS extraído más un arnés HTML manejado desde el navegador.

## Global Constraints

- Solo se modifica `templates/admin_dashboard.html`. El backend no cambia.
- Máximo 10 archivos por lote (`AUTO_MAX_FILES = 10`).
- Máximo 10 MB por archivo (`AUTO_MAX_SIZE = 10 * 1024 * 1024`).
- Un solo consorcio para todo el lote, tomado de `$('auto-consorcio').value`.
- El guardado de gastos es **secuencial**, nunca en paralelo.
- La columna "Pagado" arranca **destildada** en todas las filas.
- La columna "✓ incluir" arranca **tildada** solo en filas sin error.
- Categorías válidas, exactamente estas 11: `electricidad`, `gas`, `agua`, `limpieza`, `ascensor`, `seguro`, `honorarios`, `impuesto`, `mantenimiento`, `sueldos`, `otro`.
- Helpers existentes que se reutilizan: `$(id)` = `getElementById`, `toast(msg, type)` con `type` en `'ok'|'warn'|'err'`, `openModal(id)`, `closeModal(id)`, `loadGastos()`.
- El repositorio no tiene framework de tests. No inventar uno ni agregar dependencias.

---

## Estructura de archivos

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `templates/admin_dashboard.html` | Markup del modal `modal-auto-extract` (líneas ~793-849) y la sección JS `// ── Auto-extraction ──` (líneas ~1602-1735) | Modificar |
| `<scratchpad>/check-js.sh` | Extrae el `<script>` del template, neutraliza Jinja, corre `node --check` | Crear (no se commitea) |
| `<scratchpad>/harness.html` | Arnés de verificación: markup del modal + funciones reales + stubs de red | Crear (no se commitea) |
| `<scratchpad>/build-harness.sh` | Regenera `harness.html` extrayendo las funciones reales del template | Crear (no se commitea) |

`<scratchpad>` es `/private/tmp/claude-501/-Users-santiagodespontin-Niddo/293d4155-23ca-420b-8545-f8bc9be70167/scratchpad`.

Los archivos de verificación viven en el scratchpad y **no se commitean**: el repositorio no tiene infraestructura de tests y agregarla excede el alcance de este cambio.

---

### Task 1: Selección múltiple de archivos

Deja la app funcionando: la extracción sigue andando con el primer archivo mediante un shim que la Task 2 reemplaza.

**Files:**
- Modify: `templates/admin_dashboard.html` (markup ~800-818, JS ~1602-1653)
- Create: `<scratchpad>/check-js.sh`

**Interfaces:**
- Consumes: `$`, `toast`, existentes en el template.
- Produces:
  - `autoFilesSelected: File[]` — reemplaza a `autoFileSelected`
  - `escHtml(s: any) => string`
  - `handleAutoFiles(input: HTMLInputElement) => void`
  - `addAutoFiles(fileList: FileList|File[]) => void`
  - `removeAutoFile(idx: number) => void`
  - `renderAutoFileList() => void`
  - Constantes `AUTO_MAX_FILES`, `AUTO_MAX_SIZE`

- [ ] **Step 1: Crear el verificador de sintaxis**

Crear `<scratchpad>/check-js.sh`:

```bash
#!/bin/bash
# Extrae el bloque <script> de admin_dashboard.html, neutraliza las expresiones
# Jinja ({{ user.name | tojson }}) y valida la sintaxis del JS resultante.
set -e
TPL=/Users/santiagodespontin/Niddo/Niddo/templates/admin_dashboard.html
OUT="$(dirname "$0")/extracted.js"
awk '/<script>/{flag=1;next} /<\/script>/{flag=0} flag' "$TPL" \
  | sed 's/{{[^}]*}}/"stub"/g' > "$OUT"
LINES=$(wc -l < "$OUT")
if [ "$LINES" -lt 500 ]; then
  echo "ERROR: la extraccion devolvio solo $LINES lineas, algo falló"; exit 1
fi
node --check "$OUT" && echo "SINTAXIS OK ($LINES lineas)"
```

Hacerlo ejecutable: `chmod +x <scratchpad>/check-js.sh`

- [ ] **Step 2: Correr el verificador sobre el código sin tocar**

Run: `<scratchpad>/check-js.sh`
Expected: `SINTAXIS OK (~1400 lineas)`. Esto establece la línea base: si falla acá, el problema es el extractor, no el código.

- [ ] **Step 3: Actualizar el markup de subida**

En `templates/admin_dashboard.html`, dentro de `<div id="auto-step-upload">`:

Reemplazar el `<input>` del dropzone para aceptar varios archivos:

```html
<input type="file" id="auto-file-input" accept="image/*,.pdf" multiple style="display:none;" onchange="handleAutoFiles(this)">
```

Reemplazar el bloque `<div id="auto-file-preview" ...>...</div>` completo por la lista:

```html
<div id="auto-file-list" style="display:none;margin-top:14px;"></div>
```

Reemplazar el botón de extracción para que tenga un label actualizable:

```html
<button class="btn-p" id="auto-extract-btn" onclick="extractGastosData()" style="width:100%;margin-top:10px;" disabled>
    <svg class="ic ic-sm"><use href="#ic-rayo"></use></svg><span id="auto-extract-btn-label">Extraer datos del comprobante</span>
</button>
```

- [ ] **Step 4: Reemplazar el estado y las funciones de selección**

En la sección `// ── Auto-extraction ──`, reemplazar las dos declaraciones de estado:

```js
let autoExtractedData = null;
let autoFileSelected = null;
```

por:

```js
const AUTO_MAX_FILES = 10;
const AUTO_MAX_SIZE = 10 * 1024 * 1024;
const escHtml = s => String(s ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let autoExtractedResults = [];
let autoFilesSelected = [];
```

Reemplazar `handleAutoFile` y `clearAutoFile` completas por:

```js
function handleAutoFiles(input) {
    addAutoFiles(input.files);
    input.value = '';
}

function addAutoFiles(fileList) {
    const incoming = Array.from(fileList || []);
    for (const f of incoming) {
        if (autoFilesSelected.length >= AUTO_MAX_FILES) {
            toast(`Máximo ${AUTO_MAX_FILES} comprobantes por lote`, 'warn');
            break;
        }
        if (f.size > AUTO_MAX_SIZE) { toast(`${f.name} supera los 10MB`, 'warn'); continue; }
        if (autoFilesSelected.some(x => x.name === f.name && x.size === f.size)) continue;
        autoFilesSelected.push(f);
    }
    renderAutoFileList();
}

function removeAutoFile(idx) {
    autoFilesSelected.splice(idx, 1);
    renderAutoFileList();
}

function renderAutoFileList() {
    const list = $('auto-file-list');
    const n = autoFilesSelected.length;
    if (!n) {
        list.style.display = 'none';
        list.innerHTML = '';
    } else {
        list.style.display = 'block';
        list.innerHTML = autoFilesSelected.map((f, i) => `
            <div style="padding:10px 14px;background:rgba(47,111,94,.08);border-radius:10px;display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                <span style="color:var(--nd-verde)"><svg class="ic ic-sm"><use href="#ic-pagado"></use></svg></span>
                <span style="font-size:.85rem;font-weight:500;flex:1;">${escHtml(f.name)}</span>
                <button onclick="removeAutoFile(${i})" style="background:none;border:none;cursor:pointer;color:var(--muted);"><svg class="ic ic-sm"><use href="#ic-cerrar"></use></svg></button>
            </div>`).join('');
    }
    $('auto-extract-btn').disabled = n === 0;
    $('auto-extract-btn-label').textContent = n > 1
        ? `Extraer datos de ${n} comprobantes`
        : 'Extraer datos del comprobante';
}
```

Reemplazar `resetAutoExtract` completa por:

```js
function resetAutoExtract() {
    autoExtractedResults = [];
    autoFilesSelected = [];
    $('auto-file-input').value = '';
    ['auto-step-upload','auto-step-processing','auto-step-results','auto-step-error'].forEach(id => $(id).style.display = 'none');
    $('auto-step-upload').style.display = '';
    renderAutoFileList();
}
```

- [ ] **Step 5: Actualizar el drop del dropzone**

Dentro de `openAutoExtract`, reemplazar la línea `dz.ondrop = ...` por:

```js
    dz.ondrop = (e) => {
        e.preventDefault();
        dz.style.borderColor='var(--border)'; dz.style.background='var(--card)';
        if (e.dataTransfer.files.length) addAutoFiles(e.dataTransfer.files);
    };
```

- [ ] **Step 6: Poner el shim para no romper la extracción**

En `extractGastoData`, reemplazar las dos referencias a `autoFileSelected`:

```js
    if (!autoFilesSelected.length) { toast('Seleccioná un archivo primero', 'warn'); return; }
```

y

```js
        fd.append('file', autoFilesSelected[0]);
```

En `confirmAutoExtract`, reemplazar:

```js
    const file = autoFilesSelected[0];
```

Este shim desaparece en la Task 2.

- [ ] **Step 7: Verificar sintaxis**

Run: `<scratchpad>/check-js.sh`
Expected: `SINTAXIS OK`. Si falla, corregir antes de seguir — un error de sintaxis acá rompe todo el panel de administración.

- [ ] **Step 8: Commit**

```bash
cd /Users/santiagodespontin/Niddo/Niddo
git add templates/admin_dashboard.html
git commit -m "feat: permite seleccionar varios comprobantes en la carga automática"
```

---

### Task 2: Extracción secuencial con progreso

**Files:**
- Modify: `templates/admin_dashboard.html` (markup del paso processing ~820-824, JS `extractGastoData`)

**Interfaces:**
- Consumes: `autoFilesSelected`, `escHtml` (Task 1).
- Produces:
  - `extractOne(file: File, consorcioId: string) => Promise<object>` — lanza `Error` con el mensaje del backend si falla
  - `extractGastosData() => Promise<void>` — reemplaza a `extractGastoData`
  - `autoExtractedResults: BatchResult[]` donde `BatchResult = { file: File, data: object|null, error: string|null, incluir: boolean, pagado: boolean }`
  - Depende de `renderBatchResults()` que define la Task 3; hasta entonces se usa un stub temporal.

- [ ] **Step 1: Agregar el indicador de progreso al markup**

En `<div id="auto-step-processing" ...>`, reemplazar el párrafo secundario para que sea actualizable:

```html
<p id="auto-progress" style="font-size:.82rem;color:var(--muted);margin:0;">La IA está extrayendo los datos. Esto puede tardar unos segundos.</p>
```

- [ ] **Step 2: Reemplazar `extractGastoData` por el loop**

Borrar la función `extractGastoData` completa (desde `async function extractGastoData() {` hasta su llave de cierre, incluyendo todo el armado del `auto-results-grid` y el manejo del paso de error) y poner en su lugar:

```js
async function extractOne(file, consorcioId) {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('consorcio_id', consorcioId);
    const r = await fetch('/api/gastos/extract', { method: 'POST', body: fd });
    if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.error || `Error ${r.status} al extraer datos`);
    }
    return r.json();
}

async function extractGastosData() {
    if (!autoFilesSelected.length) { toast('Seleccioná al menos un archivo', 'warn'); return; }
    if (!$('auto-consorcio').value) { toast('Seleccioná un consorcio', 'warn'); return; }

    const consorcioId = $('auto-consorcio').value;
    const total = autoFilesSelected.length;
    autoExtractedResults = [];

    $('auto-step-upload').style.display = 'none';
    $('auto-step-processing').style.display = '';

    for (let i = 0; i < total; i++) {
        const file = autoFilesSelected[i];
        $('auto-progress').textContent = `Analizando ${i + 1} de ${total} — ${file.name}`;
        try {
            const data = await extractOne(file, consorcioId);
            autoExtractedResults.push({ file, data, error: null, incluir: true, pagado: false });
        } catch (e) {
            autoExtractedResults.push({ file, data: null, error: e.message, incluir: false, pagado: false });
        }
    }

    $('auto-step-processing').style.display = 'none';
    renderBatchResults();
    $('auto-step-results').style.display = '';
}
```

- [ ] **Step 3: Stub temporal de `renderBatchResults`**

Agregar justo debajo, para que la Task 2 sea verificable por sí sola. La Task 3 lo reemplaza por la implementación real:

```js
function renderBatchResults() {
    console.log('renderBatchResults stub', autoExtractedResults);
}
```

- [ ] **Step 4: Verificar sintaxis**

Run: `<scratchpad>/check-js.sh`
Expected: `SINTAXIS OK`

- [ ] **Step 5: Verificar el loop secuencial contra la API real**

Crear `<scratchpad>/test_loop.py` y correrlo. Prueba la premisa central del diseño: N llamadas secuenciales funcionan y cada una devuelve JSON válido.

```python
import os, sys, time, base64, json
sys.path.insert(0, '/Users/santiagodespontin/Niddo/Niddo')
os.chdir('/Users/santiagodespontin/Niddo/Niddo')
from dotenv import load_dotenv
load_dotenv()
from groq import Groq
import fitz

client = Groq(api_key=os.environ['GROQ_API_KEY'])
PROMPT = ('Analizá esta factura y devolvé SOLO un JSON con: descripcion, monto, '
          'categoria, fecha_gasto, fecha_vencimiento, notas.')

def make_pdf(path, texto):
    doc = fitz.open(); page = doc.new_page()
    page.insert_text((72, 72), texto); doc.save(path)

archivos = []
for nombre, texto in [
    ('luz',  'FACTURA EDESUR - Monto: $15430.50 - Vto: 15/08/2026'),
    ('gas',  'FACTURA METROGAS - Monto: $8200.00 - Vto: 20/08/2026'),
    ('agua', 'FACTURA AYSA - Monto: $4100.00 - Vto: 25/08/2026'),
]:
    p = f'/tmp/test_{nombre}.pdf'
    make_pdf(p, texto)
    archivos.append(p)

t0 = time.time()
for i, path in enumerate(archivos, 1):
    with open(path, 'rb') as f:
        pdf = fitz.open(stream=f.read(), filetype='pdf')
    png = pdf[0].get_pixmap(dpi=200).tobytes('png')
    b64 = base64.b64encode(png).decode('utf-8')
    ti = time.time()
    completion = client.chat.completions.create(
        model='qwen/qwen3.6-27b',
        messages=[{'role': 'user', 'content': [
            {'type': 'text', 'text': PROMPT},
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}},
        ]}],
        response_format={'type': 'json_object'},
        max_completion_tokens=1024,
    )
    data = json.loads(completion.choices[0].message.content)
    print(f'{i}/3 {path} -> {round(time.time()-ti,2)}s -> {data}')

print('TOTAL:', round(time.time() - t0, 2), 's')
```

Run: `python3 <scratchpad>/test_loop.py`
Expected: las 3 líneas imprimen JSON parseado sin excepción, cada llamada entre 3 y 8 segundos, total por debajo de 25s. Confirma que el rate limit del plan gratuito no se toca con un lote de 3.

- [ ] **Step 6: Commit**

```bash
cd /Users/santiagodespontin/Niddo/Niddo
git add templates/admin_dashboard.html
git commit -m "feat: extrae los comprobantes del lote en secuencia con progreso visible"
```

---

### Task 3: Tabla de revisión editable

**Files:**
- Modify: `templates/admin_dashboard.html` (markup `auto-step-results` y `auto-step-error` ~826-846, JS)
- Create: `<scratchpad>/build-harness.sh`, `<scratchpad>/harness.html`

**Interfaces:**
- Consumes: `autoExtractedResults`, `extractOne`, `escHtml`.
- Produces:
  - `renderBatchResults() => void` — reemplaza al stub de la Task 2
  - `setResultField(idx: number, field: string, value: string) => void`
  - `setResultFlag(idx: number, flag: 'incluir'|'pagado', checked: boolean) => void`
  - `updateConfirmButton() => void`
  - `retryExtraction(idx: number) => Promise<void>`
  - Constantes `AUTO_CATEGORIAS: string[]`, `AUTO_CAT_LABELS: Record<string,string>`
  - Depende de `confirmBatchExtract()` que define la Task 4; hasta entonces se usa un stub temporal.

- [ ] **Step 1: Ensanchar el modal**

En `<div class="modal-overlay" id="modal-auto-extract">`, reemplazar el estilo del `modal-box`:

```html
<div class="modal-box" style="max-width:940px;">
```

- [ ] **Step 2: Reemplazar el markup de resultados y borrar el paso de error global**

Reemplazar el bloque completo `<div id="auto-step-results" ...>...</div>` **y** el bloque completo `<div id="auto-step-error" ...>...</div>` por:

```html
            <!-- Step 3: Results -->
            <div id="auto-step-results" style="display:none;">
                <div style="background:rgba(47,111,94,.08);border-radius:10px;padding:14px 18px;margin-bottom:16px;">
                    <p style="margin:0;font-size:.85rem;font-weight:600;color:var(--teal);"><svg class="ic ic-sm"><use href="#ic-pagado"></use></svg><span id="auto-results-title"></span></p>
                    <p style="margin:4px 0 0;font-size:.78rem;color:var(--muted);">Revisá y corregí los datos antes de cargar.</p>
                </div>
                <div style="overflow-x:auto;">
                    <table class="tbl" id="tbl-auto-results">
                        <thead><tr>
                            <th style="width:34px;"></th>
                            <th>Descripción</th><th>Monto</th><th>Categoría</th>
                            <th>Fecha</th><th>Vencimiento</th><th style="width:64px;">Pagado</th>
                        </tr></thead>
                        <tbody id="tbody-auto-results"></tbody>
                    </table>
                </div>
                <div style="display:flex;gap:10px;margin-top:18px;">
                    <button class="btn-s" onclick="resetAutoExtract()" style="flex:1;"><svg class="ic ic-sm"><use href="#ic-volver"></use></svg>Empezar de nuevo</button>
                    <button class="btn-s" onclick="closeModal('modal-auto-extract');openGastoModal()" style="flex:1;"><svg class="ic ic-sm"><use href="#ic-editar"></use></svg>Cargar manualmente</button>
                    <button class="btn-p" id="auto-confirm-btn" onclick="confirmBatchExtract()" style="flex:1;"><svg class="ic ic-sm"><use href="#ic-pagado"></use></svg><span id="auto-confirm-label">Cargar gastos</span></button>
                </div>
            </div>
```

El paso de error global desaparece porque los errores ahora son por fila. La escotilla de "Cargar manualmente" se preserva en el pie de la tabla.

- [ ] **Step 3: Sacar `auto-step-error` de `resetAutoExtract`**

En `resetAutoExtract`, reemplazar la línea del `forEach` por:

```js
    ['auto-step-upload','auto-step-processing','auto-step-results'].forEach(id => $(id).style.display = 'none');
```

- [ ] **Step 4: Agregar las constantes de categorías**

Junto a `AUTO_MAX_FILES`, agregar:

```js
const AUTO_CATEGORIAS = ['electricidad','gas','agua','limpieza','ascensor','seguro',
                         'honorarios','impuesto','mantenimiento','sueldos','otro'];
const AUTO_CAT_LABELS = {electricidad:'Electricidad', gas:'Gas', agua:'Agua',
    limpieza:'Limpieza', ascensor:'Ascensor', seguro:'Seguro', honorarios:'Honorarios',
    impuesto:'Impuesto', mantenimiento:'Mantenimiento', sueldos:'Sueldos', otro:'Otro'};
```

- [ ] **Step 5: Reemplazar el stub por la implementación real**

Borrar el stub `renderBatchResults` de la Task 2 y poner:

```js
function renderBatchResults() {
    const total = autoExtractedResults.length;
    const ok = autoExtractedResults.filter(r => !r.error).length;
    const fallidos = total - ok;
    $('auto-results-title').textContent = fallidos
        ? `${ok} de ${total} comprobantes analizados (${fallidos} con error)`
        : `${ok} comprobante${ok === 1 ? '' : 's'} analizado${ok === 1 ? '' : 's'}`;

    $('tbody-auto-results').innerHTML = autoExtractedResults.map((r, i) => {
        if (r.error) {
            return `<tr style="background:rgba(192,86,58,.07);">
                <td></td>
                <td colspan="5" style="font-size:.8rem;color:var(--nd-terracota-hondo);">
                    <strong>${escHtml(r.file.name)}</strong> — ${escHtml(r.error)}
                </td>
                <td style="text-align:center;"><button class="btn-s btn-sm" onclick="retryExtraction(${i})">Reintentar</button></td>
            </tr>`;
        }
        const d = r.data;
        const cats = AUTO_CATEGORIAS.map(c =>
            `<option value="${c}"${d.categoria === c ? ' selected' : ''}>${AUTO_CAT_LABELS[c]}</option>`).join('');
        return `<tr>
            <td><input type="checkbox" ${r.incluir ? 'checked' : ''} onchange="setResultFlag(${i},'incluir',this.checked)"></td>
            <td><input class="form-ctrl" style="min-width:180px;" value="${escHtml(d.descripcion)}" oninput="setResultField(${i},'descripcion',this.value)"></td>
            <td><input class="form-ctrl" type="number" step="0.01" style="width:115px;" value="${d.monto ?? ''}" oninput="setResultField(${i},'monto',this.value)"></td>
            <td><select class="form-ctrl" style="width:145px;" onchange="setResultField(${i},'categoria',this.value)">${cats}</select></td>
            <td><input class="form-ctrl" type="date" style="width:150px;" value="${d.fecha_gasto || ''}" oninput="setResultField(${i},'fecha_gasto',this.value)"></td>
            <td><input class="form-ctrl" type="date" style="width:150px;" value="${d.fecha_vencimiento || ''}" oninput="setResultField(${i},'fecha_vencimiento',this.value)"></td>
            <td style="text-align:center;"><input type="checkbox" ${r.pagado ? 'checked' : ''} onchange="setResultFlag(${i},'pagado',this.checked)"></td>
        </tr>`;
    }).join('');

    updateConfirmButton();
}

function setResultField(idx, field, value) {
    autoExtractedResults[idx].data[field] = value;
}

function setResultFlag(idx, flag, checked) {
    autoExtractedResults[idx][flag] = checked;
    if (flag === 'incluir') updateConfirmButton();
}

function updateConfirmButton() {
    const n = autoExtractedResults.filter(r => !r.error && r.incluir).length;
    $('auto-confirm-btn').disabled = n === 0;
    $('auto-confirm-label').textContent = n === 1 ? 'Cargar 1 gasto' : `Cargar ${n} gastos`;
}

async function retryExtraction(idx) {
    const r = autoExtractedResults[idx];
    r.error = 'Reintentando…';
    renderBatchResults();
    try {
        r.data = await extractOne(r.file, $('auto-consorcio').value);
        r.error = null;
        r.incluir = true;
    } catch (e) {
        r.data = null;
        r.error = e.message;
        r.incluir = false;
    }
    renderBatchResults();
}
```

- [ ] **Step 6: Stub temporal de `confirmBatchExtract`**

Borrar la función `confirmAutoExtract` completa y poner:

```js
function confirmBatchExtract() {
    console.log('confirmBatchExtract stub', autoExtractedResults.filter(r => r.incluir));
}
```

- [ ] **Step 7: Verificar sintaxis**

Run: `<scratchpad>/check-js.sh`
Expected: `SINTAXIS OK`

- [ ] **Step 8: Construir el arnés de verificación**

Crear `<scratchpad>/build-harness.sh`:

```bash
#!/bin/bash
# Genera harness.html: extrae las funciones REALES de la seccion Auto-extraction
# del template y las carga con stubs, para poder ejercitar la tabla sin login.
set -e
TPL=/Users/santiagodespontin/Niddo/Niddo/templates/admin_dashboard.html
DIR="$(dirname "$0")"
awk '/\/\/ ── Auto-extraction/{flag=1} /^function openGastoModal/{flag=0} flag' "$TPL" > "$DIR/auto.js"
LINES=$(wc -l < "$DIR/auto.js")
if [ "$LINES" -lt 50 ]; then echo "ERROR: extraccion vacia ($LINES lineas)"; exit 1; fi

# Markup del modal: desde la apertura del modal auto-extract hasta el comentario
# que abre el modal siguiente. No se puede cortar en el primer </div> porque los
# divs están anidados.
awk '/<div class="modal-overlay" id="modal-auto-extract">/{flag=1} /<!-- Modal Gasto -->/{flag=0} flag' "$TPL" > "$DIR/modal.html"
if [ ! -s "$DIR/modal.html" ]; then echo "ERROR: no se extrajo el markup del modal"; exit 1; fi

cat > "$DIR/harness.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>Arnés carga múltiple</title>
<style>
 .tbl{font-size:.82rem;width:100%;border-collapse:collapse}
 .tbl th{font-size:.67rem;font-weight:600;text-transform:uppercase;padding:8px 13px;text-align:left}
 .tbl td{padding:9px 13px;border-bottom:1px solid #ddd}
 .form-ctrl{padding:4px 6px;border:1px solid #ccc;border-radius:6px}
 .modal-overlay{display:block!important}.ic{display:none}
 body{font-family:system-ui;padding:20px}
</style>
<div id="toasts"></div>
<div id="harness-modal"></div>
<script>
// ── Stubs del entorno real ──────────────────────────────────────────────
const $ = id => document.getElementById(id);
const toast = (msg, type='ok') => { console.log('[toast:'+type+']', msg); window.__toasts.push({msg,type}); };
window.__toasts = [];
function openModal(id){ console.log('openModal', id); }
function closeModal(id){ console.log('closeModal', id); }
async function loadGastos(){ console.log('loadGastos'); }
function openGastoModal(){ console.log('openGastoModal'); }
const consorcios = [{id:'c1', nombre:'Edificio Test'}];

// fetch simulado: controlable desde la consola con window.__fetchMode
window.__fetchCalls = [];
window.__fetchMode = 'ok';
window.fetch = async (url, opts) => {
    window.__fetchCalls.push({url, body: opts && opts.body});
    if (window.__fetchMode === 'fail')
        return { ok:false, status:500, json: async () => ({error:'Error simulado de la IA'}) };
    if (url.includes('/extract'))
        return { ok:true, json: async () => ({descripcion:'Factura de prueba', monto:15430.5,
            categoria:'electricidad', fecha_gasto:'2026-07-05', fecha_vencimiento:'2026-08-15',
            notas:'nro 12345'}) };
    return { ok:true, json: async () => ({id:'g1'}) };
};

// Helper para armar resultados sin pasar por la red
window.seedResults = (n, conError=0) => {
    autoExtractedResults = [];
    for (let i=0;i<n;i++){
        const file = new File(['x'], `factura_${i+1}.pdf`, {type:'application/pdf'});
        if (i < conError) autoExtractedResults.push({file, data:null, error:'No se pudo leer', incluir:false, pagado:false});
        else autoExtractedResults.push({file, data:{descripcion:`Factura ${i+1}`, monto:1000*(i+1),
            categoria:'electricidad', fecha_gasto:'2026-07-05', fecha_vencimiento:'2026-08-15', notas:''},
            error:null, incluir:true, pagado:false});
    }
    renderBatchResults();
    $('auto-step-results').style.display = '';
};
</script>
<script src="./modal-inject.js"></script>
<script src="./auto.js"></script>
HTML

# Inyecta el markup del modal antes de cargar auto.js
python3 - "$DIR" <<'PY'
import sys, json, pathlib
d = pathlib.Path(sys.argv[1])
html = (d/'modal.html').read_text()
(d/'modal-inject.js').write_text(
    "document.getElementById('harness-modal').innerHTML = " + json.dumps(html) + ";\n")
PY

echo "Arnés generado en $DIR/harness.html ($LINES lineas de auto.js)"
```

Hacerlo ejecutable y correrlo: `chmod +x <scratchpad>/build-harness.sh && <scratchpad>/build-harness.sh`
Expected: `Arnés generado ... (>50 lineas de auto.js)`

- [ ] **Step 9: Verificar la tabla en el navegador**

Abrir el arnés con `preview_start` en `file://<scratchpad>/harness.html`.

Si el esquema `file://` no carga, agregar esta entrada a `.claude/launch.json` y abrirla con `preview_start {name:"harness"}` — nunca levantar el servidor con Bash:

```json
{
  "name": "harness",
  "runtimeExecutable": "python3",
  "runtimeArgs": ["-m", "http.server", "4600", "--directory",
                  "/private/tmp/claude-501/-Users-santiagodespontin-Niddo/293d4155-23ca-420b-8545-f8bc9be70167/scratchpad"],
  "port": 4600
}
```

Ya con el arnés abierto, correr `seedResults(3)` con `javascript_tool` y comprobar con `read_page`:

1. Se dibujan 3 filas.
2. El título dice `3 comprobantes analizados`.
3. El botón dice `Cargar 3 gastos` y está habilitado.
4. Los 3 checkboxes de "incluir" están tildados; los 3 de "Pagado" destildados.

Después correr `seedResults(3, 1)` y comprobar:

5. La primera fila muestra el nombre del archivo y el motivo del error, con botón "Reintentar".
6. El título dice `2 de 3 comprobantes analizados (1 con error)`.
7. El botón dice `Cargar 2 gastos`.

Después, con `javascript_tool`, destildar la primera fila válida:
`document.querySelectorAll('#tbody-auto-results input[type=checkbox]')[0].click()` y verificar que el botón pasa a `Cargar 1 gasto`.

Por último, editar un monto:
`setResultField(1,'monto','999'); autoExtractedResults[1].data.monto`
Expected: `'999'` — confirma que la edición inline llega al modelo.

- [ ] **Step 10: Commit**

```bash
cd /Users/santiagodespontin/Niddo/Niddo
git add templates/admin_dashboard.html
git commit -m "feat: tabla de revisión editable para el lote de comprobantes"
```

---

### Task 4: Guardado en lote

**Files:**
- Modify: `templates/admin_dashboard.html` (JS: reemplazar el stub `confirmBatchExtract`)

**Interfaces:**
- Consumes: `autoExtractedResults`, `updateConfirmButton`, `resetAutoExtract`, `loadGastos`.
- Produces:
  - `saveOneGasto(r: BatchResult, consorcioId: string) => Promise<object>`
  - `confirmBatchExtract() => Promise<void>` — reemplaza al stub de la Task 3

- [ ] **Step 1: Reemplazar el stub por la implementación real**

Borrar el stub `confirmBatchExtract` de la Task 3 y poner:

```js
async function saveOneGasto(r, consorcioId) {
    const d = r.data;
    const fd = new FormData();
    fd.append('consorcio_id', consorcioId);
    fd.append('monto', d.monto);
    fd.append('descripcion', (d.descripcion || '').trim());
    fd.append('categoria', d.categoria || '');
    fd.append('fecha_gasto', d.fecha_gasto || new Date().toISOString().split('T')[0]);
    fd.append('fecha_vencimiento', d.fecha_vencimiento || '');
    fd.append('pagado', r.pagado ? 'true' : 'false');
    fd.append('notas', d.notas || '');
    fd.append('comprobante', r.file);
    const resp = await fetch('/api/gastos', { method: 'POST', body: fd });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `Error ${resp.status}`);
    }
    return resp.json();
}

async function confirmBatchExtract() {
    const consorcioId = $('auto-consorcio').value;
    const pendientes = autoExtractedResults.filter(r => !r.error && r.incluir);
    if (!pendientes.length) { toast('No hay gastos para cargar', 'warn'); return; }

    const sinMonto = pendientes.filter(r => !r.data.monto || Number(r.data.monto) <= 0);
    if (sinMonto.length) {
        toast(`Completá el monto de: ${sinMonto.map(r => r.file.name).join(', ')}`, 'warn');
        return;
    }

    $('auto-confirm-btn').disabled = true;
    const fallidos = [];
    let guardados = 0;

    for (let i = 0; i < pendientes.length; i++) {
        $('auto-confirm-label').textContent = `Cargando ${i + 1} de ${pendientes.length}…`;
        try {
            await saveOneGasto(pendientes[i], consorcioId);
            guardados++;
        } catch (e) {
            fallidos.push(`${pendientes[i].file.name}: ${e.message}`);
        }
    }

    closeModal('modal-auto-extract');
    if (guardados) toast(guardados === 1 ? '1 gasto cargado' : `${guardados} gastos cargados`);
    if (fallidos.length) toast(`No se pudieron cargar — ${fallidos.join(' | ')}`, 'err');
    resetAutoExtract();
    await loadGastos();
}
```

`fecha_gasto` cae a la fecha de hoy cuando la IA no la detectó, porque `POST /api/gastos` inserta el string vacío tal cual en una columna de tipo fecha y falla.

- [ ] **Step 2: Verificar sintaxis**

Run: `<scratchpad>/check-js.sh`
Expected: `SINTAXIS OK`

- [ ] **Step 3: Regenerar el arnés**

Run: `<scratchpad>/build-harness.sh`
Expected: `Arnés generado`

- [ ] **Step 4: Verificar el guardado en el arnés**

Recargar el arnés, y con `javascript_tool`:

```js
seedResults(3);
$('auto-consorcio').innerHTML = '<option value="c1" selected>Edificio Test</option>';
window.__fetchCalls = [];
await confirmBatchExtract();
JSON.stringify({
  posts: window.__fetchCalls.filter(c => c.url === '/api/gastos').length,
  toasts: window.__toasts.map(t => t.msg)
})
```

Expected: `posts: 3` y un toast `3 gastos cargados`.

Después verificar que cada POST lleva su propio comprobante:

```js
window.__fetchCalls.filter(c => c.url === '/api/gastos')
  .map(c => c.body.get('comprobante').name)
```

Expected: `["factura_1.pdf","factura_2.pdf","factura_3.pdf"]` — cada gasto con el archivo que le corresponde, sin cruces.

Después el camino de fallas parciales:

```js
seedResults(2);
window.__toasts = [];
window.__fetchMode = 'fail';
await confirmBatchExtract();
window.__toasts.map(t => t.type + ': ' + t.msg)
```

Expected: un solo toast de tipo `err` que nombra los 2 archivos, y ningún toast de éxito.

Después la validación de monto:

```js
window.__fetchMode = 'ok';
seedResults(1);
autoExtractedResults[0].data.monto = '';
window.__toasts = []; window.__fetchCalls = [];
await confirmBatchExtract();
JSON.stringify({toasts: window.__toasts.map(t=>t.msg), posts: window.__fetchCalls.length})
```

Expected: toast que pide completar el monto y `posts: 0` — no se manda nada al backend.

- [ ] **Step 5: Commit**

```bash
cd /Users/santiagodespontin/Niddo/Niddo
git add templates/admin_dashboard.html
git commit -m "feat: carga en lote de los gastos extraídos con su comprobante"
```

---

### Task 5: Verificación final y despliegue

**Files:**
- Modify: ninguno salvo que aparezcan defectos.

- [ ] **Step 1: Repasar el flujo completo en el arnés**

Recargar el arnés y ejercitar la secuencia de punta a punta con `javascript_tool`:

```js
autoFilesSelected = [];
addAutoFiles([new File(['x'],'luz.pdf'), new File(['x'],'gas.pdf'), new File(['x'],'agua.pdf')]);
JSON.stringify({archivos: autoFilesSelected.length, label: $('auto-extract-btn-label').textContent})
```

Expected: `{"archivos":3,"label":"Extraer datos de 3 comprobantes"}`

Después probar el tope y los duplicados:

```js
autoFilesSelected = [];
addAutoFiles(Array.from({length:12}, (_,i) => new File(['x'], `f${i}.pdf`)));
addAutoFiles([new File(['x'],'f0.pdf')]);
autoFilesSelected.length
```

Expected: `10` — corta en el máximo y no duplica un archivo ya cargado.

Después quitar uno:

```js
removeAutoFile(0);
JSON.stringify({n: autoFilesSelected.length, primero: autoFilesSelected[0].name})
```

Expected: `{"n":9,"primero":"f1.pdf"}`

- [ ] **Step 2: Verificación de sintaxis final**

Run: `<scratchpad>/check-js.sh`
Expected: `SINTAXIS OK`

- [ ] **Step 3: Confirmar que no quedaron referencias viejas**

Run:
```bash
cd /Users/santiagodespontin/Niddo/Niddo
grep -n "autoFileSelected\|autoExtractedData\|confirmAutoExtract\|extractGastoData\b\|auto-file-preview\|auto-step-error\|auto-results-grid" templates/admin_dashboard.html
```
Expected: sin resultados. Cualquier coincidencia es un resto del código anterior que hay que sacar.

- [ ] **Step 4: Push y despliegue**

```bash
cd /Users/santiagodespontin/Niddo/Niddo
git push origin main
```

Vercel despliega solo con el push. No hacen falta variables de entorno nuevas: `GROQ_API_KEY` ya está configurada.

- [ ] **Step 5: Prueba en producción**

Con facturas reales, en el panel de administración: Nuevo gasto → Carga automática → subir 3 comprobantes → elegir consorcio → extraer → revisar la tabla → cargar. Confirmar en la tabla de gastos que aparecen los 3, cada uno con su comprobante adjunto abriendo el ícono de documento.
