from flask import Flask, jsonify, request, send_file, render_template
from fpdf import FPDF
import datetime
import os

app = Flask(__name__)

# --- CONFIGURACIÓN DE LOGÍSTICA (CUPOS) ---
# Practicum II (5), III (3), IV (2)
CAPACIDAD_POR_NIVEL = {
    "II": 5,   
    "III": 3,  
    "IV": 2    
}

# --- LISTA OFICIAL DE DOCENTES ---
nombres_docentes = [
    "Alejandro Mansilla Arias", "Alfredo Víctor Copaz Pacheco", "Armengol Vaca Flores",
    "Berman Saucedo Campos", "Cecilia Rua Heredia", "Daniel Valverde Aparicio",
    "Edwin Javier Alarcón Vásquez", "Francisco Méndez Egüez", "Grover Núñez Klinsky",
    "Javier Hernández Serrano", "Juan Rubén Cabello Mérida", "José Luis Andia Fernández",
    "Julio Guzmán Gutiérrez", "Jorge Espinoza Moreno", "Jorge Francisco Rojas Bonilla",
    "Leo Ricardo Klinsky Marín", "Marcelo Arrazola Weise", "Ma. Hortencia Ayala De Fernández",
    "Manfredo Rafael Bravo Chávez", "Mario Campos Barrera", "Maria Rosario Chávez Vaca",
    "Maria Elizabeth Galarza De Eid", "Menacho Manfredo", "Maria Angélica Suárez",
    "Marcio Aranda García", "Marco Antonio Torrez Valverde", "Nicolás Ribera Cardozo",
    "Oswaldo Martorell Roca", "Odin Rodríguez Mercado", "Paula Alejandra Peña Hasbun",
    "Reymi Luis Ferreira Justiniano", "Ricardo Pérez Peredo", "Roger Emilio Tuero Velásquez",
    "Sarah Gutiérrez Mendoza"
]

# Inicializamos la base de datos en memoria
tutors_db = []
for i, nombre in enumerate(nombres_docentes, start=1):
    # El Director Odin (ID 29) se inicializa con 0 cupos (bloqueado por defecto para casos especiales)
    es_director = "Odin Rodríguez Mercado" in nombre
    
    capacidad = {k: 0 for k in CAPACIDAD_POR_NIVEL} if es_director else CAPACIDAD_POR_NIVEL.copy()
    
    tutors_db.append({
        "id": i,
        "name": nombre,
        "is_director": es_director,
        "slots": {
            "II":  {"capacity": capacidad["II"], "taken": 0},
            "III": {"capacity": capacidad["III"], "taken": 0},
            "IV":  {"capacity": capacidad["IV"], "taken": 0}
        }
    })

# --- RUTAS DEL SISTEMA ---

@app.route('/')
def index():
    # AQUI ESTA EL CAMBIO: Ahora carga el HTML de la carpeta templates
    return render_template('index.html')

@app.route('/api/tutors', methods=['GET'])
def get_tutors():
    # El estudiante pide lista para su nivel (ej: ?level=III)
    level = request.args.get('level') 
    
    if level not in CAPACIDAD_POR_NIVEL:
        return jsonify({"error": "Nivel inválido. Use II, III o IV"}), 400

    disponibles = []
    for tutor in tutors_db:
        info_cupo = tutor['slots'][level]
        # Solo mostramos al docente si tiene espacio (tomados < capacidad)
        if info_cupo['taken'] < info_cupo['capacity']:
            disponibles.append({
                "id": tutor['id'],
                "name": tutor['name'],
                "cupos_disponibles": info_cupo['capacity'] - info_cupo['taken'],
                "cupos_totales": info_cupo['capacity']
            })
            
    # Ordenamos alfabéticamente
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

    # 1. Buscar al tutor
    tutor = next((t for t in tutors_db if t['id'] == tutor_id), None)
    if not tutor:
        return jsonify({"error": "Tutor no encontrado"}), 404

    # 2. VALIDAR CUPO (Evita conflictos de concurrencia)
    cupo_actual = tutor['slots'][level]
    if cupo_actual['taken'] >= cupo_actual['capacity']:
        return jsonify({"error": "¡Lo sentimos! Este cupo se llenó hace un instante."}), 409

    # 3. ASIGNAR CUPO
    cupo_actual['taken'] += 1
    
    # 4. GENERAR PDF
    try:
        pdf_file = generar_carta_pdf(nombre_est, registro_est, carnet_est, level, tutor['name'])
        
        # URL para descargar el PDF (render usa HTTPS por defecto)
        download_url = f"/descargar/{pdf_file}"
        
        return jsonify({
            "mensaje": "Solicitud exitosa",
            "tutor": tutor['name'],
            "pdf_url": download_url
        })
    except Exception as e:
        cupo_actual['taken'] -= 1 # Revertimos el cupo si falla el PDF
        return jsonify({"error": str(e)}), 500

@app.route('/descargar/<filename>')
def descargar_archivo(filename):
    path = os.path.join(os.getcwd(), filename)
    return send_file(path, as_attachment=True)

# --- GENERADOR DE CARTAS PDF ---
def generar_carta_pdf(nombre, registro, carnet, nivel, nombre_tutor):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", size=11)
    
    # Fecha
    fecha = datetime.datetime.now().strftime("%d de %B de %Y")
    pdf.cell(0, 10, txt=f"Santa Cruz, {fecha}", ln=1, align='R')
    pdf.ln(10)
    
    # Encabezado (Director Odin)
    pdf.set_font("Arial", 'B', size=11)
    pdf.cell(0, 5, txt="Señor:", ln=1)
    pdf.cell(0, 5, txt="Lic. Odin Rodríguez Mercado", ln=1)
    pdf.cell(0, 5, txt="DIRECTOR DE CARRERA CIENCIA POLÍTICA Y ADM. PÚBLICA", ln=1)
    pdf.cell(0, 5, txt="Presente.-", ln=1)
    pdf.ln(15)
    
    # Referencia
    pdf.cell(0, 10, txt=f"REF: SOLICITUD DE TUTOR PARA PRACTICUM {nivel}", ln=1, align='R')
    pdf.ln(5)
    
    # Cuerpo
    pdf.set_font("Arial", size=11)
    texto = (
        f"De mi mayor consideración:\n\n"
        f"Mediante la presente, yo {nombre}, con Registro Universitario N° {registro} "
        f"y C.I. {carnet}, estudiante regular de la materia Practicum {nivel}, "
        f"solicito respetuosamente la designación del docente:\n\n"
        f"LIC. {nombre_tutor.upper()}\n\n"
        f"Como mi tutor guía para el desarrollo de mi trabajo de investigación en el presente semestre.\n\n"
        f"Sin otro particular, saludo a usted atentamente."
    )
    pdf.multi_cell(0, 8, texto)
    pdf.ln(30)
    
    # Firmas
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="__________________________", ln=1, align='C')
    pdf.cell(0, 5, txt=f"{nombre}", ln=1, align='C')
    pdf.cell(0, 5, txt=f"C.I. {carnet}", ln=1, align='C')
    pdf.ln(20)
    
    # Caja de validación administrativa
    pdf.set_font("Arial", 'I', size=8)
    pdf.cell(0, 5, txt="ESPACIO RESERVADO PARA DIRECCIÓN DE CARRERA", ln=1, align='L')
    pdf.cell(0, 12, txt="[  ] APROBADO    [  ] OBSERVADO", border=1, ln=1, align='C')

    nombre_archivo = f"solicitud_{registro}_{nivel}.pdf"
    pdf.output(nombre_archivo)
    return nombre_archivo

if __name__ == '__main__':
    # Configuración para que funcione tanto local como en Render
    app.run(host='0.0.0.0', port=5000)