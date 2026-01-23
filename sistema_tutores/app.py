import os
import datetime
from flask import Flask, jsonify, request, send_file, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'clave_secreta_uagrm_politica'

# --- 1. CONFIGURACIÓN ---
# Detecta automáticamente si es Render (Postgres) o Local (SQLite)
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
    """Sistema de Usuarios (Login)"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True) # Admin: 'admin', Docente: 'docente', Est: Registro
    password = db.Column(db.String(100)) # Contraseña simple (en prod usar hash)
    role = db.Column(db.String(20)) # 'admin', 'student', 'docente'
    
    # Relación inversa con perfil de estudiante
    student_profile = db.relationship('StudentProfile', backref='user_account', uselist=False)

class Tutor(db.Model):
    """Docentes y Cupos"""
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
    """Perfil Académico del Estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Se vincula al aprobar
    
    full_name = db.Column(db.String(100))
    registro = db.Column(db.String(20))
    carnet = db.Column(db.String(20))
    practicum_level = db.Column(db.String(5)) # II, III, IV
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutor.id'))
    
    status = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE -> ACTIVO -> FINALIZADO
    drive_folder_url = db.Column(db.String(300)) # Link a la carpeta de Drive (Puesto por el Director)
    
    # Relaciones con las nuevas tablas de gestión
    work_plan = db.relationship('WorkPlan', backref='student', uselist=False)
    logs = db.relationship('DailyLog', backref='student', lazy=True)
    attendance = db.relationship('AttendanceLog', backref='student', lazy=True)

class WorkPlan(db.Model):
    """El Plan de Trabajo del Estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    title = db.Column(db.String(200))
    general_objective = db.Column(db.Text)
    schedule = db.Column(db.Text) # Cronograma en texto
    status = db.Column(db.String(20), default='BORRADOR') # BORRADOR, ENVIADO, APROBADO

class DailyLog(db.Model):
    """Bitácora Diaria"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    date = db.Column(db.Date, default=datetime.date.today)
    activity = db.Column(db.Text)
    hours = db.Column(db.Float)
    observations = db.Column(db.Text)

class AttendanceLog(db.Model):
    """Control de Asistencia"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    date = db.Column(db.Date, default=datetime.date.today)
    entry_time = db.Column(db.String(10)) # Ej: "08:00"
    exit_time = db.Column(db.String(10))  # Ej: "12:00"

# --- 3. CARGA DE DATOS INICIALES ---
CAPACIDAD = {"II": 5, "III": 3, "IV": 2}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# LISTA COMPLETA DE TUTORES
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

# Inicializador de la App
with app.app_context():
    db.create_all()
    
    # 1. Cargar Tutores si la tabla está vacía
    if Tutor.query.count() == 0:
        print("Cargando lista maestra de docentes...")
        for d in DATOS_INICIALES:
            nuevo = Tutor(name=d['nombre'], phone=d['tel'], email=d['email'])
            db.session.add(nuevo)
        db.session.commit()
    
    # 2. Crear Usuario ADMIN si no existe
    if not User.query.filter_by(username='admin').first():
        print("Creando usuario Administrador...")
        admin = User(username='admin', password='123', role='admin')
        db.session.add(admin)
        db.session.commit()
    
    # 3. Crear Usuario DOCENTE si no existe
    if not User.query.filter_by(username='docente').first():
        print("Creando usuario Docente de Materia...")
        docente = User(username='docente', password='123', role='docente')
        db.session.add(docente)
        db.session.commit()

# --- 4. RUTAS PÚBLICAS Y API ---

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
        # Director Odin tiene capacidad 0 (o ilimitada según lógica, aquí 0 cupos directos)
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
        return jsonify({"error": "¡Ups! Cupo lleno."}), 409

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

# --- 5. RUTAS DE AUTENTICACIÓN (LOGIN) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'docente':
                return redirect(url_for('docente_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            # En un caso real usar flash messages, aquí simple redirect
            return render_template('login.html') 
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- 6. RUTAS ESTUDIANTE (DASHBOARD Y GESTIÓN) ---

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student': return redirect(url_for('index'))
    profile = current_user.student_profile
    return render_template('student_dashboard.html', profile=profile)

@app.route('/student/save_plan', methods=['POST'])
@login_required
def save_plan():
    p = current_user.student_profile
    if not p: return "Error perfil", 400
    
    if not p.work_plan:
        plan = WorkPlan(student_id=p.id)
        db.session.add(plan)
    else:
        plan = p.work_plan
    
    plan.title = request.form['title']
    plan.general_objective = request.form['general_objective']
    plan.schedule = request.form['schedule']
    plan.status = 'ENVIADO'
    db.session.commit()
    return redirect(url_for('student_dashboard'))

@app.route('/student/add_log', methods=['POST'])
@login_required
def add_log():
    p = current_user.student_profile
    if not p: return "Error perfil", 400

    date_obj = datetime.datetime.strptime(request.form['date'], '%Y-%m-%d').date()
    new_log = DailyLog(
        student_id=p.id, 
        date=date_obj, 
        activity=request.form['activity'], 
        hours=float(request.form['hours'])
    )
    db.session.add(new_log)
    db.session.commit()
    return redirect(url_for('student_dashboard'))

@app.route('/student/add_attendance', methods=['POST'])
@login_required
def add_attendance():
    p = current_user.student_profile
    if not p: return "Error perfil", 400

    date_obj = datetime.datetime.strptime(request.form['date'], '%Y-%m-%d').date()
    new_att = AttendanceLog(
        student_id=p.id, 
        date=date_obj, 
        entry_time=request.form['entry'], 
        exit_time=request.form['exit']
    )
    db.session.add(new_att)
    db.session.commit()
    return redirect(url_for('student_dashboard'))

# --- NUEVO: REPORTE FINAL (PORTAFOLIO) ---

@app.route('/student/descargar_portafolio')
@login_required
def descargar_portafolio():
    if current_user.role != 'student': return "Error", 403
    filename = generar_reporte_academico(current_user.student_profile)
    return send_file(os.path.join(os.getcwd(), filename), as_attachment=True)

# --- 7. RUTAS DOCENTE DE MATERIA ---

@app.route('/docente/dashboard')
@login_required
def docente_dashboard():
    if current_user.role != 'docente': return "Acceso Denegado"
    # Mostrar todos los estudiantes activos
    estudiantes = StudentProfile.query.filter_by(status='ACTIVO').all()
    return render_template('docente_dashboard.html', estudiantes=estudiantes)

@app.route('/docente/ver/<int:student_id>')
@login_required
def docente_ver_estudiante(student_id):
    if current_user.role != 'docente': return "Acceso Denegado"
    estudiante = StudentProfile.query.get(student_id)
    return render_template('docente_detail.html', e=estudiante)

# --- 8. RUTAS ADMIN (DIRECTOR) ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': return redirect(url_for('index'))
    
    pendientes = StudentProfile.query.filter_by(status='PENDIENTE').all()
    activos = StudentProfile.query.filter_by(status='ACTIVO').all()
    
    return render_template('admin_dashboard.html', pendientes=pendientes, activos=activos)

@app.route('/admin/approve/<int:student_id>', methods=['POST'])
@login_required
def approve_student(student_id):
    if current_user.role != 'admin': return "Acceso Denegado"
    
    drive_url = request.form.get('drive_url')
    student = StudentProfile.query.get(student_id)
    
    if student:
        # Verificar que no exista usuario ya
        if not User.query.filter_by(username=student.registro).first():
            # Crear Usuario (User: Registro, Pass: Carnet)
            new_user = User(username=student.registro, password=student.carnet, role='student')
            db.session.add(new_user)
            db.session.commit() # Commit para obtener el ID
            
            # Vincular y Activar
            student.user_id = new_user.id
            student.status = 'ACTIVO'
            student.drive_folder_url = drive_url
            db.session.commit()
            
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset-total')
def reset_db():
    # Solo para emergencias - Pone todos los cupos en 0
    tutors = Tutor.query.all()
    for t in tutors:
        t.taken_II = 0
        t.taken_III = 0
        t.taken_IV = 0
    db.session.commit()
    return "<h1>Reset de Cupos Exitoso</h1><a href='/'>Volver</a>"

# --- 9. GENERADOR DE PDF ---

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
    
    # Tabla de datos
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

def generar_reporte_academico(p):
    """Genera el Portafolio con Plan, Bitácora y Asistencia"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Portafolio Académico de Practicum", 0, 1, 'C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Estudiante: {p.full_name} | Registro: {p.registro}", 0, 1, 'C')
    pdf.ln(10)
    
    # 1. Plan de Trabajo
    pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "1. Plan de Trabajo", 0, 1)
    pdf.set_font("Arial", size=11)
    if p.work_plan:
        pdf.multi_cell(0, 8, f"Título: {p.work_plan.title}")
        pdf.multi_cell(0, 8, f"Objetivo: {p.work_plan.general_objective}")
    else:
        pdf.cell(0, 10, "No registrado.", 0, 1)
    pdf.ln(10)

    # 2. Bitácora
    pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "2. Bitácora de Actividades (Anexo II)", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "Fecha", 1, 0, 'C', True)
    pdf.cell(130, 10, "Actividad", 1, 0, 'C', True)
    pdf.cell(30, 10, "Horas", 1, 1, 'C', True)
    pdf.set_font("Arial", size=10)
    total_horas = 0
    for log in p.logs:
        pdf.cell(30, 10, str(log.date), 1)
        pdf.cell(130, 10, str(log.activity)[:60], 1) # Cortar texto si es muy largo
        pdf.cell(30, 10, str(log.hours), 1, 1, 'C')
        total_horas += log.hours
    pdf.cell(160, 10, "TOTAL HORAS ACUMULADAS", 1, 0, 'R')
    pdf.cell(30, 10, str(total_horas), 1, 1, 'C')
    pdf.ln(10)

    # 3. Asistencia
    pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "3. Control de Asistencia (Anexo I)", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230, 230, 230)
    pdf.cell(60, 10, "Fecha", 1, 0, 'C', True)
    pdf.cell(60, 10, "Entrada", 1, 0, 'C', True)
    pdf.cell(60, 10, "Salida", 1, 1, 'C', True)
    pdf.set_font("Arial", size=10)
    for att in p.attendance:
        pdf.cell(60, 10, str(att.date), 1, 0, 'C')
        pdf.cell(60, 10, str(att.entry_time), 1, 0, 'C')
        pdf.cell(60, 10, str(att.exit_time), 1, 1, 'C')

    filename = f"reporte_{p.registro}.pdf"
    pdf.output(filename)
    return filename

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
