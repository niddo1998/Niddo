"""Cifrado de los secretos que Niddo guarda por cuenta de un administrador.

Hoy es el access token de Mercado Pago de cada consorcio: con él se cobra en
nombre del edificio, así que no puede quedar legible en la base. Fernet (AES +
HMAC, de `cryptography`, que ya viene con pywebpush) con una clave que vive en
la variable NIDDO_CIFRADO_KEY. Sin esa variable se deriva de SECRET_KEY: anda,
pero rotar SECRET_KEY obliga a reconectar Mercado Pago en cada consorcio.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet():
    clave = os.environ.get('NIDDO_CIFRADO_KEY', '')
    if not clave:
        semilla = os.environ.get('SECRET_KEY', '') or 'niddo-dev'
        clave = base64.urlsafe_b64encode(hashlib.sha256(semilla.encode()).digest()).decode()
    return Fernet(clave.encode())


def cifrar(texto):
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(cifrado):
    """El texto original, o None si no se puede (otra clave, dato roto)."""
    if not cifrado:
        return None
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except (InvalidToken, ValueError):
        return None
