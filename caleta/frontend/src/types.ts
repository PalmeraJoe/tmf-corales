export type Base = {
  id: string;
  name: string;
  kind: "amp" | "resort" | string;
  operator: string;
  lat: number;
  lon: number;
};

export type PropertyInfo = {
  id: string;
  name: string;
  kind: string;
  manager: string;
  default_season: number;
  note: string;
  bases: Base[];
  seasons: number[];
  n_sites: number;
};

export type Station = {
  site_id: string;
  name: string;
  lat: number | null;
  lon: number | null;
  date: string | null;
  percent_bleaching: number;
  observed: string;
  dhw: number | null;
  p_severo: number;
  last_class: string;
  n_hist: number;
  km_base: number | null;
  priority: number;
  reason_code: string;
  reason: string;
  rank: number;
  selected: boolean;
};

export type Desk = {
  product: string;
  used_model: boolean;
  property: {
    id: string;
    name: string;
    manager: string;
    center: [number, number];
    zoom: number;
    note: string;
    bases: Base[];
  };
  base: Base | null;
  season: number | null;
  seasons: number[];
  dives: number;
  n_train: number;
  n_train_sites: number;
  n_stations: number;
  n_severe_observed: number;
  caleta_severe_in_budget: number;
  dhw_severe_in_budget: number;
  gain_vs_dhw: number;
  stations: Station[];
  claim: string;
};

export type SiteHistory = {
  site_id: string;
  name: string;
  n_visits: number;
  visits: {
    date: string | null;
    year: number | null;
    percent_bleaching: number | null;
    observed: string;
    dhw: number | null;
  }[];
};
