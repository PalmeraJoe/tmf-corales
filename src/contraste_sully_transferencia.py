"""Contraste empirico con Sully et al. (2019) y dos transferencias de dominio.

No es validacion externa fuera de la sintesis: el CSV termina en 2020 y no hay un
corpus independiente. Lo que si cabe, y el tribunal pedia, es:

1. Replicar las dos afirmaciones empiricas de Sully (SST en episodios de blanqueamiento
   por decenio; menos blanqueamiento donde la varianza termica es alta) sobre este
   conjunto, y senalar donde el RF-8 coincide o no.
2. Entrenar solo en Caribe + Pacifico Central (reino Eastern Indo-Pacific) y evaluar
   el resto. Bloqueo geografico mas severo que el ocean-out: dos regiones como fuente.
3. Entrenar en 2010-2017 y evaluar 2018-2020, anos posteriores a la ventana 1998-2017
   de Sully. El usuario pedia 2010-2021 / anos siguientes: 2021 no existe en el CSV.

Genera:
    reports/tables/contraste_sully_transferencia.md
    reports/figures/contraste_sully.png
    reports/figures/transferencia_dominio.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from explainability import pesos_shap_numericos
from paquete_mejoras import (
    ACUMULADO,
    CLASE,
    CONTEXTO,
    NUM_BASE,
    RANDOM_STATE,
    TERMICAS,
    ajustar_predecir,
    cargar,
    coma,
    di_entrenamiento,
    matriz_ponderada,
    metricas_binarias,
)

ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

ECO_CARIBE = {
    "Bahamas and Florida Keys",
    "Belize and west Caribbean",
    "Hispaniola Puerto Rico and Lesser Antilles",
    "Jamaica",
    "Cuba and Cayman Islands",
    "Netherlands Antilles and south Caribbean",
    "Bay of Campeche Yucatan Gulf of Mexico",
}
REALM_PACIFICO_CENTRAL = "Eastern Indo-Pacific"
ANIO_TRAIN_MIN = 2010
ANIO_TRAIN_MAX = 2017
ANIO_TEST_MIN = 2018


def mascara_caribe_pacifico(df: pd.DataFrame) -> pd.Series:
    return df["Ecoregion_Name"].isin(ECO_CARIBE) | (
        df["Realm_Name"] == REALM_PACIFICO_CENTRAL
    )


def sst_celsius(df: pd.DataFrame) -> pd.Series:
    return df["Temperature_Kelvin"] - 273.15


def crw_proba(te: pd.DataFrame) -> np.ndarray:
    return (te["TSA_DHW"].fillna(0) >= 4.0).astype(float).to_numpy()


def evaluar_bloque(
    tr: pd.DataFrame, te: pd.DataFrame, con_cuenca: bool
) -> list[dict]:
    y = te["y"].to_numpy()
    filas = []
    p_crw = crw_proba(te)
    pred_crw = np.where(p_crw >= 0.5, CLASE, "Bajo")
    m = metricas_binarias(y, p_crw, pred_crw)
    m["pr_auc"] = average_precision_score(y, p_crw) if y.any() else float("nan")
    m["Modelo"] = "Regla CRW DHW >= 4"
    filas.append(m)
    print(
        f"    CRW     rec={m['recall']:.3f}  F1={m['f1_severo']:.3f}  "
        f"prev={100 * m['prevalencia']:.1f}%"
    )

    for tipo, etiqueta, numericas, cats in (
        ("lr", "Logistica termica + DHW", TERMICAS + ACUMULADO, []),
        (
            "rf",
            "RF profundidad 8 + DHW",
            NUM_BASE,
            ["Ocean_Name"] if con_cuenca else [],
        ),
    ):
        p, pred = ajustar_predecir(tipo, tr, te, numericas, cats)
        m = metricas_binarias(y, p, pred)
        m["pr_auc"] = average_precision_score(y, p) if y.any() else float("nan")
        m["Modelo"] = etiqueta
        filas.append(m)
        print(
            f"    {etiqueta:<26} rec={m['recall']:.3f}  F1={m['f1_severo']:.3f}  "
            f"p={m['p_media']:.3f}  Brier={m['brier']:.3f}"
        )
    return filas


def aoa_porcentaje(tr: pd.DataFrame, te: pd.DataFrame) -> dict:
    numericas = NUM_BASE
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
    pesos = pesos_shap_numericos(rf, X_tr)
    Xw_tr = matriz_ponderada(X_tr, pesos)
    Xw_te = matriz_ponderada(X_te, pesos)
    nn, umbral, _ = di_entrenamiento(Xw_tr)
    di = nn.kneighbors(Xw_te, n_neighbors=1)[0][:, 0]
    dentro = di <= umbral
    return {
        "pct_dentro": float(100 * dentro.mean()),
        "umbral": float(umbral),
        "di_mediano": float(np.median(di)),
        "pesos": {k: float(v) for k, v in zip(numericas, pesos)},
    }


def contraste_sully(df: pd.DataFrame) -> dict:
    sst = sst_celsius(df)
    blanqueado = df["Percent_Bleaching"] > 0
    severo = df["y"] == 1
    periodos = [
        ("1998-2006 (Sully)", (df["Date_Year"] >= 1998) & (df["Date_Year"] <= 2006)),
        ("2007-2017 (Sully)", (df["Date_Year"] >= 2007) & (df["Date_Year"] <= 2017)),
        ("2018-2020 (post Sully)", df["Date_Year"] >= 2018),
    ]
    sst_eventos = []
    for etiqueta, mascara in periodos:
        for nombre, filtro in (("cualquier blanqueamiento", blanqueado), ("Severo", severo)):
            sel = mascara & filtro & sst.notna()
            sst_eventos.append(
                {
                    "Periodo": etiqueta,
                    "Definicion": nombre,
                    "n": int(sel.sum()),
                    "SST_media": float(sst[sel].mean()) if sel.any() else float("nan"),
                    "SST_sd": float(sst[sel].std()) if sel.any() else float("nan"),
                }
            )

    sitios = (
        df.assign(
            sst_sd=df["Temperature_Kelvin_Standard_Deviation"],
            ssta_sd=df["SSTA_Standard_Deviation"],
            sst=sst,
        )
        .groupby("Site_ID", observed=False)
        .agg(
            bleaching=("Percent_Bleaching", "mean"),
            pct_severo=("y", "mean"),
            sst_sd=("sst_sd", "mean"),
            ssta_sd=("ssta_sd", "mean"),
            clim=("ClimSST", "mean"),
            n=("Percent_Bleaching", "size"),
        )
        .dropna()
    )
    sitios = sitios[sitios["n"] >= 3]
    rho_ble = float(sitios["sst_sd"].corr(sitios["bleaching"], method="spearman"))
    rho_sev = float(sitios["sst_sd"].corr(sitios["pct_severo"], method="spearman"))
    rho_clim = float(sitios["clim"].corr(sitios["pct_severo"], method="spearman"))
    rho_ssta = float(sitios["ssta_sd"].corr(sitios["pct_severo"], method="spearman"))
    print(
        f"  Spearman sitio SST_SD vs blanqueamiento {rho_ble:.3f}; "
        f"vs P(Severo) {rho_sev:.3f}; ClimSST vs P(Severo) {rho_clim:.3f}; "
        f"SSTA_SD vs P(Severo) {rho_ssta:.3f}"
    )

    rc = df["Data_Source"] == "Reef_Check"
    sst_reef = []
    for etiqueta, mascara in periodos[:2]:
        sel = mascara & blanqueado & rc & sst.notna()
        sst_reef.append(
            {
                "Periodo": etiqueta.replace(" (Sully)", " Reef_Check"),
                "n": int(sel.sum()),
                "SST_media": float(sst[sel].mean()) if sel.any() else float("nan"),
            }
        )
    return {
        "sst_eventos": pd.DataFrame(sst_eventos),
        "sst_reef": pd.DataFrame(sst_reef),
        "sitios": sitios,
        "rho_ble": rho_ble,
        "rho_sev": rho_sev,
        "rho_clim": rho_clim,
        "rho_ssta": rho_ssta,
        "n_sitios": int(len(sitios)),
    }


def figura_sully(res: dict) -> None:
    sst_tab = res["sst_eventos"]
    sitios = res["sitios"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.2))

    sub = sst_tab[sst_tab["Definicion"] == "cualquier blanqueamiento"]
    colores = ["#1f4e79", "#e67e22", "#7f8c8d"]
    ax1.bar(
        range(len(sub)),
        sub["SST_media"],
        color=colores[: len(sub)],
        edgecolor="black",
        linewidth=0.5,
    )
    ax1.axhline(28.1, color="#1f4e79", linestyle="--", linewidth=1, label="Sully 1998-2006 (28,1 °C)")
    ax1.axhline(28.7, color="#e67e22", linestyle="--", linewidth=1, label="Sully 2007-2017 (28,7 °C)")
    ax1.set_xticks(range(len(sub)))
    ax1.set_xticklabels([p.replace(" (Sully)", "\n(Sully)").replace(" (post Sully)", "\n(post)") for p in sub["Periodo"]], fontsize=8)
    ax1.set_ylabel("SST media en observaciones con blanqueamiento (°C)")
    ax1.set_title("Replicacion del desplazamiento de umbral")
    ax1.legend(fontsize=7.5, loc="lower right")
    ax1.grid(axis="y", alpha=0.3)
    for i, v in enumerate(sub["SST_media"]):
        if np.isfinite(v):
            ax1.text(i, v + 0.05, f"{v:.2f}", ha="center", fontsize=8)

    muestra = sitios.sample(n=min(4000, len(sitios)), random_state=RANDOM_STATE)
    ax2.scatter(muestra["sst_sd"], 100 * muestra["pct_severo"], s=8, alpha=0.25, color="#1f4e79")
    ax2.set_xlabel("Desviacion tipica de SST en el emplazamiento (K)")
    ax2.set_ylabel("Episodios severos en el sitio (%)")
    ax2.set_title(f"Varianza termica frente a severidad (ρ = {res['rho_sev']:.2f})")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "contraste_sully.png", dpi=300)
    plt.close(fig)


def figura_transferencia(geo: pd.DataFrame, temporal: pd.DataFrame, temporal_nuevos: pd.DataFrame) -> None:
    bloques = [
        ("Caribe + Pacífico Central → resto", geo),
        ("2010-2017 → 2018-2020", temporal),
        ("2018-2020, sitios no vistos", temporal_nuevos),
    ]
    modelos = ["Regla CRW DHW >= 4", "Logistica termica + DHW", "RF profundidad 8 + DHW"]
    etiquetas = ["CRW DHW ≥ 4", "Logística térmica + DHW", "RF profundidad 8"]
    colores = ["#7f8c8d", "#1f4e79", "#c0392b"]
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.3))
    x = np.arange(len(bloques))
    ancho = 0.25
    for ax, metrica, titulo, ylim in (
        (axes[0], "recall", "Recall de «Severo»", (0, 1)),
        (axes[1], "f1_severo", "F1 de la clase severa", (0, 0.55)),
    ):
        for i, (modelo, etiqueta, color) in enumerate(zip(modelos, etiquetas, colores)):
            vals = []
            for _, tab in bloques:
                fila = tab[tab["Modelo"] == modelo]
                vals.append(float(fila[metrica].iloc[0]) if len(fila) else np.nan)
            ax.bar(x + (i - 1) * ancho, vals, width=ancho, label=etiqueta, color=color, edgecolor="black", linewidth=0.4)
        ax.set_xticks(x)
        ax.set_xticklabels([b[0] for b in bloques], fontsize=8)
        ax.set_ylabel(titulo)
        ax.set_ylim(*ylim)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "transferencia_dominio.png", dpi=300)
    plt.close(fig)


def filas_md(tab: pd.DataFrame) -> str:
    lineas = [
        "| Modelo | n | Prevalencia (%) | P media | Recall | Precisión | F1 severa | PR-AUC | Brier |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in tab.iterrows():
        lineas.append(
            f"| {r['Modelo']} | {coma(r['n'], 0)} | {coma(100 * r['prevalencia'], 1)} | "
            f"{coma(r['p_media'])} | {coma(r['recall'])} | {coma(r['precision'])} | "
            f"{coma(r['f1_severo'])} | {coma(r['pr_auc'])} | {coma(r['brier'])} |"
        )
    return "\n".join(lineas)


def exportar(
    sully: dict,
    geo: pd.DataFrame,
    temporal: pd.DataFrame,
    temporal_nuevos: pd.DataFrame,
    meta: dict,
) -> None:
    sst = sully["sst_eventos"]
    lineas_sst = [
        "| Periodo | Definición | n | SST media (°C) | DE |",
        "|---|---|---|---|---|",
    ]
    for _, r in sst.iterrows():
        lineas_sst.append(
            f"| {r['Periodo']} | {r['Definicion']} | {coma(r['n'], 0)} | "
            f"{coma(r['SST_media'], 2)} | {coma(r['SST_sd'], 2)} |"
        )
    lineas_rc = []
    for _, r in sully["sst_reef"].iterrows():
        lineas_rc.append(
            f"- {r['Periodo']}: n = {coma(r['n'], 0)}, media {coma(r['SST_media'], 2)} °C"
        )

    aoa = meta["aoa_geo"]
    texto = f"""# Contraste con Sully et al. (2019) y transferencias de dominio

Los tres experimentos permanecen dentro de la sintesis BCO-DMO. No sustituyen un corpus
independiente (Reef Check posterior a 2020, NOAA, una AMP concreta).

## 1. Contraste empirico con Sully et al. (2019)

Sully et al. analizaron Reef Check (9 215 puntos, 3 351 sitios, 1998-2017) con CoRTAD y un
modelo jerarquico bayesiano. Las 28,1 °C / 28,7 °C proceden de la distribucion de SST en
blanqueamiento (Figura 4, Weibull), no de la media aritmetica de este extracto. Aqui no se
reajusta ese modelo: se reporta Temperature_Kelvin - 273,15 sobre las 34 515 observaciones.

{chr(10).join(lineas_sst)}

Solo Reef_Check, cualquier blanqueamiento (Percent_Bleaching > 0):
{chr(10).join(lineas_rc)}

Spearman entre emplazamientos (n = {coma(sully['n_sitios'], 0)}, al menos 3 censos):
desviacion tipica de SST frente a blanqueamiento medio ρ = {coma(sully['rho_ble'], 3)};
frente a proporcion de «Severo» ρ = {coma(sully['rho_sev'], 3)}.
`ClimSST` frente a proporcion de «Severo» ρ = {coma(sully['rho_clim'], 3)}.
`SSTA_Standard_Deviation` frente a «Severo» ρ = {coma(sully['rho_ssta'], 3)} (signo opuesto
a la varianza absoluta; no replica el coeficiente protector de Sully sobre anomalías).

Figura: `reports/figures/contraste_sully.png`.

## 2. Transferencia geografica: Caribe + apendice polinesio → resto

Entrenamiento: ecorregiones del Gran Caribe y reino *Eastern Indo-Pacific* (Polinesia,
Hawai, Line, Phoenix, Marshall). Ese reino no es el *Central Indo-Pacific* de Spalding.
n = {coma(meta['n_geo_train'], 0)}, sitios {coma(meta['sitios_geo_train'], 0)},
prevalencia «Severo» {coma(100 * meta['prev_geo_train'], 1)} %.
Composicion: {coma(meta['n_geo_caribe'], 0)} Tropical Atlantic ({coma(100 * meta['pct_geo_caribe'], 0)} %)
y {coma(meta['n_geo_eip'], 0)} Eastern Indo-Pacific ({coma(100 * meta['pct_geo_eip'], 0)} %).
Prueba: el resto del corpus. n = {coma(meta['n_geo_test'], 0)}, sitios {coma(meta['sitios_geo_test'], 0)},
prevalencia {coma(100 * meta['prev_geo_test'], 1)} %. `Ocean_Name` se excluye: la dummy
Pacifico se compartiria entre Polinesia (train) y la Gran Barrera (test).

{filas_md(geo)}

AOA (TreeSHAP) del bosque entrenado en Caribe + Eastern Indo-Pacific: {coma(aoa['pct_dentro'], 1)} %
de los puntos de prueba dentro del umbral. DI mediano {coma(aoa['di_mediano'])}.
CRW gana F1; la logistica gana PR-AUC.

## 3. Transferencia temporal: 2010-2017 → 2018-2020

El CSV no contiene 2021 ni anos posteriores (maximo 2020, n = 90 ese ano). El ancla
honesta del pedido «2010-2021 y los siguientes» es entrenar en 2010-2017 —ultimo ano de
la ventana de Sully— y evaluar 2018-2020, posterior a esa publicacion. No sustituye al
corte 2013-2020 como test termico: ninguno de los 49 «Severo» de prueba alcanza DHW >= 4.

Entrenamiento: n = {coma(meta['n_tmp_train'], 0)}, sitios {coma(meta['sitios_tmp_train'], 0)},
prevalencia {coma(100 * meta['prev_tmp_train'], 1)} %.
Prueba 2018-2020: n = {coma(meta['n_tmp_test'], 0)}, sitios {coma(meta['sitios_tmp_test'], 0)},
prevalencia {coma(100 * meta['prev_tmp_test'], 1)} %. El 100 % de esa prueba es Reef_Check.
Sitios de prueba que ya aparecian en 2010-2017: {coma(meta['sitios_solape'], 0)} de
{coma(meta['sitios_tmp_test'], 0)}. Severos en sitios ya vistos: {coma(meta['sev_solape'], 0)}
de {coma(meta['sev_tmp_test'], 0)}.

### Todas las observaciones 2018-2020

{filas_md(temporal)}

### Solo sitios no observados en 2010-2017

{filas_md(temporal_nuevos)}

Figura: `reports/figures/transferencia_dominio.png`.

## Reproducibilidad

Script: `src/contraste_sully_transferencia.py`. Semilla {RANDOM_STATE}.
"""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (TABLES_DIR / "contraste_sully_transferencia.md").write_text(texto, encoding="utf-8")


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = cargar()
    print(f"Observaciones: {len(df):,} | anos {df['Date_Year'].min()}-{df['Date_Year'].max()}")

    print("\n=== Contraste Sully ===")
    sully = contraste_sully(df)
    figura_sully(sully)

    print("\n=== Caribe + Pacifico Central -> resto ===")
    geo_tr = mascara_caribe_pacifico(df)
    tr, te = df.loc[geo_tr], df.loc[~geo_tr]
    print(f"  train {len(tr):,} | test {len(te):,}")
    geo = pd.DataFrame(evaluar_bloque(tr, te, con_cuenca=False))
    print("  AOA TreeSHAP...")
    aoa = aoa_porcentaje(tr, te)
    print(f"  dentro del AOA {aoa['pct_dentro']:.1f}%")

    print("\n=== 2010-2017 -> 2018-2020 ===")
    tmp_tr = (df["Date_Year"] >= ANIO_TRAIN_MIN) & (df["Date_Year"] <= ANIO_TRAIN_MAX)
    tmp_te = df["Date_Year"] >= ANIO_TEST_MIN
    tr_t, te_t = df.loc[tmp_tr], df.loc[tmp_te]
    print(f"  train {len(tr_t):,} | test {len(te_t):,}")
    temporal = pd.DataFrame(evaluar_bloque(tr_t, te_t, con_cuenca=True))
    sitios_tr = set(tr_t["Site_ID"])
    te_nuevos = te_t[~te_t["Site_ID"].isin(sitios_tr)]
    print(f"  test sitios nuevos {len(te_nuevos):,}")
    temporal_nuevos = pd.DataFrame(evaluar_bloque(tr_t, te_nuevos, con_cuenca=True))

    meta = {
        "n_geo_train": int(len(tr)),
        "n_geo_test": int(len(te)),
        "sitios_geo_train": int(tr["Site_ID"].nunique()),
        "sitios_geo_test": int(te["Site_ID"].nunique()),
        "prev_geo_train": float(tr["y"].mean()),
        "prev_geo_test": float(te["y"].mean()),
        "n_geo_caribe": int((tr["Realm_Name"] == "Tropical Atlantic").sum()),
        "n_geo_eip": int((tr["Realm_Name"] == REALM_PACIFICO_CENTRAL).sum()),
        "pct_geo_caribe": float((tr["Realm_Name"] == "Tropical Atlantic").mean()),
        "pct_geo_eip": float((tr["Realm_Name"] == REALM_PACIFICO_CENTRAL).mean()),
        "aoa_geo": aoa,
        "n_tmp_train": int(len(tr_t)),
        "n_tmp_test": int(len(te_t)),
        "sitios_tmp_train": int(tr_t["Site_ID"].nunique()),
        "sitios_tmp_test": int(te_t["Site_ID"].nunique()),
        "prev_tmp_train": float(tr_t["y"].mean()),
        "prev_tmp_test": float(te_t["y"].mean()),
        "sitios_solape": int(len(sitios_tr & set(te_t["Site_ID"]))),
        "sev_tmp_test": int(te_t["y"].sum()),
        "sev_solape": int(te_t.loc[te_t["Site_ID"].isin(sitios_tr), "y"].sum()),
    }
    figura_transferencia(geo, temporal, temporal_nuevos)
    exportar(sully, geo, temporal, temporal_nuevos, meta)
    print("\nTabla:", TABLES_DIR / "contraste_sully_transferencia.md")


if __name__ == "__main__":
    main()
