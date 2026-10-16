/* ==========================================================================
   Niddo — Service worker

   Hace dos cosas y nada más:
   1. Muestra las notificaciones push aunque Niddo esté cerrado.
   2. Al tocar una, abre (o trae al frente) la pantalla que corresponde.

   No cachea nada a propósito: los datos de un consorcio tienen que ser los
   de ahora, y una versión vieja servida desde caché sería peor que la red.
   ========================================================================== */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', event => {
    let d = {};
    try { d = event.data ? event.data.json() : {}; } catch (e) { d = { cuerpo: event.data && event.data.text() }; }
    const titulo = d.titulo || 'Niddo';
    event.waitUntil(self.registration.showNotification(titulo, {
        body: d.cuerpo || '',
        icon: '/static/img/icon-192.png',
        badge: '/static/img/badge-96.png',
        tag: d.etiqueta || undefined,
        renotify: !!d.etiqueta,
        data: { url: d.url || '/login' },
    }));
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    const destino = new URL((event.notification.data && event.notification.data.url) || '/login', self.location.origin);
    event.waitUntil((async () => {
        const ventanas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
        /* Si Niddo ya está abierto en esa pantalla, se lo trae al frente y se
           lo lleva a la sección; abrir otra pestaña igual sería ruido. */
        for (const v of ventanas) {
            const u = new URL(v.url);
            if (u.origin === destino.origin && u.pathname === destino.pathname) {
                await v.focus();
                if (destino.hash && 'navigate' in v) return v.navigate(destino.href);
                return;
            }
        }
        return self.clients.openWindow(destino.href);
    })());
});
