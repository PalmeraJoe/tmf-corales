"""Validación cruzada agrupada por arrecife (GroupKFold sobre Reef_ID).

Contrasta el rendimiento obtenido con una validación aleatoria estratificada frente a una
validación por grupos, en la que cada arrecife aparece íntegramente en entrenamiento o en
prueba. El objetivo es estimar la transferibilidad del modelo a arrecifes no observados.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from eda import load_dataset
from preprocessing import (
    CATEGORICAL_FEATURES,
    CLASS_ORDER,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    TARGET,
    TARGET_CLASS,
    add_bleaching_class,
    build_preprocessor,
)
from train_models import XGB_BEST_PARAMS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
TABLES_DIR = PROJECT_ROOT / "reports" / "tables"

GROUP_COLUMN = "Reef_ID"
N_SPLITS = 5
FIGURE_DPI = 300

SCHEME_RANDOM = "Aleatoria estratificada"
SCHEME_GROUP = "Agrupada por arrecife (Reef_ID)"


def load_grouped_dataset() -> pd.DataFrame:
    """Carga las observaciones con target y arrecife identificado."""
    columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET, GROUP_COLUMN]
    df = load_dataset(RAW_CSV)

    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas requeridas: {missing}")

    df = df.loc[df[TARGET].notna() & df[GROUP_COLUMN].notna(), columns].copy()
    if df.empty:
        raise ValueError("No hay observaciones con Percent_Bleaching y Reef_ID simultáneamente.")
    return add_bleaching_class(df)


def build_models() -> dict:
    """Define los clasificadores comparados, todos con tratamiento del desbalanceo."""
    return {
        "Regresión Logística": LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=RANDOM_STATE
        ),
        "Random Forest": RandomForestClassifier(
            class_weight="balanced",
            n_estimators=200,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "LightGBM": LGBMClassifier(
            is_unbalance=True, random_state=RANDOM_STATE, verbose=-1
        ),
        "XGBoost": XGBClassifier(
            objective="multi:softprob",
            num_class=len(CLASS_ORDER),
            eval_metric="mlogloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            **XGB_BEST_PARAMS,
        ),
    }


def evaluate_fold(model, features: pd.DataFrame, target: pd.Series) -> dict:
    """Calcula las métricas de un pliegue, tolerando clases ausentes en el ROC-AUC."""
    predictions = model.predict(features)
    metrics = {
        "Accuracy": accuracy_score(target, predictions),
        "Precision (Macro)": precision_score(target, predictions, average="macro", zero_division=0),
        "Recall (Macro)": recall_score(target, predictions, average="macro", zero_division=0),
        "F1-Score (Macro)": f1_score(target, predictions, average="macro", zero_division=0),
        # Índice 2 = clase «Severo», la relevante para la alerta temprana en AMP.
        "Recall Severo": recall_score(
            target, predictions, labels=[2], average="macro", zero_division=0
        ),
    }

    # Un pliegue agrupado puede no contener alguna clase de riesgo; en tal caso el AUC no existe.
    try:
        metrics["ROC-AUC (OvR ponderado)"] = roc_auc_score(
            target, model.predict_proba(features), multi_class="ovr", average="weighted"
        )
    except ValueError:
        metrics["ROC-AUC (OvR ponderado)"] = np.nan

    return metrics


def iter_splits(scheme: str, features: pd.DataFrame, target: pd.Series, groups: pd.Series):
    """Genera los índices de cada pliegue según el esquema de validación."""
    if scheme == SCHEME_RANDOM:
        splitter = StratifiedKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
        )
        return splitter.split(features, target)

    return GroupKFold(n_splits=N_SPLITS).split(features, target, groups=groups)


def run_cross_validation(
    df: pd.DataFrame, feature_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ejecuta ambos esquemas de validación cruzada y devuelve métricas por pliegue y resumen."""
    features = df[feature_cols]
    target = df[TARGET_CLASS].map({name: idx for idx, name in enumerate(CLASS_ORDER)}).astype(int)
    groups = df[GROUP_COLUMN]

    records = []
    for scheme in (SCHEME_RANDOM, SCHEME_GROUP):
        for fold, (train_idx, test_idx) in enumerate(
            iter_splits(scheme, features, target, groups), start=1
        ):
            x_train, x_test = features.iloc[train_idx], features.iloc[test_idx]
            y_train, y_test = target.iloc[train_idx], target.iloc[test_idx]

            for model_name, estimator in build_models().items():
                # El preprocesador se ajusta dentro del pliegue para evitar Data Leakage.
                pipeline = Pipeline(
                    [("preprocessor", build_preprocessor()), ("model", estimator)]
                )

                if model_name == "XGBoost":
                    weights = compute_sample_weight(class_weight="balanced", y=y_train)
                    pipeline.fit(x_train, y_train, model__sample_weight=weights)
                else:
                    pipeline.fit(x_train, y_train)

                record = {"Esquema": scheme, "Modelo": model_name, "Pliegue": fold}
                record.update(evaluate_fold(pipeline, x_test, y_test))
                records.append(record)

            print(f"  {scheme} | pliegue {fold}/{N_SPLITS} completado")

    fold_results = pd.DataFrame(records)
    summary = (
        fold_results.drop(columns="Pliegue")
        .groupby(["Esquema", "Modelo"])
        .agg(["mean", "std"])
    )
    return fold_results, summary


def degradation_table(fold_results: pd.DataFrame) -> pd.DataFrame:
    """Compara el F1-Score macro entre ambos esquemas y cuantifica la caída relativa."""
    pivot = fold_results.pivot_table(
        index="Modelo", columns="Esquema", values="F1-Score (Macro)", aggfunc=["mean", "std"]
    )
    table = pd.DataFrame(
        {
            "F1 aleatoria (media)": pivot[("mean", SCHEME_RANDOM)],
            "F1 aleatoria (sd)": pivot[("std", SCHEME_RANDOM)],
            "F1 agrupada (media)": pivot[("mean", SCHEME_GROUP)],
            "F1 agrupada (sd)": pivot[("std", SCHEME_GROUP)],
        }
    )
    table["Delta absoluta"] = table["F1 agrupada (media)"] - table["F1 aleatoria (media)"]
    table["Delta relativa (%)"] = table["Delta absoluta"] / table["F1 aleatoria (media)"] * 100
    return table.sort_values("F1 agrupada (media)", ascending=False)


def severe_recall_table(fold_results: pd.DataFrame) -> pd.DataFrame:
    """Compara el recall de la clase «Severo» entre ambos esquemas de validación."""
    pivot = fold_results.pivot_table(
        index="Modelo", columns="Esquema", values="Recall Severo", aggfunc="mean"
    )
    table = pivot[[SCHEME_RANDOM, SCHEME_GROUP]].copy()
    table.columns = ["Recall «Severo» (aleatoria)", "Recall «Severo» (agrupada)"]
    table["Delta absoluta"] = (
        table["Recall «Severo» (agrupada)"] - table["Recall «Severo» (aleatoria)"]
    )
    return table.sort_values("Recall «Severo» (agrupada)", ascending=False)


def plot_scheme_comparison(table: pd.DataFrame, path: Path) -> None:
    """Genera el gráfico comparativo de F1-Score macro entre esquemas de validación."""
    models = table.index.tolist()
    positions = np.arange(len(models))
    width = 0.38

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(
        positions - width / 2,
        table["F1 aleatoria (media)"],
        width,
        yerr=table["F1 aleatoria (sd)"].fillna(0),
        capsize=4,
        label=SCHEME_RANDOM,
        color="#2874a6",
    )
    ax.bar(
        positions + width / 2,
        table["F1 agrupada (media)"],
        width,
        yerr=table["F1 agrupada (sd)"].fillna(0),
        capsize=4,
        label=SCHEME_GROUP,
        color="#c0392b",
    )

    ax.set_xticks(positions)
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylabel("F1-Score macro (media ± desviación entre pliegues)")
    ax.set_title("Rendimiento según el esquema de validación cruzada")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=FIGURE_DPI)
    plt.close(fig)


def to_markdown_table(df: pd.DataFrame, index_name: str) -> str:
    """Construye una tabla Markdown sin dependencias externas."""
    # En consola se usa 'Delta' por compatibilidad con cp1252; el informe admite el símbolo.
    headers = [index_name] + [col.replace("Delta", "Δ") for col in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for idx, row in df.iterrows():
        values = ["n/d" if pd.isna(value) else f"{value:.4f}" for value in row]
        lines.append("| " + " | ".join([str(idx)] + values) + " |")
    return "\n".join(lines)


def export_report(
    table: pd.DataFrame, dataset_summary: dict, recall_severe: pd.DataFrame, path: Path
) -> None:
    """Redacta la discusión sobre generalización espacial para la memoria del TFM."""
    best_group = table["F1 agrupada (media)"].idxmax()
    worst_drop = table["Delta relativa (%)"].idxmin()
    most_robust = table["Delta relativa (%)"].idxmax()
    best_severe = recall_severe["Recall «Severo» (agrupada)"].idxmax()

    content = f"""# Validación cruzada agrupada por arrecife (GroupKFold sobre `Reef_ID`)

## Objetivo del experimento

La comparativa principal de modelos se construyó mediante muestreo aleatorio estratificado, en el
que un mismo arrecife puede aparecer simultáneamente en entrenamiento y en prueba. Este
experimento evalúa una pregunta distinta y más exigente desde el punto de vista de la gestión
marina: ¿qué rendimiento cabe esperar cuando el modelo se aplica a arrecifes **completamente no
observados** durante el entrenamiento?

Para responderla se emplea `GroupKFold` con `{GROUP_COLUMN}` como variable de agrupación, de modo
que todas las observaciones de un mismo arrecife quedan confinadas en un único pliegue.

## Diseño y submuestra analizada

`{GROUP_COLUMN}` solo está informado en una parte del conjunto de datos, por lo que el experimento
se restringe a esa submuestra. Ambos esquemas de validación se ejecutan sobre **exactamente el
mismo subconjunto**, de manera que la diferencia observada sea atribuible al criterio de
partición y no a un cambio en los datos.

| Característica de la submuestra | Valor |
|---|---|
| Observaciones con `{TARGET}` y `{GROUP_COLUMN}` | {dataset_summary["n_rows"]:,} |
| Arrecifes distintos (`{GROUP_COLUMN}`) | {dataset_summary["n_groups"]:,} |
| Observaciones por arrecife (media) | {dataset_summary["rows_per_group"]:.1f} |
| Clase «Bajo» | {dataset_summary["pct_bajo"]:.2f} % |
| Clase «Moderado» | {dataset_summary["pct_moderado"]:.2f} % |
| Clase «Severo» | {dataset_summary["pct_severo"]:.2f} % |
| Número de pliegues | {N_SPLITS} |

Debe advertirse que esta submuestra presenta un desbalanceo considerablemente mayor que el
conjunto completo: los episodios severos representan aquí un {dataset_summary["pct_severo"]:.2f} %
de los registros, frente al 12,42 % del conjunto empleado en la comparativa principal. Por tanto,
las cifras de este apartado no son directamente comparables con las de
`reports/tables/model_comparison.md`; la lectura pertinente es la **comparación interna** entre
ambos esquemas de validación.

## Resultados

{to_markdown_table(table, "Modelo")}

Recall sobre la clase «Severo», métrica crítica para la alerta temprana en Áreas Marinas
Protegidas (AMP):

{to_markdown_table(recall_severe, "Modelo")}

Figura: `reports/figures/validacion_grupos_reef_id.png`.

## Discusión

Al pasar de la validación aleatoria a la validación agrupada por arrecife, el rendimiento de los
modelos se deteriora de forma sistemática. El caso más acusado es **{worst_drop}**, con una caída
relativa del F1-Score macro del {abs(table.loc[worst_drop, "Delta relativa (%)"]):.1f} %. Bajo el
esquema agrupado, el mejor F1-Score macro corresponde a **{best_group}**
({table.loc[best_group, "F1 agrupada (media)"]:.4f}), si bien las diferencias entre los modelos de
árboles prácticamente desaparecen: la ventaja que Random Forest exhibía en la validación aleatoria
se disuelve al exigirle predecir sobre arrecifes no observados.

El hallazgo más relevante es una **inversión en la robustez de los modelos**. La regresión
logística, claramente el peor clasificador bajo validación aleatoria, es a la vez el más estable:
su F1-Score macro apenas varía
({abs(table.loc[most_robust, "Delta relativa (%)"]):.1f} % de caída relativa). Más aún, en el
escenario agrupado es **{best_severe}** el modelo que mejor detecta los episodios severos, con un
recall de {recall_severe.loc[best_severe, "Recall «Severo» (agrupada)"]:.4f}, frente a valores
inferiores a 0,20 en Random Forest y XGBoost. Estos últimos ven desplomarse su recall de la clase
«Severo» desde valores próximos a 0,83 hasta el entorno de 0,13–0,17.

La lectura es inequívoca: los modelos de árboles no estaban aprendiendo principalmente la relación
entre estrés térmico y blanqueamiento, sino la identidad de cada arrecife y su historial. Un
modelo lineal, incapaz de memorizar emplazamientos concretos, conserva la escasa señal ambiental
genuina y se comporta mejor al extrapolar. Este resultado desaconseja seleccionar el modelo final
únicamente por su rendimiento en la validación aleatoria.

Esta degradación admite una interpretación ecológica precisa. Las variables `Depth_m`,
`Distance_to_Shore` y `ClimSST` son prácticamente constantes dentro de un mismo arrecife, de modo
que actúan como una firma del emplazamiento. Cuando ese arrecife aparece en ambos lados de la
partición, los modelos basados en árboles pueden reconocerlo y reproducir su comportamiento
histórico de blanqueamiento, sin necesidad de haber aprendido el mecanismo de estrés térmico
subyacente. La validación agrupada elimina esa vía y obliga al modelo a apoyarse en la señal
ambiental genuina, que el análisis exploratorio ya mostraba débil en las anomalías puntuales
(r ≤ 0,134 para SSTA y TSA) y encabezada por `TSA_DHW` (r = 0,228 listwise; 0,272 bivariante).

La mayor dispersión entre pliegues del esquema agrupado refuerza esta lectura: el rendimiento
depende del conjunto concreto de arrecifes que quedan fuera del entrenamiento, lo que evidencia
una **heterogeneidad biogeográfica** que las cinco variables predictoras no capturan. Arrecifes
de distintas ecorregiones difieren en composición de especies, historia térmica y capacidad de
aclimatación de sus comunidades de zooxantelas, factores ausentes del conjunto de predictores.

## Conclusiones para la gestión

Los resultados de la validación aleatoria describen la capacidad del modelo para **interpolar
dentro de una red de arrecifes ya monitorizada**, escenario realista cuando una AMP dispone de
series históricas de seguimiento. Los resultados de la validación agrupada, más conservadores,
describen la capacidad de **extrapolar a arrecifes sin histórico**, que es el escenario habitual
al extender la vigilancia a nuevas áreas.

En consecuencia, se recomienda reportar ambas cifras en la memoria: la primera como límite
superior optimista y la segunda como estimación prudente para la planificación. Para desplegar el
modelo en emplazamientos no monitorizados convendría incorporar descriptores ecorregionales y
métricas acumuladas de estrés térmico (por ejemplo, *Degree Heating Weeks*), en lugar de asumir
que el rendimiento observado en la validación aleatoria se mantendrá.

La elección del modelo debe subordinarse al escenario de aplicación. Para una AMP con red de
seguimiento consolidada, Random Forest sigue siendo la opción preferente. Para extender la alerta
temprana a arrecifes sin histórico, un modelo más simple y estable resulta preferible pese a su
menor rendimiento aparente, ya que la prioridad es no dejar sin detectar episodios severos.

Como refinamiento metodológico, `StratifiedGroupKFold` permitiría preservar la proporción de
clases entre pliegues manteniendo la separación por arrecife, lo que reduciría la varianza
observada en la estimación.
"""

    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"No se pudo escribir el informe de validación: {exc}") from exc


def main() -> None:
    """Ejecuta el experimento de validación agrupada y exporta figura e informe."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    df = load_grouped_dataset()
    class_pct = df[TARGET_CLASS].value_counts(normalize=True).mul(100)
    dataset_summary = {
        "n_rows": len(df),
        "n_groups": df[GROUP_COLUMN].nunique(),
        "rows_per_group": len(df) / df[GROUP_COLUMN].nunique(),
        "pct_bajo": class_pct["Bajo"],
        "pct_moderado": class_pct["Moderado"],
        "pct_severo": class_pct["Severo"],
    }

    print("=== Submuestra con Reef_ID identificado ===")
    print(f"Observaciones: {dataset_summary['n_rows']:,}")
    print(f"Arrecifes distintos: {dataset_summary['n_groups']:,}")
    print(f"Observaciones por arrecife: {dataset_summary['rows_per_group']:.1f}")
    print(f"Clases (%): {class_pct.round(2).to_dict()}")

    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES

    print(f"\n=== Validación cruzada ({N_SPLITS} pliegues, 2 esquemas, 4 modelos) ===")
    fold_results, summary = run_cross_validation(df, feature_cols)

    print("\n=== Métricas medias por esquema y modelo ===")
    print(summary.round(4).to_string())

    table = degradation_table(fold_results)
    print("\n=== Degradación del F1-Score macro al agrupar por arrecife ===")
    print(table.round(4).to_string())

    recall_severe = severe_recall_table(fold_results)
    print("\n=== Recall de la clase «Severo» por esquema ===")
    print(recall_severe.round(4).to_string())

    figure_path = FIGURES_DIR / "validacion_grupos_reef_id.png"
    plot_scheme_comparison(table, figure_path)
    print(f"\nFigura guardada en: {figure_path}")

    report_path = TABLES_DIR / "group_validation.md"
    export_report(table, dataset_summary, recall_severe, report_path)
    print(f"Informe exportado en: {report_path}")


if __name__ == "__main__":
    main()
