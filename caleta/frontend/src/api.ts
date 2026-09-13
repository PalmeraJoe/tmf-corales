import type { Desk, PropertyInfo, SiteHistory } from "./types";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function fetchProperties(): Promise<PropertyInfo[]> {
  return fetch("/api/properties").then((r) => asJson<{ properties: PropertyInfo[] }>(r)).then((d) => d.properties);
}

export function fetchDesk(params: {
  property_id: string;
  season: number | null;
  dives: number;
  base: string;
}): Promise<Desk> {
  const q = new URLSearchParams({
    property_id: params.property_id,
    dives: String(params.dives),
    base: params.base,
  });
  if (params.season != null) q.set("season", String(params.season));
  return fetch(`/api/desk?${q}`).then((r) => asJson<Desk>(r));
}

export function fetchStation(property_id: string, site_id: string): Promise<SiteHistory> {
  const q = new URLSearchParams({ property_id, site_id });
  return fetch(`/api/station?${q}`).then((r) => asJson<SiteHistory>(r));
}
