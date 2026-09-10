import type { Campaign, Capability, NetworkInfo, StationDetail } from "./types";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = (body as { detail?: string }).detail ?? "Error de servidor";
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function fetchNetworks(): Promise<NetworkInfo[]> {
  const data = await readJson<{ networks: NetworkInfo[] }>(await fetch("/api/networks"));
  return data.networks;
}

export async function fetchCapabilities(): Promise<{
  live: { ok: boolean; dhw: number | null; time: string | null; error: string | null };
  capabilities: Capability[];
}> {
  return readJson(await fetch("/api/capabilities"));
}

export type CampaignParams = {
  network: string;
  season: number | null;
  dives: number;
  costFalseAlarm: number;
  costMiss: number;
  boatDays: number;
  costDiveEur: number;
  hoursPerDive: number;
  origin: string;
};

function campaignQuery(params: CampaignParams): URLSearchParams {
  const query = new URLSearchParams({
    network: params.network,
    dives: String(params.dives),
    cost_false_alarm: String(params.costFalseAlarm),
    cost_miss: String(params.costMiss),
    boat_days: String(params.boatDays),
    cost_dive_eur: String(params.costDiveEur),
    hours_per_dive: String(params.hoursPerDive),
    origin: params.origin || "auto",
  });
  if (params.season) query.set("season", String(params.season));
  return query;
}

export async function fetchCampaign(params: CampaignParams): Promise<Campaign> {
  return readJson<Campaign>(await fetch(`/api/campaign?${campaignQuery(params).toString()}`));
}

export async function fetchStation(params: {
  network: string;
  season: number;
  siteId: string;
  costFalseAlarm: number;
  costMiss: number;
}): Promise<StationDetail> {
  const query = new URLSearchParams({
    network: params.network,
    season: String(params.season),
    site_id: params.siteId,
    cost_false_alarm: String(params.costFalseAlarm),
    cost_miss: String(params.costMiss),
  });
  return readJson<StationDetail>(await fetch(`/api/station?${query.toString()}`));
}

export function reportUrl(params: CampaignParams & { season: number }): string {
  return `/api/report?${campaignQuery(params).toString()}`;
}

export async function postCensus(body: {
  network: string;
  site_id: string;
  percent_bleaching: number;
  note: string;
}): Promise<{ ok: boolean; retrains: boolean; note: string }> {
  return readJson(
    await fetch("/api/census", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function uploadNetwork(
  network: string,
  file: File,
  useLive: boolean,
): Promise<{
  n: number;
  live_crw: boolean;
  note: string;
  stations: { name: string; p_severo: number; dhw: number | null; thermal_source: string }[];
  stored?: { ok: boolean; inserted: number; table: string; database: string; rows_in_db: number };
}> {
  const data = new FormData();
  data.append("file", file);
  return readJson(
    await fetch(`/api/network/upload?network=${encodeURIComponent(network)}&use_live=${useLive}`, {
      method: "POST",
      body: data,
    }),
  );
}
