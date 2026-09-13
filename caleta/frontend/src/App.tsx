import { useEffect, useMemo, useState } from "react";
import { fetchDesk, fetchProperties, fetchStation } from "./api";
import DeskMap from "./DeskMap";
import type { Desk, PropertyInfo, SiteHistory, Station } from "./types";

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "n/d";
  return `${Math.round(value * 100)} %`;
}

function num(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "n/d";
  return value.toLocaleString("es-ES", { maximumFractionDigits: digits });
}

export default function App() {
  const [properties, setProperties] = useState<PropertyInfo[]>([]);
  const [propertyId, setPropertyId] = useState("florida_keys");
  const [baseId, setBaseId] = useState("all");
  const [season, setSeason] = useState<number | null>(null);
  const [dives, setDives] = useState(12);
  const [desk, setDesk] = useState<Desk | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<SiteHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [onlySelected, setOnlySelected] = useState(true);

  const current = properties.find((p) => p.id === propertyId);

  useEffect(() => {
    fetchProperties()
      .then((items) => {
        setProperties(items);
        const first = items.find((p) => p.id === "florida_keys") ?? items[0];
        if (first) {
          setPropertyId(first.id);
          setSeason(null);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    setError(null);
    fetchDesk({ property_id: propertyId, season, dives, base: baseId })
      .then((data) => {
        setDesk(data);
        setSeason((prev) => data.season ?? prev);
        setSelectedId((prev) => {
          const keep = data.stations.some((s) => s.site_id === prev);
          return keep ? prev : data.stations[0]?.site_id ?? null;
        });
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [propertyId, season, dives, baseId]);

  useEffect(() => {
    if (!propertyId || !selectedId) {
      setHistory(null);
      return;
    }
    fetchStation(propertyId, selectedId)
      .then(setHistory)
      .catch(() => setHistory(null));
  }, [propertyId, selectedId]);

  const visible: Station[] = useMemo(() => {
    if (!desk) return [];
    return onlySelected ? desk.stations.filter((s) => s.selected) : desk.stations;
  }, [desk, onlySelected]);

  const selected = desk?.stations.find((s) => s.site_id === selectedId) ?? null;

  return (
    <div className="shell">
      <header className="mast">
        <div>
          <p className="kicker">Gestión local · AMP / resort · no es alerta NOAA</p>
          <h1>Caleta</h1>
          <p className="claim">
            Qué arrecifes de <em>tu</em> red inspeccionar esta temporada, según el historial
            del sitio. No sustituye Coral Reef Watch: lo deja como aviso de calor y prioriza
            con memoria local.
          </p>
        </div>
        <p className="aside">
          App hermana de Baliza. No modifica el TFM. El predictor es XGBoost + <code>Site_ID</code>.
        </p>
      </header>

      <section className="controls">
        <label>
          AMP o región
          <select
            value={propertyId}
            onChange={(e) => {
              setPropertyId(e.target.value);
              setBaseId("all");
              setSeason(null);
            }}
          >
            {properties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.n_sites} sitios
              </option>
            ))}
          </select>
        </label>
        <label>
          Base (AMP o resort)
          <select value={baseId} onChange={(e) => setBaseId(e.target.value)}>
            <option value="all">Toda la red</option>
            {(current?.bases ?? desk?.property.bases ?? []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.kind === "resort" ? "Resort" : "AMP"} · {b.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Temporada
          <select
            value={season ?? ""}
            onChange={(e) => setSeason(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Última visita de cada sitio</option>
            {(desk?.seasons ?? current?.seasons ?? []).map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <label>
          Inmersiones
          <input
            type="number"
            min={1}
            max={80}
            value={dives}
            onChange={(e) => setDives(Number(e.target.value))}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={onlySelected}
            onChange={(e) => setOnlySelected(e.target.checked)}
          />
          Solo el cupo
        </label>
      </section>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Calibrando el predictor local con el histórico anterior a la temporada…</p>}

      {desk && (
        <>
          <section className="kpis">
            <article>
              <span>Cupo</span>
              <strong>{desk.dives} inmersiones</strong>
            </article>
            <article>
              <span>Caleta pilla severos</span>
              <strong>
                {desk.caleta_severe_in_budget} / {desk.n_severe_observed}
              </strong>
            </article>
            <article>
              <span>Si ordenas por DHW</span>
              <strong>
                {desk.dhw_severe_in_budget} / {desk.n_severe_observed}
              </strong>
            </article>
            <article className={desk.gain_vs_dhw > 0 ? "gain" : ""}>
              <span>Ventaja local</span>
              <strong>
                {desk.gain_vs_dhw > 0 ? "+" : ""}
                {desk.gain_vs_dhw} severos
              </strong>
            </article>
          </section>
          <p className="claim-line">{desk.claim}</p>
          <p className="fine">
            {desk.property.manager}. Entrenado con {desk.n_train.toLocaleString("es-ES")} visitas de{" "}
            {desk.n_train_sites} sitios
            {desk.used_model ? " (XGBoost local)." : " (poca historia: se usa la tasa del sitio)."}{" "}
            {desk.season ? `Filtro ${desk.season}.` : "Última visita de cada estación con historial."}{" "}
            {desk.base ? `Radio de ${desk.base.name}.` : null}
          </p>

          <div className="workspace">
            <div className="list-pane">
              <h2>Orden de visita</h2>
              <ul className="queue">
                {visible.map((station) => (
                  <li key={station.site_id}>
                    <button
                      type="button"
                      className={station.site_id === selectedId ? "is-active" : ""}
                      onClick={() => setSelectedId(station.site_id)}
                    >
                      <span className="rank">{station.rank}</span>
                      <span className="body">
                        <strong>{station.name}</strong>
                        <em>{station.reason}</em>
                      </span>
                      <span className="meta">
                        <span>P(Severo) {pct(station.p_severo)}</span>
                        <span>Antes {station.last_class}</span>
                        <span>{station.n_hist} visitas</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div className="map-pane">
              <DeskMap desk={desk} selectedId={selectedId} onSelect={setSelectedId} />
            </div>
            <aside className="detail">
              {selected ? (
                <>
                  <p className="kicker">{selected.reason_code}</p>
                  <h2>{selected.name}</h2>
                  <p>{selected.reason}</p>
                  <dl>
                    <div>
                      <dt>Riesgo local Severo</dt>
                      <dd>{pct(selected.p_severo)}</dd>
                    </div>
                    <div>
                      <dt>Última clase conocida</dt>
                      <dd>{selected.last_class}</dd>
                    </div>
                    <div>
                      <dt>Observado esta temporada</dt>
                      <dd>
                        {selected.observed} ({num(selected.percent_bleaching, 0)} %)
                      </dd>
                    </div>
                    <div>
                      <dt>DHW (aviso de calor)</dt>
                      <dd>{num(selected.dhw, 1)}</dd>
                    </div>
                    <div>
                      <dt>Historial</dt>
                      <dd>{num(selected.n_hist, 0)} visitas previas</dd>
                    </div>
                  </dl>
                  {history && (
                    <div className="timeline">
                      <h3>Censos de este Site_ID</h3>
                      <ol>
                        {history.visits.map((visit, i) => (
                          <li key={`${visit.date}-${i}`}>
                            <span>{visit.date ?? visit.year}</span>
                            <span>{visit.observed}</span>
                            <span>DHW {num(visit.dhw, 1)}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </>
              ) : (
                <p className="muted">Elige una estación de la lista o del mapa.</p>
              )}
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
