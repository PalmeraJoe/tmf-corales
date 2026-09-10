"""Entrenamiento, optimización y comparación de modelos de clasificación del blanqueamiento."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
TABLES_DIR = PROJECT_ROOT / "reports" / "tables"

TARGET = "Percent_Bleaching"
TARGET_CLASS = "Bleaching_Class"
CLASS_ORDER = ["Bajo", "Moderado", "Severo"]

RANDOM_STATE = 42
CV_FOLDS = 3
FIGURE_DPI = 300

XGB_PARAM_GRID = {
    "max_depth": [3, 5, 7],
    "learning_rate": [0.05, 0.1, 0.2],
}

# Combinación seleccionada por GridSearchCV; la reutilizan los análisis posteriores.
XGB_BEST_PARAMS = {"learning_rate": 0.2, "max_depth": 7}


def load_processed_split(name: str) -> pd.DataFrame:
    """Carga un conjunto procesado en formato parquet."""
    path = PROCESSED_DIR / f"{name}_data.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró {path}. Ejecuta antes 'python src/preprocessing.py'."
        )

    try:
        return pd.read_parquet(path)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Error al leer {path.name}: {exc}") from exc


def split_features_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Separa los predictores ambientales de la clase de riesgo de blanqueamiento."""
    missing = [col for col in (TARGET, TARGET_CLASS) if col not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas objetivo en el dataset procesado: {missing}")

    features = df.drop(columns=[TARGET, TARGET_CLASS])
    # XGBoost exige etiquetas numéricas: se codifican respetando el orden de riesgo.
    target = df[TARGET_CLASS].map({name: idx for idx, name in enumerate(CLASS_ORDER)})
    return features, target.astype(int)


def build_models(sample_weights) -> dict:
    """Define los cuatro clasificadores, todos con tratamiento del desbalanceo."""
    logistic = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=RANDOM_STATE,
    )
    random_forest = RandomForestClassifier(
        class_weight="balanced",
        n_estimators=200,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    lightgbm = LGBMClassifier(
        is_unbalance=True,
        random_state=RANDOM_STATE,
        verbose=-1,
    )
    # En multiclase XGBoost no admite class_weight; el desbalanceo se compensa
    # con pesos por muestra calculados únicamente sobre train.
    xgboost = GridSearchCV(
        estimator=XGBClassifier(
            objective="multi:softprob",
            num_class=len(CLASS_ORDER),
            eval_metric="mlogloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        param_grid=XGB_PARAM_GRID,
        scoring="f1_macro",
        cv=CV_FOLDS,
        n_jobs=-1,
    )

    return {
        "Regresión Logística": (logistic, None),
        "Random Forest": (random_forest, None),
        "LightGBM": (lightgbm, None),
        "XGBoost (GridSearchCV)": (xgboost, sample_weights),
    }


def evaluate_model(model, features, target) -> dict:
    """Calcula las métricas de test exigidas en la memoria del TFM."""
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)

    return {
        "Accuracy": accuracy_score(target, predictions),
        "Precision (Macro)": precision_score(target, predictions, average="macro", zero_division=0),
        "Recall (Macro)": recall_score(target, predictions, average="macro", zero_division=0),
        "F1-Score (Macro)": f1_score(target, predictions, average="macro", zero_division=0),
        "ROC-AUC (OvR ponderado)": roc_auc_score(
            target, probabilities, multi_class="ovr", average="weighted"
        ),
    }


def slugify(name: str) -> str:
    """Convierte el nombre del modelo en un identificador apto para nombres de fichero."""
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    slug = name.lower()
    for accented, plain in replacements.items():
        slug = slug.replace(accented, plain)
    slug = "".join(char if char.isalnum() else "_" for char in slug)
    return "_".join(part for part in slug.split("_") if part)


def plot_confusion_matrix(model_name: str, target, predictions) -> Path:
    """Guarda la matriz de confusión del modelo a 300 DPI."""
    matrix = confusion_matrix(target, predictions, labels=range(len(CLASS_ORDER)))
    display = ConfusionMatrixDisplay(confusion_matrix=matrix, display_labels=CLASS_ORDER)

    fig, ax = plt.subplots(figsize=(7, 6))
    display.plot(ax=ax, cmap="Blues", values_format="d", colorbar=False)
    ax.set_title(f"Matriz de confusión — {model_name}")
    ax.set_xlabel("Nivel de riesgo predicho")
    ax.set_ylabel("Nivel de riesgo observado")
    fig.tight_layout()

    output_path = FIGURES_DIR / f"confusion_matrix_{slugify(model_name)}.png"
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)
    return output_path


def to_markdown_table(results: pd.DataFrame) -> str:
    """Construye la tabla Markdown de métricas sin dependencias externas."""
    headers = ["Modelo"] + list(results.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for model_name, row in results.iterrows():
        values = [f"{value:.4f}" for value in row]
        lines.append("| " + " | ".join([model_name] + values) + " |")
    return "\n".join(lines)


def site_redundancy_note() -> str:
    """Cuantifica la repetición de arrecifes para documentar la limitación del muestreo."""
    try:
        raw = pd.read_csv(
            RAW_CSV,
            usecols=["Site_ID", "Percent_Bleaching"],
            na_values=["nd", "ND"],
            low_memory=False,
        )
    except (OSError, ValueError):
        return (
            "El muestreo aleatorio estratificado opera a nivel de observación, por lo que un mismo "
            "arrecife puede aparecer en entrenamiento y en prueba."
        )

    raw = raw[raw["Percent_Bleaching"].notna()]
    n_rows = len(raw)
    n_sites = raw["Site_ID"].nunique()
    return (
        f"El conjunto analizado contiene {n_rows:,} observaciones procedentes de únicamente "
        f"{n_sites:,} arrecifes distintos (`Site_ID`), es decir, una media de "
        f"{n_rows / n_sites:.1f} muestreos por emplazamiento."
    )


def export_comparison_table(results: pd.DataFrame, best_params: dict, path: Path) -> None:
    """Exporta la tabla comparativa de métricas en Markdown académico."""
    best_model = results["F1-Score (Macro)"].idxmax()
    params_text = ", ".join(f"`{key}` = {value}" for key, value in best_params.items())

    content = f"""# Comparativa de modelos de clasificación

Los cuatro clasificadores se entrenaron sobre el conjunto de entrenamiento (80 %) y se evaluaron
sobre el conjunto de prueba (20 %), estratificado por nivel de riesgo de blanqueamiento.
Todos los modelos incorporan tratamiento del desbalanceo de clases, dado que la clase «Bajo»
representa cerca del 79 % de las observaciones.

## Tabla comparativa de métricas (conjunto de prueba)

{to_markdown_table(results)}

## Interpretación

El modelo con mejor F1-Score macro es **{best_model}**. Dado el fuerte desbalanceo de clases, la
métrica macro resulta más informativa que la exactitud global, ya que pondera por igual los
episodios de blanqueamiento severo y los arrecifes sin afectación aparente.

Los hiperparámetros óptimos de XGBoost, seleccionados mediante `GridSearchCV`
(validación cruzada de {CV_FOLDS} particiones sobre el conjunto de entrenamiento y `f1_macro`
como criterio), fueron: {params_text}.

Desde la perspectiva de la gestión de Áreas Marinas Protegidas (AMP), interesa especialmente la
capacidad de recuperación (*recall*) sobre la clase «Severo»: un falso negativo implica no activar
el protocolo de vigilancia en un arrecife que sí está sufriendo un evento de blanqueamiento.

## Limitaciones metodológicas

La partición se realizó mediante muestreo aleatorio estratificado sobre `{TARGET_CLASS}`, criterio
que garantiza la representación proporcional de los eventos severos en ambos conjuntos.
No obstante, conviene explicitar una limitación en la interpretación de los resultados.
{site_redundancy_note()}
Al operar la partición a nivel de observación y no de emplazamiento, un mismo arrecife puede estar
representado simultáneamente en entrenamiento y en prueba. Dado que `Depth_m`,
`Distance_to_Shore` y `ClimSST` presentan valores casi constantes dentro de cada emplazamiento,
los modelos basados en árboles pueden reconocer arrecifes ya observados durante el entrenamiento.

En consecuencia, las métricas de esta tabla deben interpretarse como una estimación del rendimiento
en arrecifes ya monitorizados, y no como la capacidad de generalización a emplazamientos nuevos.
Esta lectura es coherente con el análisis exploratorio: las anomalías puntuales correlacionan
débilmente con el blanqueamiento (r ≤ 0,134), mientras que `TSA_DHW` alcanza r = 0,228
(listwise) y 0,272 (bivariante). La validación agrupada por `Site_ID` se presenta en el
apartado 6.4.

## Figuras asociadas

Las matrices de confusión de cada modelo se encuentran en `reports/figures/` con el prefijo
`confusion_matrix_`.
"""

    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"No se pudo escribir la tabla comparativa: {exc}") from exc


def main() -> None:
    """Entrena, evalúa y compara los modelos de clasificación del riesgo de blanqueamiento."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    train_df = load_processed_split("train")
    test_df = load_processed_split("test")

    x_train, y_train = split_features_target(train_df)
    x_test, y_test = split_features_target(test_df)

    print("=== Conjuntos de modelado ===")
    print(f"Train: {x_train.shape[0]:,} filas x {x_train.shape[1]} predictores")
    print(f"Test:  {x_test.shape[0]:,} filas x {x_test.shape[1]} predictores")
    print(f"Predictores: {list(x_train.columns)}")

    sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)
    models = build_models(sample_weights)

    metrics = {}
    best_params: dict = {}

    for name, (model, weights) in models.items():
        print(f"\n=== Entrenando: {name} ===")
        if weights is not None:
            model.fit(x_train, y_train, sample_weight=weights)
        else:
            model.fit(x_train, y_train)

        if isinstance(model, GridSearchCV):
            best_params = model.best_params_
            print(f"Mejores hiperparámetros: {best_params}")
            print(f"F1-Score macro en validación cruzada: {model.best_score_:.4f}")

        metrics[name] = evaluate_model(model, x_test, y_test)

        predictions = model.predict(x_test)
        figure_path = plot_confusion_matrix(name, y_test, predictions)
        print(f"Matriz de confusión guardada en: {figure_path.name}")
        print(
            classification_report(
                y_test,
                predictions,
                target_names=CLASS_ORDER,
                zero_division=0,
            )
        )

    results = pd.DataFrame(metrics).T
    results.index.name = "Modelo"

    print("\n=== Tabla comparativa de métricas (test) ===")
    print(results.round(4).to_string())

    table_path = TABLES_DIR / "model_comparison.md"
    export_comparison_table(results, best_params, table_path)
    print(f"\nTabla comparativa exportada en: {table_path}")


if __name__ == "__main__":
    main()
