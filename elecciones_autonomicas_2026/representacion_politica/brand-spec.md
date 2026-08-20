# Especificación de marca — Dashboard de representación política

## Modo de trabajo

- Clasificación: extensión del Monitor de Elecciones Autonómicas 2026.
- Fidelidad: 10/10. La nueva página debe percibirse como parte del portal CIRCPyCS.
- Contratos protegidos: logo, nombre institucional, rutas existentes, navegación del Monitor, enlaces institucionales y contenido del footer.

## Activos reales

- Logo institucional local: `assets/circpycs-brand/logo.png`.
- Fuente original utilizada por el portal: `https://i.imgur.com/ldeXZmG.png`.
- Página institucional de referencia: `../../index.html`.
- Monitor electoral de referencia: `../index.html`.
- Atlas censal de referencia: `../../censo_2024/index.html`.
- Footer institucional de referencia: `../../_includes/footer.html`.

## Sistema visual

- Azul cartográfico principal: `#004494`.
- Verde institucional y área metropolitana: `#059669`.
- Celeste de apoyo: `#0284c7`.
- Brecha o subrepresentación: `#e11d48`.
- Datos estimados o advertencias: `#f59e0b`.
- Texto principal: `#0f172a`.
- Texto secundario: `#475569`.
- Fondo: `#f8fafc`.
- Superficie: `#ffffff`.
- Bordes: `#e2e8f0`.
- Tipografía: Inter, conservando el sistema actual del portal.
- Espaciado: base de 4 px, con ritmo principal de 8 px.
- Radios: 8 px para controles y 12 px para superficies analíticas.
- Sombras: mínimas y reservadas para elementos flotantes del mapa.
- Movimiento: 160–220 ms para feedback de selección; debe respetar `prefers-reduced-motion`.

## Uso semántico del color

- Los colores partidarios solo se usarán cuando se visualicen resultados electorales.
- La representación territorial se codificará con una escala divergente acompañada por etiquetas y patrones; el color nunca será el único medio de lectura.
- Los nueve recintos con georreferencia estimada usarán ámbar, un símbolo distinto y una advertencia metodológica.

## Datos previstos

- Límite departamental: `scz_departamento.json`.
- Municipios: `scz_municipios.json` (56 polígonos y campo provincial).
- Provincias: 15 geometrías derivadas de la disolución de los polígonos municipales por `NOM_PROV`.
- Recintos: `Recintos_Santa_Cruz_2026_geografia_completa_estimativa.geojson` (1.138 puntos).
- Censo por manzano: `censo_2024/manzanos.geojson`, conservando el nivel de detalle actual y cargándose bajo demanda.
- Indicadores: base electoral-censal, migración municipal y escenarios de representación ya procesados.

## Footer

Debe conservar la estructura de cuatro columnas del Centro: identidad, enlaces rápidos, contacto y redes; además del descargo institucional, privacidad y términos.
