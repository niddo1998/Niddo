/* ==========================================================================
   Niddo — Ayuda de cada sección

   Cada sección tiene un "?" arriba a la derecha que abre una explicación
   corta: de qué se trata y qué se puede hacer ahí. La primera vez que alguien
   entra a una sección, la explicación se abre sola. Lo que ya vio se guarda en
   su cuenta (/api/ayuda/vistas), así no se repite en otro dispositivo.

   El template declara:
       window.NIDDO_AYUDA = {
           rol: 'admin' | 'vecino',
           prefijo: 'sec-' | 'section-',          // id de cada sección
           encabezado: '.page-header' | '.pg-head' // dónde va el "?"
       };
   y llama a NiddoAyuda.alEntrar(seccion) cada vez que navega.
   ========================================================================== */
(function () {
    'use strict';

    var CFG = window.NIDDO_AYUDA || {};

    var TEXTOS = {
        admin: {
            dashboard: {
                t: 'Panel', i: 'ic-panel',
                d: 'Es tu día en un vistazo: en qué punto del mes está cada edificio, lo que está esperando por vos y lo que vence en las próximas dos semanas.',
                l: ['«El mes en cada edificio» muestra los cuatro pasos del cierre: gastos, prorrateo, vencimientos y envío.',
                    '«Requiere tu atención» junta solicitudes de vecinos, reclamos, pagos informados y tarifas por confirmar. Tocá una fila para ir a resolverla.',
                    'Los números de abajo son la plata del mes: cuánto se cobró, cuánto se debe y cuánto se gastó.']
            },
            consorcios: {
                t: 'Consorcios', i: 'ic-edificio',
                d: 'Tus edificios y sus unidades funcionales. Es la base de todo: sin unidades no hay expensas que repartir.',
                l: ['Tocá un consorcio para ver sus unidades y las solicitudes de vecinos que quieren sumarse.',
                    'El numerito indica solicitudes esperando tu aprobación: hasta que las aprobás, el vecino no ve nada del edificio.',
                    'Cargá los m² de cada unidad: por defecto las expensas se reparten por metros cuadrados (se cambia en Configuración).',
                    '«Carga masiva» sube muchos edificios y unidades de una vez desde un Excel.']
            },
            gastos: {
                t: 'Gastos', i: 'ic-expensa',
                d: 'Las facturas y pagos de cada consorcio, mes por mes. De acá sale la liquidación de expensas.',
                l: ['Cargá un gasto a mano o con una foto de la factura: la IA lee los datos por vos.',
                    'Tocá un gasto para ver el detalle, corregirlo o descargar el comprobante.',
                    'Un gasto recurrente (sueldos, abonos) se vuelve a cargar solo cada período; sólo tenés que confirmar el monto.',
                    'Usá las flechas para moverte entre meses.']
            },
            cobros: {
                t: 'Cobros', i: 'ic-cobro',
                d: 'Lo que cada unidad tiene que pagar y lo que ya pagó.',
                l: ['«Morosidad» muestra quién está atrasado y cuánto interés lleva.',
                    '«Pagos informados» son los pagos que avisaron los vecinos: aceptarlos marca la expensa como pagada.']
            },
            amenities: {
                t: 'Amenities', i: 'ic-reserva',
                d: 'Los espacios comunes (SUM, parrilla, pileta) y sus reservas.',
                l: ['El calendario muestra lo reservado cada día, con horario y quién reservó.',
                    'En «Amenities» cargás cada espacio con su capacidad, reservas por mes y condiciones de uso.',
                    'Los vecinos reservan desde su app y pueden avisarle al resto del edificio.']
            },
            liquidaciones: {
                t: 'Liquidaciones', i: 'ic-liquidacion',
                d: 'El cierre de mes: se juntan los gastos, se reparten entre las unidades y se envía el resumen a cada vecino.',
                l: ['«Nueva liquidación» toma los gastos del período que elijas.',
                    'El prorrateo usa el método del consorcio (m², ambientes, partes iguales o porcentaje).',
                    'Revisá el PDF y la previsualización antes de enviar: el envío por mail no se puede deshacer.']
            },
            balance: {
                t: 'Balance', i: 'ic-balance',
                d: 'Ingresos (expensas cobradas) contra egresos (gastos) de cada consorcio en el período que elijas.',
                l: ['Descargalo en Excel o PDF para rendir cuentas en la asamblea.']
            },
            comunicacion: {
                t: 'Comunicación', i: 'ic-mensaje',
                d: 'Todo lo que es hablar con los vecinos, en un solo lugar.',
                l: ['Reclamos: cada uno es una conversación. Respondé, cambiá el estado y el vecino lo ve y le llega aviso.',
                    'Mensajes: un chat privado con cada vecino.',
                    'Comunicados: avisos para todo el edificio (cortes, asambleas, obras).']
            },
            config: {
                t: 'Configuración', i: 'ic-config',
                d: 'Los datos de cada consorcio que usan la liquidación y los resúmenes.',
                l: ['Cómo se reparten las expensas: por m² (lo habitual), ambientes, partes iguales o porcentaje.',
                    'Interés por mora, días de gracia y recargo del segundo vencimiento.',
                    'Datos bancarios para que los vecinos sepan cómo pagar.']
            }
        },
        vecino: {
            inicio: {
                t: 'Inicio', i: 'ic-edificio',
                d: 'Tu resumen: la expensa de este mes, cómo pagarla y las novedades del edificio.',
                l: ['Descargá el resumen de tu expensa con el detalle de gastos.',
                    '«Informar pago» le avisa a la administración que ya pagaste, con el comprobante.']
            },
            comunicados: {
                t: 'Comunicados', i: 'ic-megafono',
                d: 'Los avisos de la administración y de tus vecinos: cortes de servicio, asambleas, reservas del SUM.',
                l: ['El numerito del menú te dice cuántos llegaron desde la última vez que entraste.']
            },
            expensas: {
                t: 'Expensas', i: 'ic-expensa',
                d: 'Tu cuenta corriente: cada expensa, si está pagada y cuándo vence.',
                l: ['Descargá el resumen de cada mes con el detalle de gastos del edificio.',
                    'Si ya pagaste, tocá «Informar pago» y adjuntá el comprobante; la administración lo confirma.']
            },
            gastos: {
                t: 'Reporte de gastos', i: 'ic-balance',
                d: 'En qué se gasta la plata del edificio, mes por mes. Transparencia total.',
                l: ['Usá las flechas para moverte entre meses.',
                    'Si el gasto tiene factura adjunta, podés abrirla.']
            },
            reclamos: {
                t: 'Reclamos', i: 'ic-alerta',
                d: 'Para avisar un problema del edificio (una pérdida, el ascensor, ruidos) y seguir qué se hace.',
                l: ['Cada reclamo es una conversación con la administración: podés contestar y adjuntar fotos.',
                    'Cuando te responden te llega un aviso y el reclamo dice «Respuesta nueva».']
            },
            mensajes: {
                t: 'Mensajes', i: 'ic-mensaje',
                d: 'Un chat directo y privado con la administración de tu edificio.',
                l: []
            },
            reservas: {
                t: 'Reservas', i: 'ic-reserva',
                d: 'Reservá los espacios comunes: SUM, parrilla, pileta.',
                l: ['Elegí el espacio y el día en el calendario del mes.',
                    'Arrastrá sobre el horario que querés y soltá: se abre la confirmación.',
                    'Si querés, avisale al resto de los vecinos: les llega como comunicado.']
            },
            archivos: {
                t: 'Archivos', i: 'ic-carpeta',
                d: 'Reglamentos, actas de asamblea y documentos del consorcio que compartió la administración.',
                l: []
            },
            perfil: {
                t: 'Mi perfil', i: 'ic-vecino',
                d: 'Tus datos y tus unidades. Desde acá también prendés o apagás las notificaciones en este celular.',
                l: []
            }
        }
    };

    var vistas = null;           // Set de secciones cuya ayuda ya se vio
    var pedido = null;

    function textos() { return TEXTOS[CFG.rol] || {}; }

    function cargarVistas() {
        if (pedido) return pedido;
        pedido = fetch('/api/ayuda/vistas').then(function (r) { return r.ok ? r.json() : []; })
            .catch(function () { return []; })
            .then(function (lista) { vistas = new Set(lista || []); return vistas; });
        return pedido;
    }

    function marcarVista(seccion) {
        if (vistas) vistas.add(seccion);
        fetch('/api/ayuda/vista', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ seccion: seccion })
        }).catch(function () {});
    }

    function modal() {
        var m = document.getElementById('nd-ayuda-modal');
        if (m) return m;
        m = document.createElement('div');
        m.id = 'nd-ayuda-modal';
        m.className = 'nd-ayuda-overlay';
        m.innerHTML =
            '<div class="nd-ayuda-caja" role="dialog" aria-modal="true" aria-labelledby="nd-ayuda-t">' +
            '<div class="nd-ayuda-cab"><span class="nd-ayuda-ic"><svg class="ic"><use href="#ic-ayuda"></use></svg></span>' +
            '<h3 id="nd-ayuda-t"></h3>' +
            '<button type="button" class="nd-ayuda-x" aria-label="Cerrar"><svg class="ic ic-sm"><use href="#ic-cerrar"></use></svg></button></div>' +
            '<p class="nd-ayuda-d"></p><ul class="nd-ayuda-l"></ul>' +
            '<div class="nd-ayuda-pie"><span class="nd-ayuda-nota">Lo volvés a ver con el <b>?</b> de arriba.</span>' +
            '<button type="button" class="nd-ayuda-ok">Entendido</button></div></div>';
        document.body.appendChild(m);
        var cerrar = function () { m.classList.remove('open'); };
        m.addEventListener('click', function (e) { if (e.target === m) cerrar(); });
        m.querySelector('.nd-ayuda-x').addEventListener('click', cerrar);
        m.querySelector('.nd-ayuda-ok').addEventListener('click', cerrar);
        document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); });
        return m;
    }

    function abrir(seccion) {
        var x = textos()[seccion];
        if (!x) return;
        var m = modal();
        m.querySelector('#nd-ayuda-t').textContent = x.t;
        m.querySelector('.nd-ayuda-ic').innerHTML = '<svg class="ic"><use href="#' + (x.i || 'ic-ayuda') + '"></use></svg>';
        m.querySelector('.nd-ayuda-d').textContent = x.d;
        var ul = m.querySelector('.nd-ayuda-l');
        ul.innerHTML = '';
        (x.l || []).forEach(function (t) { var li = document.createElement('li'); li.textContent = t; ul.appendChild(li); });
        ul.style.display = (x.l || []).length ? '' : 'none';
        m.classList.add('open');
        marcarVista(seccion);
    }

    /* El "?" en el encabezado de cada sección que tiene ayuda. */
    function ponerBotones() {
        var prefijo = CFG.prefijo || 'section-';
        Object.keys(textos()).forEach(function (seccion) {
            var sec = document.getElementById(prefijo + seccion);
            if (!sec) return;
            var cab = sec.querySelector(CFG.encabezado || '.page-header');
            if (!cab || cab.querySelector('.nd-ayuda-btn')) return;
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'nd-ayuda-btn';
            b.title = '¿De qué se trata esta sección?';
            b.setAttribute('aria-label', '¿De qué se trata esta sección?');
            b.textContent = '?';
            b.addEventListener('click', function () { abrir(seccion); });
            cab.classList.add('nd-con-ayuda');
            cab.appendChild(b);
        });
    }

    /* La primera vez que se entra a una sección, la ayuda se abre sola. Si
       hay otro cartel abierto (una tarifa por confirmar, el alta) se espera a
       la próxima visita: dos modales encimados no se leen. */
    function alEntrar(seccion) {
        if (!textos()[seccion]) return;
        cargarVistas().then(function (v) {
            if (v.has(seccion)) return;
            setTimeout(function () {
                var activa = document.getElementById((CFG.prefijo || 'section-') + seccion);
                if (!activa || !activa.classList.contains('active')) return;
                if (document.querySelector('.modal-overlay.open, .drawer-overlay.open, .full-overlay.visible')) return;
                abrir(seccion);
            }, 450);
        });
    }

    window.NiddoAyuda = { abrir: abrir, alEntrar: alEntrar };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ponerBotones);
    else ponerBotones();
})();
