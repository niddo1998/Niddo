import io
import os
import json
import base64
from datetime import datetime, timezone, date
from typing import Optional
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for,
    session, request, jsonify, send_file, Response
)
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from supabase import create_client, Client


# ── Config ─────────────────────────────────────────────────────────────────────
load_dotenv()

# Resolve paths relative to *this* file so the app works both locally
# and when imported from api/index.py on Vercel.
_HERE = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(_HERE, 'templates'),
    static_folder=os.path.join(_HERE, 'static'),
)
app.secret_key = os.environ['SECRET_KEY']
app.config['SESSION_COOKIE_SECURE'] = False   # True en producción (HTTPS)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

# Fix for reverse proxy headers (Vercel) so url_for uses HTTPS
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# ── Auth0 ──────────────────────────────────────────────────────────────────────
AUTH0_DOMAIN = os.environ['AUTH0_DOMAIN']

oauth = OAuth(app)
auth0 = oauth.register(
    'auth0',
    client_id=os.environ['AUTH0_CLIENT_ID'],
    client_secret=os.environ['AUTH0_CLIENT_SECRET'],
    client_kwargs={'scope': 'openid profile email'},
    server_metadata_url=f'https://{AUTH0_DOMAIN}/.well-known/openid-configuration',
)

# ── Supabase ───────────────────────────────────────────────────────────────────
supabase: Client = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_KEY'],
)

# ── Helpers ────────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_user(role: str, auth0_id: str, email: str, nombre: str) -> None:
    table = 'administradores' if role == 'admin' else 'vecinos'
    res = supabase.table(table).upsert(
        {'auth0_id': auth0_id, 'email': email, 'nombre': nombre, 'last_login': now_iso()},
        on_conflict='auth0_id'
    ).execute()

    if role == 'vecino' and res.data:
        vecino_id = res.data[0]['id']
        current_consorcio = res.data[0].get('consorcio_id')
        # Si el vecino no tiene consorcio asignado aún, intentar auto-asociación por email
        if not current_consorcio:
            uf_res = supabase.table('unidades_funcionales').select('id, consorcio_id, numero').eq('vecino_email', email).is_('vecino_id', 'null').execute()
            if uf_res.data:
                uf = uf_res.data[0]
                # Actualizar el consorcio y unidad del vecino
                supabase.table('vecinos').update({
                    'consorcio_id': uf['consorcio_id'],
                    'unidad': uf['numero']
                }).eq('id', vecino_id).execute()
                # Vincular el vecino_id en la unidad funcional
                supabase.table('unidades_funcionales').update({
                    'vecino_id': vecino_id
                }).eq('id', uf['id']).execute()


def get_admin_id() -> Optional[str]:
    """Devuelve el UUID de la fila en `administradores` para el usuario en sesión."""
    user = session.get('user')
    if not user:
        return None
    result = supabase.table('administradores').select('id').eq('auth0_id', user['sub']).execute()
    return result.data[0]['id'] if result.data else None


def get_vecino_id() -> Optional[str]:
    """Devuelve el UUID de la fila en `vecinos` para el vecino en sesión."""
    user = session.get('user')
    if not user:
        return None
    result = supabase.table('vecinos').select('id').eq('auth0_id', user['sub']).execute()
    return result.data[0]['id'] if result.data else None


def excel_response(wb, filename: str) -> Response:
    import openpyxl
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     download_name=filename, as_attachment=True)


def pdf_response(buf: io.BytesIO, filename: str) -> Response:
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', download_name=filename, as_attachment=True)


def make_excel(headers: list, rows: list, sheet_name: str):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    header_fill = PatternFill("solid", fgColor="7C3AED")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
        ws.column_dimensions[cell.column_letter].width = max(len(h) + 4, 14)
    for r, row in enumerate(rows, 2):
        for c, val in enumerate(row, 1):
            ws.cell(row=r, column=c, value=val)
    return wb


TIPOS_UF_VALIDOS = ['departamento', 'local', 'cochera', 'baulera']
MARCA_FILA_EJEMPLO = '(borrar fila)'


def es_fila_ejemplo(texto: str) -> bool:
    return MARCA_FILA_EJEMPLO in (texto or '').lower()


def build_carga_masiva_template(consorcios_existentes: list):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    header_fill = PatternFill("solid", fgColor="7C3AED")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    example_font = Font(italic=True, color="9CA3AF")

    def style_header(ws, headers):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            ws.column_dimensions[cell.column_letter].width = max(len(h) + 4, 16)

    wb = openpyxl.Workbook()

    ws_info = wb.active
    ws_info.title = 'Instrucciones'
    ws_info.column_dimensions['A'].width = 100
    info_lines = [
        ('Carga masiva de Consorcios y Unidades Funcionales', True),
        ('', False),
        ('1. Completá la hoja "Consorcios" para crear edificios nuevos. Dejala vacía si solo vas a cargar', False),
        ('   unidades de consorcios que ya existen.', False),
        ('2. Completá la hoja "Unidades" con las UF a cargar. En la columna "consorcio" escribí el nombre', False),
        ('   exacto del consorcio (nuevo, tal como lo escribiste en la hoja "Consorcios", o uno ya existente,', False),
        ('   tal como figura en la hoja "Consorcios existentes").', False),
        ('3. Guardá el archivo y subilo en el panel. No cambies los nombres de las hojas ni de las columnas.', False),
        ('', False),
        ('Campos obligatorios: nombre (Consorcios); consorcio y numero (Unidades). El resto es opcional.', False),
        (f'Valores válidos para "tipo": {", ".join(TIPOS_UF_VALIDOS)}.', False),
        ('Si un consorcio o una unidad ya existe, se reutiliza/omite automáticamente (no se duplica).', False),
    ]
    for i, (text, bold) in enumerate(info_lines, 1):
        cell = ws_info.cell(row=i, column=1, value=text)
        if bold:
            cell.font = Font(bold=True, size=13)

    ws_c = wb.create_sheet('Consorcios')
    style_header(ws_c, ['nombre*', 'direccion', 'cuit', 'pisos', 'unidades_totales', 'encargado_nombre', 'encargado_tel'])
    example_c = ['Edificio Ejemplo 123 (borrar fila)', 'Av. Siempreviva 742', '30-12345678-9', 8, 24, 'Juan Pérez', '+54 9 11 1234-5678']
    for c, val in enumerate(example_c, 1):
        ws_c.cell(row=2, column=c, value=val).font = example_font

    ws_u = wb.create_sheet('Unidades')
    style_header(ws_u, ['consorcio*', 'numero*', 'piso', 'tipo', 'superficie_m2', 'vecino_nombre', 'vecino_email'])
    example_u = ['Edificio Ejemplo 123 (borrar fila)', '3B', '3', 'departamento', 65.5, 'Juan Pérez', 'juan@mail.com']
    for c, val in enumerate(example_u, 1):
        ws_u.cell(row=2, column=c, value=val).font = example_font
    tipo_dv = DataValidation(type='list', formula1=f'"{",".join(TIPOS_UF_VALIDOS)}"', allow_blank=True, showErrorMessage=False)
    ws_u.add_data_validation(tipo_dv)
    tipo_dv.add('D2:D1000')
    if consorcios_existentes:
        nombres = [c['nombre'] for c in consorcios_existentes]
        con_dv = DataValidation(type='list', formula1=f'"{",".join(nombres)[:255]}"', allow_blank=True, showErrorMessage=False)
        ws_u.add_data_validation(con_dv)
        con_dv.add('A2:A1000')

    ws_ref = wb.create_sheet('Consorcios existentes')
    style_header(ws_ref, ['nombre', 'direccion'])
    for r, c in enumerate(consorcios_existentes, 2):
        ws_ref.cell(row=r, column=1, value=c['nombre'])
        ws_ref.cell(row=r, column=2, value=c.get('direccion', ''))
    if not consorcios_existentes:
        ws_ref.cell(row=2, column=1, value='(todavía no tenés consorcios cargados)').font = example_font

    wb.active = 0
    return wb


def make_pdf(title: str, headers: list, rows: list) -> io.BytesIO:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles['Title']), Spacer(1, 0.4*cm)]
    data = [headers] + rows
    col_w = (landscape(A4)[0] - 2*cm) / max(len(headers), 1)
    t = Table(data, colWidths=[col_w] * len(headers), repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7C3AED')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 8),
        ('GRID',       (0,0), (-1,-1), 0.4, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f5f0ff')]),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(t)
    doc.build(elements)
    return buf


# ── Auth decorator ─────────────────────────────────────────────────────────────
def require_auth(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = session.get('user')
            if not user:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'No autenticado'}), 401
                return redirect(url_for('login'))
            if allowed_roles and user.get('role') not in allowed_roles:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Sin permiso'}), 403
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated
    return decorator


@app.errorhandler(Exception)
def _api_errors_como_json(e):
    """Toda excepción bajo /api/ vuelve como JSON con su motivo.

    Sin esto Flask responde su página HTML de error, el cliente hace r.json(),
    falla el parseo y cae en el `catch(()=>({error:'Error'}))` de admin_dashboard:
    el usuario ve un toast "Error" sin causa y no queda nada con qué diagnosticar.
    """
    from werkzeug.exceptions import HTTPException
    if not request.path.startswith('/api/'):
        # Las páginas siguen con el manejo por defecto: un HTTPException ya es una
        # respuesta válida, cualquier otra cosa se re-lanza para no devolver el
        # objeto excepción como si fuera un body.
        if isinstance(e, HTTPException):
            return e
        raise e
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    app.logger.exception('Error no atrapado en %s', request.path)
    return jsonify({'error': f'{type(e).__name__}: {e}'}), 500


# ── Páginas públicas ───────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    user = session.get('user')
    if user:
        return redirect(url_for('dashboard', role=user['role']))
    return render_template('login.html')


# ── Auth0 flow ─────────────────────────────────────────────────────────────────
@app.route('/auth/login')
def auth_login():
    role = request.args.get('role', 'vecino')
    if role not in ('admin', 'vecino'):
        role = 'vecino'
    session['pending_role'] = role
    callback_url = url_for('auth_callback', _external=True)
    return auth0.authorize_redirect(redirect_uri=callback_url)


@app.route('/auth/callback')
def auth_callback():
    token = auth0.authorize_access_token()
    userinfo = token.get('userinfo', {})
    auth0_id = userinfo.get('sub')
    email    = userinfo.get('email', '')
    nombre   = userinfo.get('name', email)
    role     = session.pop('pending_role', 'vecino')
    upsert_user(role, auth0_id, email, nombre)
    session['user'] = {'sub': auth0_id, 'email': email, 'name': nombre, 'role': role}
    return redirect(url_for('dashboard', role=role))


@app.route('/auth/logout')
def auth_logout():
    session.clear()
    return redirect(
        f'https://{AUTH0_DOMAIN}/v2/logout'
        f'?returnTo={url_for("index", _external=True)}'
        f'&client_id={os.environ["AUTH0_CLIENT_ID"]}'
    )


# ── Dashboards ────────────────────────────────────────────────────────────────
@app.route('/dashboard/<role>')
@require_auth()
def dashboard(role):
    user = session['user']
    if user['role'] != role:
        return redirect(url_for('dashboard', role=user['role']))
    if role == 'admin':
        return render_template('admin_dashboard.html', user=user)
    elif role == 'vecino':
        return render_template('vecino_dashboard.html', user=user)
    return redirect(url_for('login'))


# ══════════════════════════════════════════════════════════════════════════════
# API — CONSORCIOS
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/consorcios', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_consorcios_list():
    admin_id = get_admin_id()
    res = supabase.table('consorcios').select('*').eq('admin_id', admin_id).order('nombre').execute()
    return jsonify(res.data)


@app.route('/api/consorcios', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_consorcios_create():
    admin_id = get_admin_id()
    d = request.json
    payload = {
        'nombre': d.get('nombre', '').strip(),
        'direccion': d.get('direccion', ''),
        'cuit': d.get('cuit', ''),
        'pisos': d.get('pisos'),
        'unidades_totales': d.get('unidades_totales'),
        'encargado_nombre': d.get('encargado_nombre', ''),
        'encargado_tel': d.get('encargado_tel', ''),
        'admin_id': admin_id,
    }
    res = supabase.table('consorcios').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/consorcios/<cid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_consorcios_update(cid):
    admin_id = get_admin_id()
    d = request.json
    payload = {k: v for k, v in {
        'nombre': d.get('nombre'),
        'direccion': d.get('direccion'),
        'cuit': d.get('cuit'),
        'pisos': d.get('pisos'),
        'unidades_totales': d.get('unidades_totales'),
        'encargado_nombre': d.get('encargado_nombre'),
        'encargado_tel': d.get('encargado_tel'),
    }.items() if v is not None}
    res = supabase.table('consorcios').update(payload).eq('id', cid).eq('admin_id', admin_id).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/consorcios/<cid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_consorcios_delete(cid):
    admin_id = get_admin_id()
    supabase.table('consorcios').delete().eq('id', cid).eq('admin_id', admin_id).execute()
    return jsonify({'ok': True})


@app.route('/api/consorcios/<cid>/unidades', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_ufs_list(cid):
    res = supabase.table('unidades_funcionales').select('*').eq('consorcio_id', cid).order('numero').execute()
    ufs = res.data or []

    # Obtener todos los vecinos vinculados a este consorcio
    vecinos_res = supabase.table('vecinos').select('id, nombre, email, rol, unidad, unidad_id').eq('consorcio_id', cid).execute()
    vecinos = vecinos_res.data or []

    # Agrupar vecinos por unidad_id o por número de unidad como fallback
    vecinos_por_uf = {}
    for v in vecinos:
        key = v.get('unidad_id') or v.get('unidad')
        if key:
            if key not in vecinos_por_uf:
                vecinos_por_uf[key] = []
            vecinos_por_uf[key].append(v)

    # Asociar los vecinos correspondientes a cada UF
    for uf in ufs:
        uf_key_id = uf['id']
        uf_key_num = uf['numero']
        associated = vecinos_por_uf.get(uf_key_id, [])
        if not associated:
            associated = vecinos_por_uf.get(uf_key_num, [])
        uf['vecinos_vinculados'] = associated

    return jsonify(ufs)


@app.route('/api/consorcios/<cid>/unidades', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_ufs_create(cid):
    d = request.json
    payload = {
        'consorcio_id': cid,
        'numero': d.get('numero', '').strip(),
        'piso': d.get('piso', ''),
        'tipo': d.get('tipo', 'departamento'),
        'superficie_m2': d.get('superficie_m2'),
        'vecino_nombre': d.get('vecino_nombre', ''),
        'vecino_email': d.get('vecino_email', ''),
    }
    res = supabase.table('unidades_funcionales').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/consorcios/<cid>/unidades/<uid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_ufs_update(cid, uid):
    d = request.json
    payload = {k: v for k, v in {
        'numero': d.get('numero'),
        'piso': d.get('piso'),
        'tipo': d.get('tipo'),
        'superficie_m2': d.get('superficie_m2'),
        'vecino_nombre': d.get('vecino_nombre'),
        'vecino_email': d.get('vecino_email'),
    }.items() if v is not None}
    res = supabase.table('unidades_funcionales').update(payload).eq('id', uid).eq('consorcio_id', cid).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/consorcios/<cid>/unidades/<uid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_ufs_delete(cid, uid):
    supabase.table('unidades_funcionales').delete().eq('id', uid).eq('consorcio_id', cid).execute()
    return jsonify({'ok': True})


@app.route('/api/consorcios/plantilla')
@require_auth(allowed_roles=['admin'])
def descargar_plantilla_carga_masiva():
    admin_id = get_admin_id()
    existentes = supabase.table('consorcios').select('nombre,direccion').eq('admin_id', admin_id).order('nombre').execute().data or []
    wb = build_carga_masiva_template(existentes)
    return excel_response(wb, 'plantilla_carga_masiva.xlsx')


@app.route('/api/consorcios/carga-masiva', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_carga_masiva():
    admin_id = get_admin_id()
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No se envió archivo'}), 400
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file.read()), data_only=True)
    except Exception:
        return jsonify({'error': 'No se pudo leer el archivo. Verificá que sea el .xlsx de la plantilla.'}), 400

    errores = []

    # ── Paso A: hoja "Consorcios" ────────────────────────────────────────────
    existentes_res = supabase.table('consorcios').select('id,nombre').eq('admin_id', admin_id).execute().data or []
    mapa_consorcios = {c['nombre'].strip().lower(): c['id'] for c in existentes_res}
    ids_originales = {c['id'] for c in existentes_res}
    ids_reutilizados = set()
    nuevos_consorcios = []

    if 'Consorcios' in wb.sheetnames:
        ws_c = wb['Consorcios']
        for i, row in enumerate(ws_c.iter_rows(min_row=2, values_only=True), 2):
            if not row or all(v in (None, '') for v in row):
                continue
            nombre = str(row[0]).strip() if row[0] else ''
            if es_fila_ejemplo(nombre):
                continue
            if not nombre:
                errores.append({'hoja': 'Consorcios', 'fila': i, 'mensaje': 'Falta el nombre del consorcio'})
                continue
            key = nombre.lower()
            if key in mapa_consorcios:
                ids_reutilizados.add(mapa_consorcios[key])
                continue
            nuevos_consorcios.append({
                'nombre': nombre,
                'direccion': row[1] or '',
                'cuit': row[2] or '',
                'pisos': row[3] or None,
                'unidades_totales': row[4] or None,
                'encargado_nombre': row[5] or '',
                'encargado_tel': row[6] or '',
                'admin_id': admin_id,
            })
            mapa_consorcios[key] = None  # placeholder hasta insertar, evita duplicar dentro del mismo archivo

    if nuevos_consorcios:
        creados = supabase.table('consorcios').insert(nuevos_consorcios).execute().data or []
        for c in creados:
            mapa_consorcios[c['nombre'].strip().lower()] = c['id']

    # ── Paso B: hoja "Unidades" ──────────────────────────────────────────────
    nuevas_ufs = []
    consorcio_ids_tocados = set()

    if 'Unidades' in wb.sheetnames:
        ws_u = wb['Unidades']
        filas_unidades = [(i, row) for i, row in enumerate(ws_u.iter_rows(min_row=2, values_only=True), 2)
                           if row and not all(v in (None, '') for v in row)]
        for i, row in filas_unidades:
            nombre_con = str(row[0]).strip() if row[0] else ''
            if es_fila_ejemplo(nombre_con):
                continue
            con_id = mapa_consorcios.get(nombre_con.lower())
            if not nombre_con or not con_id:
                errores.append({'hoja': 'Unidades', 'fila': i, 'mensaje': f'Consorcio no encontrado: "{nombre_con}"'})
                continue
            if con_id in ids_originales:
                ids_reutilizados.add(con_id)
            numero = str(row[1]).strip() if row[1] else ''
            if not numero:
                errores.append({'hoja': 'Unidades', 'fila': i, 'mensaje': 'Falta el número de unidad'})
                continue
            tipo = str(row[3]).strip().lower() if row[3] else 'departamento'
            if tipo not in TIPOS_UF_VALIDOS:
                tipo = 'departamento'
            consorcio_ids_tocados.add(con_id)
            nuevas_ufs.append({
                'consorcio_id': con_id,
                'numero': numero,
                'piso': str(row[2]) if row[2] not in (None, '') else '',
                'tipo': tipo,
                'superficie_m2': row[4] or None,
                'vecino_nombre': row[5] or '',
                'vecino_email': row[6] or '',
            })

    # Evitar duplicar UF ya existentes en el mismo consorcio
    numeros_existentes = set()
    if consorcio_ids_tocados:
        existentes_uf = supabase.table('unidades_funcionales').select('consorcio_id,numero') \
            .in_('consorcio_id', list(consorcio_ids_tocados)).execute().data or []
        numeros_existentes = {(u['consorcio_id'], u['numero'].strip().lower()) for u in existentes_uf}

    ufs_a_insertar = []
    unidades_omitidas = 0
    vistas_en_archivo = set()
    for uf in nuevas_ufs:
        key = (uf['consorcio_id'], uf['numero'].strip().lower())
        if key in numeros_existentes or key in vistas_en_archivo:
            unidades_omitidas += 1
            continue
        vistas_en_archivo.add(key)
        ufs_a_insertar.append(uf)

    if ufs_a_insertar:
        supabase.table('unidades_funcionales').insert(ufs_a_insertar).execute()

    return jsonify({
        'consorcios_creados': len(nuevos_consorcios),
        'consorcios_reutilizados': len(ids_reutilizados),
        'unidades_creadas': len(ufs_a_insertar),
        'unidades_omitidas': unidades_omitidas,
        'errores': errores,
    })


@app.route('/api/consorcios/<cid>/export/excel')
@require_auth(allowed_roles=['admin'])
def export_consorcios_excel(cid):
    con = supabase.table('consorcios').select('*').eq('id', cid).single().execute().data
    ufs = supabase.table('unidades_funcionales').select('*').eq('consorcio_id', cid).order('numero').execute().data
    headers = ['UF', 'Piso', 'Tipo', 'Superficie m²', 'Vecino', 'Email']
    rows = [[u['numero'], u.get('piso',''), u.get('tipo',''), u.get('superficie_m2',''),
             u.get('vecino_nombre',''), u.get('vecino_email','')] for u in ufs]
    wb = make_excel(headers, rows, 'Unidades')
    return excel_response(wb, f"consorcio_{con.get('nombre','')}.xlsx")


@app.route('/api/consorcios/<cid>/export/pdf')
@require_auth(allowed_roles=['admin'])
def export_consorcios_pdf(cid):
    con = supabase.table('consorcios').select('*').eq('id', cid).single().execute().data
    ufs = supabase.table('unidades_funcionales').select('*').eq('consorcio_id', cid).order('numero').execute().data
    headers = ['UF', 'Piso', 'Tipo', 'Sup. m²', 'Vecino', 'Email']
    rows = [[u['numero'], u.get('piso',''), u.get('tipo',''), str(u.get('superficie_m2','')),
             u.get('vecino_nombre',''), u.get('vecino_email','')] for u in ufs]
    buf = make_pdf(f"Consorcio: {con.get('nombre','')}", headers, rows)
    return pdf_response(buf, f"consorcio_{con.get('nombre','')}.pdf")


# ══════════════════════════════════════════════════════════════════════════════
# API — PROVEEDORES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/proveedores', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_proveedores_list():
    admin_id = get_admin_id()
    res = supabase.table('proveedores').select('*').eq('admin_id', admin_id).order('nombre').execute()
    return jsonify(res.data)


@app.route('/api/proveedores', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_proveedores_create():
    admin_id = get_admin_id()
    d = request.json
    payload = {
        'nombre': d.get('nombre', '').strip(),
        'cuit': d.get('cuit', ''),
        'rubro': d.get('rubro', ''),
        'email': d.get('email', ''),
        'telefono': d.get('telefono', ''),
        'admin_id': admin_id,
    }
    res = supabase.table('proveedores').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/proveedores/<pid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_proveedores_update(pid):
    admin_id = get_admin_id()
    d = request.json
    payload = {k: v for k, v in d.items() if k in ('nombre','cuit','rubro','email','telefono') and v is not None}
    res = supabase.table('proveedores').update(payload).eq('id', pid).eq('admin_id', admin_id).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/proveedores/<pid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_proveedores_delete(pid):
    admin_id = get_admin_id()
    supabase.table('proveedores').delete().eq('id', pid).eq('admin_id', admin_id).execute()
    return jsonify({'ok': True})


@app.route('/api/proveedores/<pid>/gastos')
@require_auth(allowed_roles=['admin'])
def api_proveedores_gastos(pid):
    res = supabase.table('gastos').select('*, consorcios(nombre)').eq('proveedor_id', pid).order('fecha_gasto', desc=True).execute()
    return jsonify(res.data)


# ══════════════════════════════════════════════════════════════════════════════
# API — GASTOS
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/gastos', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_gastos_list():
    admin_id = get_admin_id()
    q = supabase.table('gastos') \
        .select('*, consorcios(nombre), proveedores(nombre), unidades_funcionales(numero, piso)') \
        .eq('admin_id', admin_id)
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    if request.args.get('desde'):
        q = q.gte('fecha_gasto', request.args['desde'])
    if request.args.get('hasta'):
        q = q.lte('fecha_gasto', request.args['hasta'])
    res = q.order('fecha_gasto', desc=True).execute()
    return jsonify(res.data)


def _falta_schema_v9(msg):
    """¿El error de Supabase es "no existe la columna" de las que agrega v9?

    Las tres columnas nuevas (gastos.unidad_id, liquidacion_items.unidad_id y
    liquidacion_prorrateo.gastos_particulares) llegan todas juntas en esa
    migración, así que un fallo por cualquiera de ellas se responde igual: hay
    que correr el SQL. Sin este chequeo el admin ve un 500 genérico y no tiene
    forma de saber que le falta un paso de setup.
    """
    return (('unidad_id' in msg or 'gastos_particulares' in msg)
            and ('does not exist' in msg or '42703' in msg
                 or 'PGRST204' in msg or 'schema cache' in msg))


ERROR_FALTA_V9 = ('Falta correr supabase_schema_v9.sql en Supabase: la base todavía no '
                  'tiene las columnas que separan los gastos generales de los '
                  'específicos de una UF.')


def _unidad_es_del_consorcio(unidad_id, consorcio_id):
    """La UF a la que se imputa un gasto tiene que ser de ese mismo consorcio.

    Si no, el gasto se prorratearía sobre un edificio y se cobraría en otro: la
    liquidación del consorcio dueño del gasto nunca lo repartiría y la unidad
    ajena aparecería con un cargo que nadie puede explicar.
    """
    if not unidad_id or not consorcio_id:
        return True
    res = supabase.table('unidades_funcionales').select('id') \
        .eq('id', unidad_id).eq('consorcio_id', consorcio_id).execute()
    return bool(res.data)


@app.route('/api/gastos', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_gastos_create():
    admin_id = get_admin_id()
    # Soporte multipart/form-data para archivos adjuntos
    d = request.form if request.content_type and 'multipart' in request.content_type else request.json or {}
    payload = {
        'consorcio_id': d.get('consorcio_id') or d.get('consorcio_id', ''),
        'proveedor_id': d.get('proveedor_id') or None,
        # NULL = gasto general del consorcio (el caso normal). Con unidad_id el
        # gasto no se prorratea: se le carga entero a esa UF.
        'unidad_id': d.get('unidad_id') or None,
        'descripcion': (d.get('descripcion') or '').strip(),
        'categoria': d.get('categoria', ''),
        'monto': float(d.get('monto', 0)),
        'fecha_gasto': d.get('fecha_gasto', str(date.today())),
        'fecha_vencimiento': d.get('fecha_vencimiento') or None,
        'pagado': d.get('pagado') in (True, 'true', 'on', '1'),
        'fecha_pago': d.get('fecha_pago') or None,
        'metodo_pago': d.get('metodo_pago', ''),
        'recurrente': d.get('recurrente') in (True, 'true', 'on', '1'),
        'frecuencia': d.get('frecuencia', ''),
        'notas': d.get('notas', ''),
        'admin_id': admin_id,
    }
    if not _unidad_es_del_consorcio(payload['unidad_id'], payload['consorcio_id']):
        return jsonify({'error': 'La unidad funcional elegida no pertenece a ese consorcio'}), 400

    try:
        res = supabase.table('gastos').insert(payload).execute()
    except Exception as e:
        if _falta_schema_v9(str(e)):
            return jsonify({'error': f'{ERROR_FALTA_V9} [{e}]'}), 409
        raise
    gasto = res.data[0] if res.data else {}

    # Guardar comprobante si se adjuntó
    archivo = request.files.get('comprobante')
    if archivo and archivo.filename and gasto.get('id'):
        file_bytes = archivo.read()
        b64 = base64.b64encode(file_bytes).decode('utf-8')
        mime = archivo.content_type or 'application/pdf'
        supabase.table('comprobantes_gastos').insert({
            'gasto_id': gasto['id'],
            'archivo_nombre': archivo.filename,
            'archivo_base64': b64,
            'mime_type': mime,
        }).execute()
        supabase.table('gastos').update({'archivo_nombre': archivo.filename}).eq('id', gasto['id']).execute()
        gasto['archivo_nombre'] = archivo.filename

    return jsonify(gasto), 201


@app.route('/api/gastos/<gid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_gastos_update(gid):
    admin_id = get_admin_id()
    d = request.form if request.content_type and 'multipart' in request.content_type else request.json or {}
    allowed = ('consorcio_id','proveedor_id','unidad_id','descripcion','categoria','monto','fecha_gasto',
                'fecha_vencimiento','pagado','fecha_pago','metodo_pago','recurrente','frecuencia','notas')
    payload = {}
    for k in allowed:
        if k in d:
            v = d[k]
            if k == 'monto':
                v = float(v)
            elif k in ('pagado', 'recurrente'):
                v = v in (True, 'true', 'on', '1')
            elif k in ('proveedor_id', 'unidad_id', 'fecha_vencimiento', 'fecha_pago'):
                v = v or None
            payload[k] = v

    # El consorcio puede no venir en un PUT parcial; se lee el guardado para poder
    # validar igual que en el alta.
    if payload.get('unidad_id'):
        cid = payload.get('consorcio_id')
        if not cid:
            actual = supabase.table('gastos').select('consorcio_id') \
                .eq('id', gid).eq('admin_id', admin_id).execute().data
            cid = actual[0]['consorcio_id'] if actual else None
        if not _unidad_es_del_consorcio(payload['unidad_id'], cid):
            return jsonify({'error': 'La unidad funcional elegida no pertenece a ese consorcio'}), 400

    try:
        res = supabase.table('gastos').update(payload).eq('id', gid).eq('admin_id', admin_id).execute()
    except Exception as e:
        if _falta_schema_v9(str(e)):
            return jsonify({'error': f'{ERROR_FALTA_V9} [{e}]'}), 409
        raise
    gasto = res.data[0] if res.data else {}

    # Guardar/reemplazar comprobante si se adjuntó
    archivo = request.files.get('comprobante')
    if archivo and archivo.filename:
        file_bytes = archivo.read()
        b64 = base64.b64encode(file_bytes).decode('utf-8')
        mime = archivo.content_type or 'application/pdf'
        # Eliminar comprobante anterior si existe
        supabase.table('comprobantes_gastos').delete().eq('gasto_id', gid).execute()
        supabase.table('comprobantes_gastos').insert({
            'gasto_id': gid,
            'archivo_nombre': archivo.filename,
            'archivo_base64': b64,
            'mime_type': mime,
        }).execute()
        supabase.table('gastos').update({'archivo_nombre': archivo.filename}).eq('id', gid).execute()
        gasto['archivo_nombre'] = archivo.filename

    return jsonify(gasto)


@app.route('/api/gastos/<gid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_gastos_delete(gid):
    admin_id = get_admin_id()
    supabase.table('gastos').delete().eq('id', gid).eq('admin_id', admin_id).execute()
    return jsonify({'ok': True})


@app.route('/api/gastos/<gid>/comprobante')
@require_auth()
def api_gasto_comprobante(gid):
    """Servir el comprobante adjunto de un gasto (PDF o imagen)."""
    res = supabase.table('comprobantes_gastos').select('*').eq('gasto_id', gid).single().execute()
    if not res.data:
        return jsonify({'error': 'No hay comprobante adjunto para este gasto'}), 404
    comp = res.data
    file_bytes = base64.b64decode(comp['archivo_base64'])
    return send_file(
        io.BytesIO(file_bytes),
        mimetype=comp.get('mime_type', 'application/pdf'),
        download_name=comp.get('archivo_nombre', 'comprobante.pdf'),
        as_attachment=False
    )


@app.route('/api/gastos/extract', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_gastos_extract():
    """Extrae datos de un comprobante usando Groq Vision (Qwen), gratis sin tarjeta."""
    from groq import Groq

    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'GROQ_API_KEY no configurada'}), 500

    client = Groq(api_key=api_key)

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'Se requiere un archivo'}), 400

    file_bytes = file.read()
    mime = file.content_type or 'image/jpeg'

    if file.filename.lower().endswith('.pdf'):
        mime = 'image/png'
        try:
            import fitz  # PyMuPDF
            pdf = fitz.open(stream=file_bytes, filetype='pdf')
            pix = pdf[0].get_pixmap(dpi=200)
            file_bytes = pix.tobytes('png')
        except Exception as e:
            return jsonify({'error': f'No se pudo convertir el PDF: {str(e)}'}), 500
    elif file.filename.lower().endswith('.png'):
        mime = 'image/png'
    elif file.filename.lower().endswith(('.jpg', '.jpeg')):
        mime = 'image/jpeg'

    prompt = """Analizá esta factura/comprobante de un gasto de un consorcio de propiedad horizontal en Argentina.
Extraé los siguientes campos y devolvé SOLO un JSON válido (sin markdown, sin texto adicional):

{
  "descripcion": "descripción breve del gasto (ej: 'Factura Edesur junio 2026')",
  "monto": número decimal sin símbolo de moneda (ej: 15430.50),
  "categoria": una de estas opciones exactas: "electricidad", "gas", "agua", "limpieza", "ascensor", "seguro", "honorarios", "impuesto", "mantenimiento", "sueldos", "otro",
  "fecha_gasto": "YYYY-MM-DD" (fecha de emisión de la factura),
  "fecha_vencimiento": "YYYY-MM-DD" o null (fecha de vencimiento de pago),
  "notas": "datos adicionales relevantes (número de factura, cliente, medidor, etc.)"
}

IMPORTANTE:
- El monto debe ser un número, NO un string. Sin puntos de miles, con punto decimal.
- Las fechas en formato YYYY-MM-DD.
- Si no podés determinar un campo, poné null.
- Respondé SOLO el JSON, sin markdown ni explicaciones."""

    try:
        image_b64 = base64.b64encode(file_bytes).decode('utf-8')
        completion = client.chat.completions.create(
            model='qwen/qwen3.6-27b',
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{image_b64}'}}
                ]
            }],
            response_format={'type': 'json_object'},
            max_completion_tokens=1024
        )

        # Parse the response - clean markdown if present
        text = completion.choices[0].message.content.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3].strip()
            elif '```' in text:
                text = text[:text.rfind('```')].strip()

        data = json.loads(text)

        # Sanitize and validate
        result = {
            'descripcion': str(data.get('descripcion', '') or '').strip(),
            'monto': None,
            'categoria': '',
            'fecha_gasto': '',
            'fecha_vencimiento': '',
            'notas': str(data.get('notas', '') or '').strip(),
        }

        # Monto
        try:
            result['monto'] = round(float(data.get('monto', 0) or 0), 2)
        except (ValueError, TypeError):
            result['monto'] = None

        # Categoria
        valid_cats = ('electricidad','gas','agua','limpieza','ascensor','seguro',
                      'honorarios','impuesto','mantenimiento','sueldos','otro')
        cat = str(data.get('categoria', '') or '').lower().strip()
        result['categoria'] = cat if cat in valid_cats else 'otro'

        # Fechas
        for fk in ('fecha_gasto', 'fecha_vencimiento'):
            val = data.get(fk)
            if val and val != 'null':
                try:
                    datetime.strptime(str(val), '%Y-%m-%d')
                    result[fk] = str(val)
                except ValueError:
                    result[fk] = ''

        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({'error': 'La IA no devolvió datos válidos. Intentá con otra imagen.'}), 422
    except Exception as e:
        return jsonify({'error': f'Error al procesar: {str(e)}'}), 500


@app.route('/api/gastos/export')
@require_auth(allowed_roles=['admin'])
def api_gastos_export():
    admin_id = get_admin_id()
    q = supabase.table('gastos').select('*, consorcios(nombre), proveedores(nombre)').eq('admin_id', admin_id)
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    if request.args.get('desde'):
        q = q.gte('fecha_gasto', request.args['desde'])
    if request.args.get('hasta'):
        q = q.lte('fecha_gasto', request.args['hasta'])
    data = q.order('fecha_gasto', desc=True).execute().data

    headers = ['Fecha', 'Consorcio', 'Descripción', 'Categoría', 'Proveedor', 'Monto', 'Pagado', 'Método Pago', 'Recurrente']
    rows = [[
        g.get('fecha_gasto',''), (g.get('consorcios') or {}).get('nombre',''),
        g.get('descripcion',''), g.get('categoria',''),
        (g.get('proveedores') or {}).get('nombre',''),
        g.get('monto',0), 'Sí' if g.get('pagado') else 'No',
        g.get('metodo_pago',''), 'Sí' if g.get('recurrente') else 'No'
    ] for g in data]

    fmt = request.args.get('fmt', 'excel')
    if fmt == 'pdf':
        buf = make_pdf('Historial de Gastos', headers, [list(map(str, r)) for r in rows])
        return pdf_response(buf, 'gastos.pdf')
    wb = make_excel(headers, rows, 'Gastos')
    return excel_response(wb, 'gastos.xlsx')


# ══════════════════════════════════════════════════════════════════════════════
# API — COBROS
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/cobros', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_cobros_list():
    q = supabase.table('cobros').select('*, unidades_funcionales(numero, vecino_nombre, vecino_email), consorcios(nombre)')
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    if request.args.get('periodo'):
        q = q.eq('periodo', request.args['periodo'])
    if request.args.get('estado'):
        q = q.eq('estado', request.args['estado'])
    res = q.order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/cobros/generar', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_cobros_generar():
    """Genera un cobro para cada UF del consorcio en el período dado."""
    d = request.json
    consorcio_id = d['consorcio_id']
    periodo = d['periodo']
    monto_base = float(d['monto_base'])
    fecha_vencimiento = d.get('fecha_vencimiento')

    # Traer todas las UFs del consorcio
    ufs = supabase.table('unidades_funcionales').select('id').eq('consorcio_id', consorcio_id).execute().data

    rows = []
    for uf in ufs:
        rows.append({
            'unidad_id': uf['id'],
            'consorcio_id': consorcio_id,
            'periodo': periodo,
            'monto_base': monto_base,
            'interes_mora': 0,
            'total': monto_base,
            'estado': 'pendiente',
            'fecha_vencimiento': fecha_vencimiento,
        })
    if rows:
        supabase.table('cobros').insert(rows).execute()
    return jsonify({'generados': len(rows)})


@app.route('/api/cobros/<rid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_cobros_update(rid):
    d = request.json
    allowed = ('estado','fecha_pago','interes_mora','total','notas','comprobante_nombre')
    payload = {k: v for k, v in d.items() if k in allowed}
    res = supabase.table('cobros').update(payload).eq('id', rid).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/cobros/mora')
@require_auth(allowed_roles=['admin'])
def api_cobros_mora():
    """Cobros vencidos o en mora para el panel de morosidad."""
    q = supabase.table('cobros').select('*, unidades_funcionales(numero, vecino_nombre, vecino_email), consorcios(nombre)')
    q = q.in_('estado', ['vencido', 'en_mora'])
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    res = q.order('fecha_vencimiento').execute()
    return jsonify(res.data)


@app.route('/api/cobros/export')
@require_auth(allowed_roles=['admin'])
def api_cobros_export():
    q = supabase.table('cobros').select('*, unidades_funcionales(numero, vecino_nombre), consorcios(nombre)')
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    if request.args.get('periodo'):
        q = q.eq('periodo', request.args['periodo'])
    data = q.order('created_at', desc=True).execute().data

    headers = ['Consorcio', 'UF', 'Vecino', 'Período', 'Monto Base', 'Interés', 'Total', 'Estado', 'Vencimiento', 'Fecha Pago']
    rows = [[
        (c.get('consorcios') or {}).get('nombre',''),
        (c.get('unidades_funcionales') or {}).get('numero',''),
        (c.get('unidades_funcionales') or {}).get('vecino_nombre',''),
        c.get('periodo',''), c.get('monto_base',0), c.get('interes_mora',0),
        c.get('total',0), c.get('estado',''),
        c.get('fecha_vencimiento',''), c.get('fecha_pago',''),
    ] for c in data]

    fmt = request.args.get('fmt', 'excel')
    if fmt == 'pdf':
        buf = make_pdf('Cobros / Expensas', headers, [list(map(str, r)) for r in rows])
        return pdf_response(buf, 'cobros.pdf')
    wb = make_excel(headers, rows, 'Cobros')
    return excel_response(wb, 'cobros.xlsx')


# ══════════════════════════════════════════════════════════════════════════════
# API — BALANCE
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/balance')
@require_auth(allowed_roles=['admin'])
def api_balance():
    admin_id = get_admin_id()
    consorcio_id = request.args.get('consorcio_id')
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    # Ingresos (cobros pagados)
    q_cobros = supabase.table('cobros').select('total, periodo, consorcios(nombre)')
    q_cobros = q_cobros.eq('estado', 'pagado')
    if consorcio_id:
        q_cobros = q_cobros.eq('consorcio_id', consorcio_id)
    if desde:
        q_cobros = q_cobros.gte('fecha_pago', desde)
    if hasta:
        q_cobros = q_cobros.lte('fecha_pago', hasta)
    cobros = q_cobros.execute().data

    # Egresos (gastos)
    q_gastos = supabase.table('gastos').select('monto, fecha_gasto, descripcion, categoria, consorcios(nombre)').eq('admin_id', admin_id)
    if consorcio_id:
        q_gastos = q_gastos.eq('consorcio_id', consorcio_id)
    if desde:
        q_gastos = q_gastos.gte('fecha_gasto', desde)
    if hasta:
        q_gastos = q_gastos.lte('fecha_gasto', hasta)
    gastos = q_gastos.execute().data

    total_ingresos = sum(c.get('total', 0) or 0 for c in cobros)
    total_egresos  = sum(g.get('monto', 0) or 0 for g in gastos)

    return jsonify({
        'ingresos': total_ingresos,
        'egresos': total_egresos,
        'resultado': total_ingresos - total_egresos,
        'cobros': cobros,
        'gastos': gastos,
    })


@app.route('/api/balance/export')
@require_auth(allowed_roles=['admin'])
def api_balance_export():
    admin_id = get_admin_id()
    consorcio_id = request.args.get('consorcio_id')
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    q_cobros = supabase.table('cobros').select('total, periodo, consorcios(nombre)').eq('estado', 'pagado')
    if consorcio_id: q_cobros = q_cobros.eq('consorcio_id', consorcio_id)
    if desde: q_cobros = q_cobros.gte('fecha_pago', desde)
    if hasta: q_cobros = q_cobros.lte('fecha_pago', hasta)
    cobros = q_cobros.execute().data

    q_gastos = supabase.table('gastos').select('monto, fecha_gasto, descripcion, categoria, consorcios(nombre)').eq('admin_id', admin_id)
    if consorcio_id: q_gastos = q_gastos.eq('consorcio_id', consorcio_id)
    if desde: q_gastos = q_gastos.gte('fecha_gasto', desde)
    if hasta: q_gastos = q_gastos.lte('fecha_gasto', hasta)
    gastos = q_gastos.execute().data

    headers = ['Tipo', 'Consorcio', 'Descripción/Período', 'Categoría', 'Monto']
    rows = []
    for c in cobros:
        rows.append(['INGRESO', (c.get('consorcios') or {}).get('nombre',''), c.get('periodo',''), 'Expensas', str(c.get('total',0))])
    for g in gastos:
        rows.append(['EGRESO', (g.get('consorcios') or {}).get('nombre',''), g.get('descripcion',''), g.get('categoria',''), str(g.get('monto',0))])

    fmt = request.args.get('fmt', 'excel')
    if fmt == 'pdf':
        buf = make_pdf('Balance Financiero', headers, rows)
        return pdf_response(buf, 'balance.pdf')
    wb = make_excel(headers, rows, 'Balance')
    return excel_response(wb, 'balance.xlsx')


# ══════════════════════════════════════════════════════════════════════════════
# API — AMENITIES & RESERVAS DE AMENITIES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/consorcios/<cid>/amenities', methods=['GET'])
@require_auth()
def api_amenities_list(cid):
    res = supabase.table('amenities').select('*').eq('consorcio_id', cid).order('nombre').execute()
    return jsonify(res.data)


@app.route('/api/consorcios/<cid>/amenities', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_amenities_create(cid):
    d = request.json
    payload = {
        'consorcio_id': cid,
        'nombre': d.get('nombre', '').strip(),
        'descripcion': d.get('descripcion', ''),
        'condiciones_uso': d.get('condiciones_uso', ''),
        'capacidad_maxima': d.get('capacidad_maxima') or None,
    }
    res = supabase.table('amenities').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/consorcios/<cid>/amenities/<aid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_amenities_update(cid, aid):
    d = request.json
    payload = {k: v for k, v in {
        'nombre': d.get('nombre'),
        'descripcion': d.get('descripcion'),
        'condiciones_uso': d.get('condiciones_uso'),
        'capacidad_maxima': d.get('capacidad_maxima'),
    }.items() if v is not None}
    res = supabase.table('amenities').update(payload).eq('id', aid).eq('consorcio_id', cid).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/consorcios/<cid>/amenities/<aid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_amenities_delete(cid, aid):
    supabase.table('amenities').delete().eq('id', aid).eq('consorcio_id', cid).execute()
    return jsonify({'ok': True})


@app.route('/api/reservas_amenities', methods=['GET'])
@require_auth()
def api_reservas_list():
    user = session['user']
    consorcio_id = request.args.get('consorcio_id')
    amenity_id = request.args.get('amenity_id')
    fecha = request.args.get('fecha')

    q = supabase.table('reservas_amenities').select('*, amenities(nombre), vecinos(nombre, unidad)')

    if user['role'] == 'admin':
        if amenity_id:
            q = q.eq('amenity_id', amenity_id)
        elif consorcio_id:
            res_amenities = supabase.table('amenities').select('id').eq('consorcio_id', consorcio_id).execute()
            ids = [a['id'] for a in res_amenities.data]
            if ids:
                q = q.in_('amenity_id', ids)
            else:
                return jsonify([])
    else:
        vecino_id = get_vecino_id()
        if request.args.get('only_mine') == 'true':
            q = q.eq('vecino_id', vecino_id)
        elif amenity_id:
            q = q.eq('amenity_id', amenity_id)
        else:
            q = q.eq('vecino_id', vecino_id)

    if fecha:
        q = q.eq('fecha', fecha)

    res = q.order('fecha').order('hora_inicio').execute()
    return jsonify(res.data)


@app.route('/api/reservas_amenities', methods=['POST'])
@require_auth()
def api_reservas_create():
    user = session['user']
    d = request.json
    amenity_id = d['amenity_id']
    fecha = d['fecha']
    hora_inicio = d['hora_inicio']
    hora_fin = d['hora_fin']

    if user['role'] == 'admin':
        vecino_id = d.get('vecino_id') or None
    else:
        vecino_id = get_vecino_id()

    # Validar formato
    if not amenity_id or not fecha or not hora_inicio or not hora_fin:
        return jsonify({'error': 'Faltan datos obligatorios'}), 400

    # Comprobar conflictos de horario
    conflicts_res = supabase.table('reservas_amenities').select('*')\
        .eq('amenity_id', amenity_id)\
        .eq('fecha', fecha)\
        .eq('estado', 'confirmada')\
        .execute()

    def to_minutes(t_str):
        parts = list(map(int, t_str.split(':')[:2]))
        return parts[0] * 60 + parts[1]

    try:
        new_start = to_minutes(hora_inicio)
        new_end = to_minutes(hora_fin)
    except Exception:
        return jsonify({'error': 'Formato de hora inválido'}), 400

    if new_start >= new_end:
        return jsonify({'error': 'La hora de inicio debe ser anterior a la hora de fin'}), 400

    for r in conflicts_res.data:
        est_start = to_minutes(r['hora_inicio'])
        est_end = to_minutes(r['hora_fin'])
        if new_start < est_end and new_end > est_start:
            return jsonify({'error': 'El horario seleccionado entra en conflicto con otra reserva'}), 400

    payload = {
        'amenity_id': amenity_id,
        'vecino_id': vecino_id,
        'fecha': fecha,
        'hora_inicio': hora_inicio,
        'hora_fin': hora_fin,
        'estado': 'confirmada'
    }
    res = supabase.table('reservas_amenities').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/reservas_amenities/<rid>', methods=['DELETE'])
@require_auth()
def api_reservas_delete(rid):
    user = session['user']
    if user['role'] == 'admin':
        supabase.table('reservas_amenities').delete().eq('id', rid).execute()
    else:
        vecino_id = get_vecino_id()
        booking = supabase.table('reservas_amenities').select('vecino_id').eq('id', rid).single().execute()
        if booking.data and booking.data['vecino_id'] == vecino_id:
            supabase.table('reservas_amenities').delete().eq('id', rid).execute()
        else:
            return jsonify({'error': 'Sin permiso para cancelar esta reserva'}), 403

    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════════════════
# API — ASOCIACIÓN DE VECINOS
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/public/consorcios', methods=['GET'])
@require_auth()
def api_public_consorcios():
    res = supabase.table('consorcios').select('id, nombre').order('nombre').execute()
    return jsonify(res.data)


@app.route('/api/public/consorcios/<cid>/unidades-libres', methods=['GET'])
@require_auth()
def api_public_unidades_libres(cid):
    res = supabase.table('unidades_funcionales')\
        .select('id, numero, piso, tipo')\
        .eq('consorcio_id', cid)\
        .order('numero')\
        .execute()
    return jsonify(res.data)


@app.route('/api/vecinos/asociar', methods=['POST'])
@require_auth(allowed_roles=['vecino'])
def api_vecinos_asociar():
    d = request.json
    consorcio_id = d.get('consorcio_id')
    unidad_id = d.get('unidad_id')
    rol = d.get('rol', 'propietario')

    if not consorcio_id:
        return jsonify({'error': 'El Consorcio es un campo requerido'}), 400

    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify({'error': 'No se pudo identificar tu perfil de vecino'}), 404

    if not unidad_id:
        # Modo: No encuentro mi unidad -> Registrar 'Pendiente' de asignación por admin
        supabase.table('vecinos').update({
            'consorcio_id': consorcio_id,
            'unidad': 'Pendiente',
            'rol': rol
        }).eq('id', vecino_id).execute()
        return jsonify({'ok': True})

    uf_res = supabase.table('unidades_funcionales')\
        .select('*')\
        .eq('id', unidad_id)\
        .eq('consorcio_id', consorcio_id)\
        .single()\
        .execute()

    if not uf_res.data:
        return jsonify({'error': 'La unidad seleccionada no existe'}), 400

    uf = uf_res.data

    supabase.table('vecinos').update({
        'consorcio_id': consorcio_id,
        'unidad': uf['numero'],
        'unidad_id': unidad_id,
        'rol': rol
    }).eq('id', vecino_id).execute()

    # Si la unidad no tiene vecino asignado, asignarle este (compatibilidad)
    if not uf.get('vecino_id'):
        supabase.table('unidades_funcionales').update({
            'vecino_id': vecino_id
        }).eq('id', unidad_id).execute()

    return jsonify({'ok': True})


@app.route('/api/consorcios/<cid>/vecinos/pendientes', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_consorcio_vecinos_pendientes(cid):
    res = supabase.table('vecinos')\
        .select('*')\
        .eq('consorcio_id', cid)\
        .eq('unidad', 'Pendiente')\
        .execute()
    return jsonify(res.data)


@app.route('/api/consorcios/<cid>/vecinos/<vid>/asignar-unidad', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_consorcio_vecino_asignar(cid, vid):
    d = request.json
    unidad_id = d.get('unidad_id')

    if not unidad_id:
        return jsonify({'error': 'La unidad es requerida'}), 400

    uf_res = supabase.table('unidades_funcionales')\
        .select('*')\
        .eq('id', unidad_id)\
        .eq('consorcio_id', cid)\
        .single()\
        .execute()

    if not uf_res.data:
        return jsonify({'error': 'La unidad seleccionada no existe'}), 400

    uf = uf_res.data

    # Vincular al vecino con el número de unidad y su ID de unidad
    supabase.table('vecinos').update({
        'unidad': uf['numero'],
        'unidad_id': unidad_id
    }).eq('id', vid).eq('consorcio_id', cid).execute()

    # Si la unidad no tiene vecino_id principal asignado, ponle este (compatibilidad)
    if not uf.get('vecino_id'):
        supabase.table('unidades_funcionales').update({
            'vecino_id': vid
        }).eq('id', unidad_id).execute()

    return jsonify({'ok': True})


# ── API: gastos para vecinos ───────────────────────────────────────────────────
@app.route('/api/vecinos/gastos')
@require_auth(allowed_roles=['vecino'])
def api_vecinos_gastos():
    """Lista gastos del consorcio del vecino logueado (datos seguros, sin datos de admin)."""
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    vecino = supabase.table('vecinos').select('consorcio_id').eq('id', vecino_id).single().execute()
    if not vecino.data or not vecino.data.get('consorcio_id'):
        return jsonify([])
    cid = vecino.data['consorcio_id']
    res = supabase.table('gastos')\
        .select('id, descripcion, categoria, monto, fecha_gasto, pagado, archivo_nombre')\
        .eq('consorcio_id', cid)\
        .order('fecha_gasto', desc=True)\
        .execute()
    return jsonify(res.data)


# ── API: datos del dashboard ───────────────────────────────────────────────────
@app.route('/api/dashboard/kpis')
@require_auth(allowed_roles=['admin'])
def api_dashboard_kpis():
    admin_id = get_admin_id()
    consorcios_count = len(supabase.table('consorcios').select('id').eq('admin_id', admin_id).execute().data)
    gastos_pendientes = len(supabase.table('gastos').select('id').eq('admin_id', admin_id).eq('pagado', False).execute().data)
    mora_count = len(supabase.table('cobros').select('id').in_('estado', ['vencido','en_mora']).execute().data)
    return jsonify({'consorcios': consorcios_count, 'gastos_pendientes': gastos_pendientes, 'en_mora': mora_count})


# ── API: perfil ────────────────────────────────────────────────────────────────
@app.route('/api/me')
@require_auth()
def api_me():
    user = session['user']
    table = 'administradores' if user['role'] == 'admin' else 'vecinos'
    result = supabase.table(table).select('*').eq('auth0_id', user['sub']).execute()
    if not result.data:
        # La sesión es válida pero no hay fila de perfil (usuario borrado, DB
        # reseteada, etc.). Cerramos la sesión en vez de devolver un 500: si
        # no, el frontend reintenta, /login ve la sesión viva y redirige de
        # vuelta al dashboard -> loop infinito de refrescos.
        session.clear()
        return jsonify({'error': 'Perfil no encontrado'}), 401
    return jsonify(result.data[0])




# ══════════════════════════════════════════════════════════════════════════════
# API — VECINOS DASHBOARD COMPLETO
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/vecinos/mis-unidades')
@require_auth(allowed_roles=['vecino'])
def api_vecinos_mis_unidades():
    """Devuelve todas las unidades del vecino (multi-unidad vía vecinos_unidades o fallback vecinos)."""
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    try:
        res = supabase.table('vecinos_unidades')            .select('*, unidades_funcionales(id, numero, piso, tipo, superficie_m2), consorcios(id, nombre, direccion, encargado_nombre, encargado_tel)')            .eq('vecino_id', vecino_id).eq('activo', True).execute()
        if res.data:
            return jsonify(res.data)
    except Exception:
        pass
    vecino = supabase.table('vecinos').select('consorcio_id, unidad, unidad_id, rol').eq('id', vecino_id).single().execute()
    if not vecino.data or not vecino.data.get('consorcio_id'):
        return jsonify([])
    v = vecino.data
    uf_data = {}
    if v.get('unidad_id'):
        uf_res = supabase.table('unidades_funcionales').select('*').eq('id', v['unidad_id']).single().execute()
        uf_data = uf_res.data or {}
    con_res = supabase.table('consorcios').select('id, nombre, direccion, encargado_nombre, encargado_tel').eq('id', v['consorcio_id']).single().execute()
    return jsonify([{'vecino_id': vecino_id, 'unidad_id': v.get('unidad_id'), 'consorcio_id': v.get('consorcio_id'), 'rol': v.get('rol', 'propietario'), 'activo': True, 'unidades_funcionales': uf_data, 'consorcios': con_res.data or {}}])


@app.route('/api/vecinos/cobros')
@require_auth(allowed_roles=['vecino'])
def api_vecinos_cobros():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    unidad_id = request.args.get('unidad_id')
    if not unidad_id:
        v = supabase.table('vecinos').select('unidad_id').eq('id', vecino_id).single().execute()
        unidad_id = (v.data or {}).get('unidad_id')
    if not unidad_id:
        return jsonify([])
    q = supabase.table('cobros').select('*').eq('unidad_id', unidad_id)
    if request.args.get('desde'):
        q = q.gte('created_at', request.args['desde'])
    if request.args.get('hasta'):
        q = q.lte('created_at', request.args['hasta'])
    res = q.order('periodo', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/vecinos/cobro-actual')
@require_auth(allowed_roles=['vecino'])
def api_vecinos_cobro_actual():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify(None)
    unidad_id = request.args.get('unidad_id')
    if not unidad_id:
        v = supabase.table('vecinos').select('unidad_id').eq('id', vecino_id).single().execute()
        unidad_id = (v.data or {}).get('unidad_id')
    if not unidad_id:
        return jsonify(None)
    res = supabase.table('cobros').select('*').eq('unidad_id', unidad_id).in_('estado', ['pendiente', 'vencido', 'en_mora']).order('periodo', desc=True).limit(1).execute()
    return jsonify(res.data[0] if res.data else None)


@app.route('/api/vecinos/cobros/<rid>/cupon')
@require_auth(allowed_roles=['vecino'])
def api_vecinos_cupon_pago(rid):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    vecino_id = get_vecino_id()
    cobro_res = supabase.table('cobros').select('*').eq('id', rid).single().execute()
    if not cobro_res.data:
        return jsonify({'error': 'Cobro no encontrado'}), 404
    cobro = cobro_res.data
    uf_data = {}
    if cobro.get('unidad_id'):
        uf_res = supabase.table('unidades_funcionales').select('*, consorcios(nombre, direccion, cuit)').eq('id', cobro['unidad_id']).single().execute()
        uf_data = uf_res.data or {}
    con = (uf_data.get('consorcios') or {})
    vecino = supabase.table('vecinos').select('nombre').eq('id', vecino_id).single().execute()
    v_data = vecino.data or {}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph('<b>CUPÓN DE PAGO DE EXPENSAS</b>', styles['Title']))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"<b>Consorcio:</b> {con.get('nombre', '')} — {con.get('direccion', '')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CUIT:</b> {con.get('cuit', 'N/A')}", styles['Normal']))
    elements.append(Spacer(1, 0.4*cm))
    elements.append(Paragraph(f"<b>Unidad:</b> {uf_data.get('numero', '')} (Piso {uf_data.get('piso', '')})", styles['Normal']))
    elements.append(Paragraph(f"<b>Vecino:</b> {v_data.get('nombre', '')}", styles['Normal']))
    elements.append(Spacer(1, 0.6*cm))
    data = [['Campo', 'Detalle'], ['Período', cobro.get('periodo', '')], ['Monto Base', f"$ {cobro.get('monto_base', 0):,.2f}"], ['Interés/Mora', f"$ {cobro.get('interes_mora', 0):,.2f}"], ['TOTAL A PAGAR', f"$ {cobro.get('total', 0):,.2f}"], ['Estado', str(cobro.get('estado', '')).upper()], ['Vencimiento', cobro.get('fecha_vencimiento', 'N/A')]]
    t = Table(data, colWidths=[8*cm, 9*cm])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7C3AED')), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 10), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')), ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f5f0ff')]), ('ALIGN', (1,0), (1,-1), 'RIGHT')]))
    elements.append(t)
    elements.append(Spacer(1, 0.8*cm))
    elements.append(Paragraph('<i>Para informar su pago, ingrese al panel y use "Informar Pago".</i>', styles['Normal']))
    doc.build(elements)
    return pdf_response(buf, f"cupon_{cobro.get('periodo', '')}_UF{uf_data.get('numero', '')}.pdf")


@app.route('/api/vecinos/medios-pago')
@require_auth(allowed_roles=['vecino'])
def api_vecinos_medios_pago():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    v = supabase.table('vecinos').select('consorcio_id').eq('id', vecino_id).single().execute()
    cid = (v.data or {}).get('consorcio_id')
    if not cid:
        return jsonify([])
    res = supabase.table('medios_pago').select('*').eq('consorcio_id', cid).eq('activo', True).execute()
    return jsonify(res.data)


@app.route('/api/vecinos/gastos-reporte')
@require_auth(allowed_roles=['vecino'])
def api_vecinos_gastos_reporte():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    v = supabase.table('vecinos').select('consorcio_id').eq('id', vecino_id).single().execute()
    cid = (v.data or {}).get('consorcio_id')
    if not cid:
        return jsonify([])
    q = supabase.table('gastos').select('id, descripcion, categoria, monto, fecha_gasto, fecha_vencimiento, pagado, metodo_pago, recurrente, frecuencia, notas, archivo_nombre, proveedores(nombre, rubro)').eq('consorcio_id', cid)
    if request.args.get('desde'):
        q = q.gte('fecha_gasto', request.args['desde'])
    if request.args.get('hasta'):
        q = q.lte('fecha_gasto', request.args['hasta'])
    if request.args.get('categoria'):
        q = q.eq('categoria', request.args['categoria'])
    res = q.order('fecha_gasto', desc=True).execute()
    return jsonify(res.data)


# ══════════════════════════════════════════════════════════════════════════════
# API — COMUNICADOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/comunicados')
@require_auth(allowed_roles=['vecino'])
def api_comunicados_list():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    v = supabase.table('vecinos').select('consorcio_id').eq('id', vecino_id).single().execute()
    cid = (v.data or {}).get('consorcio_id')
    if not cid:
        return jsonify([])
    q = supabase.table('comunicados').select('*').eq('consorcio_id', cid)
    if request.args.get('importante') == 'true':
        q = q.eq('importante', True)
    comunicados = q.order('created_at', desc=True).execute().data or []
    leidos_res = supabase.table('comunicados_leidos').select('comunicado_id').eq('vecino_id', vecino_id).execute()
    leidos_set = {r['comunicado_id'] for r in (leidos_res.data or [])}
    for c in comunicados:
        c['leido'] = c['id'] in leidos_set
    if request.args.get('no_leidos') == 'true':
        comunicados = [c for c in comunicados if not c['leido']]
    return jsonify(comunicados)


@app.route('/api/comunicados/<cid_com>/leer', methods=['POST'])
@require_auth(allowed_roles=['vecino'])
def api_comunicados_leer(cid_com):
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify({'error': 'No autenticado'}), 401
    try:
        supabase.table('comunicados_leidos').upsert({'comunicado_id': cid_com, 'vecino_id': vecino_id}, on_conflict='comunicado_id,vecino_id').execute()
    except Exception:
        pass
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════════════════
# API — AVISOS DE PAGO
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/avisos_pago', methods=['GET'])
@require_auth(allowed_roles=['vecino'])
def api_avisos_pago_list():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    res = supabase.table('avisos_pago').select('id, monto, fecha_pago, medio_pago, estado, created_at, cobro_id').eq('vecino_id', vecino_id).order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/avisos_pago', methods=['POST'])
@require_auth(allowed_roles=['vecino'])
def api_avisos_pago_create():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify({'error': 'No autenticado'}), 401
    d = request.form if request.content_type and 'multipart' in request.content_type else request.json or {}
    v = supabase.table('vecinos').select('consorcio_id, unidad_id').eq('id', vecino_id).single().execute()
    v_data = v.data or {}
    payload = {'vecino_id': vecino_id, 'consorcio_id': v_data.get('consorcio_id'), 'unidad_id': v_data.get('unidad_id'), 'cobro_id': d.get('cobro_id') or None, 'monto': float(d.get('monto', 0)) if d.get('monto') else None, 'fecha_pago': d.get('fecha_pago') or None, 'medio_pago': d.get('medio_pago', ''), 'observaciones': d.get('observaciones', ''), 'estado': 'pendiente'}
    archivo = request.files.get('comprobante') if hasattr(request, 'files') and request.files else None
    if archivo and archivo.filename:
        file_bytes = archivo.read()
        payload['adjunto_base64'] = base64.b64encode(file_bytes).decode('utf-8')
        payload['adjunto_nombre'] = archivo.filename
        payload['adjunto_mime'] = archivo.content_type or 'application/pdf'
    res = supabase.table('avisos_pago').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


# ══════════════════════════════════════════════════════════════════════════════
# API — RECLAMOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/reclamos', methods=['GET'])
@require_auth(allowed_roles=['vecino'])
def api_reclamos_list():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    q = supabase.table('reclamos').select('id, titulo, descripcion, categoria, estado, respuesta_admin, adjunto_nombre, created_at, updated_at').eq('vecino_id', vecino_id)
    if request.args.get('estado'):
        q = q.eq('estado', request.args['estado'])
    res = q.order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/reclamos', methods=['POST'])
@require_auth(allowed_roles=['vecino'])
def api_reclamos_create():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify({'error': 'No autenticado'}), 401
    d = request.form if request.content_type and 'multipart' in request.content_type else request.json or {}
    titulo = (d.get('titulo') or '').strip()
    descripcion = (d.get('descripcion') or '').strip()
    if not titulo or not descripcion:
        return jsonify({'error': 'Título y descripción son obligatorios'}), 400
    v = supabase.table('vecinos').select('consorcio_id, unidad_id').eq('id', vecino_id).single().execute()
    v_data = v.data or {}
    payload = {'vecino_id': vecino_id, 'consorcio_id': v_data.get('consorcio_id'), 'unidad_id': v_data.get('unidad_id'), 'titulo': titulo, 'descripcion': descripcion, 'categoria': d.get('categoria', 'otro'), 'estado': 'activo'}
    archivo = request.files.get('adjunto') if hasattr(request, 'files') and request.files else None
    if archivo and archivo.filename:
        file_bytes = archivo.read()
        payload['adjunto_base64'] = base64.b64encode(file_bytes).decode('utf-8')
        payload['adjunto_nombre'] = archivo.filename
        payload['adjunto_mime'] = archivo.content_type or 'application/pdf'
    res = supabase.table('reclamos').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/reclamos/<rid>', methods=['DELETE'])
@require_auth(allowed_roles=['vecino'])
def api_reclamos_delete(rid):
    vecino_id = get_vecino_id()
    reclamo = supabase.table('reclamos').select('vecino_id, estado').eq('id', rid).single().execute()
    if not reclamo.data or reclamo.data['vecino_id'] != vecino_id:
        return jsonify({'error': 'Sin permiso'}), 403
    if reclamo.data['estado'] not in ('activo',):
        return jsonify({'error': 'Solo se pueden cancelar reclamos activos'}), 400
    supabase.table('reclamos').update({'estado': 'cerrado', 'updated_at': now_iso()}).eq('id', rid).execute()
    return jsonify({'ok': True})


@app.route('/api/reclamos/<rid>/adjunto')
@require_auth(allowed_roles=['vecino'])
def api_reclamos_adjunto(rid):
    vecino_id = get_vecino_id()
    reclamo = supabase.table('reclamos').select('vecino_id, adjunto_base64, adjunto_nombre, adjunto_mime').eq('id', rid).single().execute()
    if not reclamo.data or reclamo.data['vecino_id'] != vecino_id:
        return jsonify({'error': 'No encontrado'}), 404
    if not reclamo.data.get('adjunto_base64'):
        return jsonify({'error': 'Sin adjunto'}), 404
    file_bytes = base64.b64decode(reclamo.data['adjunto_base64'])
    return send_file(io.BytesIO(file_bytes), mimetype=reclamo.data.get('adjunto_mime', 'application/pdf'), download_name=reclamo.data.get('adjunto_nombre', 'adjunto'), as_attachment=False)


# ══════════════════════════════════════════════════════════════════════════════
# API — VOTACIONES & VOTOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/votaciones')
@require_auth(allowed_roles=['vecino'])
def api_votaciones_list():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    v = supabase.table('vecinos').select('consorcio_id, unidad_id').eq('id', vecino_id).single().execute()
    v_data = v.data or {}
    cid = v_data.get('consorcio_id')
    if not cid:
        return jsonify([])
    q = supabase.table('votaciones').select('*').eq('consorcio_id', cid)
    if request.args.get('estado'):
        q = q.eq('estado', request.args['estado'])
    votaciones = q.order('created_at', desc=True).execute().data or []
    unidad_id = v_data.get('unidad_id')
    vot_ids = [vot['id'] for vot in votaciones]
    votos_por_votacion = {}
    if vot_ids:
        todos_votos = supabase.table('votos').select('votacion_id, opcion, unidad_id').in_('votacion_id', vot_ids).execute().data or []
        for voto in todos_votos:
            votos_por_votacion.setdefault(voto['votacion_id'], []).append(voto)
    for vot in votaciones:
        votos = votos_por_votacion.get(vot['id'], [])
        conteo = {}
        for voto in votos:
            op = voto['opcion']
            conteo[op] = conteo.get(op, 0) + 1
        vot['conteo_votos'] = conteo
        vot['total_votos'] = len(votos)
        vot['ya_vote'] = False
        if unidad_id:
            mi_voto = next((voto for voto in votos if voto.get('unidad_id') == unidad_id), None)
            if mi_voto:
                vot['ya_vote'] = True
                vot['mi_opcion'] = mi_voto['opcion']
    return jsonify(votaciones)


@app.route('/api/votaciones/<vid>/votar', methods=['POST'])
@require_auth(allowed_roles=['vecino'])
def api_votaciones_votar(vid):
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify({'error': 'No autenticado'}), 401
    d = request.json or {}
    opcion = (d.get('opcion') or '').strip()
    if not opcion:
        return jsonify({'error': 'La opción es obligatoria'}), 400
    v = supabase.table('vecinos').select('unidad_id, consorcio_id').eq('id', vecino_id).single().execute()
    v_data = v.data or {}
    unidad_id = v_data.get('unidad_id')
    votacion_res = supabase.table('votaciones').select('*').eq('id', vid).single().execute()
    if not votacion_res.data:
        return jsonify({'error': 'Votación no encontrada'}), 404
    votacion = votacion_res.data
    if votacion.get('estado') != 'activa':
        return jsonify({'error': 'La votación ya no está activa'}), 400
    opciones_validas = votacion.get('opciones') or ['Si', 'No', 'Abstención']
    if opcion not in opciones_validas:
        return jsonify({'error': f'Opción inválida. Opciones: {opciones_validas}'}), 400
    if unidad_id:
        ya_voto = supabase.table('votos').select('id').eq('votacion_id', vid).eq('unidad_id', unidad_id).execute()
        if ya_voto.data:
            return jsonify({'error': 'Tu unidad ya emitió un voto en esta votación'}), 409
    try:
        res = supabase.table('votos').insert({'votacion_id': vid, 'vecino_id': vecino_id, 'unidad_id': unidad_id, 'opcion': opcion}).execute()
        return jsonify(res.data[0] if res.data else {}), 201
    except Exception:
        return jsonify({'error': 'Ya votaste en esta votación'}), 409


# ══════════════════════════════════════════════════════════════════════════════
# API — ARCHIVOS DEL CONSORCIO
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/archivos')
@require_auth(allowed_roles=['vecino'])
def api_archivos_list():
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify([])
    v = supabase.table('vecinos').select('consorcio_id').eq('id', vecino_id).single().execute()
    cid = (v.data or {}).get('consorcio_id')
    if not cid:
        return jsonify([])
    q = supabase.table('archivos_consorcio').select('id, categoria, nombre, mime_type, created_at').eq('consorcio_id', cid)
    if request.args.get('categoria'):
        q = q.eq('categoria', request.args['categoria'])
    res = q.order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/archivos/<aid>/descargar')
@require_auth(allowed_roles=['vecino'])
def api_archivos_descargar(aid):
    vecino_id = get_vecino_id()
    if not vecino_id:
        return jsonify({'error': 'No autenticado'}), 401
    archivo_res = supabase.table('archivos_consorcio').select('*').eq('id', aid).single().execute()
    if not archivo_res.data:
        return jsonify({'error': 'Archivo no encontrado'}), 404
    archivo = archivo_res.data
    v = supabase.table('vecinos').select('consorcio_id').eq('id', vecino_id).single().execute()
    if (v.data or {}).get('consorcio_id') != archivo['consorcio_id']:
        return jsonify({'error': 'Sin permiso'}), 403
    file_bytes = base64.b64decode(archivo['archivo_base64'])
    return send_file(io.BytesIO(file_bytes), mimetype=archivo.get('mime_type', 'application/pdf'), download_name=archivo.get('nombre', 'archivo'), as_attachment=True)


# ══════════════════════════════════════════════════════════════════════════════
# API — ADMIN: COMUNICADOS, VOTACIONES, ARCHIVOS, MEDIOS DE PAGO, RECLAMOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/admin/comunicados', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_admin_comunicados_list():
    admin_id = get_admin_id()
    q = supabase.table('comunicados').select('*').eq('admin_id', admin_id)
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    return jsonify(q.order('created_at', desc=True).execute().data)


@app.route('/api/admin/comunicados', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_admin_comunicados_create():
    admin_id = get_admin_id()
    d = request.json or {}
    payload = {'consorcio_id': d.get('consorcio_id'), 'admin_id': admin_id, 'titulo': (d.get('titulo') or '').strip(), 'cuerpo': (d.get('cuerpo') or '').strip(), 'importante': bool(d.get('importante', False))}
    if not payload['titulo'] or not payload['cuerpo'] or not payload['consorcio_id']:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
    res = supabase.table('comunicados').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/admin/comunicados/<cid_com>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_admin_comunicados_delete(cid_com):
    admin_id = get_admin_id()
    supabase.table('comunicados').delete().eq('id', cid_com).eq('admin_id', admin_id).execute()
    return jsonify({'ok': True})


@app.route('/api/admin/votaciones', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_admin_votaciones_create():
    admin_id = get_admin_id()
    d = request.json or {}
    payload = {'consorcio_id': d.get('consorcio_id'), 'admin_id': admin_id, 'titulo': (d.get('titulo') or '').strip(), 'descripcion': d.get('descripcion', ''), 'opciones': d.get('opciones', ['Si', 'No', 'Abstención']), 'fecha_limite': d.get('fecha_limite') or None, 'votos_necesarios': d.get('votos_necesarios') or None, 'estado': 'activa'}
    res = supabase.table('votaciones').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/admin/votaciones/<vid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_admin_votaciones_update(vid):
    admin_id = get_admin_id()
    d = request.json or {}
    allowed = ('titulo', 'descripcion', 'estado', 'fecha_limite', 'votos_necesarios')
    payload = {k: v for k, v in d.items() if k in allowed}
    res = supabase.table('votaciones').update(payload).eq('id', vid).eq('admin_id', admin_id).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/admin/archivos', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_admin_archivos_create():
    admin_id = get_admin_id()
    d = request.form
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return jsonify({'error': 'Se requiere un archivo'}), 400
    file_bytes = archivo.read()
    payload = {'consorcio_id': d.get('consorcio_id'), 'admin_id': admin_id, 'categoria': d.get('categoria', 'otros'), 'nombre': d.get('nombre') or archivo.filename, 'archivo_base64': base64.b64encode(file_bytes).decode('utf-8'), 'mime_type': archivo.content_type or 'application/pdf'}
    res = supabase.table('archivos_consorcio').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/admin/archivos/<aid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_admin_archivos_delete(aid):
    admin_id = get_admin_id()
    supabase.table('archivos_consorcio').delete().eq('id', aid).eq('admin_id', admin_id).execute()
    return jsonify({'ok': True})


@app.route('/api/admin/medios-pago', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_admin_medios_pago_list():
    admin_id = get_admin_id()
    q = supabase.table('medios_pago').select('*').eq('admin_id', admin_id)
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    return jsonify(q.order('nombre').execute().data)


@app.route('/api/admin/medios-pago', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_admin_medios_pago_create():
    admin_id = get_admin_id()
    d = request.json or {}
    payload = {'consorcio_id': d.get('consorcio_id'), 'admin_id': admin_id, 'nombre': (d.get('nombre') or '').strip(), 'descripcion': d.get('descripcion', ''), 'activo': bool(d.get('activo', True))}
    res = supabase.table('medios_pago').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/admin/medios-pago/<mid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_admin_medios_pago_delete(mid):
    admin_id = get_admin_id()
    supabase.table('medios_pago').delete().eq('id', mid).eq('admin_id', admin_id).execute()
    return jsonify({'ok': True})


@app.route('/api/admin/reclamos')
@require_auth(allowed_roles=['admin'])
def api_admin_reclamos_list():
    admin_id = get_admin_id()
    cid = request.args.get('consorcio_id')
    if cid:
        con_check = supabase.table('consorcios').select('id').eq('id', cid).eq('admin_id', admin_id).execute()
        if not con_check.data:
            return jsonify({'error': 'Sin permiso'}), 403
        q = supabase.table('reclamos').select('*, vecinos(nombre, email, unidad)').eq('consorcio_id', cid)
    else:
        cons = supabase.table('consorcios').select('id').eq('admin_id', admin_id).execute().data or []
        cids = [c['id'] for c in cons]
        if not cids:
            return jsonify([])
        q = supabase.table('reclamos').select('*, vecinos(nombre, email, unidad)').in_('consorcio_id', cids)
    if request.args.get('estado'):
        q = q.eq('estado', request.args['estado'])
    res = q.order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/admin/reclamos/<rid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_admin_reclamos_update(rid):
    d = request.json or {}
    allowed = ('estado', 'respuesta_admin')
    payload = {k: v for k, v in d.items() if k in allowed}
    payload['updated_at'] = now_iso()
    res = supabase.table('reclamos').update(payload).eq('id', rid).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/admin/avisos-pago')
@require_auth(allowed_roles=['admin'])
def api_admin_avisos_pago_list():
    admin_id = get_admin_id()
    cid = request.args.get('consorcio_id')
    if cid:
        q = supabase.table('avisos_pago').select('id, consorcio_id, vecino_id, unidad_id, cobro_id, monto, fecha_pago, medio_pago, observaciones, adjunto_nombre, adjunto_mime, estado, created_at, vecinos(nombre, email, unidad)').eq('consorcio_id', cid)
    else:
        cons = supabase.table('consorcios').select('id').eq('admin_id', admin_id).execute().data or []
        cids = [c['id'] for c in cons]
        if not cids:
            return jsonify([])
        q = supabase.table('avisos_pago').select('id, consorcio_id, vecino_id, unidad_id, cobro_id, monto, fecha_pago, medio_pago, observaciones, adjunto_nombre, adjunto_mime, estado, created_at, vecinos(nombre, email, unidad)').in_('consorcio_id', cids)
    res = q.order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/admin/avisos-pago/<aid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_admin_avisos_pago_update(aid):
    d = request.json or {}
    payload = {k: v for k, v in d.items() if k in ('estado',)}
    res = supabase.table('avisos_pago').update(payload).eq('id', aid).execute()
    return jsonify(res.data[0] if res.data else {})



# ══════════════════════════════════════════════════════════════════════════════
# API — LIQUIDACIONES
# ══════════════════════════════════════════════════════════════════════════════

# Mapeo de categorías de gastos a rubros SIPAC simplificados
CATEGORIA_A_RUBRO = {
    'sueldos': (1, 'Remuneraciones y cargas sociales'),
    'aportes': (1, 'Remuneraciones y cargas sociales'),
    'electricidad': (2, 'Servicios públicos'),
    'gas': (2, 'Servicios públicos'),
    'agua': (2, 'Servicios públicos'),
    'internet': (2, 'Servicios públicos'),
    'limpieza': (3, 'Abonos de servicios'),
    'fumigacion': (3, 'Abonos de servicios'),
    'ascensor': (3, 'Abonos de servicios'),
    'mantenimiento': (4, 'Mantenimiento partes comunes'),
    'reparacion': (5, 'Reparaciones en UF'),
    'bancario': (6, 'Gastos bancarios'),
    'honorarios': (8, 'Gastos de administración'),
    'seguro': (9, 'Seguros'),
    'impuesto': (10, 'Otros gastos'),
    'otro': (10, 'Otros gastos'),
}

# Categorías simplificadas para el resumen del vecino
RUBRO_A_CATEGORIA_SIMPLE = {
    1: 'Personal',
    2: 'Servicios',
    3: 'Servicios',
    4: 'Mantenimiento',
    5: 'Mantenimiento',
    6: 'Administración',
    7: 'Administración',
    8: 'Administración',
    9: 'Seguros',
    10: 'Otros',
}


@app.route('/api/liquidaciones', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_liquidaciones_list():
    admin_id = get_admin_id()
    q = supabase.table('liquidaciones').select('*, consorcios(nombre, direccion)').eq('admin_id', admin_id)
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    # Se ordena por created_at (no por numero_revision) para que el listado siga
    # funcionando aunque todavía no se haya corrido supabase_schema_v8.sql.
    res = q.order('periodo', desc=True).order('created_at', desc=True).execute()
    return jsonify(res.data)


def _periodo_rango(periodo):
    """'2026-07' → ('2026-07-01', '2026-08-01') para filtrar gastos del mes."""
    year, month = periodo.split('-')[:2]
    desde = f'{year}-{month}-01'
    if int(month) == 12:
        hasta = f'{int(year)+1}-01-01'
    else:
        hasta = f'{year}-{int(month)+1:02d}-01'
    return desde, hasta


def _liquidaciones_del_periodo(consorcio_id, periodo):
    """Liquidaciones existentes de ese consorcio+período (todas sus revisiones)."""
    return supabase.table('liquidaciones').select('*') \
        .eq('consorcio_id', consorcio_id).eq('periodo', periodo).execute().data


def _ultima_revision(liquidaciones):
    """Mayor numero_revision del set. Devuelve 0 si no hay ninguna.

    Se usa .get() con fallback a 1 para que siga funcionando contra una base a la
    que todavía no se le corrió supabase_schema_v8.sql.
    """
    return max([int(l.get('numero_revision') or 1) for l in liquidaciones], default=0)


def _gastos_ya_enviados(consorcio_id, periodo, excluir_liq_id=None):
    """IDs de gastos que ya viajaron en un resumen efectivamente enviado por email.

    Se apoya en `resumen_envios.estado='enviado'` (no en `liquidaciones.estado`) para que
    una liquidación en borrador o cuyo envío falló no marque sus gastos como ya avisados.
    """
    liqs = supabase.table('liquidaciones').select('id') \
        .eq('consorcio_id', consorcio_id).eq('periodo', periodo).execute().data
    liq_ids = [l['id'] for l in liqs if l['id'] != excluir_liq_id]
    if not liq_ids:
        return set()

    envios = supabase.table('resumen_envios').select('liquidacion_id') \
        .in_('liquidacion_id', liq_ids).eq('estado', 'enviado').execute().data
    liq_enviadas = {e['liquidacion_id'] for e in envios}
    if not liq_enviadas:
        return set()

    rubros = supabase.table('liquidacion_rubros').select('id') \
        .in_('liquidacion_id', list(liq_enviadas)).execute().data
    rubro_ids = [r['id'] for r in rubros]
    if not rubro_ids:
        return set()

    items = supabase.table('liquidacion_items').select('gasto_id') \
        .in_('rubro_id', rubro_ids).execute().data
    return {it['gasto_id'] for it in items if it.get('gasto_id')}


@app.route('/api/liquidaciones/gastos-disponibles', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_gastos_disponibles():
    """Gastos del período con la marca de si ya se avisaron por email.

    Alimenta el selector del modal "Nueva liquidación": los `ya_enviado=False`
    vienen tildados por defecto, los `ya_enviado=True` destildados pero elegibles.
    """
    admin_id = get_admin_id()
    consorcio_id = request.args.get('consorcio_id')
    periodo = request.args.get('periodo')
    if not consorcio_id or not periodo:
        return jsonify({'error': 'Faltan consorcio_id y periodo'}), 400

    desde, hasta = _periodo_rango(periodo)
    gastos = supabase.table('gastos') \
        .select('id, descripcion, categoria, monto, fecha_gasto, pagado, unidad_id, '
                'proveedores(nombre), unidades_funcionales(numero)') \
        .eq('consorcio_id', consorcio_id) \
        .eq('admin_id', admin_id) \
        .gte('fecha_gasto', desde) \
        .lt('fecha_gasto', hasta) \
        .order('fecha_gasto').execute().data

    ya = _gastos_ya_enviados(consorcio_id, periodo)
    for g in gastos:
        g['ya_enviado'] = g['id'] in ya

    previas = _liquidaciones_del_periodo(consorcio_id, periodo)
    ultima_rev = _ultima_revision(previas)

    return jsonify({
        'gastos': gastos,
        'liquidaciones_previas': len(previas),
        'proxima_revision': ultima_rev + 1,
        'ya_enviados': len(ya),
    })


@app.route('/api/liquidaciones', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_liquidaciones_create():
    """Crea una liquidación nueva. Opcionalmente auto-genera rubros desde gastos del período.

    Se admite más de una liquidación por consorcio+período (revisiones): la 2da y
    siguientes sirven para liquidar gastos que se cargaron después del primer envío.
    """
    admin_id = get_admin_id()
    d = request.json
    consorcio_id = d['consorcio_id']
    periodo = d['periodo']  # "2026-07"
    gastos_ids = d.get('gastos_ids')  # None = todos los gastos del período

    if gastos_ids is not None and not gastos_ids:
        return jsonify({'error': 'Seleccioná al menos un gasto para liquidar'}), 400

    # Número de revisión: 1 para la primera del período, +1 para cada reliquidación
    previas = _liquidaciones_del_periodo(consorcio_id, periodo)
    numero_revision = _ultima_revision(previas) + 1

    # Crear cabecera
    payload = {
        'consorcio_id': consorcio_id,
        'admin_id': admin_id,
        'periodo': periodo,
        'numero_revision': numero_revision,
        'fecha_vencimiento_1': d.get('fecha_vencimiento_1'),
        'fecha_vencimiento_2': d.get('fecha_vencimiento_2'),
        'interes_2_vto': d.get('interes_2_vto', 0),
        'saldo_inicial': d.get('saldo_inicial', 0),
        'notas': d.get('notas', ''),
        'estado': 'borrador',
    }
    try:
        liq_res = supabase.table('liquidaciones').insert(payload).execute()
    except Exception as e:
        msg = str(e)
        # El texto crudo de Supabase se adjunta siempre: sin él, un fallo acá es
        # indistinguible de otro y no hay forma de diagnosticarlo desde la UI.
        if 'PGRST204' in msg or 'schema cache' in msg:
            return jsonify({'error':
                'PostgREST tiene el esquema viejo en caché y no ve la columna numero_revision. '
                'Corré  NOTIFY pgrst, \'reload schema\';  en el SQL Editor de Supabase '
                f'y reintentá. [{msg}]'
            }), 409
        if 'numero_revision' in msg and ('does not exist' in msg or '42703' in msg):
            return jsonify({'error':
                'Falta correr supabase_schema_v8.sql en Supabase '
                f'(la columna numero_revision no existe). [{msg}]'
            }), 409
        if 'duplicate key' in msg or '23505' in msg:
            return jsonify({'error':
                'Ya existe una liquidación para este consorcio, período y revisión. Si ya corriste '
                'supabase_schema_v8.sql, puede haber quedado la UNIQUE vieja de v7 sin bajar. '
                f'[{msg}]'
            }), 409
        return jsonify({'error': f'Error al crear la liquidación: {msg}'}), 500

    liq = liq_res.data[0] if liq_res.data else {}
    liq_id = liq.get('id')

    if not liq_id:
        return jsonify({'error': 'Error al crear liquidación'}), 500

    # Auto-generar rubros desde gastos del período.
    # Si algo falla acá la cabecera ya está insertada: se borra para no dejar una
    # liquidación vacía que después ocupe un número de revisión y confunda.
    if d.get('auto_generar', True):
        try:
            _generar_rubros_desde_gastos(liq_id, consorcio_id, periodo, admin_id, gastos_ids=gastos_ids)
            _generar_prorrateo(liq_id, consorcio_id, periodo, numero_revision=numero_revision)
            _recalcular_totales(liq_id)
        except Exception as e:
            supabase.table('liquidaciones').delete().eq('id', liq_id).execute()
            if _falta_schema_v9(str(e)):
                return jsonify({'error': f'{ERROR_FALTA_V9} [{e}]'}), 409
            return jsonify({'error':
                f'La liquidación se creó pero falló al generar rubros/prorrateo: {e}'
            }), 500

    # Refetch con datos completos
    liq = supabase.table('liquidaciones').select('*, consorcios(nombre, direccion)').eq('id', liq_id).single().execute().data
    return jsonify(liq), 201


def _generar_rubros_desde_gastos(liq_id, consorcio_id, periodo, admin_id, gastos_ids=None):
    """Agrupa los gastos del consorcio en el período por categoría → rubros.

    `gastos_ids` acota la liquidación a esos gastos (selección manual del admin).
    Con None entran todos los del período, como antes.
    """
    desde, hasta = _periodo_rango(periodo)

    gastos = supabase.table('gastos').select('*') \
        .eq('consorcio_id', consorcio_id) \
        .eq('admin_id', admin_id) \
        .gte('fecha_gasto', desde) \
        .lt('fecha_gasto', hasta) \
        .execute().data

    if gastos_ids is not None:
        elegidos = set(gastos_ids)
        gastos = [g for g in gastos if g.get('id') in elegidos]

    # Agrupar por rubro
    rubros_dict = {}  # {numero_rubro: {nombre, items: [{descripcion, monto, gasto_id, unidad_id}]}}
    for g in gastos:
        cat = (g.get('categoria') or 'otro').lower()
        num, nombre = CATEGORIA_A_RUBRO.get(cat, (10, 'Otros gastos'))
        if num not in rubros_dict:
            rubros_dict[num] = {'nombre': nombre, 'items': []}
        rubros_dict[num]['items'].append({
            'descripcion': g.get('descripcion', ''),
            'monto': float(g.get('monto', 0)),
            'gasto_id': g.get('id'),
            # El alcance se congela acá: el prorrateo se calcula sobre los ítems,
            # así que editar el gasto después no cambia una liquidación emitida.
            'unidad_id': g.get('unidad_id'),
        })

    total_general = sum(
        sum(it['monto'] for it in r['items'])
        for r in rubros_dict.values()
    )

    # Insertar rubros e items
    for num in sorted(rubros_dict.keys()):
        r = rubros_dict[num]
        subtotal = sum(it['monto'] for it in r['items'])
        pct = (subtotal / total_general * 100) if total_general > 0 else 0

        rubro_res = supabase.table('liquidacion_rubros').insert({
            'liquidacion_id': liq_id,
            'numero_rubro': num,
            'nombre': r['nombre'],
            'subtotal': subtotal,
            'porcentaje_sobre_total': round(pct, 2),
        }).execute()
        rubro_id = rubro_res.data[0]['id'] if rubro_res.data else None

        if rubro_id:
            items_payload = [{
                'rubro_id': rubro_id,
                'descripcion': it['descripcion'],
                'monto': it['monto'],
                'gasto_id': it['gasto_id'],
                'unidad_id': it['unidad_id'],
            } for it in r['items']]
            if items_payload:
                supabase.table('liquidacion_items').insert(items_payload).execute()


def _egresos_por_alcance(liq_id):
    """Separa los egresos de la liquidación en generales y particulares por UF.

    Devuelve (total_general, {unidad_id: monto}). Sólo el total general se
    prorratea; lo particular se le carga entero a su unidad.
    """
    rubros = supabase.table('liquidacion_rubros').select('id') \
        .eq('liquidacion_id', liq_id).execute().data
    rubro_ids = [r['id'] for r in rubros]
    if not rubro_ids:
        return 0.0, {}

    items = supabase.table('liquidacion_items').select('monto, unidad_id') \
        .in_('rubro_id', rubro_ids).execute().data

    total_general = 0.0
    particulares = {}
    for it in items:
        monto = float(it.get('monto') or 0)
        unidad_id = it.get('unidad_id')
        if unidad_id:
            particulares[unidad_id] = round(particulares.get(unidad_id, 0.0) + monto, 2)
        else:
            total_general += monto
    return round(total_general, 2), particulares


def _repartir(total, pesos):
    """Reparte `total` entre n partes según `pesos`, cerrando los centavos.

    Redondear cada parte por separado casi nunca suma el total (100 entre 3 da
    33.33 tres veces = 99.99). La diferencia se ajusta en la primera parte y se
    devuelve aparte para poder registrarla como `redondeo` en el prorrateo: la
    suma de lo que se le cobra a las UFs tiene que dar exactamente lo gastado.

    Devuelve (partes, ajustes) — ajustes es 0 en todas menos la primera.
    """
    n = len(pesos)
    if n == 0:
        return [], []
    suma_pesos = sum(pesos)
    if suma_pesos <= 0:
        return [0.0] * n, [0.0] * n

    partes = [round(total * p / suma_pesos, 2) for p in pesos]
    ajustes = [0.0] * n
    dif = round(total - sum(partes), 2)
    if dif:
        partes[0] = round(partes[0] + dif, 2)
        ajustes[0] = dif
    return partes, ajustes


def _generar_prorrateo(liq_id, consorcio_id, periodo, numero_revision=1):
    """Genera la tabla de prorrateo para cada UF del consorcio.

    El gasto general del consorcio se reparte en partes iguales entre todas las
    UFs (prorrateo lineal). Si en algún momento se cargan los porcentajes de
    `unidades_funcionales.porcentaje_a` y suman 100, se usan esos en su lugar;
    mientras estén todos en 0 —que es como vienen— el reparto lineal es el que
    manda. Antes se multiplicaba directo por ese porcentaje, así que sin cargar
    daba $0 a cada unidad.

    Los gastos específicos de una UF (el juego de llaves que pidió sólo ella) no
    entran en el reparto: se le suman enteros a esa unidad en `gastos_particulares`.

    En una reliquidación del mismo período (numero_revision > 1) NO se vuelve a
    arrastrar el saldo del mes anterior: ya se le cobró al vecino en la revisión 1
    y volver a incluirlo le facturaría dos veces la misma deuda vieja. La revisión
    complementaria factura únicamente los gastos nuevos que se le sumaron.
    """
    ufs = supabase.table('unidades_funcionales').select('*') \
        .eq('consorcio_id', consorcio_id).order('numero').execute().data
    if not ufs:
        return

    total_general, particulares = _egresos_por_alcance(liq_id)

    # Base del reparto: porcentajes cargados si cierran en 100, lineal si no.
    # La tolerancia de 0.5 absorbe el redondeo de cargar 33.333 tres veces.
    pcts_cargados = [float(uf.get('porcentaje_a') or 0) for uf in ufs]
    usar_porcentajes = abs(sum(pcts_cargados) - 100) <= 0.5

    if usar_porcentajes:
        pesos = pcts_cargados
        pcts_efectivos = pcts_cargados
    else:
        pesos = [1.0] * len(ufs)
        pcts_efectivos = [round(100 / len(ufs), 3)] * len(ufs)

    expensas, ajustes = _repartir(total_general, pesos)

    # Buscar cobros del período anterior para saldos
    year, month = periodo.split('-')[:2]
    if int(month) == 1:
        periodo_ant = f'{int(year)-1}-12'
    else:
        periodo_ant = f'{year}-{int(month)-1:02d}'

    uf_ids = [uf['id'] for uf in ufs]
    cobros_ant_por_uf = {}
    if uf_ids and numero_revision <= 1:
        cobros_ant = supabase.table('cobros').select('unidad_id, total, estado, fecha_pago') \
            .in_('unidad_id', uf_ids).eq('periodo', periodo_ant).execute().data
        for c in cobros_ant:
            cobros_ant_por_uf.setdefault(c['unidad_id'], c)

    prorrateo_rows = []
    for i, uf in enumerate(ufs):
        pct_a = pcts_efectivos[i]
        pct_c = float(uf.get('porcentaje_c') or 0)
        expensa_a = expensas[i]
        adicional = round(total_general * pct_c / 100, 2) if pct_c > 0 else 0
        particular = particulares.get(uf['id'], 0.0)

        # Buscar saldo anterior (cobro del período anterior)
        c = cobros_ant_por_uf.get(uf['id'])
        saldo_ant = 0
        pago = 0
        if c:
            if c.get('estado') == 'pagado':
                pago = float(c.get('total', 0))
            else:
                saldo_ant = float(c.get('total', 0))

        saldo_pend = round(saldo_ant - pago, 2) if saldo_ant > 0 else 0
        total_unidad = round(expensa_a + adicional + particular + saldo_pend, 2)

        prorrateo_rows.append({
            'liquidacion_id': liq_id,
            'unidad_id': uf['id'],
            'saldo_anterior': saldo_ant,
            'pago_realizado': pago,
            'saldo_pendiente': saldo_pend,
            'interes_mora': 0,
            'porcentaje_a': pct_a,
            'expensa_a': expensa_a,
            'porcentaje_c': pct_c,
            'adicional_ordinaria': adicional,
            'gastos_particulares': particular,
            'extraordinaria': 0,
            'redondeo': ajustes[i],
            'total_unidad': total_unidad,
        })

    if prorrateo_rows:
        supabase.table('liquidacion_prorrateo').insert(prorrateo_rows).execute()


def _recalcular_totales(liq_id):
    """Recalcula total_egresos y saldo_final de la liquidación."""
    rubros = supabase.table('liquidacion_rubros').select('subtotal') \
        .eq('liquidacion_id', liq_id).execute().data
    total_egresos = sum(float(r.get('subtotal', 0)) for r in rubros)

    liq = supabase.table('liquidaciones').select('saldo_inicial, total_ingresos') \
        .eq('id', liq_id).single().execute().data
    saldo_inicial = float(liq.get('saldo_inicial', 0))
    total_ingresos = float(liq.get('total_ingresos', 0))
    saldo_final = saldo_inicial + total_ingresos - total_egresos

    supabase.table('liquidaciones').update({
        'total_egresos': total_egresos,
        'saldo_final': round(saldo_final, 2),
    }).eq('id', liq_id).execute()


@app.route('/api/liquidaciones/<lid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_liquidaciones_update(lid):
    admin_id = get_admin_id()
    d = request.json
    allowed = ('fecha_vencimiento_1', 'fecha_vencimiento_2', 'interes_2_vto',
               'saldo_inicial', 'total_ingresos', 'saldo_bancario', 'saldo_superfondo',
               'saldo_administrador', 'notas', 'estado')
    payload = {k: v for k, v in d.items() if k in allowed}
    res = supabase.table('liquidaciones').update(payload).eq('id', lid).eq('admin_id', admin_id).execute()
    if payload.get('saldo_inicial') is not None or payload.get('total_ingresos') is not None:
        _recalcular_totales(lid)
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/liquidaciones/<lid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_liquidaciones_delete(lid):
    admin_id = get_admin_id()
    res = supabase.table('liquidaciones').delete() \
        .eq('id', lid).eq('admin_id', admin_id).eq('estado', 'borrador').execute()
    if not res.data:
        # Antes devolvía ok igual y la liquidación seguía ahí sin que el admin se enterara.
        return jsonify({'error':
            'Sólo se pueden eliminar liquidaciones en borrador. Esta ya fue publicada: '
            'creá una nueva liquidación del mismo período con los gastos que falten.'
        }), 409
    return jsonify({'ok': True})


def _rubros_con_items(liq_id):
    """Trae los rubros de una liquidación junto con sus items, en 2 queries en vez de 1+N."""
    rubros = supabase.table('liquidacion_rubros').select('*') \
        .eq('liquidacion_id', liq_id).order('numero_rubro').execute().data
    rubro_ids = [r['id'] for r in rubros]
    items_por_rubro = {}
    if rubro_ids:
        todos_items = supabase.table('liquidacion_items') \
            .select('*, unidades_funcionales(numero)') \
            .in_('rubro_id', rubro_ids).execute().data
        for it in todos_items:
            items_por_rubro.setdefault(it['rubro_id'], []).append(it)
    for r in rubros:
        r['items'] = items_por_rubro.get(r['id'], [])
    return rubros


@app.route('/api/liquidaciones/<lid>/rubros', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_rubros(lid):
    return jsonify(_rubros_con_items(lid))


@app.route('/api/liquidaciones/<lid>/prorrateo', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_prorrateo(lid):
    res = supabase.table('liquidacion_prorrateo') \
        .select('*, unidades_funcionales(numero, piso, tipo, vecino_nombre, vecino_email)') \
        .eq('liquidacion_id', lid).order('unidades_funcionales(numero)').execute()
    return jsonify(res.data)


@app.route('/api/liquidaciones/<lid>/prorrateo/<pid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_prorrateo_update(lid, pid):
    d = request.json
    allowed = ('saldo_anterior', 'pago_realizado', 'saldo_pendiente', 'interes_mora',
               'porcentaje_a', 'expensa_a', 'porcentaje_c', 'adicional_ordinaria',
               'gastos_particulares', 'extraordinaria', 'redondeo', 'total_unidad')
    payload = {k: v for k, v in d.items() if k in allowed}
    res = supabase.table('liquidacion_prorrateo').update(payload).eq('id', pid).execute()
    return jsonify(res.data[0] if res.data else {})


# ── Resumen personalizado por UF ───────────────────────────────────────────────

def _generar_resumen_html(liq, prorrateo, rubros, consorcio, uf):
    """Genera el HTML del resumen personalizado para una UF."""
    periodo_display = liq.get('periodo', '')
    try:
        y, m = periodo_display.split('-')
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        periodo_display = f'{meses[int(m)]} {y}'
    except:
        pass

    # Una revisión > 1 es una liquidación complementaria: se emitió después de haber
    # mandado la del mes y factura sólo los gastos que se cargaron más tarde. El mail
    # tiene que decirlo, porque si no el vecino recibe dos veces "Tu expensa este mes"
    # y no puede saber si el segundo reemplaza al primero o se suma.
    es_complementaria = int(liq.get('numero_revision') or 1) > 1

    total_unidad = float(prorrateo.get('total_unidad', 0))
    uf_id = prorrateo.get('unidad_id')

    # Agrupar rubros en categorías simples. Sólo entran los gastos generales del
    # consorcio: los específicos de una UF no se prorratean, así que mezclarlos
    # acá le mostraría al vecino un desglose que no coincide con lo que paga.
    categorias = {}
    particulares_uf = []
    obras_en_curso = []
    for r in rubros:
        cat_simple = RUBRO_A_CATEGORIA_SIMPLE.get(r.get('numero_rubro', 10), 'Otros')

        for it in r.get('items', []):
            monto_item = float(it.get('monto') or 0)
            unidad_item = it.get('unidad_id')
            if unidad_item:
                if unidad_item == uf_id:
                    particulares_uf.append({'desc': it.get('descripcion', ''), 'monto': monto_item})
                continue  # gasto particular de otra UF: no es asunto de ésta
            categorias[cat_simple] = categorias.get(cat_simple, 0) + monto_item

            # Buscar items con cuotas (obras en curso)
            if it.get('es_cuota') and it.get('cuota_actual') and it.get('cuota_total'):
                obras_en_curso.append({
                    'desc': it['descripcion'],
                    'cuota': it['cuota_actual'],
                    'total': it['cuota_total'],
                })

    total_general = sum(categorias.values())
    pct_a = float(prorrateo.get('porcentaje_a', 0))
    gastos_particulares = float(prorrateo.get('gastos_particulares', 0) or 0)
    cat_icons = {'Personal': '👤', 'Servicios': '⚡', 'Mantenimiento': '🔧',
                 'Administración': '📋', 'Seguros': '🛡️', 'Otros': '📦'}

    # Build category rows
    cat_rows = ''
    for cat, monto in sorted(categorias.items(), key=lambda x: -x[1]):
        pct = (monto / total_general * 100) if total_general > 0 else 0
        monto_uf = round(monto * pct_a / 100, 2) if pct_a > 0 else monto
        icon = cat_icons.get(cat, '📦')
        cat_rows += f'''
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;font-size:14px;">{icon} {cat}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;text-align:right;font-size:14px;font-weight:600;">${monto_uf:,.2f}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;text-align:right;font-size:13px;color:#888;">{pct:.1f}%</td>
        </tr>'''

    # Gastos que no se prorratean: se le cobran enteros a esta UF y punto. Van en
    # su propio bloque y con el detalle ítem por ítem porque es lo primero que el
    # vecino va a querer discutir si no lo reconoce.
    particulares_html = ''
    if particulares_uf:
        particulares_rows = ''.join(f'''
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;font-size:14px;">{p["desc"]}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;text-align:right;font-size:14px;font-weight:600;">${p["monto"]:,.2f}</td>
        </tr>''' for p in particulares_uf)
        particulares_html = f'''
<div style="background:#fff;border-radius:12px;margin-top:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
    <h3 style="margin:0 0 6px;font-size:15px;font-weight:700;color:#111;">🔑 Gastos de tu unidad</h3>
    <p style="margin:0 0 12px;font-size:12px;color:#888;">Estos gastos no se reparten entre el edificio: corresponden sólo a tu UF.</p>
    <table style="width:100%;border-collapse:collapse;">
        <tbody>{particulares_rows}</tbody>
        <tfoot>
            <tr>
                <td style="padding:10px 14px;font-size:14px;font-weight:700;">Total</td>
                <td style="padding:10px 14px;text-align:right;font-size:14px;font-weight:700;">${gastos_particulares:,.2f}</td>
            </tr>
        </tfoot>
    </table>
</div>'''

    # Build obras rows
    obras_html = ''
    if obras_en_curso:
        obras_items = ''.join(
            f'<li style="padding:6px 0;font-size:13px;color:#444;">{o["desc"]} — Cuota {o["cuota"]} de {o["total"]}</li>'
            for o in obras_en_curso
        )
        obras_html = f'''
        <div style="margin-top:24px;background:#f8f7ff;border-radius:10px;padding:18px;">
            <h3 style="margin:0 0 10px;font-size:15px;color:#7C3AED;">🏗️ Obras en curso</h3>
            <ul style="margin:0;padding-left:18px;">{obras_items}</ul>
        </div>'''

    saldo_final = float(liq.get('saldo_final', 0))

    aviso_complementaria = ''
    if es_complementaria:
        aviso_complementaria = (
            '<p style="margin:14px 0 0;padding:10px 12px;background:#FEF3C7;border-radius:8px;'
            'font-size:12px;color:#92400E;line-height:1.5;">Este importe <strong>se suma</strong> '
            f'a la expensa de {periodo_display} que ya recibiste: corresponde a gastos del mismo '
            'período que se cargaron después de ese envío. No reemplaza al resumen anterior.</p>'
        )

    # El bloque del fondo se omite en una complementaria: saldo_final se calcula sobre
    # saldo_inicial/total_ingresos propios de esta revisión, que arrancan en cero, así que
    # daría un negativo igual a sus egresos y no el fondo real del consorcio.
    fondo_html = '' if es_complementaria else f'''
<div style="background:#f8f7ff;border-radius:12px;margin-top:16px;padding:18px;text-align:center;">
    <p style="margin:0;font-size:12px;color:#888;text-transform:uppercase;font-weight:600;">Saldo del fondo del consorcio</p>
    <p style="margin:6px 0 0;font-size:22px;font-weight:800;color:#7C3AED;">${saldo_final:,.2f}</p>
</div>'''
    vto1 = liq.get('fecha_vencimiento_1', '—')
    vto2 = liq.get('fecha_vencimiento_2', '—')
    interes_2 = float(liq.get('interes_2_vto', 0))
    banco_cbu = consorcio.get('banco_cbu', '—')
    banco_nombre = consorcio.get('banco_nombre', '—')

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Resumen de Expensas — {periodo_display}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5fa;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:20px;">

<!-- Header -->
<div style="background:linear-gradient(135deg,#7C3AED,#10B981);border-radius:14px;padding:28px;color:#fff;text-align:center;">
    <h1 style="margin:0;font-size:22px;font-weight:800;">🏢 {consorcio.get('nombre', '')}</h1>
    <p style="margin:6px 0 0;font-size:13px;opacity:.85;">{consorcio.get('direccion', '')}</p>
    <p style="margin:4px 0 0;font-size:13px;opacity:.85;">Período: {periodo_display}</p>
</div>

<!-- Tu expensa -->
<div style="background:#fff;border-radius:12px;margin-top:16px;padding:24px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.05);">
    <p style="margin:0;font-size:13px;color:#888;text-transform:uppercase;letter-spacing:.05em;font-weight:600;">{'Expensa complementaria' if es_complementaria else 'Tu expensa este mes'}</p>
    <p style="margin:8px 0 0;font-size:38px;font-weight:800;color:#111;">${total_unidad:,.2f}</p>
    <p style="margin:6px 0 0;font-size:12px;color:#888;">UF {uf.get('numero', '')} — Piso {uf.get('piso', '—')} — {uf.get('vecino_nombre', '')}</p>
    {aviso_complementaria}
</div>

<!-- Desglose por categoría -->
<div style="background:#fff;border-radius:12px;margin-top:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
    <h3 style="margin:0 0 6px;font-size:15px;font-weight:700;color:#111;">📊 Desglose por categoría</h3>
    <p style="margin:0 0 12px;font-size:12px;color:#888;">Los montos son la parte que te toca a vos ({pct_a:.3f}% de los gastos comunes del edificio).</p>
    <table style="width:100%;border-collapse:collapse;">
        <thead>
            <tr style="border-bottom:2px solid #7C3AED;">
                <th style="padding:8px 14px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;">Categoría</th>
                <th style="padding:8px 14px;text-align:right;font-size:11px;color:#888;text-transform:uppercase;">Tu parte</th>
                <th style="padding:8px 14px;text-align:right;font-size:11px;color:#888;text-transform:uppercase;">% del total</th>
            </tr>
        </thead>
        <tbody>{cat_rows}</tbody>
    </table>
</div>
{particulares_html}

<!-- Estado de cuenta -->
<div style="background:#fff;border-radius:12px;margin-top:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
    <h3 style="margin:0 0 14px;font-size:15px;font-weight:700;color:#111;">📒 Tu estado de cuenta</h3>
    <table style="width:100%;font-size:14px;">
        <tr><td style="padding:6px 0;color:#666;">Saldo anterior</td><td style="text-align:right;font-weight:600;">${float(prorrateo.get('saldo_anterior',0)):,.2f}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Tu pago registrado</td><td style="text-align:right;font-weight:600;color:#10B981;">-${float(prorrateo.get('pago_realizado',0)):,.2f}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Saldo pendiente</td><td style="text-align:right;font-weight:600;color:#EF4444;">${float(prorrateo.get('saldo_pendiente',0)):,.2f}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Intereses</td><td style="text-align:right;font-weight:600;">${float(prorrateo.get('interes_mora',0)):,.2f}</td></tr>
        <tr style="border-top:2px solid #eee;">
            <td style="padding:10px 0;font-weight:700;">Expensa ordinaria ({pct_a:.3f}%)</td>
            <td style="text-align:right;font-weight:700;">${float(prorrateo.get('expensa_a',0)):,.2f}</td>
        </tr>
        <tr><td style="padding:6px 0;color:#666;">Adicional ordinaria</td><td style="text-align:right;font-weight:600;">${float(prorrateo.get('adicional_ordinaria',0)):,.2f}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Gastos de tu unidad</td><td style="text-align:right;font-weight:600;">${gastos_particulares:,.2f}</td></tr>
        <tr style="border-top:2px solid #eee;">
            <td style="padding:10px 0;font-weight:700;">Total a pagar</td>
            <td style="text-align:right;font-weight:800;">${total_unidad:,.2f}</td>
        </tr>
    </table>
</div>

<!-- Datos de pago -->
<div style="background:#fff;border-radius:12px;margin-top:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
    <h3 style="margin:0 0 14px;font-size:15px;font-weight:700;color:#111;">💳 Datos de pago</h3>
    <table style="width:100%;font-size:14px;">
        <tr><td style="padding:5px 0;color:#666;">Banco</td><td style="text-align:right;font-weight:500;">{banco_nombre}</td></tr>
        <tr><td style="padding:5px 0;color:#666;">CBU</td><td style="text-align:right;font-weight:600;font-family:monospace;font-size:13px;">{banco_cbu}</td></tr>
        <tr><td style="padding:5px 0;color:#666;">1er vencimiento</td><td style="text-align:right;font-weight:600;">{vto1}</td></tr>
        <tr><td style="padding:5px 0;color:#666;">2do vencimiento</td><td style="text-align:right;font-weight:500;">{vto2} (+{interes_2}%)</td></tr>
    </table>
    <p style="margin:12px 0 0;font-size:12px;color:#888;text-align:center;">📧 Recordá enviar tu comprobante de pago por email o por la plataforma.</p>
</div>

<!-- Fondo del consorcio (se omite en una liquidación complementaria) -->
{fondo_html}

{obras_html}

<!-- Footer -->
<div style="text-align:center;margin-top:24px;padding:16px;">
    <p style="font-size:12px;color:#aaa;">Generado por Niddo — Gestión de consorcios inteligente</p>
    <p style="font-size:11px;color:#ccc;">{liq.get('notas', '')}</p>
</div>

</div>
</body>
</html>'''


@app.route('/api/liquidaciones/<lid>/resumen/<uid>')
@require_auth(allowed_roles=['admin'])
def api_liquidacion_resumen(lid, uid):
    """Genera y devuelve el resumen HTML personalizado de una UF."""
    liq = supabase.table('liquidaciones').select('*, consorcios(nombre, direccion, banco_nombre, banco_sucursal, banco_cuenta, banco_cbu, banco_cuit_pago)') \
        .eq('id', lid).single().execute().data
    if not liq:
        return jsonify({'error': 'Liquidación no encontrada'}), 404

    consorcio = liq.get('consorcios', {})

    prorrateo = supabase.table('liquidacion_prorrateo') \
        .select('*, unidades_funcionales(numero, piso, tipo, vecino_nombre, vecino_email)') \
        .eq('liquidacion_id', lid).eq('unidad_id', uid).single().execute().data
    if not prorrateo:
        return jsonify({'error': 'Prorrateo no encontrado para esta UF'}), 404

    uf = prorrateo.get('unidades_funcionales', {})

    rubros = _rubros_con_items(lid)

    html = _generar_resumen_html(liq, prorrateo, rubros, consorcio, uf)

    if request.args.get('format') == 'html':
        return Response(html, mimetype='text/html')
    return jsonify({'html': html, 'uf': uf, 'total': prorrateo.get('total_unidad')})


# ── Envío de resúmenes por email ───────────────────────────────────────────────

@app.route('/api/liquidaciones/<lid>/enviar', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_enviar(lid):
    """Envía resúmenes por email a todas las UFs (o las seleccionadas)."""
    d = request.json or {}
    unidades_ids = d.get('unidades_ids')  # None / ausente = todas

    # Una lista vacía es "el admin destildó todo", no "mandale a todo el consorcio".
    if unidades_ids is not None and not unidades_ids:
        return jsonify({'error': 'Seleccioná al menos una unidad funcional para enviar'}), 400

    import resend
    resend.api_key = os.environ.get('RESEND_API_KEY', '')

    liq = supabase.table('liquidaciones').select('*, consorcios(nombre, direccion, banco_nombre, banco_sucursal, banco_cuenta, banco_cbu, banco_cuit_pago)') \
        .eq('id', lid).single().execute().data
    if not liq:
        return jsonify({'error': 'Liquidación no encontrada'}), 404

    consorcio = liq.get('consorcios', {})

    # Obtener prorrateos
    q = supabase.table('liquidacion_prorrateo') \
        .select('*, unidades_funcionales(id, numero, piso, tipo, vecino_nombre, vecino_email)') \
        .eq('liquidacion_id', lid)
    if unidades_ids:
        q = q.in_('unidad_id', unidades_ids)
    prorrateos = q.execute().data

    # Obtener rubros con items
    rubros = _rubros_con_items(lid)

    enviados = 0
    fallidos = 0
    from_email = os.environ.get('RESEND_FROM_EMAIL', 'Niddo <noreply@niddo.app>')

    for prorrateo in prorrateos:
        uf = prorrateo.get('unidades_funcionales', {})
        email_destino = uf.get('vecino_email', '')

        html = _generar_resumen_html(liq, prorrateo, rubros, consorcio, uf)

        estado = 'enviado'
        error_detalle = None
        fecha_envio = now_iso()

        if email_destino and resend.api_key:
            try:
                periodo_display = liq.get('periodo', '')
                resend.Emails.send({
                    'from': from_email,
                    'to': [email_destino],
                    'subject': (
                        # El asunto distingue la complementaria: es lo primero que ve el
                        # vecino y con el mismo texto los dos mails se confunden entre sí.
                        f'📋 Expensa complementaria — {consorcio.get("nombre", "")} — {periodo_display}'
                        if int(liq.get('numero_revision') or 1) > 1 else
                        f'📋 Resumen de expensas — {consorcio.get("nombre", "")} — {periodo_display}'
                    ),
                    'html': html,
                })
                enviados += 1
            except Exception as e:
                estado = 'fallido'
                error_detalle = str(e)
                fallidos += 1
        elif not email_destino:
            estado = 'fallido'
            error_detalle = 'Sin email configurado'
            fallidos += 1
        elif not resend.api_key:
            estado = 'fallido'
            error_detalle = 'RESEND_API_KEY no configurada'
            fallidos += 1

        # Registrar envío
        supabase.table('resumen_envios').insert({
            'liquidacion_id': lid,
            'unidad_id': uf.get('id'),
            'canal': 'email',
            'estado': estado,
            'email_destino': email_destino,
            'fecha_envio': fecha_envio if estado == 'enviado' else None,
            'error_detalle': error_detalle,
            'resumen_html': html,
        }).execute()

    # Actualizar estado de liquidación a publicada
    if enviados > 0:
        supabase.table('liquidaciones').update({'estado': 'publicada'}).eq('id', lid).execute()

    return jsonify({'enviados': enviados, 'fallidos': fallidos, 'total': len(prorrateos)})


@app.route('/api/liquidaciones/<lid>/envios', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_envios(lid):
    res = supabase.table('resumen_envios') \
        .select('*, unidades_funcionales(numero, vecino_nombre, vecino_email)') \
        .eq('liquidacion_id', lid).order('created_at', desc=True).execute()
    return jsonify(res.data)


# ── Envío programado ───────────────────────────────────────────────────────────

@app.route('/api/envio-programado/<cid>', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_envio_programado_get(cid):
    res = supabase.table('envio_programado').select('*') \
        .eq('consorcio_id', cid).limit(1).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/envio-programado/<cid>', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_envio_programado_set(cid):
    admin_id = get_admin_id()
    d = request.json
    payload = {
        'consorcio_id': cid,
        'admin_id': admin_id,
        'dia_mes': d.get('dia_mes', 1),
        'hora_envio': d.get('hora_envio', '09:00'),
        'canal': d.get('canal', 'email'),
        'activo': d.get('activo', True),
    }
    res = supabase.table('envio_programado').upsert(payload, on_conflict='consorcio_id').execute()
    return jsonify(res.data[0] if res.data else {})


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('🏢 Niddo server starting...')
    print('📍 http://localhost:3500')
    app.run(host='127.0.0.1', port=3500, debug=True)

