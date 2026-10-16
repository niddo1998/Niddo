"""Manda una notificación push de prueba a los dispositivos de un usuario.

    python scripts/push_prueba.py novick43@gmail.com
    python scripts/push_prueba.py novick43@gmail.com "Título" "Texto"

Busca las suscripciones por el mail (vecino o admin) en la base del .env
(DATABASE_URL). La clave privada de push sale de VAPID_PRIVATE_KEY (.env) o, si
no está, de ~/.niddo-vapid.json (ver scripts/vapid.py). Tiene que ser la MISMA
que está en Vercel: con otra, Apple y Google rechazan el envío. Nunca la imprime.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import psycopg
from dotenv import dotenv_values
from pywebpush import WebPushException, webpush

env = dotenv_values(os.path.join(RAIZ, '.env'))
privada = env.get('VAPID_PRIVATE_KEY') or ''
if not privada and os.path.exists(os.path.expanduser('~/.niddo-vapid.json')):
    privada = json.load(open(os.path.expanduser('~/.niddo-vapid.json')))['VAPID_PRIVATE_KEY']
if not privada:
    sys.exit('Falta VAPID_PRIVATE_KEY (en el .env o en ~/.niddo-vapid.json).')

if len(sys.argv) < 2:
    sys.exit(__doc__)
mail = sys.argv[1].lower()
titulo = sys.argv[2] if len(sys.argv) > 2 else 'Tus expensas están disponibles'
cuerpo = sys.argv[3] if len(sys.argv) > 3 else 'Ya podés ver el resumen y cómo pagarlo.'

with psycopg.connect(env['DATABASE_URL']) as c:
    subs = c.execute("""
        select s.endpoint, s.p256dh, s.auth from push_suscripciones s
          left join vecinos v on s.usuario_tipo = 'vecino' and v.id = s.usuario_id
          left join administradores a on s.usuario_tipo = 'admin' and a.id = s.usuario_id
         where lower(coalesce(v.email, a.email)) = %s""", (mail,)).fetchall()
if not subs:
    sys.exit(f'{mail} no tiene ningún dispositivo con notificaciones activadas (Mi perfil → Activar).')

datos = {'titulo': titulo, 'cuerpo': cuerpo, 'url': '/', 'etiqueta': 'prueba'}
for endpoint, p256dh, auth in subs:
    try:
        r = webpush(subscription_info={'endpoint': endpoint, 'keys': {'p256dh': p256dh, 'auth': auth}},
                    data=json.dumps(datos), vapid_private_key=privada,
                    vapid_claims={'sub': 'mailto:niddo1998@gmail.com'}, ttl=3600, timeout=10)
        print('enviada:', r.status_code)
    except WebPushException as e:
        print('falló:', getattr(e.response, 'status_code', None), str(e)[:200])
