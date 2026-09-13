"""Rutas y parámetros. Caleta solo lee el CSV del TFM; no escribe fuera de caleta/."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
TFM_ROOT = APP_ROOT.parent
DATA_CSV = TFM_ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
ARTIFACTS = APP_ROOT / "artifacts"
FRONTEND_DIST = APP_ROOT / "frontend" / "dist"

NUMERIC_FEATURES = ["SSTA", "TSA", "TSA_DHW", "Depth_m", "Distance_to_Shore", "ClimSST"]
LOCAL_FEATURES = [
    "local_site_bleach_mean",
    "local_site_severo_rate",
    "local_site_dhw_mean",
    "local_site_n_hist",
    "local_site_last_class",
]
CATEGORICAL_FEATURES = ["Ocean_Name"]
CLASS_ORDER = ["Bajo", "Moderado", "Severo"]
RANDOM_STATE = 42
N_ESTIMATORS = 200
MAX_DEPTH = 6
MIN_TRAIN_ROWS = 80
MIN_TRAIN_SITES = 15
RESORT_RADIUS_KM = 45.0
RESORT_MIN_SITES = 8
MODEL_VERSION = "xgb-site-local-v1"
