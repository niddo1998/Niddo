import io
import os
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

# ── Export libs ────────────────────────────────────────────────────────────────
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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
    supabase.table(table).upsert(
        {'auth0_id': auth0_id, 'email': email, 'nombre': nombre, 'last_login': now_iso()},
        on_conflict='auth0_id'
    ).execute()


def get_admin_id() -> Optional[str]:
    """Devuelve el UUID de la fila en `administradores` para el usuario en sesión."""
    user = session.get('user')
    if not user:
        return None
    result = supabase.table('administradores').select('id').eq('auth0_id', user['sub']).single().execute()
    return result.data['id'] if result.data else None


def excel_response(wb: openpyxl.Workbook, filename: str) -> Response:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     download_name=filename, as_attachment=True)


def pdf_response(buf: io.BytesIO, filename: str) -> Response:
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', download_name=filename, as_attachment=True)


def make_excel(headers: list, rows: list, sheet_name: str) -> openpyxl.Workbook:
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


def build_carga_masiva_template(consorcios_existentes: list) -> openpyxl.Workbook:
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
    return jsonify(res.data)


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
    q = supabase.table('gastos').select('*, consorcios(nombre), proveedores(nombre)').eq('admin_id', admin_id)
    if request.args.get('consorcio_id'):
        q = q.eq('consorcio_id', request.args['consorcio_id'])
    if request.args.get('desde'):
        q = q.gte('fecha_gasto', request.args['desde'])
    if request.args.get('hasta'):
        q = q.lte('fecha_gasto', request.args['hasta'])
    res = q.order('fecha_gasto', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/gastos', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_gastos_create():
    admin_id = get_admin_id()
    d = request.json
    payload = {
        'consorcio_id': d['consorcio_id'],
        'proveedor_id': d.get('proveedor_id') or None,
        'descripcion': d.get('descripcion', '').strip(),
        'categoria': d.get('categoria', ''),
        'monto': d.get('monto', 0),
        'fecha_gasto': d.get('fecha_gasto', str(date.today())),
        'fecha_vencimiento': d.get('fecha_vencimiento') or None,
        'pagado': d.get('pagado', False),
        'fecha_pago': d.get('fecha_pago') or None,
        'metodo_pago': d.get('metodo_pago', ''),
        'recurrente': d.get('recurrente', False),
        'frecuencia': d.get('frecuencia', ''),
        'notas': d.get('notas', ''),
        'admin_id': admin_id,
    }
    res = supabase.table('gastos').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {}), 201


@app.route('/api/gastos/<gid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_gastos_update(gid):
    admin_id = get_admin_id()
    d = request.json
    allowed = ('consorcio_id','proveedor_id','descripcion','categoria','monto','fecha_gasto',
                'fecha_vencimiento','pagado','fecha_pago','metodo_pago','recurrente','frecuencia','notas')
    payload = {k: v for k, v in d.items() if k in allowed}
    res = supabase.table('gastos').update(payload).eq('id', gid).eq('admin_id', admin_id).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/gastos/<gid>', methods=['DELETE'])
@require_auth(allowed_roles=['admin'])
def api_gastos_delete(gid):
    admin_id = get_admin_id()
    supabase.table('gastos').delete().eq('id', gid).eq('admin_id', admin_id).execute()
    return jsonify({'ok': True})


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
    result = supabase.table(table).select('*').eq('auth0_id', user['sub']).single().execute()
    return jsonify(result.data)


def get_vecino_id() -> Optional[str]:
    """Devuelve el UUID de la fila en `vecinos` para el usuario en sesión."""
    user = session.get('user')
    if not user:
        return None
    result = supabase.table('vecinos').select('id').eq('auth0_id', user['sub']).single().execute()
    return result.data['id'] if result.data else None


# ── API: Vinculación Vecino-Unidad ─────────────────────────────────────────────
@app.route('/api/consorcios/buscar')
@require_auth()
def api_consorcios_buscar():
    res = supabase.table('consorcios').select('id, nombre, direccion').order('nombre').execute()
    return jsonify(res.data)


@app.route('/api/consorcios/<cid>/unidades-disponibles')
@require_auth()
def api_consorcios_unidades_disponibles(cid):
    # Traer UFs de este consorcio que no tengan vecino asignado
    res = supabase.table('unidades_funcionales').select('id, numero, piso, tipo').eq('consorcio_id', cid).is_('vecino_id', 'null').order('numero').execute()
    return jsonify(res.data)


@app.route('/api/solicitudes/crear', methods=['POST'])
@require_auth(allowed_roles=['vecino'])
def api_solicitudes_crear():
    vid = get_vecino_id()
    if not vid:
        return jsonify({'error': 'Vecino no encontrado'}), 404
    
    d = request.json
    consorcio_id = d.get('consorcio_id')
    unidad_id = d.get('unidad_id')
    if not consorcio_id or not unidad_id:
        return jsonify({'error': 'Campos obligatorios faltantes'}), 400
    
    # Verificar si ya existe una solicitud pendiente para este vecino
    existing = supabase.table('solicitudes_vinculacion').select('id').eq('vecino_id', vid).eq('estado', 'pendiente').execute().data
    if existing:
        return jsonify({'error': 'Ya tienes una solicitud de vinculación pendiente'}), 400
    
    payload = {
        'vecino_id': vid,
        'consorcio_id': consorcio_id,
        'unidad_id': unidad_id,
        'estado': 'pendiente'
    }
    res = supabase.table('solicitudes_vinculacion').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/solicitudes/mi-estado')
@require_auth(allowed_roles=['vecino'])
def api_solicitudes_mi_estado():
    vid = get_vecino_id()
    if not vid:
        return jsonify({'error': 'Vecino no encontrado'}), 404
    
    res = supabase.table('solicitudes_vinculacion').select(
        'id, estado, created_at, consorcios(nombre), unidades_funcionales(numero)'
    ).eq('vecino_id', vid).in_('estado', ['pendiente', 'rechazada']).order('created_at', desc=True).limit(1).execute()
    
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/admin/solicitudes')
@require_auth(allowed_roles=['admin'])
def api_admin_solicitudes():
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Admin no encontrado'}), 404
    
    # Buscar consorcios administrados por este admin
    consorcios_res = supabase.table('consorcios').select('id').eq('admin_id', admin_id).execute()
    cids = [c['id'] for c in consorcios_res.data]
    if not cids:
        return jsonify([])
    
    # Buscar solicitudes pendientes para esos consorcios
    res = supabase.table('solicitudes_vinculacion').select(
        'id, estado, created_at, vecino_id, vecinos(nombre, email), consorcios(nombre), unidades_funcionales(id, numero)'
    ).eq('estado', 'pendiente').in_('consorcio_id', cids).order('created_at', desc=True).execute()
    
    return jsonify(res.data)


@app.route('/api/admin/solicitudes/<sid>/procesar', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_admin_solicitudes_procesar(sid):
    d = request.json
    nuevo_estado = d.get('estado')
    if nuevo_estado not in ('aprobada', 'rechazada'):
        return jsonify({'error': 'Estado inválido'}), 400
    
    # Buscar la solicitud
    req_res = supabase.table('solicitudes_vinculacion').select('*').eq('id', sid).single().execute()
    req = req_res.data
    if not req:
        return jsonify({'error': 'Solicitud no encontrada'}), 404
    if req['estado'] != 'pendiente':
        return jsonify({'error': 'La solicitud ya fue procesada anteriormente'}), 400
    
    # Actualizar estado de la solicitud
    supabase.table('solicitudes_vinculacion').update({'estado': nuevo_estado}).eq('id', sid).execute()
    
    if nuevo_estado == 'aprobada':
        # Obtener información del vecino
        vecino_res = supabase.table('vecinos').select('*').eq('id', req['vecino_id']).single().execute()
        vecino = vecino_res.data
        nombre_vecino = vecino.get('nombre') or vecino.get('email', '')
        
        # 1. Asignar vecino a la unidad funcional
        supabase.table('unidades_funcionales').update({
            'vecino_id': req['vecino_id'],
            'vecino_nombre': nombre_vecino,
            'vecino_email': vecino.get('email', '')
        }).eq('id', req['unidad_id']).execute()
        
        # Obtener el número de la unidad funcional
        uf_res = supabase.table('unidades_funcionales').select('numero').eq('id', req['unidad_id']).single().execute()
        uf_numero = uf_res.data['numero'] if uf_res.data else ''
        
        # 2. Vincular el consorcio y unidad en el perfil del vecino
        supabase.table('vecinos').update({
            'consorcio_id': req['consorcio_id'],
            'unidad': uf_numero
        }).eq('id', req['vecino_id']).execute()
        
    return jsonify({'status': 'success', 'nuevo_estado': nuevo_estado})


# ── API: Comunicados y Notificaciones ──────────────────────────────────────────
@app.route('/api/admin/comunicados', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_admin_comunicados_crear():
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Admin no encontrado'}), 404
    
    d = request.json
    consorcio_id = d.get('consorcio_id') or None
    unidad_id = d.get('unidad_id') or None
    asunto = d.get('asunto')
    cuerpo = d.get('cuerpo')
    
    if not asunto or not cuerpo:
        return jsonify({'error': 'Asunto y cuerpo son requeridos'}), 400
    
    payload = {
        'admin_id': admin_id,
        'consorcio_id': consorcio_id,
        'unidad_id': unidad_id,
        'asunto': asunto,
        'cuerpo': cuerpo
    }
    res = supabase.table('comunicados').insert(payload).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/vecino/comunicados')
@require_auth(allowed_roles=['vecino'])
def api_vecino_comunicados():
    vid = get_vecino_id()
    if not vid:
        return jsonify({'error': 'Vecino no encontrado'}), 404
    
    # Obtener perfil del vecino
    vecino_res = supabase.table('vecinos').select('consorcio_id').eq('id', vid).single().execute()
    vecino = vecino_res.data
    if not vecino or not vecino.get('consorcio_id'):
        return jsonify([])
    
    cid = vecino['consorcio_id']
    
    # Obtener el admin_id del consorcio
    consorcio_res = supabase.table('consorcios').select('admin_id').eq('id', cid).single().execute()
    admin_id = consorcio_res.data['admin_id'] if consorcio_res.data else None
    if not admin_id:
        return jsonify([])
    
    # Obtener id de la unidad funcional
    uf_res = supabase.table('unidades_funcionales').select('id').eq('consorcio_id', cid).eq('vecino_id', vid).limit(1).execute()
    uf_id = uf_res.data[0]['id'] if uf_res.data else None
    
    # Construir consulta con filtros OR
    filter_str = f'and(consorcio_id.is.null,admin_id.eq.{admin_id})'
    filter_str += f',and(consorcio_id.eq.{cid},unidad_id.is.null)'
    if uf_id:
        filter_str += f',and(consorcio_id.eq.{cid},unidad_id.eq.{uf_id})'
        
    res = supabase.table('comunicados').select('*').or_(filter_str).order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/vecino/expensas', methods=['GET'])
@require_auth(allowed_roles=['vecino'])
def api_vecino_expensas():
    vid = get_vecino_id()
    if not vid:
        return jsonify({'error': 'Vecino no encontrado'}), 404
    
    # Obtener perfil del vecino
    vecino_res = supabase.table('vecinos').select('consorcio_id').eq('id', vid).single().execute()
    vecino = vecino_res.data
    if not vecino or not vecino.get('consorcio_id'):
        return jsonify([])
    
    cid = vecino['consorcio_id']
    
    # Obtener id de la unidad funcional
    uf_res = supabase.table('unidades_funcionales').select('id').eq('consorcio_id', cid).eq('vecino_id', vid).limit(1).execute()
    uf_id = uf_res.data[0]['id'] if uf_res.data else None
    
    if not uf_id:
        return jsonify([])
    
    res = supabase.table('cobros').select('*').eq('unidad_id', uf_id).order('periodo', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/vecino/expensas/<cobro_id>/pagar', methods=['POST'])
@require_auth(allowed_roles=['vecino'])
def api_vecino_expensas_pagar(cobro_id):
    vid = get_vecino_id()
    if not vid:
        return jsonify({'error': 'Vecino no encontrado'}), 404
        
    # Obtener perfil del vecino
    vecino_res = supabase.table('vecinos').select('consorcio_id').eq('id', vid).single().execute()
    vecino = vecino_res.data
    if not vecino or not vecino.get('consorcio_id'):
        return jsonify({'error': 'Vecino sin consorcio vinculado'}), 400
        
    cid = vecino['consorcio_id']
    
    # Obtener id de la unidad funcional
    uf_res = supabase.table('unidades_funcionales').select('id').eq('consorcio_id', cid).eq('vecino_id', vid).limit(1).execute()
    uf_id = uf_res.data[0]['id'] if uf_res.data else None
    
    if not uf_id:
        return jsonify({'error': 'Vecino sin unidad funcional vinculada'}), 400
        
    # Validar que el cobro pertenezca a la unidad del vecino
    cobro_res = supabase.table('cobros').select('*').eq('id', cobro_id).single().execute()
    cobro = cobro_res.data
    if not cobro or cobro['unidad_id'] != uf_id:
        return jsonify({'error': 'Cobro no encontrado o acceso denegado'}), 404
        
    d = request.json
    monto = d.get('monto')
    fecha_pago = d.get('fecha_pago') or str(date.today())
    comprobante_nombre = d.get('comprobante_nombre') or 'comprobante.pdf'
    
    # Actualizar estado de cobro
    payload = {
        'fecha_pago': fecha_pago,
        'comprobante_nombre': comprobante_nombre,
        'notas': f"Comprobante cargado por vecino por ${monto}. Pago a verificar."
    }
    
    res = supabase.table('cobros').update(payload).eq('id', cobro_id).execute()
    return jsonify(res.data[0] if res.data else {})


@app.route('/api/vecino/gastos', methods=['GET'])
@require_auth(allowed_roles=['vecino'])
def api_vecino_gastos():
    vid = get_vecino_id()
    if not vid:
        return jsonify({'error': 'Vecino no encontrado'}), 404
        
    # Obtener perfil del vecino
    vecino_res = supabase.table('vecinos').select('consorcio_id').eq('id', vid).single().execute()
    vecino = vecino_res.data
    if not vecino or not vecino.get('consorcio_id'):
        return jsonify([])
        
    cid = vecino['consorcio_id']
    
    q = supabase.table('gastos').select('*, proveedores(nombre)').eq('consorcio_id', cid)
    
    if request.args.get('desde'):
        q = q.gte('fecha_gasto', request.args['desde'])
    if request.args.get('hasta'):
        q = q.lte('fecha_gasto', request.args['hasta'])
        
    res = q.order('fecha_gasto', desc=True).execute()
    return jsonify(res.data)


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
    res = q.order('periodo', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/liquidaciones', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_liquidaciones_create():
    """Crea una liquidación nueva. Opcionalmente auto-genera rubros desde gastos del período."""
    admin_id = get_admin_id()
    d = request.json
    consorcio_id = d['consorcio_id']
    periodo = d['periodo']  # "2026-07"

    # Crear cabecera
    payload = {
        'consorcio_id': consorcio_id,
        'admin_id': admin_id,
        'periodo': periodo,
        'fecha_vencimiento_1': d.get('fecha_vencimiento_1'),
        'fecha_vencimiento_2': d.get('fecha_vencimiento_2'),
        'interes_2_vto': d.get('interes_2_vto', 0),
        'saldo_inicial': d.get('saldo_inicial', 0),
        'notas': d.get('notas', ''),
        'estado': 'borrador',
    }
    liq_res = supabase.table('liquidaciones').insert(payload).execute()
    liq = liq_res.data[0] if liq_res.data else {}
    liq_id = liq.get('id')

    if not liq_id:
        return jsonify({'error': 'Error al crear liquidación'}), 500

    # Auto-generar rubros desde gastos del período
    if d.get('auto_generar', True):
        _generar_rubros_desde_gastos(liq_id, consorcio_id, periodo, admin_id)
        _generar_prorrateo(liq_id, consorcio_id, periodo)
        _recalcular_totales(liq_id)

    # Refetch con datos completos
    liq = supabase.table('liquidaciones').select('*, consorcios(nombre, direccion)').eq('id', liq_id).single().execute().data
    return jsonify(liq), 201


def _generar_rubros_desde_gastos(liq_id, consorcio_id, periodo, admin_id):
    """Agrupa los gastos del consorcio en el período por categoría → rubros."""
    # Determinar rango de fechas del período
    year, month = periodo.split('-')
    desde = f'{year}-{month}-01'
    if int(month) == 12:
        hasta = f'{int(year)+1}-01-01'
    else:
        hasta = f'{year}-{int(month)+1:02d}-01'

    gastos = supabase.table('gastos').select('*') \
        .eq('consorcio_id', consorcio_id) \
        .eq('admin_id', admin_id) \
        .gte('fecha_gasto', desde) \
        .lt('fecha_gasto', hasta) \
        .execute().data

    # Agrupar por rubro
    rubros_dict = {}  # {numero_rubro: {nombre, items: [{descripcion, monto, gasto_id}]}}
    for g in gastos:
        cat = (g.get('categoria') or 'otro').lower()
        num, nombre = CATEGORIA_A_RUBRO.get(cat, (10, 'Otros gastos'))
        if num not in rubros_dict:
            rubros_dict[num] = {'nombre': nombre, 'items': []}
        rubros_dict[num]['items'].append({
            'descripcion': g.get('descripcion', ''),
            'monto': float(g.get('monto', 0)),
            'gasto_id': g.get('id'),
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
            } for it in r['items']]
            if items_payload:
                supabase.table('liquidacion_items').insert(items_payload).execute()


def _generar_prorrateo(liq_id, consorcio_id, periodo):
    """Genera la tabla de prorrateo para cada UF del consorcio."""
    ufs = supabase.table('unidades_funcionales').select('*') \
        .eq('consorcio_id', consorcio_id).order('numero').execute().data

    # Calcular total de egresos de esta liquidación
    rubros = supabase.table('liquidacion_rubros').select('subtotal') \
        .eq('liquidacion_id', liq_id).execute().data
    total_egresos = sum(float(r.get('subtotal', 0)) for r in rubros)

    # Buscar cobros del período anterior para saldos
    year, month = periodo.split('-')
    if int(month) == 1:
        periodo_ant = f'{int(year)-1}-12'
    else:
        periodo_ant = f'{year}-{int(month)-1:02d}'

    prorrateo_rows = []
    for uf in ufs:
        pct_a = float(uf.get('porcentaje_a', 0))
        pct_c = float(uf.get('porcentaje_c', 0))
        expensa_a = round(total_egresos * pct_a / 100, 2) if pct_a > 0 else 0
        adicional = round(total_egresos * pct_c / 100, 2) if pct_c > 0 else 0

        # Buscar saldo anterior (cobro del período anterior)
        cobro_ant = supabase.table('cobros').select('total, estado, fecha_pago') \
            .eq('unidad_id', uf['id']).eq('periodo', periodo_ant).limit(1).execute().data
        saldo_ant = 0
        pago = 0
        if cobro_ant:
            c = cobro_ant[0]
            if c.get('estado') == 'pagado':
                pago = float(c.get('total', 0))
            else:
                saldo_ant = float(c.get('total', 0))

        saldo_pend = round(saldo_ant - pago, 2) if saldo_ant > 0 else 0
        total_unidad = round(expensa_a + adicional + saldo_pend, 2)

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
            'extraordinaria': 0,
            'redondeo': 0,
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
    supabase.table('liquidaciones').delete().eq('id', lid).eq('admin_id', admin_id).eq('estado', 'borrador').execute()
    return jsonify({'ok': True})


@app.route('/api/liquidaciones/<lid>/rubros', methods=['GET'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_rubros(lid):
    rubros = supabase.table('liquidacion_rubros').select('*') \
        .eq('liquidacion_id', lid).order('numero_rubro').execute().data
    for r in rubros:
        items = supabase.table('liquidacion_items').select('*') \
            .eq('rubro_id', r['id']).execute().data
        r['items'] = items
    return jsonify(rubros)


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
               'extraordinaria', 'redondeo', 'total_unidad')
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

    total_unidad = float(prorrateo.get('total_unidad', 0))
    total_egresos = float(liq.get('total_egresos', 0)) or 1

    # Agrupar rubros en categorías simples
    categorias = {}
    obras_en_curso = []
    for r in rubros:
        cat_simple = RUBRO_A_CATEGORIA_SIMPLE.get(r.get('numero_rubro', 10), 'Otros')
        monto = float(r.get('subtotal', 0))
        if cat_simple not in categorias:
            categorias[cat_simple] = 0
        categorias[cat_simple] += monto

        # Buscar items con cuotas (obras en curso)
        for it in r.get('items', []):
            if it.get('es_cuota') and it.get('cuota_actual') and it.get('cuota_total'):
                obras_en_curso.append({
                    'desc': it['descripcion'],
                    'cuota': it['cuota_actual'],
                    'total': it['cuota_total'],
                })

    pct_a = float(prorrateo.get('porcentaje_a', 0))
    cat_icons = {'Personal': '👤', 'Servicios': '⚡', 'Mantenimiento': '🔧',
                 'Administración': '📋', 'Seguros': '🛡️', 'Otros': '📦'}

    # Build category rows
    cat_rows = ''
    for cat, monto in sorted(categorias.items(), key=lambda x: -x[1]):
        pct = (monto / total_egresos * 100) if total_egresos > 0 else 0
        monto_uf = round(monto * pct_a / 100, 2) if pct_a > 0 else monto
        icon = cat_icons.get(cat, '📦')
        cat_rows += f'''
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;font-size:14px;">{icon} {cat}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;text-align:right;font-size:14px;font-weight:600;">${monto_uf:,.2f}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f0f0f5;text-align:right;font-size:13px;color:#888;">{pct:.1f}%</td>
        </tr>'''

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
    <p style="margin:0;font-size:13px;color:#888;text-transform:uppercase;letter-spacing:.05em;font-weight:600;">Tu expensa este mes</p>
    <p style="margin:8px 0 0;font-size:38px;font-weight:800;color:#111;">${total_unidad:,.2f}</p>
    <p style="margin:6px 0 0;font-size:12px;color:#888;">UF {uf.get('numero', '')} — Piso {uf.get('piso', '—')} — {uf.get('vecino_nombre', '')}</p>
</div>

<!-- Desglose por categoría -->
<div style="background:#fff;border-radius:12px;margin-top:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
    <h3 style="margin:0 0 14px;font-size:15px;font-weight:700;color:#111;">📊 Desglose por categoría</h3>
    <table style="width:100%;border-collapse:collapse;">
        <thead>
            <tr style="border-bottom:2px solid #7C3AED;">
                <th style="padding:8px 14px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;">Categoría</th>
                <th style="padding:8px 14px;text-align:right;font-size:11px;color:#888;text-transform:uppercase;">Monto</th>
                <th style="padding:8px 14px;text-align:right;font-size:11px;color:#888;text-transform:uppercase;">%</th>
            </tr>
        </thead>
        <tbody>{cat_rows}</tbody>
    </table>
</div>

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

<!-- Fondo del consorcio -->
<div style="background:#f8f7ff;border-radius:12px;margin-top:16px;padding:18px;text-align:center;">
    <p style="margin:0;font-size:12px;color:#888;text-transform:uppercase;font-weight:600;">Saldo del fondo del consorcio</p>
    <p style="margin:6px 0 0;font-size:22px;font-weight:800;color:#7C3AED;">${saldo_final:,.2f}</p>
</div>

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

    rubros = supabase.table('liquidacion_rubros').select('*') \
        .eq('liquidacion_id', lid).order('numero_rubro').execute().data
    # Fetch items for each rubro
    for r in rubros:
        items = supabase.table('liquidacion_items').select('*') \
            .eq('rubro_id', r['id']).execute().data
        r['items'] = items

    html = _generar_resumen_html(liq, prorrateo, rubros, consorcio, uf)

    if request.args.get('format') == 'html':
        return Response(html, mimetype='text/html')
    return jsonify({'html': html, 'uf': uf, 'total': prorrateo.get('total_unidad')})


# ── Envío de resúmenes por email ───────────────────────────────────────────────

@app.route('/api/liquidaciones/<lid>/enviar', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_liquidacion_enviar(lid):
    """Envía resúmenes por email a todas las UFs (o las seleccionadas)."""
    import resend
    resend.api_key = os.environ.get('RESEND_API_KEY', '')

    d = request.json or {}
    unidades_ids = d.get('unidades_ids')  # None = todas

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
    rubros = supabase.table('liquidacion_rubros').select('*') \
        .eq('liquidacion_id', lid).order('numero_rubro').execute().data
    for r in rubros:
        items = supabase.table('liquidacion_items').select('*') \
            .eq('rubro_id', r['id']).execute().data
        r['items'] = items

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
                    'subject': f'📋 Resumen de expensas — {consorcio.get("nombre", "")} — {periodo_display}',
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
