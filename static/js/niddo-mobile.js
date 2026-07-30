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

    document.addEventListener('DOMContentLoaded', function () {
        wrapShowSection();

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
