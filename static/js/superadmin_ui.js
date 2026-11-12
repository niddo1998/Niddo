/* Centro de control: lo que hace que el panel se sienta vivo.
 *
 * No pinta datos: sólo acompaña lo que pintan superadmin.html y
 * superadmin_negocio.js (saludo, título de cada sección, números que cuentan
 * hasta su valor, barras que crecen en orden). Si el sistema pide menos
 * movimiento, los números aparecen directo.
 */
(() => {
    const quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const $ = (id) => document.getElementById(id);

    /* ── Saludo y fecha ── */
    const h = new Date().getHours();
    const nombre = $('saludo').dataset.nombre;
    $('saludo').textContent = `${h < 6 ? 'Buenas noches' : h < 13 ? 'Buen día' : h < 20 ? 'Buenas tardes' : 'Buenas noches'}${nombre ? ', ' + nombre : ''}`;
    $('fecha-hoy').textContent = new Date().toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' });

    /* ── Título de cada sección ── */
    const SECCIONES = {
        hoy:             ['Resumen', 'Cómo viene Niddo hoy, de un vistazo.'],
        finanzas:        ['Finanzas', 'Caja, suscripciones y cobros del mes.'],
        comercial:       ['Comercial', 'Metas, pipeline, planes y cómo cobramos.'],
        aprobaciones:    ['Aprobaciones', 'Administraciones que piden entrar a Niddo.'],
        administradores: ['Administradores', 'Todas las administraciones y cómo usan Niddo.'],
        vecinos:         ['Vecinos', 'Quiénes se registraron y en qué edificio.'],
        auditoria:       ['Auditoría', 'Quién dio o quitó acceso, y quién miró qué cuenta.'],
    };
    function titular(sec) {
        const [t, b] = SECCIONES[sec] || [];
        if (!t) return;
        for (const [id, txt] of [['titulo-seccion', t], ['bajada-seccion', b]]) {
            const el = $(id);
            el.textContent = txt;
            el.classList.remove('cambia'); void el.offsetWidth; el.classList.add('cambia');
        }
        document.title = `${t} · Niddo`;
        window.scrollTo({ top: 0, behavior: quieto ? 'auto' : 'smooth' });
    }
    document.querySelectorAll('.tab[data-sec]').forEach((t) => t.addEventListener('click', () => titular(t.dataset.sec)));
    document.title = 'Resumen · Niddo';

    /* ── Chip de pendientes: espejo del contador de Aprobaciones ── */
    const badge = $('badge-aprob');
    const chip = $('chip-pendientes');
    const espejar = () => {
        const n = parseInt(badge.textContent, 10) || 0;
        chip.hidden = badge.classList.contains('cero') || n === 0;
        $('chip-pendientes-txt').textContent = n === 1 ? '1 administración espera tu OK' : `${n} administraciones esperan tu OK`;
    };
    new MutationObserver(espejar).observe(badge, { childList: true, characterData: true, subtree: true, attributes: true });
    chip.addEventListener('click', () => document.querySelector('.tab[data-sec="aprobaciones"]').click());
    espejar();

    /* ── Números que cuentan hasta su valor ── */
    // Respeta el formato argentino que ya trae el texto: «$ 1.250.000», «2,3 meses».
    const NUM = /-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?/;
    function contar(el) {
        if (quieto || el.dataset.contado) return;
        const nodo = [...el.childNodes].find((n) => n.nodeType === 3 && NUM.test(n.textContent));
        if (!nodo) return;
        el.dataset.contado = '1';
        const original = nodo.textContent;
        const m = original.match(NUM);
        const decimales = (m[0].split(',')[1] || '').length;
        const fin = parseFloat(m[0].replace(/\./g, '').replace(',', '.'));
        if (!isFinite(fin) || fin === 0) return;
        const fmt = (v) => v.toLocaleString('es-AR', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
        const dur = Math.min(1400, 600 + Math.log10(Math.abs(fin) + 1) * 140);
        const t0 = performance.now();
        const paso = (t) => {
            const p = Math.min(1, (t - t0) / dur);
            const e = 1 - Math.pow(1 - p, 4);
            nodo.textContent = original.replace(m[0], fmt(fin * e));
            if (p < 1) requestAnimationFrame(paso); else nodo.textContent = original;
        };
        requestAnimationFrame(paso);
    }

    /* ── Barras del gráfico, de a una ── */
    function escalonar(svg) {
        svg.querySelectorAll('rect').forEach((r, i) => { r.style.animationDelay = `${Math.min(i * 22, 700)}ms`; });
    }

    // Todo lo que se pinta pasa por acá: se engancha una sola vez y alcanza
    // también lo que se vuelve a pintar después de cada acción.
    const raiz = document.querySelector('.principal');
    new MutationObserver((cambios) => {
        for (const c of cambios) {
            for (const n of c.addedNodes) {
                if (n.nodeType !== 1) continue;
                if (n.matches('.kpi .valor, .grande')) contar(n);
                n.querySelectorAll?.('.kpi .valor, .grande').forEach(contar);
                if (n.tagName === 'rect') escalonar(n.ownerSVGElement);
            }
        }
    }).observe(raiz, { childList: true, subtree: true });
    document.querySelectorAll('.kpi .valor').forEach(contar);
})();
