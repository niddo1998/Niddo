/* ==========================================================================
   Niddo — Números con formato argentino mientras se escriben

   Un <input type="number"> muestra "184532.5": sin separador de miles, con
   punto decimal y sin signo. Nadie en Argentina lee así un importe, y en un
   monto de siete cifras es fácil errarle a un cero. Este archivo convierte los
   campos numéricos en campos de texto que se escriben como se leen:

       $ 1.234.567,89     (importes: los que tienen data-monto)
       1.250,5            (el resto: m², porcentajes, cantidades)

   Lo que NO cambia es lo que ve el resto del código: `input.value` sigue
   devolviendo el número crudo ("1234567.89") y aceptando un número para
   escribir. Así ninguna función que ya lee o escribe estos campos se entera.

   El punto que se tipea se toma como coma decimal: el teclado numérico de la
   computadora y el de muchos Android en inglés sólo tienen punto, y en un
   campo que ya muestra puntos de miles el punto no puede ser otra cosa.
   ========================================================================== */
(function () {
    'use strict';

    var nativo = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');

    function decimalesDe(input) {
        if (input.dataset.decimales) return parseInt(input.dataset.decimales, 10) || 0;
        var step = input.getAttribute('step');
        if (!step || step === 'any') return input.hasAttribute('data-monto') ? 2 : 0;
        var i = step.indexOf('.');
        return i === -1 ? 0 : step.length - i - 1;
    }

    function miles(entero) {
        return entero.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    /* Texto de pantalla a partir de lo que el usuario escribió. `final` es para
       el blur: ahí se completan los decimales de un importe ("1.500" pasa a
       "$ 1.500,00"); mientras se escribe no, porque "1.500," tiene que poder
       quedar a medio escribir. */
    function formatear(input, texto, final) {
        var dec = decimalesDe(input);
        var monto = input.hasAttribute('data-monto');
        var s = String(texto == null ? '' : texto);
        var negativo = input.hasAttribute('data-negativo') && /^\s*(\$\s*)?-/.test(s);
        s = s.replace(/[^\d,]/g, '');
        if (!s) return negativo ? '-' : '';

        var coma = s.indexOf(',');
        var entero = coma === -1 ? s : s.slice(0, coma);
        var frac = coma === -1 ? null : s.slice(coma + 1).replace(/,/g, '').slice(0, dec);
        entero = entero.replace(/^0+(?=\d)/, '');
        if (!entero) entero = '0';

        if (final && monto && dec) frac = ((frac || '') + '00').slice(0, dec);
        if (final && frac !== null && !frac.length) frac = null;

        var out = miles(entero) + (dec && frac !== null ? ',' + frac : '');
        if (negativo) out = '-' + out;
        return monto ? '$ ' + out : out;
    }

    /* Número crudo ("1234.5") a texto de pantalla. */
    function desdeNumero(input, v) {
        if (v === '' || v === null || v === undefined) return '';
        var n = Number(v);
        if (!isFinite(n)) return '';
        var dec = decimalesDe(input);
        var fijo = dec ? n.toFixed(dec) : String(Math.round(n));
        /* Un importe de $ 1.500 se escribe $ 1.500,00; una superficie de 62
           no necesita ",00" al lado. */
        if (!input.hasAttribute('data-monto') && dec) fijo = String(Number(fijo));
        return formatear(input, fijo.replace('.', ','), true);
    }

    /* Texto de pantalla a número crudo, como lo devolvía el input nativo. */
    function aNumero(texto) {
        var s = String(texto || '');
        var negativo = /^\s*(\$\s*)?-/.test(s);
        s = s.replace(/[^\d,]/g, '').replace(',', '.');
        if (!s || s === '.') return '';
        var n = Number(s);
        if (!isFinite(n)) return '';
        return String(negativo ? -n : n);
    }

    /* Dónde queda el cursor: después del mismo número de dígitos (y coma) que
       tenía a su izquierda antes de reformatear. Los puntos de miles aparecen y
       desaparecen, así que contar caracteres a secas lo haría saltar. */
    function significativos(s) { return (s.match(/[\d,]/g) || []).length; }

    function posicionTras(s, n) {
        if (n <= 0) {
            var primero = s.search(/[\d,-]/);
            return primero === -1 ? s.length : primero;
        }
        var vistos = 0;
        for (var i = 0; i < s.length; i++) {
            if (/[\d,]/.test(s[i])) vistos++;
            if (vistos === n) return i + 1;
        }
        return s.length;
    }

    /* Qué separador es el decimal en un número que llegó de otro lado. El
       último de los dos, si están los dos; una coma sola siempre; un punto
       solo, únicamente si deja una o dos cifras atrás (15.5 o 15.50, pero no
       1.500, que en Argentina son mil quinientos). */
    function normalizarPegado(txt) {
        var t = String(txt).replace(/[^\d.,-]/g, '');
        var p = t.lastIndexOf('.'), c = t.lastIndexOf(',');
        var dec = -1;
        if (p !== -1 && c !== -1) dec = Math.max(p, c);
        else if (c !== -1) dec = c;
        else if (p !== -1 && t.indexOf('.') === p && /^\d{1,2}$/.test(t.slice(p + 1))) dec = p;
        if (dec === -1) return t.replace(/[.,]/g, '');
        return t.slice(0, dec).replace(/[.,]/g, '') + ',' + t.slice(dec + 1).replace(/[.,]/g, '');
    }

    function alEscribir(ev) {
        var input = ev.target;
        var visible = nativo.get.call(input);
        var cursor = input.selectionStart == null ? visible.length : input.selectionStart;

        /* El punto recién tipeado es la coma decimal (ver arriba). Se mira en
           el evento `input` y no en `beforeinput` porque algunos teclados de
           Android no mandan el segundo. */
        if (ev.data === '.' && cursor > 0 && visible[cursor - 1] === '.') {
            var sinPunto = visible.slice(0, cursor - 1) + visible.slice(cursor);
            var ponerComa = decimalesDe(input) && sinPunto.indexOf(',') === -1;
            visible = sinPunto.slice(0, cursor - 1) + (ponerComa ? ',' : '') + sinPunto.slice(cursor - 1);
            if (!ponerComa) cursor -= 1;
        } else if (ev.data && ev.data.length > 1 && /[.,]/.test(ev.data)) {
            /* Un número pegado o dictado llega entero: "1.234,56", "1234.56"
               o "1,234.56". Se traduce a la forma argentina antes de mezclarlo
               con lo que ya había escrito. */
            var inicio = cursor - ev.data.length;
            if (inicio >= 0 && visible.slice(inicio, cursor) === ev.data) {
                var pegado = normalizarPegado(ev.data);
                visible = visible.slice(0, inicio) + pegado + visible.slice(cursor);
                cursor = inicio + pegado.length;
            }
        }

        var antes = significativos(visible.slice(0, cursor));
        var nuevo = formatear(input, visible, false);
        if (nuevo === nativo.get.call(input)) return;
        nativo.set.call(input, nuevo);
        try {
            var pos = posicionTras(nuevo, antes);
            input.setSelectionRange(pos, pos);
        } catch (e) { /* algunos navegadores no dejan en campos sin foco */ }
    }

    function alSalir(ev) {
        var input = ev.target;
        var visible = nativo.get.call(input);
        var final = formatear(input, visible, true);
        if (final !== visible) nativo.set.call(input, final);
    }

    function mejorar(input) {
        if (input.dataset.ndNumero) return;
        if (input.hasAttribute('data-sin-formato')) return;
        input.dataset.ndNumero = '1';

        var inicial = nativo.get.call(input);
        var dec = decimalesDe(input);
        input.type = 'text';
        input.setAttribute('inputmode', dec ? 'decimal' : 'numeric');
        input.setAttribute('autocomplete', 'off');
        if (input.hasAttribute('data-monto') && !input.getAttribute('placeholder')) {
            input.setAttribute('placeholder', '$ 0,00');
        } else if (input.getAttribute('placeholder') === '0.00') {
            input.setAttribute('placeholder', input.hasAttribute('data-monto') ? '$ 0,00' : '0,00');
        }

        Object.defineProperty(input, 'value', {
            configurable: true,
            get: function () { return aNumero(nativo.get.call(this)); },
            set: function (v) { nativo.set.call(this, desdeNumero(this, v)); }
        });
        /* valueAsNumber lo usaban algunos navegadores viejos; por las dudas. */
        Object.defineProperty(input, 'valueAsNumber', {
            configurable: true,
            get: function () { var v = this.value; return v === '' ? NaN : Number(v); }
        });

        input.addEventListener('input', alEscribir);
        input.addEventListener('blur', alSalir);

        if (inicial) input.value = inicial;
    }

    function mejorarEn(raiz) {
        if (!raiz || !raiz.querySelectorAll) return;
        if (raiz.matches && raiz.matches('input[type="number"], input[data-monto]')) mejorar(raiz);
        var lista = raiz.querySelectorAll('input[type="number"], input[data-monto]');
        for (var i = 0; i < lista.length; i++) mejorar(lista[i]);
    }

    window.NiddoNumeros = {
        mejorar: mejorar,
        mejorarEn: mejorarEn,
        aNumero: aNumero,
        formatear: function (input, n) { return desdeNumero(input, n); }
    };

    function arrancar() {
        mejorarEn(document);
        /* Los campos que se arman con innerHTML después de cargar —la tabla de
           la carga con IA, el cartel de tarifas— se mejoran apenas aparecen. */
        if (window.MutationObserver) {
            new MutationObserver(function (cambios) {
                for (var i = 0; i < cambios.length; i++) {
                    var nodos = cambios[i].addedNodes;
                    for (var j = 0; j < nodos.length; j++) {
                        if (nodos[j].nodeType === 1) mejorarEn(nodos[j]);
                    }
                }
            }).observe(document.body, { childList: true, subtree: true });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancar);
    } else {
        arrancar();
    }
})();
