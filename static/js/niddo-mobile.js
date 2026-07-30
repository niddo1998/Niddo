/* ==========================================================================
   Niddo — Comportamientos mobile

   Sale temprano en escritorio: arriba de 900px este archivo no hace
   absolutamente nada, así el dashboard de escritorio queda intacto.

   Se carga con defer, así que corre después de que el <script> inline del
   template definió showSection() y las demás globales que envolvemos.
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

    /* ── Tab bar ──────────────────────────────────────────────────────────
       Cinco tabs para nueve secciones. Comunidad agrupa comunicados,
       votaciones y reclamos; Más agrupa las que viven en la hoja. Este mapa
       dice qué tab se ilumina para cada sección. */
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

    /* Distingue una navegación que dispara el usuario —hay que empujar al
       historial— de una que viene del propio popstate, que no debe empujar
       o se duplicaría la entrada y el atrás dejaría de avanzar. */
    var restoring = false;

    /* showSection() la define el <script> inline del template. La envolvemos
       en vez de tocarla para que el escritorio siga usando la original. */
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

    NiddoMobile.TAB_OF = TAB_OF;
    NiddoMobile.setTab = setTab;

    /* La hoja de "Más" llega en la Task 5. Hasta entonces, atajo a perfil
       para que el tab no quede muerto. */
    NiddoMobile.openMas = function () {
        window.showSection('perfil');
    };

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
        wrapShowSection();
        initSheets();

        /* La entrada inicial del historial, para que el primer "atrás" tenga
           adónde volver en vez de sacarte del sitio. De paso habilita deep
           links: /vecino#reservas abre reservas directo. */
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
})();
