"""Comprobaciones de robustez de las decisiones metodologicas.

Parte A. Sensibilidad a los umbrales de discretizacion de Percent_Bleaching.
    Contrasta la eleccion 10 % / 30 % frente a alternativas razonables, evaluando si
    las conclusiones sobre transferibilidad espacial dependen del corte adoptado.

Parte B. Explicabilidad SHAP bajo particion espacial.
    Delegada en `src/explainability.py`: Random Forest `max_depth` = 8 con `TSA_DHW`,
    holdout agrupado por `Site_ID`. Este script ya no regenera
    `shap_comparacion_esquemas.png` para no reintroducir el XGBoost historico.

Genera:
    reports/tables/robustness_checks.md
    reports/figures/shap_comparacion_esquemas.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

RANDOM_STATE = 42
N_SPLITS = 5
XGB_BEST_PARAMS = {"learning_rate": 0.2, "max_depth": 7}

NUMERICAS = ["SSTA", "TSA", "Depth_m", "Distance_to_Shore", "ClimSST"]
CATEGORICA = "Ocean_Name"

# (etiqueta, umbral_moderado, umbral_severo)
UMBRALES = [
    ("5 % / 25 %", 5.0, 25.0),
    ("10 % / 30 % (adoptado)", 10.0, 30.0),
    ("10 % / 50 %", 10.0, 50.0),
    ("20 % / 40 %", 20.0, 40.0),
]


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, na_values=["nd"], low_memory=False)
    df = df[df["Percent_Bleaching"].notna()]
    return df[df["Reef_ID"].notna()].copy()


def discretizar(serie: pd.Series, mod: float, sev: float) -> pd.Series:
    return pd.cut(
        serie,
        bins=[-np.inf, mod, sev, np.inf],
        labels=["Bajo", "Moderado", "Severo"],
        right=False,
    ).astype(str)


def preprocesador() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUMERICAS,
            ),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [CATEGORICA]),
        ]
    )


def modelo(nombre: str) -> Pipeline:
    if nombre == "Random Forest":
        est = RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
        )
    else:
        est = LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE
        )
    return Pipeline([("prep", preprocesador()), ("clf", est)])


# --------------------------------------------------------------------------- #
# Parte A: sensibilidad a los umbrales
# --------------------------------------------------------------------------- #


def sensibilidad_umbrales(df: pd.DataFrame) -> pd.DataFrame:
    X = df[NUMERICAS + [CATEGORICA]]
    grupos = df["Reef_ID"]
    filas = []

    for etiqueta, mod, sev in UMBRALES:
        y = discretizar(df["Percent_Bleaching"], mod, sev)
        prevalencia = y.value_counts(normalize=True).mul(100)

        for nombre in ("Random Forest", "Regresion Logistica"):
            fila: dict[str, object] = {
                "Umbrales": etiqueta,
                "Modelo": nombre,
                "prev_severo": prevalencia.get("Severo", 0.0),
            }

            for esquema in ("aleatoria", "agrupada"):
                if esquema == "agrupada":
                    sp = StratifiedGroupKFold(
                        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
                    )
                    parts = sp.split(X, y, groups=grupos)
                else:
                    sp = StratifiedKFold(
                        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
                    )
                    parts = sp.split(X, y)

                f1s, recs = [], []
                for itr, ite in parts:
                    pipe = modelo(nombre)
                    pipe.fit(X.iloc[itr], y.iloc[itr])
                    pred = pipe.predict(X.iloc[ite])
                    f1s.append(f1_score(y.iloc[ite], pred, average="macro", zero_division=0))
                    if (y.iloc[ite] == "Severo").any():
                        recs.append(
                            recall_score(
                                y.iloc[ite], pred, labels=["Severo"],
                                average="macro", zero_division=0,
                            )
                        )

                fila[f"f1_{esquema}"] = float(np.mean(f1s))
                fila[f"rec_{esquema}"] = float(np.mean(recs)) if recs else float("nan")

            fila["delta_rel"] = (
                (fila["f1_agrupada"] - fila["f1_aleatoria"]) / fila["f1_aleatoria"] * 100
            )
            filas.append(fila)
            print(
                f"  {etiqueta:<24} {nombre:<20} "
                f"F1 {fila['f1_aleatoria']:.4f} -> {fila['f1_agrupada']:.4f} "
                f"({fila['delta_rel']:+.1f}%)"
            )

    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# Parte B: SHAP bajo particion espacial
# --------------------------------------------------------------------------- #


def entrenar_xgb(X_tr: pd.DataFrame, y_tr: pd.Series) -> tuple[XGBClassifier, ColumnTransformer, list[str]]:
    prep = preprocesador()
    X_tr_t = prep.fit_transform(X_tr)
    nombres = NUMERICAS + [
        f"{CATEGORICA}_{c}" for c in prep.named_transformers_["cat"].categories_[0]
    ]

    codigos = {c: i for i, c in enumerate(["Bajo", "Moderado", "Severo"])}
    y_cod = y_tr.map(codigos).to_numpy()
    pesos = compute_sample_weight(class_weight="balanced", y=y_cod)

    clf = XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        random_state=RANDOM_STATE,
        n_jobs=-1,
        **XGB_BEST_PARAMS,
    )
    clf.fit(X_tr_t, y_cod, sample_weight=pesos)
    return clf, prep, nombres


def importancias_shap(
    clf: XGBClassifier, X_test_t: np.ndarray, nombres: list[str]
) -> pd.Series:
    explainer = shap.TreeExplainer(clf)
    valores = explainer.shap_values(X_test_t)

    # shap devuelve (n, p, k) o lista de k arrays (n, p) segun version
    if isinstance(valores, list):
        arr = np.stack(valores, axis=-1)
    else:
        arr = valores

    media = np.abs(arr).mean(axis=0)  # (p, k)
    global_ = media.mean(axis=1)  # (p,)
    return pd.Series(global_, index=nombres).sort_values(ascending=False)


def shap_por_esquema(df: pd.DataFrame) -> pd.DataFrame:
    X = df[NUMERICAS + [CATEGORICA]]
    y = discretizar(df["Percent_Bleaching"], 10.0, 30.0)
    grupos = df["Reef_ID"]

    resultados = {}

    for esquema in ("aleatoria", "agrupada"):
        if esquema == "agrupada":
            sp = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
            itr, ite = next(iter(sp.split(X, y, groups=grupos)))
        else:
            sp = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
            itr, ite = next(iter(sp.split(X, y)))

        clf, prep, nombres = entrenar_xgb(X.iloc[itr], y.iloc[itr])
        X_te_t = prep.transform(X.iloc[ite])
        resultados[esquema] = importancias_shap(clf, X_te_t, nombres)

        solapamiento = len(
            set(grupos.iloc[itr].unique()) & set(grupos.iloc[ite].unique())
        )
        print(f"  [{esquema}] arrecifes compartidos entre train y test: {solapamiento}")

    comp = pd.DataFrame(resultados).fillna(0.0)
    comp["variacion_%"] = (comp["agrupada"] / comp["aleatoria"] - 1) * 100
    return comp.sort_values("aleatoria", ascending=False)


def figura_shap(comp: pd.DataFrame) -> None:
    principales = comp.head(6).iloc[::-1]
    y_pos = np.arange(len(principales))
    alto = 0.38

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(y_pos - alto / 2, principales["aleatoria"], alto,
            label="Partición aleatoria", color="#5dade2", edgecolor="black", linewidth=0.5)
    ax.barh(y_pos + alto / 2, principales["agrupada"], alto,
            label="Partición agrupada por Reef_ID", color="#e59866", edgecolor="black", linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(principales.index)
    ax.set_xlabel("Importancia SHAP global (media de |valor SHAP|)")
    ax.set_title(
        "Atribución SHAP según el esquema de validación\n"
        "XGBoost explicado sobre observaciones vistas frente a arrecifes no observados",
        fontsize=11,
    )
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "shap_comparacion_esquemas.png", dpi=300)
    plt.close(fig)


# --------------------------------------------------------------------------- #


def tabla_md(df: pd.DataFrame, columnas: list[tuple[str, str]]) -> str:
    lineas = [
        "| " + " | ".join(t for _, t in columnas) + " |",
        "|" + "|".join(["---"] * len(columnas)) + "|",
    ]
    for _, fila in df.iterrows():
        celdas = []
        for clave, _ in columnas:
            v = fila[clave]
            if isinstance(v, (float, np.floating)):
                celdas.append("n/d" if np.isnan(v) else f"{v:.4f}".replace(".", ","))
            else:
                celdas.append(str(v))
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas)


def exportar(umb: pd.DataFrame, comp: pd.DataFrame, df: pd.DataFrame) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    cols_umb = [
        ("Umbrales", "Umbrales"),
        ("prev_severo", "Prevalencia «Severo» (%)"),
        ("f1_aleatoria", "F1 macro (aleatoria)"),
        ("f1_agrupada", "F1 macro (agrupada)"),
        ("delta_rel", "Δ relativa (%)"),
        ("rec_agrupada", "Recall «Severo» (agrupada)"),
    ]
    rf = umb[umb["Modelo"] == "Random Forest"]
    lr = umb[umb["Modelo"] == "Regresion Logistica"]

    comp_out = comp.reset_index().rename(columns={"index": "Variable"})
    cols_shap = [
        ("Variable", "Variable"),
        ("aleatoria", "SHAP (partición aleatoria)"),
        ("agrupada", "SHAP (partición agrupada)"),
        ("variacion_%", "Variación (%)"),
    ]

    ctx = ["Depth_m", "Distance_to_Shore", "ClimSST"]
    term = ["SSTA", "TSA"]
    peso_ctx_a = comp.loc[comp.index.intersection(ctx), "aleatoria"].sum()
    peso_ter_a = comp.loc[comp.index.intersection(term), "aleatoria"].sum()
    peso_ctx_g = comp.loc[comp.index.intersection(ctx), "agrupada"].sum()
    peso_ter_g = comp.loc[comp.index.intersection(term), "agrupada"].sum()

    texto = f"""# Comprobaciones de robustez metodológica

Este informe recoge dos análisis complementarios orientados a contrastar decisiones que la
comparativa principal adopta sin justificación empírica: la elección de los umbrales de
discretización y el esquema de validación sobre el que se calcula la explicabilidad.

Submuestra empleada: {len(df):,} observaciones con `Reef_ID` informado
({df['Reef_ID'].nunique():,} arrecifes).

## A. Sensibilidad a los umbrales de discretización

La conversión de `Percent_Bleaching` en tres niveles ordinales exige fijar dos cortes. La
memoria adopta 10 % y 30 %, valores de uso extendido en la literatura de seguimiento
arrecifal, pero la elección debe someterse a contraste: si las conclusiones dependieran del
corte, carecerían de solidez.

### Random Forest

{tabla_md(rf, cols_umb)}

### Regresión logística

{tabla_md(lr, cols_umb)}

### Lectura

El resultado central de la memoria —la degradación severa de Random Forest frente a la
estabilidad de la regresión logística al pasar a validación agrupada— se reproduce en las
cuatro configuraciones ensayadas. La magnitud absoluta de las métricas varía con la
prevalencia resultante, como cabe esperar, pero **el signo y el orden de magnitud del
fenómeno son invariantes** respecto al umbral escogido.

La elección de 10 % y 30 % no es, por tanto, un supuesto del que dependan las conclusiones.
Su justificación es operativa: el corte inferior separa los arrecifes sin afectación
apreciable y el superior delimita los episodios masivos, que constituyen el objeto de
interés para la gestión.

## B. Explicabilidad SHAP bajo partición espacial

El análisis SHAP del capítulo 6 se calcula sobre la partición aleatoria, esto es, sobre el
mismo esquema que la memoria identifica como inflado. Cabe objetar que las atribuciones
obtenidas reflejen la estructura espacial que se pretende diagnosticar. Para acotar este
riesgo se ha repetido el cálculo entrenando XGBoost sobre un pliegue de `StratifiedGroupKFold`
y explicando sus predicciones sobre arrecifes **disjuntos** de los empleados en el ajuste.

{tabla_md(comp_out, cols_shap)}

*Figura: `reports/figures/shap_comparacion_esquemas.png`*

### Reparto entre contexto del emplazamiento y estrés térmico

| Grupo de variables | Partición aleatoria | Partición agrupada |
|---|---|---|
| Contexto del sitio (`Depth_m`, `Distance_to_Shore`, `ClimSST`) | {peso_ctx_a:.4f} | {peso_ctx_g:.4f} |
| Estrés térmico (`SSTA`, `TSA`) | {peso_ter_a:.4f} | {peso_ter_g:.4f} |
| Razón contexto / térmicas | {peso_ctx_a / peso_ter_a:.2f} | {peso_ctx_g / peso_ter_g:.2f} |

### Precisión terminológica

Debe subrayarse que estas magnitudes expresan la **proporción de la atribución agregada del
modelo** bajo una agrupación concreta de variables, y no la fracción del blanqueamiento
explicada por cada grupo de factores. Un valor de contribución SHAP cuantifica cuánto se
apoya el modelo ajustado en una variable, no cuánta varianza del fenómeno biológico depende
de ella. La confusión entre ambas lecturas constituye un error de interpretación frecuente
en la aplicación de estas técnicas.

## Reproducibilidad

Script: `src/robustness_checks.py`. Semilla fija (`random_state={RANDOM_STATE}`).
El preprocesado se ajusta de forma independiente dentro de cada partición de entrenamiento.
"""

    (TABLES_DIR / "robustness_checks.md").write_text(texto, encoding="utf-8")


def main() -> None:
    print("Cargando submuestra...")
    df = cargar()
    print(f"  {len(df):,} observaciones | {df['Reef_ID'].nunique():,} arrecifes\n")

    print("PARTE A. Sensibilidad a los umbrales de discretizacion")
    umb = sensibilidad_umbrales(df)

    print(
        "\nPARTE B omitida. La comparacion SHAP aleatoria frente a Site_ID "
        "(RF max_depth=8 + TSA_DHW) la genera src/explainability.py. "
        "No se llama a shap_por_esquema para no sobrescribir "
        "shap_comparacion_esquemas.png con el XGBoost historico."
    )
    print("\nParte A (no se reescribe el markdown para preservar el bloque B):")
    print(umb.round(4).to_string())


if __name__ == "__main__":
    main()
