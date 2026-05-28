from flask import Flask, render_template, send_from_directory, request, redirect, url_for
import os

app = Flask(__name__)
app.secret_key = 'niddo-secret-key-2024'

# Configure static folder
app.static_folder = 'static'

@app.route('/')
def index():
    """Serve the main landing page"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Serve the login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if username == 'admin' and password == '1234':
            return redirect(url_for('dashboard', role=role))
        else:
            return render_template('login.html', error='Credenciales incorrectas')
    
    return render_template('login.html')

@app.route('/dashboard/<role>')
def dashboard(role):
    """Serve role-specific dashboards"""
    if role == 'admin':
        return render_template('admin_dashboard.html')
    elif role == 'vecino':
        return render_template('vecino_dashboard.html')
    elif role == 'proveedor':
        return render_template('proveedor_dashboard.html')
    else:
        return redirect(url_for('login'))

@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files (CSS, JS, images)"""
    return send_from_directory('.', filename)

@app.route('/vecinos')
def vecinos():
    """Placeholder for vecinos page"""
    return render_template('index.html')

@app.route('/proveedores')
def proveedores():
    """Placeholder for proveedores page"""
    return render_template('index.html')

@app.route('/clientes')
def clientes():
    """Placeholder for clientes page"""
    return render_template('index.html')

@app.route('/administradores')
def administradores():
    """Placeholder for administradores page"""
    return render_template('index.html')

if __name__ == '__main__':
    app.debug = True
    print("🏢 Niddo landing page starting...")
    print("📍 Server will be available at: http://localhost:3500")
    print("🚀 Press Ctrl+C to stop the server")
    app.run(host='127.0.0.1', port=3500, debug=True)
