"""Rutas y parámetros de Baliza. No escribe nada fuera de APP/."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
TFM_ROOT = APP_ROOT.parent
DATA_CSV = TFM_ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
ARTIFACTS = APP_ROOT / "artifacts"
FRONTEND_DIST = APP_ROOT / "frontend" / "dist"

NUMERIC_FEATURES = ["SSTA", "TSA", "TSA_DHW", "Depth_m", "Distance_to_Shore", "ClimSST"]
CATEGORICAL_FEATURES = ["Ocean_Name"]
CLASS_ORDER = ["Bajo", "Moderado", "Severo"]
RANDOM_STATE = 42
N_ESTIMATORS = 200
MAX_DEPTH = 8
MIN_SEASON_SITES = 25
MIN_TRAIN_ROWS = 80
MIN_TRAIN_SEVERE = 8
MODEL_VERSION = "rf8-dhw-local-v3"

FEATURE_COPY = {
    "TSA_DHW": "Degree Heating Weeks: estrés térmico acumulado en doce semanas (Coral Reef Watch).",
    "TSA": "Anomalía de estrés térmico: temperatura por encima del umbral de blanqueamiento.",
    "SSTA": "Anomalía de temperatura superficial respecto a la climatología del sitio.",
    "ClimSST": "Régimen térmico basal. En el TFM, valores altos tienden a reducir P(Severo).",
    "Depth_m": "Profundidad del muestreo. En el modelo global su SHAP mezcla protocolo y hábitat.",
    "Distance_to_Shore": "Distancia a costa; aproxima presiones terrestres. Efecto no monótono.",
}

FEATURE_PLAIN = {
    "TSA_DHW": {
        "name": "Estrés acumulado (DHW)",
        "plain": "Cuánto calor extra lleva el agua en las últimas 12 semanas.",
    },
    "TSA": {
        "name": "Calor sobre el umbral",
        "plain": "Si hoy el agua está más caliente que el umbral de blanqueo.",
    },
    "SSTA": {
        "name": "Anomalía de temperatura",
        "plain": "Si está más caliente de lo normal en ese mismo sitio.",
    },
    "ClimSST": {
        "name": "Temperatura habitual",
        "plain": "Lo cálido que suele ser ese arrecife. Un sitio ya cálido no siempre sale peor.",
    },
    "Depth_m": {
        "name": "Profundidad",
        "plain": "A qué profundidad se midió. Cambia el estrés y cómo se muestreó.",
    },
    "Distance_to_Shore": {
        "name": "Distancia a costa",
        "plain": "Qué tan cerca está de tierra (escorrentía, gente, puertos).",
    },
}

RANK_MODEL_SHARE = 0.55
RANK_DHW_SHARE = 0.45
RANK_DHW_CAP = 8.0

CRW_LEVELS = (
    (8.0, "Alerta 2", 4),
    (4.0, "Alerta 1", 3),
    (1.0, "Aviso", 2),
)
