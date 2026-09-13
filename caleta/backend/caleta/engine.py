"""Motor de Caleta: predictor local por Site_ID para una AMP o un resort.

Lee el CSV del TFM en modo consulta. Entrena un XGBoost con historial del
emplazamiento (visitas anteriores a la temporada) y ordena inspecciones.
No es un termómetro CRW: el DHW solo evita perder un evento de calor nuevo.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from .config import (
    ARTIFACTS,
    CATEGORICAL_FEATURES,
    CLASS_ORDER,
    DATA_CSV,
    LOCAL_FEATURES,
    MAX_DEPTH,
    MIN_TRAIN_ROWS,
    MIN_TRAIN_SITES,
    MODEL_VERSION,
    N_ESTIMATORS,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    RESORT_MIN_SITES,
    RESORT_RADIUS_KM,
)
from .properties import PROPERTIES, list_properties

CLASS_TO_INT = {name: idx for idx, name in enumerate(CLASS_ORDER)}


def classify_bleaching(pct: float) -> str:
    if pd.isna(pct):
        return "Sin dato"
    if pct < 10:
        return "Bajo"
    if pct <= 30:
        return "Moderado"
    return "Severo"


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return float(2 * r * np.arcsin(np.sqrt(a)))


def _station_name(row: pd.Series) -> str:
    site = row.get("Site_Name")
    city = row.get("City_Town_Name")
    if pd.notna(site) and str(site).strip() and str(site).strip().lower() not in {"nan", "nd"}:
        base = str(site).strip()
    elif pd.notna(city) and str(city).strip():
        base = str(city).strip()
    else:
        base = f"Estación {row['Site_ID']}"
    return base


@lru_cache(maxsize=1)
def load_observations() -> pd.DataFrame:
    if not DATA_CSV.exists():
        raise FileNotFoundError(
            f"No está el corpus del TFM en {DATA_CSV}. Caleta solo lo lee; no lo modifica."
        )
    df = pd.read_csv(DATA_CSV, na_values=["nd", "ND"], low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Date_Year"] = pd.to_numeric(df.get("Date_Year"), errors="coerce")
    if df["Date_Year"].isna().all():
        df["Date_Year"] = df["Date"].dt.year
    return df


def _property_frame(df: pd.DataFrame, property_id: str) -> pd.DataFrame:
    meta = PROPERTIES.get(property_id)
    if not meta:
        raise KeyError(f"No hay AMP/resort '{property_id}'.")
    mask = meta["filter"](df)
    out = df.loc[mask].copy()
    if out.empty:
        raise ValueError(f"Sin observaciones para {meta['name']}.")
    return out


def _last_visit_split(work: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Última visita de cada Site_ID con historial = mesa; el resto = train."""
    ordered = work.sort_values(
        ["Site_ID", "Date_Year", "Date"],
        kind="mergesort",
    ).copy()
    ordered["n_site"] = ordered.groupby("Site_ID")["Site_ID"].transform("size")
    ordered["is_last"] = ordered.groupby("Site_ID").cumcount(ascending=False).eq(0)
    test_mask = ordered["n_site"].ge(2) & ordered["is_last"]
    train = ordered.loc[~test_mask].drop(columns=["n_site", "is_last"])
    test = ordered.loc[test_mask].drop(columns=["n_site", "is_last"])
    return train.reset_index(drop=True), test.reset_index(drop=True)


def _site_history(train: pd.DataFrame) -> pd.DataFrame:
    tmp = train.assign(is_severo=(train["target"] == 2).astype(float))
    stats = tmp.groupby("Site_ID").agg(
        local_site_bleach_mean=("target", "mean"),
        local_site_severo_rate=("is_severo", "mean"),
        local_site_dhw_mean=("TSA_DHW", "mean"),
        local_site_n_hist=("Site_ID", "size"),
    )
    last = (
        train.sort_values(["Site_ID", "Date_Year", "Date"], kind="mergesort")
        .groupby("Site_ID")["target"]
        .last()
        .rename("local_site_last_class")
    )
    stats = stats.join(last)
    stats["local_site_n_hist"] = stats["local_site_n_hist"].astype(float)
    return stats


def _attach_local(df: pd.DataFrame, stats: pd.DataFrame, fallback: dict) -> pd.DataFrame:
    out = df.copy()
    if stats is not None and not stats.empty:
        out = out.merge(stats, left_on="Site_ID", right_index=True, how="left")
    for col, value in fallback.items():
        if col not in out.columns:
            out[col] = value
        else:
            out[col] = out[col].fillna(value)
    return out


def _fallback(train: pd.DataFrame) -> dict:
    return {
        "local_site_bleach_mean": float(train["target"].mean()),
        "local_site_severo_rate": float((train["target"] == 2).mean()),
        "local_site_dhw_mean": float(train["TSA_DHW"].mean()) if train["TSA_DHW"].notna().any() else 0.0,
        "local_site_n_hist": 0.0,
        "local_site_last_class": float(train["target"].mode().iloc[0]),
    }


def _pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "prep",
                ColumnTransformer(
                    [
                        (
                            "num",
                            SimpleImputer(strategy="median"),
                            NUMERIC_FEATURES + LOCAL_FEATURES,
                        ),
                        (
                            "cat",
                            Pipeline(
                                [
                                    ("imputer", SimpleImputer(strategy="most_frequent")),
                                    (
                                        "enc",
                                        OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                                    ),
                                ]
                            ),
                            CATEGORICAL_FEATURES,
                        ),
                    ]
                ),
            ),
            (
                "clf",
                XGBClassifier(
                    n_estimators=N_ESTIMATORS,
                    max_depth=MAX_DEPTH,
                    objective="multi:softprob",
                    num_class=3,
                    eval_metric="mlogloss",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _cache_path(property_id: str, season: int, n_train: int) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{MODEL_VERSION}|{property_id}|{season}|{n_train}".encode()).hexdigest()[:12]
    return ARTIFACTS / f"caleta_{property_id}_{season}_{key}.pkl"


def _fit_local_model(train: pd.DataFrame, property_id: str, season: int) -> Pipeline:
    path = _cache_path(property_id, season, len(train))
    if path.exists():
        return joblib.load(path)
    model = _pipeline()
    y = train["target"].astype(int)
    weights = compute_sample_weight("balanced", y)
    model.fit(
        train[NUMERIC_FEATURES + CATEGORICAL_FEATURES + LOCAL_FEATURES],
        y,
        clf__sample_weight=weights,
    )
    joblib.dump(model, path)
    return model


def _reason(last_class: int, p_severo: float, dhw: float | None, n_hist: float) -> tuple[str, str]:
    heat = dhw is not None and dhw >= 4
    chronic = last_class == 2 and n_hist >= 1
    if n_hist < 1:
        code = "nuevo"
        text = "Sin visitas previas en esta red: se apoya en el patrón térmico de estaciones vecinas."
    elif chronic and not heat:
        code = "cronico"
        text = "Este arrecife ya venía grave. NOAA no alerta por calor; Caleta lo pone arriba por historial."
    elif last_class == 0 and heat:
        code = "evento"
        text = "Historial bueno, pero hay estrés térmico. Posible evento nuevo: no fiarse solo de la memoria."
    elif chronic and heat:
        code = "doble"
        text = "Sitio crónico y además con calor. Prioridad alta de inspección."
    elif p_severo >= 0.35:
        code = "modelo"
        text = "El predictor local (historial del Site_ID + condiciones de la temporada) lo marca de riesgo."
    else:
        code = "estable"
        text = "Historial local estable. Puede esperar si el cupo de inmersiones está lleno."
    return code, text


def _filter_base(snap: pd.DataFrame, base: dict | None) -> pd.DataFrame:
    if not base:
        return snap
    coords = snap.dropna(subset=["Latitude_Degrees", "Longitude_Degrees"]).copy()
    if coords.empty:
        return snap
    coords["km_base"] = [
        _haversine_km(base["lat"], base["lon"], lat, lon)
        for lat, lon in zip(coords["Latitude_Degrees"], coords["Longitude_Degrees"])
    ]
    near = coords.loc[coords["km_base"] <= RESORT_RADIUS_KM]
    if len(near) < RESORT_MIN_SITES:
        near = coords.sort_values("km_base").head(max(RESORT_MIN_SITES, min(20, len(coords))))
    return near


def _priority(p_severo: float, last_class: float, dhw: float | None) -> float:
    """Historial local manda; el DHW solo empuja un evento de calor nuevo."""
    chronic = 1.0 if last_class >= 1.5 else (0.45 if last_class >= 0.5 else 0.0)
    if dhw is None:
        heat = 0.0
    elif dhw >= 8:
        heat = 1.0
    elif dhw >= 4:
        heat = 0.55
    else:
        heat = 0.0
    return float(0.62 * p_severo + 0.28 * chronic + 0.10 * heat)


def build_desk(
    property_id: str,
    season: int | None,
    dives: int,
    base_id: str | None = None,
) -> dict:
    meta = PROPERTIES.get(property_id)
    if not meta:
        raise KeyError(f"AMP/resort desconocido: {property_id}")

    df = load_observations()
    frame = _property_frame(df, property_id)
    work = frame.loc[frame["Percent_Bleaching"].notna()].copy()
    work["target"] = work["Percent_Bleaching"].map(
        lambda v: 0 if v < 10 else (1 if v <= 30 else 2)
    )
    train, snap = _last_visit_split(work)
    if snap.empty:
        raise ValueError("Esta red no tiene estaciones con historial (más de una visita).")

    last_years = sorted(int(y) for y in snap["Date_Year"].dropna().unique())
    if season is not None and season in last_years:
        filtered = snap.loc[snap["Date_Year"] == season]
        if len(filtered) >= RESORT_MIN_SITES:
            snap = filtered
        else:
            season = None
    else:
        season = None

    bases = [dict(b) for b in meta["bases"]]
    base = next((b for b in bases if b["id"] == base_id), None) if base_id else None
    snap = _filter_base(snap, base)
    if snap.empty:
        raise ValueError("No quedan estaciones con historial alrededor de esa base.")

    n_sites_train = int(train["Site_ID"].nunique()) if not train.empty else 0
    use_model = len(train) >= MIN_TRAIN_ROWS and n_sites_train >= MIN_TRAIN_SITES

    stats = _site_history(train) if not train.empty else pd.DataFrame()
    fallback = _fallback(train) if not train.empty else {
        "local_site_bleach_mean": 0.0,
        "local_site_severo_rate": 0.0,
        "local_site_dhw_mean": 0.0,
        "local_site_n_hist": 0.0,
        "local_site_last_class": 0.0,
    }
    scored = _attach_local(snap, stats, fallback) if not stats.empty else _attach_local(snap, pd.DataFrame(), fallback)

    if use_model:
        model = _fit_local_model(
            _attach_local(train, stats, fallback),
            property_id,
            season or 0,
        )
        proba = model.predict_proba(
            scored[NUMERIC_FEATURES + CATEGORICAL_FEATURES + LOCAL_FEATURES]
        )
        p_map = {0: np.zeros(len(scored)), 1: np.zeros(len(scored)), 2: np.zeros(len(scored))}
        classes = [int(c) for c in model.named_steps["clf"].classes_]
        for col, cls in enumerate(classes):
            if cls in p_map:
                p_map[cls] = proba[:, col]
    else:
        p_map = {
            0: np.clip(1.0 - scored["local_site_severo_rate"].to_numpy(), 0, 1),
            1: np.zeros(len(scored)),
            2: scored["local_site_severo_rate"].to_numpy(),
        }
        model = None

    stations = []
    for idx, (_, row) in enumerate(scored.iterrows()):
        dhw = None if pd.isna(row.get("TSA_DHW")) else float(row["TSA_DHW"])
        last_class = int(row["local_site_last_class"]) if pd.notna(row["local_site_last_class"]) else 0
        n_hist = float(row["local_site_n_hist"])
        p_sev = float(p_map[2][idx])
        p_mod = float(p_map[1][idx])
        p_low = float(p_map[0][idx])
        code, text = _reason(last_class, p_sev, dhw, n_hist)
        observed = classify_bleaching(row["Percent_Bleaching"])
        stations.append(
            {
                "site_id": str(row["Site_ID"]),
                "name": _station_name(row),
                "lat": None if pd.isna(row.get("Latitude_Degrees")) else float(row["Latitude_Degrees"]),
                "lon": None if pd.isna(row.get("Longitude_Degrees")) else float(row["Longitude_Degrees"]),
                "date": None if pd.isna(row.get("Date")) else str(pd.Timestamp(row["Date"]).date()),
                "percent_bleaching": float(row["Percent_Bleaching"]),
                "observed": observed,
                "dhw": dhw,
                "p_bajo": p_low,
                "p_moderado": p_mod,
                "p_severo": p_sev,
                "last_class": CLASS_ORDER[last_class] if 0 <= last_class < 3 else "Sin dato",
                "n_hist": n_hist,
                "km_base": None if "km_base" not in row or pd.isna(row.get("km_base")) else float(row["km_base"]),
                "priority": _priority(p_sev, last_class, dhw),
                "reason_code": code,
                "reason": text,
            }
        )

    ranked = sorted(stations, key=lambda s: s["priority"], reverse=True)
    k = max(1, min(int(dives), len(ranked)))
    chosen_ids = {s["site_id"] for s in ranked[:k]}
    dhw_order = sorted(
        stations,
        key=lambda s: (s["dhw"] is not None, s["dhw"] or -1),
        reverse=True,
    )
    dhw_ids = {s["site_id"] for s in dhw_order[:k]}

    def _severe_hits(ids: set[str]) -> int:
        return sum(1 for s in stations if s["site_id"] in ids and s["observed"] == "Severo")

    n_severe = sum(1 for s in stations if s["observed"] == "Severo")
    caleta_hits = _severe_hits(chosen_ids)
    dhw_hits = _severe_hits(dhw_ids)

    for i, station in enumerate(ranked, start=1):
        station["rank"] = i
        station["selected"] = station["site_id"] in chosen_ids

    return {
        "product": "Caleta",
        "model_version": MODEL_VERSION,
        "used_model": bool(use_model),
        "property": {
            "id": meta["id"],
            "name": meta["name"],
            "manager": meta["manager"],
            "kind": meta["kind"],
            "center": meta["center"],
            "zoom": meta["zoom"],
            "note": meta["note"],
            "bases": bases,
        },
        "base": base,
        "season": season,
        "seasons": last_years,
        "dives": k,
        "n_train": int(len(train)),
        "n_train_sites": n_sites_train,
        "n_stations": len(ranked),
        "n_severe_observed": n_severe,
        "caleta_severe_in_budget": caleta_hits,
        "dhw_severe_in_budget": dhw_hits,
        "gain_vs_dhw": caleta_hits - dhw_hits,
        "stations": ranked,
        "claim": (
            f"Con {k} inmersiones, Caleta habría inspeccionado {caleta_hits} de {n_severe} "
            f"episodios severos observados. Ordenar por DHW (termómetro NOAA) habría pillado {dhw_hits}."
        ),
    }


def station_history(property_id: str, site_id: str) -> dict:
    df = load_observations()
    frame = _property_frame(df, property_id)
    hist = frame.loc[frame["Site_ID"].astype(str) == str(site_id)].sort_values("Date")
    if hist.empty:
        raise KeyError(f"Sitio {site_id} no está en {property_id}.")
    visits = []
    for _, row in hist.iterrows():
        visits.append(
            {
                "date": None if pd.isna(row.get("Date")) else str(pd.Timestamp(row["Date"]).date()),
                "year": None if pd.isna(row.get("Date_Year")) else int(row["Date_Year"]),
                "percent_bleaching": None
                if pd.isna(row.get("Percent_Bleaching"))
                else float(row["Percent_Bleaching"]),
                "observed": classify_bleaching(row.get("Percent_Bleaching")),
                "dhw": None if pd.isna(row.get("TSA_DHW")) else float(row["TSA_DHW"]),
            }
        )
    last = hist.iloc[-1]
    return {
        "site_id": str(site_id),
        "name": _station_name(last),
        "n_visits": len(visits),
        "visits": visits,
    }


def properties_catalog() -> dict:
    df = load_observations()
    items = []
    for spec in list_properties():
        try:
            frame = _property_frame(df, spec["id"])
            work = frame.loc[frame["Percent_Bleaching"].notna()].copy()
            work["target"] = 0
            _, snap = _last_visit_split(work)
            years = sorted(int(y) for y in snap["Date_Year"].dropna().unique())
            spec = dict(spec)
            spec["seasons"] = years
            spec["n_sites"] = int(snap["Site_ID"].nunique())
        except (ValueError, KeyError):
            spec = dict(spec)
            spec["seasons"] = []
            spec["n_sites"] = 0
        items.append(spec)
    return {"properties": items}
