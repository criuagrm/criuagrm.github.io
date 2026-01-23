import os
import datetime
from flask import Flask, jsonify, request, send_file, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'clave_secreta_uagrm_politica' # Necesario para el login

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
# Render entrega la URL como 'postgres://', SQLAlchemy necesita 'postgresql://'
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local_tutores.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 2. MODELOS DE BASE DE DATOS ---

class User(UserMixin, db.Model):
    """Sistema de Usuarios (Admin y Estudiantes)"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True) # Admin: 'admin', Est: Registro
    password = db.Column(db.String(100)) # Admin: 'admin123', Est: Carnet
    role = db.Column(db.String(20)) # 'admin' o 'student'
    
    # Relación con perfil de estudiante
    student_profile = db.relationship('StudentProfile', backref='user_account', uselist=False)

class Tutor(db.Model):
    """Lista de Docentes y Cupos"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    # Contadores de cupos ocupados
    taken_II = db.Column(db.Integer, default=0)
    taken_III = db.Column(db.Integer, default=0)
    taken_IV = db.Column(db.Integer, default=0)
    
    students = db.relationship('StudentProfile', backref='tutor', lazy=True)

class StudentProfile(db.Model):
    """Perfil del Estudiante (Solicitudes)"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Se vincula al aprobar
    
    full_name = db.Column(db.String(100))
    registro = db.Column(db.String(20))
    carnet = db.Column(db.String(20))
    practicum_level = db.Column(db.String(5)) # II, III, IV
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutor.id'))
    
    status = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE -> ACTIVO -> FINALIZADO
    drive_folder_url = db.Column(db.String(300)) # Link a la carpeta de Drive (Puesto por el Director)
    
    submissions = db.relationship('Submission', backref='student', lazy=True)

class Submission(db.Model):
    """Control de Hitos/Entregas"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    tipo = db.Column(db.String(50)) # 'PLAN', 'INFORME', 'MEMORIA'
    date_submitted = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(20), default='EN_REVISION') 
    teacher_feedback = db.Column(db.Text)

# --- 3. CONFIGURACIÓN INICIAL ---
CAPACIDAD = {"II": 5, "III": 3, "IV": 2}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Datos semilla de tutores
DATOS_INICIALES = [
    {"nombre": "Alejandro Mansilla Arias", "tel": "716 30 108", "email": "alejandro.mansilla@uagrm.edu.bo"},
    {"nombre": "Alfredo Víctor Copaz Pacheco", "tel": "726 48 166", "email": "alfredo.copaz@uagrm.edu.bo"},
    {"nombre": "Armengol Vaca Flores", "tel": "716 31 448", "email": "armengol.vaca@uagrm.edu.bo"},
    {"nombre": "Berman Saucedo Campos", "tel": "721 55 880", "email": "berman.saucedo@uagrm.edu.bo"},
    {"nombre": "Cecilia Rua Heredia", "tel": "721 26 100", "email": "cecilia.rua@uagrm.edu.bo"},
    {"nombre": "Daniel Valverde Aparicio", "tel": "760 09 909", "email": "daniel.valverde@uagrm.edu.bo"},
    {"nombre": "Edwin Javier Alarcón Vásquez", "tel": "721 70 868", "email": "edwin.alarcon@uagrm.edu.bo"},
    {"nombre": "Francisco Méndez Egüez", "tel": "721 65 897", "email": "francisco.mendez@uagrm.edu.bo"},
    {"nombre": "Grover Núñez Klinsky", "tel": "721 23 441", "email": "grover.nunez@uagrm.edu.bo"},
    {"nombre": "Javier Hernández Serrano", "tel": "763 32 033", "email": "javier.hernandez@uagrm.edu.bo"},
    {"nombre": "Juan Rubén Cabello Mérida", "tel": "713 45 312", "email": "juan.cabello@uagrm.edu.bo"},
    {"nombre": "José Luis Andia Fernández", "tel": "721 89 977", "email": "jose.andia@uagrm.edu.bo"},
    {"nombre": "Julio Guzmán Gutiérrez", "tel": "770 24 779", "email": "julio.guzman@uagrm.edu.bo"},
    {"nombre": "Jorge Espinoza Moreno", "tel": "702 04 333", "email": "jorge.espinoza@uagrm.edu.bo"},
    {"nombre": "Jorge Francisco Rojas Bonilla", "tel": "709 37 494", "email": "jorge.rojas@uagrm.edu.bo"},
    {"nombre": "Leo Ricardo Klinsky Marín", "tel": "708 88 383", "email": "leo.klinsky@uagrm.edu.bo"},
    {"nombre": "Marcelo Arrazola Weise", "tel": "709 55 063", "email": "marcelo.arrazola@uagrm.edu.bo"},
    {"nombre": "Ma. Hortencia Ayala De Fernández", "tel": "700 08 294", "email": "hortencia.ayala@uagrm.edu.bo"},
    {"nombre": "Manfredo Rafael Bravo Chávez", "tel": "760 03 190", "email": "manfredo.bravo@uagrm.edu.bo"},
    {"nombre": "Mario Campos Barrera", "tel": "776 59 663", "email": "mario.campos@uagrm.edu.bo"},
    {"nombre": "Maria Rosario Chávez Vaca", "tel": "768 58 598", "email": "maria.chavez@uagrm.edu.bo"},
    {"nombre": "Maria Elizabeth Galarza De Eid", "tel": "760 00 944", "email": "maria.galarza@uagrm.edu.bo"},
    {"nombre": "Menacho Manfredo", "tel": "756 37 378", "email": "manfredo.menacho@uagrm.edu.bo"},
    {"nombre": "Maria Angélica Suárez", "tel": "678 94 922", "email": "maria.suarez@uagrm.edu.bo"},
    {"nombre": "Marcio Aranda García", "tel": "620 00 571", "email": "marcio.aranda@uagrm.edu.bo"},
    {"nombre": "Marco Antonio Torrez Valverde", "tel": "776 72 950", "email": "marco.torrez@uagrm.edu.bo"},
    {"nombre": "Nicolás Ribera Cardozo", "tel": "708 27 450", "email": "nicolas.ribera@uagrm.edu.bo"},
    {"nombre": "Oswaldo Martorell Roca", "tel": "773 42 184", "email": "oswaldo.martorell@uagrm.edu.bo"},
    {"nombre": "Odin Rodríguez Mercado", "tel": "721 58 042", "email": "odin.rodriguez@uagrm.edu.bo"},
    {"nombre": "Paula Alejandra Peña Hasbun", "tel": "773 54 565", "email": "paula.pena@uagrm.edu.bo"},
    {"nombre": "Reymi Luis Ferreira Justiniano", "tel": "721 20 832", "email": "reymi.ferreira@uagrm.edu.bo"},
    {"nombre": "Ricardo Pérez Peredo", "tel": "726 62 754", "email": "ricardo.perez@uagrm.edu.bo"},
    {"nombre": "Roger Emilio Tuero Velásquez", "tel": "708 14 346", "email": "roger.tuero@uagrm.edu.bo"},
    {"nombre": "Sarah Gutiérrez Mendoza", "tel": "709 50 778", "email": "sarah.gutierrez@uagrm.edu.bo"}
]

with app.app_context():
    db.create_all()
    
    # 1. Cargar Tutores si está vacío
    if Tutor.query.count() == 0:
        print("Cargando docentes...")
        for d in DATOS_INICIALES:
            nuevo = Tutor(name=d['nombre'], phone=d['tel'], email=d['email'])
            db.session.add(nuevo)
        db.session.commit()
    
    # 2. Crear ADMIN si no existe
    if not User.query.filter_by(username='admin').first():
        print("Creando Admin...")
        # Contraseña simple para pruebas. En producción usar hash.
        admin = User(username='admin', password='123', role='admin')
        db.session.add(admin)
        db.session.commit()

# --- RUTAS PÚBLICAS (LANDING Y SOLICITUD) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tutors', methods=['GET'])
def get_tutors():
    level = request.args.get('level') 
    if level not in CAPACIDAD: return jsonify({"error": "Nivel inválido"}), 400

    tutors = Tutor.query.order_by(Tutor.name).all()
    disponibles = []
    
    for t in tutors:
        tomados = getattr(t, f"taken_{level}") 
        maximo = 0 if "Odin Rodríguez Mercado" in t.name else CAPACIDAD[level]
        if tomados < maximo:
            disponibles.append({
                "id": t.id,
                "name": t.name,
                "phone": t.phone,
                "email": t.email,
                "cupos_disponibles": maximo - tomados,
                "cupos_totales": maximo
            })
    return jsonify(disponibles)

@app.route('/api/solicitar', methods=['POST'])
def solicitar_tutor():
    # Esta ruta crea la solicitud PENDIENTE y genera el PDF
    data = request.json
    tutor_id = data.get('tutor_id')
    level = data.get('nivel')
    
    tutor = Tutor.query.get(tutor_id)
    if not tutor: return jsonify({"error": "Tutor no encontrado"}), 404

    # Verificar cupo
    campo_cupo = f"taken_{level}"
    tomados = getattr(tutor, campo_cupo)
    maximo = 0 if "Odin Rodríguez Mercado" in tutor.name else CAPACIDAD[level]

    if tomados >= maximo:
        return jsonify({"error": "Cupo lleno."}), 409

    # 1. Reservar Cupo
    setattr(tutor, campo_cupo, tomados + 1)
    
    # 2. Crear Perfil PENDIENTE
    nuevo_estudiante = StudentProfile(
        full_name=data.get('nombre'),
        registro=data.get('registro'),
        carnet=data.get('carnet'),
        practicum_level=level,
        tutor_id=tutor.id,
        status='PENDIENTE'
    )
    db.session.add(nuevo_estudiante)
    db.session.commit()
    
    # 3. Generar PDF (Carta para el Director)
    try:
        pdf_file = generar_carta_pdf(nuevo_estudiante.full_name, nuevo_estudiante.registro, nuevo_estudiante.carnet, level, tutor.name)
        return jsonify({
            "mensaje": "Solicitud registrada. Pendiente de aprobación.",
            "pdf_url": f"/descargar/{pdf_file}"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/descargar/<filename>')
def descargar_archivo(filename):
    path = os.path.join(os.getcwd(), filename)
    return send_file(path, as_attachment=True)

# --- RUTAS DE AUTENTICACIÓN (LOGIN) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        # Validación simple (en prod usar check_password_hash)
        if user and user.password == password:
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            return "<h1>Usuario o contraseña incorrectos</h1><a href='/login'>Volver</a>"
            
    # Formulario Login Simple (HTML incrustado para no crear archivo extra por ahora)
    return """
    <div style="font-family:sans-serif; max-width:400px; margin:50px auto; padding:20px; border:1px solid #ccc; border-radius:10px;">
        <h2 style="text-align:center;">Ingreso al Sistema</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Usuario / Registro" required style="width:100%; padding:10px; margin-bottom:10px;">
            <input type="password" name="password" placeholder="Contraseña / Carnet" required style="width:100%; padding:10px; margin-bottom:10px;">
            <button type="submit" style="width:100%; padding:10px; background:#cc0000; color:white; border:none; border-radius:5px; cursor:pointer;">Ingresar</button>
        </form>
    </div>
    """

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- RUTAS DIRECTOR (ADMIN) ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': return "Acceso Denegado"
    
    # Lista de solicitudes pendientes
    pendientes = StudentProfile.query.filter_by(status='PENDIENTE').all()
    activos = StudentProfile.query.filter_by(status='ACTIVO').all()
    
    # HTML simple del Admin
    html = """
    <div style="font-family:sans-serif; padding:20px;">
        <h1>Panel del Director</h1>
        <a href="/logout" style="color:red;">Cerrar Sesión</a>
        <hr>
        <h2>Solicitudes Pendientes (Requieren Aprobación)</h2>
        <table border="1" cellpadding="10" style="border-collapse:collapse; width:100%;">
            <tr style="background:#eee;">
                <th>Estudiante</th><th>Registro</th><th>Nivel</th><th>Tutor Solicitado</th><th>Acción</th>
            </tr>
    """
    for p in pendientes:
        html += f"""
            <tr>
                <td>{p.full_name}</td>
                <td>{p.registro}</td>
                <td>{p.practicum_level}</td>
                <td>{p.tutor.name}</td>
                <td>
                    <form action="/admin/approve/{p.id}" method="POST">
                        <input type="text" name="drive_url" placeholder="Pegar Link Carpeta Drive" required style="width:200px;">
                        <button type="submit" style="background:green; color:white;">APROBAR Y CREAR USUARIO</button>
                    </form>
                </td>
            </tr>
        """
    
    html += "</table><h2>Estudiantes Activos</h2><ul>"
    for a in activos:
        html += f"<li>{a.full_name} - <a href='{a.drive_folder_url}' target='_blank'>Ver Carpeta Drive</a></li>"
    
    html += "</ul></div>"
    return html

@app.route('/admin/approve/<int:student_id>', methods=['POST'])
@login_required
def approve_student(student_id):
    if current_user.role != 'admin': return "Acceso Denegado"
    
    drive_url = request.form.get('drive_url')
    student = StudentProfile.query.get(student_id)
    
    if student:
        # 1. Crear Usuario para el estudiante (Reg, Carnet)
        if not User.query.filter_by(username=student.registro).first():
            new_user = User(username=student.registro, password=student.carnet, role='student')
            db.session.add(new_user)
            db.session.commit()
            
            # 2. Vincular y Activar
            student.user_id = new_user.id
            student.status = 'ACTIVO'
            student.drive_folder_url = drive_url
            db.session.commit()
            
    return redirect(url_for('admin_dashboard'))

# --- RUTAS ESTUDIANTE ---

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student': return "Acceso Denegado"
    
    profile = current_user.student_profile
    if not profile: return "Perfil no encontrado"
    
    return f"""
    <div style="font-family:sans-serif; max-width:800px; margin:20px auto; padding:20px; border:1px solid #ddd;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h1>Bienvenido, {profile.full_name}</h1>
            <a href="/logout">Salir</a>
        </div>
        <div style="background:#f9f9f9; padding:15px; border-radius:10px; margin-bottom:20px;">
            <p><strong>Estado:</strong> <span style="color:green;">{profile.status}</span></p>
            <p><strong>Tutor:</strong> {profile.tutor.name}</p>
            <p><strong>Nivel:</strong> Practicum {profile.practicum_level}</p>
        </div>
        
        <div style="text-align:center; padding:30px; border:2px dashed #ccc; border-radius:10px;">
            <h2>📂 Tu Carpeta Digital</h2>
            <p>Sube tus informes, bitácoras y avances directamente aquí.</p>
            <a href="{profile.drive_folder_url}" target="_blank" style="display:inline-block; padding:15px 30px; background:#4285F4; color:white; text-decoration:none; font-weight:bold; border-radius:5px; font-size:18px;">
                ABRIR CARPETA DRIVE
            </a>
            <p style="margin-top:10px; font-size:12px; color:#666;">(La Dirección de Carrera revisará el contenido de esta carpeta)</p>
        </div>
        
        <h3>Calendario de Hitos</h3>
        <ul>
            <li>✅ Solicitud Aprobada</li>
            <li>⬜ Plan de Trabajo (Subir a Drive)</li>
            <li>⬜ Informe Medio (Subir a Drive)</li>
            <li>⬜ Memoria Final (Subir a Drive)</li>
        </ul>
    </div>
    """

# --- FUNCIONALIDAD EXTRA ---
@app.route('/admin/reset-total')
def reset_db():
    # Solo para emergencias - Borra cupos
    tutors = Tutor.query.all()
    for t in tutors:
        t.taken_II = 0
        t.taken_III = 0
        t.taken_IV = 0
    db.session.commit()
    return "Reset OK"

# --- GENERADOR PDF (Mismo diseño de tabla) ---
def generar_carta_pdf(nombre, registro, carnet, nivel, nombre_tutor):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    fecha = datetime.datetime.now().strftime("%d de %B de %Y")
    pdf.cell(0, 10, txt=f"Santa Cruz, {fecha}", ln=1, align='R'); pdf.ln(10)
    pdf.set_font("Arial", 'B', size=11)
    pdf.cell(0, 5, txt="Señor:", ln=1)
    pdf.cell(0, 5, txt="Lic. Odin Rodríguez Mercado", ln=1)
    pdf.cell(0, 5, txt="DIRECTOR DE CARRERA CIENCIA POLÍTICA Y ADM. PÚBLICA", ln=1)
    pdf.cell(0, 5, txt="Presente.-", ln=1); pdf.ln(15)
    pdf.cell(0, 10, txt=f"REF: SOLICITUD DE TUTOR PARA PRACTICUM {nivel}", ln=1, align='R'); pdf.ln(10)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, "De mi mayor consideración:\n\nMediante la presente, solicito formalmente la asignación de tutoría. A continuación detallo mis datos y el docente seleccionado:"); pdf.ln(10)
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', size=10)
    w_label = 60; w_data = 130; h_row = 10
    pdf.cell(w_label, h_row, "NOMBRE ESTUDIANTE:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre).upper(), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "REGISTRO UNIVERSITARIO:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(registro), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "CÉDULA DE IDENTIDAD:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(carnet), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "MATERIA:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, f"PRACTICUM {nivel}", 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "TUTOR SOLICITADO:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre_tutor).upper(), 1, 1, 'L')
    pdf.ln(20); pdf.multi_cell(0, 8, "Sin otro particular, saludo a usted atentamente."); pdf.ln(30)
    pdf.cell(0, 5, txt="__________________________", ln=1, align='C'); pdf.cell(0, 5, txt=f"{nombre}", ln=1, align='C'); pdf.cell(0, 5, txt=f"C.I. {carnet}", ln=1, align='C')
    filename = f"solicitud_{registro}_{nivel}.pdf"
    pdf.output(filename)
    return filename

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
