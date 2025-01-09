import plotly.graph_objects as go

# Datos de la encuesta
estudiantes = {
    "Ns/Nc": 37.25,
    "Carlos Martínez": 17.25,
    "Reinerio Vargas": 12.5,
    "Juana Borja": 7.25,
    "Oscar Nogales": 5.5,
    "Orlando Pedraza": 5.25,
    "Alfonso Coca": 3.75,
    "Rogelio Espinoza": 3.75,
    "Sarah Gutiérrez": 3.25,
    "Roque Méndez": 3.0,
    "Oswaldo Ulloa": 1.25
}

docentes = {
    "Ns/Nc": 28.18,
    "Carlos Martínez": 25.76,
    "Reinerio Vargas": 11.21,
    "Juana Borja": 6.67,
    "Oscar Nogales": 6.36,
    "Orlando Pedraza": 4.24,
    "Alfonso Coca": 4.24,
    "Rogelio Espinoza": 3.94,
    "Sarah Gutiérrez": 3.94,
    "Roque Méndez": 3.03,
    "Oswaldo Ulloa": 2.42
}

# Crear la gráfica
fig = go.Figure()

fig.add_trace(go.Bar(
    x=list(estudiantes.keys()),
    y=list(estudiantes.values()),
    name='Estudiantes',
    marker_color='blue'
))

fig.add_trace(go.Bar(
    x=list(docentes.keys()),
    y=list(docentes.values()),
    name='Docentes',
    marker_color='orange'
))

# Configuración de la gráfica
fig.update_layout(
    title='Resultados de la Encuesta - Preferencias para Rector',
    xaxis_title='Candidatos',
    yaxis_title='Porcentaje (%)',
    barmode='group',
    template='plotly_white'
)

# Guardar la gráfica como archivo HTML
fig.write_html("grafica_interactiva.html")
