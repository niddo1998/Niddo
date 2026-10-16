"""Niddo con datos falsos en memoria, para mirar pantallas sin tocar la base.

    python scripts/devserver_datos_falsos.py 5056

Usa el mismo doble de la base que los tests (tests/conftest.py). Para entrar:
    http://localhost:5056/dev/entrar/admin
    http://localhost:5056/dev/entrar/vecino
    http://localhost:5056/l/demo-token-123456   (página pública de una liquidación)
Nada de lo que se haga acá se guarda: se pierde al cortar el servidor.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.environ.update(SECRET_KEY='dev', AUTH0_DOMAIN='x.auth0.com', AUTH0_CLIENT_ID='x',
                  AUTH0_CLIENT_SECRET='x', NIDDO_LOCAL='1',
                  DATABASE_URL='postgresql://test@localhost/test',
                  GMAIL_USUARIO='', GMAIL_APP_PASSWORD='', RESEND_API_KEY='')

import app as app_mod
from tests.conftest import FakeSupabase, _datos

store = _datos()
store['liquidaciones'] = [{
    'id': 'liq-1', 'consorcio_id': 'cons-1', 'admin_id': 'admin-1', 'periodo': '2026-10',
    'numero_revision': 1, 'estado': 'publicada', 'token_publico': 'demo-token-123456',
    'fecha_vencimiento_1': '2026-10-10',
    'consorcios': {'nombre': 'Torres del Parque', 'direccion': 'Av. Rivadavia 5200, CABA'}}]
store['liquidacion_rubros'] = [
    {'id': 'r1', 'liquidacion_id': 'liq-1', 'numero_rubro': 1,
     'nombre': 'Remuneraciones al personal y cargas sociales', 'subtotal': 812300},
    {'id': 'r2', 'liquidacion_id': 'liq-1', 'numero_rubro': 4, 'nombre': 'Servicios públicos', 'subtotal': 143900}]
store['liquidacion_items'] = [
    {'id': 'i1', 'rubro_id': 'r1', 'descripcion': 'Sueldo encargado octubre', 'monto': 812300,
     'gasto_id': 'g1', 'proveedor_nombre': 'Carlos Gómez', 'fecha_pago': '2026-10-05'},
    {'id': 'i2', 'rubro_id': 'r2', 'descripcion': 'Edesur, luz espacios comunes', 'monto': 98400,
     'gasto_id': 'g2', 'proveedor_nombre': 'Edesur S.A.', 'comprobante_tipo': 'Factura B'},
    {'id': 'i3', 'rubro_id': 'r2', 'descripcion': 'AySA, agua', 'monto': 45500, 'gasto_id': 'g3'}]
store['comprobantes_gastos'] = [{'gasto_id': 'g2', 'archivo_nombre': 'edesur.pdf',
                                 'archivo_base64': 'JVBERi0xLjQK', 'mime_type': 'application/pdf'}]
store['archivos_consorcio'] = []
store['administradores'][0].update(matricula='12345', cuit='20-12345678-6',
                                   nombre_contacto='Administración Gómez')
app_mod.supabase = FakeSupabase(store)
app = app_mod.app


@app.route('/dev/entrar/<rol>')
def dev_entrar(rol):
    from flask import redirect, session
    session['user'] = ({'sub': 'auth0|admin', 'email': 'admin@test', 'name': 'Admin Demo', 'role': 'admin'}
                       if rol == 'admin' else
                       {'sub': 'auth0|uno', 'email': 'uno@test', 'name': 'Uno', 'role': 'vecino'})
    return redirect(f'/dashboard/{rol}')


if __name__ == '__main__':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True
    puerto = int(os.environ.get('PORT') or (sys.argv[1] if len(sys.argv) > 1 else 5056))
    app.run(host='127.0.0.1', port=puerto, debug=False)
