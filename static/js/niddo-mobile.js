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

    /* showSection() la define el <script> inline del template. La envolvemos
       en vez de tocarla para que el escritorio siga usando la original. */
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

    /* La hoja de "Más" llega en la Task 5. Hasta entonces, atajo a perfil
       para que el tab no quede muerto. */
    NiddoMobile.openMas = function () {
        window.showSection('perfil');
    };

    document.addEventListener('DOMContentLoaded', function () {
        wrapShowSection();
        setTab('inicio');
    });
})();
