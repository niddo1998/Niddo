"""Lo que Niddo le cobra a cada administrador, por débito automático de Mercado Pago.

Usa las suscripciones de Mercado Pago (preapproval) con la cuenta de Niddo,
cuyo access token va en la variable MP_NIDDO_ACCESS_TOKEN. Es otra cosa que
`mercadopago_niddo.py`, que es para que los vecinos paguen la expensa a la
cuenta de cada edificio.

Cómo funciona:
1. El administrador toca «Activar débito automático». Niddo crea una
   suscripción pendiente por el total de sus edificios y lo manda al
   `init_point` de Mercado Pago, donde elige la tarjeta y la autoriza.
2. Mercado Pago cobra solo todos los meses y avisa por webhook cada cobro.
3. Si el total cambia (pasó de plan, agregó o sacó un edificio) Niddo
   actualiza el monto de la suscripción, y la pausa mientras tenga pase gratis.

Igual que en el otro módulo, nunca se cree lo que trae el webhook: sólo dice
"mirá tal cosa", y el estado se lee de la API con el token de Niddo. Este
módulo no conoce la base: recibe datos y devuelve diccionarios, así se prueba
sin red.
"""

import hashlib
import hmac
import os
from typing import Optional

from mercadopago_niddo import ErrorMercadoPago, _llamar

__all__ = ['ErrorMercadoPago', 'token', 'configurado', 'cuenta', 'crear', 'leer', 'actualizar',
           'leer_cobro', 'firma_valida']


def token() -> str:
    return os.environ.get('MP_NIDDO_ACCESS_TOKEN', '').strip()


def configurado() -> bool:
    return bool(token())


def cuenta() -> dict:
    """La cuenta dueña del token: para mostrar en el superadmin a qué cuenta entra la plata."""
    c = _llamar('GET', '/users/me', token())
    return {'id': c.get('id'), 'nickname': c.get('nickname'), 'email': c.get('email')}


def _resumen(s: dict) -> dict:
    ar = s.get('auto_recurring') or {}
    return {
        'id': s.get('id'),
        'estado': s.get('status'),                 # pending, authorized, paused, cancelled
        'monto': float(ar.get('transaction_amount') or 0),
        'admin_id': s.get('external_reference'),
        'payer_email': s.get('payer_email'),
        'proximo_cobro': (s.get('next_payment_date') or '')[:10] or None,
        'init_point': s.get('init_point'),
    }


def crear(admin_id: str, payer_email: str, monto: float, motivo: str,
          url_volver: str, url_webhook: str, empieza: Optional[str] = None) -> dict:
    """Una suscripción pendiente: el administrador la autoriza en el init_point.

    `empieza` (ISO, con hora) es cuándo cobra la primera vez: así el que tiene
    pase gratis puede dejar el débito armado y no se le cobra hasta que vence.
    """
    recurrente = {
        'frequency': 1,
        'frequency_type': 'months',
        'transaction_amount': round(float(monto), 2),
        'currency_id': 'ARS',
    }
    if empieza:
        recurrente['start_date'] = empieza
    s = _llamar('POST', '/preapproval', token(), {
        'reason': motivo[:250],
        'external_reference': str(admin_id),
        'payer_email': payer_email,
        'auto_recurring': recurrente,
        'back_url': url_volver,
        'notification_url': url_webhook,
        'status': 'pending',
    })
    return _resumen(s)


def leer(preapproval_id: str) -> dict:
    return _resumen(_llamar('GET', f'/preapproval/{preapproval_id}', token()))


def actualizar(preapproval_id: str, monto: Optional[float] = None,
               estado: Optional[str] = None) -> dict:
    """Cambia el monto y/o el estado (authorized, paused, cancelled)."""
    cuerpo = {}
    if monto is not None:
        cuerpo['auto_recurring'] = {'transaction_amount': round(float(monto), 2), 'currency_id': 'ARS'}
    if estado:
        cuerpo['status'] = estado
    return _resumen(_llamar('PUT', f'/preapproval/{preapproval_id}', token(), cuerpo))


def leer_cobro(authorized_payment_id: str) -> dict:
    """Un cobro mensual de una suscripción, con el estado real del pago."""
    c = _llamar('GET', f'/authorized_payments/{authorized_payment_id}', token())
    pago = c.get('payment') or {}
    return {
        'id': str(c.get('id')),
        'preapproval_id': c.get('preapproval_id'),
        'pago_id': str(pago.get('id')) if pago.get('id') else None,
        'aprobado': pago.get('status') == 'approved',
        'monto': float(c.get('transaction_amount') or 0),
        'fecha': (c.get('debit_date') or c.get('date_created') or '')[:10] or None,
    }


def firma_valida(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """Valida la cabecera x-signature de Mercado Pago con MP_NIDDO_WEBHOOK_SECRET.

    Sin secreto configurado se acepta: igual nada se cree sin leerlo de la API.
    """
    secreto = os.environ.get('MP_NIDDO_WEBHOOK_SECRET', '').strip()
    if not secreto:
        return True
    partes = dict(p.split('=', 1) for p in (x_signature or '').split(',') if '=' in p)
    ts, v1 = partes.get('ts', '').strip(), partes.get('v1', '').strip()
    if not ts or not v1:
        return False
    manifiesto = f'id:{str(data_id).lower()};request-id:{x_request_id};ts:{ts};'
    esperado = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
