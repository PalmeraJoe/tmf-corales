import { Fragment, useEffect, useMemo } from "react";
import { divIcon } from "leaflet";
import { CircleMarker, MapContainer, Marker, Pane, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { BoatRoute, Campaign, FieldStatus, Station } from "./types";

type Props = {
  campaign: Campaign;
  selectedId: string | null;
  visible: Station[];
  statuses: Record<string, FieldStatus>;
  onSelect: (siteId: string) => void;
  visibleBaseIds: string[];
  showRoutes: boolean;
  active: boolean;
};

function markerColor(station: Station, status: FieldStatus | undefined): string {
  if (status === "visited") return "#3d6b58";
  if (status === "blocked") return "#7a7a7a";
  if (station.selected) return "#c4491d";
  return "#8a9698";
}

function numberIcon(order: number, color: string, active: boolean) {
  const size = active ? 26 : 22;
  return divIcon({
    className: "visit-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<span class="visit-num${active ? " is-active" : ""}" style="background:${color}">${order}</span>`,
  });
}

function baseIcon(kind: string, active: boolean) {
  const label = kind === "amp" ? "AMP" : "Resort";
  return divIcon({
    className: "base-marker",
    iconSize: [64, 28],
    iconAnchor: [32, 14],
    html: `<span class="base-pin ${kind}${active ? " is-active" : ""}">${label}</span>`,
  });
}

function FitRoute({
  positions,
  enabled,
  token,
  active,
}: {
  positions: [number, number][];
  enabled: boolean;
  token: string;
  active: boolean;
}) {
  const map = useMap();
  useEffect(() => {
    if (!active || !enabled || positions.length < 2) return;
    const id = window.setTimeout(() => {
      map.invalidateSize();
      map.fitBounds(positions, { padding: [36, 36], maxZoom: 11 });
    }, 80);
    return () => window.clearTimeout(id);
  }, [active, enabled, map, token]);
  return null;
}

function routePositions(route: BoatRoute): [number, number][] {
  return [
    [route.base.lat, route.base.lon],
    ...route.stops.map((stop) => [stop.lat, stop.lon] as [number, number]),
    [route.base.lat, route.base.lon],
  ];
}

export default function ReefMap({ campaign, selectedId, visible, statuses, onSelect, visibleBaseIds, showRoutes, active }: Props) {
  const points = visible.filter((s) => s.lat != null && s.lon != null);
  const visibleIds = useMemo(() => new Set(points.map((s) => s.site_id)), [points]);
  const center = campaign.network.center;
  const routes = showRoutes ? campaign.routes ?? [] : [];
  const shownRoutes = (
    visibleBaseIds.length === 0 ? routes : routes.filter((route) => visibleBaseIds.includes(route.base.id))
  )
    .map((route) => ({
      ...route,
      stops: route.stops.filter((stop) => visibleIds.has(stop.site_id)),
    }))
    .filter((route) => route.stops.length > 0);
  const numbered = useMemo(() => {
    const ids = new Set(points.map((s) => s.site_id));
    return shownRoutes.flatMap((route) =>
      route.stops
        .filter((stop) => ids.has(stop.site_id))
        .map((stop) => ({ ...stop, color: route.color, day: route.day })),
    );
  }, [points, shownRoutes]);
  const numberedIds = useMemo(() => new Set(numbered.map((item) => item.site_id)), [numbered]);
  const bases = (campaign.network.bases?.length ? campaign.network.bases : routes.map((route) => route.base)).filter(
    (base, index, list) => list.findIndex((item) => item.id === base.id) === index,
  );
  const shownBases = visibleBaseIds.length ? bases.filter((base) => visibleBaseIds.includes(base.id)) : bases;
  const usedBaseIds = new Set(shownRoutes.map((route) => route.base.id));
  const fitPositions = shownRoutes.flatMap(routePositions);

  return (
    <MapContainer
      center={center}
      zoom={campaign.network.zoom}
      className="reef-map"
      scrollWheelZoom
    >
      <TileLayer
        attribution="&copy; OpenStreetMap"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitRoute
        positions={fitPositions}
        enabled={fitPositions.length >= 2}
        token={`${campaign.network.id}-${campaign.season}-${visibleBaseIds.join(",") || "all"}-${[...visibleIds].sort().join("|")}`}
        active={active}
      />
      <Pane name="baliza-routes" style={{ zIndex: 410 }}>
        {shownRoutes.map((route) => {
          const outbound = [[route.base.lat, route.base.lon] as [number, number], ...route.stops.map((stop) => [stop.lat, stop.lon] as [number, number])];
          const back: [number, number][] =
            route.stops.length > 0
              ? [
                  [route.stops[route.stops.length - 1].lat, route.stops[route.stops.length - 1].lon],
                  [route.base.lat, route.base.lon],
                ]
              : [];
          const thick =
            visibleBaseIds.includes(route.base.id) ||
            (selectedId != null && route.stops.some((s) => s.site_id === selectedId));
          return (
            <Fragment key={route.day}>
              <Polyline
                key={`${route.day}-out`}
                positions={outbound}
                pathOptions={{
                  color: route.color,
                  weight: thick ? 4 : 3,
                  opacity: 0.92,
                  lineJoin: "round",
                  lineCap: "round",
                }}
              />
              {back.length === 2 && (
                <Polyline
                  positions={back}
                  pathOptions={{
                    color: route.color,
                    weight: thick ? 3 : 2,
                    opacity: 0.55,
                    dashArray: "7 7",
                  }}
                />
              )}
            </Fragment>
          );
        })}
      </Pane>
      {points
        .filter((station) => !numberedIds.has(station.site_id))
        .map((station) => {
          const active = station.site_id === selectedId;
          const status = statuses[station.site_id];
          const radius = active ? 9 : 3.5 + station.p_severo * 8;
          return (
            <CircleMarker
              key={station.site_id}
              center={[station.lat as number, station.lon as number]}
              radius={radius}
              pathOptions={{
                color: active ? "#082c32" : markerColor(station, status),
                weight: station.selected ? 2 : 1,
                fillColor: markerColor(station, status),
                fillOpacity: station.selected ? 0.92 : 0.4,
              }}
              eventHandlers={{ click: () => onSelect(station.site_id) }}
            >
              <Tooltip>
                <strong>{station.name}</strong>
                <br />
                {station.selected ? "Entra en el presupuesto" : "Se queda fuera"}
                <br />
                {station.crw_level} · riesgo severo {(station.p_severo * 100).toFixed(0)}% · DHW{" "}
                {station.dhw?.toFixed(1) ?? "n/d"}
              </Tooltip>
            </CircleMarker>
          );
        })}
      {numbered.map((stop) => {
        const station = points.find((item) => item.site_id === stop.site_id);
        const active = stop.site_id === selectedId;
        return (
          <Marker
            key={`visit-${stop.site_id}`}
            position={[stop.lat, stop.lon]}
            icon={numberIcon(stop.order, stop.color, active)}
            zIndexOffset={active ? 800 : 500}
            eventHandlers={{ click: () => onSelect(stop.site_id) }}
          >
            <Tooltip>
              <strong>
                Parada {stop.order} · {stop.name}
              </strong>
              <br />
              Entra en el presupuesto · {station?.boat_label ?? `Día ${stop.day}`}
              <br />
              {station
                ? `${station.crw_level} · riesgo severo ${(station.p_severo * 100).toFixed(0)}% · DHW ${station.dhw?.toFixed(1) ?? "n/d"}`
                : ""}
            </Tooltip>
          </Marker>
        );
      })}
      {shownBases.map((base) => {
        const active = usedBaseIds.has(base.id);
        return (
          <Marker
            key={`base-${base.id}`}
            position={[base.lat, base.lon]}
            icon={baseIcon(base.kind, active)}
            zIndexOffset={900}
            opacity={active ? 1 : 0.45}
          >
            <Tooltip>
              <strong>{base.name}</strong>
              <br />
              {base.kind === "amp" ? "Muelle AMP" : "Muelle de resort / operador"}
              {base.operator ? ` · ${base.operator}` : ""}
            </Tooltip>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
