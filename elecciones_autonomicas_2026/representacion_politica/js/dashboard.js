(() => {
  "use strict";

  const DATA_PATHS = {
    dashboard: "representacion_politica/data/dashboard.json",
    department: "representacion_politica/data/departamento.geojson",
    provinces: "representacion_politica/data/provincias.geojson",
    municipalities: "representacion_politica/data/municipios.geojson",
    precincts: "representacion_politica/data/recintos.geojson",
    census: "../censo_2024/manzanos.geojson",
    censusFields: "../censo_2024/campos.json"
  };

  const PALETTES = {
    blue: ["#dbeafe", "#93c5fd", "#38bdf8", "#0284c7", "#004494"],
    green: ["#d1fae5", "#6ee7b7", "#10b981", "#047857", "#065f46"],
    divergent: ["#e11d48", "#f59e0b", "#cbd5e1", "#38bdf8", "#059669"]
  };

  const METRICS = {
    provinces: [
      { key: "territorial_representation_index_population", label: "Índice de representación · población", kind: "ratio", palette: "divergent", breaks: [0.25, 0.5, 0.85, 1.15] },
      { key: "population_2024", label: "Población 2024", kind: "number", palette: "blue" },
      { key: "registered_2026", label: "Padrón 2026", kind: "number", palette: "green" },
      { key: "population_share", label: "Participación en la población", kind: "percent", palette: "blue" },
      { key: "registered_share", label: "Participación en el padrón", kind: "percent", palette: "green" },
      { key: "population_per_territorial_seat", label: "Habitantes por escaño territorial", kind: "number", palette: "divergent" }
    ],
    municipalities: [
      { key: "population_2024", label: "Población 2024", kind: "number", palette: "blue" },
      { key: "registered_2026", label: "Padrón 2026", kind: "number", palette: "green" },
      { key: "lifetime_immigrant_share", label: "Inmigración de toda la vida", kind: "percent", palette: "green" },
      { key: "recent_immigrant_share", label: "Inmigración reciente", kind: "percent", palette: "green" },
      { key: "libre_share", label: "Voto LIBRE · lectura preliminar", kind: "percent", palette: "blue" },
      { key: "participation", label: "Participación electoral", kind: "percent", palette: "blue" }
    ],
    precincts: [
      { key: "registered_2026", label: "Personas habilitadas", kind: "number", palette: "blue" },
      { key: "tables_2026", label: "Mesas electorales", kind: "number", palette: "green" }
    ],
    census: [
      { key: "a1", label: "Población del manzano", kind: "number", palette: "blue" },
      { key: "b1", label: "Densidad · habitantes por hectárea", kind: "number", palette: "blue" },
      { key: "h1", label: "Población migrante", kind: "percent", palette: "green" },
      { key: "g1", label: "Educación superior", kind: "percent", palette: "blue" },
      { key: "b2", label: "Viviendas con internet", kind: "percent", palette: "green" }
    ]
  };

  const state = {
    map: null,
    dashboard: null,
    geojson: {},
    leafletLayers: {},
    mainLayer: null,
    departmentLayer: null,
    metroLayer: null,
    activeLayer: "provinces",
    activeMetric: METRICS.provinces[0].key,
    breaks: [],
    mode: "evidence",
    selected: null,
    showMetro: true,
    showEstimated: true,
    censusLoaded: false,
    searchItems: []
  };

  const elements = {};
  const numberFormatter = new Intl.NumberFormat("es-BO", { maximumFractionDigits: 0 });
  const decimalFormatter = new Intl.NumberFormat("es-BO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function normalized(value = "") {
    return String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  function escapeHtml(value = "") {
    return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
  }

  function finite(value) {
    return Number.isFinite(Number(value));
  }

  function formatNumber(value) {
    return finite(value) ? numberFormatter.format(Number(value)) : "s/d";
  }

  function formatPercent(value, digits = 1) {
    if (!finite(value)) return "s/d";
    return new Intl.NumberFormat("es-BO", { style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value));
  }

  function formatRatio(value) {
    return finite(value) ? decimalFormatter.format(Number(value)) : "s/d";
  }

  function formatMetric(value, metric = currentMetric()) {
    if (!metric) return formatNumber(value);
    if (metric.kind === "percent") return formatPercent(value);
    if (metric.kind === "ratio") return formatRatio(value);
    return formatNumber(value);
  }

  function currentMetric() {
    return METRICS[state.activeLayer].find((metric) => metric.key === state.activeMetric) || METRICS[state.activeLayer][0];
  }

  function cacheElements() {
    [
      "metric-select", "geography-search", "geography-options", "metro-toggle", "estimated-toggle",
      "map-breadcrumb", "map-status", "map-legend", "legend-title", "legend-scale", "legend-min", "legend-max",
      "map-message", "message-title", "message-copy", "loading-progress", "selection-kicker", "selection-title",
      "selection-subtitle", "panel-content", "theme-toggle", "migration-scatter", "correlation-caption"
    ].forEach((id) => { elements[id] = document.getElementById(id); });
  }

  function showMessage(title, copy, progress = 18) {
    elements["message-title"].textContent = title;
    elements["message-copy"].textContent = copy;
    elements["loading-progress"].style.width = `${Math.max(6, Math.min(100, progress))}%`;
    elements["map-message"].hidden = false;
  }

  function hideMessage() {
    elements["map-message"].hidden = true;
  }

  function setStatus(message) {
    elements["map-status"].textContent = message;
  }

  async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${url}`);
    return response.json();
  }

  async function fetchJsonWithProgress(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${url}`);
    if (!response.body || !response.body.getReader) return response.json();

    const total = Number(response.headers.get("content-length")) || 0;
    const reader = response.body.getReader();
    const chunks = [];
    let loaded = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      loaded += value.byteLength;
      const megabytes = (loaded / 1048576).toFixed(1);
      const progress = total ? 8 + (loaded / total) * 74 : Math.min(78, 8 + loaded / 700000);
      showMessage("Cargando 61.335 manzanos", `${megabytes} MB recibidos. Esta descarga ocurre solo una vez.`, progress);
    }

    const blob = new Blob(chunks, { type: "application/json" });
    return JSON.parse(await blob.text());
  }

  function initializeMap() {
    state.map = L.map("representation-map", {
      center: [-17.75, -63.2],
      zoom: 6,
      minZoom: 5,
      preferCanvas: true,
      zoomControl: true
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(state.map);

    const resizeObserver = new ResizeObserver(() => state.map.invalidateSize({ pan: false }));
    resizeObserver.observe(document.getElementById("map-stage"));
  }

  function featureName(layerKey, properties) {
    if (layerKey === "provinces") return properties.province;
    if (layerKey === "municipalities") return properties.municipality;
    if (layerKey === "precincts") return properties.precinct;
    return "Manzano censal";
  }

  function computeBreaks(featureCollection, metric) {
    if (metric.breaks) return [...metric.breaks];
    const values = featureCollection.features
      .map((feature) => Number(feature.properties?.[metric.key]))
      .filter(Number.isFinite)
      .sort((a, b) => a - b);
    if (!values.length) return [0, 0, 0, 0];
    const quantile = (share) => values[Math.min(values.length - 1, Math.floor((values.length - 1) * share))];
    return [quantile(.2), quantile(.4), quantile(.6), quantile(.8)];
  }

  function paletteColor(value, metric = currentMetric()) {
    if (!finite(value)) return "#cbd5e1";
    const palette = PALETTES[metric.palette] || PALETTES.blue;
    const numeric = Number(value);
    const index = numeric <= state.breaks[0] ? 0 : numeric <= state.breaks[1] ? 1 : numeric <= state.breaks[2] ? 2 : numeric <= state.breaks[3] ? 3 : 4;
    return palette[index];
  }

  function territoryStyle(feature) {
    const selected = state.selected?.feature === feature;
    return {
      color: selected ? "#0f172a" : "#ffffff",
      weight: selected ? 3 : 1.1,
      opacity: .95,
      fillColor: paletteColor(feature.properties?.[state.activeMetric]),
      fillOpacity: .78
    };
  }

  function censusStyle(feature) {
    const selected = state.selected?.feature === feature;
    return {
      color: selected ? "#0f172a" : "#ffffff",
      weight: selected ? 2 : .35,
      opacity: .75,
      fillColor: paletteColor(feature.properties?.[state.activeMetric]),
      fillOpacity: .72
    };
  }

  function precinctStyle(feature) {
    const estimated = Boolean(feature.properties?.estimated_coordinate);
    const selected = state.selected?.feature === feature;
    return {
      color: selected ? "#0f172a" : estimated ? "#92400e" : "#ffffff",
      weight: selected ? 3 : estimated ? 2 : 1,
      fillColor: estimated ? "#f59e0b" : "#004494",
      fillOpacity: .82
    };
  }

  function tooltipMarkup(layerKey, feature) {
    const properties = feature.properties || {};
    const value = properties[state.activeMetric];
    return `<strong>${escapeHtml(featureName(layerKey, properties))}</strong><br>${escapeHtml(currentMetric().label)}: ${escapeHtml(formatMetric(value))}`;
  }

  function bindTerritoryEvents(layerKey, feature, layer) {
    layer.bindTooltip(() => tooltipMarkup(layerKey, feature), { sticky: true, direction: "top" });
    layer.on("click", () => selectFeature(layerKey, feature, layer));
    layer.on("mouseover", () => {
      if (layer.setStyle) layer.setStyle({ weight: 3, color: "#0f172a" });
      if (layer.bringToFront) layer.bringToFront();
    });
    layer.on("mouseout", () => {
      if (!layer.setStyle) return;
      if (layerKey === "census") layer.setStyle(censusStyle(feature));
      else if (layerKey === "precincts") layer.setStyle(precinctStyle(feature));
      else layer.setStyle(territoryStyle(feature));
    });
  }

  function createTerritoryLayer(layerKey, featureCollection) {
    const renderer = L.canvas({ padding: .4, tolerance: 5 });
    return L.geoJSON(featureCollection, {
      renderer,
      style: layerKey === "census" ? censusStyle : territoryStyle,
      onEachFeature: (feature, layer) => bindTerritoryEvents(layerKey, feature, layer)
    });
  }

  function createPrecinctLayer(featureCollection) {
    const renderer = L.canvas({ padding: .5, tolerance: 8 });
    return L.geoJSON(featureCollection, {
      renderer,
      filter: (feature) => state.showEstimated || !feature.properties.estimated_coordinate,
      pointToLayer: (feature, latlng) => {
        const properties = feature.properties;
        const value = Number(properties[state.activeMetric]) || 0;
        const radius = Math.max(3, Math.min(13, Math.sqrt(Math.max(value, 1)) / 8));
        return L.circleMarker(latlng, {
          renderer,
          radius,
          ...precinctStyle(feature)
        });
      },
      onEachFeature: (feature, layer) => bindTerritoryEvents("precincts", feature, layer)
    });
  }

  function addDepartmentOutline() {
    state.departmentLayer = L.geoJSON(state.geojson.department, {
      interactive: false,
      style: { color: "#334155", weight: 2, opacity: .8, fillOpacity: 0 }
    }).addTo(state.map);
  }

  async function ensureMunicipalities() {
    if (!state.geojson.municipalities) {
      state.geojson.municipalities = await fetchJson(DATA_PATHS.municipalities);
      indexSearchItems("municipalities", state.geojson.municipalities);
    }
    if (!state.metroLayer) {
      state.metroLayer = L.geoJSON(state.geojson.municipalities, {
        filter: (feature) => feature.properties.metropolitan,
        interactive: false,
        style: { color: "#059669", weight: 3.5, opacity: .95, dashArray: "8 5", fillColor: "#059669", fillOpacity: .055 }
      });
      if (state.showMetro) state.metroLayer.addTo(state.map);
    }
    return state.geojson.municipalities;
  }

  async function ensurePrecincts() {
    if (!state.geojson.precincts) {
      state.geojson.precincts = await fetchJson(DATA_PATHS.precincts);
      indexSearchItems("precincts", state.geojson.precincts);
    }
    return state.geojson.precincts;
  }

  async function ensureCensus() {
    if (state.censusLoaded) return state.geojson.census;
    showMessage("Cargando la capa censal", "El archivo conserva los 61.335 manzanos del Atlas actual.", 8);
    const [census, fields] = await Promise.all([
      fetchJsonWithProgress(DATA_PATHS.census),
      fetchJson(DATA_PATHS.censusFields)
    ]);
    state.geojson.census = census;
    state.censusFields = fields;
    state.censusLoaded = true;
    showMessage("Preparando el mapa censal", "Aplicando el indicador seleccionado a los 61.335 manzanos.", 88);
    await new Promise((resolve) => setTimeout(resolve, 30));
    return census;
  }

  async function ensureLayerData(layerKey) {
    if (state.geojson[layerKey]) return state.geojson[layerKey];
    if (layerKey === "municipalities") return ensureMunicipalities();
    if (layerKey === "precincts") return ensurePrecincts();
    if (layerKey === "census") return ensureCensus();
    state.geojson[layerKey] = await fetchJson(DATA_PATHS[layerKey]);
    return state.geojson[layerKey];
  }

  function configureMetricSelect(layerKey) {
    const metrics = METRICS[layerKey];
    elements["metric-select"].replaceChildren(...metrics.map((metric) => {
      const option = document.createElement("option");
      option.value = metric.key;
      option.textContent = metric.label;
      return option;
    }));
    state.activeMetric = metrics[0].key;
    elements["metric-select"].value = state.activeMetric;
  }

  function updateLegend(featureCollection) {
    const metric = currentMetric();
    state.breaks = computeBreaks(featureCollection, metric);
    elements["legend-title"].textContent = metric.label;
    const values = featureCollection.features.map((feature) => Number(feature.properties?.[metric.key])).filter(Number.isFinite);
    const minimum = values.length ? Math.min(...values) : 0;
    const maximum = values.length ? Math.max(...values) : 0;
    elements["legend-min"].textContent = formatMetric(minimum, metric);
    elements["legend-max"].textContent = formatMetric(maximum, metric);
    const palette = PALETTES[metric.palette] || PALETTES.blue;
    [...elements["legend-scale"].children].forEach((segment, index) => { segment.style.background = palette[index]; });
  }

  function rebuildActiveLayer() {
    const data = state.geojson[state.activeLayer];
    if (!data) return;
    if (state.mainLayer) state.map.removeLayer(state.mainLayer);
    state.mainLayer = state.activeLayer === "precincts" ? createPrecinctLayer(data) : createTerritoryLayer(state.activeLayer, data);
    state.leafletLayers[state.activeLayer] = state.mainLayer;
    state.mainLayer.addTo(state.map);
    if (state.departmentLayer) state.departmentLayer.bringToFront();
    if (state.metroLayer && state.showMetro) state.metroLayer.bringToFront();
  }

  async function activateLayer(layerKey, fit = true) {
    state.activeLayer = layerKey;
    state.selected = null;
    document.querySelectorAll("[data-layer]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.layer === layerKey)));
    elements["estimated-toggle"].hidden = layerKey !== "precincts";
    configureMetricSelect(layerKey);
    elements["map-breadcrumb"].textContent = `Santa Cruz / ${{ provinces: "Provincias", municipalities: "Municipios", precincts: "Recintos 2026", census: "Censo 2024 / Manzanos" }[layerKey]}`;
    setStatus(layerKey === "census" ? "La capa censal se carga bajo demanda." : "Cargando capa territorial…");

    try {
      const data = await ensureLayerData(layerKey);
      updateLegend(data);
      rebuildActiveLayer();
      if (fit && state.mainLayer.getBounds?.().isValid()) state.map.fitBounds(state.mainLayer.getBounds(), { padding: [18, 18] });
      hideMessage();
      setStatus(statusMessage(layerKey, data));
      renderDefaultSelection();
    } catch (error) {
      console.error(error);
      showMessage("No se pudo cargar la capa", "Revise la conexión o intente nuevamente.", 100);
      setStatus(`Error: ${error.message}`);
    }
  }

  function statusMessage(layerKey, data) {
    if (layerKey === "provinces") return `${data.features.length} provincias · indicador: ${currentMetric().label}`;
    if (layerKey === "municipalities") return `${data.features.length} municipios · área metropolitana delimitada en verde`;
    if (layerKey === "precincts") return `${data.features.length} recintos · 9 coordenadas estimadas identificadas en ámbar`;
    return `${data.features.length} manzanos censales · misma resolución del Atlas Censo 2024`;
  }

  function updateActiveMetric() {
    state.activeMetric = elements["metric-select"].value;
    const data = state.geojson[state.activeLayer];
    if (!data) return;
    updateLegend(data);
    if (state.activeLayer === "precincts") rebuildActiveLayer();
    else if (state.mainLayer?.setStyle) state.mainLayer.setStyle(state.activeLayer === "census" ? censusStyle : territoryStyle);
    setStatus(statusMessage(state.activeLayer, data));
    if (state.selected) renderSelection();
  }

  function selectFeature(layerKey, feature, leafletLayer) {
    const previous = state.selected;
    state.selected = { layerKey, feature, leafletLayer };
    if (previous?.leafletLayer?.setStyle && previous.feature !== feature) {
      previous.leafletLayer.setStyle(previous.layerKey === "census" ? censusStyle(previous.feature) : territoryStyle(previous.feature));
    }
    if (leafletLayer?.setStyle) leafletLayer.setStyle({ weight: 3, color: "#0f172a" });
    renderSelection();
  }

  function detailGrid(cells) {
    return `<div class="detail-grid">${cells.map(([label, value]) => `<div class="detail-cell"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>`;
  }

  function renderDefaultSelection() {
    elements["selection-kicker"].textContent = "Lectura departamental";
    elements["selection-title"].textContent = state.activeLayer === "census" ? "Censo 2024 por manzano" : "Santa Cruz";
    elements["selection-subtitle"].textContent = "Seleccione un elemento del mapa para consultar su perfil completo.";
    if (state.mode === "hypothesis") renderQuestions();
    else {
      elements["panel-content"].innerHTML = `
        <div class="reading"><p class="reading-label">Población departamental</p><p class="reading-value">3.122.605</p><p class="reading-copy">Censo 2024.</p></div>
        <div class="reading"><p class="reading-label">Padrón 2026</p><p class="reading-value">2.038.004</p><p class="reading-copy">Distribuido en 56 municipios y 1.138 recintos.</p></div>
        <div class="data-note">La selección cambia la ficha sin alterar el indicador cartográfico.</div>`;
    }
  }

  function renderSelection() {
    if (!state.selected) return renderDefaultSelection();
    const { layerKey, feature } = state.selected;
    const properties = feature.properties || {};
    elements["selection-kicker"].textContent = { provinces: "Provincia", municipalities: "Municipio", precincts: "Recinto electoral", census: "Manzano censal" }[layerKey];
    elements["selection-title"].textContent = featureName(layerKey, properties);
    elements["selection-subtitle"].textContent = selectionSubtitle(layerKey, properties);
    if (state.mode === "hypothesis") return renderQuestions();

    if (layerKey === "provinces") {
      elements["panel-content"].innerHTML = `${detailGrid([
        ["Población 2024", formatNumber(properties.population_2024)],
        ["Padrón 2026", formatNumber(properties.registered_2026)],
        ["Participación población", formatPercent(properties.population_share)],
        ["Índice representación", formatRatio(properties.territorial_representation_index_population)]
      ])}
      <div class="reading"><p class="reading-label">Diseño vigente</p><p class="reading-value">1 escaño territorial</p><p class="reading-copy">${formatNumber(properties.population_per_territorial_seat)} habitantes por escaño provincial.</p></div>
      <div class="reading"><p class="reading-label">Escenario proporcional</p><p class="reading-value">${formatNumber(properties.strict_proportional_23_population)} de 23</p><p class="reading-copy">Asignación hipotética según población, manteniendo fuera los cinco escaños indígenas.</p></div>`;
    } else if (layerKey === "municipalities") {
      elements["panel-content"].innerHTML = `${detailGrid([
        ["Población 2024", formatNumber(properties.population_2024)],
        ["Padrón 2026", formatNumber(properties.registered_2026)],
        ["Migración de vida", formatPercent(properties.lifetime_immigrant_share)],
        ["Migración reciente", formatPercent(properties.recent_immigrant_share)]
      ])}
      <div class="reading"><p class="reading-label">Infraestructura electoral</p><p class="reading-value">${formatNumber(properties.precincts_2026)} recintos</p><p class="reading-copy">${formatNumber(properties.tables_2026)} mesas en ${formatNumber(properties.localities_2026)} localidades.</p></div>
      <div class="reading"><p class="reading-label">Lectura electoral preliminar</p><p class="reading-value">${formatPercent(properties.libre_share)}</p><p class="reading-copy">Voto por LIBRE en la base utilizada para explorar migración y voto. La asociación municipal no implica causalidad individual.</p></div>`;
    } else if (layerKey === "precincts") {
      const estimated = properties.estimated_coordinate;
      elements["panel-content"].innerHTML = `${detailGrid([
        ["Habilitados", formatNumber(properties.registered_2026)],
        ["Mesas", formatNumber(properties.tables_2026)],
        ["Código", formatNumber(properties.precinct_code)],
        ["Confianza", properties.georeference_confidence || "s/d"]
      ])}
      <div class="reading"><p class="reading-label">Localidad</p><p class="reading-value">${escapeHtml(properties.locality || "s/d")}</p><p class="reading-copy">${escapeHtml(properties.municipality)}, provincia ${escapeHtml(properties.province)}.</p></div>
      <div class="${estimated ? "data-warning" : "data-note"}">${estimated ? "Coordenada estimada mediante referencia de comunidad o localidad; no corresponde a un punto oficial exacto del recinto." : "Coordenada oficial o heredada de una fuente electoral verificada."}</div>`;
    } else {
      elements["panel-content"].innerHTML = `${detailGrid([
        ["Población", formatNumber(properties.a1)],
        ["Hab./hectárea", formatNumber(properties.b1)],
        ["Población migrante", formatPercent(properties.h1)],
        ["Educación superior", formatPercent(properties.g1)]
      ])}
      <div class="reading"><p class="reading-label">Vivienda y conectividad</p><p class="reading-value">${formatPercent(properties.b2)}</p><p class="reading-copy">Viviendas con acceso a internet en el manzano.</p></div>
      <div class="data-note">Perfil calculado con la misma matriz comprimida utilizada por el Atlas Censo 2024 del Centro.</div>`;
    }
  }

  function selectionSubtitle(layerKey, properties) {
    if (layerKey === "provinces") return `${formatNumber(properties.municipalities)} municipios · ${formatNumber(properties.precincts_2026)} recintos`;
    if (layerKey === "municipalities") return `${properties.province}${properties.metropolitan ? " · Área metropolitana" : ""}`;
    if (layerKey === "precincts") return `${properties.municipality} · ${properties.locality}`;
    return "Unidad censal de máxima resolución disponible";
  }

  function renderQuestions() {
    const questions = {
      provinces: [
        ["Representación", "¿Debe una provincia mantener un escaño territorial idéntico cuando su población supera en decenas de veces a otra?"],
        ["Compensación", "¿Cuántos escaños de población serían necesarios para corregir la desigualdad territorial sin eliminar la representación provincial?"]
      ],
      municipalities: [
        ["Metrópolis", "¿Deberían los municipios integrados funcionalmente al área metropolitana contar en un diseño territorial propio?"],
        ["Migración", "¿El crecimiento por migración está cambiando las coaliciones electorales o coincide con otros procesos urbanos?"]
      ],
      precincts: [
        ["Acceso", "¿La distribución de recintos acompaña la concentración de población y padrón en las periferias urbanas?"],
        ["Calidad", "¿Qué decisiones requieren coordenadas oficiales exactas y cuáles toleran referencias estimadas?"]
      ],
      census: [
        ["Escala", "¿Las brechas municipales ocultan concentraciones migratorias y electorales mucho más localizadas?"],
        ["Estacionalidad", "¿Qué fuentes adicionales permitirían distinguir residencia habitual, movilidad temporal y lugar efectivo de votación?"]
      ]
    }[state.selected?.layerKey || state.activeLayer];

    elements["panel-content"].innerHTML = questions.map(([label, question]) => `<div class="reading"><p class="reading-label">${escapeHtml(label)}</p><p class="reading-value" style="font-size:17px;line-height:1.35;">${escapeHtml(question)}</p></div>`).join("") + `<div class="data-note">Estas preguntas organizan la exploración; no sustituyen una conclusión causal o normativa.</div>`;
  }

  function indexSearchItems(layerKey, featureCollection) {
    const existing = new Set(state.searchItems.map((item) => `${item.layerKey}:${item.label}`));
    featureCollection.features.forEach((feature) => {
      const label = featureName(layerKey, feature.properties || {});
      const key = `${layerKey}:${label}`;
      if (!label || existing.has(key)) return;
      state.searchItems.push({ layerKey, label, feature });
      existing.add(key);
    });
    refreshSearchOptions();
  }

  function refreshSearchOptions() {
    const prefixes = { provinces: "Provincia", municipalities: "Municipio", precincts: "Recinto" };
    elements["geography-options"].replaceChildren(...state.searchItems.map((item) => {
      const option = document.createElement("option");
      option.value = item.label;
      option.label = `${prefixes[item.layerKey] || "Territorio"}: ${item.label}`;
      return option;
    }));
  }

  function findLeafletLayer(feature) {
    let found = null;
    state.mainLayer?.eachLayer((layer) => { if (layer.feature === feature) found = layer; });
    return found;
  }

  async function runSearch() {
    const query = normalized(elements["geography-search"].value);
    if (!query) return;
    const item = state.searchItems.find((candidate) => normalized(candidate.label) === query) || state.searchItems.find((candidate) => normalized(candidate.label).includes(query));
    if (!item) {
      setStatus("No se encontró una coincidencia. Pruebe con otro nombre.");
      return;
    }
    if (state.activeLayer !== item.layerKey) await activateLayer(item.layerKey, false);
    const leafletLayer = findLeafletLayer(item.feature);
    if (!leafletLayer) return;
    if (leafletLayer.getBounds?.().isValid()) state.map.fitBounds(leafletLayer.getBounds(), { padding: [40, 40], maxZoom: 12 });
    else if (leafletLayer.getLatLng) state.map.setView(leafletLayer.getLatLng(), 14);
    selectFeature(item.layerKey, item.feature, leafletLayer);
    leafletLayer.openTooltip?.();
  }

  function createSvgElement(name, attributes = {}, text = "") {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (text) element.textContent = text;
    return element;
  }

  function renderMigrationScatter() {
    const data = state.dashboard.municipality_migration_vote.filter((item) => finite(item.lifetime_immigrant_share) && finite(item.libre_share));
    const svg = elements["migration-scatter"];
    svg.replaceChildren();
    const width = 620;
    const height = 330;
    const margin = { top: 18, right: 18, bottom: 48, left: 54 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const xMax = Math.max(.5, ...data.map((item) => item.lifetime_immigrant_share)) * 1.06;
    const yMin = Math.max(0, Math.min(...data.map((item) => item.libre_share)) - .06);
    const yMax = Math.min(1, Math.max(...data.map((item) => item.libre_share)) + .06);
    const x = (value) => margin.left + (value / xMax) * innerWidth;
    const y = (value) => margin.top + (1 - (value - yMin) / (yMax - yMin)) * innerHeight;

    svg.append(createSvgElement("line", { x1: margin.left, y1: margin.top + innerHeight, x2: width - margin.right, y2: margin.top + innerHeight, stroke: "#94a3b8", "stroke-width": 1 }));
    svg.append(createSvgElement("line", { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + innerHeight, stroke: "#94a3b8", "stroke-width": 1 }));

    [0, .1, .2, .3, .4, .5].filter((tick) => tick <= xMax).forEach((tick) => {
      const px = x(tick);
      svg.append(createSvgElement("line", { x1: px, y1: margin.top, x2: px, y2: margin.top + innerHeight, stroke: "#cbd5e1", "stroke-width": .6, "stroke-dasharray": "3 5" }));
      svg.append(createSvgElement("text", { x: px, y: height - 25, fill: "#64748b", "font-size": 10, "text-anchor": "middle" }, `${Math.round(tick * 100)}%`));
    });

    const yStep = .1;
    for (let tick = Math.ceil(yMin / yStep) * yStep; tick <= yMax + .001; tick += yStep) {
      const py = y(tick);
      svg.append(createSvgElement("line", { x1: margin.left, y1: py, x2: width - margin.right, y2: py, stroke: "#cbd5e1", "stroke-width": .6, "stroke-dasharray": "3 5" }));
      svg.append(createSvgElement("text", { x: margin.left - 9, y: py + 3, fill: "#64748b", "font-size": 10, "text-anchor": "end" }, `${Math.round(tick * 100)}%`));
    }

    data.forEach((item) => {
      const circle = createSvgElement("circle", {
        cx: x(item.lifetime_immigrant_share),
        cy: y(item.libre_share),
        r: item.metropolitan ? 6 : 4,
        fill: item.metropolitan ? "#059669" : "#004494",
        opacity: item.metropolitan ? .9 : .62,
        stroke: "#ffffff",
        "stroke-width": 1.2
      });
      circle.append(createSvgElement("title", {}, `${item.municipality}: migración ${formatPercent(item.lifetime_immigrant_share)}, LIBRE ${formatPercent(item.libre_share)}`));
      svg.append(circle);
    });

    svg.append(createSvgElement("text", { x: margin.left + innerWidth / 2, y: height - 6, fill: "#475569", "font-size": 11, "font-weight": 700, "text-anchor": "middle" }, "Inmigrantes de toda la vida / población municipal"));
    const yLabel = createSvgElement("text", { x: 14, y: margin.top + innerHeight / 2, fill: "#475569", "font-size": 11, "font-weight": 700, "text-anchor": "middle", transform: `rotate(-90 14 ${margin.top + innerHeight / 2})` }, "Voto LIBRE");
    svg.append(yLabel);

    const preliminary = state.dashboard.migration_vote_preliminary;
    elements["correlation-caption"].textContent = `Pearson: ${decimalFormatter.format(preliminary.pearson_lifetime_immigrant_share_vs_libre_share)} · Spearman: ${decimalFormatter.format(preliminary.spearman_lifetime_immigrant_share_vs_libre_share)}`;
  }

  function bindUiEvents() {
    document.querySelectorAll("[data-layer]").forEach((button) => button.addEventListener("click", () => activateLayer(button.dataset.layer)));
    document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      document.querySelectorAll("[data-mode]").forEach((item) => item.setAttribute("aria-pressed", String(item.dataset.mode === state.mode)));
      renderSelection();
    }));
    elements["metric-select"].addEventListener("change", updateActiveMetric);
    elements["geography-search"].addEventListener("change", runSearch);
    elements["geography-search"].addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
    elements["metro-toggle"].addEventListener("click", async () => {
      state.showMetro = !state.showMetro;
      elements["metro-toggle"].setAttribute("aria-pressed", String(state.showMetro));
      await ensureMunicipalities();
      if (state.showMetro) state.metroLayer.addTo(state.map).bringToFront();
      else state.map.removeLayer(state.metroLayer);
      setStatus(`${state.showMetro ? "Área metropolitana visible" : "Área metropolitana oculta"} · ${statusMessage(state.activeLayer, state.geojson[state.activeLayer])}`);
    });
    elements["estimated-toggle"].addEventListener("click", () => {
      state.showEstimated = !state.showEstimated;
      elements["estimated-toggle"].setAttribute("aria-pressed", String(state.showEstimated));
      if (state.activeLayer === "precincts") rebuildActiveLayer();
      setStatus(`${state.showEstimated ? "Incluye" : "Oculta"} 9 recintos con coordenada estimada`);
    });
    elements["theme-toggle"].addEventListener("click", () => {
      const root = document.documentElement;
      const dark = root.dataset.theme === "dark";
      root.dataset.theme = dark ? "light" : "dark";
      elements["theme-toggle"].setAttribute("aria-pressed", String(!dark));
      document.querySelector('meta[name="theme-color"]').setAttribute("content", dark ? "#ffffff" : "#0f172a");
      localStorage.setItem("representation-theme", root.dataset.theme);
      state.map.invalidateSize({ pan: false });
    });
  }

  function restoreTheme() {
    const stored = localStorage.getItem("representation-theme");
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
    const theme = stored || (prefersDark ? "dark" : "light");
    document.documentElement.dataset.theme = theme;
    elements["theme-toggle"].setAttribute("aria-pressed", String(theme === "dark"));
  }

  async function initialize() {
    cacheElements();
    restoreTheme();
    bindUiEvents();
    initializeMap();
    document.getElementById("year").textContent = new Date().getFullYear();
    showMessage("Preparando el mapa", "Cargando límites provinciales e indicadores.", 12);

    try {
      const [dashboard, department, provinces] = await Promise.all([
        fetchJson(DATA_PATHS.dashboard),
        fetchJson(DATA_PATHS.department),
        fetchJson(DATA_PATHS.provinces)
      ]);
      state.dashboard = dashboard;
      state.geojson.department = department;
      state.geojson.provinces = provinces;
      indexSearchItems("provinces", provinces);
      addDepartmentOutline();
      renderMigrationScatter();
      await activateLayer("provinces");
      Promise.allSettled([ensureMunicipalities(), ensurePrecincts()]).then(() => setStatus(statusMessage(state.activeLayer, state.geojson[state.activeLayer])));
    } catch (error) {
      console.error(error);
      showMessage("No se pudo iniciar el dashboard", "Revise la conexión o vuelva a cargar la página.", 100);
      setStatus(`Error de carga: ${error.message}`);
    }
  }

  document.addEventListener("DOMContentLoaded", initialize);
})();
