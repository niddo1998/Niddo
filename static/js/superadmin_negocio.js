/* Panel del negocio: Comercial y Finanzas, dentro de /superadmin.
 *
 * Usa lo que ya define el script de superadmin.html ($, escapar, toast, CARGAR).
 * Todo lo de Finanzas lo valida el servidor: acá sólo se muestra el candado
 * cuando la API contesta 423.
 */
(() => {
    const pesos = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 });
    const plata = (n) => pesos.format(Number(n) || 0);
    const hoyISO = () => {
        const d = new Date();
        return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    };
    const fechaCorta = (iso) => iso ? new Date(iso + 'T12:00:00').toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric' }) : '';

    async function pedir(url, metodo = 'GET', cuerpo) {
        const opciones = { method: metodo, headers: {} };
        if (cuerpo !== undefined) {
            opciones.headers['Content-Type'] = 'application/json';
            opciones.body = JSON.stringify(cuerpo);
        }
        const r = await fetch(url, opciones);
        const json = await r.json().catch(() => ({}));
        return { ok: r.ok, status: r.status, json };
    }

    /* ── Formulario en modal, reutilizable ── */
    let alGuardar = null;
    function abrirForm(titulo, html, guardar) {
        $('n-form-titulo').textContent = titulo;
        $('n-form-cuerpo').innerHTML = html;
        alGuardar = guardar;
        $('n-overlay').classList.add('visible');
        $('n-form-cuerpo').querySelector('input, select, textarea')?.focus();
    }
    const cerrarForm = () => { $('n-overlay').classList.remove('visible'); alGuardar = null; };
    $('n-cancelar').addEventListener('click', cerrarForm);
    $('n-overlay').addEventListener('click', (e) => { if (e.target === $('n-overlay')) cerrarForm(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') cerrarForm(); });
    $('n-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!alGuardar) return;
        const boton = $('n-form').querySelector('button[type=submit]');
        boton.disabled = true;
        try { if (await alGuardar()) cerrarForm(); }
        finally { boton.disabled = false; }
    });
    const valor = (id) => $(id)?.value ?? '';

    // ══════════════════════════════════════════════════════════════════════
    // COMERCIAL
    // ══════════════════════════════════════════════════════════════════════
    let com = null;
    let filtroEtapa = 'abiertos';

    async function cargarComercial() {
        const r = await pedir('/api/superadmin/comercial');
        if (!r.ok) return toast(r.json.error || 'No pudimos cargar el plan comercial', true);
        com = r.json;
        pintarMetas();
        pintarPipeline();
        pintarPlanes();
        pintarConfigCobro();
        if (document.activeElement !== $('n-notas')) $('n-notas').value = com.notas || '';
    }

    /* ── Metas ── */
    function pintarMetas() {
        if (!com.metas.length) {
            $('n-metas').innerHTML = '<p class="ayuda">Todavía no hay metas. Poné dos o tres (por ejemplo, «10 administraciones activas para marzo») y el avance se calcula solo con los datos reales.</p>';
            return;
        }
        $('n-metas').innerHTML = com.metas.map((m) => `
            <div class="meta">
                <div class="paso-cab">
                    <span>${escapar(m.titulo)}${m.fecha_limite ? ` <span class="ayuda">· para el ${fechaCorta(m.fecha_limite)}</span>` : ''}</span>
                    <span><span class="n">${m.actual}</span> / ${m.objetivo}</span>
                </div>
                <div class="barra"><i class="${m.avance >= 100 ? 'lista' : ''}" style="width:${m.avance}%"></i></div>
            </div>`).join('');
    }

    function filaMeta(m = {}) {
        const opciones = Object.entries(com.metricas).map(([k, v]) =>
            `<option value="${k}" ${m.metrica === k ? 'selected' : ''}>${escapar(v)}</option>`).join('');
        return `<div class="plan-editor" data-meta>
            <label class="campo">Qué mide<select data-c="metrica">${opciones}</select></label>
            <label class="campo">Objetivo<input data-c="objetivo" inputmode="numeric" value="${m.objetivo ?? ''}"></label>
            <label class="campo">Para cuándo<input data-c="fecha_limite" type="date" value="${m.fecha_limite || ''}"></label>
            <label class="campo ancho-movil">Título (opcional)<input data-c="titulo" maxlength="120" value="${escapar(m.titulo || '')}"></label>
            <button type="button" class="btn-icono" data-quitar title="Quitar">✕</button>
        </div>`;
    }

    $('n-editar-metas').addEventListener('click', () => {
        abrirForm('Metas', `
            <p class="ayuda" style="margin-bottom:.8rem">El número actual sale de la base: sólo elegís qué medir y hasta dónde querés llegar.</p>
            <div id="n-lista-metas">${(com.metas.length ? com.metas : [{}]).map(filaMeta).join('')}</div>
            <button type="button" class="btn btn-fantasma" id="n-agregar-meta">+ Agregar meta</button>`,
        async () => {
            const metas = [...document.querySelectorAll('[data-meta]')].map((f) => Object.fromEntries(
                [...f.querySelectorAll('[data-c]')].map((i) => [i.dataset.c, i.value])));
            const r = await pedir('/api/superadmin/comercial/metas', 'PUT', { metas });
            if (!r.ok) { toast(r.json.error || 'No se pudo guardar', true); return false; }
            toast('Metas guardadas');
            await cargarComercial();
            return true;
        });
    });

    /* ── Pipeline ── */
    function pintarPipeline() {
        const ps = com.prospectos;
        const cuenta = (id) => ps.filter((p) => p.etapa === id).length;
        const abiertos = ps.filter((p) => !['cliente', 'perdido'].includes(p.etapa)).length;
        $('n-etapas').innerHTML =
            `<button class="etapa-chip ${filtroEtapa === 'abiertos' ? 'activa' : ''}" data-filtro="abiertos">En curso<b>${abiertos}</b></button>` +
            com.etapas.map((e) => `<button class="etapa-chip ${filtroEtapa === e.id ? 'activa' : ''}" data-filtro="${e.id}">${e.nombre}<b>${cuenta(e.id)}</b></button>`).join('') +
            `<button class="etapa-chip ${filtroEtapa === 'todos' ? 'activa' : ''}" data-filtro="todos">Todos<b>${ps.length}</b></button>`;

        const visibles = ps.filter((p) => filtroEtapa === 'todos' ? true
            : filtroEtapa === 'abiertos' ? !['cliente', 'perdido'].includes(p.etapa)
            : p.etapa === filtroEtapa);

        if (!ps.length) {
            $('n-pipeline').innerHTML = '<div class="vacio">Todavía no cargaste prospectos. Sumá las administraciones con las que estás hablando y seguí en qué etapa está cada una.</div>';
            return;
        }
        if (!visibles.length) { $('n-pipeline').innerHTML = '<div class="vacio">Nada en esta etapa.</div>'; return; }

        const hoy = hoyISO();
        $('n-pipeline').innerHTML = visibles.map((p) => {
            const opciones = com.etapas.map((e) => `<option value="${e.id}" ${p.etapa === e.id ? 'selected' : ''}>${e.nombre}</option>`).join('');
            const vencida = p.proxima_fecha && p.proxima_fecha < hoy && !['cliente', 'perdido'].includes(p.etapa);
            const tamaño = [p.consorcios ? `${p.consorcios} consorcios` : '', p.unidades ? `${p.unidades} unidades` : ''].filter(Boolean).join(' · ');
            return `<div class="ficha">
                <div class="quien">
                    <div class="nombre">${escapar(p.nombre)} <span class="pill ${p.etapa}">${escapar(com.etapas.find((e) => e.id === p.etapa)?.nombre || p.etapa)}</span></div>
                    <div class="detalle">${escapar([p.contacto, tamaño].filter(Boolean).join(' · '))}</div>
                    ${p.proxima_accion || p.proxima_fecha ? `<div class="proxima ${vencida ? 'vencida' : ''}">→ ${escapar(p.proxima_accion || 'Seguimiento')}${p.proxima_fecha ? ` · ${fechaCorta(p.proxima_fecha)}${vencida ? ' (atrasado)' : ''}` : ''}</div>` : ''}
                </div>
                <div class="acciones">
                    ${p.telefono ? `<a class="chip" href="https://wa.me/${escapar(p.telefono.replace(/\D/g, ''))}" target="_blank" rel="noopener">WhatsApp</a>` : ''}
                    ${p.email ? `<a class="chip" href="mailto:${escapar(p.email)}">Mail</a>` : ''}
                    <select class="etapa-sel" data-etapa="${p.id}" aria-label="Etapa">${opciones}</select>
                    <button class="btn btn-fantasma" data-editar-prospecto="${p.id}">Editar</button>
                </div>
            </div>`;
        }).join('');
    }

    $('n-etapas').addEventListener('click', (e) => {
        const b = e.target.closest('[data-filtro]');
        if (!b) return;
        filtroEtapa = b.dataset.filtro;
        pintarPipeline();
    });

    $('n-pipeline').addEventListener('change', async (e) => {
        const sel = e.target.closest('[data-etapa]');
        if (!sel) return;
        const r = await pedir(`/api/superadmin/comercial/prospectos/${sel.dataset.etapa}`, 'PATCH', { etapa: sel.value });
        if (!r.ok) return toast(r.json.error || 'No se pudo cambiar la etapa', true);
        toast('Etapa actualizada');
        await cargarComercial();
    });

    function formProspecto(p = {}) {
        const opciones = com.etapas.map((e) => `<option value="${e.id}" ${(p.etapa || 'contactado') === e.id ? 'selected' : ''}>${e.nombre}</option>`).join('');
        const v = (k) => escapar(p[k] ?? '');
        return `<div class="grilla">
            <label class="campo ancho">Administración *<input id="p-nombre" required maxlength="120" value="${v('nombre')}" placeholder="Administración Pérez"></label>
            <label class="campo">Contacto<input id="p-contacto" maxlength="120" value="${v('contacto')}" placeholder="Nombre"></label>
            <label class="campo">Teléfono<input id="p-telefono" maxlength="40" value="${v('telefono')}"></label>
            <label class="campo">Mail<input id="p-email" type="email" maxlength="160" value="${v('email')}"></label>
            <label class="campo">Etapa<select id="p-etapa">${opciones}</select></label>
            <label class="campo">Consorcios<input id="p-consorcios" inputmode="numeric" value="${p.consorcios || ''}"></label>
            <label class="campo">Unidades<input id="p-unidades" inputmode="numeric" value="${p.unidades || ''}"></label>
            <label class="campo ancho">Próxima acción<input id="p-accion" maxlength="200" value="${v('proxima_accion')}" placeholder="Mandar la demo, llamar el jueves…"></label>
            <label class="campo">Para cuándo<input id="p-fecha" type="date" value="${v('proxima_fecha')}"></label>
            <label class="campo ancho">Notas<textarea id="p-notas" rows="3" maxlength="2000">${v('notas')}</textarea></label>
        </div>
        ${p.id ? `<button type="button" class="btn btn-rechazar" id="p-borrar" style="margin-top:.9rem">Borrar prospecto</button>` : ''}`;
    }

    const datosProspecto = () => ({
        nombre: valor('p-nombre'), contacto: valor('p-contacto'), telefono: valor('p-telefono'),
        email: valor('p-email'), etapa: valor('p-etapa'), consorcios: valor('p-consorcios'),
        unidades: valor('p-unidades'), proxima_accion: valor('p-accion'),
        proxima_fecha: valor('p-fecha'), notas: valor('p-notas'),
    });

    $('n-nuevo-prospecto').addEventListener('click', () => abrirForm('Nuevo prospecto', formProspecto(), async () => {
        const r = await pedir('/api/superadmin/comercial/prospectos', 'POST', datosProspecto());
        if (!r.ok) { toast(r.json.error || 'No se pudo guardar', true); return false; }
        toast('Prospecto agregado');
        await cargarComercial();
        return true;
    }));

    $('n-pipeline').addEventListener('click', (e) => {
        const b = e.target.closest('[data-editar-prospecto]');
        if (!b) return;
        const p = com.prospectos.find((x) => x.id === b.dataset.editarProspecto);
        abrirForm(p.nombre, formProspecto(p), async () => {
            const r = await pedir(`/api/superadmin/comercial/prospectos/${p.id}`, 'PATCH', datosProspecto());
            if (!r.ok) { toast(r.json.error || 'No se pudo guardar', true); return false; }
            toast('Guardado');
            await cargarComercial();
            return true;
        });
        $('p-borrar').addEventListener('click', async () => {
            if (!confirm(`¿Borrar a ${p.nombre} del pipeline? No se puede deshacer.`)) return;
            const r = await pedir(`/api/superadmin/comercial/prospectos/${p.id}`, 'DELETE');
            if (!r.ok) return toast(r.json.error || 'No se pudo borrar', true);
            cerrarForm();
            toast('Prospecto borrado');
            await cargarComercial();
        });
    });

    /* ── Planes (los de verdad: con esto se cobra) ── */
    const topeTxt = (p) => p.max_unidades ? `hasta ${p.max_unidades} unidades` : 'sin tope de unidades';

    function pintarPlanes() {
        if (!com.planes.length) {
            $('n-planes').innerHTML = '<div class="vacio">No hay planes. Sin planes, nadie paga nada.</div>';
            return;
        }
        $('n-planes').innerHTML = `<div class="planes">${com.planes.map((p) => `
            <div class="panel plan">
                <div class="nombre" style="font-weight:700">${escapar(p.nombre)}</div>
                <div class="precio">${plata(p.precio_mensual)}</div>
                <div class="ayuda">por edificio / mes · ${topeTxt(p)}</div>
                ${p.descripcion ? `<p class="ayuda" style="margin-top:.6rem;color:var(--text)">${escapar(p.descripcion)}</p>` : ''}
            </div>`).join('')}</div>`;
    }

    function filaPlan(p = {}) {
        return `<div class="plan-editor" data-plan data-id="${escapar(p.id || '')}">
            <label class="campo">Nombre<input data-c="nombre" maxlength="60" value="${escapar(p.nombre || '')}"></label>
            <label class="campo">Precio / mes<input data-c="precio_mensual" inputmode="decimal" value="${p.precio_mensual ?? ''}"></label>
            <label class="campo">Hasta (unidades)<input data-c="max_unidades" inputmode="numeric" placeholder="sin tope" value="${p.max_unidades ?? ''}"></label>
            <label class="campo ancho-movil">Qué incluye<input data-c="descripcion" maxlength="400" value="${escapar(p.descripcion || '')}"></label>
            <button type="button" class="btn-icono" data-quitar title="Quitar">✕</button>
        </div>`;
    }

    $('n-editar-planes').addEventListener('click', () => {
        abrirForm('Planes y precios', `
            <p class="ayuda" style="margin-bottom:.8rem">El precio es por edificio y por mes. Dejá vacío «Hasta» en el plan más grande. Los cobros ya generados no cambian.</p>
            <div id="n-lista-planes">${(com.planes.length ? com.planes : [{}]).map(filaPlan).join('')}</div>
            <button type="button" class="btn btn-fantasma" id="n-agregar-plan">+ Agregar plan</button>`,
        async () => {
            const planes = [...document.querySelectorAll('[data-plan]')].map((f) => ({
                id: f.dataset.id || null,
                ...Object.fromEntries([...f.querySelectorAll('[data-c]')].map((i) => [i.dataset.c, i.value])),
            }));
            const r = await pedir('/api/superadmin/planes', 'PUT', { planes });
            if (!r.ok) { toast(r.json.error || 'No se pudo guardar', true); return false; }
            toast('Planes guardados');
            await cargarComercial();
            return true;
        });
    });

    /* ── Cómo cobramos ── */
    function pintarConfigCobro() {
        const c = com.cobro || {};
        [['c-prueba', c.prueba_dias], ['c-titular', c.titular], ['c-cbu', c.cbu], ['c-alias', c.alias]]
            .forEach(([id, v]) => { if (document.activeElement !== $(id)) $(id).value = v ?? ''; });
    }

    $('n-form-cobro').addEventListener('submit', async (e) => {
        e.preventDefault();
        const r = await pedir('/api/superadmin/cobro/config', 'PUT', {
            prueba_dias: $('c-prueba').value, titular: $('c-titular').value,
            cbu: $('c-cbu').value, alias: $('c-alias').value,
        });
        if (!r.ok) return toast(r.json.error || 'No se pudo guardar', true);
        toast('Guardado');
    });

    // Agregar y quitar filas en los editores de metas y planes.
    $('n-form-cuerpo').addEventListener('click', (e) => {
        if (e.target.closest('[data-quitar]')) e.target.closest('[data-meta], [data-plan]').remove();
        if (e.target.id === 'n-agregar-meta') $('n-lista-metas').insertAdjacentHTML('beforeend', filaMeta());
        if (e.target.id === 'n-agregar-plan') $('n-lista-planes').insertAdjacentHTML('beforeend', filaPlan());
    });

    /* ── Notas: se guardan solas ── */
    let timerNotas = null;
    $('n-notas').addEventListener('input', () => {
        $('n-notas-estado').textContent = 'Escribiendo…';
        clearTimeout(timerNotas);
        timerNotas = setTimeout(async () => {
            const r = await pedir('/api/superadmin/comercial/notas', 'PUT', { texto: $('n-notas').value });
            $('n-notas-estado').textContent = r.ok ? 'Guardado ✓' : 'No se pudo guardar';
        }, 900);
    });

    // ══════════════════════════════════════════════════════════════════════
    // FINANZAS
    // ══════════════════════════════════════════════════════════════════════
    let fin = null;
    let tipoMov = 'gasto';
    let timerBloqueo = null;

    function mostrarCandado() {
        clearTimeout(timerBloqueo);
        $('f-contenido').hidden = true;
        $('f-candado').hidden = false;
        $('f-clave').value = '';
    }

    async function cargarFinanzas() {
        const r = await pedir('/api/superadmin/finanzas');
        if (r.status === 423) return mostrarCandado();
        if (!r.ok) return toast(r.json.error || 'No pudimos cargar Finanzas', true);
        fin = r.json;
        $('f-candado').hidden = true;
        $('f-contenido').hidden = false;
        pintarFinanzas();
        cargarCobros();
        // La pantalla se cierra sola cuando vence el desbloqueo del servidor.
        clearTimeout(timerBloqueo);
        const resta = fin.abierta_hasta * 1000 - Date.now();
        if (resta > 0) timerBloqueo = setTimeout(mostrarCandado, resta);
    }

    $('f-form-clave').addEventListener('submit', async (e) => {
        e.preventDefault();
        const r = await pedir('/api/superadmin/finanzas/desbloquear', 'POST', { clave: $('f-clave').value });
        if (!r.ok) { $('f-clave').value = ''; return toast(r.json.error || 'No se pudo desbloquear', true); }
        await cargarFinanzas();
    });

    $('f-bloquear').addEventListener('click', async () => {
        await pedir('/api/superadmin/finanzas/bloquear', 'POST');
        mostrarCandado();
    });

    function kpi(titulo, valorTxt, nota = '', clase = '') {
        return `<div class="kpi ${clase}"><div class="valor">${valorTxt}</div>
            <div class="etiqueta">${titulo}</div>${nota ? `<div class="delta neutro">${nota}</div>` : ''}</div>`;
    }

    function pintarFinanzas() {
        const k = fin.kpis;
        const hasta = new Date(fin.abierta_hasta * 1000).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
        $('f-abierta').textContent = `Desbloqueado hasta las ${hasta}`;
        const signo = (n) => (n > 0 ? 'positivo' : n < 0 ? 'negativo' : '');
        $('f-kpis').innerHTML =
            kpi('Caja', plata(k.caja), 'ingresos − gastos, desde siempre', signo(k.caja)) +
            kpi('Resultado del mes', plata(k.resultado_mes), '', signo(k.resultado_mes)) +
            kpi('Ingresos del mes', plata(k.ingresos_mes)) +
            kpi('Gastos del mes', plata(k.gastos_mes)) +
            kpi('Burn mensual', plata(k.burn), 'gasto promedio de los 3 meses cerrados') +
            kpi('Runway', k.runway_meses === null ? '—' : `${String(k.runway_meses).replace('.', ',')} meses`,
                k.runway_meses === null ? (k.burn ? 'sin caja positiva' : 'sin gastos cargados') : 'si no entrara un peso más');

        pintarGraficoFinanzas(fin.serie);
        pintarSuscripciones(fin.suscripciones);

        $('f-categorias').innerHTML = fin.categorias.map((c) => `<option value="${escapar(c)}">`).join('');
        const cats = fin.gastos_por_categoria;
        const tope = Math.max(1, ...cats.map((c) => c.monto));
        $('f-categorias-gasto').innerHTML = cats.length ? cats.map((c) => `
            <div class="paso">
                <div class="paso-cab"><span>${escapar(c.categoria)}</span><span class="n">${plata(c.monto)}</span></div>
                <div class="barra" style="height:10px"><i style="width:${(c.monto / tope) * 100}%"></i></div>
            </div>`).join('') : '<p class="ayuda">Sin gastos cargados en los últimos 12 meses.</p>';

        $('f-movimientos').innerHTML = fin.movimientos.length ? fin.movimientos.map((m) => `
            <div class="fila">
                <span class="cuando" style="min-width:86px">${fechaCorta(m.fecha)}</span>
                <div class="quien">
                    <div class="nombre">${escapar(m.categoria || 'Otros')}</div>
                    ${m.nota ? `<div class="detalle">${escapar(m.nota)}</div>` : ''}
                </div>
                <span class="mov-monto ${m.tipo}">${m.tipo === 'gasto' ? '−' : '+'}${plata(m.monto)}</span>
                <button class="btn-icono" data-borrar-mov="${m.id}" title="Borrar">✕</button>
            </div>`).join('') : '<div class="vacio">Todavía no cargaste movimientos. Empezá por los gastos fijos del mes (servidores, dominio, herramientas).</div>';

        if (!$('f-fecha').value) $('f-fecha').value = hoyISO();
    }

    function pintarGraficoFinanzas(serie) {
        const W = 720, H = 170, base = H - 22, tope = 10;
        const max = Math.max(1, ...serie.flatMap((m) => [m.ingresos, m.gastos]));
        const paso = W / serie.length, ancho = Math.min(14, paso / 3.2);
        const alto = (v) => (v / max) * (base - tope);
        let svg = `<line x1="0" y1="${base}" x2="${W}" y2="${base}" stroke="var(--border)" stroke-width="1"/>`;
        serie.forEach((m, i) => {
            const centro = i * paso + paso / 2;
            [['ingresos', 'var(--nd-verde)', -1], ['gastos', 'var(--nd-terracota)', 0]].forEach(([clave, color, lado]) => {
                const h = alto(m[clave]);
                const x = centro + lado * (ancho + 2) + 1;
                if (h > 0) svg += `<rect x="${x}" y="${base - h}" width="${ancho}" height="${h}" fill="${color}" rx="1.5"><title>${m.mes} · ${clave}: ${plata(m[clave])}</title></rect>`;
            });
            svg += `<text x="${centro}" y="${H - 6}" text-anchor="middle">${m.mes.slice(5)}</text>`;
        });
        $('f-grafico').innerHTML = svg;
    }

    /* ── Suscripciones ── */
    function pintarSuscripciones(su) {
        $('f-subs-kpis').innerHTML =
            kpi('Facturación mensual', plata(su.mrr), 'lo que pagan hoy los que pagan', su.mrr > 0 ? 'positivo' : '') +
            kpi('Al año', plata(su.anual)) +
            kpi('Si nadie tuviera pase gratis', plata(su.potencial), 'fundadores y prueba incluidos') +
            kpi('Pipeline en curso', `+${plata(su.pipeline.mensual)}`, `${su.pipeline.prospectos} prospectos, por mes`);
        $('f-subs-planes').innerHTML = `
            <thead><tr><th>Plan</th><th class="num">Precio</th><th class="num">Edificios</th><th class="num">Pagando</th><th class="num">Sin cargo</th><th class="num">Por mes</th></tr></thead>
            <tbody>${su.por_plan.map((p) => `<tr>
                <td>${escapar(p.plan)}</td><td class="num">${plata(p.precio)}</td>
                <td class="num">${p.edificios}</td><td class="num">${p.pagando}</td>
                <td class="num">${p.sin_cargo}</td><td class="num"><b>${plata(p.mrr)}</b></td>
            </tr>`).join('')}</tbody>`;
        const c = su.cuentas;
        $('f-subs-cuentas').textContent =
            `Administradores: ${c.pagando} pagando · ${c.fundador} fundadores con pase gratis · ${c.prueba} en prueba · ` +
            `${c.sin_edificios} sin edificios todavía · ${c.equipo} del equipo (no pagan nunca).`;
    }

    /* ── Cobros del mes ── */
    const ESTADOS = { pendiente: 'A cobrar', pagado: 'Pagado', bonificado: 'Sin cargo' };
    const MOTIVOS = { fundador: 'fundador', prueba: 'en prueba' };
    let periodo = hoyISO().slice(0, 7);
    let cobrosFilas = [];

    async function cargarCobros() {
        $('f-periodo').value = periodo;
        const r = await pedir(`/api/superadmin/cobros?periodo=${periodo}`);
        if (r.status === 423) return mostrarCandado();
        if (!r.ok) return toast(r.json.error || 'No pudimos cargar los cobros', true);
        const d = r.json;
        cobrosFilas = d.filas;
        const res = d.resumen;
        $('f-cobros-kpis').innerHTML =
            kpi('A cobrar este mes', plata(res.facturado)) +
            kpi('Cobrado', plata(res.cobrado), '', res.cobrado > 0 ? 'positivo' : '') +
            kpi('Falta cobrar', plata(res.pendiente), '', res.pendiente > 0 ? 'negativo' : '') +
            kpi('Bonificado', plata(res.bonificado), 'pase gratis');
        $('f-generar').textContent = res.sin_generar ? `Generar cobros (${res.sin_generar})` : 'Todo generado';
        $('f-generar').disabled = !res.sin_generar;

        $('f-cobros').innerHTML = d.filas.length ? d.filas.map((f) => {
            const c = f.cobro;
            const estado = c ? c.estado : 'sin-generar';
            const detalle = c ? c.detalle.map((e) => `${escapar(e.consorcio)} (${e.unidades} u., ${escapar(e.plan || '—')})`).join(' · ') : 'Todavía no se generó';
            return `<div class="ficha" data-admin="${f.admin_id}">
                <div class="quien">
                    <div class="nombre">${escapar(f.nombre)} <span class="pill ${estado}">${c ? ESTADOS[c.estado] : 'Sin generar'}</span></div>
                    <div class="detalle">${detalle}</div>
                    <div class="detalle" style="margin-top:.3rem">Gratis hasta
                        <input type="date" class="gratis-input" data-gratis="${f.admin_id}" value="${f.gratis_hasta || ''}">
                        ${f.sin_cargo ? `<b>(${MOTIVOS[f.sin_cargo] || f.sin_cargo})</b>` : ''}</div>
                </div>
                <span class="mov-monto ${c && c.estado === 'pagado' ? 'ingreso' : ''}">${c ? (c.estado === 'bonificado' ? `<s>${plata(c.total)}</s>` : plata(c.total)) : '—'}</span>
                <div class="acciones">
                    ${c && c.estado === 'pendiente' ? `<button class="btn btn-aprobar" data-pagado="${c.id}">Marcar pagado</button>` : ''}
                    ${c && c.estado === 'pagado' ? `<button class="btn btn-fantasma" data-deshacer="${c.id}">Deshacer</button>` : ''}
                    ${c && c.estado !== 'pagado' ? `<button class="btn-icono" data-borrar-cobro="${c.id}" title="Borrar para rehacerlo">✕</button>` : ''}
                </div>
            </div>`;
        }).join('') : '<div class="vacio">No hay administradores que paguen todavía.</div>';
    }

    $('f-periodo').addEventListener('change', () => { periodo = $('f-periodo').value || periodo; cargarCobros(); });

    $('f-generar').addEventListener('click', async () => {
        const r = await pedir('/api/superadmin/cobros/generar', 'POST', { periodo });
        if (r.status === 423) return mostrarCandado();
        if (!r.ok) return toast(r.json.error || 'No se pudieron generar', true);
        toast(r.json.generados ? `Listo: ${r.json.generados} cobros generados` : 'No había nada para generar');
        await cargarCobros();
    });

    $('f-cobros').addEventListener('click', async (e) => {
        const b = e.target.closest('[data-pagado], [data-deshacer], [data-borrar-cobro]');
        if (!b) return;
        let url, metodo = 'POST', ok;
        if (b.dataset.pagado) { url = `/api/superadmin/cobros/${b.dataset.pagado}/pagado`; ok = 'Pagado. Entró como ingreso en Finanzas.'; }
        if (b.dataset.deshacer) { url = `/api/superadmin/cobros/${b.dataset.deshacer}/deshacer`; ok = 'Pago deshecho'; }
        if (b.dataset.borrarCobro) {
            if (!confirm('¿Borrar este cobro? Lo podés volver a generar con los planes de hoy.')) return;
            url = `/api/superadmin/cobros/${b.dataset.borrarCobro}`; metodo = 'DELETE'; ok = 'Cobro borrado';
        }
        b.disabled = true;
        const r = await pedir(url, metodo);
        if (r.status === 423) return mostrarCandado();
        if (!r.ok) { b.disabled = false; return toast(r.json.error || 'No se pudo', true); }
        toast(ok);
        await cargarFinanzas();
    });

    $('f-cobros').addEventListener('change', async (e) => {
        const inp = e.target.closest('[data-gratis]');
        if (!inp) return;
        const r = await pedir(`/api/superadmin/administradores/${inp.dataset.gratis}/gratis`, 'PUT', { gratis_hasta: inp.value || null });
        if (r.status === 423) return mostrarCandado();
        if (!r.ok) return toast(r.json.error || 'No se pudo guardar', true);
        toast(inp.value ? 'Pase gratis actualizado' : 'Pase gratis quitado');
        await cargarFinanzas();
    });

    $('f-tipo').addEventListener('click', (e) => {
        const b = e.target.closest('[data-tipo]');
        if (!b) return;
        tipoMov = b.dataset.tipo;
        $('f-tipo').querySelectorAll('button').forEach((x) => x.classList.toggle('activo', x === b));
    });

    $('f-form-mov').addEventListener('submit', async (e) => {
        e.preventDefault();
        const r = await pedir('/api/superadmin/finanzas/movimientos', 'POST', {
            tipo: tipoMov, fecha: $('f-fecha').value, monto: $('f-monto').value,
            categoria: $('f-categoria').value, nota: $('f-nota').value,
        });
        if (r.status === 423) return mostrarCandado();
        if (!r.ok) return toast(r.json.error || 'No se pudo guardar', true);
        ['f-monto', 'f-nota'].forEach((id) => { $(id).value = ''; });
        toast(tipoMov === 'gasto' ? 'Gasto cargado' : 'Ingreso cargado');
        await cargarFinanzas();
        $('f-monto').focus();
    });

    $('f-movimientos').addEventListener('click', async (e) => {
        const b = e.target.closest('[data-borrar-mov]');
        if (!b || !confirm('¿Borrar este movimiento? No se puede deshacer.')) return;
        const r = await pedir(`/api/superadmin/finanzas/movimientos/${b.dataset.borrarMov}`, 'DELETE');
        if (r.status === 423) return mostrarCandado();
        if (!r.ok) return toast(r.json.error || 'No se pudo borrar', true);
        toast('Movimiento borrado');
        await cargarFinanzas();
    });

    CARGAR.comercial = cargarComercial;
    CARGAR.finanzas = cargarFinanzas;
})();
