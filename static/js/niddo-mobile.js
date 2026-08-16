/* ==========================================================================
   Niddo — Comportamientos mobile

   Sale temprano en escritorio: arriba de 900px este archivo no hace
   absolutamente nada, así el dashboard de escritorio queda intacto.

   Se carga con defer, así que corre después de que el <script> inline del
   template definió su función de navegación y las globales que envolvemos.
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

    /* Construye la lista que reemplaza a una tabla en mobile, a partir de la
       misma fuente de datos que llenó el <tbody>. Se declara antes del early
       return para que en escritorio sea un no-op y el template pueda llamarla
       sin condicionales.

       La duplicación es de forma, no de lógica: una función, un objeto, dos
       markups. La alternativa —transformar el DOM tras cada respuesta de la
       API— es frágil por timing. */
    window.NiddoMobile.renderList = function (tbodyId, data, mapper) {
        if (!isMobile()) return;
        var tb = document.getElementById(tbodyId);
        if (!tb || !data) return;
        var wrap = tb.closest('.card') || tb.closest('.table-wrap') || tb.parentNode.parentNode;
        if (!wrap) return;
        var list = wrap.querySelector('.nd-list');
        if (!list) {
            list = document.createElement('div');
            list.className = 'nd-list';
            wrap.appendChild(list);
        }
        list.innerHTML = data.map(mapper).join('');
    };

    if (!isMobile()) return;

    document.documentElement.classList.add('nd-mobile');

    /* ── Configuración ────────────────────────────────────────────────────
       Los valores por defecto son los del vecino, que fue el primer
       consumidor. Así ese template no necesita declarar nada y no hubo que
       tocarlo para que admin entrara — y lo que está en producción no puede
       romperse por esta parametrización.

       Si aparece un tercer consumidor, conviene mover estos defaults a su
       propio template y dejar este archivo sin ninguno. */
    var CFG = window.NIDDO_MOBILE_CONFIG || {};

    var navFn          = CFG.navFn || 'showSection';
    var sectionPrefix  = CFG.sectionPrefix || 'section-';
    var headerSelector = CFG.headerSelector || '.app-header';
    var navPassesEl    = CFG.navPassesElement === true;
    var usesHash       = CFG.usesHash === true;
    var defaultSection = CFG.defaultSection || 'inicio';

    /* ── Tab bar ──────────────────────────────────────────────────────────
       Qué tab se ilumina para cada sección. En el vecino, Comunidad agrupa
       comunicados, votaciones y reclamos; Más agrupa las que viven en la
       hoja. */
    var TAB_OF = CFG.tabOf || {
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
        var tabs = document.querySelectorAll('#nd-tabbar .bottom-btn, .nd-tabbar .bottom-btn');
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].classList.toggle('active', tabs[i].dataset.tab === tabId);
        }
    }

    /* Distingue una navegación que dispara el usuario —hay que empujar al
       historial— de una que viene del propio popstate, que no debe empujar
       o se duplicaría la entrada y el atrás dejaría de avanzar. */
    var restoring = false;

    /* La función de navegación la define el <script> inline del template:
       showSection(name) en el vecino, show(id, el) en admin. La envolvemos
       en vez de tocarla, para que el escritorio siga usando la original. */
    function wrapNav() {
        var original = window[navFn];
        if (typeof original !== 'function') return;
        window[navFn] = function (name) {
            /* show(id, el) usa el segundo argumento para marcar el nav-link
               del sidebar. Desde la tab bar no hay elemento; la función ya
               hace `if (el)`, así que pasar undefined es seguro, y en mobile
               el sidebar está oculto igual. */
            original.call(this, name, navPassesEl ? arguments[1] : undefined);
            setTab(TAB_OF[name] || name);
            setTitle(name);
            markDrawer(name);
            /* Si el template ya escribe el hash por su cuenta —admin lo
               hace dentro de show()— empujar además duplicaría entradas y el
               atrás necesitaría dos toques. */
            if (!restoring && !usesHash) {
                history.pushState({ ndSection: name }, '', '#' + name);
            }
        };
    }

    function onPopState(e) {
        var name = (e.state && e.state.ndSection) || 'inicio';
        restoring = true;
        try {
            window[navFn](name);
        } finally {
            restoring = false;
        }
    }

    NiddoMobile.TAB_OF = TAB_OF;
    NiddoMobile.setTab = setTab;

    NiddoMobile.openMas = function () {
        var o = document.getElementById('nd-mas-overlay');
        if (!o) return;
        o.classList.add('open');
        setTab('mas');
    };

    /* ── Top app bar ─────────────────────────────────────────────────────── */

    var TITLES = CFG.titles || {
        inicio: 'Inicio', expensas: 'Mis expensas', gastos: 'Gastos del consorcio',
        comunicados: 'Comunicados', votaciones: 'Votaciones', reclamos: 'Reclamos',
        reservas: 'Reservas', archivos: 'Archivos', perfil: 'Mi perfil'
    };

    function buildHeader() {
        var header = document.querySelector(headerSelector);
        if (!header || header.querySelector('.nd-largetitle')) return;

        var row = document.createElement('div');
        row.className = 'nd-titlerow';

        /* El botón del cajón va antes del título para que el título quede
           centrado entre él y lo que el template tenga a la derecha. */
        if (CFG.drawer) {
            var menu = document.createElement('button');
            menu.className = 'nd-menu-btn';
            menu.type = 'button';
            menu.setAttribute('aria-label', 'Menú');
            menu.innerHTML = '<svg class="ic"><use href="#ic-menu"></use></svg>';
            menu.addEventListener('click', function () {
                /* Un solo botón con dos papeles: ☰ en la raíz, ← adentro de
                   un flujo. Dos botones en la misma esquina competirían por
                   el pulgar y sólo uno tiene sentido a la vez. */
                if (backHandler) backHandler(); else openDrawer();
            });
            row.appendChild(menu);
        }

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
        var header = document.querySelector(headerSelector);
        if (!header) return;
        window.addEventListener('scroll', function () {
            header.classList.toggle('nd-scrolled', window.scrollY > 26);
        }, { passive: true });
    }

    /* ── Cajón lateral ────────────────────────────────────────────────────
       Opt-in: sólo se construye si el template declara `drawer`. El vecino
       no lo declara y sigue con la hoja de "Más", que para sus tres ítems
       alcanza. Admin tiene once secciones y necesita un índice.

       Estructura declarada por el template:
           drawer: {
               brand: 'niddo',
               contextLabel: 'Consorcio activo',
               contextSelectors: ['filter-gastos-consorcio', ...],
               groups: [{ label: 'Operación', items: [
                   { section: 'gastos', label: 'Gastos', icon: 'ic-expensa', badge: 3 },
                   { href: '/superadmin', label: 'Aprobaciones', icon: 'ic-vecino' }
               ]}]
           } */

    var DRAWER = CFG.drawer || null;

    /* Mientras haya un handler, el botón de la esquina es "atrás" en vez de
       "menú". Lo pone y lo saca el flujo que lo necesita (hoy, el cierre de
       mes); en la raíz siempre vuelve a ser el cajón. */
    var backHandler = null;

    NiddoMobile.setBack = function (fn) {
        backHandler = fn || null;
        var btn = document.querySelector('.nd-menu-btn');
        if (!btn) return;
        btn.innerHTML = '<svg class="ic"><use href="#' +
            (backHandler ? 'ic-volver' : 'ic-menu') + '"></use></svg>';
        btn.setAttribute('aria-label', backHandler ? 'Atrás' : 'Menú');
    };

    function buildDrawer() {
        if (!DRAWER || document.getElementById('nd-drawer')) return;

        var overlay = document.createElement('div');
        overlay.id = 'nd-drawer-overlay';

        var panel = document.createElement('aside');
        panel.id = 'nd-drawer';

        var html = '';
        if (DRAWER.brand) {
            html += '<div class="nd-dr-brand">' + DRAWER.brand + '<i>o</i></div>';
        }
        if (DRAWER.contextSelectors && DRAWER.contextSelectors.length) {
            html += '<button type="button" class="nd-dr-cons" id="nd-dr-cons">' +
                '<span class="nd-dr-ic"><svg class="ic"><use href="#ic-edificio"></use></svg></span>' +
                '<span><span class="lb">' + (DRAWER.contextLabel || 'Contexto') + '</span>' +
                '<span class="nm" id="nd-dr-cons-nombre">—</span></span>' +
                '<svg class="ic ic-sm"><use href="#ic-chevron"></use></svg></button>';
        }

        html += '<div class="nd-dr-scroll">';
        (DRAWER.groups || []).forEach(function (g) {
            if (g.label) html += '<div class="nd-dr-lbl">' + g.label + '</div>';
            (g.items || []).forEach(function (it) {
                var tag = it.href ? 'a' : 'button';
                var attrs = it.href
                    ? ' href="' + it.href + '"'
                    : ' type="button" data-nd-section="' + it.section + '"';
                html += '<' + tag + ' class="nd-dr-item"' + attrs + '>' +
                    '<svg class="ic"><use href="#' + it.icon + '"></use></svg>' +
                    '<span>' + it.label + '</span>' +
                    (it.badge ? '<i class="nd-dr-badge">' + it.badge + '</i>' : '') +
                    '</' + tag + '>';
            });
        });
        html += '</div>';

        html += '<div class="nd-dr-foot">' +
            '<a class="nd-dr-item danger" href="/auth/logout">' +
            '<svg class="ic"><use href="#ic-salir"></use></svg><span>Cerrar sesión</span></a></div>';

        panel.innerHTML = html;
        document.body.appendChild(overlay);
        document.body.appendChild(panel);

        overlay.addEventListener('click', closeDrawer);

        panel.addEventListener('click', function (ev) {
            if (ev.target.closest('#nd-dr-cons')) {
                closeDrawer();
                /* Después de que el cajón termine de salir: dos capas
                   deslizando a la vez se lee como un salto. */
                setTimeout(openCtxSheet, 200);
                return;
            }
            var it = ev.target.closest('[data-nd-section]');
            if (!it) return;
            closeDrawer();
            window[navFn](it.dataset.ndSection);
        });

        /* Los <select> se llenan cuando responde /api/consorcios, que es
           después de esto. Sin observar, el cajón mostraría "—" para siempre. */
        /* Los <select> siguen existiendo y siguen siendo la fuente de verdad,
           pero dejan de verse: el contexto ya dice en qué edificio estás, y
           cinco filtros repetidos era justamente lo que se sacaba. */
        ctxSelectors().forEach(function (s) { s.classList.add('nd-ctx-oculto'); });

        /* Se observan los cinco, no sólo el primero: el de liquidaciones se
           llena al entrar a esa sección y el de la extracción con IA al abrir
           el modal, mucho después de esto. El que llegue tarde recibe el
           contexto que ya se eligió. */
        if (window.MutationObserver) {
            ctxSelectors().forEach(function (s) {
                new MutationObserver(function () {
                    aplicarCtx(s);
                    refreshCtxLabel();
                }).observe(s, { childList: true });
            });
        }
        refreshCtxLabel();

        makeDrawerDraggable(panel);
        watchEdgeSwipe();
    }

    function openDrawer() {
        var p = document.getElementById('nd-drawer');
        var o = document.getElementById('nd-drawer-overlay');
        if (!p) return;
        p.classList.add('open');
        if (o) o.classList.add('open');
    }

    function closeDrawer() {
        var p = document.getElementById('nd-drawer');
        var o = document.getElementById('nd-drawer-overlay');
        if (p) p.classList.remove('open');
        if (o) o.classList.remove('open');
    }

    /* Qué ítem se ilumina. Se llama desde la navegación, igual que setTab. */
    function markDrawer(section) {
        var items = document.querySelectorAll('#nd-drawer [data-nd-section]');
        for (var i = 0; i < items.length; i++) {
            items[i].classList.toggle('active', items[i].dataset.ndSection === section);
        }
    }

    /* Arrastrar el cajón hacia la izquierda lo cierra. */
    function makeDrawerDraggable(panel) {
        var overlay = document.getElementById('nd-drawer-overlay');
        panel.addEventListener('pointerdown', function (e) {
            /* Si el toque empieza sobre un ítem, es un tap, no un arrastre. */
            if (e.target.closest('.nd-dr-item, .nd-dr-cons')) return;
            var x0 = e.clientX, w = panel.offsetWidth;
            panel.classList.add('nd-dragging');
            function move(ev) {
                var dx = Math.min(0, ev.clientX - x0);
                panel.style.transform = 'translateX(' + dx + 'px)';
                if (overlay) overlay.style.opacity = String(Math.max(0, 1 + dx / w));
            }
            function up(ev) {
                panel.removeEventListener('pointermove', move);
                panel.removeEventListener('pointerup', up);
                panel.classList.remove('nd-dragging');
                panel.style.transform = '';
                if (overlay) overlay.style.opacity = '';
                if (ev.clientX - x0 < -70) closeDrawer();
            }
            panel.addEventListener('pointermove', move);
            panel.addEventListener('pointerup', up);
        });
    }

    /* Entrar desde el borde izquierdo abre el cajón. El umbral de 22px es el
       mismo que usa el sistema para su propio gesto de atrás, así que no se
       dispara con un scroll normal. */
    function watchEdgeSwipe() {
        document.addEventListener('pointerdown', function (e) {
            if (e.clientX > 22) return;
            if (document.getElementById('nd-drawer').classList.contains('open')) return;
            /* No robarle el gesto a una sheet abierta. */
            if (document.querySelector('.modal-overlay.open, .drawer-overlay.open')) return;

            var panel = document.getElementById('nd-drawer');
            var overlay = document.getElementById('nd-drawer-overlay');
            var x0 = e.clientX, w = panel.offsetWidth;
            var movido = false;

            function move(ev) {
                var dx = Math.min(w, Math.max(0, ev.clientX - x0));
                if (dx < 6) return;
                movido = true;
                panel.classList.add('nd-dragging');
                panel.style.transform = 'translateX(' + (dx - w) + 'px)';
                if (overlay) {
                    overlay.classList.add('open');
                    overlay.style.opacity = String(dx / w);
                }
            }
            function up(ev) {
                document.removeEventListener('pointermove', move);
                document.removeEventListener('pointerup', up);
                panel.classList.remove('nd-dragging');
                panel.style.transform = '';
                if (overlay) overlay.style.opacity = '';
                if (!movido) return;
                if (ev.clientX - x0 > 80) openDrawer(); else closeDrawer();
            }
            document.addEventListener('pointermove', move);
            document.addEventListener('pointerup', up);
        });
    }

    /* ── Contexto de consorcio ────────────────────────────────────────────
       En escritorio el consorcio es un filtro, y el mismo <select> aparece
       repetido en cinco pantallas. En el teléfono eso es lo que más hace
       que el panel se sienta un formulario web: elegís el edificio una vez
       por sección en vez de estar "parado" en uno.

       La implementación es deliberadamente conservadora. El contexto no
       reemplaza a los <select>: les escribe el valor y dispara su `change`.
       Así loadGastos(), loadCobros(), loadMora() y loadLiquidaciones()
       siguen leyendo de donde siempre, no hay segunda fuente de verdad, y
       el escritorio no se entera de nada. */

    function ctxSelectors() {
        return (DRAWER && DRAWER.contextSelectors || [])
            .map(function (id) { return document.getElementById(id); })
            .filter(Boolean);
    }

    /* El primero que tenga opciones cargadas manda: son todos el mismo
       listado, pero se llenan en momentos distintos según qué sección se
       haya visitado. */
    function ctxPrimary() {
        var sels = ctxSelectors();
        for (var i = 0; i < sels.length; i++) {
            if (sels[i].options.length > 1) return sels[i];
        }
        return sels[0] || null;
    }

    /* El valor vacío es "todos" en los cinco <select>, pero cada uno lo
       rotula distinto ("Todos", "Todos los consorcios"). El contexto es uno
       solo, así que la etiqueta también. */
    function ctxLabel() {
        if (!ctxValue) return 'Todos los consorcios';
        var s = ctxPrimary();
        if (!s) return 'Todos los consorcios';
        for (var i = 0; i < s.options.length; i++) {
            if (s.options[i].value === ctxValue) return s.options[i].textContent.trim();
        }
        return 'Todos los consorcios';
    }

    function refreshCtxLabel() {
        var el = document.getElementById('nd-dr-cons-nombre');
        if (el) el.textContent = ctxLabel();
    }

    /* El contexto elegido, recordado aparte de los <select>.
       Hace falta porque los cinco no se llenan a la vez: los de gastos y
       cobros cargan al abrir la página, pero el de liquidaciones se llena al
       entrar a esa sección y el de la extracción con IA al abrir el modal.
       Un <select> descarta un value que todavía no tiene como opción, así que
       sin recordarlo esas dos pantallas se quedaban en "todos". */
    var ctxValue = '';

    function aplicarCtx(s) {
        if (s.value === ctxValue) return;
        s.value = ctxValue;
        /* Si el valor no existe como opción, el select queda en '' y no hay
           nada que avisar: cuando se llene, este mismo camino lo corrige. */
        if (s.value !== ctxValue) return;
        s.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function setCtx(value) {
        ctxValue = value;
        ctxSelectors().forEach(aplicarCtx);
        refreshCtxLabel();
    }

    function openCtxSheet() {
        var primary = ctxPrimary();
        if (!primary) return;

        var overlay = document.getElementById('nd-ctx-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.id = 'nd-ctx-overlay';
            overlay.innerHTML =
                '<div class="modal-box">' +
                '<div class="modal-head"><h3>Cambiar de consorcio</h3></div>' +
                '<div class="modal-body" id="nd-ctx-lista"></div></div>';
            document.body.appendChild(overlay);
            makeDraggable(overlay.querySelector('.modal-box'), overlay);
            overlay.addEventListener('click', function (ev) {
                if (ev.target === overlay) overlay.classList.remove('open');
            });
            overlay.addEventListener('click', function (ev) {
                var b = ev.target.closest('[data-nd-ctx]');
                if (!b) return;
                setCtx(b.dataset.ndCtx);
                overlay.classList.remove('open');
            });
        }

        var html = '';
        for (var i = 0; i < primary.options.length; i++) {
            var o = primary.options[i];
            var sel = o.value === ctxValue;
            /* Cada <select> rotula la opción vacía distinto; en el contexto
               es una sola cosa y se llama de una sola manera. */
            var texto = o.value ? o.textContent.trim() : 'Todos los consorcios';
            html += '<button type="button" class="nd-dr-item' + (sel ? ' active' : '') + '"' +
                ' data-nd-ctx="' + o.value.replace(/"/g, '&quot;') + '">' +
                '<svg class="ic"><use href="#' + (sel ? 'ic-pagado' : 'ic-edificio') + '"></use></svg>' +
                '<span>' + texto + '</span></button>';
        }
        document.getElementById('nd-ctx-lista').innerHTML = html;
        overlay.classList.add('open');
    }

    NiddoMobile.openDrawer = openDrawer;
    NiddoMobile.closeDrawer = closeDrawer;
    NiddoMobile.setContexto = setCtx;

    /* ── Hoja de "Más" ───────────────────────────────────────────────────── */

    var MAS_ITEMS = CFG.masItems || [
        { section: 'archivos', label: 'Archivos', icon: 'ic-carpeta' },
        { section: 'gastos', label: 'Gastos del consorcio', icon: 'ic-balance' },
        { section: 'perfil', label: 'Mi perfil', icon: 'ic-vecino' }
    ];

    function buildMas() {
        /* Con cajón no hay hoja de "Más": son la misma función y tener las dos
           dejaría dos índices que se pueden contradecir. */
        if (DRAWER) return;
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
            /* Un item puede apuntar a una sección del dashboard o a una página
               propia. El panel de aprobaciones es lo segundo: vive en su propia
               ruta para que quien no sea superadmin reciba un 404, y sin este
               caso quedaba inalcanzable desde el teléfono. */
            var el;
            if (item.href) {
                el = document.createElement('a');
                el.href = item.href;
            } else {
                el = document.createElement('button');
                el.addEventListener('click', function () {
                    closeMas();
                    window[navFn](item.section);
                });
            }
            el.className = 'nd-mas-item';
            el.innerHTML = '<svg class="ic"><use href="#' + item.icon + '"></use></svg>' + item.label;
            sheet.appendChild(el);
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

        /* El mismo arrastre que las otras hojas. */
        makeDraggableMas(sheet, overlay);
    }

    function makeDraggableMas(sheet, overlay) {
        var grabber = sheet.querySelector('.nd-grabber');
        grabber.addEventListener('pointerdown', function (e) {
            var y0 = e.clientY, h = sheet.offsetHeight;
            sheet.style.transition = 'none';
            grabber.setPointerCapture(e.pointerId);
            function move(ev) {
                var dy = Math.max(0, ev.clientY - y0);
                sheet.style.transform = 'translateY(' + dy + 'px)';
                overlay.style.background = 'rgba(42,33,28,' + Math.max(0, 0.5 - dy / h * 0.7) + ')';
            }
            function up(ev) {
                grabber.removeEventListener('pointermove', move);
                grabber.removeEventListener('pointerup', up);
                sheet.style.transition = '';
                sheet.style.transform = '';
                overlay.style.background = '';
                if (ev.clientY - y0 > 90) closeMas();
            }
            grabber.addEventListener('pointermove', move);
            grabber.addEventListener('pointerup', up);
        });
    }

    function closeMas() {
        var o = document.getElementById('nd-mas-overlay');
        if (o) o.classList.remove('open');
    }

    /* ── Bottom sheets ────────────────────────────────────────────────────
       El arrastre se ata sólo al grabber, nunca al cuerpo scrolleable: si
       no, arrastrar para leer cerraría la hoja. */

    function closeOverlay(overlay) {
        /* Usamos las funciones del template si existen, para no saltearnos
           la limpieza de formularios que puedan hacer. */
        if (overlay.classList.contains('drawer-overlay') && typeof window.closeDrawer === 'function') {
            window.closeDrawer(overlay.id);
        } else if (typeof window.closeModal === 'function') {
            window.closeModal(overlay.id);
        } else {
            overlay.classList.remove('open');
        }
    }

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
                overlay.style.background = 'rgba(42,33,28,' + Math.max(0, 0.5 - dy / h * 0.7) + ')';
            }
            function up(ev) {
                grabber.removeEventListener('pointermove', move);
                grabber.removeEventListener('pointerup', up);
                panel.classList.remove('nd-dragging');
                panel.style.transform = '';
                overlay.style.background = '';
                /* 90px es suficiente para que un roce no cierre la hoja, y
                   poco como para que el gesto no se sienta pesado. */
                if (ev.clientY - y0 > 90) closeOverlay(overlay);
            }
            grabber.addEventListener('pointermove', move);
            grabber.addEventListener('pointerup', up);
        });
    }

    function initSheets() {
        var overlays = document.querySelectorAll('.drawer-overlay, .modal-overlay');
        for (var i = 0; i < overlays.length; i++) {
            var overlay = overlays[i];
            var panel = overlay.querySelector('.drawer, .modal-box');
            if (!panel || panel.querySelector(':scope > .nd-grabber')) continue;
            makeDraggable(panel, overlay);

            overlay.addEventListener('click', function (ev) {
                if (ev.target === this) closeOverlay(this);
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        wrapNav();
        initSheets();
        /* El cajón antes del header: buildHeader ata el botón ☰ a openDrawer,
           que necesita que el panel exista para el gesto de borde. */
        buildDrawer();
        buildHeader();
        buildMas();
        watchScroll();

        if (!usesHash) {
            /* El template no toca el historial: lo manejamos nosotros. La
               entrada inicial hace que el primer "atrás" tenga adónde volver
               en vez de sacarte del sitio, y habilita deep links por hash. */
            var initial = (location.hash || '#' + defaultSection).slice(1);
            if (!TAB_OF[initial]) initial = defaultSection;
            history.replaceState({ ndSection: initial }, '', '#' + initial);
            window.addEventListener('popstate', onPopState);

            restoring = true;
            try {
                window[navFn](initial);
            } finally {
                restoring = false;
            }
        } else {
            /* El template ya escribe el hash dentro de su función de
               navegación, pero nadie escucha cuando el hash cambia solo: al
               volver, la URL retrocede y la vista se queda quieta.

               La guarda `restoring` es obligatoria: la función escribe el
               hash, lo que dispara hashchange, que la llamaría otra vez.
               La comparación con la sección activa es la segunda defensa. */
            window.addEventListener('hashchange', function () {
                var name = location.hash.slice(1);
                if (!name || !TAB_OF[name]) return;
                var actual = document.querySelector('.section.active');
                if (actual && actual.id === sectionPrefix + name) return;
                restoring = true;
                try { window[navFn](name); } finally { restoring = false; }
            });

            /* El template ya restauró la sección desde el hash al cargar, así
               que no navegamos: sólo sincronizamos el tab y el título con lo
               que ya está activo. Navegar acá dejaría la sección equivocada. */
            var activa = document.querySelector('.section.active');
            var nombre = activa && activa.id.indexOf(sectionPrefix) === 0
                ? activa.id.slice(sectionPrefix.length)
                : defaultSection;
            setTab(TAB_OF[nombre] || nombre);
            setTitle(nombre);
            markDrawer(nombre);
        }
    });
})();
