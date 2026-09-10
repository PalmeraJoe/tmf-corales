import { useEffect, useState } from "react";
import {
  fetchCampaign,
  fetchCapabilities,
  fetchNetworks,
  reportUrl,
  uploadNetwork,
} from "./api";
import ReefMap from "./ReefMap";
import type {
  Campaign,
  Capability,
  FieldStatus,
  NetworkInfo,
  QueueKey,
  Station,
} from "./types";

type View = "mesa" | "informe" | "alcance";
type FilterKey = "budget" | "all" | "out";
type TableSort = "boat" | "rank" | "percent";

const ALERT_ORDER = ["Alerta 2", "Alerta 1", "Aviso", "Vigilancia", "Sin estrés", "Sin dato"] as const;

function fmtPct(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "n/d";
  return `${(value * 100).toLocaleString("es-ES", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })} %`;
}

function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/d";
  return value.toLocaleString("es-ES", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function fmtEur(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "n/d";
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

function statusKey(network: string, season: number) {
  return `baliza-field-${network}-${season}`;
}

export default function App() {
  const [networks, setNetworks] = useState<NetworkInfo[]>([]);
  const [networkId, setNetworkId] = useState("florida_keys");
  const [season, setSeason] = useState<number | null>(2011);
  const [dives, setDives] = useState(24);
  const [costMiss, setCostMiss] = useState(6);
  const [boatDays, setBoatDays] = useState(3);
  const [origin, setOrigin] = useState("auto");
  const [costDiveEur, setCostDiveEur] = useState(400);
  const [hoursPerDive, setHoursPerDive] = useState(3);
  const [campaignTotal, setCampaignTotal] = useState<number | null>(null);
  const [workers, setWorkers] = useState(4);
  const [notes, setNotes] = useState("");
  const [view, setView] = useState<View>("informe");
  const [filter, setFilter] = useState<FilterKey>("budget");
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [statuses, setStatuses] = useState<Record<string, FieldStatus>>({});

  useEffect(() => {
    fetchNetworks()
      .then(setNetworks)
      .catch((err: Error) => setError(err.message));
    fetchCapabilities()
      .then((data) => {
        setCapabilities(data.capabilities);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!season) return;
    try {
      const raw = localStorage.getItem(statusKey(networkId, season));
      setStatuses(raw ? (JSON.parse(raw) as Record<string, FieldStatus>) : {});
    } catch {
      setStatuses({});
    }
  }, [networkId, season]);

  useEffect(() => {
    if (!season) return;
    localStorage.setItem(statusKey(networkId, season), JSON.stringify(statuses));
  }, [statuses, networkId, season]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const timer = window.setTimeout(() => {
      fetchCampaign({
        network: networkId,
        season,
        dives,
        costFalseAlarm: 1,
        costMiss,
        boatDays,
        costDiveEur,
        hoursPerDive,
        origin,
      })
        .then((data) => {
          if (cancelled) return;
          setCampaign(data);
          setSeason(data.season);
          setSelectedId((current) => {
            if (current && data.stations.some((s) => s.site_id === current)) return current;
            return data.stations.find((s) => s.selected)?.site_id ?? data.stations[0]?.site_id ?? null;
          });
        })
        .catch((err: Error) => {
          if (!cancelled) {
            setCampaign(null);
            setError(err.message);
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 400);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [networkId, season, dives, costMiss, boatDays, costDiveEur, hoursPerDive, origin]);

  const currentNetwork = networks.find((n) => n.id === networkId);
  const params = {
    network: networkId,
    season,
    dives,
    costFalseAlarm: 1,
    costMiss,
    boatDays,
    costDiveEur,
    hoursPerDive,
    origin,
  };

  return (
    <div className="shell">
      <header className="mast">
        <div>
          <p className="kicker">Qué inspeccionar primero</p>
          <h1>Baliza</h1>
          <p className="claim">Rellena primero el cupo. Luego abre el mapa de acción para ver a dónde va el barco.</p>
        </div>
        <nav className="views" aria-label="Vistas">
          {(
            [
              ["informe", "Informe"],
              ["mesa", "Mapa"],
              ["alcance", "Alcance"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              className={view === id ? "active" : ""}
              onClick={() => setView(id)}
              type="button"
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      {view !== "informe" && (
      <section className="controls controls-main">
        <label>
          Dónde
          <select
            value={networkId}
            onChange={(event) => {
              const next = event.target.value;
              setNetworkId(next);
              const meta = networks.find((n) => n.id === next);
              setSeason(meta?.default_season ?? null);
            }}
          >
            {(networks.length ? networks : [{ id: networkId, name: "Florida Keys" }]).map((n) => (
              <option key={n.id} value={n.id}>
                {n.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Temporada
          <select value={season ?? ""} onChange={(event) => setSeason(Number(event.target.value))}>
            {(campaign?.seasons ?? currentNetwork?.seasons ?? []).map((s) => (
              <option key={s.year} value={s.year}>
                {s.year}
              </option>
            ))}
          </select>
        </label>
      </section>
      )}

      {campaign && view === "mesa" && (
        <p className="banner">{campaign.network.name} · {campaign.season} · histórico, no es el DHW de hoy</p>
      )}
      {error && <p className="error">{error}</p>}
      {loading && (
        <p className="status">
          {view === "informe"
            ? "Actualizando el mapa de acción con estos números…"
            : "Preparando la campaña…"}
        </p>
      )}

      {view === "informe" && campaign && (
        <Informe
          campaign={campaign}
          params={{ ...params, season: campaign.season }}
          networks={networks.length ? networks : [{ id: networkId, name: "Florida Keys" } as NetworkInfo]}
          networkId={networkId}
          onNetwork={(id) => {
            setNetworkId(id);
            const meta = networks.find((n) => n.id === id);
            setSeason(meta?.default_season ?? null);
            setCampaignTotal(null);
          }}
          season={season}
          onSeason={setSeason}
          dives={dives}
          onDives={(value) => {
            setDives(value);
            setCampaignTotal(null);
          }}
          boatDays={boatDays}
          onBoatDays={setBoatDays}
          campaignTotal={campaignTotal ?? campaign.kpis.budget_eur}
          onCampaignTotal={(value) => setCampaignTotal(value)}
          workers={workers}
          onWorkers={setWorkers}
          notes={notes}
          onNotes={setNotes}
          onGoMap={() => setView("mesa")}
        />
      )}
      {campaign && (
        <div className={view === "mesa" ? undefined : "mesa-park"} hidden={view !== "mesa"}>
          <Mesa
            key={campaign.network.id}
            campaign={campaign}
            selectedId={selectedId}
            onSelect={setSelectedId}
            filter={filter}
            onFilter={setFilter}
            statuses={statuses}
            mapActive={view === "mesa"}
          />
        </div>
      )}
      {view === "alcance" && campaign && <Alcance campaign={campaign} capabilities={capabilities} />}
    </div>
  );
}

function CapabilitiesStrip({
  items,
  liveOk,
}: {
  items: Capability[];
  liveOk: boolean | null;
}) {
  const blocked = items.filter((i) => i.status !== "listo");
  const [open, setOpen] = useState(false);
  return (
    <section className="caps">
      <button type="button" className="caps-toggle" onClick={() => setOpen((value) => !value)}>
        {blocked.length} capacidades no listas
        {liveOk === false ? " · NOAA/ERDDAP no contestó" : ""}
        {open ? " · ocultar" : " · ver detalle"}
      </button>
      {open && (
        <ul>
          {blocked.map((item) => (
            <li key={item.id} className={item.status.replace(" ", "-")}>
              <b>{item.status}</b> {item.title}: {item.note}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function dockOf(station: Station): string | null {
  return station.base_id ?? station.home_base_id;
}

function shortDock(name: string | null | undefined): string {
  if (!name) return "Sin muelle";
  return name.split("·")[0].trim();
}

function Mesa({
  campaign,
  selectedId,
  onSelect,
  filter,
  onFilter,
  statuses,
  mapActive,
}: {
  campaign: Campaign;
  selectedId: string | null;
  onSelect: (id: string) => void;
  filter: FilterKey;
  onFilter: (value: FilterKey) => void;
  statuses: Record<string, FieldStatus>;
  mapActive: boolean;
}) {
  const [tableSort, setTableSort] = useState<TableSort>("boat");
  const [dockIds, setDockIds] = useState<string[]>([]);
  const [alertTypes, setAlertTypes] = useState<string[]>([]);
  const bases = campaign.network.bases ?? [];
  const nBudget = campaign.stations.filter((s) => s.selected).length;
  const nOut = campaign.stations.length - nBudget;

  const scoped = campaign.stations.filter((station) => {
    if (filter === "budget" && !station.selected) return false;
    if (filter === "out" && station.selected) return false;
    if (dockIds.length) {
      const dock = dockOf(station);
      if (!dock || !dockIds.includes(dock)) return false;
    }
    return true;
  });
  const alertCounts = scoped.reduce<Record<string, number>>((acc, station) => {
    const level = station.crw_level || "Sin dato";
    acc[level] = (acc[level] ?? 0) + 1;
    return acc;
  }, {});
  const extraAlerts = Object.keys(alertCounts).filter(
    (level) => !(ALERT_ORDER as readonly string[]).includes(level),
  );
  const alertOptions = [
    ...ALERT_ORDER.filter((level) => (alertCounts[level] ?? 0) > 0 || alertTypes.includes(level)),
    ...extraAlerts.filter((level) => (alertCounts[level] ?? 0) > 0 || alertTypes.includes(level)),
  ];
  const visible = scoped.filter(
    (station) => !alertTypes.length || alertTypes.includes(station.crw_level || "Sin dato"),
  );
  const rows = [...visible].sort((a, b) => {
    if (tableSort === "percent") return b.p_severo - a.p_severo;
    if (tableSort === "rank") return a.rank - b.rank;
    const dayA = a.boat_day ?? 99;
    const dayB = b.boat_day ?? 99;
    if (dayA !== dayB) return dayA - dayB;
    const stopA = a.visit_order ?? 99;
    const stopB = b.visit_order ?? 99;
    if (stopA !== stopB) return stopA - stopB;
    return a.rank - b.rank;
  });

  function toggleDock(id: string) {
    setDockIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  function toggleAlert(level: string) {
    setAlertTypes((current) =>
      current.includes(level) ? current.filter((item) => item !== level) : [...current, level],
    );
  }

  return (
    <main className="mesa">
      <div className="map-filters">
        <div className="filter-row">
          <span>Qué ver</span>
          <button type="button" className={filter === "budget" ? "on" : ""} onClick={() => onFilter("budget")}>
            En el presupuesto · {nBudget}
          </button>
          <button type="button" className={filter === "out" ? "on" : ""} onClick={() => onFilter("out")}>
            Fuera · {nOut}
          </button>
          <button type="button" className={filter === "all" ? "on" : ""} onClick={() => onFilter("all")}>
            Todas · {campaign.stations.length}
          </button>
        </div>
        <div className="filter-row">
          <span>Sale de</span>
          <button type="button" className={dockIds.length === 0 ? "on" : ""} onClick={() => setDockIds([])}>
            Todos los muelles
          </button>
          {bases.map((base) => (
            <button
              key={base.id}
              type="button"
              className={dockIds.includes(base.id) ? "on" : ""}
              onClick={() => toggleDock(base.id)}
            >
              {shortDock(base.name)}
            </button>
          ))}
        </div>
        <div className="filter-row">
          <span>Alerta</span>
          <button type="button" className={alertTypes.length === 0 ? "on" : ""} onClick={() => setAlertTypes([])}>
            Todas las alertas
          </button>
          {alertOptions.map((level) => (
            <button
              key={level}
              type="button"
              className={alertTypes.includes(level) ? "on" : ""}
              onClick={() => toggleAlert(level)}
            >
              {level} · {alertCounts[level] ?? 0}
            </button>
          ))}
        </div>
      </div>

      <div className="workspace map-only">
        <div className="map-wrap">
          <ReefMap
            key={`${campaign.network.id}-${campaign.season}-${campaign.threshold.boat_days}`}
            campaign={campaign}
            selectedId={selectedId}
            visible={visible}
            statuses={statuses}
            onSelect={onSelect}
            visibleBaseIds={dockIds}
            showRoutes={filter !== "out"}
            active={mapActive}
          />
        </div>
      </div>
      <MapLegend campaign={campaign} />

      <section className="table-wrap">
        <header className="table-toolbar">
          <div>
            <h2>Estas estaciones</h2>
            <p>
              {filter === "budget"
                ? "Caben en el presupuesto."
                : filter === "out"
                  ? "Se quedan fuera con este número de inmersiones."
                  : "Todas las estaciones de la red."}
              {alertTypes.length ? ` Alerta NOAA: ${alertTypes.join(", ")}.` : ""} {rows.length} en la lista.
            </p>
          </div>
          <label>
            Ordenar por
            <select
              value={tableSort}
              onChange={(event) => setTableSort(event.target.value as TableSort)}
            >
              <option value="boat">Orden de parada del barco</option>
              <option value="rank">Puesto del lugar (prioridad Baliza)</option>
              <option value="percent">Porcentaje P(Severo)</option>
            </select>
          </label>
        </header>
        <div className="table-scroll">
          <table className="inspect-table">
            <thead>
              <tr>
                <th>Día · parada</th>
                <th>Puesto</th>
                <th>Estación</th>
                <th>Muelle</th>
                <th>P(Severo)</th>
                <th>DHW</th>
                <th>CRW</th>
                <th>Observado</th>
                <th>Cola</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((station) => (
                <tr
                  key={station.site_id}
                  className={`${station.selected ? "in-budget" : ""} ${station.site_id === selectedId ? "is-selected" : ""}`}
                  onClick={() => onSelect(station.site_id)}
                >
                  <td>
                    {station.visit_order != null
                      ? `${station.boat_day} · ${station.visit_order}`
                      : "—"}
                  </td>
                  <td>{station.rank}</td>
                  <td>
                    <strong>{station.name}</strong>
                    <small>
                      {station.zone} · {station.inside_aoa ? "AOA" : "fuera AOA"}
                    </small>
                  </td>
                  <td>{station.base_name ?? "—"}</td>
                  <td>{fmtPct(station.p_severo)}</td>
                  <td>{fmtNum(station.dhw, 1)}</td>
                  <td>{station.crw_level}</td>
                  <td>
                    {station.observed_class}
                    {station.observed_bleaching != null
                      ? ` · ${fmtNum(station.observed_bleaching, 0)} %`
                      : ""}
                  </td>
                  <td>{station.disagreement}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function MapLegend({ campaign }: { campaign: Campaign }) {
  const routes = campaign.routes ?? [];
  return (
    <section className="map-key" aria-label="Cómo leer el mapa">
      <p className="map-key-title">Así se lee cada punto</p>
      <ul className="map-key-items">
        <li>
          <span className="key-num">3</span>
          Número: orden en que el barco visita ese arrecife ese día.
        </li>
        <li>
          <span className="key-line solid" />
          <span className="key-line dashed" />
          Continua: ida. A trozos: vuelta al muelle.
        </li>
        <li>
          <span className="key-pin amp">AMP</span>
          <span className="key-pin resort">Resort</span>
          De dónde sale el barco.
        </li>
        <li>
          <span className="dot inspect" />
          Naranja: cabe en el presupuesto.
        </li>
        <li>
          <span className="dot rest" />
          Gris: se queda fuera.
        </li>
        <li>
          <span className="dot inspect big" />
          Más grande: más riesgo de blanqueo severo.
        </li>
      </ul>
      {routes.length > 0 && (
        <ul className="map-key-days">
          {routes.map((route) => (
            <li key={route.day}>
              <span className="key-day" style={{ background: route.color }}>
                {route.day}
              </span>
              {route.label}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function avgNum(values: Array<number | null | undefined>): number | null {
  const xs = values.filter((value): value is number => value != null && Number.isFinite(value));
  if (!xs.length) return null;
  return xs.reduce((sum, value) => sum + value, 0) / xs.length;
}

function countQueue(stations: Station[], key: QueueKey): number {
  return stations.filter((station) => station.disagreement === key).length;
}

function aoaWasSkipped(station: Station, selected: Station[]): boolean {
  if (station.selected || station.inside_aoa) return false;
  return selected.some((pick) => pick.rank > station.rank);
}

function whyChosen(station: Station): string {
  const bits: string[] = [];
  if (station.disagreement === "consenso") {
    bits.push("El bosque y NOAA coinciden: hay riesgo y hay calor.");
  } else if (station.disagreement === "modelo") {
    bits.push("El bosque lo ve grave aunque NOAA no lo marque (DHW bajo).");
  } else if (station.disagreement === "crw") {
    bits.push("NOAA marca calor; entra porque el DHW sube la nota de visita.");
  } else {
    bits.push("Entra por la nota combinada (bosque + DHW), sin alerta fuerte.");
  }
  if (!station.inside_aoa) {
    bits.push("Entra con recelo: se parece poco al histórico de esta red.");
  }
  return bits.join(" ");
}

function whyLeftOut(station: Station, k: number, skippedForAoa: boolean): string {
  if (skippedForAoa) {
    return "Iba alto en la lista, pero se parece poco al histórico y el cupo de sitios raros ya estaba lleno.";
  }
  if ((station.dhw ?? 0) >= 4 && station.p_severo < 0.2) {
    return "Hay calor (NOAA alerta), pero el bosque no lo ve tan grave y el cupo ya estaba lleno.";
  }
  if (station.p_severo < 0.1 && (station.dhw ?? 0) < 4) {
    return "Poco riesgo y poco calor: no merece una inmersión de este cupo.";
  }
  return `Queda fuera porque solo caben ${k} inmersiones y otras estaciones tienen mejor nota.`;
}

function ClientCsv({ networkId }: { networkId: string }) {
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <section className="csv-drop no-print">
      <h3>Cargar estaciones (CSV)</h3>
      <p className="explain">
        El archivo se vuelca a la base local de Baliza (<code>APP/artifacts/baliza_client.sqlite</code>,
        tabla <code>stations</code>) y se puntúa con el bosque de esta red. No se escribe en el CSV
        científico del TFM.
      </p>
      <div className="csv-spec">
        <p>
          <strong>Cómo tiene que estar el archivo</strong> — UTF-8, primera fila con nombres de
          columna, separador coma o punto y coma. Una fila = una estación. Sin latitud y longitud
          esa fila no entra.
        </p>
        <table>
          <thead>
            <tr>
              <th>Columna</th>
              <th>¿Obligatoria?</th>
              <th>También vale</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <code>name</code>
              </td>
              <td>Sí</td>
              <td>
                <code>site</code>, <code>estacion</code>
              </td>
            </tr>
            <tr>
              <td>
                <code>lat</code>
              </td>
              <td>Sí</td>
              <td>
                <code>latitude</code>, <code>latitude_degrees</code>
              </td>
            </tr>
            <tr>
              <td>
                <code>lon</code>
              </td>
              <td>Sí</td>
              <td>
                <code>lng</code>, <code>longitude</code>, <code>longitude_degrees</code>
              </td>
            </tr>
            <tr>
              <td>
                <code>site_id</code>
              </td>
              <td>No</td>
              <td>
                <code>id</code> — si falta, se genera
              </td>
            </tr>
            <tr>
              <td>
                <code>depth_m</code>
              </td>
              <td>No</td>
              <td>
                <code>depth</code>, <code>profundidad</code>
              </td>
            </tr>
            <tr>
              <td>
                <code>distance_to_shore</code>
              </td>
              <td>No</td>
              <td>
                <code>distance</code>, <code>distancia</code>
              </td>
            </tr>
            <tr>
              <td>
                <code>dhw</code>
              </td>
              <td>No</td>
              <td>
                <code>tsa_dhw</code> — si falta, NOAA o el vecino de la red
              </td>
            </tr>
            <tr>
              <td>
                <code>tsa</code>, <code>ssta</code>, <code>climsst</code>
              </td>
              <td>No</td>
              <td>Térmico extra; si falta, se completa</td>
            </tr>
          </tbody>
        </table>
        <pre>
          {`site_id,name,lat,lon,depth_m,distance_to_shore,dhw,tsa,ssta,climsst
FK-01,Molasses Reef,25.010,-80.377,8.5,1200,6.2,1.1,0.8,27.4
FK-02,Carysfort,25.222,-80.211,6.0,900,4.8,0.7,0.5,27.1`}
        </pre>
      </div>
      <label className="csv-file">
        Elegir CSV
        <input
          type="file"
          accept=".csv,text/csv"
          disabled={busy}
          onChange={async (event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (!file) return;
            setBusy(true);
            setNote(null);
            try {
              const result = await uploadNetwork(networkId, file, true);
              const stored = result.stored
                ? ` Guardadas ${result.stored.inserted} filas en ${result.stored.table} (hay ${result.stored.rows_in_db} en total).`
                : "";
              setNote(
                `${result.note} ${result.n} estaciones puntuadas.${stored} CRW en vivo: ${result.live_crw ? "sí" : "no"}. Primera: ${result.stations[0]?.name ?? "—"} · P(Severo) ${fmtPct(result.stations[0]?.p_severo)}.`,
              );
            } catch (err) {
              setNote(err instanceof Error ? err.message : "No se pudo leer el CSV");
            } finally {
              setBusy(false);
            }
          }}
        />
      </label>
      {note && <p className="status">{note}</p>}
    </section>
  );
}

function Informe({
  campaign,
  params,
  networks,
  networkId,
  onNetwork,
  season,
  onSeason,
  dives,
  onDives,
  boatDays,
  onBoatDays,
  campaignTotal,
  onCampaignTotal,
  workers,
  onWorkers,
  notes,
  onNotes,
  onGoMap,
}: {
  campaign: Campaign;
  params: {
    network: string;
    season: number;
    dives: number;
    costFalseAlarm: number;
    costMiss: number;
    boatDays: number;
    costDiveEur: number;
    hoursPerDive: number;
    origin: string;
  };
  networks: NetworkInfo[];
  networkId: string;
  onNetwork: (id: string) => void;
  season: number | null;
  onSeason: (year: number) => void;
  dives: number;
  onDives: (value: number) => void;
  boatDays: number;
  onBoatDays: (value: number) => void;
  campaignTotal: number;
  onCampaignTotal: (value: number) => void;
  workers: number;
  onWorkers: (value: number) => void;
  notes: string;
  onNotes: (value: string) => void;
  onGoMap: () => void;
}) {
  const selected = campaign.stations.filter((s) => s.selected);
  const leftover = campaign.stations
    .filter((s) => !s.selected)
    .slice()
    .sort((a, b) => a.rank - b.rank);
  const href = reportUrl(params);
  const { kpis, backtest, savings } = campaign;
  const priority = campaign.priority;
  const drivers = priority?.drivers ?? [];
  const routes = campaign.routes ?? [];
  const lastIn = selected.slice().sort((a, b) => a.rank - b.rank).at(-1) ?? null;
  const firstOut = leftover[0] ?? null;
  const aoaBlocked = leftover.filter((station) => aoaWasSkipped(station, selected));
  const noaaLeft = leftover.filter((station) => (station.dhw ?? 0) >= 4);
  const nearMiss = leftover.slice(0, 8);
  const inP = avgNum(selected.map((s) => s.p_severo));
  const inDhw = avgNum(selected.map((s) => s.dhw));
  const outP = avgNum(leftover.map((s) => s.p_severo));
  const outDhw = avgNum(leftover.map((s) => s.dhw));
  const modelPct = Math.round((priority?.model_share ?? 0.55) * 100);
  const dhwPct = Math.round((priority?.dhw_share ?? 0.45) * 100);
  const quotaPct = Math.round((campaign.threshold.aoa_quota ?? 0.25) * 100);
  const balizaCaught = savings?.baliza_caught ?? backtest.product_caught;
  const crwCaught = savings?.crw_caught ?? backtest.crw_then_dhw_caught;
  const extra = savings?.extra_severe ?? backtest.lift_vs_crw;
  const budgetQ = campaign.queues?.budget ?? {};
  const kmTotal = routes.reduce((sum, route) => sum + (route.loop_km ?? 0), 0);
  const noaaText = savings?.crw_cannot_match
    ? `NOAA no alcanza esos ${balizaCaught} episodios ni recorriendo toda la red.`
    : savings?.dives_saved
      ? `Para encontrar los mismos ${balizaCaught} episodios, NOAA necesitaría ${savings.crw_dives_to_match} inmersiones. Te ahorras ${savings.dives_saved} inmersiones (${fmtEur(savings.eur_saved)}, ${fmtNum(savings.hours_saved, 0)} h).`
      : `Con el mismo cupo, Baliza encuentra ${extra >= 0 ? extra : 0} episodios severos más.`;

  return (
    <>
    <article className="report printable">
      <header className="report-head">
        <div>
          <p className="kicker">Informe de campaña</p>
          <h2>
            {campaign.network.name}, {campaign.season}
          </h2>
          <p className="sub">{campaign.network.buyer}</p>
        </div>
        <div className="report-actions">
          <a href={href} download={`baliza-${campaign.network.id}-${campaign.season}.md`}>
            Descargar markdown
          </a>
          <button type="button" onClick={() => window.print()}>
            Imprimir / PDF
          </button>
        </div>
      </header>

      <section className="client-edit no-print">
        <h3>Cuestionario de la campaña</h3>
        <p className="explain">
          Rellena aquí dónde, cuándo y cuántas inmersiones. El mapa de acción se recalcula a la
          vez con estos números. Cuando esté listo, ábrelo en la pestaña Mapa.
        </p>
        <div className="client-fields">
          <label>
            Dónde
            <select value={networkId} onChange={(event) => onNetwork(event.target.value)}>
              {networks.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Temporada
            <select
              value={season ?? ""}
              onChange={(event) => onSeason(Number(event.target.value))}
            >
              {(campaign.seasons ?? []).map((s) => (
                <option key={s.year} value={s.year}>
                  {s.year}
                </option>
              ))}
            </select>
          </label>
          <label>
            Inmersiones de la campaña
            <input
              type="number"
              min={1}
              max={400}
              step={1}
              value={dives}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (!Number.isFinite(next)) return;
                onDives(Math.max(1, Math.min(400, Math.round(next))));
              }}
            />
          </label>
          <label>
            Días de barco
            <input
              type="number"
              min={1}
              max={14}
              step={1}
              value={boatDays}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (!Number.isFinite(next)) return;
                onBoatDays(Math.max(1, Math.min(14, Math.round(next))));
              }}
            />
          </label>
          <label>
            Dinero total de la campaña
            <input
              type="number"
              min={0}
              max={5000000}
              step={100}
              value={campaignTotal}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (!Number.isFinite(next)) return;
                onCampaignTotal(Math.max(0, Math.round(next)));
              }}
            />
          </label>
          <label>
            Trabajadores
            <input
              type="number"
              min={1}
              max={80}
              step={1}
              value={workers}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (!Number.isFinite(next)) return;
                onWorkers(Math.max(1, Math.min(80, Math.round(next))));
              }}
            />
          </label>
        </div>
        <label className="client-notes">
          Observaciones
          <textarea
            rows={4}
            value={notes}
            placeholder="Marea, permisos, hueco de barco, lo que el director debe leer…"
            onChange={(event) => onNotes(event.target.value)}
          />
        </label>
        <button type="button" className="go-map" onClick={onGoMap}>
          Ver el mapa de acción
        </button>
      </section>

      <section className="client-ficha">
        <h3>Ficha de la campaña</h3>
        <dl>
          <div>
            <dt>Inmersiones</dt>
            <dd>{dives}</dd>
          </div>
          <div>
            <dt>Días de barco</dt>
            <dd>{boatDays}</dd>
          </div>
          <div>
            <dt>Dinero total</dt>
            <dd>{fmtEur(campaignTotal)}</dd>
          </div>
          <div>
            <dt>Trabajadores</dt>
            <dd>{workers}</dd>
          </div>
        </dl>
        {notes.trim() ? (
          <p className="notes-out">
            <strong>Observaciones.</strong> {notes}
          </p>
        ) : (
          <p className="fine">Sin observaciones.</p>
        )}
      </section>

      <p className="lead">
        Con {kpis.dives} inmersiones, Baliza encuentra {balizaCaught} episodios severos reales.
        NOAA, con las mismas inmersiones, encuentra {crwCaught}.
      </p>

      <section className="report-block">
        <h3>Cuánto ayuda Baliza frente a NOAA</h3>
        <p className="explain">
          NOAA Coral Reef Watch mira sobre todo el DHW: va primero a donde el agua lleva más
          semanas calientes (Alerta 1 = DHW ≥ 4). Baliza usa eso y, además, el histórico de
          esta misma red. Aquí se compara el mismo número de inmersiones, con lo que luego se
          vio en el censo.
        </p>
        <div className="vs-grid">
          <article>
            <span>Si sigues a NOAA</span>
            <strong>{crwCaught}</strong>
            <p>
              episodios severos con {kpis.dives} inmersiones. Ordena por alerta CRW / DHW.
            </p>
          </article>
          <article className="win">
            <span>Si sigues a Baliza</span>
            <strong>
              {balizaCaught}
              <small>
                {extra >= 0 ? "+" : ""}
                {extra} más
              </small>
            </strong>
            <p>
              {savings?.extra_sites ?? kpis.model_only_in_budget} puntos severos que NOAA no
              pisa. {kpis.model_only_in_budget} paradas del cupo ni siquiera tenían DHW ≥ 4.
            </p>
          </article>
        </div>
        <div className="vs-note">
          <p>{noaaText}</p>
          <p>
            Ahorro estimado: <strong>{fmtEur(savings?.eur_saved ?? 0)}</strong>
            {savings?.hours_saved ? ` · ${fmtNum(savings.hours_saved, 0)} horas de campo` : ""}.
            De las {kpis.dives} paradas: {budgetQ.consenso ?? 0} las marcan las dos, {budgetQ.modelo ?? 0} las
            caza solo Baliza y {budgetQ.crw ?? 0} las marca NOAA por calor aunque el bosque no las alerte.
          </p>
        </div>
      </section>

      <section className="report-block">
        <h3>Qué se valora y cuánto</h3>
        <p className="explain">{priority?.how ?? campaign.model.ranking}</p>
        <div className="mix">
          <div>
            <b>{Math.round((priority?.model_share ?? 0.55) * 100)} %</b>
            <span>Bosque de esta red</span>
          </div>
          <div>
            <b>{Math.round((priority?.dhw_share ?? 0.45) * 100)} %</b>
            <span>DHW de NOAA</span>
          </div>
        </div>
        <p className="explain">
          Dentro del bosque, estas son las variables y el peso que tienen al estimar un
          episodio severo. El DHW también entra aparte: es el {Math.round((priority?.dhw_share ?? 0.45) * 100)} % del
          orden de las paradas, aunque dentro del bosque pese menos.
        </p>
        {drivers.length > 0 && (
          <ul className="drivers">
            {drivers.map((driver) => (
              <li key={driver.id}>
                <div className="driver-label">
                  <strong>{driver.name}</strong>
                  <span>{driver.plain}</span>
                </div>
                <div className="driver-bar" aria-hidden>
                  <span style={{ width: `${Math.max(4, driver.share * 100)}%` }} />
                </div>
                <em>{Math.round(driver.share * 100)} %</em>
              </li>
            ))}
          </ul>
        )}
        <p className="fine">{campaign.disclaimer}</p>
      </section>

      <section className="report-block">
        <h3>Por qué entran estas estaciones (y no las otras)</h3>
        <p className="explain">
          Solo caben {kpis.dives} inmersiones. Baliza ordena las {kpis.stations} estaciones
          de la red por una nota: {modelPct} % el bosque de esta AMP y {dhwPct} % el DHW de NOAA.
          Si un punto se parece poco al histórico (fuera del área de aplicabilidad), su nota se
          recorta y, como máximo, {quotaPct} % de las paradas pueden ser de ese tipo. Entran las{" "}
          {kpis.dives} primeras de esa lista, salvo sitios raros que se saltan si el cupo de
          “poco parecido al histórico” ya está lleno. Por eso la última del cupo no tiene por qué
          ser el puesto {kpis.dives}.
        </p>
        <div className="pick-grid">
          <article className="pick-in">
            <span>Entran en el cupo</span>
            <strong>{selected.length}</strong>
            <p>
              Riesgo medio {fmtPct(inP)} · DHW medio {fmtNum(inDhw, 1)}. {countQueue(selected, "consenso")} las
              marcan las dos, {countQueue(selected, "modelo")} las caza solo Baliza,{" "}
              {countQueue(selected, "crw")} las marca NOAA por calor.
            </p>
            {lastIn ? (
              <p>
                La última plaza del cupo es <b>{lastIn.name}</b> (n.º {lastIn.rank} de la cola).{" "}
                {whyChosen(lastIn)}
              </p>
            ) : null}
          </article>
          <article className="pick-out">
            <span>Quedan fuera</span>
            <strong>{leftover.length}</strong>
            {leftover.length === 0 ? (
              <p>El cupo cubre la red entera: no se descarta ninguna estación.</p>
            ) : (
              <>
                <p>
                  No es que estén sanas: el cupo está lleno. Riesgo medio {fmtPct(outP)} · DHW medio{" "}
                  {fmtNum(outDhw, 1)}.{" "}
                  {noaaLeft.length === 1
                    ? "1 todavía tiene alerta NOAA (DHW ≥ 4)"
                    : `${noaaLeft.length} todavía tienen alerta NOAA (DHW ≥ 4)`}
                  {aoaBlocked.length === 1
                    ? "; 1 se saltó aunque iba alta porque se parece poco al histórico"
                    : aoaBlocked.length > 1
                      ? `; ${aoaBlocked.length} se saltaron aunque iban altas porque se parecen poco al histórico`
                      : ""}
                  .
                </p>
                {firstOut ? (
                  <p>
                    La primera que no entra es <b>{firstOut.name}</b> (n.º {firstOut.rank} de la cola).{" "}
                    {whyLeftOut(firstOut, kpis.dives, aoaWasSkipped(firstOut, selected))}
                  </p>
                ) : null}
              </>
            )}
          </article>
        </div>
        {nearMiss.length > 0 ? (
          <>
            <p className="explain">
              Estas son las que más cerca se quedaron de entrar. El resto queda fuera por la
              misma razón: su nota es más baja y ya no hay inmersiones.
            </p>
            <div className="table-scroll">
              <table className="inspect-table report-table">
                <thead>
                  <tr>
                    <th>Puesto</th>
                    <th>Estación</th>
                    <th>Riesgo Baliza</th>
                    <th>Alerta NOAA</th>
                    <th>Por qué queda fuera</th>
                  </tr>
                </thead>
                <tbody>
                  {nearMiss.map((station) => (
                    <tr key={station.site_id}>
                      <td>{station.rank}</td>
                      <td>
                        <strong>{station.name}</strong>
                        <small>{station.zone}</small>
                      </td>
                      <td>{fmtPct(station.p_severo)}</td>
                      <td>
                        {station.crw_level}
                        {station.dhw != null ? ` · DHW ${fmtNum(station.dhw, 1)}` : ""}
                      </td>
                      <td>
                        {whyLeftOut(station, kpis.dives, aoaWasSkipped(station, selected))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>

      <section className="report-block">
        <h3>Resumen de las salidas</h3>
        <p className="explain">
          {routes.length} días de barco, {kpis.dives} inmersiones, {fmtEur(campaignTotal)} y{" "}
          {fmtNum(kmTotal, 0)} km de ida y vuelta al muelle (línea recta, no ruteo náutico).
          Cada día sale, visita en este orden y vuelve.
        </p>
        <div className="trip-grid">
          {routes.map((route) => (
            <article key={route.day} className="trip-card" style={{ borderTopColor: route.color }}>
              <span>{route.label}</span>
              <strong>
                {route.n_dives} inmersiones
                <small>{fmtNum(route.loop_km, 0)} km</small>
              </strong>
              <p>
                Sale de {shortDock(route.base.name)} ({route.base.kind === "amp" ? "AMP" : "resort"}
                ). Primera parada: {route.stops[0]?.name ?? "—"}.
              </p>
            </article>
          ))}
        </div>
        <div className="table-scroll">
          <table className="inspect-table report-table">
            <thead>
              <tr>
                <th>Día</th>
                <th>Orden</th>
                <th>Estación</th>
                <th>Sale de</th>
                <th>Riesgo Baliza</th>
                <th>Alerta NOAA</th>
                <th>Lo que se vio</th>
                <th>Por qué está</th>
              </tr>
            </thead>
            <tbody>
              {selected
                .slice()
                .sort(
                  (a, b) =>
                    (a.boat_day ?? 99) - (b.boat_day ?? 99) ||
                    (a.visit_order ?? 99) - (b.visit_order ?? 99),
                )
                .map((s) => (
                  <tr key={s.site_id}>
                    <td>{s.boat_day ?? "—"}</td>
                    <td>{s.visit_order ?? "—"}</td>
                    <td>
                      <strong>{s.name}</strong>
                      <small>{s.zone}</small>
                    </td>
                    <td>{shortDock(s.base_name)}</td>
                    <td>{fmtPct(s.p_severo)}</td>
                    <td>
                      {s.crw_level}
                      {s.dhw != null ? ` · DHW ${fmtNum(s.dhw, 1)}` : ""}
                    </td>
                    <td>
                      {s.observed_class}
                      {s.observed_bleaching != null ? ` · ${fmtNum(s.observed_bleaching, 0)} %` : ""}
                    </td>
                    <td>{whyChosen(s)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p className="fine">
          “Lo que se vio” es el censo de esa temporada, no un pronóstico. Sirve para comprobar
          si el orden acertó.
        </p>
      </section>
    </article>
    <ClientCsv networkId={networkId} />
    </>
  );
}

function Alcance({
  campaign,
  capabilities,
}: {
  campaign: Campaign;
  capabilities: Capability[];
}) {
  const items = capabilities.length ? capabilities : campaign.capabilities;
  return (
    <article className="scope">
      <h2>Qué es esto, y qué no</h2>
      <p>
        Baliza empaqueta el escenario de <em>sitio conocido</em> del TFM sobre{" "}
        <strong>{campaign.network.name}</strong> ({campaign.model.trained_on}).
      </p>
      <table>
        <thead>
          <tr>
            <th>Capacidad</th>
            <th>Estado</th>
            <th>Nota</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className={`cap-${item.status.replace(" ", "-")}`}>
              <td>{item.title}</td>
              <td>{item.status}</td>
              <td>{item.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="split">
        <section>
          <h3>Se puede decir</h3>
          <ul>
            {campaign.language.do.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <h3>No se debe vender todavía</h3>
          <ul>
            {campaign.language.dont.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>
      <p className="banner">{campaign.disclaimer}</p>
    </article>
  );
}
