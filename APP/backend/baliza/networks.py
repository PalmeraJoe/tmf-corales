"""Catálogo de redes territoriales.

Baliza no se vende como cobertura mundial. Cada red es una implantación local
con estaciones ya observadas: el escenario de interpolación del TFM, no el de
cuenca nueva.
"""

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


NETWORKS: dict[str, dict] = {
    "florida_keys": {
        "id": "florida_keys",
        "name": "Florida Keys",
        "region": "Bahamas and Florida Keys",
        "buyer": "Santuario marino y programa de resiliencia arrecifal (FRRP)",
        "scenario": "Sitio conocido: interpolación dentro de una red con histórico local",
        "default_season": 2011,
        "center": [24.72, -81.05],
        "zoom": 8,
        "filter": _florida,
        "note": (
            "Red FRRP. 2011 es la temporada por defecto: un año ordinario, "
            "donde priorizar importa más que en 2014–2015 (crisis)."
        ),
        "bases": [
            _base(
                "key_largo",
                "Key Largo · John Pennekamp / FKNMS",
                "amp",
                "Florida Keys National Marine Sanctuary y John Pennekamp Coral Reef State Park",
                25.1226,
                -80.4066,
            ),
            _base(
                "islamorada",
                "Islamorada · Founders Park",
                "resort",
                "Operadores de buceo y muelle de Founders Park (Islamorada)",
                24.9237,
                -80.6276,
            ),
            _base(
                "marathon",
                "Marathon · Boot Key Harbor / FKNMS",
                "amp",
                "Florida Keys National Marine Sanctuary (oficina de Marathon)",
                24.7112,
                -81.0947,
            ),
            _base(
                "key_west",
                "Key West · Key West Bight / FKNMS",
                "amp",
                "Florida Keys National Marine Sanctuary (sede de Key West)",
                24.5615,
                -81.8073,
            ),
            _base(
                "dry_tortugas",
                "Dry Tortugas · Garden Key",
                "amp",
                "Dry Tortugas National Park (muelle de Garden Key / Fort Jefferson)",
                24.6283,
                -82.8734,
            ),
        ],
    },
    "bahamas": {
        "id": "bahamas",
        "name": "Bahamas",
        "region": "Bahamas and Florida Keys",
        "buyer": "Autoridad de áreas protegidas y gestores de parques marinos",
        "scenario": "Sitio conocido dentro de la misma ecorregión",
        "default_season": 2015,
        "center": [24.7, -76.2],
        "zoom": 7,
        "filter": _bahamas,
        "note": "Misma ecorregión que Florida Keys, con menor densidad de estaciones.",
        "bases": [
            _base(
                "nassau",
                "Nassau · Puerto de Nueva Providencia",
                "amp",
                "Bahamas National Trust y operadores del puerto de Nassau",
                25.077,
                -77.321,
            ),
            _base(
                "marsh_harbour",
                "Marsh Harbour · Abaco",
                "amp",
                "Parques marinos de Abaco / muelle de Marsh Harbour",
                26.544,
                -77.063,
            ),
            _base(
                "freeport",
                "Freeport · Gran Bahama",
                "amp",
                "Puerto de Freeport y gestores de Gran Bahama",
                26.515,
                -78.636,
            ),
            _base(
                "warderick",
                "Warderick Wells · Exuma Cays Land and Sea Park",
                "amp",
                "Bahamas National Trust (cuartel del parque de Exuma)",
                24.394,
                -76.63,
            ),
            _base(
                "georgetown_exuma",
                "George Town · Great Exuma",
                "resort",
                "Muelle turístico de George Town",
                23.508,
                -75.767,
            ),
            _base(
                "andros",
                "Andros Town · Fresh Creek",
                "amp",
                "Operaciones frente a la barrera de Andros",
                24.705,
                -77.786,
            ),
        ],
    },
    "jamaica": {
        "id": "jamaica",
        "name": "Jamaica",
        "region": "Jamaica",
        "buyer": "Agencia ambiental y AMP costeras",
        "scenario": "Red nacional compacta",
        "default_season": 2005,
        "center": [18.15, -77.3],
        "zoom": 8,
        "filter": _jamaica,
        "note": "Red insular; las temporadas con más estaciones suelen ser anteriores a 2010.",
        "bases": [
            _base(
                "montego_bay",
                "Montego Bay · Marine Park",
                "amp",
                "Montego Bay Marine Park Trust",
                18.473,
                -77.931,
            ),
            _base(
                "ocho_rios",
                "Ocho Ríos / Discovery Bay",
                "amp",
                "AMP del norte y estación de Discovery Bay",
                18.467,
                -77.408,
            ),
            _base(
                "port_royal",
                "Port Royal · Kingston",
                "amp",
                "NEPA / Palisadoes-Port Royal",
                17.937,
                -76.841,
            ),
            _base(
                "negril",
                "Negril · West End",
                "resort",
                "Operadores de buceo de Negril y reserva marina",
                18.284,
                -78.348,
            ),
            _base(
                "port_antonio",
                "Port Antonio",
                "amp",
                "AMP del este y muelle de Port Antonio",
                18.176,
                -76.451,
            ),
        ],
    },
    "gbr_norte": {
        "id": "gbr_norte",
        "name": "Gran Barrera norte y central",
        "region": "Central and northern Great Barrier Reef",
        "buyer": "Parques marinos y autoridad de la Gran Barrera",
        "scenario": "Archipiélago / red nacional",
        "default_season": 2016,
        "center": [-16.3, 146.0],
        "zoom": 6,
        "filter": _gbr,
        "note": "Implantación territorial distinta del Atlántico; no se mezcla con Florida.",
        "bases": [
            _base(
                "cooktown",
                "Cooktown",
                "amp",
                "Operaciones del extremo norte de la Gran Barrera",
                -15.4758,
                145.2471,
            ),
            _base(
                "port_douglas",
                "Port Douglas",
                "resort",
                "Flota turística de Port Douglas / Low Isles",
                -16.4836,
                145.465,
            ),
            _base(
                "cairns",
                "Cairns",
                "amp",
                "Puerto de Cairns y región norte de GBRMPA",
                -16.923,
                145.7781,
            ),
            _base(
                "townsville",
                "Townsville · GBRMPA",
                "amp",
                "Great Barrier Reef Marine Park Authority (sede)",
                -19.2576,
                146.8239,
            ),
            _base(
                "airlie",
                "Airlie Beach · Whitsundays",
                "resort",
                "Flota de Whitsundays / Airlie Beach",
                -20.2675,
                148.7169,
            ),
        ],
    },
    "belice": {
        "id": "belice",
        "name": "Belice",
        "region": "Belize and west Caribbean",
        "buyer": "Sistema de reservas de la barrera de Belice",
        "scenario": "AMP con histórico más disperso",
        "default_season": 2009,
        "center": [17.2, -87.9],
        "zoom": 8,
        "filter": _belice,
        "note": "Menos estaciones por temporada: sirve para ver el producto con datos escasos.",
        "bases": [
            _base(
                "san_pedro",
                "San Pedro · Hol Chan",
                "amp",
                "Hol Chan Marine Reserve / Ambergris Caye",
                17.9214,
                -87.9615,
            ),
            _base(
                "belize_city",
                "Belize City",
                "amp",
                "Fisheries Department / Tourism Village",
                17.4946,
                -88.1866,
            ),
            _base(
                "dangriga",
                "Dangriga",
                "amp",
                "South Water Caye / Glover's Reef (acceso desde Dangriga)",
                16.9692,
                -88.2325,
            ),
            _base(
                "placencia",
                "Placencia",
                "resort",
                "Flota de Placencia y reservas del sur",
                16.5142,
                -88.3663,
            ),
            _base(
                "punta_gorda",
                "Punta Gorda",
                "amp",
                "AMP del extremo sur / Port Honduras",
                16.1005,
                -88.8096,
            ),
        ],
    },
}


def bases_for(network_id: str) -> list[dict]:
    meta = NETWORKS.get(network_id) or {}
    return [dict(item) for item in meta.get("bases") or []]
