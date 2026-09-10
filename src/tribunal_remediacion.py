"""Experimentos que cierran las objeciones metodologicas del tribunal.

1. Sesgo de la submuestra Reef_ID (Reef_Check frente al resto de fuentes).
2. Paradoja profundidad-blanqueamiento (confusor de fuente).
3. Autocorrelacion espacial (I de Moran sobre centroides de sitio).
4. Baseline operativo NOAA CRW (umbrales DHW 4 y 8).
5. DHW en el modelo principal, con validacion agrupada por Site_ID en el conjunto completo.
6. Bloqueo geografico: leave-one-ocean-out y agrupacion por ecorregion.
7. Random Forest con profundidad acotada frente a profundidad libre.
8. Validacion temporal y PR-AUC de la clase Severo.

Genera:
    reports/tables/tribunal_remediacion.md
    reports/figures/tribunal_fuentes_severidad.png
    reports/figures/tribunal_profundidad_fuente.png
    reports/figures/tribunal_baseline_crw.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, StratifiedKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

RANDOM_STATE = 42
N_SPLITS = 5
FIGURE_DPI = 300
CLASS_ORDER = ["Bajo", "Moderado", "Severo"]

BASE_NUM = ["SSTA", "TSA", "Depth_m", "Distance_to_Shore", "ClimSST"]
DHW_NUM = BASE_NUM + ["TSA_DHW"]
TERMICA_DHW = ["SSTA", "TSA", "TSA_DHW"]


def clasificar(pct: pd.Series) -> pd.Series:
    return pd.Categorical(
        np.select([pct < 10, pct <= 30], ["Bajo", "Moderado"], default="Severo"),
        categories=CLASS_ORDER,
        ordered=True,
    )


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, na_values=["nd", "ND"], low_memory=False)
    df = df.loc[df["Percent_Bleaching"].notna()].copy()
    df["Bleaching_Class"] = clasificar(df["Percent_Bleaching"])
    df["es_reef_check"] = df["Data_Source"] == "Reef_Check"
    df["tiene_reef_id"] = df["Reef_ID"].notna()
    return df


def preprocesador(numericas: list[str], categoricas: list[str] | None) -> ColumnTransformer:
    transformadores = [
        (
            "num",
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]
            ),
            numericas,
        )
    ]
    if categoricas:
        transformadores.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categoricas,
            )
        )
    return ColumnTransformer(transformadores, remainder="drop")


def construir_modelo(nombre: str, numericas: list[str], categoricas: list[str] | None) -> Pipeline:
    if nombre == "logistica":
        clf = LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=RANDOM_STATE,
        )
    elif nombre == "rf_libre":
        clf = RandomForestClassifier(
            n_estimators=100,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    elif nombre == "rf_prof8":
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    elif nombre == "rf_prof16":
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=16,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Modelo desconocido: {nombre}")

    return Pipeline(
        [
            ("prep", preprocesador(numericas, categoricas)),
            ("clf", clf),
        ]
    )


def metricas(y_true: pd.Series, y_pred: np.ndarray, y_score: np.ndarray | None = None) -> dict[str, float]:
    out = {
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_severo": float(
            recall_score(y_true, y_pred, labels=["Severo"], average="macro", zero_division=0)
        ),
        "precision_severo": float(
            precision_score(y_true, y_pred, labels=["Severo"], average="macro", zero_division=0)
        ),
    }
    if y_score is not None:
        y_bin = (np.asarray(y_true) == "Severo").astype(int)
        if y_bin.sum() > 0 and y_bin.min() == 0:
            out["pr_auc_severo"] = float(average_precision_score(y_bin, y_score))
        else:
            out["pr_auc_severo"] = float("nan")
    else:
        out["pr_auc_severo"] = float("nan")
    return out


def crw_tres_clases(dhw: pd.Series) -> np.ndarray:
    return np.select(
        [dhw >= 8, dhw >= 4],
        ["Severo", "Moderado"],
        default="Bajo",
    )


def evaluar_regla(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return metricas(y_true, y_pred, y_score=None)


def score_severo(pipe: Pipeline, X: pd.DataFrame) -> np.ndarray:
    proba = pipe.predict_proba(X)
    clases = list(pipe.named_steps["clf"].classes_)
    if "Severo" not in clases:
        return np.zeros(len(X))
    return proba[:, clases.index("Severo")]


def evaluar_cv(
    df: pd.DataFrame,
    numericas: list[str],
    categoricas: list[str] | None,
    modelo: str,
    grupos: pd.Series | None,
    esquema: str,
) -> dict[str, float]:
    X = df[numericas + (categoricas or [])]
    y = df["Bleaching_Class"].astype(str)
    registros: list[dict[str, float]] = []

    if esquema == "aleatoria":
        splitter = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
        particiones = splitter.split(X, y)
    elif esquema == "grupos":
        if grupos is None:
            raise ValueError("esquema='grupos' exige una serie de grupos.")
        splitter = StratifiedGroupKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
        )
        particiones = splitter.split(X, y, groups=grupos)
    elif esquema == "loo_grupo":
        if grupos is None:
            raise ValueError("esquema='loo_grupo' exige una serie de grupos.")
        splitter = GroupKFold(n_splits=int(grupos.nunique()))
        particiones = splitter.split(X, y, groups=grupos)
    else:
        raise ValueError(f"Esquema desconocido: {esquema}")

    for idx_train, idx_test in particiones:
        pipe = construir_modelo(modelo, numericas, categoricas)
        pipe.fit(X.iloc[idx_train], y.iloc[idx_train])
        pred = pipe.predict(X.iloc[idx_test])
        score = score_severo(pipe, X.iloc[idx_test])
        registros.append(metricas(y.iloc[idx_test], pred, score))

    frame = pd.DataFrame(registros)
    resumen = {}
    for col in frame.columns:
        resumen[col] = float(frame[col].mean())
        resumen[f"{col}_sd"] = float(frame[col].std(ddof=1)) if len(frame) > 1 else 0.0
    resumen["n_pliegues"] = float(len(frame))
    return resumen


def evaluar_holdout(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numericas: list[str],
    categoricas: list[str] | None,
    modelo: str,
) -> dict[str, float]:
    cols = numericas + (categoricas or [])
    pipe = construir_modelo(modelo, numericas, categoricas)
    pipe.fit(train[cols], train["Bleaching_Class"].astype(str))
    pred = pipe.predict(test[cols])
    score = score_severo(pipe, test[cols])
    return metricas(test["Bleaching_Class"].astype(str), pred, score)


def moran_knn(valores: np.ndarray, coords: np.ndarray, k: int = 8, n_perm: int = 99) -> dict[str, float]:
    n = len(valores)
    k_eff = min(k, n - 1)
    nn = NearestNeighbors(n_neighbors=k_eff, algorithm="ball_tree")
    nn.fit(coords)
    ind = nn.kneighbors(return_distance=False)

    pesos = np.zeros((n, n), dtype=np.float64)
    rows = np.repeat(np.arange(n), k_eff)
    pesos[rows, ind.ravel()] = 1.0
    pesos = np.maximum(pesos, pesos.T)
    np.fill_diagonal(pesos, 0.0)
    w_sum = pesos.sum()
    z = valores - valores.mean()
    numerador = float(z @ pesos @ z)
    denominador = float(z @ z)
    i_obs = (n / w_sum) * (numerador / denominador)

    rng = np.random.default_rng(RANDOM_STATE)
    mayores = 0
    for _ in range(n_perm):
        z_p = rng.permutation(valores)
        z_p = z_p - z_p.mean()
        i_p = (n / w_sum) * float(z_p @ pesos @ z_p) / float(z_p @ z_p)
        if i_p >= i_obs:
            mayores += 1
    p_val = (mayores + 1) / (n_perm + 1)
    esperanza = -1.0 / (n - 1)
    return {"I": i_obs, "E_I": esperanza, "p_perm": p_val, "k": float(k_eff), "n": float(n)}


def correlacion_parcial_fuente(df: pd.DataFrame) -> float:
    usable = df.dropna(subset=["Depth_m", "Percent_Bleaching", "Data_Source"]).copy()
    dummies = pd.get_dummies(usable["Data_Source"], drop_first=True)
    X = dummies.to_numpy(dtype=float)
    y_depth = usable["Depth_m"].to_numpy(dtype=float)
    y_bleach = usable["Percent_Bleaching"].to_numpy(dtype=float)
    residual_depth = y_depth - LinearRegression().fit(X, y_depth).predict(X)
    residual_bleach = y_bleach - LinearRegression().fit(X, y_bleach).predict(X)
    return float(np.corrcoef(residual_depth, residual_bleach)[0, 1])


def fmt(valor: float, dec: int = 4) -> str:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "n/d"
    texto = f"{valor:.{dec}f}"
    return texto.replace(".", ",")


def tabla_md(filas: list[list[str]], encabezados: list[str]) -> str:
    lineas = [
        "| " + " | ".join(encabezados) + " |",
        "|" + "|".join(["---"] * len(encabezados)) + "|",
    ]
    for fila in filas:
        lineas.append("| " + " | ".join(fila) + " |")
    return "\n".join(lineas)


def figura_fuentes(df: pd.DataFrame) -> None:
    resumen = (
        df.groupby("Data_Source", observed=False)
        .agg(n=("Percent_Bleaching", "size"), sev=("Percent_Bleaching", lambda s: (s > 30).mean()))
        .sort_values("n", ascending=False)
    )
    resumen = resumen[resumen["n"] >= 50]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(resumen.index.astype(str), resumen["sev"] * 100, color="#1f6f8b", edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Prevalencia de blanqueamiento severo (%)")
    ax.set_xlabel("Fuente de datos")
    ax.set_title("Prevalencia de episodios severos por programa de muestreo")
    ax.tick_params(axis="x", rotation=30)
    for i, (n_obs, sev) in enumerate(zip(resumen["n"], resumen["sev"])):
        ax.text(i, sev * 100 + 1.2, f"n={n_obs}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "tribunal_fuentes_severidad.png", dpi=FIGURE_DPI)
    plt.close(fig)


def figura_profundidad(df: pd.DataFrame) -> None:
    tmp = df.dropna(subset=["Depth_m"]).copy()
    tmp["bin"] = pd.cut(tmp["Depth_m"], bins=[-0.1, 3, 6, 10, 20, 1000], labels=["0-3 m", "3-6 m", "6-10 m", "10-20 m", ">20 m"])
    tmp["grupo"] = np.where(tmp["es_reef_check"], "Reef_Check", "Resto de fuentes")
    pivot = tmp.groupby(["bin", "grupo"], observed=False)["Percent_Bleaching"].mean().unstack("grupo")
    fig, ax = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="bar", ax=ax, color=["#1f6f8b", "#c0392b"], edgecolor="black", linewidth=0.4)
    ax.set_ylabel("Porcentaje medio de blanqueamiento (%)")
    ax.set_xlabel("Profundidad")
    ax.set_title("Relación profundidad–blanqueamiento estratificada por fuente")
    ax.legend(title="")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "tribunal_profundidad_fuente.png", dpi=FIGURE_DPI)
    plt.close(fig)


def figura_baseline(filas: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    y = np.arange(len(filas))
    ax.barh(y, filas["recall_severo"] * 100, color="#1f6f8b", edgecolor="black", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(filas["metodo"])
    ax.set_xlabel("Recall de la clase Severo (%)")
    ax.set_title("Detección de episodios severos: reglas CRW frente a modelos, CV por Site_ID")
    ax.set_xlim(0, 100)
    for i, valor in enumerate(filas["recall_severo"]):
        ax.text(valor * 100 + 1, i, f"{valor:.2f}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "tribunal_baseline_crw.png", dpi=FIGURE_DPI)
    plt.close(fig)


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = cargar()
    print(f"Observaciones con respuesta: {len(df)}")

    # ------------------------------------------------------------------
    # 1. Sesgo Reef_ID / Reef_Check
    # ------------------------------------------------------------------
    print("1/8 Sesgo de fuentes...")
    fuente = (
        df.groupby("Data_Source", observed=False)
        .agg(
            n=("Percent_Bleaching", "size"),
            pct_severo=("Percent_Bleaching", lambda s: (s > 30).mean()),
            bleach_medio=("Percent_Bleaching", "mean"),
            con_reef_id=("tiene_reef_id", "mean"),
            profundidad=("Depth_m", "mean"),
        )
        .sort_values("n", ascending=False)
        .reset_index()
    )
    figura_fuentes(df)

    # ------------------------------------------------------------------
    # 2. Profundidad
    # ------------------------------------------------------------------
    print("2/8 Profundidad...")
    r_bruta = float(df["Depth_m"].corr(df["Percent_Bleaching"]))
    r_reef = float(df.loc[df["es_reef_check"], "Depth_m"].corr(df.loc[df["es_reef_check"], "Percent_Bleaching"]))
    r_resto = float(df.loc[~df["es_reef_check"], "Depth_m"].corr(df.loc[~df["es_reef_check"], "Percent_Bleaching"]))
    r_parcial = correlacion_parcial_fuente(df)
    sitio = (
        df.dropna(subset=["Depth_m"])
        .groupby("Site_ID", observed=False)
        .agg(depth=("Depth_m", "mean"), bleach=("Percent_Bleaching", "mean"))
    )
    r_sitio = float(sitio["depth"].corr(sitio["bleach"]))
    figura_profundidad(df)

    # ------------------------------------------------------------------
    # 3. Moran
    # ------------------------------------------------------------------
    print("3/8 I de Moran...")
    sitios = (
        df.groupby("Site_ID", observed=False)
        .agg(
            lat=("Latitude_Degrees", "mean"),
            lon=("Longitude_Degrees", "mean"),
            bleach=("Percent_Bleaching", "mean"),
            tsa=("TSA", "mean"),
            dhw=("TSA_DHW", "mean"),
        )
        .dropna()
    )
    moran_bleach = moran_knn(sitios["bleach"].to_numpy(), sitios[["lat", "lon"]].to_numpy())
    moran_tsa = moran_knn(sitios["tsa"].to_numpy(), sitios[["lat", "lon"]].to_numpy())
    moran_dhw = moran_knn(sitios["dhw"].to_numpy(), sitios[["lat", "lon"]].to_numpy())

    # ------------------------------------------------------------------
    # 4. Baseline CRW
    # ------------------------------------------------------------------
    print("4/8 Baseline CRW...")
    dhw = df["TSA_DHW"]
    y = df["Bleaching_Class"].astype(str)
    reglas = {
        "CRW 3 clases (DHW 4/8)": crw_tres_clases(dhw.fillna(0)),
        "Alerta si DHW >= 4": np.where(dhw.fillna(0) >= 4, "Severo", "Bajo"),
        "Alerta si DHW >= 8": np.where(dhw.fillna(0) >= 8, "Severo", "Bajo"),
        "HotSpot TSA >= 1": np.where(df["TSA"].fillna(-99) >= 1, "Severo", "Bajo"),
    }
    crw_filas = []
    for nombre, pred in reglas.items():
        m = evaluar_regla(y, pred)
        m_rc = evaluar_regla(y[df["es_reef_check"]], pred[df["es_reef_check"].to_numpy()])
        m_nr = evaluar_regla(y[~df["es_reef_check"]], pred[(~df["es_reef_check"]).to_numpy()])
        crw_filas.append(
            {
                "metodo": nombre,
                **{f"full_{k}": v for k, v in m.items()},
                **{f"rc_{k}": v for k, v in m_rc.items()},
                **{f"nr_{k}": v for k, v in m_nr.items()},
            }
        )
    crw_df = pd.DataFrame(crw_filas)

    # ------------------------------------------------------------------
    # 5-7. Modelos: Site_ID en conjunto completo, RF acotado, DHW
    # ------------------------------------------------------------------
    print("5/8 CV por Site_ID en el conjunto completo...")
    df_ml = df.dropna(subset=["Site_ID"]).copy()
    experimentos = [
        ("Logistica base", "logistica", BASE_NUM, ["Ocean_Name"]),
        ("Logistica + DHW", "logistica", DHW_NUM, ["Ocean_Name"]),
        ("Logistica termica + DHW", "logistica", TERMICA_DHW, None),
        ("RF profundidad 8 + DHW", "rf_prof8", DHW_NUM, ["Ocean_Name"]),
        ("RF profundidad 16 + DHW", "rf_prof16", DHW_NUM, ["Ocean_Name"]),
        ("RF libre + DHW", "rf_libre", DHW_NUM, ["Ocean_Name"]),
    ]
    site_rows = []
    for etiqueta, modelo, nums, cats in experimentos:
        print(f"   {etiqueta} ...")
        aleat = evaluar_cv(df_ml, nums, cats, modelo, None, "aleatoria")
        grup = evaluar_cv(df_ml, nums, cats, modelo, df_ml["Site_ID"], "grupos")
        site_rows.append(
            {
                "metodo": etiqueta,
                "f1_aleatoria": aleat["f1_macro"],
                "f1_aleatoria_sd": aleat["f1_macro_sd"],
                "f1_sitio": grup["f1_macro"],
                "f1_sitio_sd": grup["f1_macro_sd"],
                "rec_aleatoria": aleat["recall_severo"],
                "rec_sitio": grup["recall_severo"],
                "rec_sitio_sd": grup["recall_severo_sd"],
                "pr_auc_sitio": grup["pr_auc_severo"],
                "delta_rel": (grup["f1_macro"] - aleat["f1_macro"]) / aleat["f1_macro"] * 100,
            }
        )
    site_df = pd.DataFrame(site_rows)

    # ------------------------------------------------------------------
    # 6. Bloqueo geografico
    # ------------------------------------------------------------------
    print("6/8 Leave-one-ocean-out y ecorregion...")
    ocean_rows = []
    for etiqueta, modelo, nums in [
        ("Logistica termica + DHW", "logistica", TERMICA_DHW),
        ("RF profundidad 8 + DHW", "rf_prof8", DHW_NUM),
    ]:
        print(f"   oceano {etiqueta} ...")
        res = evaluar_cv(df_ml, nums, None, modelo, df_ml["Ocean_Name"], "loo_grupo")
        ocean_rows.append({"metodo": etiqueta, "bloqueo": "Leave-one-ocean-out", **res})
        print(f"   ecorregion {etiqueta} ...")
        eco = df_ml.dropna(subset=["Ecoregion_Name"])
        res_e = evaluar_cv(eco, nums, None, modelo, eco["Ecoregion_Name"], "grupos")
        ocean_rows.append({"metodo": etiqueta, "bloqueo": "Ecorregion (5 pliegues)", **res_e})
    geo_df = pd.DataFrame(ocean_rows)

    # ------------------------------------------------------------------
    # 8. Temporal
    # ------------------------------------------------------------------
    print("7/8 Validacion temporal...")
    temp_rows = []
    cortes = [
        ("Entrena <=2012 / test >=2013", 2012, 2013),
        ("Entrena <=2013 / test >=2014", 2013, 2014),
    ]
    for etiqueta, y_train, y_test in cortes:
        train = df_ml[df_ml["Date_Year"] <= y_train]
        test = df_ml[df_ml["Date_Year"] >= y_test]
        for metodo, modelo, nums, cats in [
            ("Logistica + DHW", "logistica", DHW_NUM, ["Ocean_Name"]),
            ("RF profundidad 8 + DHW", "rf_prof8", DHW_NUM, ["Ocean_Name"]),
            ("CRW DHW>=4", None, None, None),
        ]:
            if metodo.startswith("CRW"):
                pred = np.where(test["TSA_DHW"].fillna(0) >= 4, "Severo", "Bajo")
                m = evaluar_regla(test["Bleaching_Class"].astype(str), pred)
            else:
                m = evaluar_holdout(train, test, nums, cats, modelo)
            temp_rows.append(
                {
                    "corte": etiqueta,
                    "metodo": metodo,
                    "n_train": len(train),
                    "n_test": len(test),
                    **m,
                }
            )
    temp_df = pd.DataFrame(temp_rows)

    print("8/8 Figuras y memoria tabular...")
    fig_df = pd.DataFrame(
        [
            {
                "metodo": "CRW DHW >= 4 (conjunto completo)",
                "recall_severo": crw_df.loc[crw_df["metodo"] == "Alerta si DHW >= 4", "full_recall_severo"].iloc[0],
            },
            {
                "metodo": "CRW DHW >= 8 (conjunto completo)",
                "recall_severo": crw_df.loc[crw_df["metodo"] == "Alerta si DHW >= 8", "full_recall_severo"].iloc[0],
            },
        ]
    )
    extra = site_df[["metodo", "rec_sitio"]].rename(columns={"rec_sitio": "recall_severo"})
    figura_baseline(pd.concat([fig_df, extra], ignore_index=True))

    # ------------------------------------------------------------------
    # Informe
    # ------------------------------------------------------------------
    md: list[str] = []
    md.append("# Remedición de las objeciones del tribunal")
    md.append("")
    md.append(
        "Experimentos diseñados para cerrar las lagunas identificadas en la "
        "evaluación de la memoria. Script: `src/tribunal_remediacion.py`. "
        "Semilla fija (`random_state=42`). El preprocesado se ajusta dentro "
        "de cada partición de entrenamiento."
    )
    md.append("")
    md.append("## 1. El sesgo de `Reef_ID` no es de prevalencia: es de protocolo")
    md.append("")
    md.append(
        "`Reef_ID` está informado **solo** en Reef_Check. Donner, AGRRA, FRRP "
        "y el resto de programas —precisamente los que concentran los eventos "
        "masivos— quedan fuera de la validación agrupada de la memoria. "
        "La solución no es discutir el 2,11 % frente al 12,42 %: es repetir "
        "la validación agrupando por `Site_ID` (cobertura 100 %) o por bloque "
        "geográfico."
    )
    md.append("")
    md.append(
        tabla_md(
            [
                [
                    str(r["Data_Source"]),
                    str(int(r["n"])),
                    fmt(r["pct_severo"] * 100, 2) + " %",
                    fmt(r["bleach_medio"], 2),
                    fmt(r["con_reef_id"] * 100, 1) + " %",
                    fmt(r["profundidad"], 2),
                ]
                for _, r in fuente.iterrows()
            ],
            ["Fuente", "n", "Severo", "Bleach medio (%)", "Con Reef_ID", "Profundidad media (m)"],
        )
    )
    md.append("")
    md.append("## 2. La correlación positiva con la profundidad es un confusor de fuente")
    md.append("")
    md.append(
        f"Correlación bruta `Depth_m`–`Percent_Bleaching`: r = {fmt(r_bruta, 3)}. "
        f"Dentro de Reef_Check: r = {fmt(r_reef, 3)}. "
        f"En el resto de fuentes: r = {fmt(r_resto, 3)}. "
        f"Tras residualizar ambas variables respecto a `Data_Source`: r parcial = {fmt(r_parcial, 3)}. "
        f"Agregando al sitio: r = {fmt(r_sitio, 3)}. "
        "La asociación aparente se desinfla cuando se controla el protocolo. "
        "Reef_Check muestrea rutinariamente aguas someras con poco blanqueamiento; "
        "Donner y McClanahan concentran campañas de evento, algo más profundas y con mucha más severidad."
    )
    md.append("")
    md.append("## 3. I de Moran sobre centroides de sitio (k = 8 vecinos)")
    md.append("")
    md.append(
        tabla_md(
            [
                ["Percent_Bleaching (media de sitio)", fmt(moran_bleach["I"], 3), fmt(moran_bleach["p_perm"], 3), str(int(moran_bleach["n"]))],
                ["TSA", fmt(moran_tsa["I"], 3), fmt(moran_tsa["p_perm"], 3), str(int(moran_tsa["n"]))],
                ["TSA_DHW", fmt(moran_dhw["I"], 3), fmt(moran_dhw["p_perm"], 3), str(int(moran_dhw["n"]))],
            ],
            ["Variable", "I de Moran", "p (99 permutaciones)", "Sitios"],
        )
    )
    md.append("")
    md.append(
        "La autocorrelación de los índices térmicos justifica el bloqueo geográfico: "
        "no basta con separar réplicas del mismo `Reef_ID`."
    )
    md.append("")
    md.append("## 4. Baseline operativo NOAA Coral Reef Watch")
    md.append("")
    md.append(
        "Reglas sin entrenamiento, evaluadas sobre las 34 515 observaciones con respuesta. "
        "Mapeo de tres clases: DHW < 4 Bajo, 4–8 Moderado, ≥ 8 Severo. "
        "Las reglas binarias etiquetan positivo como Severo y el resto como Bajo."
    )
    md.append("")
    md.append(
        tabla_md(
            [
                [
                    r["metodo"],
                    fmt(r["full_recall_severo"], 3),
                    fmt(r["full_precision_severo"], 3),
                    fmt(r["full_f1_macro"], 3),
                    fmt(r["rc_recall_severo"], 3),
                    fmt(r["nr_recall_severo"], 3),
                ]
                for _, r in crw_df.iterrows()
            ],
            ["Regla", "Recall Severo", "Precisión Severo", "F1 macro", "Recall en Reef_Check", "Recall en resto"],
        )
    )
    md.append("")
    md.append("## 5. DHW en el modelo principal y RF con profundidad acotada")
    md.append("")
    md.append(
        "Conjunto completo (n = 34 515), validación aleatoria estratificada frente a "
        "`StratifiedGroupKFold` por `Site_ID` (11 068 sitios, cobertura 100 %). "
        "Media ± desviación de 5 pliegues."
    )
    md.append("")
    md.append(
        tabla_md(
            [
                [
                    r["metodo"],
                    fmt(r["f1_aleatoria"], 3),
                    fmt(r["f1_sitio"], 3),
                    fmt(r["delta_rel"], 1) + " %",
                    fmt(r["rec_sitio"], 3),
                    fmt(r["pr_auc_sitio"], 3),
                ]
                for _, r in site_df.iterrows()
            ],
            ["Modelo", "F1 aleatoria", "F1 por Site_ID", "Δ relativa", "Recall Severo (Site_ID)", "PR-AUC Severo (Site_ID)"],
        )
    )
    md.append("")
    md.append("## 6. Transferencia entre cuencas y ecorregiones")
    md.append("")
    md.append(
        tabla_md(
            [
                [
                    r["metodo"],
                    r["bloqueo"],
                    fmt(r["f1_macro"], 3),
                    fmt(r["recall_severo"], 3),
                    fmt(r["pr_auc_severo"], 3),
                ]
                for _, r in geo_df.iterrows()
            ],
            ["Modelo", "Bloqueo", "F1 macro", "Recall Severo", "PR-AUC Severo"],
        )
    )
    md.append("")
    md.append("## 7. Validación temporal")
    md.append("")
    md.append(
        tabla_md(
            [
                [
                    r["corte"],
                    r["metodo"],
                    str(int(r["n_train"])),
                    str(int(r["n_test"])),
                    fmt(r["f1_macro"], 3),
                    fmt(r["recall_severo"], 3),
                    fmt(r["pr_auc_severo"], 3),
                ]
                for _, r in temp_df.iterrows()
            ],
            ["Corte", "Modelo", "n train", "n test", "F1 macro", "Recall Severo", "PR-AUC Severo"],
        )
    )
    md.append("")
    md.append("## Lectura para la defensa")
    md.append("")
    md.append(
        "- Si la logística con DHW no supera de forma clara a `DHW >= 4` en recall, "
        "el valor del TFM no es el clasificador, sino haber cuantificado cuándo el ML no transfiere."
    )
    md.append(
        "- Si acotar `max_depth` reduce la brecha aleatoria/espacial, parte del «colapso» de Random Forest era hiperparámetro, no destino de la familia."
    )
    md.append(
        "- El leave-one-ocean-out es la cifra que hay que dar cuando un gestor pregunta por un arrecife en una cuenca nueva."
    )
    md.append("")
    md.append("Figuras: `tribunal_fuentes_severidad.png`, `tribunal_profundidad_fuente.png`, `tribunal_baseline_crw.png`.")

    texto = "\n".join(md) + "\n"
    out = TABLES_DIR / "tribunal_remediacion.md"
    out.write_text(texto, encoding="utf-8")
    print(f"Escrito {out}")


if __name__ == "__main__":
    main()
