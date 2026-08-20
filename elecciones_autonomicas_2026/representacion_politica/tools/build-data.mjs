import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const toolDirectory = path.dirname(fileURLToPath(import.meta.url));
const featureDirectory = path.resolve(toolDirectory, "..");
const outputDirectory = path.join(featureDirectory, "data");

const sourceFiles = {
  department: process.env.REP_INPUT_DEPARTMENT,
  municipalities: process.env.REP_INPUT_MUNICIPALITIES,
  precincts: process.env.REP_INPUT_PRECINCTS,
  base: process.env.REP_INPUT_ELECTORAL_CENSUS,
  simulation: process.env.REP_INPUT_REPRESENTATION_SIMULATION,
  migration: process.env.REP_INPUT_INE_MIGRATION
};

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function normalized(value = "") {
  return String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function numberOrNull(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function writeJson(fileName, value) {
  fs.writeFileSync(path.join(outputDirectory, fileName), JSON.stringify(value));
}

for (const [label, filePath] of Object.entries(sourceFiles)) {
  if (!filePath || !fs.existsSync(filePath)) {
    throw new Error(`Defina una ruta válida para la fuente ${label} mediante la variable REP_INPUT correspondiente.`);
  }
}

fs.mkdirSync(outputDirectory, { recursive: true });

const departmentSource = readJson(sourceFiles.department);
const municipalitySource = readJson(sourceFiles.municipalities);
const precinctSource = readJson(sourceFiles.precincts);
const base = readJson(sourceFiles.base);
const simulation = readJson(sourceFiles.simulation);
const migration = readJson(sourceFiles.migration);

const municipalityByCode = new Map(
  base.municipalities.map((municipality) => [Number(municipality.municipality_code), municipality])
);
const migrationVoteByName = new Map(
  simulation.municipality_migration_vote.map((municipality) => [normalized(municipality.municipality), municipality])
);
const migrationByName = new Map(
  migration.municipalities.map((municipality) => [normalized(municipality.municipality), municipality])
);
const provinceByName = new Map(
  base.provinces.map((province) => [normalized(province.province), province])
);
const scenarioByProvince = new Map(
  simulation.province_scenarios.map((province) => [normalized(province.province), province])
);

const municipalityFeatures = municipalitySource.features.map((feature) => {
  const code = Number(feature.properties.mun_cod || feature.properties.CODIGO);
  const electoral = municipalityByCode.get(code) || {};
  const nameKey = normalized(electoral.municipality || feature.properties.NOM_MUN);
  const migrationVote = migrationVoteByName.get(nameKey) || {};
  const migrationRecord = migrationByName.get(nameKey) || {};

  return {
    type: "Feature",
    geometry: feature.geometry,
    properties: {
      municipality_code: code,
      municipality: electoral.municipality || feature.properties.NOM_MUN,
      province: electoral.province || feature.properties.NOM_PROV,
      metropolitan: Boolean(electoral.metropolitan),
      population_2024: numberOrNull(electoral.population_2024),
      male_2024: numberOrNull(electoral.male_2024),
      female_2024: numberOrNull(electoral.female_2024),
      registered_2026: numberOrNull(electoral.registered_2026),
      precincts_2026: numberOrNull(electoral.precincts_2026),
      localities_2026: numberOrNull(electoral.localities_2026),
      tables_2026: numberOrNull(electoral.tables_2026),
      registered_population_ratio: numberOrNull(electoral.registered_population_ratio),
      lifetime_immigrant_share: numberOrNull(
        migrationVote.lifetime_immigrant_share ?? migrationRecord.lifetime_immigrant_share_of_population
      ),
      recent_immigrant_share: numberOrNull(
        migrationVote.recent_immigrant_share ?? migrationRecord.recent_immigrant_share_of_population_5plus
      ),
      recent_net_migration: numberOrNull(
        migrationVote.recent_net_migration ?? migrationRecord.recent_net_migration
      ),
      valid_votes: numberOrNull(migrationVote.valid_votes),
      libre_votes: numberOrNull(migrationVote.libre_votes),
      spt_votes: numberOrNull(migrationVote.spt_votes),
      libre_share: numberOrNull(migrationVote.libre_share),
      participation: numberOrNull(migrationVote.participation),
      source_area_km2: numberOrNull(feature.properties.area_km2)
    }
  };
});

const municipalityGeoJson = {
  type: "FeatureCollection",
  name: "Municipios de Santa Cruz con indicadores censales y electorales",
  features: municipalityFeatures
};

const provinceGeometry = new Map();
for (const feature of municipalityFeatures) {
  const provinceName = feature.properties.province;
  if (!provinceGeometry.has(provinceName)) provinceGeometry.set(provinceName, []);
  const target = provinceGeometry.get(provinceName);
  if (feature.geometry?.type === "Polygon") target.push(feature.geometry.coordinates);
  if (feature.geometry?.type === "MultiPolygon") target.push(...feature.geometry.coordinates);
}

const provinceFeatures = [...provinceGeometry.entries()].map(([provinceName, coordinates]) => {
  const electoral = provinceByName.get(normalized(provinceName)) || {};
  const scenario = scenarioByProvince.get(normalized(provinceName)) || {};
  return {
    type: "Feature",
    geometry: { type: "MultiPolygon", coordinates },
    properties: {
      province: electoral.province || provinceName,
      metropolitan_province: ["andres ibanez", "warnes"].includes(normalized(provinceName)),
      population_2024: numberOrNull(electoral.population_2024),
      registered_2026: numberOrNull(electoral.registered_2026),
      municipalities: numberOrNull(electoral.municipalities),
      precincts_2026: numberOrNull(electoral.precincts_2026),
      tables_2026: numberOrNull(electoral.tables_2026),
      territorial_seats: numberOrNull(electoral.territorial_seats),
      population_share: numberOrNull(electoral.population_share),
      registered_share: numberOrNull(electoral.registered_share),
      population_per_territorial_seat: numberOrNull(electoral.population_per_territorial_seat),
      registered_per_territorial_seat: numberOrNull(electoral.registered_per_territorial_seat),
      territorial_representation_index_population: numberOrNull(
        electoral.territorial_representation_index_population
      ),
      territorial_representation_index_registered: numberOrNull(
        electoral.territorial_representation_index_registered
      ),
      strict_proportional_23_population: numberOrNull(scenario.strict_proportional_23_population),
      strict_proportional_23_registered: numberOrNull(scenario.strict_proportional_23_registered),
      mixed_compensatory_23_population: numberOrNull(scenario.mixed_compensatory_23_population),
      mixed_compensatory_23_registered: numberOrNull(scenario.mixed_compensatory_23_registered),
      ideal_quota_23_population: numberOrNull(scenario.ideal_quota_23_population),
      ideal_quota_23_registered: numberOrNull(scenario.ideal_quota_23_registered)
    }
  };
});

const provinceGeoJson = {
  type: "FeatureCollection",
  name: "Provincias de Santa Cruz derivadas de límites municipales",
  metadata: {
    method: "Agrupación de geometrías municipales por provincia, sin alterar coordenadas de origen",
    province_count: provinceFeatures.length
  },
  features: provinceFeatures
};

const metroNames = new Set(base.metropolitan_six_municipalities.definition.map(normalized));
const precinctFeatures = precinctSource.features.map((feature) => {
  const status = normalized(feature.properties.coordinate_status);
  const confidence = normalized(feature.properties.georeference_confidence);
  return {
    ...feature,
    properties: {
      ...feature.properties,
      metropolitan: metroNames.has(normalized(feature.properties.municipality)),
      estimated_coordinate: status.includes("estimat") || confidence === "medium" || confidence === "low"
    }
  };
});

const precinctGeoJson = {
  type: "FeatureCollection",
  name: "Recintos electorales de Santa Cruz 2026",
  metadata: {
    ...(precinctSource.metadata || {}),
    total_features: precinctFeatures.length,
    estimated_features: precinctFeatures.filter((feature) => feature.properties.estimated_coordinate).length
  },
  features: precinctFeatures
};

const departmentFeature = departmentSource.features[0];
const departmentGeoJson = {
  type: "FeatureCollection",
  name: "Departamento de Santa Cruz",
  features: [
    {
      type: "Feature",
      geometry: departmentFeature.geometry,
      properties: {
        ...departmentFeature.properties,
        ...base.department,
        metropolitan_population_share: base.metropolitan_six_municipalities.population_share,
        metropolitan_registered_share: base.metropolitan_six_municipalities.registered_share
      }
    }
  ]
};

const dashboard = {
  version: "1.0.0",
  scope: "Representación política, concentración metropolitana y cambio electoral en Santa Cruz",
  department: base.department,
  metropolitan: {
    ...base.metropolitan_six_municipalities,
    ...simulation.metropolitan,
    lifetime_immigrant_share: simulation.migration_summary.metropolitan_lifetime_immigrant_share,
    recent_immigrant_share: simulation.migration_summary.metropolitan_recent_immigrant_share
  },
  malapportionment: simulation.malapportionment,
  migration_summary: simulation.migration_summary,
  migration_vote_preliminary: simulation.migration_vote_preliminary,
  municipality_migration_vote: simulation.municipality_migration_vote,
  province_scenarios: simulation.province_scenarios,
  assumptions: simulation.assumptions,
  methodological_scope: migration.methodological_scope,
  census_layer: {
    file: "../../../censo_2024/manzanos.geojson",
    fields_file: "../../../censo_2024/campos.json",
    feature_count: 61335,
    loading_strategy: "on_demand"
  },
  sources: {
    census_and_electoral_base: "INE, Censo de Población y Vivienda 2024; OEP/TED Santa Cruz, padrón y geografía electoral 2026",
    ine_migration: "INE, Censo de Población y Vivienda 2024, tabulados municipales de migración",
    oep_vote_results: "OEP/TED Santa Cruz, resultados municipales de la elección de gobernador 2026, segunda vuelta",
    official_statute: simulation.sources.official_statute,
    oep_2026_design: simulation.sources.oep_2026_design
  },
  coverage: {
    municipalities: municipalityFeatures.length,
    provinces: provinceFeatures.length,
    precincts: precinctFeatures.length,
    precincts_estimated: precinctFeatures.filter((feature) => feature.properties.estimated_coordinate).length
  }
};

writeJson("departamento.geojson", departmentGeoJson);
writeJson("municipios.geojson", municipalityGeoJson);
writeJson("provincias.geojson", provinceGeoJson);
writeJson("recintos.geojson", precinctGeoJson);
writeJson("dashboard.json", dashboard);

console.log(
  JSON.stringify(
    {
      outputDirectory,
      municipalities: municipalityFeatures.length,
      provinces: provinceFeatures.length,
      precincts: precinctFeatures.length,
      estimatedPrecincts: dashboard.coverage.precincts_estimated
    },
    null,
    2
  )
);
