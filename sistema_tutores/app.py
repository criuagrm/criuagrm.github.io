from flask import Flask, jsonify, request, send_file, render_template
from fpdf import FPDF
import datetime
import os

app = Flask(__name__)

# --- CONFIGURACIÓN DE LOGÍSTICA ---
CAPACIDAD_POR_NIVEL = {
    "II": 5, "III": 3, "IV": 2    
}

# --- DATOS COMPLETOS DE DOCENTES (Nombre, Tel, Email) ---
datos_docentes = [
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

# Inicialización de DB
tutors_db = []
for i, docente in enumerate(datos_docentes, start=1):
    nombre = docente["nombre"]
    es_director = "Odin Rodríguez Mercado" in nombre
    capacidad = {k: 0 for k in CAPACIDAD_POR_NIVEL} if es_director else CAPACIDAD_POR_NIVEL.copy()
    
    tutors_db.append({
        "id": i,
        "name": nombre,
        "phone": docente["tel"],
        "email": docente["email"],
        "slots": {
            "II":  {"capacity": capacidad["II"], "taken": 0},
            "III": {"capacity": capacidad["III"], "taken": 0},
            "IV":  {"capacity": capacidad["IV"], "taken": 0}
        }
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tutors', methods=['GET'])
def get_tutors():
    level = request.args.get('level') 
    if level not in CAPACIDAD_POR_NIVEL:
        return jsonify({"error": "Nivel inválido"}), 400

    disponibles = []
    for tutor in tutors_db:
        info_cupo = tutor['slots'][level]
        if info_cupo['taken'] < info_cupo['capacity']:
            disponibles.append({
                "id": tutor['id'],
                "name": tutor['name'],
                "phone": tutor['phone'],
                "email": tutor['email'],
                "cupos_disponibles": info_cupo['capacity'] - info_cupo['taken'],
                "cupos_totales": info_cupo['capacity']
            })
    disponibles.sort(key=lambda x: x['name'])
    return jsonify(disponibles)

@app.route('/api/solicitar', methods=['POST'])
def solicitar_tutor():
    data = request.json
    tutor_id = data.get('tutor_id')
    level = data.get('nivel')
    nombre_est = data.get('nombre')
    registro_est = data.get('registro')
    carnet_est = data.get('carnet')

    tutor = next((t for t in tutors_db if t['id'] == tutor_id), None)
    if not tutor: return jsonify({"error": "Tutor no encontrado"}), 404

    cupo_actual = tutor['slots'][level]
    if cupo_actual['taken'] >= cupo_actual['capacity']:
        return jsonify({"error": "Cupo lleno."}), 409

    cupo_actual['taken'] += 1
    
    try:
        pdf_file = generar_carta_pdf(nombre_est, registro_est, carnet_est, level, tutor['name'])
        return jsonify({
            "mensaje": "Solicitud exitosa",
            "pdf_url": f"/descargar/{pdf_file}"
        })
    except Exception as e:
        cupo_actual['taken'] -= 1
        return jsonify({"error": str(e)}), 500

@app.route('/descargar/<filename>')
def descargar_archivo(filename):
    path = os.path.join(os.getcwd(), filename)
    return send_file(path, as_attachment=True)

# --- GENERADOR PDF ESTILO TABLA ---
def generar_carta_pdf(nombre, registro, carnet, nivel, nombre_tutor):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # Fecha
    fecha = datetime.datetime.now().strftime("%d de %B de %Y")
    pdf.cell(0, 10, txt=f"Santa Cruz, {fecha}", ln=1, align='R')
    pdf.ln(10)
    
    # Destinatario
    pdf.set_font("Arial", 'B', size=11)
    pdf.cell(0, 5, txt="Señor:", ln=1)
    pdf.cell(0, 5, txt="Lic. Odin Rodríguez Mercado", ln=1)
    pdf.cell(0, 5, txt="DIRECTOR DE CARRERA CIENCIA POLÍTICA Y ADM. PÚBLICA", ln=1)
    pdf.cell(0, 5, txt="Presente.-", ln=1)
    pdf.ln(15)
    
    # Referencia
    pdf.cell(0, 10, txt=f"REF: SOLICITUD DE TUTOR PARA PRACTICUM {nivel}", ln=1, align='R')
    pdf.ln(10)
    
    # Cuerpo Intro
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, "De mi mayor consideración:\n\nMediante la presente, solicito formalmente la asignación de tutoría para la materia de Practicum. A continuación detallo mis datos y el docente seleccionado:")
    pdf.ln(10)

    # --- TABLA DE DATOS ---
    pdf.set_fill_color(240, 240, 240) # Gris suave para encabezados
    pdf.set_font("Arial", 'B', size=10)
    
    # Anchos de columnas
    w_label = 60
    w_data = 130
    h_row = 10

    # Fila 1: Estudiante
    pdf.cell(w_label, h_row, "NOMBRE ESTUDIANTE:", 1, 0, 'L', True)
    pdf.set_font("Arial", size=10)
    pdf.cell(w_data, h_row, nombre.upper(), 1, 1, 'L')

    # Fila 2: Registro
    pdf.set_font("Arial", 'B', size=10)
    pdf.cell(w_label, h_row, "REGISTRO UNIVERSITARIO:", 1, 0, 'L', True)
    pdf.set_font("Arial", size=10)
    pdf.cell(w_data, h_row, str(registro), 1, 1, 'L')

    # Fila 3: Carnet
    pdf.set_font("Arial", 'B', size=10)
    pdf.cell(w_label, h_row, "CÉDULA DE IDENTIDAD:", 1, 0, 'L', True)
    pdf.set_font("Arial", size=10)
    pdf.cell(w_data, h_row, str(carnet), 1, 1, 'L')

    # Fila 4: Nivel
    pdf.set_font("Arial", 'B', size=10)
    pdf.cell(w_label, h_row, "MATERIA:", 1, 0, 'L', True)
    pdf.set_font("Arial", size=10)
    pdf.cell(w_data, h_row, f"PRACTICUM {nivel}", 1, 1, 'L')

    # Fila 5: Tutor
    pdf.set_font("Arial", 'B', size=10)
    pdf.cell(w_label, h_row, "TUTOR SOLICITADO:", 1, 0, 'L', True)
    pdf.set_font("Arial", size=10)
    pdf.cell(w_data, h_row, nombre_tutor.upper(), 1, 1, 'L')
    
    pdf.ln(20)
    pdf.multi_cell(0, 8, "Sin otro particular, saludo a usted atentamente.")
    pdf.ln(30)
    
    # Firma Simple
    pdf.cell(0, 5, txt="__________________________", ln=1, align='C')
    pdf.cell(0, 5, txt=f"{nombre}", ln=1, align='C')
    pdf.cell(0, 5, txt=f"C.I. {carnet}", ln=1, align='C')

    # (SE ELIMINÓ EL CUADRO DE APROBADO/OBSERVADO COMO PEDISTE)

    filename = f"solicitud_{registro}_{nivel}.pdf"
    pdf.output(filename)
    return filename

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)