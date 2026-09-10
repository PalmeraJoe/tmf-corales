"""Leave-one-program-out, calibracion de P(Severo) y area de aplicabilidad.

Cierra tres lagunas que la memoria ya senalaba en 7.3-7.4:

1. Transferencia entre programas de monitoreo (interno por protocolo, no validacion
   externa). McClanahan y Donner documentan eventos; Reef_Check y AGRRA, el estado
   rutinario del arrecife.
2. Brier y diagrama de fiabilidad de P(Severo) bajo CV por Site_ID y corte temporal.
3. Indice de disimilitud de Meyer y Pebesma (2021) sobre el leave-one-ocean-out:
   distancia euclidea ponderada en el espacio de predictores estandarizado, con
   pesos TreeSHAP del propio bosque (no importancia Gini, inconsistente segun
   Lundberg et al., 2020), umbral del AOA como bigote superior del DI de
   entrenamiento.

Genera:
    reports/tables/paquete_mejoras.md
    reports/figures/calibracion_severo.png
    reports/figures/leave_one_program.png
    reports/figures/area_aplicabilidad.png
    reports/figures/pipeline_pronostico.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from explainability import pesos_shap_numericos

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

RANDOM_STATE = 42
N_SPLITS = 5
ANIO_CORTE = 2012
CLASE = "Severo"
MIN_N_PROGRAMA = 200
N_BINS = 10

TERMICAS = ["SSTA", "TSA"]
ACUMULADO = ["TSA_DHW"]
CONTEXTO = ["Depth_m", "Distance_to_Shore", "ClimSST"]
NUM_BASE = TERMICAS + ACUMULADO + CONTEXTO
RUTINA = {"Reef_Check", "AGRRA"}
EVENTO = {"Donner", "McClanahan", "Kumagai"}


def clasificar(v: float) -> str:
    if v < 10:
        return "Bajo"
    if v <= 30:
        return "Moderado"
    return "Severo"


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, na_values=["nd", "ND"], low_memory=False)
    df = df.loc[df["Percent_Bleaching"].notna()].copy()
    df["Bleaching_Class"] = df["Percent_Bleaching"].apply(clasificar)
    df["y"] = (df["Bleaching_Class"] == CLASE).astype(int)
    df["Data_Source"] = df["Data_Source"].fillna("Desconocido")
    return df


def construir(tipo: str, numericas: list[str], categoricas: list[str]) -> Pipeline:
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
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categoricas,
            )
        )
    if tipo == "rf":
        clf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    else:
        clf = LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE
        )
    return Pipeline([("prep", ColumnTransformer(transformadores)), ("clf", clf)])


def proba_severo(pipe: Pipeline, X: pd.DataFrame) -> np.ndarray:
    clases = list(pipe.classes_)
    col = clases.index(CLASE)
    return pipe.predict_proba(X)[:, col]


def ece(y: np.ndarray, p: np.ndarray, n_bins: int = N_BINS) -> float:
    """Expected calibration error en bins de cuantiles."""
    orden = np.argsort(p)
    y_s, p_s = y[orden], p[orden]
    cortes = np.array_split(np.arange(len(p)), n_bins)
    total = 0.0
    n = len(p)
    for idx in cortes:
        if len(idx) == 0:
            continue
        total += (len(idx) / n) * abs(y_s[idx].mean() - p_s[idx].mean())
    return float(total)


def ajustar_predecir(
    tipo: str,
    tr: pd.DataFrame,
    te: pd.DataFrame,
    numericas: list[str],
    categoricas: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    cols = numericas + categoricas
    pipe = construir(tipo, numericas, categoricas)
    pipe.fit(tr[cols], tr["Bleaching_Class"])
    return proba_severo(pipe, te[cols]), pipe.predict(te[cols])


def metricas_binarias(
    y: np.ndarray, p: np.ndarray, pred_clase: np.ndarray | None = None
) -> dict:
    pred = (p >= 0.5).astype(int)
    salida = {
        "n": int(len(y)),
        "prevalencia": float(y.mean()),
        "p_media": float(p.mean()),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "f1_severo": float(f1_score(y, pred, zero_division=0)),
        "brier": float(brier_score_loss(y, p)),
    }
    if pred_clase is not None:
        sev = (pred_clase == CLASE).astype(int)
        salida["recall_argmax"] = float(recall_score(y, sev, zero_division=0))
        salida["f1_argmax"] = float(f1_score(y, sev, zero_division=0))
    return salida


def leave_one_program(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    conteo = df["Data_Source"].value_counts()
    programas = [p for p in conteo.index if conteo[p] >= MIN_N_PROGRAMA]
    filas = []
    for programa in programas:
        te = df["Data_Source"] == programa
        tr = df.loc[~te]
        y_te = df.loc[te, "y"].to_numpy()
        for tipo, etiqueta, numericas, cats in (
            ("lr", "Logistica termica + DHW", TERMICAS + ACUMULADO, []),
            ("rf", "RF profundidad 8 + DHW", NUM_BASE, ["Ocean_Name"]),
        ):
            p, pred = ajustar_predecir(tipo, tr, df.loc[te], numericas, cats)
            m = metricas_binarias(y_te, p, pred)
            m.update(
                {
                    "Programa": programa,
                    "Modelo": etiqueta,
                    "n_train": int((~te).sum()),
                    "prev_train": float(tr["y"].mean()),
                }
            )
            filas.append(m)
            print(
                f"  {programa:<12} {etiqueta:<26} n={m['n']:>5} "
                f"prev {100 * m['prevalencia']:5.1f}%  p={m['p_media']:.3f}  "
                f"rec={m['recall']:.3f}  Brier={m['brier']:.3f}"
            )

    # Contraste de protocolo: rutina frente a documentacion de evento.
    tr = df[df["Data_Source"].isin(RUTINA)]
    te = df[df["Data_Source"].isin(EVENTO)]
    protocolo = {}
    y_te = te["y"].to_numpy()
    for tipo, etiqueta, numericas, cats in (
        ("lr", "Logistica termica + DHW", TERMICAS + ACUMULADO, []),
        ("rf", "RF profundidad 8 + DHW", NUM_BASE, ["Ocean_Name"]),
    ):
        p, pred = ajustar_predecir(tipo, tr, te, numericas, cats)
        m = metricas_binarias(y_te, p, pred)
        m["Modelo"] = etiqueta
        protocolo[etiqueta] = m
        print(
            f"  protocolo    {etiqueta:<26} n={m['n']:>5} "
            f"prev {100 * m['prevalencia']:5.1f}%  p={m['p_media']:.3f}  "
            f"rec={m['recall']:.3f}  Brier={m['brier']:.3f}"
        )
    protocolo["n_train"] = int(len(tr))
    protocolo["prev_train"] = float(tr["y"].mean())
    protocolo["n_test"] = int(len(te))
    return pd.DataFrame(filas), protocolo


def oof_site_id(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Probabilidades fuera de pliegue agrupadas por Site_ID."""
    y = df["y"].to_numpy()
    grupos = df["Site_ID"]
    plegado = StratifiedGroupKFold(
        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
    )
    configs = {
        "lr": (TERMICAS + ACUMULADO, []),
        "rf": (NUM_BASE, ["Ocean_Name"]),
    }
    oof = {k: np.zeros(len(df), dtype=float) for k in configs}
    pred_oof = {k: np.empty(len(df), dtype=object) for k in configs}
    for tipo, (numericas, cats) in configs.items():
        cols = numericas + cats
        X = df[cols]
        yy = df["Bleaching_Class"]
        for idx_tr, idx_te in plegado.split(X, yy, groups=grupos):
            pipe = construir(tipo, numericas, cats)
            pipe.fit(X.iloc[idx_tr], yy.iloc[idx_tr])
            oof[tipo][idx_te] = proba_severo(pipe, X.iloc[idx_te])
            pred_oof[tipo][idx_te] = pipe.predict(X.iloc[idx_te])
        print(f"  OOF {tipo}: Brier={brier_score_loss(y, oof[tipo]):.4f}")
    oof["y"] = y
    oof["crw"] = (df["TSA_DHW"].fillna(0) >= 4.0).astype(float).to_numpy()
    oof["pred_lr"] = pred_oof["lr"]
    oof["pred_rf"] = pred_oof["rf"]
    return oof


def corte_temporal(df: pd.DataFrame) -> dict:
    tr = df[df["Date_Year"] <= ANIO_CORTE].copy()
    te = df[df["Date_Year"] > ANIO_CORTE].copy()
    y_te = te["y"].to_numpy()
    salida: dict = {
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "prev_train": float(tr["y"].mean()),
        "prev_test": float(te["y"].mean()),
    }
    p_lr, pred_lr = ajustar_predecir("lr", tr, te, TERMICAS + ACUMULADO, [])
    p_rf, pred_rf = ajustar_predecir("rf", tr, te, NUM_BASE, ["Ocean_Name"])
    p_crw = (te["TSA_DHW"].fillna(0) >= 4.0).astype(float).to_numpy()
    pred_crw = np.where(p_crw >= 0.5, CLASE, "Bajo")

    # Isotonica ajustada solo sobre el entrenamiento (OOF por sitio).
    grupos = tr["Site_ID"]
    oof_rf = np.zeros(len(tr), dtype=float)
    X_tr = tr[NUM_BASE + ["Ocean_Name"]]
    splitter = StratifiedGroupKFold(
        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
    )
    for idx_a, idx_b in splitter.split(X_tr, tr["Bleaching_Class"], groups=grupos):
        pipe = construir("rf", NUM_BASE, ["Ocean_Name"])
        pipe.fit(X_tr.iloc[idx_a], tr["Bleaching_Class"].iloc[idx_a])
        oof_rf[idx_b] = proba_severo(pipe, X_tr.iloc[idx_b])
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(oof_rf, tr["y"].to_numpy())
    p_rf_iso = iso.predict(p_rf)

    for nombre, p, pred in (
        ("Logistica termica + DHW", p_lr, pred_lr),
        ("RF profundidad 8 + DHW", p_rf, pred_rf),
        ("RF profundidad 8 + isotonica", p_rf_iso, None),
        ("Regla CRW DHW >= 4", p_crw, pred_crw),
    ):
        m = metricas_binarias(y_te, p, pred)
        m["ece"] = ece(y_te, p)
        salida[nombre] = {"p": p, **m}
        rec = m.get("recall_argmax", m["recall"])
        print(
            f"  temporal {nombre:<32} Brier={m['brier']:.4f} ECE={m['ece']:.4f} "
            f"rec_argmax={rec:.3f} rec_0.5={m['recall']:.3f}"
        )
    salida["y"] = y_te
    return salida


def matriz_ponderada(X: np.ndarray, pesos: np.ndarray) -> np.ndarray:
    pesos = np.clip(pesos, 1e-8, None)
    pesos = pesos / pesos.sum()
    return X * np.sqrt(pesos)


def di_entrenamiento(Xw: np.ndarray) -> tuple[NearestNeighbors, float, np.ndarray]:
    """Umbral AOA: bigote superior (Q3 + 1,5 IQR) del DI de cada punto de train al vecino."""
    nn = NearestNeighbors(n_neighbors=2, algorithm="auto")
    nn.fit(Xw)
    dist, _ = nn.kneighbors(Xw, n_neighbors=2)
    di_train = dist[:, 1]
    q1, q3 = np.percentile(di_train, [25, 75])
    umbral = float(q3 + 1.5 * (q3 - q1))
    return nn, umbral, di_train


def area_aplicabilidad(df: pd.DataFrame) -> pd.DataFrame:
    """Leave-one-ocean-out con DI de Meyer y Pebesma (2021) sobre RF profundidad 8."""
    numericas = NUM_BASE
    filas = []
    di_puntos = []
    for cuenca in sorted(df["Ocean_Name"].dropna().unique()):
        mascara_te = df["Ocean_Name"] == cuenca
        n_te = int(mascara_te.sum())
        n_sev = int(df.loc[mascara_te, "y"].sum())
        if n_te < 50 or n_sev < 5:
            continue
        tr = df.loc[~mascara_te]
        te = df.loc[mascara_te]
        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(imputer.fit_transform(tr[numericas]))
        X_te = scaler.transform(imputer.transform(te[numericas]))

        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        rf.fit(X_tr, tr["Bleaching_Class"])
        # TreeSHAP del propio bosque de la cuenca, no Gini (apartado 4.3.2).
        pesos = pesos_shap_numericos(rf, X_tr)
        Xw_tr = matriz_ponderada(X_tr, pesos)
        Xw_te = matriz_ponderada(X_te, pesos)
        nn, umbral, _ = di_entrenamiento(Xw_tr)
        di = nn.kneighbors(Xw_te, n_neighbors=1)[0][:, 0]
        clases = list(rf.classes_)
        p = rf.predict_proba(X_te)[:, clases.index(CLASE)]
        y = te["y"].to_numpy()
        dentro = di <= umbral
        fuera = ~dentro

        def bloque(mask: np.ndarray) -> dict:
            if mask.sum() == 0:
                return {"n": 0, "recall": float("nan"), "brier": float("nan")}
            pred = (p[mask] >= 0.5).astype(int)
            return {
                "n": int(mask.sum()),
                "recall": float(recall_score(y[mask], pred, zero_division=0)),
                "brier": float(brier_score_loss(y[mask], p[mask])),
            }

        d = bloque(dentro)
        f = bloque(fuera)
        t = bloque(np.ones(len(y), dtype=bool))
        fila = {
            "Cuenca": cuenca,
            "n_test": n_te,
            "pct_severo": float(100 * y.mean()),
            "umbral_DI": umbral,
            "pct_dentro_AOA": float(100 * dentro.mean()),
            "DI_mediano": float(np.median(di)),
            "recall_dentro": d["recall"],
            "recall_fuera": f["recall"],
            "recall_total": t["recall"],
            "brier_dentro": d["brier"],
            "brier_fuera": f["brier"],
            "n_dentro": d["n"],
            "n_fuera": f["n"],
            "pesos_shap": {nombre: float(w) for nombre, w in zip(numericas, pesos)},
        }
        filas.append(fila)
        di_puntos.append(
            pd.DataFrame(
                {
                    "Cuenca": cuenca,
                    "DI": di,
                    "dentro": dentro,
                    "y": y,
                    "p": p,
                    "error": np.abs(y - p),
                }
            )
        )
        print(
            f"  {cuenca:<18} dentro {fila['pct_dentro_AOA']:5.1f}%  "
            f"rec in={d['recall']:.3f} out={f['recall']:.3f}  "
            f"Brier in={d['brier']:.3f} out={f['brier']:.3f}"
        )
    puntos = pd.concat(di_puntos, ignore_index=True)
    puntos.attrs["resumen"] = pd.DataFrame(filas)
    return puntos


def coma(v, dec: int = 3) -> str:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "n/d"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}".replace(",", " ")
    return f"{float(v):.{dec}f}".replace(".", ",")


def figura_calibracion(oof: dict, temporal: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.4))
    series_oof = [
        ("Logistica termica + DHW", oof["lr"], "#1f4e79"),
        ("RF profundidad 8 + DHW", oof["rf"], "#c0392b"),
        ("Regla CRW (0/1)", oof["crw"], "#7f8c8d"),
    ]
    series_tmp = [
        ("Logistica termica + DHW", temporal["Logistica termica + DHW"]["p"], "#1f4e79"),
        ("RF profundidad 8 + DHW", temporal["RF profundidad 8 + DHW"]["p"], "#c0392b"),
        ("RF + isotonica", temporal["RF profundidad 8 + isotonica"]["p"], "#e67e22"),
        ("Regla CRW (0/1)", temporal["Regla CRW DHW >= 4"]["p"], "#7f8c8d"),
    ]
    for ax, y, series, titulo in (
        (axes[0], oof["y"], series_oof, "CV agrupada por Site_ID"),
        (axes[1], temporal["y"], series_tmp, "Corte temporal 2013–2020"),
    ):
        ax.plot([0, 1], [0, 1], linestyle="--", color="0.5", linewidth=1, label="Calibracion perfecta")
        for nombre, p, color in series:
            frac, mean_p = calibration_curve(y, p, n_bins=N_BINS, strategy="quantile")
            ax.plot(mean_p, frac, marker="o", color=color, label=nombre, linewidth=1.6)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("P(Severo) media del bin")
        ax.set_ylabel("Frecuencia observada")
        ax.set_title(titulo, fontsize=11)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "calibracion_severo.png", dpi=300)
    plt.close(fig)


def figura_programas(res: pd.DataFrame) -> None:
    rf = res[res["Modelo"] == "RF profundidad 8 + DHW"].copy()
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    x = np.arange(len(rf))
    ax.bar(x - 0.2, 100 * rf["prevalencia"], width=0.4, label="Prevalencia observada (%)",
           color="#7f8c8d", edgecolor="black", linewidth=0.4)
    ax.bar(x + 0.2, 100 * rf["p_media"], width=0.4, label="P(Severo) media predicha (%)",
           color="#c0392b", edgecolor="black", linewidth=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(rf["Programa"], rotation=20, ha="right")
    ax.set_ylabel("%")
    ax.set_title("Leave-one-program-out: prevalencia frente a probabilidad media (RF profundidad 8)")
    ax.legend(fontsize=8.5)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "leave_one_program.png", dpi=300)
    plt.close(fig)


def figura_aoa(puntos: pd.DataFrame) -> None:
    resumen = puntos.attrs["resumen"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.3))
    for cuenca, sub in puntos.groupby("Cuenca"):
        ax1.scatter(sub["DI"], sub["error"], s=6, alpha=0.25, label=cuenca)
    umbral_med = float(resumen["umbral_DI"].median())
    ax1.axvline(umbral_med, color="black", linestyle="--", linewidth=1,
                label="Umbral AOA (mediana entre cuencas)")
    ax1.set_xlabel("Indice de disimilitud (Meyer y Pebesma, 2021)")
    ax1.set_ylabel("|y − P(Severo)|")
    ax1.set_title("Error de probabilidad frente a disimilitud")
    ax1.legend(fontsize=7.5, markerscale=3)
    ax1.grid(alpha=0.3)

    y = np.arange(len(resumen))
    rec_in = resumen["recall_dentro"].to_numpy(dtype=float)
    rec_out = resumen["recall_fuera"].to_numpy(dtype=float)
    ax2.barh(
        y - 0.18,
        np.where(np.isnan(rec_in), 0, 100 * rec_in),
        height=0.36,
        color="#1f4e79",
        edgecolor="black",
        linewidth=0.4,
        label="Dentro del AOA",
    )
    ax2.barh(
        y + 0.18,
        np.where(np.isnan(rec_out), 0, 100 * rec_out),
        height=0.36,
        color="#c0392b",
        edgecolor="black",
        linewidth=0.4,
        label="Fuera del AOA",
    )
    for i, r in enumerate(resumen.itertuples(index=False)):
        if r.n_dentro == 0:
            ax2.text(1.5, i - 0.18, "0 % en el AOA", va="center", fontsize=7, color="#1f4e79")
    ax2.set_yticks(y)
    ax2.set_yticklabels(resumen["Cuenca"])
    ax2.set_xlabel("Recall de «Severo» (%)")
    ax2.set_title("Leave-one-ocean-out segun el area de aplicabilidad")
    ax2.legend(fontsize=8)
    ax2.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "area_aplicabilidad.png", dpi=300)
    plt.close(fig)


def figura_pipeline() -> None:
    fig, ax = plt.subplots(figsize=(11.2, 4.6))
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    def caja(x, y, w, h, texto, color):
        patch = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=color, edgecolor="#2c3e50", linewidth=1.1,
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center",
                fontsize=8.2, wrap=True)

    def flecha(x1, y1, x2, y2):
        ax.add_patch(
            FancyArrowPatch(
                (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
                linewidth=1.2, color="#2c3e50",
            )
        )

    caja(0.3, 3.15, 2.4, 0.9, "SST observada\n(CoralTemp / CRW)", "#d6eaf8")
    caja(3.1, 3.15, 2.4, 0.9, "DHW observado\n(este trabajo)", "#d6eaf8")
    caja(5.9, 3.15, 2.5, 0.9, "Clasificador\n(logística / RF-8)", "#fdebd0")
    caja(8.8, 3.15, 2.1, 0.9, "Severidad\nconcurrente", "#d5f5e3")
    flecha(2.7, 3.6, 3.1, 3.6)
    flecha(5.5, 3.6, 5.9, 3.6)
    flecha(8.4, 3.6, 8.8, 3.6)

    caja(0.3, 0.55, 2.4, 0.9, "Pronóstico SST\n(NMME / CFSv2)", "#e8daef")
    caja(3.1, 0.55, 2.4, 0.9, "DHW previsto\n(1–3 meses)", "#e8daef")
    caja(5.9, 0.55, 2.5, 0.9, "El mismo\nclasificador", "#fdebd0")
    caja(8.8, 0.55, 2.1, 0.9, "Alerta a\n1–3 meses", "#f9e79f")
    flecha(2.7, 1.0, 3.1, 1.0)
    flecha(5.5, 1.0, 5.9, 1.0)
    flecha(8.4, 1.0, 8.8, 1.0)

    ax.text(5.6, 2.35, "Lo medido en este TFM", ha="center", fontsize=9, color="#1f4e79")
    ax.text(5.6, 0.18, "Acoplamiento no implementado: requiere un pronóstico térmico ajeno al clasificador",
            ha="center", fontsize=8, style="italic", color="#5d6d7e")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "pipeline_pronostico.png", dpi=300)
    plt.close(fig)


def tabla_md(lodso: pd.DataFrame, protocolo: dict, oof: dict, temporal: dict, aoa: pd.DataFrame) -> str:
    rf = lodso[lodso["Modelo"] == "RF profundidad 8 + DHW"]
    lr = lodso[lodso["Modelo"] == "Logistica termica + DHW"]
    resumen_aoa = aoa.attrs["resumen"]

    def filas_lodso(bloque: pd.DataFrame) -> str:
        lineas = [
            "| Programa | n | Prevalencia test (%) | P(Severo) media | Recall | Precisión | F1 severa | Brier |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for _, r in bloque.iterrows():
            lineas.append(
                f"| {r['Programa']} | {coma(r['n'], 0)} | {coma(100 * r['prevalencia'], 1)} | "
                f"{coma(r['p_media'])} | {coma(r['recall'])} | {coma(r['precision'])} | "
                f"{coma(r['f1_severo'])} | {coma(r['brier'])} |"
            )
        return "\n".join(lineas)

    def fila_cal(nombre: str, m: dict) -> str:
        rec = m.get("recall_argmax", m["recall"])
        return (
            f"| {nombre} | {coma(m['brier'], 4)} | {coma(m.get('ece', float('nan')), 4)} | "
            f"{coma(m['p_media'])} | {coma(rec)} |"
        )

    cal_oof = []
    pred_crw_oof = np.where(oof["crw"] >= 0.5, CLASE, "Bajo")
    for clave, etiqueta, pred in (
        ("lr", "Logistica termica + DHW", oof["pred_lr"]),
        ("rf", "RF profundidad 8 + DHW", oof["pred_rf"]),
        ("crw", "Regla CRW DHW >= 4", pred_crw_oof),
    ):
        m = metricas_binarias(oof["y"], oof[clave], pred)
        m["ece"] = ece(oof["y"], oof[clave])
        cal_oof.append(fila_cal(etiqueta, m))

    cal_tmp = []
    for nombre in (
        "Logistica termica + DHW",
        "RF profundidad 8 + DHW",
        "RF profundidad 8 + isotonica",
        "Regla CRW DHW >= 4",
    ):
        cal_tmp.append(fila_cal(nombre, temporal[nombre]))

    def filas_aoa() -> str:
        lineas = [
            "| Cuenca | n | Severo (%) | Dentro del AOA (%) | DI mediano | Recall dentro | Recall fuera | Brier dentro | Brier fuera |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in resumen_aoa.iterrows():
            lineas.append(
                f"| {r['Cuenca']} | {coma(r['n_test'], 0)} | {coma(r['pct_severo'], 1)} | "
                f"{coma(r['pct_dentro_AOA'], 1)} | {coma(r['DI_mediano'])} | "
                f"{coma(r['recall_dentro'])} | {coma(r['recall_fuera'])} | "
                f"{coma(r['brier_dentro'])} | {coma(r['brier_fuera'])} |"
            )
        return "\n".join(lineas)

    pr = protocolo["RF profundidad 8 + DHW"]
    pl = protocolo["Logistica termica + DHW"]

    return f"""# Leave-one-program-out, calibracion y area de aplicabilidad

Experimentos del paquete de mejoras. El leave-one-program-out permanece **dentro** de la
sintesis de Sully et al. (2019): mide transferencia entre protocolos, no validacion externa.

## 1. Leave-one-program-out

Se retiene como conjunto de prueba un programa con n ≥ {MIN_N_PROGRAMA} y se entrena con el resto.
`Ocean_Name` se codifica con `handle_unknown='ignore'`.

### Random Forest profundidad 8 + DHW

{filas_lodso(rf)}

### Logistica termica + DHW (sin contexto ni cuenca)

{filas_lodso(lr)}

## 2. Contraste de protocolo (rutina → evento)

Entrenamiento: Reef_Check + AGRRA (n = {coma(protocolo['n_train'], 0)}, prevalencia {coma(100 * protocolo['prev_train'], 2)} %).
Prueba: Donner + McClanahan + Kumagai (n = {coma(protocolo['n_test'], 0)}, prevalencia {coma(100 * pr['prevalencia'], 2)} %).

| Modelo | n test | Prevalencia (%) | P(Severo) media | Recall | Precisión | F1 severa | Brier |
|---|---|---|---|---|---|---|---|
| Logistica termica + DHW | {coma(pl['n'], 0)} | {coma(100 * pl['prevalencia'], 1)} | {coma(pl['p_media'])} | {coma(pl['recall'])} | {coma(pl['precision'])} | {coma(pl['f1_severo'])} | {coma(pl['brier'])} |
| RF profundidad 8 + DHW | {coma(pr['n'], 0)} | {coma(100 * pr['prevalencia'], 1)} | {coma(pr['p_media'])} | {coma(pr['recall'])} | {coma(pr['precision'])} | {coma(pr['f1_severo'])} | {coma(pr['brier'])} |

## 3. Calibracion de P(Severo)

CV agrupada por `Site_ID` (probabilidades fuera de pliegue) y corte temporal
(entrenamiento ≤ {ANIO_CORTE}, prueba ≥ {ANIO_CORTE + 1}). El ECE se calcula en {N_BINS} bins de cuantiles. El recall de esta tabla es el de
`predict` (argmax), salvo la isotonica, que solo calibra P(Severo) y se evalua a umbral 0,5.
La isotonica no sustituye las cifras oficiales de F1 del apartado 6.7.2.

### CV por Site_ID

| Modelo | Brier | ECE | P media | Recall (argmax) |
|---|---|---|---|---|
{chr(10).join(cal_oof)}

### Corte temporal

| Modelo | Brier | ECE | P media | Recall (argmax) |
|---|---|---|---|---|
{chr(10).join(cal_tmp)}

Prevalencia de prueba temporal: {coma(100 * temporal['prev_test'], 2)} %.

## 4. Area de aplicabilidad (Meyer y Pebesma, 2021)

Leave-one-ocean-out del Random Forest profundidad 8. Predictores numericos
`SSTA`, `TSA`, `TSA_DHW`, `Depth_m`, `Distance_to_Shore`, `ClimSST`, estandarizados
sobre el entrenamiento. Pesos: media |SHAP| del propio bosque de cada cuenca
(TreeSHAP; Lundberg et al., 2020), no la reduccion de impureza Gini. El umbral
del AOA es el bigote superior (Q3 + 1,5 IQR) del DI de cada punto de
entrenamiento a su vecino mas proximo.

{filas_aoa()}

Media ponderada de observaciones de prueba dentro del AOA:
{coma(100 * (resumen_aoa['n_dentro'].sum() / resumen_aoa['n_test'].sum()), 1)} %.

## Reproducibilidad

Script: `src/paquete_mejoras.py`. Semilla `{RANDOM_STATE}`.
"""


def _reescribir_seccion_aoa(aoa: pd.DataFrame) -> None:
    """Actualiza solo el bloque AOA de paquete_mejoras.md si el resto ya existe."""
    resumen = aoa.attrs["resumen"]
    destino = TABLES_DIR / "paquete_mejoras.md"
    lineas_tabla = [
        "| Cuenca | n | Severo (%) | Dentro del AOA (%) | DI mediano | Recall dentro | Recall fuera | Brier dentro | Brier fuera |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in resumen.iterrows():
        lineas_tabla.append(
            f"| {r['Cuenca']} | {coma(r['n_test'], 0)} | {coma(r['pct_severo'], 1)} | "
            f"{coma(r['pct_dentro_AOA'], 1)} | {coma(r['DI_mediano'])} | "
            f"{coma(r['recall_dentro'])} | {coma(r['recall_fuera'])} | "
            f"{coma(r['brier_dentro'])} | {coma(r['brier_fuera'])} |"
        )
    media = 100 * (resumen["n_dentro"].sum() / resumen["n_test"].sum())
    pesos_filas = []
    if "pesos_shap" in resumen.columns:
        acumulado: dict[str, list[float]] = {}
        for pesos in resumen["pesos_shap"]:
            for nombre, valor in pesos.items():
                acumulado.setdefault(nombre, []).append(valor)
        pesos_filas = [
            f"- `{nombre}`: {coma(float(np.mean(vals)))}"
            for nombre, vals in acumulado.items()
        ]
    bloque = (
        "Leave-one-ocean-out del Random Forest profundidad 8. Predictores numericos\n"
        "`SSTA`, `TSA`, `TSA_DHW`, `Depth_m`, `Distance_to_Shore`, `ClimSST`, estandarizados\n"
        "sobre el entrenamiento. Pesos: media |SHAP| del propio bosque de cada cuenca\n"
        "(TreeSHAP; Lundberg et al., 2020), no la reduccion de impureza Gini. El umbral\n"
        "del AOA es el bigote superior (Q3 + 1,5 IQR) del DI de cada punto de\n"
        "entrenamiento a su vecino mas proximo.\n\n"
        + "\n".join(lineas_tabla)
        + f"\n\nMedia ponderada de observaciones de prueba dentro del AOA:\n{coma(media, 1)} %.\n"
    )
    if pesos_filas:
        bloque += "\nPesos TreeSHAP medios entre cuencas:\n" + "\n".join(pesos_filas) + "\n"
    if destino.exists():
        texto = destino.read_text(encoding="utf-8")
        marca = "## 4. Area de aplicabilidad"
        if marca in texto:
            cabeza, resto = texto.split(marca, 1)
            if "## Reproducibilidad" in resto:
                _, cola = resto.split("## Reproducibilidad", 1)
                texto = (
                    cabeza
                    + marca
                    + " (Meyer y Pebesma, 2021)\n\n"
                    + bloque
                    + "\n## Reproducibilidad"
                    + cola
                )
                destino.write_text(texto, encoding="utf-8")
                return
    destino.write_text(
        "# Leave-one-program-out, calibracion y area de aplicabilidad\n\n"
        "## 4. Area de aplicabilidad (Meyer y Pebesma, 2021)\n\n"
        + bloque,
        encoding="utf-8",
    )


def main() -> None:
    import sys

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = cargar()
    print(f"Observaciones: {len(df)}")

    solo_aoa = "--aoa" in sys.argv
    if solo_aoa:
        print("\nArea de aplicabilidad (TreeSHAP)")
        aoa = area_aplicabilidad(df)
        figura_aoa(aoa)
        _reescribir_seccion_aoa(aoa)
        print("\nFigura:", FIGURES_DIR / "area_aplicabilidad.png")
        return

    print("\nLeave-one-program-out")
    lodso, protocolo = leave_one_program(df)

    print("\nCalibracion OOF por Site_ID")
    oof = oof_site_id(df)

    print("\nCalibracion corte temporal")
    temporal = corte_temporal(df)

    print("\nArea de aplicabilidad")
    aoa = area_aplicabilidad(df)

    figura_calibracion(oof, temporal)
    figura_programas(lodso)
    figura_aoa(aoa)
    figura_pipeline()

    texto = tabla_md(lodso, protocolo, oof, temporal, aoa)
    (TABLES_DIR / "paquete_mejoras.md").write_text(texto, encoding="utf-8")
    print("\nTabla:", TABLES_DIR / "paquete_mejoras.md")
    print("Figuras: calibracion_severo, leave_one_program, area_aplicabilidad, pipeline_pronostico")


if __name__ == "__main__":
    main()
