import os
from flask import Flask, jsonify, request, send_file, render_template
from flask_sqlalchemy import SQLAlchemy
from fpdf import FPDF
import datetime

app = Flask(__name__)

# --- 1. CONFIGURACIÓN DE BASE DE DATOS (POSTGRESQL) ---
# Render entrega la URL como 'postgres://', pero SQLAlchemy necesita 'postgresql://'
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local_tutores.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 2. MODELO DE LA BASE DE DATOS ---
class Tutor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    # Contadores de cupos ocupados
    taken_II = db.Column(db.Integer, default=0)
    taken_III = db.Column(db.Integer, default=0)
    taken_IV = db.Column(db.Integer, default=0)

# --- 3. CONFIGURACIÓN DE CUPOS ---
CAPACIDAD = {"II": 5, "III": 3, "IV": 2}

# --- 4. LISTA MAESTRA DE DOCENTES ---
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

# --- 5. INICIALIZADOR DE BASE DE DATOS ---
with app.app_context():
    db.create_all() # Crea tablas si no existen
    # Si la tabla está vacía, carga los docentes automáticamente
    if Tutor.query.count() == 0:
        print("Base de datos vacía. Cargando docentes...")
        for d in DATOS_INICIALES:
            nuevo = Tutor(name=d['nombre'], phone=d['tel'], email=d['email'])
            db.session.add(nuevo)
        db.session.commit()
        print("¡Carga inicial completada!")

# --- 6. RUTAS DEL SISTEMA ---

@app.route('/')
def index():
    return render_template('index.html')

# --- RUTA SECRETA PARA REINICIAR LA BASE DE DATOS (PANIC BUTTON) ---
@app.route('/admin/reset-total')
def reset_db():
    try:
        # Pone todos los contadores en 0
        tutors = Tutor.query.all()
        for t in tutors:
            t.taken_II = 0
            t.taken_III = 0
            t.taken_IV = 0
        db.session.commit()
        return """
        <div style="font-family:sans-serif; text-align:center; padding:50px;">
            <h1 style="color:green;">¡RESET EXITOSO!</h1>
            <p>Todos los cupos han vuelto a 0.</p>
            <p>La base de datos está limpia para nuevas pruebas.</p>
            <a href="/" style="font-size:20px;">Volver al Inicio</a>
        </div>
        """
    except Exception as e:
        return f"Error reseteando DB: {str(e)}"

@app.route('/api/tutors', methods=['GET'])
def get_tutors():
    level = request.args.get('level') 
    if level not in CAPACIDAD:
        return jsonify({"error": "Nivel inválido"}), 400

    tutors = Tutor.query.order_by(Tutor.name).all()
    disponibles = []
    
    for t in tutors:
        tomados = getattr(t, f"taken_{level}") 
        # Director Odin tiene capacidad 0, el resto usa la constante
        maximo = 0 if "Odin Rodríguez Mercado" in t.name else CAPACIDAD[level]
        
        # Solo mostramos si hay cupo
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

    campo_cupo = f"taken_{level}"
    tomados = getattr(tutor, campo_cupo)
    maximo = 0 if "Odin Rodríguez Mercado" in tutor.name else CAPACIDAD[level]

    # VALIDACIÓN DE CONCURRENCIA
    if tomados >= maximo:
        return jsonify({"error": "¡Ups! Alguien ganó el cupo hace un segundo."}), 409

    # GUARDAR EN BASE DE DATOS
    setattr(tutor, campo_cupo, tomados + 1)
    db.session.commit()
    
    # GENERAR PDF
    try:
        pdf_file = generar_carta_pdf(data.get('nombre'), data.get('registro'), data.get('carnet'), level, tutor.name)
        return jsonify({
            "mensaje": "Solicitud exitosa",
            "pdf_url": f"/descargar/{pdf_file}"
        })
    except Exception as e:
        # Rollback manual si falla el PDF
        setattr(tutor, campo_cupo, tomados)
        db.session.commit()
        return jsonify({"error": str(e)}), 500

@app.route('/descargar/<filename>')
def descargar_archivo(filename):
    path = os.path.join(os.getcwd(), filename)
    return send_file(path, as_attachment=True)

# --- 7. GENERADOR PDF (DISEÑO TABLA) ---
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
    pdf.multi_cell(0, 8, "De mi mayor consideración:\n\nMediante la presente, solicito formalmente la asignación de tutoría para la materia de Practicum. A continuación detallo mis datos y el docente seleccionado:"); pdf.ln(10)
    
    # TABLA DE DATOS
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
