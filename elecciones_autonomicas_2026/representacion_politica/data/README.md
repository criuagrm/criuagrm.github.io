# Datos del dashboard de representación política

Los archivos de esta carpeta son artefactos reproducibles generados por `../tools/build-data.mjs`.

- `departamento.geojson`: límite departamental con resumen censal y electoral.
- `provincias.geojson`: 15 provincias construidas agrupando las geometrías municipales por provincia, sin modificar las coordenadas originales.
- `municipios.geojson`: 56 municipios con indicadores del Censo 2024, padrón 2026, migración y lectura electoral preliminar.
- `recintos.geojson`: 1.138 recintos electorales; nueve coordenadas estimadas se identifican explícitamente.
- `dashboard.json`: indicadores departamentales, metropolitanos, escenarios de representación y advertencias metodológicas.

La capa censal de 61.335 manzanos no se duplica. El dashboard reutiliza `../../../censo_2024/manzanos.geojson` y `../../../censo_2024/campos.json`, cargándolos únicamente cuando la persona activa esa capa.

## Principio metodológico

El dashboard separa hechos observados, simulaciones institucionales e hipótesis. Las asociaciones municipales entre migración y voto son exploratorias y no permiten inferir causalidad individual.
