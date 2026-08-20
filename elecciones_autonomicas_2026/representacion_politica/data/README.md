# Datos del dashboard de representación política

Los archivos de esta carpeta son artefactos reproducibles generados por `../tools/build-data.mjs`.

- `departamento.geojson`: límite departamental con resumen censal y electoral.
- `provincias.geojson`: 15 provincias construidas agrupando las geometrías municipales por provincia, sin modificar las coordenadas originales.
- `municipios.geojson`: 56 municipios con cantidades oficiales, universos de referencia y proporciones de migración de toda la vida y reciente, además de Censo 2024, padrón 2026 y lectura electoral preliminar.
- `recintos.geojson`: 1.138 recintos electorales; nueve coordenadas estimadas se identifican explícitamente.
- `dashboard.json`: indicadores departamentales, metropolitanos, escenarios de representación y advertencias metodológicas.

La capa censal de 61.335 manzanos no se duplica. El dashboard reutiliza `../../../censo_2024/manzanos.geojson` y `../../../censo_2024/campos.json`, cargándolos únicamente cuando la persona activa esa capa.

La cantidad de migrantes por manzano es un indicador derivado para visualización: `población del manzano × proporción migrante`. Solo se calcula en los 35.743 manzanos que contienen `h1`; los demás se muestran como “sin dato” y no como cero. Esta estimación no debe sumarse para producir totales oficiales municipales.

## Principio metodológico

El dashboard separa hechos observados, simulaciones institucionales e hipótesis. La definición de migrante depende de la escala: fuera del departamento en el agregado departamental y fuera del municipio actual en las fichas municipales. Las asociaciones municipales entre migración y voto son exploratorias y no permiten inferir causalidad individual.
