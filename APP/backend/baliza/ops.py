"""Reglas operativas de campaña: zonas, cupo AOA, días de barco, planes y colas."""

from __future__ import annotations

import math
from itertools import combinations

import numpy as np


CAPABILITIES = [
    {
        "id": "historical_campaign",
        "title": "Mesa histórica sobre una red conocida",
        "status": "listo",
        "note": "Ranking, umbral, CRW, AOA y contraste retrospectivo con Sully et al.",
    },
    {
        "id": "queues",
        "title": "Tres colas (consenso / solo modelo / solo CRW)",
        "status": "listo",
        "note": "Separan lo que NOAA ya cubre de lo que Baliza añade o recorta.",
    },
    {
        "id": "aoa_quota",
        "title": "El AOA cambia la decisión",
        "status": "listo",
        "note": "Fuera de dominio: prioridad penalizada y tope en el presupuesto (por defecto 25 %).",
    },
    {
        "id": "boat_days",
        "title": "Rutas desde muelle AMP / resort",
        "status": "listo",
        "note": (
            "Cada día sale del muelle que elijas (o de un conjunto automático), "
            "visita en orden y vuelve. Distancia geodésica, no canales."
        ),
    },
    {
        "id": "costs_eur",
        "title": "Coste en euros y horas",
        "status": "listo",
        "note": "Inmersión tipo 400 € / 3 h, editable. No usa la contabilidad real del AMP.",
    },
    {
        "id": "plan_compare",
        "title": "Comparar Baliza vs CRW vs aleatorio",
        "status": "listo",
        "note": "Sobre la temporada histórica, con el mismo número de inmersiones.",
    },
    {
        "id": "calendar",
        "title": "Calendario de estación (visitada / aplazada / bloqueada)",
        "status": "listo",
        "note": "Se guarda en el navegador. No hay multiusuario ni servidor de campo.",
    },
    {
        "id": "live_crw",
        "title": "DHW de ayer (Coral Reef Watch / ERDDAP)",
        "status": "parcial",
        "note": "Hay conector. Si NOAA responde, el modo «Hoy» puntúa estaciones fijas con el DHW actual. Si no, queda marcado como no conectado.",
    },
    {
        "id": "client_csv",
        "title": "Alta de red del cliente (CSV)",
        "status": "parcial",
        "note": "Puedes cargar nombre, lat, lon, profundidad. El térmico sale de CRW en vivo o del vecino más cercano en Sully, no de un censo nuevo.",
    },
    {
        "id": "census",
        "title": "Censo de vuelta al modelo",
        "status": "parcial",
        "note": "Puedes anotar % blanqueado en la ficha. No reentrena el bosque hasta un piloto con n suficiente.",
    },
    {
        "id": "reef_gazetteer",
        "title": "Nombres oficiales de arrecife",
        "status": "parcial",
        "note": "Zona (Upper/Middle/Lower Keys o sector) + coordenadas. No hay catálogo de nombres locales tipo Sombrero Reef.",
    },
    {
        "id": "sentinel",
        "title": "Capa Sentinel-2 / Sentinel-3",
        "status": "no ahora",
        "note": "Hace falta cuenta Copernicus, mosaicos raster y una calibración nueva. No sustituye el DHW de NOAA.",
    },
    {
        "id": "forecast",
        "title": "Modo a 1–3 meses (DHW de pronóstico)",
        "status": "no ahora",
        "note": "El TFM pide CFSv2/NMME u otro pronóstico y validar el acoplamiento. No está implementado.",
    },
    {
        "id": "pdf_signed",
        "title": "PDF institucional firmable",
        "status": "parcial",
        "note": "Hay informe imprimible / markdown. No hay plantilla oficial ni firma.",
    },
    {
        "id": "insurance",
        "title": "Seguros y blue finance",
        "status": "no ahora",
        "note": "El modelo estima severidad ecológica, no mortalidad ni pérdida de ingresos.",
    },
    {
        "id": "push_global",
        "title": "Alertas push globales",
        "status": "no ahora",
        "note": "Fuera de alcance: primero un piloto en una AMP.",
    },
    {
        "id": "nautical_routing",
        "title": "Ruteo náutico (canales, oleaje, AIS)",
        "status": "no ahora",
        "note": (
            "Las líneas del mapa son rumbo geodésico desde muelles publicados. "
            "No evitan bajos, no leen parte meteorológica ni posiciones AIS reales."
        ),
    },
]

DAY_COLORS = [
    "#c4491d",
    "#11464e",
    "#8a6a2f",
    "#3d6b58",
    "#5b4b8a",
    "#2f5d7a",
    "#8a3b4a",
    "#4d6b70",
    "#6b4e31",
    "#1f6b5a",
    "#7a3e1d",
    "#3a4a7a",
    "#5a6b2f",
    "#7a5b12",
]


def zone_for(network_id: str, lat: float | None, lon: float | None) -> str:
    if lat is None or lon is None or np.isnan(lat) or np.isnan(lon):
        return "Sin posición"
    if network_id == "florida_keys":
        if lon <= -82.4:
            return "Dry Tortugas"
        if lon <= -81.15:
            return "Lower Keys"
        if lon <= -80.52:
            return "Middle Keys"
        return "Upper Keys"
    if network_id == "gbr_norte":
        if lat >= -15.5:
            return "Norte"
        if lat >= -17.5:
            return "Centro"
        return "Sur"
    if lon < -80:
        return "Sector oeste"
    if lon < -76:
        return "Sector central"
    return "Sector este"


def apply_aoa_penalty(score: float, inside: bool, factor: float = 0.72) -> float:
    return float(score if inside else score * factor)


def select_with_aoa_quota(ranked: list[dict], k: int, max_outside_frac: float = 0.25) -> list[dict]:
    k = max(1, min(k, len(ranked)))
    max_out = int(np.floor(k * max_outside_frac))
    chosen: list[dict] = []
    n_out = 0
    for station in ranked:
        if len(chosen) >= k:
            break
        if station["inside_aoa"]:
            chosen.append(station)
        elif n_out < max_out:
            chosen.append(station)
            n_out += 1
    if len(chosen) < k:
        ids = {s["site_id"] for s in chosen}
        for station in ranked:
            if station["site_id"] in ids:
                continue
            chosen.append(station)
            if len(chosen) >= k:
                break
    return chosen


def _finite_coord(value: object) -> bool:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlamb = math.radians(lon2 - lon1)
    chord = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlamb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, max(0.0, chord))))


def _bearing(base: dict, station: dict) -> float:
    return math.atan2(station["lat"] - base["lat"], station["lon"] - base["lon"])


def _path_km(base: dict, stops: list[dict]) -> float:
    points = [(base["lat"], base["lon"])] + [(s["lat"], s["lon"]) for s in stops] + [(base["lat"], base["lon"])]
    return sum(haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(points, points[1:]))


def _nearest_base(lat: float, lon: float, bases: list[dict]) -> dict:
    return min(bases, key=lambda base: haversine_km(lat, lon, base["lat"], base["lon"]))


def _nearest_neighbor(base: dict, stations: list[dict]) -> list[dict]:
    remaining = list(stations)
    route: list[dict] = []
    lat, lon = float(base["lat"]), float(base["lon"])
    while remaining:
        nxt = min(remaining, key=lambda item: haversine_km(lat, lon, item["lat"], item["lon"]))
        remaining.remove(nxt)
        route.append(nxt)
        lat, lon = float(nxt["lat"]), float(nxt["lon"])
    return route


def _two_opt(base: dict, stops: list[dict], max_passes: int = 10) -> list[dict]:
    if len(stops) < 4:
        return list(stops)
    best = list(stops)
    best_km = _path_km(base, best)
    for _ in range(max_passes):
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best)):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                km = _path_km(base, candidate)
                if km + 1e-6 < best_km:
                    best = candidate
                    best_km = km
                    improved = True
        if not improved:
            break
    return best


def _pmedian_bases(stations: list[dict], bases: list[dict], k: int) -> list[dict]:
    k = max(1, min(int(k), len(bases), len(stations)))
    best_combo: list[dict] | None = None
    best_cost = float("inf")
    for combo in combinations(bases, k):
        docks = list(combo)
        cost = 0.0
        for station in stations:
            dock = _nearest_base(station["lat"], station["lon"], docks)
            cost += haversine_km(station["lat"], station["lon"], dock["lat"], dock["lon"])
        ids = tuple(sorted(d["id"] for d in docks))
        best_ids = tuple(sorted(d["id"] for d in best_combo)) if best_combo else None
        if cost < best_cost - 1e-6 or (best_combo is not None and abs(cost - best_cost) <= 1e-6 and ids < (best_ids or ids)):
            best_cost = cost
            best_combo = docks
    return best_combo or bases[:k]


def _days_per_chosen_base(counts: dict[str, int], chosen: list[dict], n_days: int) -> dict[str, int]:
    days = {base["id"]: 1 for base in chosen if counts.get(base["id"], 0) > 0}
    leftover = n_days - sum(days.values())
    if leftover <= 0 or not days:
        return days
    ranked = sorted(days, key=lambda base_id: (-counts.get(base_id, 0), base_id))
    index = 0
    while leftover > 0 and ranked:
        days[ranked[index % len(ranked)]] += 1
        leftover -= 1
        index += 1
    return days


def _split_by_bearing(stations: list[dict], base: dict, n_chunks: int) -> list[list[dict]]:
    if n_chunks <= 1 or len(stations) <= 1:
        return [list(stations)]
    n_chunks = min(int(n_chunks), len(stations))
    ordered = sorted(stations, key=lambda station: _bearing(base, station))
    return [list(chunk) for chunk in np.array_split(ordered, n_chunks) if len(chunk)]


def assign_home_bases(stations: list[dict], network_id: str) -> None:
    from .networks import bases_for

    bases = bases_for(network_id)
    for station in stations:
        if bases and _finite_coord(station.get("lat")) and _finite_coord(station.get("lon")):
            home = _nearest_base(station["lat"], station["lon"], bases)
            station["home_base_id"] = home["id"]
            station["home_base_name"] = home["name"]
            station["home_base_kind"] = home.get("kind")
        else:
            station["home_base_id"] = None
            station["home_base_name"] = None
            station["home_base_kind"] = None


def _clear_route_fields(station: dict) -> None:
    station["boat_day"] = None
    station["boat_label"] = None
    station["visit_order"] = None
    station["base_id"] = None
    station["base_name"] = None
    station["base_kind"] = None
    station["leg_km"] = None


def _build_one_route(day: int, base: dict, ordered: list[dict]) -> dict:
    kind_label = "AMP" if base.get("kind") == "amp" else "resort"
    short = str(base["name"]).split("·")[0].strip()
    label = f"Día {day} · {short}"
    color = DAY_COLORS[(day - 1) % len(DAY_COLORS)]
    stops = []
    prev_lat, prev_lon = float(base["lat"]), float(base["lon"])
    loop_km = 0.0
    for order, station in enumerate(ordered, start=1):
        km = haversine_km(prev_lat, prev_lon, station["lat"], station["lon"])
        loop_km += km
        station["boat_day"] = day
        station["boat_label"] = label
        station["visit_order"] = order
        station["base_id"] = base["id"]
        station["base_name"] = base["name"]
        station["base_kind"] = base.get("kind")
        station["leg_km"] = round(km, 1)
        stops.append(
            {
                "site_id": station["site_id"],
                "name": station["name"],
                "order": order,
                "lat": station["lat"],
                "lon": station["lon"],
                "leg_km": round(km, 1),
            }
        )
        prev_lat, prev_lon = float(station["lat"]), float(station["lon"])
    loop_km += haversine_km(prev_lat, prev_lon, base["lat"], base["lon"])
    return {
        "day": day,
        "label": label,
        "short_label": short,
        "color": color,
        "n_dives": len(ordered),
        "loop_km": round(loop_km, 1),
        "note": (
            f"Sale de {base['name']} ({kind_label}) y vuelve al mismo muelle. "
            "Orden por vecino más cercano sobre distancia geodésica."
        ),
        "base": {
            "id": base["id"],
            "name": base["name"],
            "kind": base.get("kind"),
            "kind_label": kind_label,
            "operator": base.get("operator"),
            "lat": base["lat"],
            "lon": base["lon"],
        },
        "stops": stops,
    }


def plan_routes(
    selected: list[dict],
    network_id: str,
    n_days: int,
    origin_id: str | None = None,
) -> list[dict]:
    """Ordena las inmersiones en salidas que parten de un muelle AMP o resort y vuelven."""
    from .networks import bases_for

    for station in selected:
        _clear_route_fields(station)

    usable = [s for s in selected if _finite_coord(s.get("lat")) and _finite_coord(s.get("lon"))]
    if not usable:
        return []

    bases = bases_for(network_id)
    if not bases:
        bases = [
            {
                "id": "centroide",
                "name": "Base estimada (sin muelle publicado)",
                "kind": "amp",
                "operator": "Esta red no tiene catálogo de muelles.",
                "lat": float(np.mean([s["lat"] for s in usable])),
                "lon": float(np.mean([s["lon"] for s in usable])),
            }
        ]

    n_days = max(1, min(int(n_days), len(usable)))
    origin = (origin_id or "auto").strip() or "auto"
    wanted = [part.strip() for part in origin.split(",") if part.strip() and part.strip() != "auto"]
    forced = [base for base in bases if base["id"] in wanted]
    if forced:
        kept = forced
        assignment = {s["site_id"]: _nearest_base(s["lat"], s["lon"], kept) for s in usable}
        counts = {base["id"]: 0 for base in kept}
        for station in usable:
            counts[assignment[station["site_id"]]["id"]] += 1
        days_per_base = _days_per_chosen_base(counts, kept, n_days)
        kept = [base for base in kept if days_per_base.get(base["id"], 0) > 0]
    else:
        k_docks = min(n_days, len(bases), len(usable))
        kept = _pmedian_bases(usable, bases, k_docks)
        assignment = {s["site_id"]: _nearest_base(s["lat"], s["lon"], kept) for s in usable}
        counts = {base["id"]: 0 for base in kept}
        for station in usable:
            counts[assignment[station["site_id"]]["id"]] += 1
        days_per_base = _days_per_chosen_base(counts, kept, n_days)
        kept = [base for base in kept if days_per_base.get(base["id"], 0) > 0]
    if not kept:
        return []

    grouped: dict[str, list[dict]] = {base["id"]: [] for base in kept}
    for station in usable:
        grouped[assignment[station["site_id"]]["id"]].append(station)

    routes: list[dict] = []
    day = 1
    for base in sorted(kept, key=lambda item: (-len(grouped[item["id"]]), item["id"])):
        chunks = _split_by_bearing(grouped[base["id"]], base, days_per_base[base["id"]])
        for chunk in chunks:
            ordered = _two_opt(base, _nearest_neighbor(base, chunk))
            routes.append(_build_one_route(day, base, ordered))
            day += 1
    return routes


def assign_boat_days(
    selected: list[dict],
    n_days: int,
    network_id: str = "florida_keys",
    origin_id: str | None = None,
) -> list[dict]:
    plan_routes(selected, network_id, n_days, origin_id=origin_id)
    return selected


def campaign_savings(stations: list[dict], k: int, cost_dive: float, hours: float) -> dict:
    """Ahorro y episodios extra de Baliza frente a ordenar las mismas inmersiones por CRW."""
    selected = [s for s in stations if s.get("selected")]
    observed = [s for s in stations if s.get("observed_class") != "Sin dato"]
    by_crw = sorted(
        observed,
        key=lambda s: (s.get("crw_rank", 0) >= 3, s.get("dhw") or -1),
        reverse=True,
    )
    crw_plan = by_crw[:k]
    baliza_caught = sum(1 for s in selected if s.get("observed_severe"))
    crw_caught = sum(1 for s in crw_plan if s.get("observed_severe"))
    extra_severe = baliza_caught - crw_caught
    baliza_ids = {s["site_id"] for s in selected if s.get("observed_severe")}
    crw_ids = {s["site_id"] for s in crw_plan if s.get("observed_severe")}
    extra_sites = len(baliza_ids - crw_ids)

    crw_needed = None
    running = 0
    if baliza_caught:
        for index, station in enumerate(by_crw, start=1):
            if station.get("observed_severe"):
                running += 1
            if running >= baliza_caught:
                crw_needed = index
                break
    crw_cannot_match = bool(baliza_caught) and crw_needed is None
    dives_saved = max(0, (crw_needed or k) - k) if crw_needed is not None else 0
    if crw_cannot_match:
        dives_equiv = max(0, extra_severe)
        note = (
            f"Con {k} inmersiones Baliza localiza {baliza_caught} episodios severos y NOAA/CRW {crw_caught} "
            f"({extra_severe:+d}; {extra_sites} puntos que CRW no visita). "
            "NOAA no alcanza ese número ni recorriendo toda la red."
        )
    elif dives_saved:
        dives_equiv = dives_saved
        note = (
            f"Con {k} inmersiones Baliza localiza {baliza_caught} episodios severos y NOAA/CRW {crw_caught} "
            f"({extra_severe:+d}; {extra_sites} puntos a mayores). "
            f"CRW necesitaría {crw_needed} inmersiones para igualar: te ahorras {dives_saved}."
        )
    else:
        dives_equiv = max(0, extra_severe)
        note = (
            f"Con las mismas {k} inmersiones Baliza localiza {baliza_caught} episodios severos "
            f"y NOAA/CRW {crw_caught} ({extra_severe:+d}; {extra_sites} puntos a mayores)."
        )
    return {
        "baliza_caught": baliza_caught,
        "crw_caught": crw_caught,
        "extra_severe": extra_severe,
        "extra_sites": extra_sites,
        "dives": k,
        "crw_dives_to_match": crw_needed,
        "dives_saved": dives_saved,
        "eur_saved": round(dives_equiv * cost_dive, 0),
        "hours_saved": round(dives_equiv * hours, 1),
        "crw_cannot_match": crw_cannot_match,
        "cost_dive_eur": cost_dive,
        "note": note,
    }


def caught(seq: list[dict], k: int) -> int:
    return sum(1 for s in seq[:k] if s.get("observed_severe"))


def build_plans(ranked: list[dict], selected_ids: set[str], k: int, cost_dive: float, hours: float) -> list[dict]:
    observed = [s for s in ranked if s.get("observed_class") != "Sin dato"]
    n_severe = sum(1 for s in observed if s["observed_severe"])
    by_score = sorted(observed, key=lambda s: s["priority_score"], reverse=True)
    by_dhw = sorted(observed, key=lambda s: (s["dhw"] is not None, s["dhw"] or -1), reverse=True)
    rng = np.random.default_rng(42)
    shuffled = list(observed)
    rng.shuffle(shuffled)

    def pack(plan_id: str, name: str, seq: list[dict], note: str) -> dict:
        hits = caught(seq, k)
        return {
            "id": plan_id,
            "name": name,
            "caught": hits,
            "expected_p": float(sum(s["p_severo"] for s in seq[:k])),
            "hours": round(k * hours, 1),
            "eur": round(k * cost_dive, 0),
            "recall": (hits / n_severe) if n_severe else None,
            "note": note,
            "site_ids": [s["site_id"] for s in seq[:k]],
        }

    plans = [
        pack(
            "baliza",
            "Plan Baliza (modelo local + DHW + AOA)",
            [s for s in ranked if s["site_id"] in selected_ids] or by_score,
            "Lo que propone la mesa con el presupuesto actual.",
        ),
        pack(
            "crw",
            "Plan Coral Reef Watch (DHW)",
            by_dhw,
            "Las mismas inmersiones, ordenadas solo por estrés térmico de NOAA.",
        ),
        pack(
            "random",
            "Plan aleatorio",
            shuffled,
            "Misma capacidad, sin priorizar. Línea base de un cupo ciego.",
        ),
    ]
    if plans[0]["site_ids"] and set(plans[0]["site_ids"]) != set(s["site_id"] for s in by_score[:k]):
        pass
    return plans


def queue_counts(stations: list[dict], selected_only: bool = False) -> dict:
    pool = [s for s in stations if s["selected"]] if selected_only else stations
    counts = {"consenso": 0, "modelo": 0, "crw": 0, "ninguno": 0}
    for station in pool:
        key = station.get("disagreement") or "ninguno"
        counts[key] = counts.get(key, 0) + 1
    return counts
