import os
import datetime
from flask import Flask, jsonify, request, send_file, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
# LIBRERÍA DE SEGURIDAD (HASHING)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# 1. CONFIGURACIÓN SEGURA
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_uagrm_politica_desarrollo')

# Configuración de Base de Datos (Render vs Local)
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
    """Sistema de Usuarios"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True) 
    password_hash = db.Column(db.String(256)) # Guardamos el HASH
    role = db.Column(db.String(20)) 
    display_name = db.Column(db.String(100))
    
    # RELACIONES CORREGIDAS
    student_profile = db.relationship(
        'StudentProfile', 
        backref='user_account', 
        uselist=False, 
        foreign_keys='StudentProfile.user_id'
    )
    
    assigned_students = db.relationship(
        'StudentProfile', 
        backref='assigned_docente', 
        lazy=True, 
        foreign_keys='StudentProfile.docente_id'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Tutor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    taken_II = db.Column(db.Integer, default=0)
    taken_III = db.Column(db.Integer, default=0)
    taken_IV = db.Column(db.Integer, default=0)
    students = db.relationship('StudentProfile', backref='tutor', lazy=True, foreign_keys='StudentProfile.tutor_id')

class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    full_name = db.Column(db.String(100))
    registro = db.Column(db.String(20))
    carnet = db.Column(db.String(20))
    practicum_level = db.Column(db.String(5))
    
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutor.id')) 
    status = db.Column(db.String(20), default='PENDIENTE')
    drive_folder_url = db.Column(db.String(300))
    
    work_plan = db.relationship('WorkPlan', backref='student', uselist=False)
    logs = db.relationship('DailyLog', backref='student', lazy=True)
    attendance = db.relationship('AttendanceLog', backref='student', lazy=True)

class WorkPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    
    # Contenido del Plan
    title = db.Column(db.String(200))
    general_objective = db.Column(db.Text)
    schedule = db.Column(db.Text)
    
    # --- NUEVO MOTOR DE REVISIÓN ---
    status = db.Column(db.String(20), default='BORRADOR') # BORRADOR, EN_REVISION, OBSERVADO, APROBADO
    
    teacher_feedback = db.Column(db.Text) # Comentarios del docente
    submitted_at = db.Column(db.Date)     # Fecha de envío (para calcular retraso)
    approved_at = db.Column(db.Date)      # Fecha de aprobación

    @property
    def days_waiting(self):
        """Calcula días esperando revisión"""
        if self.status == 'EN_REVISION' and self.submitted_at:
            delta = datetime.date.today() - self.submitted_at
            return delta.days
        return 0

class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    date = db.Column(db.Date, default=datetime.date.today)
    activity = db.Column(db.Text)
    hours = db.Column(db.Float)
    observations = db.Column(db.Text)

class AttendanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    date = db.Column(db.Date, default=datetime.date.today)
    entry_time = db.Column(db.String(10))
    exit_time = db.Column(db.String(10))

# --- 3. CARGA DE DATOS INICIALES ---
CAPACIDAD = {"II": 5, "III": 3, "IV": 2}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

DATOS_TUTORES = [
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

DOCENTES_MATERIA_DATA = [
    {"user": "p2_manana", "pass": "123", "name": "Practicum II - Turno Mañana (A)"},
    {"user": "p2_noche",  "pass": "123", "name": "Practicum II - Turno Noche (B)"},
    {"user": "p3_manana", "pass": "123", "name": "Practicum III - Turno Mañana (A)"},
    {"user": "p3_noche",  "pass": "123", "name": "Practicum III - Turno Noche (B)"},
    {"user": "p4_manana", "pass": "123", "name": "Practicum IV - Turno Mañana (A)"},
    {"user": "p4_noche",  "pass": "123", "name": "Practicum IV - Turno Noche (B)"}
]

# --- INICIALIZADOR SIMPLE (PARA BD LIMPIA) ---
with app.app_context():
    # 1. Crear tablas
    db.create_all()
    
    # 2. CARGA DE DATOS INICIALES
    
    # Cargar Tutores
    if Tutor.query.count() == 0:
        print("Cargando lista maestra de tutores...")
        for d in DATOS_TUTORES:
            db.session.add(Tutor(name=d['nombre'], phone=d['tel'], email=d['email']))
        db.session.commit()
    
    # Cargar Admin
    if not User.query.filter_by(username='admin').first():
        print("Creando Admin...")
        admin = User(username='admin', role='admin', display_name="Dirección de Carrera")
        admin.set_password('123') 
        db.session.add(admin)
    
    # Cargar Docentes
    for dm in DOCENTES_MATERIA_DATA:
        if not User.query.filter_by(username=dm['user']).first():
            print(f"Creando docente: {dm['name']}")
            doc = User(username=dm['user'], role='docente', display_name=dm['name'])
            doc.set_password(dm['pass']) 
            db.session.add(doc)
            
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

@app.route('/api/docentes_materia', methods=['GET'])
def get_docentes_materia():
    docentes = User.query.filter_by(role='docente').all()
    lista = []
    for d in docentes:
        lista.append({
            "id": d.id,
            "name": d.display_name
        })
    return jsonify(lista)

@app.route('/api/solicitar', methods=['POST'])
def solicitar_tutor():
    data = request.json
    tutor_id = data.get('tutor_id')
    docente_id = data.get('docente_id') 
    level = data.get('nivel')
    
    tutor = Tutor.query.get(tutor_id)
    if not tutor: return jsonify({"error": "Tutor no encontrado"}), 404
    
    if not docente_id: return jsonify({"error": "Debes seleccionar tu turno/docente de materia"}), 400

    campo_cupo = f"taken_{level}"
    tomados = getattr(tutor, campo_cupo)
    maximo = 0 if "Odin Rodríguez Mercado" in tutor.name else CAPACIDAD[level]

    if tomados >= maximo:
        return jsonify({"error": "¡Ups! Cupo lleno."}), 409

    setattr(tutor, campo_cupo, tomados + 1)
    
    est = StudentProfile(
        full_name=data.get('nombre'),
        registro=data.get('registro'),
        carnet=data.get('carnet'),
        practicum_level=level,
        tutor_id=tutor.id,
        docente_id=int(docente_id), 
        status='PENDIENTE'
    )
    db.session.add(est)
    db.session.commit()
    
    try:
        docente_obj = User.query.get(int(docente_id))
        docente_nombre = docente_obj.display_name if docente_obj else ""
        
        pdf_file = generar_carta_pdf(est.full_name, est.registro, est.carnet, level, tutor.name, docente_nombre)
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

# --- 5. RUTAS DE AUTENTICACIÓN SEGURA ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'docente':
                return redirect(url_for('docente_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            return render_template('login.html', error=True) 
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- 6. RUTAS ESTUDIANTE (CON WORKFLOW Y BLOQUEO) ---

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
    
    # BLOQUEO DE EDICIÓN: Si ya está enviado o aprobado, no dejar editar
    if plan.status in ['EN_REVISION', 'APROBADO']:
         return "El plan está bajo revisión o aprobado. No puedes editarlo.", 403

    plan.title = request.form['title']
    plan.general_objective = request.form['general_objective']
    plan.schedule = request.form['schedule']
    # El estado sigue siendo BORRADOR hasta que envíe explícitamente
    
    db.session.commit()
    return redirect(url_for('student_dashboard'))

@app.route('/student/submit_plan', methods=['POST'])
@login_required
def submit_plan():
    """ACCIÓN: Estudiante envía a revisión (cambia estado y fecha)"""
    p = current_user.student_profile
    if p.work_plan:
        p.work_plan.status = 'EN_REVISION'
        p.work_plan.submitted_at = datetime.date.today()
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

@app.route('/student/descargar_portafolio')
@login_required
def descargar_portafolio():
    if current_user.role != 'student': return "Error", 403
    filename = generar_reporte_academico(current_user.student_profile)
    return send_file(os.path.join(os.getcwd(), filename), as_attachment=True)

# --- 7. RUTAS DOCENTE (CON REVISIÓN Y FEEDBACK) ---

@app.route('/docente/dashboard')
@login_required
def docente_dashboard():
    if current_user.role != 'docente': return "Acceso Denegado"
    
    mis_estudiantes = StudentProfile.query.filter_by(
        docente_id=current_user.id, 
        status='ACTIVO'
    ).all()
    
    return render_template('docente_dashboard.html', estudiantes=mis_estudiantes, docente_nombre=current_user.display_name)

@app.route('/docente/ver/<int:student_id>')
@login_required
def docente_ver_estudiante(student_id):
    if current_user.role != 'docente': return "Acceso Denegado"
    estudiante = StudentProfile.query.get(student_id)
    
    if estudiante.docente_id != current_user.id:
        return "<h1>Acceso Restringido: Este estudiante no está en su turno.</h1>", 403
        
    return render_template('docente_detail.html', e=estudiante)

@app.route('/docente/review_plan', methods=['POST'])
@login_required
def review_plan():
    """ACCIÓN: Docente aprueba o rechaza el plan"""
    if current_user.role != 'docente': return "Acceso Denegado"
    
    plan_id = request.form.get('plan_id')
    action = request.form.get('action') # 'approve' o 'reject'
    feedback = request.form.get('feedback')
    
    plan = WorkPlan.query.get(plan_id)
    
    if action == 'approve':
        plan.status = 'APROBADO'
        plan.approved_at = datetime.date.today()
        plan.teacher_feedback = "Plan Aprobado. " + feedback
    elif action == 'reject':
        plan.status = 'OBSERVADO' # Regresa al estudiante para correcciones
        plan.teacher_feedback = feedback
    
    db.session.commit()
    return redirect(url_for('docente_ver_estudiante', student_id=plan.student.id))

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
        if not User.query.filter_by(username=student.registro).first():
            # CREACIÓN SEGURA DE USUARIO ESTUDIANTE
            new_user = User(username=student.registro, role='student')
            new_user.set_password(student.carnet) 
            db.session.add(new_user)
            db.session.commit() 
            
            student.user_id = new_user.id
            student.status = 'ACTIVO'
            student.drive_folder_url = drive_url
            db.session.commit()
            
    return redirect(url_for('admin_dashboard'))

# --- 9. GENERADORES PDF ---

def generar_carta_pdf(nombre, registro, carnet, nivel, nombre_tutor, nombre_docente_materia):
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
    pdf.multi_cell(0, 8, "Mediante la presente, solicito formalmente la asignación de tutoría. A continuación detallo mis datos y el docente seleccionado:"); pdf.ln(10)
    
    # Tabla de datos
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', size=10)
    w_label = 60; w_data = 130; h_row = 10
    
    pdf.cell(w_label, h_row, "NOMBRE:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre).upper(), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "REGISTRO:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(registro), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "CI:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(carnet), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "MATERIA:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, f"PRACTICUM {nivel}", 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "DOCENTE MATERIA:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre_docente_materia), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "TUTOR TESIS:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre_tutor).upper(), 1, 1, 'L')
    
    pdf.ln(20); pdf.multi_cell(0, 8, "Sin otro particular, saludo a usted atentamente."); pdf.ln(30)
    
    pdf.cell(0, 5, txt="__________________________", ln=1, align='C'); pdf.cell(0, 5, txt=f"{nombre}", ln=1, align='C')
    
    filename = f"solicitud_{registro}_{nivel}.pdf"
    pdf.output(filename)
    return filename

def generar_reporte_academico(p):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Portafolio Académico de Practicum", 0, 1, 'C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Estudiante: {p.full_name} | Registro: {p.registro}", 0, 1, 'C')
    if p.assigned_docente:
        pdf.cell(0, 10, f"Docente Materia: {p.assigned_docente.display_name}", 0, 1, 'C')
    pdf.ln(10)
    
    # 1. Plan de Trabajo
    pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "1. Plan de Trabajo", 0, 1)
    pdf.set_font("Arial", size=11)
    if p.work_plan:
        pdf.multi_cell(0, 8, f"Título: {p.work_plan.title}")
        pdf.multi_cell(0, 8, f"Objetivo: {p.work_plan.general_objective}")
    else: pdf.cell(0, 10, "No registrado.", 0, 1)
    pdf.ln(10)

    # 2. Bitácora
    pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "2. Bitácora (Anexo II)", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "Fecha", 1, 0, 'C', True); pdf.cell(130, 10, "Actividad", 1, 0, 'C', True); pdf.cell(30, 10, "Horas", 1, 1, 'C', True)
    pdf.set_font("Arial", size=10)
    total = 0
    for log in p.logs:
        pdf.cell(30, 10, str(log.date), 1); pdf.cell(130, 10, str(log.activity)[:60], 1); pdf.cell(30, 10, str(log.hours), 1, 1, 'C')
        total += log.hours
    pdf.cell(160, 10, "TOTAL", 1, 0, 'R'); pdf.cell(30, 10, str(total), 1, 1, 'C')
    pdf.ln(10)

    # 3. Asistencia
    pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "3. Asistencia (Anexo I)", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230, 230, 230)
    pdf.cell(60, 10, "Fecha", 1, 0, 'C', True); pdf.cell(60, 10, "Entrada", 1, 0, 'C', True); pdf.cell(60, 10, "Salida", 1, 1, 'C', True)
    pdf.set_font("Arial", size=10)
    for att in p.attendance:
        pdf.cell(60, 10, str(att.date), 1, 0, 'C'); pdf.cell(60, 10, str(att.entry_time), 1, 0, 'C'); pdf.cell(60, 10, str(att.exit_time), 1, 1, 'C')

    filename = f"reporte_{p.registro}.pdf"
    pdf.output(filename)
    return filename

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
