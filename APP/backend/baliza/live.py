"""Conector a Coral Reef Watch vía ERDDAP, CSV de estaciones y diario de censo."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import ARTIFACTS

ERDDAP_CANDIDATES = [
    (
        "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/dhw_5km.json"
        "?CRW_DHW[(last)][({lat}):({lat})][({lon}):({lon})]"
        ",CRW_HOTSPOT[(last)][({lat}):({lat})][({lon}):({lon})]"
        ",CRW_SSTANOMALY[(last)][({lat}):({lat})][({lon}):({lon})]"
    ),
    (
        "https://coastwatch.noaa.gov/erddap/griddap/noaacrwdhwDaily.json"
        "?CRW_DHW[(last)][({lat}):({lat})][({lon}):({lon})]"
    ),
]


def _http_json(url: str, timeout: int = 12) -> dict:
    req = Request(url, headers={"User-Agent": "Baliza/0.2 (AMP decision support)"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def probe_live_crw(lat: float = 24.72, lon: float = -81.05) -> dict:
    last_error = None
    for template in ERDDAP_CANDIDATES:
        url = template.format(lat=f"{lat:.3f}", lon=f"{lon:.3f}")
        try:
            payload = _http_json(url)
            rows = payload.get("table", {}).get("rows") or []
            if not rows:
                last_error = "ERDDAP respondió sin filas"
                continue
            row = rows[-1]
            names = payload.get("table", {}).get("columnNames") or []
            named = dict(zip(names, row))
            dhw = named.get("CRW_DHW", named.get("degree_heating_week"))
            tsa = named.get("CRW_HOTSPOT")
            ssta = named.get("CRW_SSTANOMALY")
            if dhw is None:
                nums = [c for c in row if isinstance(c, (int, float))]
                dhw = nums[-1] if nums else None
            return {
                "ok": True,
                "url": url.split("?")[0],
                "dhw": None if dhw is None else float(dhw),
                "tsa": None if tsa is None else float(tsa),
                "ssta": None if ssta is None else float(ssta),
                "time": named.get("time"),
                "error": None,
            }
        except (URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
            last_error = str(exc)
            continue
    return {
        "ok": False,
        "url": None,
        "dhw": None,
        "tsa": None,
        "ssta": None,
        "time": None,
        "error": last_error,
    }


def parse_station_csv(text: str) -> list[dict]:
    sample = text.lstrip()
    dialect = csv.Sniffer().sniff(sample[:2000], delimiters=",;")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for idx, raw in enumerate(reader, start=1):
        lower = {str(k).strip().lower(): v for k, v in raw.items() if k}

        def num(*keys: str):
            for key in keys:
                if key in lower and str(lower[key]).strip() != "":
                    try:
                        return float(str(lower[key]).replace(",", "."))
                    except ValueError:
                        return None
            return None

        lat = num("lat", "latitude", "latitude_degrees")
        lon = num("lon", "lng", "longitude", "longitude_degrees")
        if lat is None or lon is None:
            continue
        rows.append(
            {
                "site_id": str(lower.get("site_id") or lower.get("id") or f"csv-{idx}"),
                "name": str(
                    lower.get("name")
                    or lower.get("site")
                    or lower.get("estacion")
                    or f"Estación {idx}"
                ),
                "lat": lat,
                "lon": lon,
                "depth_m": num("depth_m", "depth", "profundidad"),
                "distance_to_shore": num("distance_to_shore", "distance", "distancia"),
                "dhw": num("dhw", "tsa_dhw"),
                "ssta": num("ssta"),
                "tsa": num("tsa", "hotspot"),
                "climsst": num("climsst", "clim_sst"),
            }
        )
    if not rows:
        raise ValueError(
            "El CSV no tiene filas con lat y lon. "
            "Cabecera mínima: name,lat,lon. Opcional: site_id,depth_m,distance_to_shore,dhw,tsa,ssta,climsst."
        )
    return rows


def store_client_stations(network_id: str, filename: str, rows: list[dict]) -> dict:
    """Vuelca el CSV del cliente a la base SQLite de Baliza (APP/artifacts). No toca el CSV del TFM."""
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / "baliza_client.sqlite"
    uploaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    con = sqlite3.connect(path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS stations (
                id INTEGER PRIMARY KEY,
                uploaded_at TEXT NOT NULL,
                network_id TEXT NOT NULL,
                source_file TEXT,
                site_id TEXT,
                name TEXT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                depth_m REAL,
                distance_to_shore REAL,
                dhw REAL,
                ssta REAL,
                tsa REAL,
                climsst REAL
            )
            """
        )
        payload = [
            (
                uploaded_at,
                network_id,
                filename,
                row.get("site_id"),
                row.get("name"),
                row.get("lat"),
                row.get("lon"),
                row.get("depth_m"),
                row.get("distance_to_shore"),
                row.get("dhw"),
                row.get("ssta"),
                row.get("tsa"),
                row.get("climsst"),
            )
            for row in rows
        ]
        con.executemany(
            """
            INSERT INTO stations (
                uploaded_at, network_id, source_file, site_id, name, lat, lon,
                depth_m, distance_to_shore, dhw, ssta, tsa, climsst
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            payload,
        )
        con.commit()
        total = con.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    finally:
        con.close()
    return {
        "ok": True,
        "inserted": len(rows),
        "table": "stations",
        "database": str(path),
        "rows_in_db": int(total),
        "uploaded_at": uploaded_at,
    }


def save_census(network_id: str, site_id: str, percent: float, note: str = "") -> dict:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / "census_log.jsonl"
    record = {
        "network_id": network_id,
        "site_id": site_id,
        "percent_bleaching": percent,
        "note": note,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "ok": True,
        "stored": record,
        "retrains": False,
        "note": "Anotado. El bosque no se reentrena en esta versión.",
    }
