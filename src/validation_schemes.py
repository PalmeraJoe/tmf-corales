"""Esquemas de validacion sobre el conjunto completo: sitio, cuenca y ecorregion.

Corrige tres limitaciones del experimento agrupado original:

1. Aquel se ejecutaba sobre la submuestra con `Reef_ID`, que coincide exactamente con el
   programa Reef_Check (vease `src/data_provenance.py`). Aqui la agrupacion se realiza por
   `Site_ID`, con cobertura del 100 %, sobre las 34 515 observaciones.
2. El Random Forest carecia de tope de profundidad, de modo que parte de la degradacion
   atribuida a la transferencia espacial era en realidad capacidad no regularizada. Se
   contrastan tres niveles de profundidad maxima.
3. Se anade `average_precision_score` sobre la clase «Severo», medida mas informativa que
   el ROC-AUC en presencia de desbalanceo (Saito y Rehmsmeier, 2015).

Incorpora ademas el bloqueo geografico que la memoria solo mencionaba: leave-one-ocean-out
y validacion cruzada por ecorregion.

Genera:
    reports/tables/validation_schemes.md
    reports/figures/esquemas_validacion.png
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, recall_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "global_bleaching_environmental.csv"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"

RANDOM_STATE = 42
N_SPLITS = 5

TERMICAS = ["SSTA", "TSA"]
ACUMULADO = ["TSA_DHW"]
CONTEXTO = ["Depth_m", "Distance_to_Shore", "ClimSST"]

CONJUNTOS: dict[str, tuple[list[str], bool]] = {
    # etiqueta: (numericas, incluye Ocean_Name)
    "Base": (TERMICAS + CONTEXTO, True),
    "Base + DHW": (TERMICAS + ACUMULADO + CONTEXTO, True),
    "Termicas + DHW (sin contexto ni cuenca)": (TERMICAS + ACUMULADO, False),
}

MODELOS = {
    "Regresion logistica": {"tipo": "lr"},
    "Random Forest (max_depth=8)": {"tipo": "rf", "max_depth": 8},
    "Random Forest (max_depth=16)": {"tipo": "rf", "max_depth": 16},
    "Random Forest (sin tope)": {"tipo": "rf", "max_depth": None},
}

CLASE_POSITIVA = "Severo"


def clasificar(v: float) -> str:
    if v < 10:
        return "Bajo"
    if v <= 30:
        return "Moderado"
    return "Severo"


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, na_values=["nd"], low_memory=False)
    df = df[df["Percent_Bleaching"].notna()].copy()
    df["Bleaching_Class"] = df["Percent_Bleaching"].apply(clasificar)
    return df


def construir(spec: dict, numericas: list[str], categoricas: list[str]) -> Pipeline:
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
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categoricas)
        )

    if spec["tipo"] == "rf":
        estimador = RandomForestClassifier(
            n_estimators=200,
            max_depth=spec["max_depth"],
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    else:
        estimador = LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE
        )

    return Pipeline([("prep", ColumnTransformer(transformadores)), ("clf", estimador)])


def metricas_pliegue(pipe: Pipeline, X_te: pd.DataFrame, y_te: pd.Series) -> dict:
    pred = pipe.predict(X_te)
    salida = {
        "f1": f1_score(y_te, pred, average="macro", zero_division=0),
        "recall_sev": recall_score(
            y_te, pred, labels=[CLASE_POSITIVA], average="macro", zero_division=0
        ),
    }
    # PR-AUC de la clase severa: exige probabilidad, no etiqueta.
    if CLASE_POSITIVA in pipe.classes_ and (y_te == CLASE_POSITIVA).any():
        col = list(pipe.classes_).index(CLASE_POSITIVA)
        proba = pipe.predict_proba(X_te)[:, col]
        salida["pr_auc"] = average_precision_score(
            (y_te == CLASE_POSITIVA).astype(int), proba
        )
    else:
        salida["pr_auc"] = float("nan")
    return salida


def evaluar_cv(
    df: pd.DataFrame, numericas: list[str], categoricas: list[str],
    spec: dict, esquema: str,
) -> dict:
    """Ejecuta un esquema de validacion cruzada y promedia las metricas por pliegue."""
    X = df[numericas + categoricas]
    y = df["Bleaching_Class"]

    if esquema == "aleatoria":
        particiones = StratifiedKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
        ).split(X, y)
    elif esquema == "sitio":
        particiones = StratifiedGroupKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
        ).split(X, y, groups=df["Site_ID"])
    elif esquema == "ecorregion":
        sub = df["Ecoregion_Name"].fillna("__desconocida__")
        particiones = GroupKFold(n_splits=N_SPLITS).split(X, y, groups=sub)
    else:
        raise ValueError(f"Esquema no reconocido: {esquema}")

    acumulado: dict[str, list[float]] = {"f1": [], "recall_sev": [], "pr_auc": []}
    for idx_tr, idx_te in particiones:
        pipe = construir(spec, numericas, categoricas)
        pipe.fit(X.iloc[idx_tr], y.iloc[idx_tr])
        for clave, valor in metricas_pliegue(pipe, X.iloc[idx_te], y.iloc[idx_te]).items():
            acumulado[clave].append(valor)

    return {
        "f1": float(np.nanmean(acumulado["f1"])),
        "f1_sd": float(np.nanstd(acumulado["f1"])),
        "recall_sev": float(np.nanmean(acumulado["recall_sev"])),
        "pr_auc": float(np.nanmean(acumulado["pr_auc"])),
    }


def evaluar_ocean_out(
    df: pd.DataFrame, numericas: list[str], categoricas: list[str], spec: dict
) -> tuple[dict, pd.DataFrame]:
    """Leave-one-ocean-out: cada cuenca actua una vez como region enteramente nueva."""
    X = df[numericas + categoricas]
    y = df["Bleaching_Class"]

    detalle = []
    for cuenca in sorted(df["Ocean_Name"].dropna().unique()):
        te = df["Ocean_Name"] == cuenca
        if te.sum() < 50 or (y[te] == CLASE_POSITIVA).sum() < 5:
            continue
        pipe = construir(spec, numericas, categoricas)
        pipe.fit(X[~te], y[~te])
        m = metricas_pliegue(pipe, X[te], y[te])
        m["Cuenca"] = cuenca
        m["n_test"] = int(te.sum())
        m["pct_severo"] = float(100 * (y[te] == CLASE_POSITIVA).mean())
        detalle.append(m)

    det = pd.DataFrame(detalle)
    resumen = {
        "f1": float(det["f1"].mean()),
        "f1_sd": float(det["f1"].std(ddof=0)),
        "recall_sev": float(det["recall_sev"].mean()),
        "pr_auc": float(det["pr_auc"].mean()),
    }
    return resumen, det


def ejecutar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    filas = []
    detalle_ocean = pd.DataFrame()

    for etiqueta, (numericas, usa_cuenca) in CONJUNTOS.items():
        categoricas = ["Ocean_Name"] if usa_cuenca else []
        for nombre_modelo, spec in MODELOS.items():
            fila: dict[str, object] = {"Conjunto": etiqueta, "Modelo": nombre_modelo}

            for esquema in ("aleatoria", "sitio"):
                r = evaluar_cv(df, numericas, categoricas, spec, esquema)
                fila[f"f1_{esquema}"] = r["f1"]
                fila[f"f1sd_{esquema}"] = r["f1_sd"]
                fila[f"rec_{esquema}"] = r["recall_sev"]
                fila[f"pr_{esquema}"] = r["pr_auc"]

            base = fila["f1_aleatoria"]
            fila["delta_rel"] = (fila["f1_sitio"] - base) / base * 100 if base else np.nan

            filas.append(fila)
            print(
                f"  {etiqueta[:34]:<34} {nombre_modelo:<28} "
                f"F1 {fila['f1_aleatoria']:.4f}->{fila['f1_sitio']:.4f} "
                f"({fila['delta_rel']:+.1f}%)  recall_sev {fila['rec_sitio']:.4f}  "
                f"PR-AUC {fila['pr_sitio']:.4f}"
            )

    return pd.DataFrame(filas), detalle_ocean


def ejecutar_geografico(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bloqueo geografico sobre la configuracion que la memoria adopta como principal."""
    numericas, usa_cuenca = CONJUNTOS["Base + DHW"]
    categoricas = ["Ocean_Name"] if usa_cuenca else []

    filas = []
    detalles = []
    for nombre_modelo, spec in MODELOS.items():
        eco = evaluar_cv(df, numericas, categoricas, spec, "ecorregion")
        # En leave-one-ocean-out la cuenca no puede figurar como predictor: seria
        # constante en test y desconocida respecto al entrenamiento.
        oce, det = evaluar_ocean_out(df, numericas, [], spec)
        det["Modelo"] = nombre_modelo
        detalles.append(det)

        filas.append(
            {
                "Modelo": nombre_modelo,
                "f1_eco": eco["f1"],
                "rec_eco": eco["recall_sev"],
                "pr_eco": eco["pr_auc"],
                "f1_oce": oce["f1"],
                "rec_oce": oce["recall_sev"],
                "pr_oce": oce["pr_auc"],
            }
        )
        print(
            f"  {nombre_modelo:<28} ecorregion F1 {eco['f1']:.4f} rec {eco['recall_sev']:.4f} | "
            f"cuenca-out F1 {oce['f1']:.4f} rec {oce['recall_sev']:.4f}"
        )

    return pd.DataFrame(filas), pd.concat(detalles, ignore_index=True)


def coma(v: float, dec: int = 4) -> str:
    return "n/d" if (v is None or (isinstance(v, float) and np.isnan(v))) else f"{v:.{dec}f}".replace(".", ",")


def figura(res: pd.DataFrame) -> None:
    datos = res[res["Conjunto"] == "Base + DHW"].copy()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.5))

    y = np.arange(len(datos))
    ax1.barh(y - 0.2, datos["f1_aleatoria"], height=0.4, label="Aleatoria",
             color="#95a5a6", edgecolor="black", linewidth=0.5)
    ax1.barh(y + 0.2, datos["f1_sitio"], height=0.4, label="Agrupada por `Site_ID`",
             color="#2980b9", edgecolor="black", linewidth=0.5)
    ax1.set_yticks(y)
    ax1.set_yticklabels(datos["Modelo"], fontsize=9)
    ax1.set_xlabel("F1-Score macro")
    ax1.set_title("Efecto del esquema de particion", fontsize=11)
    ax1.legend(fontsize=8.5)
    ax1.grid(axis="x", alpha=0.3)
    for i, (a, g) in enumerate(zip(datos["f1_aleatoria"], datos["f1_sitio"])):
        ax1.text(a + 0.008, i - 0.2, f"{a:.3f}", va="center", fontsize=8)
        ax1.text(g + 0.008, i + 0.2, f"{g:.3f}", va="center", fontsize=8)

    colores = ["#c0392b" if v < -18 else "#e67e22" if v < -8 else "#27ae60"
               for v in datos["delta_rel"]]
    ax2.barh(y, datos["delta_rel"], color=colores, edgecolor="black", linewidth=0.6)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.axvline(0, color="black", linewidth=0.9)
    ax2.set_xlabel("Variacion relativa del F1 macro (%)")
    ax2.set_title("Degradacion por capacidad del modelo", fontsize=11)
    ax2.grid(axis="x", alpha=0.3)
    for i, v in enumerate(datos["delta_rel"]):
        ax2.text(v - 0.4, i, f"{v:+.1f} %", va="center", ha="right", fontsize=8.5)
    ax2.set_xlim(min(datos["delta_rel"]) * 1.5, 3)

    fig.suptitle(
        "Validacion agrupada por emplazamiento sobre el conjunto completo (34 515 observaciones)\n"
        "Conjunto de predictores «Base + DHW»",
        fontsize=12,
    )
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "esquemas_validacion.png", dpi=300)
    plt.close(fig)


def exportar(df: pd.DataFrame, res: pd.DataFrame, geo: pd.DataFrame, det: pd.DataFrame) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    prev = 100 * (df["Bleaching_Class"] == CLASE_POSITIVA).mean()

    def bloque(conj: str) -> str:
        sub = res[res["Conjunto"] == conj]
        filas = "\n".join(
            f"| {r['Modelo']} | {coma(r['f1_aleatoria'])} | {coma(r['f1_sitio'])} | "
            f"{coma(r['delta_rel'], 1)} % | {coma(r['rec_sitio'])} | {coma(r['pr_sitio'])} |"
            for _, r in sub.iterrows()
        )
        return (
            "| Modelo | F1 aleatoria | F1 por sitio | Δ relativa | Recall «Severo» | PR-AUC «Severo» |\n"
            "|---|---|---|---|---|---|\n" + filas
        )

    geo_md = "\n".join(
        f"| {r['Modelo']} | {coma(r['f1_eco'])} | {coma(r['rec_eco'])} | {coma(r['pr_eco'])} | "
        f"{coma(r['f1_oce'])} | {coma(r['rec_oce'])} | {coma(r['pr_oce'])} |"
        for _, r in geo.iterrows()
    )

    mejor = det[det["Modelo"] == "Random Forest (max_depth=8)"]
    det_md = "\n".join(
        f"| {r['Cuenca']} | {int(r['n_test']):,} | {coma(r['pct_severo'], 2)} % | "
        f"{coma(r['f1'])} | {coma(r['recall_sev'])} |"
        for _, r in mejor.iterrows()
    )

    rf8 = res[(res["Conjunto"] == "Base + DHW") & (res["Modelo"] == "Random Forest (max_depth=8)")].iloc[0]
    rfl = res[(res["Conjunto"] == "Base + DHW") & (res["Modelo"] == "Random Forest (sin tope)")].iloc[0]
    rf16 = res[(res["Conjunto"] == "Base + DHW") & (res["Modelo"] == "Random Forest (max_depth=16)")].iloc[0]
    lr_base = res[(res["Conjunto"] == "Base") & (res["Modelo"] == "Regresion logistica")].iloc[0]
    lr_dhw = res[(res["Conjunto"] == "Base + DHW") & (res["Modelo"] == "Regresion logistica")].iloc[0]
    lr_term = res[(res["Conjunto"].str.startswith("Termicas")) & (res["Modelo"] == "Regresion logistica")].iloc[0]

    texto = f"""# Esquemas de validacion sobre el conjunto completo

Revision del experimento de transferibilidad espacial, corrigiendo tres limitaciones del
diseno original: la submuestra empleada, la capacidad no regularizada del Random Forest y la
ausencia de una metrica sensible al desbalanceo.

## Diseno

- **Datos**: {len(df):,} observaciones, {df['Site_ID'].nunique():,} emplazamientos,
  {df['Ecoregion_Name'].nunique():,} ecorregiones, {df['Ocean_Name'].nunique()} cuencas.
  Prevalencia de la clase «Severo»: {prev:.2f} %.
- **Agrupacion**: `Site_ID`, con cobertura del 100 %, en sustitucion de `Reef_ID`, que
  cubre unicamente el programa Reef_Check (vease `reports/tables/data_provenance.md`).
- **Esquemas**: `StratifiedKFold` frente a `StratifiedGroupKFold` por emplazamiento,
  ambos con {N_SPLITS} pliegues sobre identicos datos.
- **Metricas**: F1 macro, exhaustividad de la clase «Severo» y precision media
  (`average_precision_score`), equivalente al area bajo la curva de precision-exhaustividad.
  La linea base de esta ultima es la prevalencia, {prev / 100:.4f}.

## 1. Efecto del conjunto de predictores y de la capacidad del modelo

### Conjunto «Base» (sin estres acumulado)

{bloque("Base")}

### Conjunto «Base + DHW»

{bloque("Base + DHW")}

### Conjunto «Termicas + DHW», sin contexto del sitio ni cuenca

{bloque("Termicas + DHW (sin contexto ni cuenca)")}

## 2. Lectura

### La capacidad del modelo explica buena parte del colapso

Bajo el conjunto «Base + DHW» y agrupacion por emplazamiento, la degradacion del F1 macro
depende fuertemente del tope de profundidad del Random Forest:

| Configuracion | Δ relativa del F1 macro |
|---|---|
| `max_depth=8` | {coma(rf8['delta_rel'], 1)} % |
| `max_depth=16` | {coma(rf16['delta_rel'], 1)} % |
| Sin tope | {coma(rfl['delta_rel'], 1)} % |

El desplome documentado en la version anterior de este trabajo no es, por tanto, una
propiedad inevitable de los metodos de conjunto: es en parte consecuencia de haber comparado
un modelo lineal regularizado con un bosque de profundidad ilimitada. Un Random Forest
acotado conserva la mayor parte de su rendimiento al cambiar de esquema. El bosque sin tope
queda reinterpretado como lo que realmente es, una **ablacion de capacidad**.

### El estres acumulado aporta senal transferible

Bajo agrupacion por emplazamiento, la exhaustividad sobre episodios severos de la regresion
logistica evoluciona del modo siguiente:

| Configuracion | Recall «Severo» (agrupada por sitio) |
|---|---|
| Base | {coma(lr_base['rec_sitio'])} |
| Base + DHW | {coma(lr_dhw['rec_sitio'])} |
| Termicas + DHW, sin contexto ni cuenca | {coma(lr_term['rec_sitio'])} |

La mejora se obtiene **anadiendo** el indice fisiologicamente fundamentado y **retirando**
los descriptores del emplazamiento. Ello justifica la incorporacion de `TSA_DHW` al conjunto
principal de predictores y no su tratamiento como apendice.

## 3. Bloqueo geografico

Validacion por ecorregion y leave-one-ocean-out sobre el conjunto «Base + DHW». En la
segunda, `Ocean_Name` se excluye de los predictores por ser constante en cada conjunto de
prueba.

| Modelo | F1 (ecorregion) | Recall sev. | PR-AUC | F1 (cuenca nueva) | Recall sev. | PR-AUC |
|---|---|---|---|---|---|---|
{geo_md}

Detalle por cuenca, Random Forest con `max_depth=8`:

| Cuenca excluida del entrenamiento | n prueba | Severos | F1 macro | Recall «Severo» |
|---|---|---|---|---|
{det_md}

## Reproducibilidad

Script: `src/validation_schemes.py`. Semilla fija (`random_state={RANDOM_STATE}`).
El preprocesado se ajusta de forma independiente dentro de cada pliegue de entrenamiento.

*Figura: `reports/figures/esquemas_validacion.png`*
"""

    (TABLES_DIR / "validation_schemes.md").write_text(texto, encoding="utf-8")


def main() -> None:
    print("Cargando conjunto completo...")
    df = cargar()
    print(
        f"  {len(df):,} observaciones | {df['Site_ID'].nunique():,} emplazamientos | "
        f"{df['Ecoregion_Name'].nunique():,} ecorregiones"
    )
    print(df["Bleaching_Class"].value_counts(normalize=True).mul(100).round(2).to_string())

    print("\n=== Validacion aleatoria frente a agrupada por Site_ID ===")
    res, _ = ejecutar(df)

    print("\n=== Bloqueo geografico (conjunto Base + DHW) ===")
    geo, det = ejecutar_geografico(df)

    figura(res)
    exportar(df, res, geo, det)
    print("\nExportado a reports/tables/validation_schemes.md")


if __name__ == "__main__":
    main()
