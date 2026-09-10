"""Motor operativo: modelo local, CRW, AOA y ranking por presupuesto.

El clasificador es el Random Forest oficial del TFM (200 árboles, profundidad 8,
TSA_DHW incluido), calibrado solo con el histórico de la red elegida y de
temporadas anteriores a la campaña. No predice la severidad a 1–3 meses: estima
la severidad probable bajo las condiciones térmicas de esa temporada.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import (
    ARTIFACTS,
    CATEGORICAL_FEATURES,
    CLASS_ORDER,
    CRW_LEVELS,
    DATA_CSV,
    FEATURE_COPY,
    FEATURE_PLAIN,
    MAX_DEPTH,
    MIN_SEASON_SITES,
    MIN_TRAIN_ROWS,
    MIN_TRAIN_SEVERE,
    MODEL_VERSION,
    N_ESTIMATORS,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    RANK_DHW_CAP,
    RANK_DHW_SHARE,
    RANK_MODEL_SHARE,
)
from .networks import NETWORKS, bases_for
from .ops import (
    CAPABILITIES,
    apply_aoa_penalty,
    assign_home_bases,
    build_plans,
    campaign_savings,
    plan_routes,
    queue_counts,
    select_with_aoa_quota,
    zone_for,
)

try:
    import shap
except ImportError:  # pragma: no cover
    shap = None


def classify_bleaching(pct: float) -> str:
    if pd.isna(pct):
        return "Sin dato"
    if pct < 10:
        return "Bajo"
    if pct <= 30:
        return "Moderado"
    return "Severo"


def crw_level(dhw: float, tsa: float) -> tuple[str, int]:
    if pd.isna(dhw):
        return "Sin dato", 0
    for threshold, label, rank in CRW_LEVELS:
        if dhw >= threshold:
            return label, rank
    if not pd.isna(tsa) and tsa > 0:
        return "Vigilancia", 1
    return "Sin estrés", 0


def _station_name(row: pd.Series) -> str:
    site = row.get("Site_Name")
    city = row.get("City_Town_Name")
    lat = row.get("Latitude_Degrees")
    lon = row.get("Longitude_Degrees")
    if pd.notna(site) and str(site).strip() and str(site).strip().lower() not in {"nan", "nd"}:
        base = str(site).strip()
    elif pd.notna(city) and str(city).strip():
        base = str(city).strip()
    else:
        base = f"Estación {row['Site_ID']}"
    if pd.notna(lat) and pd.notna(lon):
        return f"{base} ({float(lat):.3f}, {float(lon):.3f})"
    return f"{base} · {row['Site_ID']}"


def _read_csv() -> pd.DataFrame:
    if not DATA_CSV.exists():
        raise FileNotFoundError(
            f"No se encuentra el dataset del TFM en {DATA_CSV}. "
            "Baliza lee en modo consulta; no modifica el proyecto original."
        )
    df = pd.read_csv(DATA_CSV, na_values=["nd", "ND"], low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if "Date_Year" not in df.columns or df["Date_Year"].isna().all():
        df["Date_Year"] = df["Date"].dt.year
    df["Date_Year"] = pd.to_numeric(df["Date_Year"], errors="coerce")
    return df


@lru_cache(maxsize=1)
def load_observations() -> pd.DataFrame:
    return _read_csv()


def network_frame(network_id: str) -> pd.DataFrame:
    if network_id not in NETWORKS:
        raise KeyError(f"Red desconocida: {network_id}")
    df = load_observations()
    mask = NETWORKS[network_id]["filter"](df)
    out = df.loc[mask].copy()
    if out.empty:
        raise ValueError(f"La red {network_id} no tiene observaciones.")
    return out


def seasons_for(network_id: str) -> list[dict]:
    df = network_frame(network_id)
    usable = df.loc[df["Percent_Bleaching"].notna() & df["TSA_DHW"].notna()]
    rows = []
    for year, grp in usable.groupby(usable["Date_Year"].dropna().astype(int)):
        n_sites = int(grp["Site_ID"].nunique())
        if n_sites < MIN_SEASON_SITES:
            continue
        pct = grp["Percent_Bleaching"]
        rows.append(
            {
                "year": int(year),
                "sites": n_sites,
                "observations": int(len(grp)),
                "severe_rate": float((pct > 30).mean()),
                "dhw_mean": float(grp["TSA_DHW"].mean()),
                "dhw_max": float(grp["TSA_DHW"].max()),
            }
        )
    return sorted(rows, key=lambda r: r["year"])


def list_networks() -> list[dict]:
    catalog = []
    for item in NETWORKS.values():
        seasons = seasons_for(item["id"])
        catalog.append(
            {
                "id": item["id"],
                "name": item["name"],
                "region": item["region"],
                "buyer": item["buyer"],
                "scenario": item["scenario"],
                "note": item["note"],
                "default_season": item["default_season"],
                "center": item["center"],
                "zoom": item["zoom"],
                "bases": bases_for(item["id"]),
                "seasons": seasons,
                "n_seasons": len(seasons),
            }
        )
    return catalog


def _season_snapshot(df: pd.DataFrame, year: int) -> pd.DataFrame:
    season = df.loc[df["Date_Year"] == year].copy()
    season = season.loc[season["TSA_DHW"].notna()]
    if season.empty:
        return season
    season["_peak"] = season["TSA_DHW"]
    season = season.sort_values(["Site_ID", "_peak", "Date"], ascending=[True, False, False])
    snap = season.groupby("Site_ID", as_index=False).head(1).drop(columns="_peak")
    snap["observed_class"] = snap["Percent_Bleaching"].map(classify_bleaching)
    snap["observed_severe"] = (snap["Percent_Bleaching"] > 30).fillna(False).astype(bool)
    return snap.reset_index(drop=True)


def _train_table(df: pd.DataFrame, year: int) -> pd.DataFrame:
    hist = df.loc[df["Date_Year"] < year].copy()
    hist = hist.loc[hist["Percent_Bleaching"].notna()]
    hist["Bleaching_Class"] = hist["Percent_Bleaching"].map(classify_bleaching)
    hist = hist.loc[hist["Bleaching_Class"].isin(CLASS_ORDER)]
    return hist


def _build_pipeline() -> Pipeline:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    prep = ColumnTransformer(
        transformers=[
            ("num", numeric, NUMERIC_FEATURES),
            ("cat", categorical, CATEGORICAL_FEATURES),
        ]
    )
    rf = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    return Pipeline([("prep", prep), ("clf", rf)])


def _transformed_matrix(pipe: Pipeline, frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    prep: ColumnTransformer = pipe.named_steps["prep"]
    matrix = prep.transform(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
    names = [name.split("__", 1)[-1] for name in prep.get_feature_names_out()]
    return np.asarray(matrix), names


def _shap_weights(pipe: Pipeline, X: np.ndarray, class_index: int) -> np.ndarray:
    clf = pipe.named_steps["clf"]
    n_features = X.shape[1]
    if shap is None or X.shape[0] < 10:
        weights = np.asarray(clf.feature_importances_, dtype=float)
        if weights.size != n_features:
            weights = np.ones(n_features, dtype=float)
        return np.clip(weights, 1e-8, None)

    sample = X if len(X) <= 250 else X[np.random.default_rng(RANDOM_STATE).choice(len(X), 250, replace=False)]
    explainer = shap.TreeExplainer(clf)
    values = explainer.shap_values(sample)
    if isinstance(values, list):
        arr = np.asarray(values[class_index])
    else:
        arr = np.asarray(values)
        if arr.ndim == 3:
            arr = arr[:, :, class_index]
    weights = np.abs(arr).mean(axis=0)
    return np.clip(np.asarray(weights, dtype=float), 1e-8, None)


def _aoa_fit(X: np.ndarray, weights: np.ndarray) -> dict:
    w = np.clip(weights[: X.shape[1]], 1e-8, None)
    w = w / w.sum()
    weighted = X * np.sqrt(w)
    nn = NearestNeighbors(n_neighbors=2, algorithm="auto")
    nn.fit(weighted)
    dist = nn.kneighbors(weighted, n_neighbors=2)[0][:, 1]
    q1, q3 = np.percentile(dist, [25, 75])
    threshold = float(q3 + 1.5 * (q3 - q1))
    return {"nn": nn, "threshold": threshold, "weights": w}


def _aoa_score(pack: dict, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    weighted = X * np.sqrt(pack["weights"][: X.shape[1]])
    di = pack["nn"].kneighbors(weighted, n_neighbors=1)[0][:, 0]
    inside = di <= pack["threshold"]
    return di, inside


def _artifact_path(network_id: str, year: int, n_train: int) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{MODEL_VERSION}|{network_id}|{year}|{n_train}".encode()).hexdigest()[:12]
    return ARTIFACTS / f"{network_id}_{year}_{key}.joblib"


def _fit_local_model(train: pd.DataFrame, network_id: str, year: int) -> dict:
    path = _artifact_path(network_id, year, len(train))
    if path.exists():
        return joblib.load(path)

    pipe = _build_pipeline()
    X = train[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = train["Bleaching_Class"]
    pipe.fit(X, y)
    X_mat, feat_names = _transformed_matrix(pipe, train)
    classes = list(pipe.named_steps["clf"].classes_)
    severe_idx = classes.index("Severo") if "Severo" in classes else 0
    weights = _shap_weights(pipe, X_mat, severe_idx)
    aoa = _aoa_fit(X_mat[:, : len(NUMERIC_FEATURES)], weights[: len(NUMERIC_FEATURES)])
    p_train = _proba(pipe, train, classes)["Severo"]
    y_severe = (y == "Severo").astype(int).to_numpy()
    calibrator = None
    if y_severe.min() != y_severe.max():
        calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        calibrator.fit(p_train, y_severe)
    pack = {
        "pipeline": pipe,
        "feature_names": feat_names,
        "classes": classes,
        "severe_idx": severe_idx,
        "shap_weights": weights,
        "aoa": aoa,
        "calibrator": calibrator,
        "n_train": int(len(train)),
        "n_train_sites": int(train["Site_ID"].nunique()),
        "severe_rate_train": float((y == "Severo").mean()),
        "year_min": int(train["Date_Year"].min()),
        "year_max": int(train["Date_Year"].max()),
    }
    joblib.dump(pack, path)
    return pack


def _proba(pipe: Pipeline, frame: pd.DataFrame, classes: list[str]) -> np.ndarray:
    proba = pipe.predict_proba(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
    out = {label: proba[:, i] for i, label in enumerate(classes)}
    for label in CLASS_ORDER:
        out.setdefault(label, np.zeros(len(frame)))
    return out


def _uncertainty(p_severe: float, inside: bool, di: float, threshold: float) -> str:
    if not inside:
        return "alta"
    if threshold > 0 and di > 0.75 * threshold:
        return "media"
    if 0.28 <= p_severe <= 0.55:
        return "media"
    return "baja"


def _priority_explain(weights: np.ndarray) -> dict:
    n = len(NUMERIC_FEATURES)
    raw = np.clip(np.asarray(weights[:n], dtype=float), 0.0, None)
    total = float(raw.sum()) or 1.0
    drivers = []
    for i, key in enumerate(NUMERIC_FEATURES):
        meta = FEATURE_PLAIN[key]
        drivers.append(
            {
                "id": key,
                "name": meta["name"],
                "plain": meta["plain"],
                "share": round(float(raw[i] / total), 4),
            }
        )
    drivers.sort(key=lambda item: item["share"], reverse=True)
    return {
        "model_share": RANK_MODEL_SHARE,
        "dhw_share": RANK_DHW_SHARE,
        "how": (
            f"El orden de las inmersiones mezcla dos cosas: un {int(RANK_MODEL_SHARE * 100)} % "
            "el riesgo de episodio severo que estima el bosque de esta red, y un "
            f"{int(RANK_DHW_SHARE * 100)} % el DHW de NOAA "
            f"(calor acumulado, tope Alerta 2 = {int(RANK_DHW_CAP)})."
        ),
        "drivers": drivers,
    }


def _factors(row: pd.Series, medians: pd.Series, weights: np.ndarray) -> list[dict]:
    items = []
    for i, name in enumerate(NUMERIC_FEATURES):
        value = row.get(name)
        ref = medians.get(name)
        if pd.isna(value) or pd.isna(ref):
            continue
        direction = "aumenta" if value > ref else "reduce"
        if name == "ClimSST":
            direction = "reduce" if value > ref else "aumenta"
        items.append(
            {
                "feature": name,
                "label": FEATURE_COPY[name],
                "value": float(value),
                "network_median": float(ref),
                "weight": float(weights[i]) if i < len(weights) else 0.0,
                "direction": direction,
                "delta": float(value - ref),
            }
        )
    items.sort(key=lambda x: abs(x["delta"]) * (x["weight"] + 1e-6), reverse=True)
    return items[:4]


def _explain_row(pack: dict, frame: pd.DataFrame) -> list[dict]:
    if shap is None or frame.empty:
        return []
    pipe = pack["pipeline"]
    clf = pipe.named_steps["clf"]
    X, names = _transformed_matrix(pipe, frame)
    explainer = shap.TreeExplainer(clf)
    values = explainer.shap_values(X)
    if isinstance(values, list):
        arr = np.asarray(values[pack["severe_idx"]])
    else:
        arr = np.asarray(values)
        if arr.ndim == 3:
            arr = arr[:, :, pack["severe_idx"]]
    row = arr[0]
    pairs = sorted(zip(names, row), key=lambda kv: abs(kv[1]), reverse=True)
    out = []
    for name, val in pairs[:5]:
        out.append(
            {
                "feature": name,
                "shap": float(val),
                "effect": "aumenta P(Severo)" if val > 0 else "reduce P(Severo)",
                "label": FEATURE_COPY.get(name, name),
            }
        )
    return out


def _station_payload(
    row: pd.Series,
    p: dict[str, float],
    di: float,
    inside: bool,
    tau: float,
    medians: pd.Series,
    weights: np.ndarray,
    rank: int | None,
    selected: bool,
) -> dict:
    dhw = float(row["TSA_DHW"]) if pd.notna(row["TSA_DHW"]) else None
    tsa = float(row["TSA"]) if pd.notna(row["TSA"]) else None
    crw_name, crw_rank = crw_level(row["TSA_DHW"], row["TSA"])
    p_sev = float(p["Severo"])
    model_class = max(CLASS_ORDER, key=lambda c: p[c])
    model_alert = p_sev >= tau
    crw_alert = crw_rank >= 3
    if model_alert and crw_alert:
        disagreement = "consenso"
        disagreement_label = "Consenso: modelo y Coral Reef Watch coinciden en inspeccionar"
    elif model_alert and not crw_alert:
        disagreement = "modelo"
        disagreement_label = "Prioridad no cubierta por DHW ≥ 4 °C·semana"
    elif crw_alert and not model_alert:
        disagreement = "crw"
        disagreement_label = "CRW alerta; el modelo local sugiere menor prioridad"
    else:
        disagreement = "ninguno"
        disagreement_label = "Baja prioridad para ambos criterios"
    name = _station_name(row)
    return {
        "site_id": str(row["Site_ID"]),
        "name": str(name),
        "country": None if pd.isna(row.get("Country_Name")) else str(row["Country_Name"]),
        "locality": None if pd.isna(row.get("City_Town_Name")) else str(row["City_Town_Name"]),
        "source": None if pd.isna(row.get("Data_Source")) else str(row["Data_Source"]),
        "lat": float(row["Latitude_Degrees"]) if pd.notna(row["Latitude_Degrees"]) else None,
        "lon": float(row["Longitude_Degrees"]) if pd.notna(row["Longitude_Degrees"]) else None,
        "date": None if pd.isna(row.get("Date")) else pd.Timestamp(row["Date"]).strftime("%Y-%m-%d"),
        "depth_m": None if pd.isna(row.get("Depth_m")) else float(row["Depth_m"]),
        "distance_to_shore": None if pd.isna(row.get("Distance_to_Shore")) else float(row["Distance_to_Shore"]),
        "ssta": None if pd.isna(row.get("SSTA")) else float(row["SSTA"]),
        "tsa": tsa,
        "dhw": dhw,
        "climsst": None if pd.isna(row.get("ClimSST")) else float(row["ClimSST"]),
        "crw_level": crw_name,
        "crw_rank": crw_rank,
        "p_bajo": float(p["Bajo"]),
        "p_moderado": float(p["Moderado"]),
        "p_severo": p_sev,
        "model_class": model_class,
        "operational_alert": model_alert,
        "inside_aoa": bool(inside),
        "dissimilarity": float(di),
        "uncertainty": _uncertainty(p_sev, bool(inside), float(di), float(row.get("_aoa_threshold", 0) or 0)),
        "observed_class": row.get("observed_class"),
        "observed_bleaching": None if pd.isna(row.get("Percent_Bleaching")) else float(row["Percent_Bleaching"]),
        "observed_severe": bool(row.get("observed_severe", False)),
        "disagreement": disagreement,
        "disagreement_label": disagreement_label,
        "rank": rank,
        "selected": selected,
        "zone": "Sin posición",
        "boat_day": None,
        "boat_label": None,
        "visit_order": None,
        "base_id": None,
        "base_name": None,
        "base_kind": None,
        "leg_km": None,
        "home_base_id": None,
        "home_base_name": None,
        "home_base_kind": None,
        "data_as_of": None,
        "factors": _factors(row, medians, weights),
    }


def _backtest(stations: list[dict], dives: int) -> dict:
    n = len(stations)
    k = max(0, min(dives, n))
    observed = [s for s in stations if s.get("observed_class") != "Sin dato"]
    n_obs = len(observed)
    n_severe = sum(1 for s in observed if s["observed_severe"])
    by_model = sorted(observed, key=lambda s: s["p_severo"], reverse=True)
    by_dhw = sorted(observed, key=lambda s: (s["dhw"] is not None, s["dhw"] or -1), reverse=True)
    by_product = sorted(observed, key=lambda s: s["priority_score"], reverse=True)
    crw_first = sorted(
        observed,
        key=lambda s: (s["crw_rank"] >= 3, s["dhw"] or -1),
        reverse=True,
    )

    def caught(seq: list[dict]) -> int:
        return sum(1 for s in seq[:k] if s["observed_severe"])

    model_caught = caught(by_model)
    dhw_caught = caught(by_dhw)
    product_caught = caught(by_product)
    crw_caught = caught(crw_first)
    expected = float(sum(s["p_severo"] for s in by_product[:k]))
    return {
        "sites_with_observation": n_obs,
        "severe_observed": n_severe,
        "dives": k,
        "model_caught": model_caught,
        "dhw_caught": dhw_caught,
        "product_caught": product_caught,
        "crw_then_dhw_caught": crw_caught,
        "model_expected": expected,
        "model_recall": (product_caught / n_severe) if n_severe else None,
        "crw_recall": (crw_caught / n_severe) if n_severe else None,
        "lift_vs_crw": product_caught - crw_caught,
        "coverage_vs_all": (k / n_obs) if n_obs else None,
    }


def build_campaign(
    network_id: str,
    season: int | None,
    dives: int,
    cost_false_alarm: float,
    cost_miss: float,
    boat_days: int = 3,
    cost_dive_eur: float = 400.0,
    hours_per_dive: float = 3.0,
    aoa_quota: float = 0.25,
    origin_id: str | None = None,
) -> dict:
    meta = NETWORKS[network_id]
    df = network_frame(network_id)
    seasons = seasons_for(network_id)
    if not seasons:
        raise ValueError("Esta red no tiene temporadas con suficientes estaciones.")

    def trainable(year_value: int) -> bool:
        hist = _train_table(df, year_value)
        return len(hist) >= MIN_TRAIN_ROWS and int((hist["Bleaching_Class"] == "Severo").sum()) >= MIN_TRAIN_SEVERE

    viable = [s["year"] for s in seasons if trainable(s["year"])]
    if not viable:
        raise ValueError("Ninguna temporada de esta red tiene histórico local suficiente.")
    preferred = int(season or meta["default_season"])
    year = preferred if preferred in viable else min(viable, key=lambda y: abs(y - preferred))

    train = _train_table(df, year)
    snap = _season_snapshot(df, year).reset_index(drop=True)
    if len(snap) < 8:
        raise ValueError("Temporada sin estaciones suficientes para armar una campaña.")

    pack = _fit_local_model(train, network_id, year)
    pipe = pack["pipeline"]
    classes = pack["classes"]
    proba = _proba(pipe, snap, classes)
    p_rank = np.asarray(proba["Severo"], dtype=float)
    calibrator = pack.get("calibrator")
    if calibrator is not None:
        proba["Severo"] = np.asarray(calibrator.predict(p_rank), dtype=float)
    X_mat, _ = _transformed_matrix(pipe, snap)
    di, inside = _aoa_score(pack["aoa"], X_mat[:, : len(NUMERIC_FEATURES)])
    tau = float(cost_false_alarm / (cost_false_alarm + cost_miss))
    medians = train[NUMERIC_FEATURES].median(numeric_only=True)
    weights = np.asarray(pack["shap_weights"], dtype=float)

    raw = []
    for i, row in snap.iterrows():
        idx = int(i)
        p = {label: float(proba[label][idx]) for label in CLASS_ORDER}
        row = row.copy()
        row["_aoa_threshold"] = pack["aoa"]["threshold"]
        station = _station_payload(
            row,
            p,
            float(di[idx]),
            bool(inside[idx]),
            tau,
            medians,
            weights,
            rank=None,
            selected=False,
        )
        dhw = station["dhw"]
        thermal = 0.0 if dhw is None else float(min(max(dhw, 0.0) / RANK_DHW_CAP, 1.0))
        raw_score = float(RANK_MODEL_SHARE * p_rank[idx] + RANK_DHW_SHARE * thermal)
        station["priority_score"] = apply_aoa_penalty(raw_score, station["inside_aoa"])
        station["zone"] = zone_for(network_id, station["lat"], station["lon"])
        station["data_as_of"] = station["date"]
        raw.append(station)

    assign_home_bases(raw, network_id)
    ranked = sorted(raw, key=lambda s: s["priority_score"], reverse=True)
    k = max(1, min(int(dives), len(ranked)))
    chosen = select_with_aoa_quota(ranked, k, aoa_quota)
    chosen_ids = {s["site_id"] for s in chosen}
    routes = plan_routes(
        [s for s in ranked if s["site_id"] in chosen_ids],
        network_id,
        boat_days,
        origin_id=origin_id,
    )
    for i, station in enumerate(ranked, start=1):
        station["rank"] = i
        station["selected"] = station["site_id"] in chosen_ids
        if not station["selected"]:
            station["boat_day"] = None
            station["boat_label"] = None
            station["visit_order"] = None
            station["base_id"] = None
            station["base_name"] = None
            station["base_kind"] = None
            station["leg_km"] = None

    backtest = _backtest(ranked, k)
    selected = [s for s in ranked if s["selected"]]
    n_alert = sum(1 for s in ranked if s["operational_alert"])
    n_aoa = sum(1 for s in ranked if s["inside_aoa"])
    extra_vs_crw = [s for s in selected if s["disagreement"] == "modelo"]
    crw_downgraded = [s for s in ranked if s["disagreement"] == "crw"]
    queues = queue_counts(ranked)
    queues_budget = queue_counts(ranked, selected_only=True)
    plans = build_plans(ranked, chosen_ids, k, cost_dive_eur, hours_per_dive)
    savings = campaign_savings(ranked, k, cost_dive_eur, hours_per_dive)
    dates = [s["date"] for s in ranked if s.get("date")]
    capabilities = [dict(item) for item in CAPABILITIES]

    return {
        "product": "Baliza",
        "claim": (
            "Con el presupuesto disponible, qué arrecifes inspeccionar primero, "
            "con qué nivel de confianza y por qué."
        ),
        "disclaimer": (
            "Esto no es una alerta temprana a uno, dos o tres meses. "
            "Es una evaluación de severidad probable bajo las condiciones térmicas "
            "de la temporada, para priorizar inspecciones en una red ya conocida."
        ),
        "network": {
            "id": meta["id"],
            "name": meta["name"],
            "region": meta["region"],
            "buyer": meta["buyer"],
            "scenario": meta["scenario"],
            "note": meta["note"],
            "center": meta["center"],
            "zoom": meta["zoom"],
            "bases": bases_for(network_id),
        },
        "season": year,
        "seasons": seasons,
        "model": {
            "name": "Prioridad operativa: Random Forest local (profundidad 8) + DHW",
            "version": MODEL_VERSION,
            "trained_on": f"{pack['year_min']}–{pack['year_max']}",
            "n_train": pack["n_train"],
            "n_train_sites": pack["n_train_sites"],
            "severe_rate_train": pack["severe_rate_train"],
            "competitor": "Regla Coral Reef Watch: DHW ≥ 4 °C·semana",
            "ranking": (
                f"No sustituye a NOAA: combina el riesgo del bosque local ({int(RANK_MODEL_SHARE * 100)} %) "
                f"con la intensidad DHW en la escala de Alerta 2 (DHW/{int(RANK_DHW_CAP)}, {int(RANK_DHW_SHARE * 100)} %). "
                "La P(Severo) que se muestra está calibrada; el orden usa también el DHW."
            ),
        },
        "priority": _priority_explain(weights),
        "threshold": {
            "cost_false_alarm": cost_false_alarm,
            "cost_miss": cost_miss,
            "tau": tau,
            "rule": "Inspeccionar si P(Severo) ≥ C_falsa / (C_falsa + C_omisión)",
            "cost_dive_eur": cost_dive_eur,
            "hours_per_dive": hours_per_dive,
            "budget_eur": round(k * cost_dive_eur, 0),
            "budget_hours": round(k * hours_per_dive, 1),
            "aoa_quota": aoa_quota,
            "boat_days": int(boat_days),
            "origin_id": (origin_id or "auto"),
        },
        "aoa": {
            "method": "Índice de disimilitud de Meyer y Pebesma (2021), umbral Q3 + 1,5 IQR",
            "threshold": float(pack["aoa"]["threshold"]),
            "inside_share": n_aoa / len(ranked) if ranked else 0.0,
            "quota_note": (
                f"Como máximo el {int(aoa_quota * 100)} % del presupuesto puede "
                "estar fuera del área de aplicabilidad."
            ),
        },
        "kpis": {
            "stations": len(ranked),
            "dives": k,
            "alerts": n_alert,
            "inside_aoa": n_aoa,
            "inside_budget": sum(1 for s in selected if s["inside_aoa"]),
            "mean_p_severo": float(np.mean([s["p_severo"] for s in ranked])),
            "mean_dhw": float(np.nanmean([s["dhw"] for s in ranked if s["dhw"] is not None])),
            "model_only_in_budget": len(extra_vs_crw),
            "crw_downgraded": len(crw_downgraded),
            "budget_eur": round(k * cost_dive_eur, 0),
            "budget_hours": round(k * hours_per_dive, 1),
        },
        "queues": {"all": queues, "budget": queues_budget},
        "plans": plans,
        "routes": routes,
        "savings": savings,
        "capabilities": capabilities,
        "freshness": {
            "mode": "histórico",
            "as_of": max(dates) if dates else None,
            "label": (
                f"Temporada {year} · último muestreo del recorte "
                f"{max(dates) if dates else 'n/d'}. No es el DHW de hoy."
            ),
        },
        "backtest": backtest,
        "stations": ranked,
        "language": {
            "do": [
                "priorización operativa",
                "evaluación de severidad probable bajo condiciones actuales",
                "apoyo al seguimiento",
                "detección y focalización de inspecciones",
            ],
            "dont": [
                "predicción de blanqueamiento a tres meses",
                "alerta temprana autónoma global",
                "IA que supera a NOAA en cualquier cuenca",
            ],
        },
    }


def station_detail(network_id: str, season: int, site_id: str, cost_false_alarm: float, cost_miss: float) -> dict:
    campaign = build_campaign(network_id, season, dives=10**6, cost_false_alarm=cost_false_alarm, cost_miss=cost_miss)
    match = next((s for s in campaign["stations"] if s["site_id"] == str(site_id)), None)
    if match is None:
        raise KeyError(f"Estación {site_id} no está en la temporada {season}.")

    df = network_frame(network_id)
    hist = df.loc[df["Site_ID"].astype(str) == str(site_id)].sort_values("Date")
    history = []
    for _, row in hist.iterrows():
        history.append(
            {
                "date": None if pd.isna(row.get("Date")) else pd.Timestamp(row["Date"]).strftime("%Y-%m-%d"),
                "year": None if pd.isna(row.get("Date_Year")) else int(row["Date_Year"]),
                "dhw": None if pd.isna(row.get("TSA_DHW")) else float(row["TSA_DHW"]),
                "tsa": None if pd.isna(row.get("TSA")) else float(row["TSA"]),
                "bleaching": None if pd.isna(row.get("Percent_Bleaching")) else float(row["Percent_Bleaching"]),
                "observed_class": classify_bleaching(row.get("Percent_Bleaching")),
            }
        )

    train = _train_table(df, int(campaign["season"]))
    pack = _fit_local_model(train, network_id, int(campaign["season"]))
    snap = _season_snapshot(df, int(campaign["season"]))
    row = snap.loc[snap["Site_ID"].astype(str) == str(site_id)]
    shap_rows = _explain_row(pack, row) if not row.empty else []
    match = dict(match)
    match["shap"] = shap_rows
    match["history"] = history
    match["network"] = campaign["network"]
    match["season"] = campaign["season"]
    match["threshold"] = campaign["threshold"]
    match["disclaimer"] = campaign["disclaimer"]
    return match


def _mean(values: list) -> float | None:
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None
    return sum(xs) / len(xs)


def _aoa_skipped(station: dict, selected: list[dict]) -> bool:
    if station.get("selected") or station.get("inside_aoa"):
        return False
    return any(pick["rank"] > station["rank"] for pick in selected)


def _why_chosen(station: dict) -> str:
    key = station.get("disagreement")
    if key == "consenso":
        text = "El bosque y NOAA coinciden: hay riesgo y hay calor."
    elif key == "modelo":
        text = "El bosque lo ve grave aunque NOAA no lo marque (DHW bajo)."
    elif key == "crw":
        text = "NOAA marca calor; entra porque el DHW sube la nota de visita."
    else:
        text = "Entra por la nota combinada (bosque + DHW), sin alerta fuerte."
    if not station.get("inside_aoa"):
        text += " Entra con recelo: se parece poco al histórico de esta red."
    return text


def _why_left_out(station: dict, k: int, skipped_for_aoa: bool) -> str:
    dhw = station.get("dhw") or 0
    p_sev = float(station.get("p_severo") or 0)
    if skipped_for_aoa:
        return (
            "Iba alto en la lista, pero se parece poco al histórico "
            "y el cupo de sitios raros ya estaba lleno."
        )
    if dhw >= 4 and p_sev < 0.2:
        return "Hay calor (NOAA alerta), pero el bosque no lo ve tan grave y el cupo ya estaba lleno."
    if p_sev < 0.1 and dhw < 4:
        return "Poco riesgo y poco calor: no merece una inmersión de este cupo."
    return f"Queda fuera porque solo caben {k} inmersiones y otras estaciones tienen mejor nota."


def campaign_brief(campaign: dict) -> str:
    net = campaign["network"]
    bt = campaign["backtest"]
    k = campaign["kpis"]
    selected = sorted(
        [s for s in campaign["stations"] if s["selected"]],
        key=lambda s: s["rank"],
    )
    lines = [
        f"# Informe de campaña — {net['name']} ({campaign['season']})",
        "",
        campaign["disclaimer"],
        "",
        f"**Propuesta de valor:** {campaign['claim']}",
        "",
        "## Decisión",
        f"- Red: {net['name']} ({net['scenario']})",
        f"- Temporada evaluada: {campaign['season']}",
        f"- Presupuesto: {k['dives']} inspecciones · {campaign['threshold']['budget_eur']:.0f} € · "
        f"{campaign['threshold']['budget_hours']} h de campo",
        f"- Umbral operativo τ = {campaign['threshold']['tau']:.3f} "
        f"(falsa alarma {campaign['threshold']['cost_false_alarm']:.1f} / "
        f"omisión {campaign['threshold']['cost_miss']:.1f}; inmersión "
        f"{campaign['threshold']['cost_dive_eur']:.0f} € / {campaign['threshold']['hours_per_dive']} h)",
        f"- Estaciones dentro del área de aplicabilidad: {k['inside_aoa']} "
        f"({100 * campaign['aoa']['inside_share']:.0f} %)",
        "",
    ]
    sav = campaign.get("savings") or {}
    pri = campaign.get("priority") or {}
    lines += [
        "",
        "## Qué mira Baliza y cuánto cuenta",
        pri.get("how", campaign["model"]["ranking"]),
        "",
    ]
    for driver in pri.get("drivers") or []:
        lines.append(
            f"- {driver['name']}: {100 * driver['share']:.0f} % del bosque. {driver['plain']}"
        )
    leftover = sorted(
        [s for s in campaign["stations"] if not s["selected"]],
        key=lambda s: s["rank"],
    )
    last_in = selected[-1] if selected else None
    first_out = leftover[0] if leftover else None
    aoa_blocked = [s for s in leftover if _aoa_skipped(s, selected)]
    noaa_left = [s for s in leftover if (s.get("dhw") or 0) >= 4]
    in_p = _mean([s.get("p_severo") for s in selected])
    in_dhw = _mean([s.get("dhw") for s in selected])
    out_p = _mean([s.get("p_severo") for s in leftover])
    out_dhw = _mean([s.get("dhw") for s in leftover])
    model_pct = int(round(100 * pri.get("model_share", 0.55)))
    dhw_pct = int(round(100 * pri.get("dhw_share", 0.45)))
    quota_pct = int(round(100 * campaign["threshold"].get("aoa_quota", 0.25)))
    n_consenso = sum(1 for s in selected if s.get("disagreement") == "consenso")
    n_modelo = sum(1 for s in selected if s.get("disagreement") == "modelo")
    n_crw = sum(1 for s in selected if s.get("disagreement") == "crw")
    lines += [
        "",
        "## Por qué entran estas estaciones (y no las otras)",
        (
            f"Solo caben {k['dives']} inmersiones. Baliza ordena las {k['stations']} "
            f"estaciones de la red por una nota: {model_pct} % el bosque de esta AMP y "
            f"{dhw_pct} % el DHW de NOAA. Si un punto se parece poco al histórico "
            f"(fuera del área de aplicabilidad), su nota se recorta y, como máximo, "
            f"{quota_pct} % de las paradas pueden ser de ese tipo. Entran las "
            f"{k['dives']} primeras de esa lista, salvo sitios raros que se saltan "
            "si el cupo de “poco parecido al histórico” ya está lleno. Por eso la "
            f"última del cupo no tiene por qué ser el puesto {k['dives']}."
        ),
        "",
        "### Entran en el cupo",
        (
            f"{len(selected)} estaciones. Riesgo medio "
            f"{'n/d' if in_p is None else f'{100 * in_p:.0f} %'} · DHW medio "
            f"{'n/d' if in_dhw is None else f'{in_dhw:.1f}'}. "
            f"{n_consenso} las marcan las dos, {n_modelo} las caza solo Baliza, "
            f"{n_crw} las marca NOAA por calor."
        ),
    ]
    if last_in:
        lines.append(
            f"Última plaza del cupo: {last_in['name']} (n.º {last_in['rank']} de la cola). {_why_chosen(last_in)}"
        )
    lines += [
        "",
        "### Quedan fuera",
    ]
    if not leftover:
        lines.append("El cupo cubre la red entera: no se descarta ninguna estación.")
    else:
        noaa_bit = (
            "1 todavía tiene alerta NOAA (DHW ≥ 4)"
            if len(noaa_left) == 1
            else f"{len(noaa_left)} todavía tienen alerta NOAA (DHW ≥ 4)"
        )
        aoa_bit = ""
        if len(aoa_blocked) == 1:
            aoa_bit = "; 1 se saltó aunque iba alta porque se parece poco al histórico"
        elif len(aoa_blocked) > 1:
            aoa_bit = (
                f"; {len(aoa_blocked)} se saltaron aunque iban altas "
                "porque se parecen poco al histórico"
            )
        lines.append(
            f"{len(leftover)} estaciones. No es que estén sanas: el cupo está lleno. "
            f"Riesgo medio {'n/d' if out_p is None else f'{100 * out_p:.0f} %'} · "
            f"DHW medio {'n/d' if out_dhw is None else f'{out_dhw:.1f}'}. "
            f"{noaa_bit}{aoa_bit}."
        )
        if first_out:
            lines.append(
                f"Primera que no entra: {first_out['name']} (n.º {first_out['rank']} de la cola). "
                f"{_why_left_out(first_out, k['dives'], _aoa_skipped(first_out, selected))}"
            )
        lines += ["", "Las que más cerca se quedaron:"]
        for station in leftover[:8]:
            lines.append(
                f"- Puesto {station['rank']}. {station['name']} — "
                f"P(Severo) {station['p_severo']:.2f}, "
                f"DHW {station['dhw'] if station['dhw'] is not None else 'n/d'}. "
                f"{_why_left_out(station, k['dives'], _aoa_skipped(station, selected))}"
            )
    lines += [
        "",
        "## Contraste con Coral Reef Watch",
        f"- Eventos severos observados en la temporada: {bt['severe_observed']}",
        f"- Con las mismas {k['dives']} inmersiones, Baliza localiza {bt['product_caught']} y NOAA/CRW {bt['crw_then_dhw_caught']} "
        f"(diferencia {bt['lift_vs_crw']:+d}).",
        f"- Sitios del cupo que NOAA no habría marcado (DHW < 4): {k['model_only_in_budget']}",
        "",
        "## Ahorro frente a NOAA / Coral Reef Watch",
        sav.get("note", "n/d"),
    ]
    if sav:
        lines.append(
            f"- Extra: {sav.get('extra_severe', 0)} episodios · {sav.get('extra_sites', 0)} puntos "
            f"que CRW no visita · ahorro {sav.get('eur_saved', 0):.0f} € / {sav.get('hours_saved', 0)} h"
        )
    lines += [
        "",
        "## Rutas de barco",
        "Cada salida parte de un muelle AMP o resort publicado, recorre las estaciones en orden y vuelve. Distancia geodésica, no ruteo náutico.",
    ]
    for route in campaign.get("routes") or []:
        base = route.get("base") or {}
        lines.append(
            f"- {route['label']}: {base.get('name')} ({base.get('kind_label')}) · "
            f"{route['n_dives']} inmersiones · {route['loop_km']} km de vuelta al muelle."
        )
        for stop in route.get("stops") or []:
            lines.append(f"  {stop['order']}. {stop['name']} ({stop['leg_km']} km)")
    lines += [
        "",
        "## Lista de inspección",
    ]
    for s in selected:
        aoa = "dentro AOA" if s["inside_aoa"] else "fuera AOA"
        stop = "" if s.get("visit_order") is None else f", parada {s['visit_order']}"
        lines.append(
            f"{s['rank']}. {s['name']} — P(Severo) {s['p_severo']:.2f}, "
            f"DHW {s['dhw'] if s['dhw'] is not None else 'n/d'}, "
            f"{s['crw_level']}, {aoa}. {s.get('boat_label') or 'sin salida'}{stop}. "
            f"{_why_chosen(s)}"
        )
    lines += [
        "",
        "## Alcance",
        "- El modelo está calibrado con el histórico de esta red, no con una cuenca nueva.",
        "- NOAA Coral Reef Watch sigue siendo el competidor gratuito; Baliza añade umbral, ranking y trazabilidad.",
        "- Validación externa independiente (AMP fuera de Sully et al.) sigue pendiente.",
        "",
        f"_Modelo {campaign['model']['name']} · {campaign['model']['trained_on']} · {MODEL_VERSION}_",
    ]
    return "\n".join(lines)


def nearest_thermal(lat: float, lon: float, network_id: str) -> dict:
    df = network_frame(network_id)
    df = df.loc[
        df["TSA_DHW"].notna()
        & df["Latitude_Degrees"].notna()
        & df["Longitude_Degrees"].notna()
    ]
    if df.empty:
        raise ValueError("No hay vecinos térmicos en esta red.")
    dist = (df["Latitude_Degrees"] - lat) ** 2 + (df["Longitude_Degrees"] - lon) ** 2
    row = df.loc[dist.idxmin()]
    return {
        "dhw": None if pd.isna(row.get("TSA_DHW")) else float(row["TSA_DHW"]),
        "ssta": None if pd.isna(row.get("SSTA")) else float(row["SSTA"]),
        "tsa": None if pd.isna(row.get("TSA")) else float(row["TSA"]),
        "climsst": None if pd.isna(row.get("ClimSST")) else float(row["ClimSST"]),
        "ocean": None if pd.isna(row.get("Ocean_Name")) else str(row["Ocean_Name"]),
        "depth_m": None if pd.isna(row.get("Depth_m")) else float(row["Depth_m"]),
        "distance_to_shore": None if pd.isna(row.get("Distance_to_Shore")) else float(row["Distance_to_Shore"]),
        "source": "vecino más cercano en Sully et al. (no es una medida nueva)",
        "neighbor_year": None if pd.isna(row.get("Date_Year")) else int(row["Date_Year"]),
    }


def score_custom_sites(network_id: str, rows: list[dict], use_live: bool = False) -> dict:
    """Puntúa estaciones subidas por CSV. El térmico es CRW en vivo o un vecino Sully."""
    from .live import probe_live_crw

    df = network_frame(network_id)
    year = int(df["Date_Year"].max()) + 1
    train = _train_table(df, year)
    if train.empty:
        raise ValueError("No hay histórico local para puntuar la red subida.")
    pack = _fit_local_model(train, network_id, year)
    live_probe = probe_live_crw() if use_live else {"ok": False}

    records = []
    for item in rows:
        thermal = {
            "dhw": item.get("dhw"),
            "ssta": item.get("ssta"),
            "tsa": item.get("tsa"),
            "climsst": item.get("climsst"),
            "source": "columnas del CSV",
        }
        if thermal["dhw"] is None and live_probe.get("ok"):
            live = probe_live_crw(item["lat"], item["lon"])
            if live.get("ok"):
                thermal = {
                    "dhw": live.get("dhw"),
                    "ssta": live.get("ssta"),
                    "tsa": live.get("tsa"),
                    "climsst": None,
                    "source": f"CRW en vivo ({live.get('time')})",
                }
        if thermal["dhw"] is None:
            thermal = nearest_thermal(item["lat"], item["lon"], network_id)
        records.append({**item, **{k: thermal.get(k) for k in ("dhw", "ssta", "tsa", "climsst")}, "thermal_source": thermal.get("source")})

    frame = pd.DataFrame(records)
    for col, default in (("depth_m", train["Depth_m"].median()), ("distance_to_shore", train["Distance_to_Shore"].median())):
        if col not in frame or frame[col].isna().all():
            frame[col] = default
        else:
            frame[col] = frame[col].fillna(default)
    frame["TSA_DHW"] = frame["dhw"]
    frame["SSTA"] = frame["ssta"].fillna(train["SSTA"].median())
    frame["TSA"] = frame["tsa"].fillna(train["TSA"].median())
    frame["ClimSST"] = frame["climsst"].fillna(train["ClimSST"].median())
    frame["Ocean_Name"] = train["Ocean_Name"].mode().iloc[0] if "Ocean_Name" in train else "Atlantic"
    frame["Depth_m"] = frame["depth_m"]
    frame["Distance_to_Shore"] = frame["distance_to_shore"]

    proba = _proba(pack["pipeline"], frame, pack["classes"])
    X_mat, _ = _transformed_matrix(pack["pipeline"], frame)
    di, inside = _aoa_score(pack["aoa"], X_mat[:, : len(NUMERIC_FEATURES)])
    stations = []
    for i, rec in enumerate(records):
        dhw = rec.get("dhw")
        tsa = rec.get("tsa")
        crw_name, crw_rank = crw_level(dhw if dhw is not None else np.nan, tsa if tsa is not None else np.nan)
        p_sev = float(proba["Severo"][i])
        thermal = 0.0 if dhw is None else float(min(max(dhw, 0.0) / 8.0, 1.0))
        stations.append(
            {
                "site_id": rec["site_id"],
                "name": rec["name"],
                "lat": rec["lat"],
                "lon": rec["lon"],
                "dhw": dhw,
                "tsa": tsa,
                "ssta": rec.get("ssta"),
                "p_severo": p_sev,
                "crw_level": crw_name,
                "crw_rank": crw_rank,
                "inside_aoa": bool(inside[i]),
                "dissimilarity": float(di[i]),
                "priority_score": apply_aoa_penalty(0.55 * p_sev + 0.45 * thermal, bool(inside[i])),
                "zone": zone_for(network_id, rec["lat"], rec["lon"]),
                "thermal_source": rec.get("thermal_source"),
                "observed_class": "Sin dato",
                "observed_severe": False,
                "disagreement": "modelo" if p_sev >= 0.2 and crw_rank < 3 else ("consenso" if crw_rank >= 3 else "ninguno"),
            }
        )
    stations.sort(key=lambda s: s["priority_score"], reverse=True)
    for i, station in enumerate(stations, start=1):
        station["rank"] = i
        station["selected"] = i <= min(12, len(stations))
    return {
        "network_id": network_id,
        "n": len(stations),
        "live_crw": bool(live_probe.get("ok")),
        "stations": stations,
        "note": "Red subida por CSV. El bosque no se ha reentrenado con estas estaciones.",
    }

