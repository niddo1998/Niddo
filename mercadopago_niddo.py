"""Cobrar la expensa con Mercado Pago (Checkout Pro).

Cada consorcio conecta SU cuenta de Mercado Pago pegando el access token de
producción: la plata entra directo a la cuenta del edificio y Niddo no la toca.
Vive aparte de `app.py` y no conoce la base: recibe datos, habla con la API
de Mercado Pago y devuelve diccionarios. Así se prueba sin red.

La confirmación del pago nunca se cree por lo que trae el webhook: el webhook
sólo dice "mirá el pago N", y el estado se lee de la API con el token del
consorcio. Un POST falso a la URL del webhook no puede marcar nada como pagado.
"""

import json
import urllib.error
import urllib.request

API = 'https://api.mercadopago.com'


class ErrorMercadoPago(Exception):
    pass


def _llamar(metodo, ruta, token, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(API + ruta, data=datos, method=metodo, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors='replace')[:300]
        raise ErrorMercadoPago(f'Mercado Pago respondió {e.code}: {detalle}') from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErrorMercadoPago('No pudimos hablar con Mercado Pago. Probá de nuevo en un rato.') from e


def cuenta(token):
    """Los datos de la cuenta dueña del token. Sirve para validarlo al conectar."""
    return _llamar('GET', '/users/me', token)


def crear_preferencia(token, cobro, consorcio_nombre, unidad, url_volver, url_webhook):
    """El link de pago de UN cobro. Devuelve {'id', 'init_point'}."""
    total = round(float(cobro['total']), 2)
    pref = _llamar('POST', '/checkout/preferences', token, {
        'items': [{
            'id': str(cobro['id']),
            'title': f"Expensa {cobro.get('periodo', '')} — {consorcio_nombre} — UF {unidad}"[:250],
            'quantity': 1,
            'currency_id': 'ARS',
            'unit_price': total,
        }],
        'external_reference': str(cobro['id']),
        'notification_url': url_webhook,
        'back_urls': {'success': url_volver, 'pending': url_volver, 'failure': url_volver},
        'auto_return': 'approved',
        'statement_descriptor': 'EXPENSAS',
    })
    return {'id': pref.get('id'), 'init_point': pref.get('init_point')}


def pago(token, payment_id):
    """El pago tal como lo ve Mercado Pago: estado, monto y a qué cobro pertenece."""
    p = _llamar('GET', f'/v1/payments/{int(payment_id)}', token)
    return {
        'id': str(p.get('id')),
        'estado': p.get('status'),
        'monto': float(p.get('transaction_amount') or 0),
        'cobro_id': p.get('external_reference'),
        'fecha': (p.get('date_approved') or '')[:10] or None,
    }
