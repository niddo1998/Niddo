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

    /* ── Hoja de "Más" ───────────────────────────────────────────────────── */

    var MAS_ITEMS = CFG.masItems || [
        { section: 'archivos', label: 'Archivos', icon: 'ic-carpeta' },
        { section: 'gastos', label: 'Gastos del consorcio', icon: 'ic-balance' },
        { section: 'perfil', label: 'Mi perfil', icon: 'ic-vecino' }
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
                window[navFn](item.section);
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
        buildHeader();
        buildMas();
        watchScroll();

        /* La entrada inicial del historial, para que el primer "atrás" tenga
           adónde volver en vez de sacarte del sitio. De paso habilita deep
           links: /vecino#reservas abre reservas directo. */
        var initial = (location.hash || '#inicio').slice(1);
        if (!TAB_OF[initial]) initial = 'inicio';
        history.replaceState({ ndSection: initial }, '', '#' + initial);

        window.addEventListener('popstate', onPopState);

        restoring = true;
        try {
            window[navFn](initial);
        } finally {
            restoring = false;
        }
    });
})();
