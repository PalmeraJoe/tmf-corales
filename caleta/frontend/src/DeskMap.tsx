import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { Desk, Station } from "./types";

type Props = {
  desk: Desk;
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function colorFor(station: Station): string {
  if (station.selected) return "#22d3ee";
  if (station.reason_code === "cronico" || station.reason_code === "doble") return "#fb7185";
  if (station.reason_code === "evento") return "#fbbf24";
  return "#64748b";
}

function Fit({ desk, token }: { desk: Desk; token: string }) {
  const map = useMap();
  useEffect(() => {
    const pts = desk.stations.filter((s) => s.lat != null && s.lon != null) as Station[];
    const id = window.setTimeout(() => {
      map.invalidateSize();
      if (pts.length >= 2) {
        map.fitBounds(
          pts.map((s) => [s.lat as number, s.lon as number]),
          { padding: [28, 28], maxZoom: 11 },
        );
      } else {
        map.setView(desk.property.center, desk.property.zoom);
      }
    }, 60);
    return () => window.clearTimeout(id);
  }, [desk.property.center, desk.property.zoom, desk.stations, map, token]);
  return null;
}

export default function DeskMap({ desk, selectedId, onSelect }: Props) {
  const points = desk.stations.filter((s) => s.lat != null && s.lon != null);
  return (
    <MapContainer
      className="map"
      center={desk.property.center}
      zoom={desk.property.zoom}
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <Fit desk={desk} token={`${desk.property.id}-${desk.season}-${desk.base?.id ?? "all"}`} />
      {points.map((station) => {
        const active = station.site_id === selectedId;
        return (
          <CircleMarker
            key={station.site_id}
            center={[station.lat as number, station.lon as number]}
            radius={active ? 10 : station.selected ? 8 : 5}
            pathOptions={{
              color: active ? "#f8fafc" : colorFor(station),
              weight: active ? 2 : 1,
              fillColor: colorFor(station),
              fillOpacity: station.selected ? 0.9 : 0.45,
            }}
            eventHandlers={{ click: () => onSelect(station.site_id) }}
          >
            <Tooltip>
              {station.rank}. {station.name} · P(Severo) {(station.p_severo * 100).toFixed(0)}%
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
