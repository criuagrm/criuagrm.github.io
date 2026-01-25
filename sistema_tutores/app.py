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

# --- 2. MODELOS DE BASE DE DATOS ---

class User(UserMixin, db.Model):
    """Sistema de Usuarios"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True) # Registro o Email
    password_hash = db.Column(db.String(200))
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
    """Base de Datos de Tutores Externos"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    cupos_practicum_2 = db.Column(db.Integer, default=0)
    cupos_practicum_3 = db.Column(db.Integer, default=0)

class StudentProfile(db.Model):
    """Perfil Académico del Estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    docente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Docente Materia

    full_name = db.Column(db.String(100))
    registro = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    practicum_level = db.Column(db.String(5))

    tutor_id = db.Column(db.Integer, db.ForeignKey('tutor.id')) 
    status = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, ACTIVO
    drive_folder_url = db.Column(db.String(300))

    # RELACIONES
    documents = db.relationship('StudentDocument', backref='student', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)
    logs = db.relationship('TimeLog', backref='student', lazy=True)
    
    @property
    def total_hours(self):
        return sum(log.hours for log in self.logs if log.is_validated) or 0
    
    @property
    def meeting_hours_count(self):
        total = sum(log.hours for log in self.logs if log.activity_type == 'Reunión Tutor' and log.is_validated)
        return total

    @property
    def progress_percent(self):
        # Lógica simple: 120 horas = 100%
        p = (self.total_hours / 120) * 100
        return min(p, 100)
    
    def check_completeness(self):
        # Verifica si tiene todo para aprobar
        if self.total_hours >= 120 and self.meeting_hours_count >= 5:
            return "OK"
        return "PENDING"

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
    
    title = db.Column(db.String(200)) # Ej: "Avance 1"
    description = db.Column(db.Text)
    order = db.Column(db.Integer) # 1, 2, 3...
    deadline = db.Column(db.Date, nullable=True) # FECHA LIMITE
    
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade="all, delete-orphan")

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
    def is_late(self):
        if self.assignment.deadline and self.submitted_at:
            return self.submitted_at > self.assignment.deadline
        return False
    
    @property
    def score(self):
        # Sistema cualitativo, pero si necesitas numérico:
        if self.status == 'APROBADO': return 100
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
    """Control de Asistencia a Clases (Opcional)"""
    id = db.Column(db.Integer, primary_key=True)
    # ... por implementar si se requiere

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- DATOS DE PRUEBA ---
DATOS_TUTORES = [
    {"nombre": "Lic. Juan Pérez", "tel": "70012345", "email": "juan@uagrm.edu.bo"},
    {"nombre": "Msc. Maria Lopez", "tel": "70054321", "email": "maria@uagrm.edu.bo"},
    {"nombre": "Dr. Carlos Mendez", "tel": "71122334", "email": "carlos@uagrm.edu.bo"},
]

DOCENTES_MATERIA_DATA = [
    {"user": "docente_ii", "name": "Lic. Mario Gutierrez - Practicum II"},
    {"user": "docente_iii", "name": "Dra. Ana Suarez - Practicum III"},
    {"user": "docente_iv", "name": "Msc. Pedro Castillo - Practicum IV"}
]

DOCS_REQUERIDOS = ['Boleta Inscripción', 'CV', 'Fotocopia Carnet', 'Formulario Datos', 'Evaluación de Tutor']

# --- INICIALIZACIÓN ---
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
            doc.set_password('123')
            db.session.add(doc)
            db.session.commit() 

            # TAREAS POR DEFECTO (AVANCE 1, 2, 3...)
            tareas = ["Avance 1", "Avance 2", "Avance 3", "Avance 4", "Presentación Final"]
            for idx, t in enumerate(tareas):
                if not Assignment.query.filter_by(docente_id=doc.id, title=t).first():
                    db.session.add(Assignment(docente_id=doc.id, title=t, order=idx+1, description="Pendiente de configuración por el docente."))
            db.session.commit()

# --- RUTAS PÚBLICAS ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'student': return redirect(url_for('student_dashboard'))
        if current_user.role == 'docente': return redirect(url_for('docente_dashboard'))
        if current_user.role == 'admin': return redirect(url_for('admin_dashboard'))
    
    # Cargar tutores para el select del registro
    tutores = Tutor.query.all()
    return render_template('login_register.html', tutores=tutores)

@app.route('/api/tutores', methods=['GET'])
def get_tutores():
    tutores = Tutor.query.all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'cupos_ii': t.cupos_practicum_2,
        'cupos_iii': t.cupos_practicum_3
    } for t in tutores])

@app.route('/api/docentes_materia', methods=['GET'])
def get_docentes_materia():
    # CORRECCIÓN DE FILTRADO PARA QUE NO SALGAN TODOS LOS TURNOS MEZCLADOS
    level = request.args.get('level') # Ej: "II", "III", "IV"
    query = User.query.filter_by(role='docente')

    if level:
        # Filtramos si el nombre contiene "Practicum NIVEL " (con espacio para no confundir II con III)
        search_term = f"Practicum {level} "
        search_term_b = f"Practicum {level} -"
        
        docentes = query.filter(
            db.or_(
                User.display_name.contains(search_term),
                User.display_name.contains(search_term_b)
            )
        ).all()
    else:
        docentes = query.all()

    return jsonify([{
        'id': d.id, 
        'name': d.display_name
    } for d in docentes])

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        login_user(user)
        flash('Bienvenido', 'success')
        if user.role == 'student': return redirect(url_for('student_dashboard'))
        if user.role == 'docente': return redirect(url_for('docente_dashboard'))
        if user.role == 'admin': return redirect(url_for('admin_dashboard'))
    
    flash('Credenciales incorrectas', 'error')
    return redirect(url_for('index'))

@app.route('/student/register', methods=['POST'])
def student_register():
    data = request.form
    
    # Validar usuario existente
    if User.query.filter_by(username=data.get('registro')).first():
        flash('El registro ya existe', 'error')
        return redirect(url_for('index'))

    # Crear Usuario
    user = User(username=data.get('registro'), role='student', display_name=data.get('nombre'))
    user.set_password(data.get('password'))
    db.session.add(user)
    db.session.commit()

    # Actualizar Cupos Tutor
    tutor_id = data.get('tutor_id')
    tutor = Tutor.query.get(tutor_id)
    nivel = data.get('nivel') # 'II', 'III'
    
    if nivel == 'II': campo_cupo = 'cupos_practicum_2'
    else: campo_cupo = 'cupos_practicum_3'
    
    tomados = getattr(tutor, campo_cupo)
    setattr(tutor, campo_cupo, tomados + 1)

    # Crear Perfil PENDIENTE
    est = StudentProfile(
        full_name=data.get('nombre'),
        registro=data.get('registro'),
        phone=data.get('celular'),
        email=data.get('email'),
        practicum_level=nivel,
        tutor_id=tutor_id,
        user_id=user.id,
        docente_id=data.get('docente_id')
    )
    db.session.add(est)
    db.session.commit()

    # Inicializar Documentos
    for doc_name in DOCS_REQUERIDOS:
        db.session.add(StudentDocument(student_id=est.id, doc_type=doc_name))
    db.session.commit()
    
    login_user(user)
    return redirect(url_for('student_dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- MÓDULO ESTUDIANTE ---

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
        # Si el docente no tiene tareas, se crean las DEFAULT (AVANCES NUMERADOS)
        if not tareas_docente:
             defaults = ["Avance 1", "Avance 2", "Avance 3", "Avance 4", "Presentación Final"]
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
    
    # Lógica para mostrar la evaluación solo al final
    evaluacion_activada = (profile.total_hours >= 100) # Ejemplo de lógica

    return render_template('student_dashboard.html', profile=profile, submissions=submissions, evaluacion_activada=evaluacion_activada)

@app.route('/student/upload_doc', methods=['POST'])
@login_required
def student_upload_doc():
    """El estudiante confirma subida de docs"""
    doc_id = request.form.get('doc_id')
    doc = StudentDocument.query.get(doc_id)
    if doc and doc.student_id == current_user.student_profile.id:
        doc.status = 'REVISION' # Pasa a estado de revisión
        db.session.commit()
        flash('Documento marcado para revisión.', 'success')
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
            if prev_sub and prev_sub.status != 'APROBADO':
                flash('Debes aprobar el avance anterior primero.', 'error')
                return redirect(url_for('student_dashboard'))

        sub.content = content
        sub.status = 'EN_REVISION'
        sub.submitted_at = datetime.date.today()
        db.session.commit()
        flash('Avance enviado correctamente.', 'success')
    
    return redirect(url_for('student_dashboard'))

@app.route('/student/add_timelog', methods=['POST'])
@login_required
def student_add_timelog():
    date_str = request.form.get('date')
    activity = request.form.get('activity_type')
    detail = request.form.get('activity_detail')
    hours = float(request.form.get('hours'))

    log = TimeLog(
        student_id=current_user.student_profile.id,
        date=datetime.datetime.strptime(date_str, '%Y-%m-%d').date(),
        activity_type=activity,
        activity_detail=detail,
        hours=hours,
        is_validated=False # Requiere validación docente
    )
    db.session.add(log)
    db.session.commit()
    return redirect(url_for('student_dashboard'))

# --- MÓDULO DOCENTE ---

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
                           tareas=mis_tareas,
                           docente=current_user)

@app.route('/docente/config_assignment', methods=['POST'])
@login_required
def docente_config_assignment():
    """El docente configura fechas y descripciones"""
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
        flash('Tarea configurada', 'success')

    return redirect(url_for('docente_dashboard'))

@app.route('/docente/add_assignment', methods=['POST'])
@login_required
def docente_add_assignment():
    """DOCENTE AGREGA UN NUEVO AVANCE AL FINAL"""
    if current_user.role != 'docente': return "Acceso Denegado"

    # Buscar el orden más alto actual
    ultimo = Assignment.query.filter_by(docente_id=current_user.id).order_by(Assignment.order.desc()).first()
    nuevo_orden = 1 if not ultimo else ultimo.order + 1
    titulo = f"Avance Extra {nuevo_orden}"

    nueva_tarea = Assignment(
        docente_id=current_user.id, 
        title=titulo, 
        order=nuevo_orden, 
        description="Configura este avance..."
    )
    db.session.add(nueva_tarea)
    db.session.commit()

    # Asignar a todos los estudiantes activos
    estudiantes = StudentProfile.query.filter_by(docente_id=current_user.id).all()
    for e in estudiantes:
        db.session.add(Submission(student_id=e.id, assignment_id=nueva_tarea.id))
    db.session.commit()
    
    return redirect(url_for('docente_dashboard'))

@app.route('/docente/delete_assignment', methods=['POST'])
@login_required
def docente_delete_assignment():
    """DOCENTE ELIMINA UN AVANCE"""
    if current_user.role != 'docente': return "Acceso Denegado"

    assign_id = request.form.get('assignment_id')
    tarea = Assignment.query.get(assign_id)

    if tarea and tarea.docente_id == current_user.id:
        db.session.delete(tarea) # Cascade borrará las submissions
        db.session.commit()

    return redirect(url_for('docente_dashboard'))

@app.route('/docente/ver_estudiante/<int:student_id>')
@login_required
def docente_ver_estudiante(student_id):
    est = StudentProfile.query.get_or_404(student_id)
    if est.docente_id != current_user.id: return "Acceso Denegado"

    submissions = Submission.query.filter_by(student_id=est.id).join(Assignment).order_by(Assignment.order).all()
    
    return render_template('docente_detalle_alumno.html', student=est, submissions=submissions)

@app.route('/docente/calificar', methods=['POST'])
@login_required
def docente_calificar():
    sub_id = request.form.get('submission_id')
    accion = request.form.get('accion') # APROBAR, OBSERVAR
    feedback = request.form.get('feedback')

    sub = Submission.query.get(sub_id)
    if sub.assignment.docente_id != current_user.id: return "Error"

    if accion == 'APROBAR':
        sub.status = 'APROBADO'
        sub.approved_at = datetime.date.today()
    elif accion == 'OBSERVAR':
        sub.status = 'OBSERVADO'
    
    sub.feedback = feedback
    db.session.commit()

    return redirect(url_for('docente_ver_estudiante', student_id=sub.student_id))

@app.route('/docente/validar_horas', methods=['POST'])
@login_required
def docente_validar_horas():
    log_id = request.form.get('log_id')
    student_id = request.form.get('student_id')
    
    log = TimeLog.query.get(log_id)
    # Seguridad básica
    if log.student.docente_id == current_user.id:
        log.is_validated = True
        db.session.commit()
    return redirect(url_for('docente_ver_estudiante', student_id=student_id))

# --- MÓDULO ADMIN ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': return "Acceso Denegado"
    
    pendientes = StudentProfile.query.filter_by(status='PENDIENTE').all()
    activos = StudentProfile.query.filter_by(status='ACTIVO').all()
    tutores = Tutor.query.all()
    
    return render_template('admin_dashboard.html', pendientes=pendientes, activos=activos, tutores=tutores)

@app.route('/admin/activar_estudiante', methods=['POST'])
@login_required
def admin_activar():
    if current_user.role != 'admin': return "Acceso Denegado"
    est_id = request.form.get('student_id')
    drive_url = request.form.get('drive_url')
    
    est = StudentProfile.query.get(est_id)
    est.status = 'ACTIVO'
    est.drive_folder_url = drive_url
    
    # Validar documentos base automáticamente al activar
    for doc in est.documents:
        if doc.doc_type in ['Boleta Inscripción', 'CV']: # Ejemplo
            doc.status = 'VALIDADO'
            
    db.session.commit()
    flash('Estudiante Activado', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/download/solicitud_pdf')
@login_required
def download_solicitud_pdf():
    profile = current_user.student_profile
    tutor = Tutor.query.get(profile.tutor_id)
    docente = User.query.get(profile.docente_id)
    
    filename = generar_carta_pdf(profile.full_name, profile.registro, "123456 SC", profile.practicum_level, tutor.name, docente.display_name)
    return send_file(filename, as_attachment=True)

@app.route('/download/bitacora_pdf')
@login_required
def download_bitacora_pdf():
    profile = current_user.student_profile
    filename = generar_reporte_academico(profile)
    return send_file(filename, as_attachment=True)

@app.route('/admin/export_csv')
@login_required
def export_csv():
    if current_user.role != 'admin': return "Acceso Denegado"
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Nombre', 'Registro', 'Tutor', 'Docente', 'Horas', 'Estado'])
    
    estudiantes = StudentProfile.query.all()
    for e in estudiantes:
        tutor_name = Tutor.query.get(e.tutor_id).name if e.tutor_id else "N/A"
        docente_name = User.query.get(e.docente_id).display_name if e.docente_id else "N/A"
        cw.writerow([e.id, e.full_name, e.registro, tutor_name, docente_name, e.total_hours, e.status])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export_estudiantes.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# --- RESET COMPLETO ---
@app.route('/peligro/reset-completo')
def reset_completo():
    db.drop_all()
    db.create_all()
    
    # Crear Admin
    admin = User(username='admin', role='admin', display_name="Dirección de Carrera")
    admin.set_password('123')
    db.session.add(admin)
    
    # Crear Tutores
    for d in DATOS_TUTORES:
        db.session.add(Tutor(name=d['nombre'], phone=d['tel'], email=d['email']))
    
    # Crear Docentes Base
    for dm in DOCENTES_MATERIA_DATA:
        doc = User(username=dm['user'], role='docente', display_name=dm['name'])
        doc.set_password('123')
        db.session.add(doc)
        db.session.commit()

        # Tareas por defecto
        tareas = ["Avance 1", "Avance 2", "Avance 3", "Avance 4", "Presentación Final"]
        for idx, t in enumerate(tareas):
             db.session.add(Assignment(docente_id=doc.id, title=t, order=idx+1, description="Por configurar..."))
    
    db.session.commit()
    return "<h1>Sistema Reconstruido con Nueva Arquitectura (Assignments + Docs)</h1>"

# --- PDF GENERATOR (CARTA FORMAL) ---
def generar_carta_pdf(nombre, registro, carnet, nivel, nombre_tutor, nombre_docente_materia):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # --- FECHA EN ESPAÑOL MANUAL ---
    pdf.set_margins(25, 25, 25)
    pdf.set_auto_page_break(auto=True, margin=25)

    # 1. Fecha
    pdf.set_font("Times", size=11)
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    now = datetime.datetime.now()
    fecha = f"{now.day} de {meses[now.month - 1]} de {now.year}"
    # -----------------------------------
    pdf.cell(0, 10, txt=f"Santa Cruz de la Sierra, {fecha}", ln=1, align='R')
    pdf.ln(15)

    # 2. Destinatario
    pdf.set_font("Times", 'B', size=11)
    pdf.cell(0, 5, txt="Señor:", ln=1)
    pdf.cell(0, 5, txt="Lic. Odin Rodríguez Mercado", ln=1)
    pdf.cell(0, 5, txt="DIRECTOR DE CARRERA CIENCIA POLÍTICA Y ADM. PÚBLICA", ln=1)
    pdf.cell(0, 5, txt="Presente.-", ln=1); pdf.ln(15)

    # 3. Referencia
    pdf.set_font("Times", 'B', size=12)
    pdf.cell(0, 10, txt=f"REF.: SOLICITUD DE DESIGNACIÓN DE TUTOR PARA PRACTICUM {nivel}", ln=1, align='C')
    pdf.ln(10)

    # 4. Cuerpo
    pdf.set_font("Times", size=12)
    body = (
        "De mi mayor consideración:\n\n"
        "Mediante la presente, tengo a bien dirigirme a su autoridad para saludarle muy cordialmente "
        "y desearle éxitos en las funciones que desempeña.\n\n"
        "El motivo de la presente es solicitar formalmente la designación de Tutor para la asignatura "
        f"de Practicum {nivel}, cumpliendo con los requisitos académicos establecidos. A continuación, "
        "detallo mis datos personales y la selección del docente para su correspondiente validación:"
    )
    pdf.multi_cell(0, 6, body, align='J')
    pdf.ln(10)

    # 5. Tabla Centrada
    pdf.set_x(35)
    w_label = 50
    w_data = 95
    h_row = 8

    pdf.set_font("Times", 'B', size=10)
    pdf.set_fill_color(245, 245, 245)

    # Tabla de datos
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', size=10)
    w_label = 60; w_data = 130; h_row = 10
    
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "NOMBRE:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre).upper(), 1, 1, 'L')
    
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "REGISTRO:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(registro), 1, 1, 'L')
    
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "CI:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(carnet), 1, 1, 'L')
    
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "MATERIA:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, f"PRACTICUM {nivel}", 1, 1, 'L')
    
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "DOCENTE MATERIA:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre_docente_materia), 1, 1, 'L')
    
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "TUTOR TESIS:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre_tutor).upper(), 1, 1, 'L')

    pdf.ln(20); pdf.multi_cell(0, 8, "Sin otro particular, saludo a usted atentamente."); pdf.ln(30)

    # 7. Firma
    pdf.set_font("Times", size=11)
    pdf.cell(0, 5, "____________________________________", ln=1, align='C')
    pdf.set_font("Times", 'B', size=11)
    pdf.cell(0, 5, str(nombre).upper(), ln=1, align='C')
    pdf.set_font("Times", size=11)
    pdf.cell(0, 5, f"Registro: {registro}", ln=1, align='C')
    pdf.cell(0, 5, f"C.I.: {carnet}", ln=1, align='C')

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
    app.run(debug=True)
