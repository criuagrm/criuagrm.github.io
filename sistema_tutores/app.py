import os
import datetime
import io
import csv
from flask import Flask, jsonify, request, send_file, render_template, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
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
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20)) # 'admin', 'student', 'docente'
    display_name = db.Column(db.String(100))

    # RELACIONES
    student_profile = db.relationship(
        'StudentProfile', backref='user_account', uselist=False, foreign_keys='StudentProfile.user_id'
    )
    
    assigned_students = db.relationship(
        'StudentProfile', backref='assigned_docente', lazy=True, foreign_keys='StudentProfile.docente_id'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Tutor(db.Model):
    """Tutores con cupos por nivel"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    cupo_ii = db.Column(db.Integer, default=5)
    cupo_iii = db.Column(db.Integer, default=5)
    cupo_iv = db.Column(db.Integer, default=5)

class StudentProfile(db.Model):
    """Datos del estudiante registrado"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    full_name = db.Column(db.String(100))
    registro = db.Column(db.String(50), unique=True)
    ci = db.Column(db.String(20))
    practicum_level = db.Column(db.String(5))
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutor.id')) 
    status = db.Column(db.String(20), default='PENDIENTE')
    drive_folder_url = db.Column(db.String(300))

    # RELACIONES
    documents = db.relationship('StudentDocument', backref='student', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)
    logs = db.relationship('TimeLog', backref='student', lazy=True)
    attendance = db.relationship('AttendanceLog', backref='student', lazy=True)

    # Campos para asignación docente
    docente_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def total_hours(self):
        validated_logs = [log for log in self.logs if log.is_validated]
        return sum(log.hours for log in validated_logs) if validated_logs else 0

    def health_check(self):
        """Para monitoreo de consistencia"""
        return "OK"

class StudentDocument(db.Model):
    """Módulo Administrativo: Papeles y Requisitos"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    doc_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='PENDIENTE')
    drive_link = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Assignment(db.Model):
    """Módulo Académico: El 'Molde' de la tarea creado por el Docente"""
    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    order = db.Column(db.Integer)
    deadline = db.Column(db.Date, nullable=True)
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade="all, delete-orphan")

class Submission(db.Model):
    """Módulo Académico: La entrega del estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'))
    content = db.Column(db.Text)
    status = db.Column(db.String(20), default='BORRADOR')
    feedback = db.Column(db.Text)
    submitted_at = db.Column(db.Date)
    approved_at = db.Column(db.Date)

    def is_approved(self):
        return self.status == 'APROBADO'

    def approval_days(self):
        if self.submitted_at and self.approved_at:
            delta = self.approved_at - self.submitted_at
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
    """Asistencias de estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    date = db.Column(db.Date, default=datetime.date.today)
    attended = db.Column(db.Boolean, default=False)

# --- DATOS POR DEFECTO (DURANTE EL SETUP) ---

DATOS_TUTORES = [
    {"nombre": "Dr. Juan Perez", "tel": "12345678", "email": "juanperez@uagrm.edu.bo"},
    {"nombre": "M.Sc. Ana Gómez", "tel": "87654321", "email": "anagomez@uagrm.edu.bo"},
    {"nombre": "M.Sc. Carlos Ruiz", "tel": "55555555", "email": "carlosruiz@uagrm.edu.bo"},
    {"nombre": "Lic. María Fernández", "tel": "44444444", "email": "mariaf@uagrm.edu.bo"}
]

DOCS_REQUERIDOS = ["Boleta Inscripción", "CV", "Fotocopia Carnet", "Formulario Datos"]

DOCENTES_MATERIA_DATA = [
    {"user": "docenteii", "nombre": "M.Sc. Roberto Carlos - Practicum II", "password": "123"},
    {"user": "docenteiii", "nombre": "Lic. Sofia Ramirez - Practicum III", "password": "123"},
    {"user": "docenteiv", "nombre": "Dr. Luis Vargas - Practicum IV", "password": "123"}
]

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
        db.session.commit()

    # Carga Docentes
    for dm in DOCENTES_MATERIA_DATA:
        doc = User.query.filter_by(username=dm['user']).first()
        if not doc:
            nuevo = User(username=dm['user'], role='docente', display_name=dm['nombre'])
            nuevo.set_password(dm['password'])
            db.session.add(nuevo)
            db.session.commit()

            # TAREAS POR DEFECTO
            tareas = ["Avance 1", "Avance 2", "Avance 3", "Avance 4", "Presentación Final"]
            for idx, t in enumerate(tareas):
                if not Assignment.query.filter_by(docente_id=nuevo.id, title=t).first():
                    db.session.add(Assignment(
                        docente_id=nuevo.id,
                        title=t,
                        order=idx+1,
                        description="Pendiente de configuración por el docente."
                    ))
            db.session.commit()

# --- RUTAS PÚBLICAS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register_page')
def register_page():
    tutores = Tutor.query.all()
    return render_template('register.html', tutores=tutores)

@app.route('/api/docentes_materia', methods=['GET'])
def get_docentes_materia():
    level = request.args.get('level')
    query = User.query.filter_by(role='docente')

    if level:
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

@app.route('/api/register_student', methods=['POST'])
def api_register_student():
    data = request.json
    
    # Verificar cupo tutor
    tutor = Tutor.query.get(data['tutor_id'])
    campo_cupo = f"cupo_{data['nivel'].lower()}"
    cupo_disponible = getattr(tutor, campo_cupo, 0)
    if cupo_disponible <= 0:
        return jsonify({'error': 'Cupo lleno en este nivel'}), 400

    # Crear usuario
    user = User(
        username=data['registro'],
        role='student',
        display_name=data['nombre']
    )
    user.set_password(data['ci'])
    db.session.add(user)
    db.session.commit()

    # Reducir cupo
    tomados = getattr(tutor, campo_cupo)
    setattr(tutor, campo_cupo, tomados + 1)

    # Crear Perfil PENDIENTE
    est = StudentProfile(
        full_name=data.get('nombre'),
        registro=data.get('registro'),
        ci=data.get('ci'),
        practicum_level=data.get('nivel'),
        tutor_id=data.get('tutor_id'),
        docente_id=data.get('docente_id'),
        user_id=user.id
    )
    db.session.add(est)
    db.session.commit()

    # Inicializar Documentos
    for doc_name in DOCS_REQUERIDOS:
        db.session.add(StudentDocument(student_id=est.id, doc_type=doc_name))
    db.session.commit()

    # Generar carta PDF
    tutor_nombre = tutor.name
    docente = User.query.get(data['docente_id'])
    docente_nombre = docente.display_name if docente else "No asignado"
    
    pdf_filename = generar_carta_pdf(
        data['nombre'],
        data['registro'],
        data['ci'],
        data['nivel'],
        tutor_nombre,
        docente_nombre
    )

    return jsonify({
        'success': True,
        'message': 'Registro exitoso',
        'carta_pdf': pdf_filename
    })

# --- AUTENTICACIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'docente':
                return redirect(url_for('docente_dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- MÓDULO ESTUDIANTE ---

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('index'))
    
    profile = current_user.student_profile

    # 2. ASEGURAR TAREAS (Si el docente ya las tiene configuradas)
    if profile.docente_id:
        tareas_docente = Assignment.query.filter_by(docente_id=profile.docente_id).all()
        
        # Vincular estudiante a las tareas
        for t in tareas_docente:
            if not Submission.query.filter_by(student_id=profile.id, assignment_id=t.id).first():
                db.session.add(Submission(student_id=profile.id, assignment_id=t.id))
        db.session.commit()

    return render_template('student_dashboard.html', profile=profile)

@app.route('/student/upload_doc', methods=['POST'])
@login_required
def student_upload_doc():
    doc_id = request.form.get('doc_id')
    doc = StudentDocument.query.get(doc_id)
    if doc and doc.student_id == current_user.student_profile.id:
        doc.drive_link = request.form.get('drive_link')
        doc.status = 'REVISION'
        db.session.commit()
    return redirect(url_for('student_dashboard'))

@app.route('/student/submit_assignment', methods=['POST'])
@login_required
def student_submit_assignment():
    sub_id = request.form.get('submission_id')
    content = request.form.get('content')

    sub = Submission.query.get(sub_id)
    if sub and sub.student_id == current_user.student_profile.id:
        
        # LÓGICA SEMÁFORO: Verificar si la anterior está aprobada
        prev_assign = Assignment.query.filter_by(
            docente_id=sub.assignment.docente_id,
            order=sub.assignment.order - 1
        ).first()
        
        if prev_assign:
            prev_sub = Submission.query.filter_by(
                student_id=current_user.student_profile.id,
                assignment_id=prev_assign.id
            ).first()
            if prev_sub and not prev_sub.is_approved():
                flash('Debe aprobar el avance anterior primero')
                return redirect(url_for('student_dashboard'))
        
        sub.content = content
        sub.status = 'EN_REVISION'
        sub.submitted_at = datetime.date.today()
        db.session.commit()
        flash('Entrega enviada para revisión')
    
    return redirect(url_for('student_dashboard'))

@app.route('/student/add_log', methods=['POST'])
@login_required
def student_add_log():
    profile = current_user.student_profile
    log = TimeLog(
        student_id=profile.id,
        activity_type=request.form.get('activity_type'),
        activity_detail=request.form.get('activity_detail'),
        hours=float(request.form.get('hours', 0))
    )
    db.session.add(log)
    db.session.commit()
    return redirect(url_for('student_dashboard'))

# --- MÓDULO DOCENTE ---

@app.route('/docente/dashboard')
@login_required
def docente_dashboard():
    if current_user.role != 'docente':
        return "Acceso Denegado"

    # Obtener alumnos
    mis_estudiantes = StudentProfile.query.filter_by(
        docente_id=current_user.id,
        status='ACTIVO'
    ).all()
    
    # Obtener Tareas para configuración
    mis_tareas = Assignment.query.filter_by(docente_id=current_user.id).order_by(Assignment.order).all()

    return render_template('docente_dashboard.html',
        estudiantes=mis_estudiantes,
        tareas=mis_tareas
    )

@app.route('/docente/config_assignment', methods=['POST'])
@login_required
def docente_config_assignment():
    if current_user.role != 'docente':
        return "Acceso Denegado"

    assign_id = request.form.get('assignment_id')
    description = request.form.get('description')
    deadline_str = request.form.get('deadline')

    tarea = Assignment.query.get(assign_id)
    if tarea and tarea.docente_id == current_user.id:
        tarea.description = description
        if deadline_str:
            tarea.deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d').date()
        db.session.commit()
    
    return redirect(url_for('docente_dashboard'))

@app.route('/docente/add_assignment', methods=['POST'])
@login_required
def docente_add_assignment():
    if current_user.role != 'docente':
        return "Acceso Denegado"

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
    if current_user.role != 'docente':
        return "Acceso Denegado"

    assign_id = request.form.get('assignment_id')
    tarea = Assignment.query.get(assign_id)

    if tarea and tarea.docente_id == current_user.id:
        db.session.delete(tarea)
        db.session.commit()

    return redirect(url_for('docente_dashboard'))

@app.route('/docente/estudiante/<int:student_id>')
@login_required
def docente_ver_estudiante(student_id):
    if current_user.role != 'docente':
        return "Acceso Denegado"
    
    estudiante = StudentProfile.query.get(student_id)
    if not estudiante or estudiante.docente_id != current_user.id:
        return "Estudiante no encontrado"
    
    return render_template('docente_review_student.html', estudiante=estudiante)

@app.route('/docente/review_submission', methods=['POST'])
@login_required
def docente_review_submission():
    if current_user.role != 'docente':
        return "Acceso Denegado"

    sub_id = request.form.get('submission_id')
    feedback = request.form.get('feedback')
    action = request.form.get('action')  # 'approve' o 'reject'

    sub = Submission.query.get(sub_id)
    if sub and sub.assignment.docente_id == current_user.id:
        sub.feedback = feedback
        if action == 'approve':
            sub.status = 'APROBADO'
            sub.approved_at = datetime.date.today()
        else:
            sub.status = 'OBSERVADO'
        db.session.commit()
    
    return redirect(url_for('docente_ver_estudiante', student_id=sub.student_id))

@app.route('/docente/validate_hours/<int:student_id>', methods=['POST'])
@login_required
def docente_validate_hours(student_id):
    if current_user.role != 'docente':
        return "Acceso Denegado"

    log_id = request.form.get('log_id')
    log = TimeLog.query.get(log_id)
    if log and log.student.docente_id == current_user.id:
        log.is_validated = True
        db.session.commit()
    
    return redirect(url_for('docente_ver_estudiante', student_id=student_id))

# --- MÓDULO ADMIN ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Acceso Denegado"
    
    # Datos para dashboard
    total_estudiantes = StudentProfile.query.count()
    estudiantes_pendientes = StudentProfile.query.filter_by(status='PENDIENTE').count()
    estudiantes_activos = StudentProfile.query.filter_by(status='ACTIVO').count()
    docentes = User.query.filter_by(role='docente').all()
    
    return render_template('admin_dashboard.html',
        total_estudiantes=total_estudiantes,
        pendientes=estudiantes_pendientes,
        activos=estudiantes_activos,
        docentes=docentes
    )

@app.route('/admin/validate_doc', methods=['POST'])
@login_required
def admin_validate_doc():
    if current_user.role != 'admin':
        return "Acceso Denegado"
    
    doc_id = request.form.get('doc_id')
    action = request.form.get('action')  # 'validate' o 'reject'
    
    doc = StudentDocument.query.get(doc_id)
    if doc:
        doc.status = 'VALIDADO' if action == 'validate' else 'RECHAZADO'
        db.session.commit()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/activate_student/<int:student_id>')
@login_required
def admin_activate_student(student_id):
    if current_user.role != 'admin':
        return "Acceso Denegado"
    
    est = StudentProfile.query.get(student_id)
    if est:
        est.status = 'ACTIVO'
        db.session.commit()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export_csv')
@login_required
def admin_export_csv():
    if current_user.role != 'admin':
        return "Acceso Denegado"
    
    # Generar CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabecera
    writer.writerow(['Registro', 'Nombre', 'CI', 'Nivel', 'Tutor', 'Docente', 'Estado', 'Horas Validadas'])
    
    # Datos
    estudiantes = StudentProfile.query.all()
    for e in estudiantes:
        tutor = Tutor.query.get(e.tutor_id)
        docente = User.query.get(e.docente_id)
        writer.writerow([
            e.registro,
            e.full_name,
            e.ci,
            e.practicum_level,
            tutor.name if tutor else '',
            docente.display_name if docente else '',
            e.status,
            e.total_hours()
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        download_name='reporte_estudiantes.csv',
        as_attachment=True
    )

# --- RESET COMPLETO ---

@app.route('/peligro/reset-completo')
def reset_completo():
    db.drop_all()
    db.create_all()
    
    # Tutores
    for d in DATOS_TUTORES:
        db.session.add(Tutor(name=d['nombre'], phone=d['tel'], email=d['email']))
    
    # Admin
    admin = User(username='admin', role='admin', display_name="Dirección de Carrera")
    admin.set_password('123')
    db.session.add(admin)
    
    # Docentes
    for dm in DOCENTES_MATERIA_DATA:
        doc = User(username=dm['user'], role='docente', display_name=dm['nombre'])
        doc.set_password(dm['password'])
        db.session.add(doc)
    
    db.session.commit()
    
    # Tareas por defecto
    for doc in User.query.filter_by(role='docente').all():
        tareas = ["Avance 1", "Avance 2", "Avance 3", "Avance 4", "Presentación Final"]
        for idx, t in enumerate(tareas):
            db.session.add(Assignment(
                docente_id=doc.id,
                title=t,
                order=idx+1,
                description="Por configurar..."
            ))
    
    db.session.commit()
    return "<h1>Sistema Reconstruido con Nueva Arquitectura (Assignments + Docs)</h1>"

# --- PDF GENERATOR (CARTA FORMAL) ---

def generar_carta_pdf(nombre, registro, carnet, nivel, nombre_tutor, nombre_docente_materia):
    pdf = FPDF()
    pdf.add_page()
    
    # Configuración
    pdf.set_margins(25, 25, 25)
    pdf.set_auto_page_break(auto=True, margin=25)

    # 1. Fecha
    pdf.set_font("Times", size=11)
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    now = datetime.datetime.now()
    fecha = f"{now.day} de {meses[now.month - 1]} de {now.year}"
    
    pdf.cell(0, 10, txt=f"Santa Cruz de la Sierra, {fecha}", ln=1, align='R')
    pdf.ln(15)

    # 2. Destinatario
    pdf.set_font("Times", 'B', size=11)
    pdf.cell(0, 5, txt="Señor:", ln=1)
    pdf.cell(0, 5, txt="Lic. Odin Rodríguez Mercado", ln=1)
    pdf.cell(0, 5, txt="DIRECTOR DE CARRERA CIENCIA POLÍTICA Y ADM. PÚBLICA", ln=1)
    pdf.cell(0, 5, txt="Presente.-", ln=1)
    pdf.ln(15)
    
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

    # Filas de la tabla
    pdf.cell(w_label, h_row, "NOMBRE COMPLETO:", 1, 0, 'L', True)
    pdf.set_font("Times", size=10)
    pdf.cell(w_data, h_row, str(nombre).upper(), 1, 1, 'L')

    pdf.set_x(35)
    pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "REGISTRO UNIVERSITARIO:", 1, 0, 'L', True)
    pdf.set_font("Times", size=10)
    pdf.cell(w_data, h_row, str(registro), 1, 1, 'L')

    pdf.set_x(35)
    pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "CÉDULA DE IDENTIDAD:", 1, 0, 'L', True)
    pdf.set_font("Times", size=10)
    pdf.cell(w_data, h_row, str(carnet), 1, 1, 'L')

    pdf.set_x(35)
    pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "NIVEL DE PRACTICUM:", 1, 0, 'L', True)
    pdf.set_font("Times", size=10)
    pdf.cell(w_data, h_row, f"PRACTICUM {nivel}", 1, 1, 'L')

    pdf.set_x(35)
    pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "DOCENTE DE MATERIA:", 1, 0, 'L', True)
    pdf.set_font("Times", size=10)
    pdf.cell(w_data, h_row, str(nombre_docente_materia), 1, 1, 'L')

    pdf.set_x(35)
    pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "TUTOR DE PRACTICUM:", 1, 0, 'L', True)
    pdf.set_font("Times", size=10)
    pdf.cell(w_data, h_row, str(nombre_tutor).upper(), 1, 1, 'L')

    pdf.ln(15)

    # 6. Despedida
    pdf.set_font("Times", size=12)
    closing = (
        "Agradeciendo de antemano su gentil atención y favorable acogida a la presente solicitud, "
        "me despido con las mayores consideraciones."
    )
    pdf.multi_cell(0, 6, closing, align='J')
    pdf.ln(30)

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

# --- REPORTE ACADÉMICO ---

def generar_reporte_academico(p):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Portafolio Académico", 0, 1, 'C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Estudiante: {p.full_name} | Horas: {p.total_hours()}", 0, 1)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Bitácora de Actividades", 0, 1)
    pdf.set_font("Arial", size=10)
    
    for log in p.logs:
        estado = 'Validado' if log.is_validated else 'Pendiente'
        pdf.cell(0, 10, f"{log.date} - {log.activity_type}: {log.hours}hrs ({estado})", 0, 1)
    
    filename = f"reporte_{p.registro}.pdf"
    pdf.output(filename)
    return filename

# Agregar estas rutas al final de tu app.py, antes de if __name__ == '__main__':

@app.route('/api/tutores')
def get_tutores():
    """Obtiene todos los tutores con cupos disponibles"""
    level = request.args.get('level', '')
    
    # Obtener todos los tutores
    tutores = Tutor.query.all()
    result = []
    
    for tutor in tutores:
        # Calcular cupos ocupados
        if level:
            # Contar estudiantes con este tutor en este nivel específico
            ocupados = StudentProfile.query.filter_by(
                tutor_id=tutor.id,
                practicum_level=level
            ).count()
        else:
            # Contar todos los estudiantes con este tutor
            ocupados = StudentProfile.query.filter_by(tutor_id=tutor.id).count()
        
        # Obtener cupo total para este nivel
        campo_cupo = f"cupo_{level.lower()}" if level else "cupo_ii"
        cupo_total = getattr(tutor, campo_cupo, 0)
        
        # Calcular cupos disponibles
        cupos_disponibles = max(0, cupo_total - ocupados)
        
        result.append({
            'id': tutor.id,
            'name': tutor.name,
            'phone': tutor.phone,
            'email': tutor.email,
            f'cupo_{level.lower()}': cupos_disponibles if level else 0,
            'ocupados': ocupados,
            'total': cupo_total
        })
    
    return jsonify(result)

@app.route('/download/carta/<filename>')
def download_carta(filename):
    """Sirve el archivo PDF generado"""
    try:
        return send_file(filename, as_attachment=True)
    except FileNotFoundError:
        return "Archivo no encontrado", 404

# También necesitas esta función para inyectar la fecha actual en los templates
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.now()}

if __name__ == '__main__':
    app.run(debug=True)

