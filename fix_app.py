import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Remove global imports
content = re.sub(
    r"# ── Export libs ────────────────────────────────────────────────────────────────\nimport openpyxl\nfrom openpyxl.styles import Font, PatternFill, Alignment\nfrom openpyxl.worksheet.datavalidation import DataValidation\nfrom reportlab.lib.pagesizes import A4, landscape\nfrom reportlab.lib import colors\nfrom reportlab.lib.units import cm\nfrom reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer\nfrom reportlab.lib.styles import getSampleStyleSheet\n",
    "", content)

# 2. Add local imports
content = content.replace("def excel_response(wb: openpyxl.Workbook, filename: str) -> Response:", "def excel_response(wb, filename: str) -> Response:\n    import openpyxl")
content = content.replace("def make_excel(headers: list, rows: list, sheet_name: str) -> openpyxl.Workbook:", "def make_excel(headers: list, rows: list, sheet_name: str):\n    import openpyxl\n    from openpyxl.styles import Font, PatternFill, Alignment")
content = content.replace("def build_carga_masiva_template(consorcios_existentes: list) -> openpyxl.Workbook:", "def build_carga_masiva_template(consorcios_existentes: list):\n    import openpyxl\n    from openpyxl.styles import Font, PatternFill, Alignment\n    from openpyxl.worksheet.datavalidation import DataValidation")
content = content.replace("def make_pdf(title: str, headers: list, rows: list) -> io.BytesIO:", "def make_pdf(title: str, headers: list, rows: list) -> io.BytesIO:\n    from reportlab.lib.pagesizes import A4, landscape\n    from reportlab.lib import colors\n    from reportlab.lib.units import cm\n    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer\n    from reportlab.lib.styles import getSampleStyleSheet")
content = content.replace("def pdf_liquidacion(consorcio: dict, periodo: str, gastos: list, resumen: dict, prorr_items: list) -> bytes:", "def pdf_liquidacion(consorcio: dict, periodo: str, gastos: list, resumen: dict, prorr_items: list) -> bytes:\n    from reportlab.lib.pagesizes import A4, landscape\n    from reportlab.lib import colors\n    from reportlab.lib.units import cm\n    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer\n    from reportlab.lib.styles import getSampleStyleSheet")
content = content.replace("wb = openpyxl.load_workbook(io.BytesIO(file.read()), data_only=True)", "import openpyxl\n        wb = openpyxl.load_workbook(io.BytesIO(file.read()), data_only=True)")
content = content.replace("def api_vecinos_cupon_pago(rid):", "def api_vecinos_cupon_pago(rid):\n    from reportlab.lib.pagesizes import A4\n    from reportlab.lib import colors\n    from reportlab.lib.units import cm\n    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer\n    from reportlab.lib.styles import getSampleStyleSheet")

# 3. Update query in avisos_pago
content = content.replace("q = supabase.table('avisos_pago').select('*, vecinos(nombre, email, unidad)').eq('consorcio_id', cid)", "q = supabase.table('avisos_pago').select('id, consorcio_id, vecino_id, unidad_id, cobro_id, monto, fecha_pago, medio_pago, observaciones, adjunto_nombre, adjunto_mime, estado, created_at, vecinos(nombre, email, unidad)').eq('consorcio_id', cid)")
content = content.replace("q = supabase.table('avisos_pago').select('*, vecinos(nombre, email, unidad)').in_('consorcio_id', cids)", "q = supabase.table('avisos_pago').select('id, consorcio_id, vecino_id, unidad_id, cobro_id, monto, fecha_pago, medio_pago, observaciones, adjunto_nombre, adjunto_mime, estado, created_at, vecinos(nombre, email, unidad)').in_('consorcio_id', cids)")

with open('app.py', 'w') as f:
    f.write(content)
