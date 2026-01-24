import os
import datetime
import io
import csv
from flask import Flask, jsonify, request, send_file, render_template, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
# LIBRERÍA DE SEGURIDAD
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# 1. CONFIGURACIÓN
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_uagrm_politica_desarrollo')

# Configuración de Base de Datos
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local_tutores.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 2. MODELOS DE BASE DE DATOS (NUEVA ARQUITECTURA) ---

class User(UserMixin, db.Model):
    """Sistema de Usuarios"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True) 
    password_hash = db.Column(db.String(256)) 
    role = db.Column(db.String(20)) # 'admin', 'student', 'docente'
    display_name = db.Column(db.String(100))
    
    # RELACIONES
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
    """Tutores de Tesis (Externos/Guías)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    taken_II = db.Column(db.Integer, default=0)
    taken_III = db.Column(db.Integer, default=0)
    taken_IV = db.Column(db.Integer, default=0)
    students = db.relationship('StudentProfile', backref='tutor', lazy=True, foreign_keys='StudentProfile.tutor_id')

class StudentProfile(db.Model):
    """Perfil Académico del Estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    full_name = db.Column(db.String(100))
    registro = db.Column(db.String(20))
    carnet = db.Column(db.String(20))
    practicum_level = db.Column(db.String(5))
    
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutor.id')) 
    status = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, ACTIVO
    drive_folder_url = db.Column(db.String(300))
    
    # RELACIONES
    documents = db.relationship('StudentDocument', backref='student', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)
    logs = db.relationship('TimeLog', backref='student', lazy=True)
    attendance = db.relationship('AttendanceLog', backref='student', lazy=True)

    @property
    def total_hours(self):
        return sum(log.hours for log in self.logs)

    @property
    def administrative_status(self):
        required = ['Boleta Inscripción', 'CV', 'Fotocopia Carnet', 'Formulario Datos']
        docs = {d.doc_type: d.status for d in self.documents}
        for r in required:
            if docs.get(r) != 'VALIDADO':
                return "PENDIENTE"
        return "OK"

class StudentDocument(db.Model):
    """Módulo Administrativo: Papeles y Requisitos"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    doc_type = db.Column(db.String(50)) # 'Boleta', 'CV', 'Carnet', 'Formulario'
    status = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, REVISION, VALIDADO, RECHAZADO
    drive_link = db.Column(db.String(300)) # Link específico si el alumno quiere ponerlo
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Assignment(db.Model):
    """Módulo Académico: El 'Molde' de la tarea creado por el Docente"""
    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    title = db.Column(db.String(200)) # Ej: "Primer Avance: Perfil"
    description = db.Column(db.Text)
    order = db.Column(db.Integer) # 1, 2, 3...
    deadline = db.Column(db.Date, nullable=True) # FECHA LIMITE (NUEVO)
    
    submissions = db.relationship('Submission', backref='assignment', lazy=True)

class Submission(db.Model):
    """Módulo Académico: La entrega del estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'))
    
    content = db.Column(db.Text) # Texto o Link al documento
    status = db.Column(db.String(20), default='BORRADOR') # BORRADOR, EN_REVISION, OBSERVADO, APROBADO
    feedback = db.Column(db.Text) # Correcciones del docente
    
    submitted_at = db.Column(db.Date)
    approved_at = db.Column(db.Date)

    @property
    def days_waiting(self):
        if self.status == 'EN_REVISION' and self.submitted_at:
            delta = datetime.date.today() - self.submitted_at
            return delta.days
        return 0

class TimeLog(db.Model):
    """Módulo Cronómetro: Bitácora de Horas"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    date = db.Column(db.Date, default=datetime.date.today)
    
    activity_type = db.Column(db.String(50)) 
    activity_detail = db.Column(db.Text)
    hours = db.Column(db.Float)
    
    is_validated = db.Column(db.Boolean, default=False) 

class AttendanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    date = db.Column(db.Date, default=datetime.date.today)
    entry_time = db.Column(db.String(10))
    exit_time = db.Column(db.String(10))

# --- 3. DATOS MAESTROS Y CARGA ---
CAPACIDAD = {"II": 5, "III": 3, "IV": 2}
DOCS_REQUERIDOS = ['Boleta Inscripción', 'CV', 'Fotocopia Carnet', 'Formulario Datos']

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- INICIALIZADOR ---
with app.app_context():
    db.create_all()
    
    # Carga Tutores
    if Tutor.query.count() == 0:
        for d in DATOS_TUTORES:
            db.session.add(Tutor(name=d['nombre'], phone=d['tel'], email=d['email']))
        db.session.commit()
    
    # Carga Admin
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin', display_name="Dirección de Carrera")
        admin.set_password('123') 
        db.session.add(admin)
    
    # Carga Docentes
    for dm in DOCENTES_MATERIA_DATA:
        doc = User.query.filter_by(username=dm['user']).first()
        if not doc:
            doc = User(username=dm['user'], role='docente', display_name=dm['name'])
            doc.set_password(dm['pass']) 
            db.session.add(doc)
            db.session.commit() 
            
            # TAREAS POR DEFECTO (EL DOCENTE DEBE EDITARLAS LUEGO)
            tareas = [
                "1. Perfil de Proyecto", 
                "2. Marco Teórico y Metodológico", 
                "3. Trabajo de Campo y Análisis",
                "4. Informe Final y Artículo Científico"
            ]
            for idx, tarea in enumerate(tareas):
                if not Assignment.query.filter_by(docente_id=doc.id, title=tarea).first():
                    # Por defecto sin fecha límite, el docente la pone
                    db.session.add(Assignment(docente_id=doc.id, title=tarea, order=idx+1, description="Pendiente de configuración por el docente."))
            db.session.commit()

# --- RUTAS PÚBLICAS ---

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
    
    # Crear Perfil PENDIENTE
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
    
    # Inicializar Documentos
    for doc_name in DOCS_REQUERIDOS:
        db.session.add(StudentDocument(student_id=est.id, doc_type=doc_name))
    db.session.commit()
    
    try:
        docente_obj = User.query.get(int(docente_id))
        docente_nombre = docente_obj.display_name if docente_obj else ""
        pdf_file = generar_carta_pdf(est.full_name, est.registro, est.carnet, level, tutor.name, docente_nombre)
        return jsonify({
            "mensaje": "Solicitud registrada.",
            "pdf_url": f"/descargar/{pdf_file}"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/descargar/<filename>')
def descargar_archivo(filename):
    path = os.path.join(os.getcwd(), filename)
    return send_file(path, as_attachment=True)

# --- RUTAS AUTENTICACIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin': return redirect(url_for('admin_dashboard'))
            elif user.role == 'docente': return redirect(url_for('docente_dashboard'))
            else: return redirect(url_for('student_dashboard'))
        else:
            return render_template('login.html', error=True) 
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- MÓDULO ESTUDIANTE (REPARADO Y CON LÓGICA SEMÁFORO) ---

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student': return redirect(url_for('index'))
    profile = current_user.student_profile
    
    # 1. AUTO-GENERAR DOCUMENTOS (Si faltan)
    if not profile.documents:
        docs_requeridos = ['Boleta Inscripción', 'CV', 'Fotocopia Carnet', 'Formulario Datos']
        for doc_name in docs_requeridos:
            db.session.add(StudentDocument(student_id=profile.id, doc_type=doc_name))
        db.session.commit()

    # 2. ASEGURAR TAREAS (Si el docente ya las tiene configuradas)
    if profile.docente_id:
        tareas_docente = Assignment.query.filter_by(docente_id=profile.docente_id).all()
        # Si el docente no tiene tareas, se crean las DEFAULT
        if not tareas_docente:
             defaults = ["1. Perfil de Proyecto", "2. Marco Teórico", "3. Trabajo de Campo", "4. Informe Final"]
             for idx, titulo in enumerate(defaults):
                db.session.add(Assignment(docente_id=profile.docente_id, title=titulo, order=idx+1, description="Por configurar..."))
             db.session.commit()
        
        # Vincular estudiante a las tareas
        tareas_actuales = Assignment.query.filter_by(docente_id=profile.docente_id).all()
        for t in tareas_actuales:
            if not Submission.query.filter_by(student_id=profile.id, assignment_id=t.id).first():
                db.session.add(Submission(student_id=profile.id, assignment_id=t.id))
        db.session.commit()

    submissions = Submission.query.filter_by(student_id=profile.id).join(Assignment).order_by(Assignment.order).all()
    return render_template('student_dashboard.html', profile=profile, submissions=submissions)

@app.route('/student/upload_doc', methods=['POST'])
@login_required
def student_upload_doc():
    """El estudiante confirma subida de docs"""
    doc_id = request.form.get('doc_id')
    doc = StudentDocument.query.get(doc_id)
    if doc and doc.student_id == current_user.student_profile.id:
        doc.status = 'REVISION' 
        db.session.commit()
    return redirect(url_for('student_dashboard'))

@app.route('/student/submit_assignment', methods=['POST'])
@login_required
def student_submit_assignment():
    """Entrega iterativa con Bloqueo (Semáforo)"""
    sub_id = request.form.get('submission_id')
    content = request.form.get('content')
    
    sub = Submission.query.get(sub_id)
    if sub and sub.student_id == current_user.student_profile.id:
        
        # LÓGICA SEMÁFORO: Verificar si la anterior está aprobada
        prev_assign = Assignment.query.filter_by(docente_id=sub.assignment.docente_id, order=sub.assignment.order - 1).first()
        if prev_assign:
            prev_sub = Submission.query.filter_by(student_id=current_user.student_profile.id, assignment_id=prev_assign.id).first()
            if not prev_sub or prev_sub.status != 'APROBADO':
                flash("⛔ Error: Debes tener APROBADO el avance anterior para entregar este.")
                return redirect(url_for('student_dashboard'))

        sub.content = content
        sub.status = 'EN_REVISION'
        sub.submitted_at = datetime.date.today()
        db.session.commit()
    return redirect(url_for('student_dashboard'))

@app.route('/student/add_timelog', methods=['POST'])
@login_required
def student_add_timelog():
    p = current_user.student_profile
    new_log = TimeLog(
        student_id=p.id, 
        date=datetime.datetime.strptime(request.form['date'], '%Y-%m-%d').date(), 
        activity_type=request.form['activity_type'],
        activity_detail=request.form['activity_detail'], 
        hours=float(request.form['hours'])
    )
    db.session.add(new_log)
    db.session.commit()
    return redirect(url_for('student_dashboard'))

# --- MÓDULO DOCENTE (CONFIGURACIÓN Y REVISIÓN) ---

@app.route('/docente/dashboard')
@login_required
def docente_dashboard():
    if current_user.role != 'docente': return "Acceso Denegado"
    
    # Obtener alumnos
    mis_estudiantes = StudentProfile.query.filter_by(docente_id=current_user.id, status='ACTIVO').all()
    
    # Obtener Tareas para configuración
    mis_tareas = Assignment.query.filter_by(docente_id=current_user.id).order_by(Assignment.order).all()
    
    return render_template('docente_dashboard.html', 
                           estudiantes=mis_estudiantes, 
                           docente_nombre=current_user.display_name,
                           tareas=mis_tareas) # Pasamos las tareas para que las edite

@app.route('/docente/config_assignment', methods=['POST'])
@login_required
def docente_config_assignment():
    """NUEVA RUTA: El docente configura fechas y descripciones"""
    if current_user.role != 'docente': return "Acceso Denegado"
    
    assign_id = request.form.get('assignment_id')
    description = request.form.get('description')
    deadline_str = request.form.get('deadline') # YYYY-MM-DD
    
    tarea = Assignment.query.get(assign_id)
    if tarea and tarea.docente_id == current_user.id:
        tarea.description = description
        if deadline_str:
            tarea.deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d').date()
        db.session.commit()
        
    return redirect(url_for('docente_dashboard'))

@app.route('/docente/ver/<int:student_id>')
@login_required
def docente_ver_estudiante(student_id):
    if current_user.role != 'docente': return "Acceso Denegado"
    estudiante = StudentProfile.query.get(student_id)
    if estudiante.docente_id != current_user.id: return "Acceso Restringido", 403
    
    submissions = Submission.query.filter_by(student_id=estudiante.id).join(Assignment).order_by(Assignment.order).all()
    return render_template('docente_detail.html', e=estudiante, submissions=submissions)

@app.route('/docente/grade_submission', methods=['POST'])
@login_required
def docente_grade_submission():
    sub_id = request.form.get('submission_id')
    action = request.form.get('action')
    feedback = request.form.get('feedback')
    
    sub = Submission.query.get(sub_id)
    if sub.assignment.docente_id != current_user.id: return "Error", 403
    
    if action == 'approve':
        sub.status = 'APROBADO'
        sub.approved_at = datetime.date.today()
        sub.feedback = feedback
    else:
        sub.status = 'OBSERVADO'
        sub.feedback = feedback
        
    db.session.commit()
    return redirect(url_for('docente_ver_estudiante', student_id=sub.student_id))

@app.route('/docente/validate_hours', methods=['POST'])
@login_required
def docente_validate_hours():
    student_id = request.form.get('student_id')
    logs = TimeLog.query.filter_by(student_id=student_id).all()
    for log in logs:
        log.is_validated = True
    db.session.commit()
    return redirect(url_for('docente_ver_estudiante', student_id=student_id))

# --- MÓDULO ADMIN (DIRECTOR) ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': return redirect(url_for('index'))
    
    docs_pendientes = StudentDocument.query.filter_by(status='REVISION').all()
    pendientes_registro = StudentProfile.query.filter_by(status='PENDIENTE').all()
    # AGREGAR ESTA LÍNEA PARA QUE APAREZCAN LOS ACTIVOS
    estudiantes_activos = StudentProfile.query.filter_by(status='ACTIVO').all()
    
    return render_template('admin_dashboard.html', 
                           docs_pendientes=docs_pendientes, 
                           pendientes_registro=pendientes_registro,
                           activos=estudiantes_activos) # PASAR A LA PLANTILLA

@app.route('/admin/validate_doc', methods=['POST'])
@login_required
def admin_validate_doc():
    doc_id = request.form.get('doc_id')
    action = request.form.get('action') 
    
    doc = StudentDocument.query.get(doc_id)
    if action == 'validate':
        doc.status = 'VALIDADO'
    else:
        doc.status = 'RECHAZADO'
        
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve/<int:student_id>', methods=['POST'])
@login_required
def approve_student(student_id):
    if current_user.role != 'admin': return "Acceso Denegado"
    
    drive_url = request.form.get('drive_url')
    student = StudentProfile.query.get(student_id)
    
    if student:
        if not User.query.filter_by(username=student.registro).first():
            new_user = User(username=student.registro, role='student')
            new_user.set_password(student.carnet) 
            db.session.add(new_user)
            db.session.commit() 
            
            student.user_id = new_user.id
            student.status = 'ACTIVO'
            student.drive_folder_url = drive_url # AQUÍ SE GUARDA EL LINK DEL DRIVE
            db.session.commit()
            
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/report_excel')
@login_required
def admin_report_excel():
    if current_user.role != 'admin': return "Acceso Denegado"
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Registro', 'Nombre', 'Nivel', 'Tutor', 'Docente', 'Horas Totales', 'Estado Docs'])
    students = StudentProfile.query.filter_by(status='ACTIVO').all()
    for s in students:
        tutor_name = s.tutor.name if s.tutor else "Sin Asignar"
        docente_name = s.assigned_docente.display_name if s.assigned_docente else "Sin Asignar"
        writer.writerow([s.registro, s.full_name, s.practicum_level, tutor_name, docente_name, s.total_hours, s.administrative_status])
    output.seek(0)
    return make_response(output.getvalue(), 200, {
        'Content-Disposition': 'attachment; filename=reporte_general.csv',
        'Content-Type': 'text/csv'
    })

# --- RESET COMPLETO (OBLIGATORIO) ---
@app.route('/peligro/reset-completo')
def reset_completo():
    db.drop_all()
    db.create_all()
    
    if Tutor.query.count() == 0:
        for d in DATOS_TUTORES:
            db.session.add(Tutor(name=d['nombre'], phone=d['tel'], email=d['email']))
    
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin', display_name="Dirección de Carrera")
        admin.set_password('123') 
        db.session.add(admin)
    
    for dm in DOCENTES_MATERIA_DATA:
        doc = User(username=dm['user'], role='docente', display_name=dm['name'])
        doc.set_password(dm['pass'])
        db.session.add(doc)
        db.session.commit()
        
        # Tareas por defecto
        tareas = ["1. Perfil", "2. Marco Teórico", "3. Campo", "4. Informe Final"]
        for idx, t in enumerate(tareas):
             db.session.add(Assignment(docente_id=doc.id, title=t, order=idx+1, description="Por configurar..."))
            
    db.session.commit()
    return "<h1>Sistema Reconstruido con Nueva Arquitectura (Assignments + Docs)</h1>"

# --- PDF GENERATOR ---
def generar_carta_pdf(nombre, registro, carnet, nivel, nombre_tutor, nombre_docente_materia):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # --- FECHA EN ESPAÑOL MANUAL ---
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    now = datetime.datetime.now()
    fecha = f"{now.day} de {meses[now.month - 1]} de {now.year}"
    # -----------------------------------

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
    pdf.cell(0, 10, "Portafolio Académico", 0, 1, 'C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Estudiante: {p.full_name} | Horas: {p.total_hours}", 0, 1)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "Bitácora de Actividades", 0, 1)
    pdf.set_font("Arial", size=10)
    for log in p.logs:
        pdf.cell(0, 10, f"{log.date} - {log.activity_type}: {log.hours}hrs ({'Validado' if log.is_validated else 'Pendiente'})", 0, 1)
    filename = f"reporte_{p.registro}.pdf"
    pdf.output(filename)
    return filename

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
