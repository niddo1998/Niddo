"""El chat 1 a 1 entre el administrador y el vecino.

La sección Mensajería del panel decía "estará disponible en la próxima
versión". Estos tests cubren las dos cosas que hay que no equivocar: que el
hilo de cada vecino sea suyo y sólo suyo —el hilo se direcciona por UUID en la
URL, así que sin chequeo alcanza con cambiar el id para leer la conversación
del vecino de al lado— y que los no leídos sean de verdad los del otro lado.
"""

import io

import pytest


PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40


@pytest.fixture
def admin(base, app_modulo):
    app_modulo.app.config['TESTING'] = True
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin', 'email': 'admin@test',
                     'name': 'Admin', 'role': 'admin'}
    return c


@pytest.fixture
def otro_admin(base, app_modulo):
    """Administrador de `cons-2`, que no es de nadie de estos tests."""
    base['administradores'].append({
        'id': 'admin-2', 'auth0_id': 'auth0|admin2', 'estado': 'aprobado',
        'es_superadmin': False, 'email': 'a2@test', 'nombre': 'Otro',
        'ultima_actividad': '2999-01-01T00:00:00+00:00'})
    c = app_modulo.app.test_client()
    with c.session_transaction() as s:
        s['user'] = {'sub': 'auth0|admin2', 'email': 'a2@test',
                     'name': 'Otro', 'role': 'admin'}
    return c


def _mensaje(base, **campos):
    fila = {'id': f'msg-{len(base.setdefault("mensajes", [])) + 1}',
            'consorcio_id': 'cons-1', 'vecino_id': 'vec-1', 'autor': 'vecino',
            'cuerpo': 'Hola', 'leido_at': None,
            'created_at': '2026-08-20T10:00:00+00:00'}
    fila.update(campos)
    base['mensajes'].append(fila)
    return fila


# ── El hilo es del vecino ─────────────────────────────────────────────────────

def test_el_vecino_ve_su_hilo(client, base):
    _mensaje(base, cuerpo='Se rompió el portero')
    r = client.get('/api/mensajes')
    assert r.status_code == 200
    assert [m['cuerpo'] for m in r.get_json()] == ['Se rompió el portero']


def test_el_vecino_no_ve_el_hilo_de_otro(client, base):
    _mensaje(base, vecino_id='vec-2', consorcio_id='cons-2', cuerpo='Ajeno')
    assert client.get('/api/mensajes').get_json() == []


def test_abrir_el_hilo_marca_leidos_los_del_admin(client, base):
    m = _mensaje(base, autor='admin', cuerpo='Ya lo vemos')
    client.get('/api/mensajes')
    assert m['leido_at'] is not None


def test_abrir_el_hilo_no_marca_leidos_los_propios(client, base):
    """Lo que escribió el vecino lo lee el administrador, no él mismo."""
    m = _mensaje(base, autor='vecino')
    client.get('/api/mensajes')
    assert m['leido_at'] is None


def test_el_badge_cuenta_lo_que_escribió_el_admin(client, base):
    _mensaje(base, autor='admin')
    _mensaje(base, autor='admin')
    _mensaje(base, autor='vecino')
    assert client.get('/api/mensajes/no-leidos').get_json()['sin_leer'] == 2


# ── Escribir ──────────────────────────────────────────────────────────────────

def test_el_vecino_escribe(client, base):
    r = client.post('/api/mensajes', json={'cuerpo': 'Consulta'})
    assert r.status_code == 201
    assert base['mensajes'][0]['autor'] == 'vecino'
    assert base['mensajes'][0]['consorcio_id'] == 'cons-1'


def test_un_mensaje_vacio_no_es_un_mensaje(client, base):
    r = client.post('/api/mensajes', json={'cuerpo': '   '})
    assert r.status_code == 400
    assert base.get('mensajes', []) == []


def test_una_foto_sola_si_es_un_mensaje(client, base):
    r = client.post('/api/mensajes', data={
        'cuerpo': '', 'adjunto': (io.BytesIO(PNG), 'foto.png')},
        content_type='multipart/form-data')
    assert r.status_code == 201
    assert base['mensajes'][0]['adjunto_nombre'] == 'foto.png'


def test_el_listado_no_devuelve_el_adjunto_en_base64(client, base):
    """Un hilo con tres fotos adentro son varios megas por cada apertura."""
    _mensaje(base, adjunto_base64='AAAA', adjunto_nombre='foto.png')
    assert 'adjunto_base64' not in client.get('/api/mensajes').get_json()[0]


# ── El lado del administrador ─────────────────────────────────────────────────

def test_el_admin_ve_los_hilos_de_sus_consorcios(admin, base):
    _mensaje(base, cuerpo='Del mío')
    _mensaje(base, vecino_id='vec-2', consorcio_id='cons-2', cuerpo='Del ajeno')
    hilos = admin.get('/api/admin/mensajes').get_json()['hilos']
    assert [h['vecino_id'] for h in hilos] == ['vec-1']


def test_el_hilo_trae_lo_ultimo_y_lo_que_falta_leer(admin, base):
    _mensaje(base, autor='vecino', cuerpo='Primero')
    _mensaje(base, autor='vecino', cuerpo='Segundo')
    hilo = admin.get('/api/admin/mensajes').get_json()['hilos'][0]
    assert hilo['ultimo']['cuerpo'] == 'Segundo'
    assert hilo['sin_leer'] == 2


def test_el_admin_puede_escribir_primero(admin, base):
    """Los vecinos sin hilo también son destinatarios posibles."""
    vecinos = admin.get('/api/admin/mensajes').get_json()['vecinos']
    assert 'vec-1' in [v['id'] for v in vecinos]


def test_abrir_el_hilo_marca_leidos_los_del_vecino(admin, base):
    m = _mensaje(base, autor='vecino')
    admin.get('/api/admin/mensajes/hilo/vec-1')
    assert m['leido_at'] is not None


def test_el_admin_responde_como_admin(admin, base):
    r = admin.post('/api/admin/mensajes/hilo/vec-1', json={'cuerpo': 'Lo vemos hoy'})
    assert r.status_code == 201
    assert base['mensajes'][0]['autor'] == 'admin'
    assert base['mensajes'][0]['admin_id'] == 'admin-1'


def test_un_admin_no_abre_el_hilo_de_un_vecino_ajeno(otro_admin, base):
    _mensaje(base)
    assert otro_admin.get('/api/admin/mensajes/hilo/vec-1').status_code == 404


def test_un_admin_no_escribe_en_el_hilo_de_un_vecino_ajeno(otro_admin, base):
    r = otro_admin.post('/api/admin/mensajes/hilo/vec-1', json={'cuerpo': 'Hola'})
    assert r.status_code == 404
    assert base.get('mensajes', []) == []


# ── Los adjuntos ──────────────────────────────────────────────────────────────

def test_el_vecino_no_baja_el_adjunto_de_otro(client, base):
    m = _mensaje(base, vecino_id='vec-2', consorcio_id='cons-2',
                 adjunto_base64='AAAA', adjunto_nombre='ajeno.png')
    assert client.get(f'/api/mensajes/{m["id"]}/adjunto').status_code == 404


def test_un_mensaje_sin_adjunto_no_devuelve_nada(client, base):
    m = _mensaje(base)
    assert client.get(f'/api/mensajes/{m["id"]}/adjunto').status_code == 404


# ── El mail del comunicado ────────────────────────────────────────────────────

def test_el_mail_del_comunicado_respeta_los_saltos_de_linea(base, app_modulo, monkeypatch):
    """`Markup.replace` escapa lo que se le pasa.

    `escape(cuerpo).replace('\\n', '<br>')` devolvía "&lt;br&gt;", así que el
    vecino recibía el mail con esos caracteres a la vista en cada renglón.
    """
    enviados = []
    monkeypatch.setattr(app_modulo, '_enviar_mail',
                        lambda dest, asunto, html: enviados.append(html))
    base['vecinos'][0]['email'] = 'uno@test'

    app_modulo._mail_comunicado(
        {'titulo': 'Corte de agua', 'cuerpo': 'Mañana de 9 a 12.\nToda la torre.',
         'consorcio_id': 'cons-1'},
        {'nombre': 'Mío'})

    assert enviados, 'no se mandó ningún mail'
    assert '<br>' in enviados[0]
    assert '&lt;br&gt;' not in enviados[0]


def test_el_cuerpo_del_comunicado_va_escapado(base, app_modulo, monkeypatch):
    """Lo escribe el administrador y termina en la casilla de todo el edificio."""
    enviados = []
    monkeypatch.setattr(app_modulo, '_enviar_mail',
                        lambda dest, asunto, html: enviados.append(html))
    base['vecinos'][0]['email'] = 'uno@test'

    app_modulo._mail_comunicado(
        {'titulo': 'Aviso', 'cuerpo': '<script>alert(1)</script>', 'consorcio_id': 'cons-1'},
        {'nombre': 'Mío'})

    assert '<script>alert(1)</script>' not in enviados[0]
    assert '&lt;script&gt;' in enviados[0]


def test_el_comunicado_no_le_muestra_a_nadie_la_libreta_del_edificio(base, app_modulo, monkeypatch):
    """Un mail por vecino, no uno con cuarenta direcciones en el "to".

    Además de la privacidad, Resend corta a los 50 destinatarios: el envío
    fallaba entero, el error se tragaba, y el administrador quedaba creyendo
    que el comunicado había salido.
    """
    envios = []
    monkeypatch.setattr(app_modulo, '_enviar_mail',
                        lambda dest, asunto, html: envios.append(list(dest)))
    base['vecinos'] = [
        {'id': 'v1', 'email': 'uno@test', 'consorcio_id': 'cons-1'},
        {'id': 'v2', 'email': 'dos@test', 'consorcio_id': 'cons-1'},
        {'id': 'v3', 'email': 'ajeno@test', 'consorcio_id': 'cons-2'},
    ]

    app_modulo._mail_comunicado({'titulo': 'Aviso', 'cuerpo': 'Hola', 'consorcio_id': 'cons-1'},
                                {'nombre': 'Mío'})

    assert envios == [['dos@test'], ['uno@test']]
