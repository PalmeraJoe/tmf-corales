"""AMP y resorts de operación. Catálogo propio de Caleta; no altera Baliza ni el TFM."""

from __future__ import annotations

from typing import Callable

import pandas as pd

FilterFn = Callable[[pd.DataFrame], pd.Series]


def _florida(df: pd.DataFrame) -> pd.Series:
    return (df["State_Island_Province_Name"] == "Florida") & (
        df["Ecoregion_Name"] == "Bahamas and Florida Keys"
    )


def _bahamas(df: pd.DataFrame) -> pd.Series:
    return df["Country_Name"] == "Bahamas"


def _jamaica(df: pd.DataFrame) -> pd.Series:
    return df["Ecoregion_Name"] == "Jamaica"


def _gbr(df: pd.DataFrame) -> pd.Series:
    return df["Ecoregion_Name"] == "Central and northern Great Barrier Reef"


def _belice(df: pd.DataFrame) -> pd.Series:
    return df["Country_Name"] == "Belize"


def _base(id_: str, name: str, kind: str, operator: str, lat: float, lon: float) -> dict:
    return {
        "id": id_,
        "name": name,
        "kind": kind,
        "operator": operator,
        "lat": lat,
        "lon": lon,
    }


PROPERTIES: dict[str, dict] = {
    "florida_keys": {
        "id": "florida_keys",
        "name": "Florida Keys",
        "kind": "amp",
        "manager": "Santuario marino (FKNMS) y operadores de los Keys",
        "default_season": 2011,
        "center": [24.72, -81.05],
        "zoom": 8,
        "filter": _florida,
        "note": "Red con histórico denso. 2011 es un año ordinario: priorizar importa más que en una crisis.",
        "bases": [
            _base("key_largo", "Key Largo · Pennekamp / FKNMS", "amp", "FKNMS y Pennekamp", 25.1226, -80.4066),
            _base("islamorada", "Islamorada · Founders Park", "resort", "Operadores de buceo de Islamorada", 24.9237, -80.6276),
            _base("marathon", "Marathon · Boot Key Harbor", "amp", "FKNMS Marathon", 24.7112, -81.0947),
            _base("key_west", "Key West · Key West Bight", "amp", "FKNMS Key West", 24.5615, -81.8073),
            _base("dry_tortugas", "Dry Tortugas · Garden Key", "amp", "Dry Tortugas National Park", 24.6283, -82.8734),
        ],
    },
    "bahamas": {
        "id": "bahamas",
        "name": "Bahamas",
        "kind": "amp",
        "manager": "Parques marinos y operadores insulares",
        "default_season": 2015,
        "center": [24.7, -76.2],
        "zoom": 7,
        "filter": _bahamas,
        "note": "Misma ecorregión que Florida, con menos estaciones por temporada.",
        "bases": [
            _base("nassau", "Nassau", "amp", "Puerto de Nueva Providencia", 25.077, -77.321),
            _base("marsh_harbour", "Marsh Harbour · Abaco", "amp", "Parques de Abaco", 26.544, -77.063),
            _base("freeport", "Freeport · Gran Bahama", "amp", "Gran Bahama", 26.515, -78.636),
            _base("warderick", "Warderick Wells · Exuma", "amp", "Exuma Cays Land and Sea Park", 24.394, -76.63),
            _base("georgetown_exuma", "George Town · Great Exuma", "resort", "Muelle turístico de George Town", 23.508, -75.767),
        ],
    },
    "jamaica": {
        "id": "jamaica",
        "name": "Jamaica",
        "kind": "amp",
        "manager": "AMP costeras y resorts del norte",
        "default_season": 2005,
        "center": [18.15, -77.3],
        "zoom": 8,
        "filter": _jamaica,
        "note": "Red insular compacta; las temporadas con más estaciones son anteriores a 2010.",
        "bases": [
            _base("montego_bay", "Montego Bay Marine Park", "amp", "Montego Bay Marine Park Trust", 18.473, -77.931),
            _base("ocho_rios", "Ocho Ríos / Discovery Bay", "amp", "AMP del norte", 18.467, -77.408),
            _base("negril", "Negril · West End", "resort", "Operadores de Negril", 18.284, -78.348),
            _base("port_antonio", "Port Antonio", "amp", "AMP del este", 18.176, -76.451),
        ],
    },
    "gbr_norte": {
        "id": "gbr_norte",
        "name": "Gran Barrera norte y central",
        "kind": "amp",
        "manager": "GBRMPA y flotas de Port Douglas / Whitsundays",
        "default_season": 2016,
        "center": [-16.3, 146.0],
        "zoom": 6,
        "filter": _gbr,
        "note": "Archipiélago distinto del Caribe; no se mezcla el modelo con Florida.",
        "bases": [
            _base("port_douglas", "Port Douglas", "resort", "Flota turística / Low Isles", -16.4836, 145.465),
            _base("cairns", "Cairns", "amp", "Puerto de Cairns", -16.923, 145.7781),
            _base("townsville", "Townsville · GBRMPA", "amp", "Sede GBRMPA", -19.2576, 146.8239),
            _base("airlie", "Airlie Beach · Whitsundays", "resort", "Flota de Whitsundays", -20.2675, 148.7169),
        ],
    },
    "belice": {
        "id": "belice",
        "name": "Belice",
        "kind": "amp",
        "manager": "Reservas de la barrera y flotas de Placencia / San Pedro",
        "default_season": 2009,
        "center": [17.2, -87.9],
        "zoom": 8,
        "filter": _belice,
        "note": "Menos estaciones: sirve para gestionar con datos escasos.",
        "bases": [
            _base("san_pedro", "San Pedro · Hol Chan", "amp", "Hol Chan Marine Reserve", 17.9214, -87.9615),
            _base("belize_city", "Belize City", "amp", "Fisheries Department", 17.4946, -88.1866),
            _base("placencia", "Placencia", "resort", "Flota de Placencia", 16.5142, -88.3663),
            _base("punta_gorda", "Punta Gorda", "amp", "Port Honduras", 16.1005, -88.8096),
        ],
    },
}


def list_properties() -> list[dict]:
    out = []
    for item in PROPERTIES.values():
        out.append(
            {
                "id": item["id"],
                "name": item["name"],
                "kind": item["kind"],
                "manager": item["manager"],
                "default_season": item["default_season"],
                "note": item["note"],
                "bases": [dict(b) for b in item["bases"]],
            }
        )
    return out
