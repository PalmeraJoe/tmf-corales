"""Preprocesado del dataset de blanqueamiento coralino para el modelado."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from eda import load_dataset

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

TARGET = "Percent_Bleaching"
TARGET_CLASS = "Bleaching_Class"

NUMERIC_FEATURES = ["SSTA", "TSA", "TSA_DHW", "Depth_m", "Distance_to_Shore", "ClimSST"]
CATEGORICAL_FEATURES = ["Ocean_Name"]

CLASS_ORDER = ["Bajo", "Moderado", "Severo"]
TEST_SIZE = 0.20
RANDOM_STATE = 42


def select_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra predictores térmicos/ambientales, categóricas regionales y el target."""
    required = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas requeridas en el dataset: {missing}")

    df_sel = df.loc[df[TARGET].notna(), required].copy()
    if df_sel.empty:
        raise ValueError("No quedan observaciones tras filtrar por Percent_Bleaching.")
    return df_sel


def add_bleaching_class(df: pd.DataFrame) -> pd.DataFrame:
    """Crea el target categórico ordenado por nivel de riesgo de blanqueamiento."""
    pct = df[TARGET]
    conditions = [pct < 10, pct <= 30]
    labels = ["Bajo", "Moderado"]
    df[TARGET_CLASS] = pd.Categorical(
        np.select(conditions, labels, default="Severo"),
        categories=CLASS_ORDER,
        ordered=True,
    )
    return df


def split_train_test(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide en 80/20 estratificando por nivel de riesgo para preservar eventos severos."""
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df[TARGET_CLASS],
    )
    return train_df, test_df


def build_preprocessor() -> ColumnTransformer:
    """Define el pipeline de imputación, escalado y codificación one-hot."""
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def clean_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Elimina los prefijos del ColumnTransformer para conservar el contexto marino."""
    names = preprocessor.get_feature_names_out()
    return [name.split("__", 1)[-1] for name in names]


def transform_split(
    preprocessor: ColumnTransformer,
    features: pd.DataFrame,
    targets: pd.DataFrame,
    feature_names: list[str],
) -> pd.DataFrame:
    """Transforma un subconjunto con el preprocesador ya ajustado y reincorpora los targets."""
    matrix = preprocessor.transform(features)
    transformed = pd.DataFrame(matrix, columns=feature_names, index=features.index)
    transformed[TARGET] = targets[TARGET]
    transformed[TARGET_CLASS] = targets[TARGET_CLASS]
    return transformed


def export_parquet(df: pd.DataFrame, path: Path) -> None:
    """Guarda un dataset procesado en formato parquet."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
    except (OSError, ImportError) as exc:
        raise RuntimeError(f"No se pudo exportar {path.name}: {exc}") from exc


def class_distribution(series: pd.Series) -> pd.DataFrame:
    """Resume el recuento y el porcentaje de cada nivel de riesgo."""
    counts = series.value_counts().reindex(CLASS_ORDER)
    return pd.DataFrame(
        {
            "n": counts,
            "%": (counts / counts.sum() * 100).round(2),
        }
    )


def main() -> None:
    """Ejecuta el preprocesado completo y exporta los conjuntos train/test."""
    df_raw = load_dataset(RAW_CSV)
    df = add_bleaching_class(select_variables(df_raw))

    print("=== Selección de variables ===")
    print(f"Observaciones con {TARGET} válido: {len(df):,}")
    print(f"Predictores numéricos: {NUMERIC_FEATURES}")
    print(f"Predictores categóricos: {CATEGORICAL_FEATURES}")
    print(f"Target continuo: {TARGET} | Target categórico: {TARGET_CLASS}")

    train_df, test_df = split_train_test(df)

    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    target_cols = [TARGET, TARGET_CLASS]

    # El preprocesador se ajusta únicamente con train para evitar Data Leakage.
    preprocessor = build_preprocessor()
    preprocessor.fit(train_df[feature_cols])
    feature_names = clean_feature_names(preprocessor)

    train_processed = transform_split(
        preprocessor, train_df[feature_cols], train_df[target_cols], feature_names
    )
    test_processed = transform_split(
        preprocessor, test_df[feature_cols], test_df[target_cols], feature_names
    )

    train_path = PROCESSED_DIR / "train_data.parquet"
    test_path = PROCESSED_DIR / "test_data.parquet"
    export_parquet(train_processed, train_path)
    export_parquet(test_processed, test_path)

    print("\n=== Dimensiones de los conjuntos procesados ===")
    print(f"Train: {train_processed.shape[0]:,} filas x {train_processed.shape[1]} columnas")
    print(f"Test:  {test_processed.shape[0]:,} filas x {test_processed.shape[1]} columnas")
    print(f"Variables tras el preprocesado: {feature_names}")

    print("\n=== Distribución estratificada de Bleaching_Class ===")
    print("\n-- Dataset completo --")
    print(class_distribution(df[TARGET_CLASS]).to_string())
    print("\n-- Train --")
    print(class_distribution(train_processed[TARGET_CLASS]).to_string())
    print("\n-- Test --")
    print(class_distribution(test_processed[TARGET_CLASS]).to_string())

    print("\n=== Control de fuga de datos (Data Leakage) ===")
    medians = preprocessor.named_transformers_["num"].named_steps["imputer"].statistics_
    print("Medianas de imputación calculadas solo sobre train:")
    for name, value in zip(NUMERIC_FEATURES, medians):
        print(f"  {name}: {value:.4f}")

    print(f"\nDatasets exportados en:\n  {train_path}\n  {test_path}")


if __name__ == "__main__":
    main()
