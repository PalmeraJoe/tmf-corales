export type SeasonInfo = {
  year: number;
  sites: number;
  observations: number;
  severe_rate: number;
  dhw_mean: number;
  dhw_max: number;
};

export type BoatBase = {
  id: string;
  name: string;
  kind: "amp" | "resort" | string;
  kind_label?: string;
  operator?: string;
  lat: number;
  lon: number;
};

export type RouteStop = {
  site_id: string;
  name: string;
  order: number;
  lat: number;
  lon: number;
  leg_km: number;
};

export type BoatRoute = {
  day: number;
  label: string;
  short_label: string;
  color: string;
  n_dives: number;
  loop_km: number;
  note: string;
  base: BoatBase;
  stops: RouteStop[];
};

export type NetworkInfo = {
  id: string;
  name: string;
  region: string;
  buyer: string;
  scenario: string;
  note: string;
  default_season: number;
  center: [number, number];
  zoom: number;
  bases?: BoatBase[];
  seasons: SeasonInfo[];
  n_seasons: number;
};

export type Factor = {
  feature: string;
  label: string;
  value: number;
  network_median: number;
  weight: number;
  direction: string;
  delta: number;
};

export type QueueKey = "consenso" | "modelo" | "crw" | "ninguno";

export type Station = {
  site_id: string;
  name: string;
  country: string | null;
  locality: string | null;
  source: string | null;
  lat: number | null;
  lon: number | null;
  date: string | null;
  depth_m: number | null;
  distance_to_shore: number | null;
  ssta: number | null;
  tsa: number | null;
  dhw: number | null;
  climsst: number | null;
  crw_level: string;
  crw_rank: number;
  p_bajo: number;
  p_moderado: number;
  p_severo: number;
  priority_score: number;
  model_class: string;
  operational_alert: boolean;
  inside_aoa: boolean;
  dissimilarity: number;
  uncertainty: string;
  observed_class: string;
  observed_bleaching: number | null;
  observed_severe: boolean;
  disagreement: QueueKey;
  disagreement_label: string;
  rank: number;
  selected: boolean;
  zone: string;
  boat_day: number | null;
  boat_label: string | null;
  visit_order: number | null;
  base_id: string | null;
  base_name: string | null;
  base_kind: string | null;
  leg_km: number | null;
  home_base_id: string | null;
  home_base_name: string | null;
  home_base_kind: string | null;
  data_as_of: string | null;
  factors: Factor[];
};

export type Plan = {
  id: string;
  name: string;
  caught: number;
  expected_p: number;
  hours: number;
  eur: number;
  recall: number | null;
  note: string;
  site_ids: string[];
};

export type Capability = {
  id: string;
  title: string;
  status: "listo" | "parcial" | "no ahora";
  note: string;
};

export type Campaign = {
  product: string;
  claim: string;
  disclaimer: string;
  network: {
    id: string;
    name: string;
    region: string;
    buyer: string;
    scenario: string;
    note: string;
    center: [number, number];
    zoom: number;
    bases?: BoatBase[];
  };
  season: number;
  seasons: SeasonInfo[];
  model: {
    name: string;
    version: string;
    trained_on: string;
    n_train: number;
    n_train_sites: number;
    severe_rate_train: number;
    competitor: string;
    ranking: string;
  };
  priority?: {
    model_share: number;
    dhw_share: number;
    how: string;
    drivers: { id: string; name: string; plain: string; share: number }[];
  };
  threshold: {
    cost_false_alarm: number;
    cost_miss: number;
    tau: number;
    rule: string;
    cost_dive_eur: number;
    hours_per_dive: number;
    budget_eur: number;
    budget_hours: number;
    aoa_quota: number;
    boat_days: number;
    origin_id?: string;
  };
  aoa: {
    method: string;
    threshold: number;
    inside_share: number;
    quota_note: string;
  };
  kpis: {
    stations: number;
    dives: number;
    alerts: number;
    inside_aoa: number;
    inside_budget: number;
    mean_p_severo: number;
    mean_dhw: number;
    model_only_in_budget: number;
    crw_downgraded: number;
    budget_eur: number;
    budget_hours: number;
  };
  queues: { all: Record<string, number>; budget: Record<string, number> };
  plans: Plan[];
  routes: BoatRoute[];
  capabilities: Capability[];
  freshness: { mode: string; as_of: string | null; label: string };
  backtest: {
    sites_with_observation: number;
    severe_observed: number;
    dives: number;
    model_caught: number;
    dhw_caught: number;
    product_caught: number;
    crw_then_dhw_caught: number;
    model_expected: number;
    model_recall: number | null;
    crw_recall: number | null;
    lift_vs_crw: number;
    coverage_vs_all: number | null;
  };
  savings: {
    baliza_caught: number;
    crw_caught: number;
    extra_severe: number;
    extra_sites: number;
    dives: number;
    crw_dives_to_match: number | null;
    dives_saved: number;
    eur_saved: number;
    hours_saved: number;
    crw_cannot_match: boolean;
    cost_dive_eur: number;
    note: string;
  };
  stations: Station[];
  language: { do: string[]; dont: string[] };
};

export type StationDetail = Station & {
  shap: { feature: string; shap: number; effect: string; label: string }[];
  history: {
    date: string | null;
    year: number | null;
    dhw: number | null;
    tsa: number | null;
    bleaching: number | null;
    observed_class: string;
  }[];
  disclaimer: string;
};

export type FieldStatus = "planned" | "visited" | "postponed" | "blocked";
