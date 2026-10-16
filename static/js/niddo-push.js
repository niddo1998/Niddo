/* ==========================================================================
   Niddo — Notificaciones en el celular (Web Push)

   Niddo no es una app de tienda: es una web que se agrega a la pantalla de
   inicio. Las notificaciones son Web Push y las muestra el service worker
   (/sw.js) aunque Niddo esté cerrado.

   Qué hace este archivo:
   - Registra el service worker en cada carga.
   - Ofrece activar las notificaciones con una tarjeta arriba del panel. El
     permiso se pide con un toque del usuario: iPhone no deja pedirlo solo, y
     en Android un pedido sin contexto se rechaza y queda bloqueado.
   - En iPhone, si Niddo no está agregado a la pantalla de inicio, explica
     cómo hacerlo: Apple sólo deja recibir push a las webs agregadas (iOS 16.4+).
   - Pone el numerito en el ícono de la app cuando el sistema lo permite.

   Estados: 'activo', 'apagado', 'bloqueado', 'ios-instalar', 'no-soportado',
   'no-configurado' (el servidor no tiene las claves VAPID).
   ========================================================================== */
(function () {
    'use strict';

    var soporta = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
    var esIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    var instalada = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) ||
        navigator.standalone === true;
    var CLAVE_CERRADO = 'niddo-push-tarjeta-cerrada';

    var registro = null;
    var config = null;

    function registrar() {
        if (!('serviceWorker' in navigator)) return Promise.resolve(null);
        if (registro) return Promise.resolve(registro);
        return navigator.serviceWorker.register('/sw.js', { scope: '/' })
            .then(function (r) { registro = r; return r; })
            .catch(function () { return null; });
    }

    function pedirConfig() {
        if (config) return Promise.resolve(config);
        return fetch('/api/push/clave').then(function (r) { return r.ok ? r.json() : {}; })
            .catch(function () { return {}; })
            .then(function (c) { config = c || {}; return config; });
    }

    function claveABytes(b64) {
        var relleno = '='.repeat((4 - b64.length % 4) % 4);
        var crudo = atob((b64 + relleno).replace(/-/g, '+').replace(/_/g, '/'));
        var out = new Uint8Array(crudo.length);
        for (var i = 0; i < crudo.length; i++) out[i] = crudo.charCodeAt(i);
        return out;
    }

    function guardarEnServidor(sub) {
        return fetch('/api/push/suscribir', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ suscripcion: sub.toJSON() })
        });
    }

    function estado() {
        if (!soporta) return Promise.resolve(esIOS && !instalada ? 'ios-instalar' : 'no-soportado');
        return pedirConfig().then(function (c) {
            if (!c.disponible) return 'no-configurado';
            if (Notification.permission === 'denied') return 'bloqueado';
            return registrar().then(function (reg) {
                if (!reg) return 'no-soportado';
                return reg.pushManager.getSubscription().then(function (sub) {
                    if (sub && Notification.permission === 'granted') {
                        /* Se vuelve a mandar en cada carga: si la suscripción
                           rotó o se borró del lado del servidor, se repone. */
                        guardarEnServidor(sub).catch(function () {});
                        return 'activo';
                    }
                    return 'apagado';
                });
            });
        });
    }

    function activar() {
        if (!soporta) return Promise.resolve(esIOS && !instalada ? 'ios-instalar' : 'no-soportado');
        return Notification.requestPermission().then(function (permiso) {
            if (permiso !== 'granted') return permiso === 'denied' ? 'bloqueado' : 'apagado';
            return Promise.all([pedirConfig(), registrar()]).then(function (r) {
                var c = r[0];
                if (!c.disponible) return 'no-configurado';
                return navigator.serviceWorker.ready.then(function (reg) {
                    return reg.pushManager.getSubscription().then(function (sub) {
                        return sub || reg.pushManager.subscribe({
                            userVisibleOnly: true,
                            applicationServerKey: claveABytes(c.clave)
                        });
                    });
                }).then(function (sub) {
                    return guardarEnServidor(sub).then(function () { return 'activo'; });
                });
            });
        }).catch(function () { return 'apagado'; });
    }

    function desactivar() {
        return registrar().then(function (reg) {
            if (!reg) return 'apagado';
            return reg.pushManager.getSubscription().then(function (sub) {
                if (!sub) return 'apagado';
                var endpoint = sub.endpoint;
                return sub.unsubscribe().then(function () {
                    return fetch('/api/push/desuscribir', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ endpoint: endpoint })
                    });
                }).then(function () { return 'apagado'; });
            });
        });
    }

    /* El numerito sobre el ícono de Niddo en la pantalla de inicio. */
    function numeroEnIcono(n) {
        try {
            if (!('setAppBadge' in navigator)) return;
            if (n > 0) navigator.setAppBadge(n); else navigator.clearAppBadge();
        } catch (e) { /* no todos los sistemas lo dejan */ }
    }

    var TEXTOS = {
        'apagado': {
            t: 'Recibí los avisos en este dispositivo',
            s: 'Te avisamos al celular cuando hay una expensa nueva, te responden un reclamo o te escriben.',
            boton: 'Activar notificaciones'
        },
        'ios-instalar': {
            t: 'Para recibir avisos en el iPhone',
            s: 'Agregá Niddo a tu pantalla de inicio: tocá el botón Compartir (el cuadrado con la flecha) y después «Agregar a inicio». Abrilo desde ahí y activá las notificaciones.',
            boton: null
        }
    };

    function cerrada() {
        try { return localStorage.getItem(CLAVE_CERRADO) === '1'; } catch (e) { return false; }
    }

    function cerrar(tarjeta) {
        try { localStorage.setItem(CLAVE_CERRADO, '1'); } catch (e) {}
        if (tarjeta) tarjeta.remove();
    }

    /* La tarjeta que ofrece activarlas. Se muestra una sola vez por
       dispositivo: si se cierra no vuelve, y se puede activar después desde
       el perfil. */
    function montarTarjeta(contenedor) {
        if (!contenedor || cerrada()) return;
        estado().then(function (e) {
            var txt = TEXTOS[e];
            if (!txt || document.getElementById('nd-push-tarjeta')) return;
            var t = document.createElement('div');
            t.id = 'nd-push-tarjeta';
            t.className = 'nd-push-tarjeta';
            t.innerHTML =
                '<span class="nd-push-ic"><svg class="ic"><use href="#ic-campana"></use></svg></span>' +
                '<span class="nd-push-txt"><b>' + txt.t + '</b><span>' + txt.s + '</span></span>' +
                '<span class="nd-push-acc">' +
                (txt.boton ? '<button type="button" class="nd-push-si">' + txt.boton + '</button>' : '') +
                '<button type="button" class="nd-push-no">' + (txt.boton ? 'Ahora no' : 'Entendido') + '</button>' +
                '</span>';
            contenedor.insertBefore(t, contenedor.firstChild);
            t.querySelector('.nd-push-no').addEventListener('click', function () { cerrar(t); });
            var si = t.querySelector('.nd-push-si');
            if (si) si.addEventListener('click', function () {
                si.disabled = true;
                activar().then(function (r) {
                    if (r === 'activo') {
                        t.querySelector('.nd-push-txt').innerHTML =
                            '<b>Listo, las notificaciones quedaron activas</b><span>Te avisamos en este dispositivo.</span>';
                        t.querySelector('.nd-push-acc').innerHTML = '';
                        setTimeout(function () { cerrar(t); }, 2600);
                    } else if (r === 'bloqueado') {
                        t.querySelector('.nd-push-txt span').textContent =
                            'El navegador tiene bloqueadas las notificaciones de Niddo. Habilitalas desde el candado de la barra de direcciones o la configuración del navegador.';
                        si.remove();
                    } else {
                        si.disabled = false;
                    }
                });
            });
        });
    }

    window.NiddoPush = {
        estado: estado,
        activar: activar,
        desactivar: desactivar,
        numeroEnIcono: numeroEnIcono,
        montarTarjeta: montarTarjeta,
        esIOS: esIOS,
        instalada: instalada
    };

    registrar();
})();
