"""Laboratorio local DSS: ¿un predictor por Site_ID supera a NOAA CRW?

Usa el corpus del TFM (BCO-DMO / Sully: data/raw/global_bleaching_environmental.csv),
las mismas familias de modelos del sandbox y un protocolo local:

    - unidad espacial: Site_ID (emplazamiento, no Reef_ID);
    - test: última visita de cada sitio con historial (n >= 2);
    - train: visitas anteriores de ese sitio + sitios de una sola visita;
    - features TFM + prior local calculado solo con train (sin fugas).

NOAA se evalúa en las mismas filas de test con la regla CRW de 4 / 8 °C·semana.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    RandomForestClassifier,
    StackingClassifier,
    VotingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
)
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
RESULTS_DIR = ROOT / "results"
MODELS_DIR = ROOT / "models"

RANDOM_STATE = 42
TFM_NUMERIC = ["SSTA", "TSA", "TSA_DHW", "Depth_m", "Distance_to_Shore", "ClimSST"]
TFM_CATEGORICAL = ["Ocean_Name"]
LOCAL_FEATURES = [
    "local_site_bleach_mean",
    "local_site_severo_rate",
    "local_site_dhw_mean",
    "local_site_n_hist",
]
CLASS_ORDER = ["Bajo", "Moderado", "Severo"]


def bleaching_class(pct: float) -> int:
    """Mapeo del TFM: <10 Bajo, 10-30 Moderado, >30 Severo."""
    if pct < 10:
        return 0
    if pct <= 30:
        return 1
    return 2


def evaluate_predictions(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    return {
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted")),
        "precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        "f1_severo": float(f1_score(y_true, y_pred, labels=[2], average="macro", zero_division=0)),
        "recall_severo": float(recall_score(y_true, y_pred, labels=[2], average="macro", zero_division=0)),
        "precision_severo": float(
            precision_score(y_true, y_pred, labels=[2], average="macro", zero_division=0)
        ),
        "accuracy": float((y_true == y_pred).mean()),
    }


def load_tfm_dataset() -> pd.DataFrame:
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"No se encontró el corpus del TFM en {RAW_CSV}")

    usecols = (
        ["Site_ID", "Percent_Bleaching", "Date_Year", "Date_Month", "Date_Day"]
        + TFM_NUMERIC
        + TFM_CATEGORICAL
    )
    df = pd.read_csv(RAW_CSV, na_values=["nd", "ND"], low_memory=False, usecols=usecols)
    df = df.loc[df["Percent_Bleaching"].notna() & df["Site_ID"].notna()].copy()
    df["target_bleaching"] = df["Percent_Bleaching"].map(bleaching_class).astype(int)
    for col in ["Date_Year", "Date_Month", "Date_Day"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Date_Month"] = df["Date_Month"].fillna(6)
    df["Date_Day"] = df["Date_Day"].fillna(15)
    return df.reset_index(drop=True)


def local_known_site_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Última visita de cada Site_ID con historial = test local; el resto = train."""
    ordered = df.sort_values(
        ["Site_ID", "Date_Year", "Date_Month", "Date_Day"],
        kind="mergesort",
    ).copy()
    ordered["n_site"] = ordered.groupby("Site_ID")["Site_ID"].transform("size")
    ordered["is_last"] = ordered.groupby("Site_ID").cumcount(ascending=False).eq(0)
    test_mask = ordered["n_site"].ge(2) & ordered["is_last"]
    train = ordered.loc[~test_mask].drop(columns=["n_site", "is_last"])
    test = ordered.loc[test_mask].drop(columns=["n_site", "is_last"])
    return train.reset_index(drop=True), test.reset_index(drop=True)


def site_history_table(train: pd.DataFrame) -> pd.DataFrame:
    tmp = train.assign(is_severo=(train["target_bleaching"] == 2).astype(float))
    stats = tmp.groupby("Site_ID").agg(
        local_site_bleach_mean=("target_bleaching", "mean"),
        local_site_severo_rate=("is_severo", "mean"),
        local_site_dhw_mean=("TSA_DHW", "mean"),
        local_site_n_hist=("Site_ID", "size"),
    )
    stats["local_site_n_hist"] = stats["local_site_n_hist"].astype(float)
    return stats


def attach_local_features(df: pd.DataFrame, stats: pd.DataFrame, fallback: dict) -> pd.DataFrame:
    out = df.merge(stats, left_on="Site_ID", right_index=True, how="left")
    for col, value in fallback.items():
        out[col] = out[col].fillna(value)
    return out


def noaa_crw_predictions(dhw: pd.Series) -> np.ndarray:
    """Regla Coral Reef Watch: DHW < 4 → 0, 4–8 → 1, ≥ 8 → 2. NA = sin alerta."""
    pred = pd.cut(dhw, bins=[-np.inf, 4, 8, np.inf], labels=[0, 1, 2]).astype("float")
    return pred.fillna(0).astype(int).to_numpy()


def persistence_predictions(test: pd.DataFrame, train: pd.DataFrame) -> np.ndarray:
    """Última clase observada en el historial de train de ese Site_ID."""
    last = (
        train.sort_values(["Site_ID", "Date_Year", "Date_Month", "Date_Day"], kind="mergesort")
        .groupby("Site_ID")["target_bleaching"]
        .last()
    )
    global_mode = int(train["target_bleaching"].mode().iloc[0])
    return test["Site_ID"].map(last).fillna(global_mode).astype(int).to_numpy()


def build_preprocessor(scale: bool) -> ColumnTransformer:
    numeric_cols = TFM_NUMERIC + LOCAL_FEATURES
    num_steps: list[tuple] = [("imputer", SimpleImputer(strategy="median"))]
    if scale:
        num_steps.append(("scaler", StandardScaler()))
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline(num_steps), numeric_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                TFM_CATEGORICAL,
            ),
        ],
        remainder="drop",
    )


def wrap_model(estimator, scale: bool = True) -> Pipeline:
    return Pipeline([("prep", build_preprocessor(scale=scale)), ("clf", estimator)])


def individual_candidates() -> dict[str, Pipeline]:
    """Familias del sandbox, adaptadas a n≈30k. GPC se omite: O(n³) no escala."""
    return {
        "Lineal_LogisticReg": wrap_model(
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
        ),
        "Bayesiano_GaussianNB": wrap_model(GaussianNB()),
        "Distancia_kNN": wrap_model(KNeighborsClassifier(n_neighbors=7)),
        "Kernel_SVM_RBF": Pipeline(
            [
                ("prep", build_preprocessor(scale=True)),
                ("nystroem", Nystroem(kernel="rbf", n_components=200, random_state=RANDOM_STATE)),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE
                    ),
                ),
            ]
        ),
        "RedNeuronal_MLP": wrap_model(
            MLPClassifier(
                hidden_layer_sizes=(64, 32),
                max_iter=300,
                random_state=RANDOM_STATE,
                early_stopping=True,
            )
        ),
        "Arboles_RandomForest": wrap_model(
            RandomForestClassifier(
                n_estimators=200,
                max_depth=8,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            scale=False,
        ),
        "Arboles_ExtraTrees": wrap_model(
            ExtraTreesClassifier(
                n_estimators=200,
                max_depth=8,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            scale=False,
        ),
        "Arboles_LightGBM": wrap_model(
            LGBMClassifier(
                n_estimators=200,
                random_state=RANDOM_STATE,
                class_weight="balanced",
                verbose=-1,
            ),
            scale=False,
        ),
        "Arboles_XGBoost": wrap_model(
            XGBClassifier(
                n_estimators=200,
                max_depth=6,
                objective="multi:softprob",
                num_class=3,
                eval_metric="mlogloss",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            scale=False,
        ),
    }


def fit_predict(name: str, model: Pipeline, X_train, y_train, X_test) -> np.ndarray:
    if name == "Arboles_XGBoost":
        weights = compute_sample_weight("balanced", y_train)
        model.fit(X_train, y_train, clf__sample_weight=weights)
    else:
        model.fit(X_train, y_train)
    return model.predict(X_test)


def print_metrics(tag: str, name: str, metrics: dict) -> None:
    print(
        f"[{tag}] {name:<22} | MCC: {metrics['mcc']:.4f} | "
        f"F1: {metrics['f1_weighted']:.4f} | Rec.Severo: {metrics['recall_severo']:.4f} | "
        f"Acc.local: {metrics['accuracy']:.4f}"
    )


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("PASO 0: CORPUS TFM Y PARTICIÓN LOCAL POR Site_ID")
    print("=" * 60)

    df = load_tfm_dataset()
    train, test = local_known_site_split(df)
    stats = site_history_table(train)
    fallback = {
        "local_site_bleach_mean": float(train["target_bleaching"].mean()),
        "local_site_severo_rate": float((train["target_bleaching"] == 2).mean()),
        "local_site_dhw_mean": float(train["TSA_DHW"].mean()),
        "local_site_n_hist": 0.0,
    }
    train = attach_local_features(train, stats, fallback)
    test = attach_local_features(test, stats, fallback)

    feature_cols = TFM_NUMERIC + TFM_CATEGORICAL + LOCAL_FEATURES
    X_train, y_train = train[feature_cols], train["target_bleaching"]
    X_test, y_test = test[feature_cols], test["target_bleaching"]

    print(f"Observaciones TFM con Percent_Bleaching: {len(df):,}")
    print(f"Sitios distintos: {df['Site_ID'].nunique():,}")
    print(f"Train: {len(train):,} | Test local (última visita, sitios n>=2): {len(test):,}")
    print(f"Sitios en test: {test['Site_ID'].nunique():,}")
    print("Distribución de clases train:", y_train.value_counts(normalize=True).sort_index().round(3).to_dict())
    print("Distribución de clases test: ", y_test.value_counts(normalize=True).sort_index().round(3).to_dict())
    print(f"Predictores TFM: {TFM_NUMERIC + TFM_CATEGORICAL}")
    print(f"Predictores locales (Site_ID, solo train): {LOCAL_FEATURES}")

    print("\n" + "=" * 60)
    print("PASO 1: BASELINES LOCALES — NOAA CRW Y PERSISTENCIA DEL SITIO")
    print("=" * 60)

    noaa_preds = noaa_crw_predictions(test["TSA_DHW"])
    persist_preds = persistence_predictions(test, train)
    noaa_metrics = evaluate_predictions(y_test, noaa_preds)
    persist_metrics = evaluate_predictions(y_test, persist_preds)
    print_metrics("BASELINE", "NOAA_CRW_DHW", noaa_metrics)
    print_metrics("BASELINE", "Persistencia_SiteID", persist_metrics)

    print("\n" + "=" * 60)
    print("PASO 2: MODELOS INDIVIDUALES LOCALES (TFM + Site_ID)")
    print("=" * 60)
    print("ProcesoGaussiano omitido: no escala a ~30k observaciones (O(n³)).")
    print("Kernel SVM RBF: Nystroem (200 componentes) para que sea tractable.")

    predictions = {"NOAA_CRW_DHW": noaa_preds, "Persistencia_SiteID": persist_preds}
    trained = {}
    individual_results = []

    for name, model in individual_candidates().items():
        y_pred = fit_predict(name, model, X_train, y_train, X_test)
        metrics = evaluate_predictions(y_test, y_pred)
        beats_noaa = metrics["mcc"] > noaa_metrics["mcc"]
        trained[name] = model
        predictions[name] = y_pred
        individual_results.append(
            {
                "name": name,
                "mcc": metrics["mcc"],
                "f1_weighted": metrics["f1_weighted"],
                "recall_severo": metrics["recall_severo"],
                "f1_severo": metrics["f1_severo"],
                "accuracy": metrics["accuracy"],
                "supera_noaa": bool(beats_noaa),
            }
        )
        status = "SUPERÓ A NOAA" if beats_noaa else "RECHAZADO"
        print_metrics(status, name, metrics)

    df_ind = pd.DataFrame(individual_results).sort_values(by="mcc", ascending=False)
    best_individual_name = str(df_ind.iloc[0]["name"])
    best_individual_mcc = float(df_ind.iloc[0]["mcc"])
    best_individual_model = trained[best_individual_name]
    print(f"\n--> MEJOR MODELO INDIVIDUAL LOCAL: {best_individual_name} con MCC = {best_individual_mcc:.4f}")

    print("\n" + "=" * 60)
    print("PASO 3: MEZCLA LOCAL (STACKING / SOFT VOTING) DE QUIENES SUPERAN A NOAA")
    print("=" * 60)

    top_names = list(df_ind.loc[df_ind["supera_noaa"], "name"].head(3))
    mixture_results: list[dict] = []
    trained_mixtures: dict[str, Pipeline] = {}

    if len(top_names) >= 2:
        top_models = [(name, trained[name]) for name in top_names]
        print(f"Mezclando los Top {len(top_models)} locales: {top_names}")
        mixtures = {
            "Mezcla_Stacking": StackingClassifier(
                estimators=top_models,
                final_estimator=LogisticRegression(max_iter=1000, class_weight="balanced"),
                cv=3,
            ),
            "Mezcla_SoftVoting": VotingClassifier(estimators=top_models, voting="soft"),
        }
        for mix_name, mix_model in mixtures.items():
            mix_model.fit(X_train, y_train)
            y_pred = mix_model.predict(X_test)
            metrics = evaluate_predictions(y_test, y_pred)
            improvement = metrics["mcc"] - best_individual_mcc
            is_better = improvement > 0.01
            trained_mixtures[mix_name] = mix_model
            predictions[mix_name] = y_pred
            mixture_results.append(
                {
                    "name": mix_name,
                    "mcc": metrics["mcc"],
                    "f1_weighted": metrics["f1_weighted"],
                    "recall_severo": metrics["recall_severo"],
                    "f1_severo": metrics["f1_severo"],
                    "accuracy": metrics["accuracy"],
                    "supera_individual": bool(is_better),
                }
            )
            status = "MEJORA EL INDIVIDUAL" if is_better else "NO MEJORA LO SUFICIENTE"
            print(
                f"[{status}] {mix_name:<20} | MCC: {metrics['mcc']:.4f} | "
                f"Dif. frente a mejor ind: {improvement:+.4f} | Rec.Severo: {metrics['recall_severo']:.4f}"
            )
    else:
        print("No hay suficientes modelos individuales que superen a NOAA para mezclar.")

    print("\n" + "=" * 60)
    print("PASO 4: DECISIÓN DEL PREDICTOR LOCAL GANADOR")
    print("=" * 60)

    best_mixture_mcc = max((m["mcc"] for m in mixture_results), default=-1.0)
    if best_mixture_mcc > best_individual_mcc + 0.01:
        best_mix_name = [m["name"] for m in mixture_results if m["mcc"] == best_mixture_mcc][0]
        final_winner_name = best_mix_name
        final_winner_model = trained_mixtures[best_mix_name]
        final_winner_mcc = best_mixture_mcc
        print(f"GANADOR ABSOLUTO: MEZCLA LOCAL ('{final_winner_name}')")
        print(
            f"   Mejora real sobre el mejor individual "
            f"(+{best_mixture_mcc - best_individual_mcc:.4f} MCC)."
        )
    else:
        final_winner_name = best_individual_name
        final_winner_model = best_individual_model
        final_winner_mcc = best_individual_mcc
        print(f"GANADOR ABSOLUTO: MODELO INDIVIDUAL LOCAL ('{final_winner_name}')")
        print("   La mezcla no mejoró ≥ 0.01 MCC. Se aplica la Navaja de Ockham.")

    winner_pred = predictions[final_winner_name]
    winner_metrics = evaluate_predictions(y_test, winner_pred)
    site_hits_model = (winner_pred == y_test.to_numpy())
    site_hits_noaa = (noaa_preds == y_test.to_numpy())
    pct_sites_model = float(site_hits_model.mean())
    pct_sites_noaa = float(site_hits_noaa.mean())
    pct_sites_better = float((site_hits_model & ~site_hits_noaa).mean())
    pct_sites_worse = float((~site_hits_model & site_hits_noaa).mean())

    print("\n--> Métricas locales (última visita por Site_ID) vs NOAA:")
    print(f"    NOAA MCC:              {noaa_metrics['mcc']:.4f}")
    print(f"    Persistencia MCC:      {persist_metrics['mcc']:.4f}")
    print(f"    Ganador MCC:           {final_winner_mcc:.4f} (Ganancia: {final_winner_mcc - noaa_metrics['mcc']:+.4f})")
    print(f"    NOAA Rec.Severo:       {noaa_metrics['recall_severo']:.4f}")
    print(f"    Ganador Rec.Severo:    {winner_metrics['recall_severo']:.4f}")
    print(f"    Aciertos NOAA:         {pct_sites_noaa:.1%} de sitios")
    print(f"    Aciertos ganador:      {pct_sites_model:.1%} de sitios")
    print(f"    Sitios que gana el ML: {pct_sites_better:.1%} (NOAA fallaba)")
    print(f"    Sitios que gana NOAA:  {pct_sites_worse:.1%} (ML fallaba)")

    beats_noaa = final_winner_mcc > noaa_metrics["mcc"]
    beats_persist = final_winner_mcc > persist_metrics["mcc"]
    if beats_noaa and beats_persist:
        veredicto = (
            "Sí: el predictor local supera a NOAA CRW y a la persistencia del sitio "
            "en la última visita de arrecifes ya muestreados."
        )
    elif beats_noaa:
        veredicto = (
            "Supera a NOAA en MCC, pero no a la persistencia del Site_ID: "
            "gran parte de la ganancia es memoria local del blanqueamiento, no estrés térmico."
        )
    else:
        veredicto = (
            "No: en este protocolo local (última visita por Site_ID) el ganador no supera a NOAA CRW."
        )
    print(f"\nVEREDICTO: {veredicto}")

    site_table = pd.DataFrame(
        {
            "Site_ID": test["Site_ID"].to_numpy(),
            "y_true": y_test.to_numpy(),
            "TSA_DHW": test["TSA_DHW"].to_numpy(),
            "local_site_n_hist": test["local_site_n_hist"].to_numpy(),
            "noaa_pred": noaa_preds,
            "persist_pred": persist_preds,
            "winner_pred": winner_pred,
        }
    )
    for name, pred in predictions.items():
        if name not in {"NOAA_CRW_DHW", "Persistencia_SiteID"}:
            site_table[name] = pred

    leaderboard = pd.concat(
        [
            pd.DataFrame(
                [
                    {"name": "NOAA_CRW_DHW", **noaa_metrics, "supera_noaa": False},
                    {"name": "Persistencia_SiteID", **persist_metrics, "supera_noaa": persist_metrics["mcc"] > noaa_metrics["mcc"]},
                ]
            ),
            df_ind,
            pd.DataFrame(mixture_results),
        ],
        ignore_index=True,
    )

    bundle = {
        "model": final_winner_model,
        "winner_name": final_winner_name,
        "feature_cols": feature_cols,
        "numeric_features": TFM_NUMERIC,
        "categorical_features": TFM_CATEGORICAL,
        "local_features": LOCAL_FEATURES,
        "site_history": stats,
        "local_fallback": fallback,
        "class_order": CLASS_ORDER,
        "protocol": "leave_last_visit_out_by_Site_ID",
    }
    model_path = MODELS_DIR / "winner_dss_model.pkl"
    joblib.dump(bundle, model_path)

    summary = {
        "protocol": "leave_last_visit_out_by_Site_ID",
        "corpus": "data/raw/global_bleaching_environmental.csv",
        "n_train": int(len(train)),
        "n_test_local": int(len(test)),
        "n_sites_test": int(test["Site_ID"].nunique()),
        "winner_type": "Mixture" if "Mezcla" in final_winner_name else "Individual",
        "winner_name": final_winner_name,
        "winner_mcc": final_winner_mcc,
        "winner_f1_weighted": winner_metrics["f1_weighted"],
        "winner_recall_severo": winner_metrics["recall_severo"],
        "winner_accuracy_local": winner_metrics["accuracy"],
        "noaa_mcc": noaa_metrics["mcc"],
        "noaa_recall_severo": noaa_metrics["recall_severo"],
        "noaa_accuracy_local": noaa_metrics["accuracy"],
        "persistence_mcc": persist_metrics["mcc"],
        "mcc_gain_vs_noaa": final_winner_mcc - noaa_metrics["mcc"],
        "mcc_gain_vs_persistence": final_winner_mcc - persist_metrics["mcc"],
        "pct_sites_correct_winner": pct_sites_model,
        "pct_sites_correct_noaa": pct_sites_noaa,
        "beats_noaa": bool(beats_noaa),
        "beats_persistence": bool(beats_persist),
        "veredicto": veredicto,
        "individual_ranking": individual_results,
        "mixture_results": mixture_results,
    }
    summary_path = RESULTS_DIR / "dss_sandbox_winner_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=4, ensure_ascii=False)

    leaderboard_path = RESULTS_DIR / "dss_sandbox_leaderboard.csv"
    leaderboard.to_csv(leaderboard_path, index=False)
    site_path = RESULTS_DIR / "dss_sandbox_site_scores.csv"
    site_table.to_csv(site_path, index=False)

    print(f"\nModelo guardado en '{model_path}'.")
    print(f"Resumen: '{summary_path}'.")
    print(f"Ranking: '{leaderboard_path}'.")
    print(f"Scores por sitio: '{site_path}'.")


if __name__ == "__main__":
    main()
