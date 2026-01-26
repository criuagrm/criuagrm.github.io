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
# --- 2. MODELOS DE BASE DE DATOS ---

class User(UserMixin, db.Model):
    """Sistema de Usuarios"""
@@ -37,19 +37,11 @@
    role = db.Column(db.String(20)) # 'admin', 'student', 'docente'
    display_name = db.Column(db.String(100))

    # RELACIONES
    student_profile = db.relationship(
        'StudentProfile', 
        backref='user_account', 
        uselist=False, 
        foreign_keys='StudentProfile.user_id'
        'StudentProfile', backref='user_account', uselist=False, foreign_keys='StudentProfile.user_id'
    )
    
    assigned_students = db.relationship(
        'StudentProfile', 
        backref='assigned_docente', 
        lazy=True, 
        foreign_keys='StudentProfile.docente_id'
        'StudentProfile', backref='assigned_docente', lazy=True, foreign_keys='StudentProfile.docente_id'
    )

    def set_password(self, password):
@@ -81,10 +73,9 @@
    practicum_level = db.Column(db.String(5))

    tutor_id = db.Column(db.Integer, db.ForeignKey('tutor.id')) 
    status = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, ACTIVO
    status = db.Column(db.String(20), default='PENDIENTE') 
    drive_folder_url = db.Column(db.String(300))

    # RELACIONES
    documents = db.relationship('StudentDocument', backref='student', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)
    logs = db.relationship('TimeLog', backref='student', lazy=True)
@@ -104,36 +95,29 @@
        return "OK"

class StudentDocument(db.Model):
    """Módulo Administrativo: Papeles y Requisitos"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    doc_type = db.Column(db.String(50)) # 'Boleta', 'CV', 'Carnet', 'Formulario'
    status = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, REVISION, VALIDADO, RECHAZADO
    drive_link = db.Column(db.String(300)) # Link específico si el alumno quiere ponerlo
    doc_type = db.Column(db.String(50)) 
    status = db.Column(db.String(20), default='PENDIENTE') 
    drive_link = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Assignment(db.Model):
    """Módulo Académico: El 'Molde' de la tarea creado por el Docente"""
    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    title = db.Column(db.String(200)) # Ej: "Avance 1"
    title = db.Column(db.String(200)) 
    description = db.Column(db.Text)
    order = db.Column(db.Integer) # 1, 2, 3...
    deadline = db.Column(db.Date, nullable=True) # FECHA LIMITE
    
    order = db.Column(db.Integer) 
    deadline = db.Column(db.Date, nullable=True) 
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade="all, delete-orphan")

class Submission(db.Model):
    """Módulo Académico: La entrega del estudiante"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'))
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'))
    
    content = db.Column(db.Text) # Texto o Link al documento
    status = db.Column(db.String(20), default='BORRADOR') # BORRADOR, EN_REVISION, OBSERVADO, APROBADO
    feedback = db.Column(db.Text) # Correcciones del docente
    
    content = db.Column(db.Text) 
    status = db.Column(db.String(20), default='BORRADOR') 
    feedback = db.Column(db.Text) 
    submitted_at = db.Column(db.Date)
    approved_at = db.Column(db.Date)

@@ -145,15 +129,12 @@
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
@@ -221,19 +202,16 @@
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
@@ -243,16 +221,10 @@
            db.session.commit() 

            # TAREAS POR DEFECTO (AVANCE 1, 2, 3...)
            tareas = [
                "Avance 1", 
                "Avance 2", 
                "Avance 3", 
                "Avance 4",
                "Presentación Final"
            ]
            for idx, tarea in enumerate(tareas):
                if not Assignment.query.filter_by(docente_id=doc.id, title=tarea).first():
                    db.session.add(Assignment(docente_id=doc.id, title=tarea, order=idx+1, description="Pendiente de configuración por el docente."))
            tareas = ["Avance 1", "Avance 2", "Avance 3", "Avance 4", "Presentación Final"]
            for idx, t in enumerate(tareas):
                if not Assignment.query.filter_by(docente_id=doc.id, title=t).first():
                    db.session.add(Assignment(docente_id=doc.id, title=t, order=idx+1, description="Pendiente de configuración por el docente."))
            db.session.commit()

# --- RUTAS PÚBLICAS ---
@@ -285,18 +257,20 @@

@app.route('/api/docentes_materia', methods=['GET'])
def get_docentes_materia():
    # CORRECCIÓN DE FILTRADO PARA QUE NO SALGAN TODOS LOS TURNOS MEZCLADOS
    level = request.args.get('level') # Ej: "II", "III", "IV"
    query = User.query.filter_by(role='docente')

    if level:
        # Filtramos si el nombre contiene "Practicum NIVEL " (con espacio para no confundir II con III)
        # Filtro estricto: Busca "Practicum II " o "Practicum II -"
        search_term = f"Practicum {level} "
        docentes = query.filter(User.display_name.contains(search_term)).all()
        # Si no encuentra (por el formato del nombre), busca con guion
        if not docentes:
            search_term_b = f"Practicum {level} -"
            docentes = query.filter(User.display_name.contains(search_term_b)).all()
        search_term_b = f"Practicum {level} -"
        
        docentes = query.filter(
            db.or_(
                User.display_name.contains(search_term),
                User.display_name.contains(search_term_b)
            )
        ).all()
    else:
        docentes = query.all()

@@ -328,7 +302,6 @@

    setattr(tutor, campo_cupo, tomados + 1)

    # Crear Perfil PENDIENTE
    est = StudentProfile(
        full_name=data.get('nombre'),
        registro=data.get('registro'),
@@ -341,7 +314,6 @@
    db.session.add(est)
    db.session.commit()

    # Inicializar Documentos
    for doc_name in DOCS_REQUERIDOS:
        db.session.add(StudentDocument(student_id=est.id, doc_type=doc_name))
    db.session.commit()
@@ -386,32 +358,28 @@
    logout_user()
    return redirect(url_for('index'))

# --- MÓDULO ESTUDIANTE (REPARADO Y CON LÓGICA SEMÁFORO) ---
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
@@ -424,7 +392,6 @@
@app.route('/student/upload_doc', methods=['POST'])
@login_required
def student_upload_doc():
    """El estudiante confirma subida de docs"""
    doc_id = request.form.get('doc_id')
    doc = StudentDocument.query.get(doc_id)
    if doc and doc.student_id == current_user.student_profile.id:
@@ -435,14 +402,11 @@
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
@@ -471,17 +435,14 @@
    db.session.commit()
    return redirect(url_for('student_dashboard'))

# --- MÓDULO DOCENTE (CONFIGURACIÓN Y REVISIÓN) ---
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
@@ -492,12 +453,11 @@
@app.route('/docente/config_assignment', methods=['POST'])
@login_required
def docente_config_assignment():
    """El docente configura fechas y descripciones"""
    if current_user.role != 'docente': return "Acceso Denegado"

    assign_id = request.form.get('assignment_id')
    description = request.form.get('description')
    deadline_str = request.form.get('deadline') # YYYY-MM-DD
    deadline_str = request.form.get('deadline') 

    tarea = Assignment.query.get(assign_id)
    if tarea and tarea.docente_id == current_user.id:
@@ -511,24 +471,18 @@
@app.route('/docente/add_assignment', methods=['POST'])
@login_required
def docente_add_assignment():
    """DOCENTE AGREGA UN NUEVO AVANCE AL FINAL"""
    if current_user.role != 'docente': return "Acceso Denegado"

    # Buscar el orden más alto actual
    ultimo = Assignment.query.filter_by(docente_id=current_user.id).order_by(Assignment.order.desc()).first()
    nuevo_orden = 1 if not ultimo else ultimo.order + 1
    titulo = f"Nuevo Avance {nuevo_orden}"
    titulo = f"Avance Extra {nuevo_orden}"

    nueva_tarea = Assignment(
        docente_id=current_user.id, 
        title=titulo, 
        order=nuevo_orden, 
        description="Configura este avance..."
        docente_id=current_user.id, title=titulo, order=nuevo_orden, description="Configura este avance..."
    )
    db.session.add(nueva_tarea)
    db.session.commit()

    # Asignar a todos los estudiantes activos
    estudiantes = StudentProfile.query.filter_by(docente_id=current_user.id).all()
    for e in estudiantes:
        db.session.add(Submission(student_id=e.id, assignment_id=nueva_tarea.id))
@@ -539,14 +493,13 @@
@app.route('/docente/delete_assignment', methods=['POST'])
@login_required
def docente_delete_assignment():
    """DOCENTE ELIMINA UN AVANCE"""
    if current_user.role != 'docente': return "Acceso Denegado"

    assign_id = request.form.get('assignment_id')
    tarea = Assignment.query.get(assign_id)

    if tarea and tarea.docente_id == current_user.id:
        db.session.delete(tarea) # Cascade borrará las submissions
        db.session.delete(tarea) 
        db.session.commit()

    return redirect(url_for('docente_dashboard'))
@@ -592,7 +545,7 @@
    db.session.commit()
    return redirect(url_for('docente_ver_estudiante', student_id=student_id))

# --- MÓDULO ADMIN (DIRECTOR) ---
# --- MÓDULO ADMIN ---

@app.route('/admin/dashboard')
@login_required
@@ -663,7 +616,7 @@
        'Content-Type': 'text/csv'
    })

# --- RESET COMPLETO (OBLIGATORIO) ---
# --- RESET COMPLETO ---
@app.route('/peligro/reset-completo')
def reset_completo():
    db.drop_all()
@@ -684,72 +637,122 @@
        db.session.add(doc)
        db.session.commit()

        # TAREAS POR DEFECTO (AVANCE 1, 2, 3...)
        # Tareas por defecto
        tareas = ["Avance 1", "Avance 2", "Avance 3", "Avance 4", "Presentación Final"]
        for idx, t in enumerate(tareas):
             db.session.add(Assignment(docente_id=doc.id, title=t, order=idx+1, description="Por configurar..."))

    db.session.commit()
    return "<h1>Sistema Reconstruido con Nueva Arquitectura (Assignments + Docs)</h1>"

# --- PDF GENERATOR ---
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

    pdf.cell(0, 10, txt=f"Santa Cruz, {fecha}", ln=1, align='R'); pdf.ln(10)
    
    pdf.set_font("Arial", 'B', size=11)
    # 2. Destinatario
    pdf.set_font("Times", 'B', size=11)
    pdf.cell(0, 5, txt="Señor:", ln=1)
    pdf.cell(0, 5, txt="Lic. Odin Rodríguez Mercado", ln=1)
    pdf.cell(0, 5, txt="DIRECTOR DE CARRERA CIENCIA POLÍTICA Y ADM. PÚBLICA", ln=1)
    pdf.cell(0, 5, txt="Presente.-", ln=1); pdf.ln(15)
    pdf.cell(0, 10, txt=f"REF: SOLICITUD DE TUTOR PARA PRACTICUM {nivel}", ln=1, align='R'); pdf.ln(10)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, "Mediante la presente, solicito formalmente la asignación de tutoría. A continuación detallo mis datos y el docente seleccionado:"); pdf.ln(10)
    pdf.cell(0, 5, txt="M.Sc. Odín Rodríguez Mercado", ln=1) 
    pdf.cell(0, 5, txt="DIRECTOR DE CARRERA DE CIENCIA POLÍTICA Y ADM. PÚBLICA", ln=1)
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

    # Filas
    pdf.cell(w_label, h_row, "NOMBRE COMPLETO:", 1, 0, 'L', True); pdf.set_font("Times", size=10); pdf.cell(w_data, h_row, str(nombre).upper(), 1, 1, 'L')

    # Tabla de datos
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', size=10)
    w_label = 60; w_data = 130; h_row = 10
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "REGISTRO UNIVERSITARIO:", 1, 0, 'L', True); pdf.set_font("Times", size=10); pdf.cell(w_data, h_row, str(registro), 1, 1, 'L')

    pdf.cell(w_label, h_row, "NOMBRE:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre).upper(), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "REGISTRO:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(registro), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "CI:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(carnet), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "MATERIA:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, f"PRACTICUM {nivel}", 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "DOCENTE MATERIA:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre_docente_materia), 1, 1, 'L')
    pdf.set_font("Arial", 'B', size=10); pdf.cell(w_label, h_row, "TUTOR TESIS:", 1, 0, 'L', True); pdf.set_font("Arial", size=10); pdf.cell(w_data, h_row, str(nombre_tutor).upper(), 1, 1, 'L')
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "CÉDULA DE IDENTIDAD:", 1, 0, 'L', True); pdf.set_font("Times", size=10); pdf.cell(w_data, h_row, str(carnet), 1, 1, 'L')

    pdf.ln(20); pdf.multi_cell(0, 8, "Sin otro particular, saludo a usted atentamente."); pdf.ln(30)
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "NIVEL DE PRACTICUM:", 1, 0, 'L', True); pdf.set_font("Times", size=10); pdf.cell(w_data, h_row, f"PRACTICUM {nivel}", 1, 1, 'L')

    pdf.cell(0, 5, txt="__________________________", ln=1, align='C'); pdf.cell(0, 5, txt=f"{nombre}", ln=1, align='C')
    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "DOCENTE DE MATERIA:", 1, 0, 'L', True); pdf.set_font("Times", size=10); pdf.cell(w_data, h_row, str(nombre_docente_materia), 1, 1, 'L')

    pdf.set_x(35); pdf.set_font("Times", 'B', size=10)
    pdf.cell(w_label, h_row, "TUTOR DE PRACTICUM:", 1, 0, 'L', True); pdf.set_font("Times", size=10); pdf.cell(w_data, h_row, str(nombre_tutor).upper(), 1, 1, 'L')

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
