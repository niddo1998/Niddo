"""Manda un mail de prueba por Gmail con las credenciales del .env local.

    python scripts/probar_gmail.py                 # se lo manda a GMAIL_USUARIO
    python scripts/probar_gmail.py alguien@mail.com

Necesita GMAIL_USUARIO y GMAIL_APP_PASSWORD en el .env. Ignora Resend a
propósito: lo que se prueba es Gmail.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from dotenv import load_dotenv

load_dotenv(os.path.join(RAIZ, '.env'), override=True)
os.environ.pop('RESEND_API_KEY', None)

import correo

print('proveedor:', correo.proveedor() or 'ninguno (faltan GMAIL_USUARIO / GMAIL_APP_PASSWORD)')
destino = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('GMAIL_USUARIO')
error = correo.enviar([{
    'to': [destino],
    'subject': 'Prueba de Niddo: los mails salen por Gmail',
    'html': '<p>Hola! Este mail lo mandó <b>Niddo</b> por Gmail. '
            'Si lo ves en la bandeja de entrada, quedó andando.</p>',
}])[0]
print('resultado:', 'enviado a ' + destino if error is None else error)
