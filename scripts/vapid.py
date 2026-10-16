"""Claves de push (VAPID) para Niddo, sin mostrarlas en pantalla.

  python3 scripts/vapid.py generar   crea el par y copia la PÚBLICA al portapapeles
  python3 scripts/vapid.py privada   copia la PRIVADA al portapapeles
  python3 scripts/vapid.py publica   vuelve a copiar la pública
Las guarda en ~/.niddo-vapid.json (sólo vos podés leerlo).
"""
import base64, json, os, subprocess, sys
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization as s

ARCHIVO = os.path.expanduser('~/.niddo-vapid.json')
b64 = lambda x: base64.urlsafe_b64encode(x).decode().rstrip('=')

def copiar(texto):
    subprocess.run(['pbcopy'], input=texto.encode(), check=True)

orden = sys.argv[1] if len(sys.argv) > 1 else ''
if orden == 'generar':
    if os.path.exists(ARCHIVO):
        sys.exit('Ya hay claves en ~/.niddo-vapid.json. Usá "publica" o "privada" para copiarlas.')
    k = ec.generate_private_key(ec.SECP256R1())
    claves = {
        'VAPID_PUBLIC_KEY': b64(k.public_key().public_bytes(s.Encoding.X962, s.PublicFormat.UncompressedPoint)),
        'VAPID_PRIVATE_KEY': b64(k.private_numbers().private_value.to_bytes(32, 'big')),
    }
    fd = os.open(ARCHIVO, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(claves, f)
    copiar(claves['VAPID_PUBLIC_KEY'])
    print('Listo. La clave PÚBLICA está en el portapapeles: pegala en Vercel como VAPID_PUBLIC_KEY.')
elif orden in ('publica', 'privada'):
    claves = json.load(open(ARCHIVO))
    copiar(claves['VAPID_PUBLIC_KEY' if orden == 'publica' else 'VAPID_PRIVATE_KEY'])
    print(f"La clave {'PÚBLICA' if orden == 'publica' else 'PRIVADA'} está en el portapapeles: pegala en Vercel como "
          f"{'VAPID_PUBLIC_KEY' if orden == 'publica' else 'VAPID_PRIVATE_KEY'}.")
else:
    print(__doc__)
