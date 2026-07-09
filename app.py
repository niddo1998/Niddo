import io
import csv
import os
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

# ── Export libs ────────────────────────────────────────────────────────────────
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
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
    result = supabase.table('administradores').select('id').eq('auth0_id', user['sub']).single().execute()
    return result.data['id'] if result.data else None


def get_vecino_id() -> Optional[str]:
    """Devuelve el UUID de la fila en `vecinos` para el vecino en sesión."""
    user = session.get('user')
    if not user:
        return None
    result = supabase.table('vecinos').select('id').eq('auth0_id', user['sub']).single().execute()
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


@app.route('/api/consorcios/<cid>/unidades/bulk', methods=['POST'])
@require_auth(allowed_roles=['admin'])
def api_ufs_bulk(cid):
    """Carga masiva desde CSV. Columnas: numero,piso,tipo,superficie_m2,vecino_nombre,vecino_email"""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No se envió archivo'}), 400
    stream = io.StringIO(file.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    rows = []
    for row in reader:
        rows.append({
            'consorcio_id': cid,
            'numero': row.get('numero', '').strip(),
            'piso': row.get('piso', ''),
            'tipo': row.get('tipo', 'departamento'),
            'superficie_m2': row.get('superficie_m2') or None,
            'vecino_nombre': row.get('vecino_nombre', ''),
            'vecino_email': row.get('vecino_email', ''),
        })
    if rows:
        supabase.table('unidades_funcionales').insert(rows).execute()
    return jsonify({'inserted': len(rows)})


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
    # Soporte multipart/form-data para archivos adjuntos
    d = request.form if request.content_type and 'multipart' in request.content_type else request.json or {}
    payload = {
        'consorcio_id': d.get('consorcio_id') or d.get('consorcio_id', ''),
        'proveedor_id': d.get('proveedor_id') or None,
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
    res = supabase.table('gastos').insert(payload).execute()
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
    allowed = ('consorcio_id','proveedor_id','descripcion','categoria','monto','fecha_gasto',
                'fecha_vencimiento','pagado','fecha_pago','metodo_pago','recurrente','frecuencia','notas')
    payload = {}
    for k in allowed:
        if k in d:
            v = d[k]
            if k == 'monto':
                v = float(v)
            elif k in ('pagado', 'recurrente'):
                v = v in (True, 'true', 'on', '1')
            elif k in ('proveedor_id', 'fecha_vencimiento', 'fecha_pago'):
                v = v or None
            payload[k] = v
    res = supabase.table('gastos').update(payload).eq('id', gid).eq('admin_id', admin_id).execute()
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
    result = supabase.table(table).select('*').eq('auth0_id', user['sub']).single().execute()
    return jsonify(result.data)




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
    for vot in votaciones:
        votos_res = supabase.table('votos').select('opcion').eq('votacion_id', vot['id']).execute()
        votos = votos_res.data or []
        conteo = {}
        for voto in votos:
            op = voto['opcion']
            conteo[op] = conteo.get(op, 0) + 1
        vot['conteo_votos'] = conteo
        vot['total_votos'] = len(votos)
        vot['ya_vote'] = False
        if unidad_id:
            mi_voto = supabase.table('votos').select('opcion').eq('votacion_id', vot['id']).eq('unidad_id', unidad_id).execute()
            if mi_voto.data:
                vot['ya_vote'] = True
                vot['mi_opcion'] = mi_voto.data[0]['opcion']
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
        q = supabase.table('avisos_pago').select('*, vecinos(nombre, email, unidad)').eq('consorcio_id', cid)
    else:
        cons = supabase.table('consorcios').select('id').eq('admin_id', admin_id).execute().data or []
        cids = [c['id'] for c in cons]
        if not cids:
            return jsonify([])
        q = supabase.table('avisos_pago').select('*, vecinos(nombre, email, unidad)').in_('consorcio_id', cids)
    res = q.order('created_at', desc=True).execute()
    return jsonify(res.data)


@app.route('/api/admin/avisos-pago/<aid>', methods=['PUT'])
@require_auth(allowed_roles=['admin'])
def api_admin_avisos_pago_update(aid):
    d = request.json or {}
    payload = {k: v for k, v in d.items() if k in ('estado',)}
    res = supabase.table('avisos_pago').update(payload).eq('id', aid).execute()
    return jsonify(res.data[0] if res.data else {})


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('🏢 Niddo server starting...')
    print('📍 http://localhost:3500')
    app.run(host='127.0.0.1', port=3500, debug=True)
